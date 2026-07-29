"""New-engine game service: the server's single entry point to the rules core.

Wraps the pure engine (``game.Game`` + ``serialization`` + ``orders.parser``
+ ``orders.validation``) over ``GameRepo`` persistence. Routes, the CLI ``Server``
and DAIDE all go through this — none of them touch engine internals.

State lives as a serialized ``GameState`` in ``games.state_json``; submitted orders
accumulate in ``games.pending_orders`` until ``process_turn`` adjudicates them and
advances the phase (the phase machine inserts retreat/adjustment phases as needed).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from persistence.game_repo import StaleGameError
from engine.map_loader import MapData, load_standard_map
from engine.game import Game
from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.orders.validation import validate
from engine.serialization import (
    order_from_dict,
    resolution_to_dict,
    state_from_dict,
    state_to_dict,
    unit_to_dict,
)
from engine.types import GameState, PhaseType

__all__ = ["GameService", "OrderError", "StaleGameError"]


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
        """Adjudicate all pending orders, advance the phase, persist, clear orders.

        Raises ``StaleGameError`` if another process already advanced this game's
        phase between the ``load`` above and the write below (the phase this call
        loaded no longer matches what's persisted) -- the caller (an HTTP route)
        should surface that as 409 rather than silently re-adjudicating or
        clobbering the concurrent result.
        """
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

        # Decorate each result with a truthful order_str, computed against the
        # *pre-adjudication* board (game.state) -- the only place a fleet at a
        # non-split-coast province can still be told apart from an army, since
        # a successful move relocates the unit and a resolution fetched after a
        # reload has no other way to recover which kind made the order (see
        # last_resolution_view's docstring / _kind_by_province).
        kind_by_province = _kind_by_province(game.state)
        resolution_dict = resolution_to_dict(resolution)
        resolution_dict["results"] = [
            {**r, "order_str": format_order(order_from_dict(r["order"]), kind_by_province)}
            for r in resolution_dict["results"]
        ]
        self._repo.save_state(
            game_id,
            state_to_dict(next_game.state),
            phase_code=next_game.state.phase_name,
            status=next_game.state.status.value.lower(),
            expected_phase_code=game.state.phase_name,
            last_resolution=resolution_dict,
            order_history_entry=history_entry,
        )
        self._repo.set_pending_orders(game_id, {})
        # A draw vote is scoped to the phase it was cast in, same as pending
        # orders -- once the phase advances, last phase's votes no longer mean
        # anything for the new phase.
        self._repo.set_draw_votes(game_id, {})
        return {
            "phase": next_game.state.phase_name,
            "status": next_game.state.status.value,
            "resolution": resolution_dict,
        }

    # -- draw / concede -----------------------------------------------------

    def _draw_quorum(self, game: Game) -> frozenset[str]:
        """Powers that must vote yes for a draw: non-eliminated, with a unit."""
        eliminated = game.eliminated_powers()
        return frozenset(u.power for u in game.state.units if u.power not in eliminated)

    def submit_draw_vote(self, game_id: str, power: str, vote: bool) -> dict[str, Any]:
        """Record ``power``'s yes/no draw vote for the current phase.

        Only yes-votes are stored (``vote=False`` removes any existing yes). If
        this vote completes quorum -- every non-eliminated power that still has
        a unit has now voted yes -- the game is immediately finalized as a draw
        (``Game.draw()``) and persisted via the same ``save_state`` path
        ``process_turn`` uses, no separate explicit "finalize" call required.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        power = power.upper()

        votes = self._repo.get_draw_votes(game_id)
        if vote:
            votes[power] = "yes"
        else:
            votes.pop(power, None)
        self._repo.set_draw_votes(game_id, votes)

        required = self._draw_quorum(game)
        yes = {p for p in votes if p in required}
        quorum_reached = bool(required) and required.issubset(yes)

        if quorum_reached:
            drawn = game.draw()
            self._repo.save_state(
                game_id,
                state_to_dict(drawn.state),
                phase_code=drawn.state.phase_name,
                status=drawn.state.status.value.lower(),
                expected_phase_code=game.state.phase_name,
            )
            self._repo.set_pending_orders(game_id, {})
            self._repo.set_draw_votes(game_id, {})
            return {
                "status": "completed",
                "game_status": drawn.state.status.value,
                "winners": sorted(drawn.state.winners or ()),
                "votes": sorted(yes),
                "required": sorted(required),
                "quorum_reached": True,
            }

        return {
            "status": "recorded",
            "game_status": game.state.status.value,
            "votes": sorted(yes),
            "required": sorted(required),
            "quorum_reached": False,
        }

    def get_draw_votes(self, game_id: str) -> Optional[dict[str, Any]]:
        """Who's voted yes to draw this phase, how many are needed, and whether
        quorum is already reached. ``None`` if the game does not exist."""
        game = self.load(game_id)
        if game is None:
            return None
        votes = self._repo.get_draw_votes(game_id)
        required = self._draw_quorum(game)
        yes = {p for p in votes if p in required}
        return {
            "phase": game.state.phase_name,
            "game_status": game.state.status.value,
            "required": sorted(required),
            "votes": sorted(yes),
            "missing": sorted(required - yes),
            "quorum_reached": bool(required) and required.issubset(yes),
        }

    def concede(self, game_id: str, power: str) -> dict[str, Any]:
        """``power`` voluntarily leaves the game.

        Distinct from a draw: this does **not** end the game -- the remaining
        powers play on. Removes all of ``power``'s units from the board;
        supply-center ownership is left untouched (SC ownership is only ever
        recomputed by the engine's normal Fall-settle capture rule, which will
        naturally leave a unit-less power's centers unclaimed until someone
        occupies them -- duplicating that logic here would risk diverging from
        it). Once ``power`` also holds no centers, ``Game.eliminated_powers()``
        reports it as eliminated on the next check, same as any other wipeout.

        Written via a dedicated ``GameRepo.update_state_json`` (not
        ``save_state``): conceding mid-phase is not a phase transition, so it
        must not bump the turn counter or clear the *other* powers'
        already-submitted pending orders for this phase.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        power = power.upper()

        remaining_units = frozenset(u for u in game.state.units if u.power != power)
        new_state = replace(game.state, units=remaining_units)
        self._repo.update_state_json(
            game_id,
            state_to_dict(new_state),
            phase_code=new_state.phase_name,
            status=new_state.status.value.lower(),
        )
        # The conceding power has nothing left to order or vote on this phase.
        self.clear_orders(game_id, power)
        votes = self._repo.get_draw_votes(game_id)
        if votes.pop(power, None) is not None:
            self._repo.set_draw_votes(game_id, votes)

        eliminated = power in Game(map=self._map, state=new_state).eliminated_powers()
        return {
            "status": "ok",
            "power": power,
            "game_status": new_state.status.value,
            "eliminated": eliminated,
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
            "winners": sorted(state.winners) if state.winners is not None else None,
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
        kind_by_province = _kind_by_province(state)
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

    def last_resolution_view(self, game_id: str) -> Optional[dict[str, Any]]:
        """The most recent adjudication result, decorated so a client can answer
        "what happened to my orders?" without re-deriving adjudication.

        Passes the canonical ``resolution_to_dict`` shape (``engine.serialization``)
        through unchanged and adds one convenience field per result: a flattened
        ``power`` (already nested inside ``order``, but tedious to dig out per
        result). ``order_str`` is truthful (a fleet renders as ``F`` even at a
        non-split-coast province) because ``process_turn`` already computed it
        against the pre-adjudication board and persisted it onto each result --
        ``Game.history`` does not survive a ``GameRepo`` round-trip
        (``state_to_dict``/``state_from_dict`` only cover ``GameState``, not
        ``Game``), so that board is unrecoverable here and must be captured at
        adjudication time instead. Only a resolution persisted before this fix
        would lack it; that falls back to ``format_order`` without a board map,
        which is round-trip safe but can print a fleet as ``A`` -- see
        ``format_order``'s docstring. Returns ``None`` if the game doesn't exist;
        ``{"results": []}`` if it exists but no turn has been processed yet.
        """
        if not self.exists(game_id):
            return None
        resolution = self._repo.get_last_resolution(game_id)
        if resolution is None:
            return {"results": []}
        results: list[dict[str, Any]] = []
        for r in resolution.get("results", []):
            order = order_from_dict(r["order"])
            order_str = r.get("order_str") or format_order(order)
            results.append({**r, "power": order.power, "order_str": order_str})
        return {"results": results}

    def order_history(self, game_id: str) -> dict[str, dict[str, list[str]]]:
        """Per-turn submitted-order history ``{turn: {power: [order_str]}}``."""
        return self._repo.get_order_history(game_id)

    def orders_status(self, game_id: str) -> Optional[dict[str, Any]]:
        """Which powers have submitted orders for the current phase, and which
        still control at least one unit and haven't. ``None`` if the game doesn't
        exist. A power counts as "submitted" once it has a ``pending_orders`` entry
        for this phase, even an empty one (0 valid orders still means it acted)."""
        sj = self._repo.get_state_json(game_id)
        if sj is None:
            return None
        state = state_from_dict(sj)
        submitted = set(self._repo.get_pending_orders(game_id).keys())
        active_powers = sorted({u.power for u in state.units})
        return {
            "phase": state.phase_name,
            "active_powers": active_powers,
            "submitted": sorted(submitted),
            "missing": sorted(p for p in active_powers if p not in submitted),
        }

    def state_json(self, game_id: str) -> Optional[dict[str, Any]]:
        """The raw serialized ``GameState`` (``engine.serialization.state_to_dict``
        shape), for callers that need to persist it verbatim (e.g. snapshots)
        rather than the view shape from ``view()``."""
        return self._repo.get_state_json(game_id)

    def restore_snapshot(
        self, game_id: str, state_json: dict[str, Any], phase_code: str
    ) -> None:
        """Roll a game's live state back to a previously captured snapshot.

        Validates that ``state_json`` actually parses as a ``GameState`` before
        writing it -- raises ``ValueError`` on a malformed payload rather than
        leaving the game in a state ``load()`` can't read back. Also clears
        pending orders (see ``GameRepo.restore_state``): whatever was pending was
        submitted against the phase being discarded.
        """
        state_from_dict(state_json)  # raises ValueError if malformed; result unused
        self._repo.restore_state(game_id, state_json, phase_code=phase_code)


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


def _kind_by_province(state: GameState) -> dict[str, str]:
    """province -> "A"/"F" for every unit on the board, standing or dislodged.

    Feeds ``format_order``'s ``kind_by_province`` so displayed unit letters are
    truthful instead of inferred from coast presence (see ``format_order``'s
    docstring). Dislodged units are included too -- during a retreat phase the
    unit a ``Retreat`` order names has already been removed from ``state.units``
    and lives only in ``state.dislodged``, so leaving it out would silently
    reintroduce the same mislabeling for retreat orders.
    """
    out = {u.province: u.kind.value for u in state.units}
    for du in state.dislodged:
        out[du.unit.province] = du.unit.kind.value
    return out
