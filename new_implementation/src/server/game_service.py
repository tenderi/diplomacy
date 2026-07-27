"""New-engine game service: the server's single entry point to the rules core.

Wraps the pure engine (``game.Game`` + ``serialization`` + ``orders.parser``
+ ``orders.validation``) over ``GameRepo`` persistence. Routes, the CLI ``Server``
and DAIDE all go through this — none of them touch engine internals.

State lives as a serialized ``GameState`` in ``games.state_json``; submitted orders
accumulate in ``games.pending_orders`` until ``process_turn`` adjudicates them and
advances the phase (the phase machine inserts retreat/adjustment phases as needed).
"""

from __future__ import annotations

from typing import Any, Optional

from engine.map_loader import MapData, load_standard_map
from engine.game import Game
from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.orders.validation import validate
from engine.serialization import (
    resolution_to_dict,
    state_from_dict,
    state_to_dict,
    unit_to_dict,
)
from engine.types import GameState, PhaseType

__all__ = ["GameService", "OrderError"]


class OrderError(ValueError):
    """A submitted order was ill-formed or illegal for the current state."""


class GameService:
    def __init__(self, repo: Any, map: Optional[MapData] = None) -> None:
        self._repo = repo
        self._map = map or load_standard_map()

    @property
    def map(self) -> MapData:
        return self._map

    # -- lifecycle --------------------------------------------------------

    def create_game(self, game_id: Optional[str] = None, map_name: str = "standard") -> str:
        """Create a fresh standard game at its opening movement phase.

        Returns the game's id (the integer PK as a string when not supplied).
        """
        game = Game(map=self._map, state=_initial_state(self._map))
        return self._repo.create(
            map_name=map_name,
            state_json=state_to_dict(game.state),
            phase_code=game.state.phase_name,
            game_id=game_id,
        )

    def load(self, game_id: str) -> Optional[Game]:
        sj = self._repo.get_state_json(game_id)
        if sj is None:
            return None
        return Game(map=self._map, state=state_from_dict(sj))

    def exists(self, game_id: str) -> bool:
        return self._repo.exists(game_id)

    # -- orders -----------------------------------------------------------

    def submit_orders(
        self, game_id: str, power: str, order_strings: list[str]
    ) -> list[dict[str, Any]]:
        """Validate and store ``power``'s orders for the current phase.

        Returns one result dict per order (``{order, ok, reason}``). Raises
        ``OrderError`` only if the game does not exist. Individual illegal orders
        are reported (``ok=False``) but do not abort the batch.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        power = power.upper()
        state = game.state

        results: list[dict[str, Any]] = []
        accepted: list[str] = []
        for raw in order_strings:
            raw = raw.strip()
            if not raw:
                continue
            try:
                order = parse_order(raw, power=power, map=self._map)
            except OrderParseError as exc:
                results.append({"order": raw, "ok": False, "reason": f"parse error: {exc}"})
                continue
            vr = validate(order, state, self._map)
            if vr.ok:
                accepted.append(format_order(order))
                results.append({"order": raw, "ok": True, "reason": None})
            else:
                results.append({"order": raw, "ok": False, "reason": vr.reason})

        pending = self._repo.get_pending_orders(game_id)
        pending[power] = accepted
        self._repo.set_pending_orders(game_id, pending)
        return results

    def clear_orders(self, game_id: str, power: str) -> None:
        pending = self._repo.get_pending_orders(game_id)
        pending.pop(power.upper(), None)
        self._repo.set_pending_orders(game_id, pending)

    # -- turn processing --------------------------------------------------

    def process_turn(self, game_id: str) -> dict[str, Any]:
        """Adjudicate all pending orders, advance the phase, persist, clear orders."""
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")

        pending = self._repo.get_pending_orders(game_id)
        orders = []
        for power, strings in pending.items():
            for s in strings:
                try:
                    orders.append(parse_order(s, power=power.upper(), map=self._map))
                except OrderParseError:
                    continue

        resolution, next_game = game.adjudicate(orders)

        # Record the orders players actually submitted (with truthful A/F letters
        # against the pre-adjudication board) before pending is cleared.
        history_entry = {
            power: strings for power, strings in
            self._humanize_orders(pending, game.state).items() if strings
        }

        resolution_dict = resolution_to_dict(resolution)
        self._repo.save_state(
            game_id,
            state_to_dict(next_game.state),
            phase_code=next_game.state.phase_name,
            status=next_game.state.status.value.lower(),
            last_resolution=resolution_dict,
            order_history_entry=history_entry,
        )
        self._repo.set_pending_orders(game_id, {})
        return {
            "phase": next_game.state.phase_name,
            "status": next_game.state.status.value,
            "resolution": resolution_dict,
        }

    # -- views ------------------------------------------------------------

    def view(self, game_id: str) -> Optional[dict[str, Any]]:
        """The clean, GameState-native API representation of a game."""
        sj = self._repo.get_state_json(game_id)
        if sj is None:
            return None
        meta = self._repo.get_meta(game_id) or {}
        state = state_from_dict(sj)
        players = self._repo.players(game_id)
        pending = self._repo.get_pending_orders(game_id)

        units_by_power: dict[str, list[dict[str, Any]]] = {}
        for u in sorted(state.units, key=lambda x: str(x.location)):
            units_by_power.setdefault(u.power, []).append(unit_to_dict(u))

        return {
            "game_id": str(game_id),
            "map_name": meta.get("map_name", "standard"),
            "phase": state.phase_name,
            "year": state.year,
            "season": state.season.value,
            "phase_type": state.phase_type.value,
            "status": state.status.value,
            "units": [unit_to_dict(u) for u in sorted(state.units, key=lambda x: str(x.location))],
            "units_by_power": units_by_power,
            "ownership": dict(state.ownership),
            "supply_centers": dict(state.ownership),
            "dislodged": [_dislodged_view(du) for du in state.dislodged],
            "contested": sorted(state.contested),
            "players": players,
            "orders": self._humanize_orders(pending, state),
        }

    def _humanize_orders(
        self, pending: dict[str, list[str]], state: GameState
    ) -> dict[str, list[str]]:
        """Rewrite stored order strings so unit letters match the board.

        Orders are stored via ``format_order``, which infers ``A``/``F`` from coast
        presence — so a fleet at a non-split-coast province is stored as ``A``. For
        display, reparse each order and reformat it against the current units so the
        letter is truthful. Anything that fails to reparse is left untouched.
        """
        kind_by_province = {u.province: u.kind.value for u in state.units}
        out: dict[str, list[str]] = {}
        for power, strings in pending.items():
            display: list[str] = []
            for s in strings:
                try:
                    order = parse_order(s, power=power.upper(), map=self._map)
                    display.append(format_order(order, kind_by_province))
                except OrderParseError:
                    display.append(s)
            out[power] = display
        return out

    def pending_orders_parsed(self, game_id: str) -> dict[str, list[Any]]:
        """Current pending orders as parsed ``Order`` objects, keyed by power.

        Ill-formed stored orders are skipped (they were validated at submit time, so
        this is defensive). Used by the orders-map renderer.
        """
        out: dict[str, list[Any]] = {}
        for power, strings in self._repo.get_pending_orders(game_id).items():
            orders: list[Any] = []
            for s in strings:
                try:
                    orders.append(parse_order(s, power=power.upper(), map=self._map))
                except OrderParseError:
                    continue
            if orders:
                out[power] = orders
        return out

    def last_resolution(self, game_id: str) -> Optional[dict[str, Any]]:
        """The most recent adjudication result (``resolution_to_dict``), or ``None``."""
        return self._repo.get_last_resolution(game_id)

    def order_history(self, game_id: str) -> dict[str, dict[str, list[str]]]:
        """Per-turn submitted-order history ``{turn: {power: [order_str]}}``."""
        return self._repo.get_order_history(game_id)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _initial_state(map: MapData) -> GameState:
    return GameState(
        year=map.start_year,
        season=map.start_season,
        phase_type=PhaseType.MOVEMENT,
        units=map.starting_units,
        ownership=dict(map.initial_ownership),
    )


def _dislodged_view(du: Any) -> dict[str, Any]:
    return {
        "unit": unit_to_dict(du.unit),
        "attacker_origin": du.attacker_origin,
        "retreats": [str(loc) for loc in du.retreats],
    }
