"""New-engine game service: the server's single entry point to the rules core.

Wraps the pure engine (``game.Game`` + ``serialization`` + ``orders.parser``
+ ``orders.validation``) over ``GameRepo`` persistence. Routes, the CLI ``Server``
and DAIDE all go through this — none of them touch engine internals.

State lives as a serialized ``GameState`` in ``games.state_json``; submitted orders
accumulate in ``games.pending_orders`` until ``process_turn`` adjudicates them and
advances the phase (the phase machine inserts retreat/adjustment phases as needed).
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any, Optional

from persistence.game_repo import StaleGameError
from engine.map_loader import MapData, load_standard_map
from engine.game import Game
from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.orders.validation import validate
from engine.simple_ai import generate_orders
from engine.serialization import (
    order_from_dict,
    resolution_to_dict,
    state_from_dict,
    state_to_dict,
    unit_to_dict,
)
from engine.types import Build, GameState, GameStatus, Order, PhaseType, Waive
from server.legal_orders import adjustments_owed, powers_with_orders_to_give

__all__ = [
    "DEMO_MAP_NAME",
    "GameService",
    "GameOverError",
    "OrderError",
    "StaleGameError",
    "kind_by_province_of",
]

# The bot's demo game (``/start`` → "Try a demo game") is a standard board whose
# ``map_name`` marks it: there, and only there, the civil-disorder dummies play
# ``engine.simple_ai`` moves instead of standing still, so a solo player sees a
# board that reacts.
DEMO_MAP_NAME = "demo"


class OrderError(ValueError):
    """A submitted order was ill-formed or illegal for the current state."""


class GameOverError(ValueError):
    """A write was attempted against a game that has already ended.

    Deliberately *not* an ``OrderError`` subclass: routes map ``OrderError`` to
    404 ("game not found"), and a finished game is very much found. Callers map
    this to 409 -- the request conflicts with the game's state.
    """


class GameService:
    def __init__(self, repo: Any, map: Optional[MapData] = None) -> None:
        self._repo = repo
        self._map = map or load_standard_map()

    @property
    def map(self) -> MapData:
        return self._map

    # -- lifecycle --------------------------------------------------------

    def create_game(
        self,
        game_id: Optional[str] = None,
        map_name: str = "standard",
        phase_length_seconds: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        dummy_powers: Optional[list[str]] = None,
        auto_process: bool = False,
        join_password_hash: Optional[str] = None,
    ) -> str:
        """Create a fresh standard game at its opening movement phase.

        ``phase_length_seconds`` is stored for later use by
        ``POST /games/{id}/deadline`` (a caller may arm a deadline from it
        explicitly); it does not itself set a deadline, and nothing re-arms one
        automatically after a turn is processed.

        Returns the game's id (the integer PK as a string when not supplied).
        """
        game = Game(map=self._map, state=_initial_state(self._map))
        return self._repo.create(
            map_name=map_name,
            state_json=state_to_dict(game.state),
            phase_code=game.state.phase_name,
            game_id=game_id,
            phase_length_seconds=phase_length_seconds,
            created_by_user_id=created_by_user_id,
            dummy_powers=_check_dummy_set(dummy_powers or [], self._map),
            auto_process=auto_process,
            join_password_hash=join_password_hash,
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
        self, game_id: str, power: str, order_strings: list[str], *, merge: bool = False
    ) -> list[dict[str, Any]]:
        """Validate and store ``power``'s orders for the current phase.

        ``merge=False`` (the web client, which always sends the full set)
        replaces the power's orders. ``merge=True`` (every bot path) adds these
        to what is already there, a new order for a unit replacing that unit's
        old one: the bot sends orders one at a time (``/selectunit``, or
        several ``/order`` messages), and until this each one silently wiped
        the ones before it -- a player ordered three units and only the last
        moved. An order that fails validation never displaces a good one.

        Returns one result dict per order (``{order, ok, reason}``). Raises
        ``OrderError`` if the game does not exist and ``GameOverError`` if it
        has ended. Individual illegal orders are reported (``ok=False``) but do
        not abort the batch.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        _require_active(game, game_id)
        power = power.upper()
        state = game.state

        # Stored strings are re-parsed at adjudication, where the A/F letter
        # decides whether a destination coast survives (an army's is dropped).
        # Without the board's real kinds, ``F MAO - SPA/NC`` was stored as
        # ``A MAO - SPA/NC``, came back as a coastless move and was VOID.
        kinds = kind_by_province_of(state)
        results: list[dict[str, Any]] = []
        accepted: list[str] = []
        accepted_keys: set[str] = set()
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
                accepted.append(format_order(order, kinds))
                key = _order_key(order)
                if key is not None:
                    accepted_keys.add(key)
                results.append({"order": raw, "ok": True, "reason": None})
            else:
                results.append({"order": raw, "ok": False, "reason": vr.reason})

        pending = self._repo.get_pending_orders(game_id)
        if merge:
            kept = []
            for existing in pending.get(power, []):
                key = _order_key(parse_order(existing, power=power, map=self._map))
                if key is None or key not in accepted_keys:
                    kept.append(existing)
            accepted = kept + accepted
        pending[power] = accepted
        self._repo.set_pending_orders(game_id, pending)
        return results

    def _orders_complete(self, power: str, state: GameState, orders: list[str]) -> bool:
        """Has ``power`` given an order to everything that must act this phase?

        Movement: every unit. Retreat: every dislodged unit. Adjustment: as
        many builds/waives, or disbands, as it is owed (``adjustments_owed``:
        builds capped at the sites it can actually build on). W10's auto-processing
        waits for this, not merely for *an* order: bot players send orders one
        at a time, and the turn must not run after the first. (A unit meant to
        stand still needs an explicit hold.)
        """
        parsed = [parse_order(o, power=power, map=self._map) for o in orders]
        ordered = {_order_key(o) for o in parsed} - {None}
        if state.phase_type == PhaseType.MOVEMENT:
            return {u.location.province for u in state.units_of(power)} <= ordered
        if state.phase_type == PhaseType.RETREAT:
            return {du.unit.location.province for du in state.dislodged if du.unit.power == power} <= ordered
        return len(parsed) >= adjustments_owed(self._map, state, power)

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
        _require_active(game, game_id)

        pending = self._repo.get_pending_orders(game_id)
        pending = {**pending, **self._demo_ai_orders(game_id, game, pending)}
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
        # last_resolution_view's docstring / kind_by_province_of).
        kind_by_province = kind_by_province_of(game.state)
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
            # Same dict as ``last_resolution``, but kept per turn so it survives
            # the next ``process_turn``.
            resolution_history_entry=resolution_dict,
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

    def active_powers(self, game_id: str) -> Optional[frozenset[str]]:
        """Powers still in the game: non-eliminated, with at least one unit.
        ``None`` if the game doesn't exist.

        The same population ``_draw_quorum`` computes for draw-vote quorum,
        exposed publicly so other majority-vote mechanisms (deadline-change
        proposals) use the identical definition of "who's still playing"
        rather than a second, driftable one.
        """
        game = self.load(game_id)
        if game is None:
            return None
        return self._draw_quorum(game, game_id)

    def _draw_quorum(self, game: Game, game_id: str) -> frozenset[str]:
        """Powers that must vote yes for a draw: non-eliminated, with a unit, and
        not a civil-disorder dummy (W9) -- a dummy has nobody to vote."""
        eliminated = game.eliminated_powers()
        dummies = self.dummy_powers(game_id)
        return frozenset(
            u.power for u in game.state.units if u.power not in eliminated and u.power not in dummies
        )

    def dummy_powers(self, game_id: str) -> frozenset[str]:
        """Powers played by civil disorder in this game (W9); empty if none."""
        meta = self._repo.get_meta(game_id) or {}
        return frozenset(meta.get("dummy_powers") or ())

    # -- W10: auto-processing and wait flags ------------------------------------

    def set_auto_process(self, game_id: str, enabled: bool) -> None:
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        _require_active(game, game_id)
        self._repo.set_auto_process(game_id, enabled)

    def join_password_hash(self, game_id: str) -> Optional[str]:
        """W8: the private game's password hash (``None`` for an open game)."""
        return self._repo.get_join_password_hash(game_id)

    def set_join_password_hash(self, game_id: str, password_hash: Optional[str]) -> None:
        if not self.exists(game_id):
            raise OrderError(f"game {game_id} not found")
        self._repo.set_join_password_hash(game_id, password_hash)

    def wait_flags(self, game_id: str) -> frozenset[str]:
        """Powers whose players asked the table to wait this phase."""
        meta = self._repo.get_meta(game_id) or {}
        return frozenset(meta.get("wait_flags") or ())

    def set_wait(self, game_id: str, power: str, waiting: bool) -> list[str]:
        """Raise or lower ``power``'s wait flag. Returns the powers now waiting."""
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        _require_active(game, game_id)
        flags = set(self.wait_flags(game_id))
        if waiting:
            flags.add(power.upper())
        else:
            flags.discard(power.upper())
        self._repo.set_wait_flags(game_id, sorted(flags))
        return sorted(flags)

    def clear_wait_flags(self, game_id: str) -> None:
        if self.wait_flags(game_id):
            self._repo.set_wait_flags(game_id, [])

    def _demo_ai_orders(self, game_id: str, game: Game, pending: dict[str, list[str]]) -> dict[str, list[str]]:
        """In a demo game, orders for every dummy that has none: ``simple_ai``
        moves, seeded by game and phase so a replay of the same turn is the same
        turn. Other games' dummies submit nothing and play by civil disorder.
        They join the turn's order history like anyone's, so the player can see
        what the other powers did."""
        if (self._repo.get_meta(game_id) or {}).get("map_name") != DEMO_MAP_NAME:
            return {}
        kinds = kind_by_province_of(game.state)
        rng = random.Random(f"{game_id}:{game.state.phase_name}")  # game moves, not security
        ai: dict[str, list[str]] = {}
        for power in self.dummy_powers(game_id):
            if power in pending:
                continue
            generated = generate_orders(self._map, game.state, power, rng)
            if generated:
                ai[power] = [format_order(o, kinds) for o in generated]
        return ai

    def ready_to_auto_process(self, game_id: str) -> bool:
        """W10: auto-process is on, the game is running, every power with
        something to order this phase has submitted (dummies are never waited
        on, W9), and no one's wait flag is up. A flag from a dummy's seat cannot
        exist -- only a seated player can raise one."""
        meta = self._repo.get_meta(game_id)
        if meta is None or not meta.get("auto_process") or meta.get("status") != "active":
            return False
        if meta.get("wait_flags"):
            return False
        status = self.orders_status(game_id)
        return status is not None and not status["missing"] and not status["incomplete"]

    def set_dummy(self, game_id: str, power: str, dummy: bool) -> list[str]:
        """Make ``power`` a civil-disorder dummy, or open it again. Returns the new set.

        Only a seat nobody holds can become a dummy; the caller checks who may do
        this (the game's creator, or an admin). Raises ``OrderError`` for an
        unknown game or power, a held seat, or a change that would leave no
        human power at all; ``GameOverError`` on a finished game.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        _require_active(game, game_id)
        power = power.upper()
        if power not in self._map.home_centers:
            raise OrderError(f"Unknown power {power}")
        current = set(self.dummy_powers(game_id))
        if dummy:
            seat = self._repo.players(game_id).get(power)
            if seat is not None and seat.get("user_id") is not None:
                raise OrderError(f"{power} is held by a player; only an empty seat can be a dummy")
            current.add(power)
        else:
            current.discard(power)
        updated = _check_dummy_set(sorted(current), self._map)
        self._repo.set_dummy_powers(game_id, updated)
        return updated

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
        _require_active(game, game_id)
        power = power.upper()

        votes = self._repo.get_draw_votes(game_id)
        if vote:
            votes[power] = "yes"
        else:
            votes.pop(power, None)
        self._repo.set_draw_votes(game_id, votes)

        required = self._draw_quorum(game, game_id)
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
        required = self._draw_quorum(game, game_id)
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
        powers play on. Removes all of ``power``'s units from the board **and
        releases its supply centers** (they become neutral, exactly like the
        unowned centers at game start, until someone occupies one at a Fall
        settle). Both halves matter: until ``v2.7.71`` only the units went, on
        the theory that the centers would sit "unclaimed" -- but ownership
        persists until a unit physically stands there, so at the next Winter
        the engine owed the conceded power ``centers - 0`` builds,
        ``orders_status`` waited on the player who had just quit, and
        ``BUILD A PAR`` walked them back into a game the web client had told
        them they could not undo leaving. With no units and no centers,
        ``Game.eliminated_powers()`` reports ``power`` eliminated at once.

        Written via a dedicated ``GameRepo.update_state_json`` (not
        ``save_state``): conceding mid-phase is not a phase transition, so it
        must not bump the turn counter or clear the *other* powers'
        already-submitted pending orders for this phase.
        """
        game = self.load(game_id)
        if game is None:
            raise OrderError(f"game {game_id} not found")
        _require_active(game, game_id)
        power = power.upper()

        remaining_units = frozenset(u for u in game.state.units if u.power != power)
        remaining_ownership = {p: o for p, o in game.state.ownership.items() if o != power}
        new_state = replace(game.state, units=remaining_units, ownership=remaining_ownership)
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
            "dummy_powers": meta.get("dummy_powers") or [],
            "auto_process": bool(meta.get("auto_process")),
            "wait_flags": meta.get("wait_flags") or [],
            "private": bool(meta.get("private")),
            # Who may end a turn early (clients show "Process turn" only to them).
            "created_by_user_id": meta.get("created_by_user_id"),
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
        kind_by_province = kind_by_province_of(state)
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

    def resolution_history(self, game_id: str) -> dict[str, dict[str, Any]]:
        """Per-turn adjudication results ``{turn: resolution_dict}``.

        The outcome half of ``order_history``: what each submitted order actually
        did. Empty for turns processed before the column existed.
        """
        return self._repo.get_resolution_history(game_id)

    def orders_status(self, game_id: str) -> Optional[dict[str, Any]]:
        """Which powers have submitted orders for the current phase, and which
        still have something to order and haven't. ``None`` if the game doesn't
        exist. A power counts as "submitted" once it has a ``pending_orders`` entry
        for this phase, even an empty one (0 valid orders still means it acted).

        ``active_powers`` is phase-shaped (``powers_with_orders_to_give``): in a
        retreat phase only powers with a dislodged unit are expected to act, in
        an adjustment phase only powers with a build or disband to make. Before
        this, every power with a unit was "missing" in every phase, so a retreat
        phase told the one player who had to retreat that six others were still
        being waited on, and ``require_all`` blocked on them."""
        sj = self._repo.get_state_json(game_id)
        if sj is None:
            return None
        state = state_from_dict(sj)
        submitted = set(self._repo.get_pending_orders(game_id).keys())
        # A civil-disorder dummy (W9) is never waited on: it submits nothing and
        # the engine plays it by the civil-disorder rules.
        dummies = self.dummy_powers(game_id)
        active_powers = sorted(p for p in powers_with_orders_to_give(self._map, state) if p not in dummies)
        pending = self._repo.get_pending_orders(game_id)
        return {
            "phase": state.phase_name,
            "active_powers": active_powers,
            "submitted": sorted(submitted),
            "missing": sorted(p for p in active_powers if p not in submitted),
            # Submitted something, but not an order for everything that must act.
            "incomplete": sorted(
                p for p in active_powers
                if p in submitted and not self._orders_complete(p, state, pending.get(p, []))
            ),
            # W10: who asked to wait, and whether the turn runs by itself.
            "waiting": sorted(self.wait_flags(game_id)),
            "auto_process": bool((self._repo.get_meta(game_id) or {}).get("auto_process")),
        }

    def meta(self, game_id: str) -> Optional[dict[str, Any]]:
        """The game's denormalized row fields -- ``map_name``, ``phase_code``,
        ``status``, ``deadline``, ``phase_length_seconds``, ``phase_started_at``,
        ``current_turn`` -- without loading or parsing the board.

        For callers that need scheduling or bookkeeping facts rather than game
        state (the post-turn path, the deadline scheduler).
        """
        return self._repo.get_meta(game_id)

    def state_json(self, game_id: str) -> Optional[dict[str, Any]]:
        """The raw serialized ``GameState`` (``engine.serialization.state_to_dict``
        shape), for callers that need to persist it verbatim (e.g. snapshots)
        rather than the view shape from ``view()``."""
        return self._repo.get_state_json(game_id)

    def import_histories(
        self,
        game_id: str,
        *,
        order_history: Optional[dict[str, Any]] = None,
        resolution_history: Optional[dict[str, Any]] = None,
        current_turn: Optional[int] = None,
    ) -> None:
        """Restore per-turn histories onto an imported game (see ``routes/archive.py``)."""
        self._repo.set_histories(
            game_id,
            order_history=order_history,
            resolution_history=resolution_history,
            current_turn=current_turn,
        )

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
        self.check_state_json(state_json)
        self._repo.restore_state(game_id, state_json, phase_code=phase_code)

    @staticmethod
    def check_state_json(state_json: dict[str, Any]) -> None:
        """Raise ``ValueError`` unless ``state_json`` parses as a ``GameState``.

        ``state_from_dict`` reports a missing field as ``KeyError`` and a wrongly
        typed one as ``TypeError``; callers only need to know the payload is bad.
        """
        try:
            state_from_dict(state_json)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"not a game state ({type(e).__name__}: {e})") from e


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


def _order_key(order: Order) -> Optional[str]:
    """The province an order is "for": its unit's, or a build's site. Two
    orders with the same key cannot both stand -- the later replaces the
    earlier when merging. ``WAIVE`` has none (a power may waive several)."""
    if isinstance(order, Waive):
        return None
    if isinstance(order, Build):
        return order.location.province
    return order.unit.province  # type: ignore[attr-defined]


def _check_dummy_set(powers: list[str], map_data: Optional[MapData] = None) -> list[str]:
    """Normalize a dummy set and refuse one that leaves no human power (W9)."""
    known = frozenset((map_data or load_standard_map()).home_centers)
    normalized = sorted({p.upper() for p in powers})
    unknown = [p for p in normalized if p not in known]
    if unknown:
        raise OrderError(f"Unknown power(s): {', '.join(unknown)}")
    if len(normalized) >= len(known):
        raise OrderError("At least one power must be left for a human player")
    return normalized


def _require_active(game: Game, game_id: str) -> None:
    """Refuse a write once the game is over.

    Every write path (orders, turn processing, draw votes, concession) used to
    go straight through on a COMPLETED game: orders were accepted and shown as
    pending, ``process_turn`` "succeeded" with an empty resolution -- and the
    route around it then snapshotted, reset the deadline and DMed every player
    "turn processed" each time -- a draw vote was "recorded", and a concession
    removed the power's units from the *final* board.
    """
    if game.state.status is GameStatus.COMPLETED:
        winners = sorted(game.state.winners or ())
        outcome = (
            f"won by {winners[0]}" if len(winners) == 1
            else f"drawn between {', '.join(winners)}" if winners
            else "over"
        )
        raise GameOverError(f"game {game_id} is {outcome}; no further orders or votes are accepted")


def _dislodged_view(du: Any) -> dict[str, Any]:
    return {
        "unit": unit_to_dict(du.unit),
        "attacker_origin": du.attacker_origin,
        "retreats": [str(loc) for loc in du.retreats],
    }


def kind_by_province_of(state: GameState) -> dict[str, str]:
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
