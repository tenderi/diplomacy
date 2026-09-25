"""Thin repository for games under the new engine.

A game is persisted as ``games.state_json`` (the serialized ``GameState``) plus
``games.pending_orders`` (``{power: [order_str]}`` submitted-but-not-adjudicated).
The denormalised ``current_*``/``phase_code``/``status`` columns are kept in sync so
existing peripheral code (deadline scheduler, channels, listings) keeps working.

Player→power assignments live in the ``players`` table (not engine-coupled) and are
read here for convenience.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Optional

from persistence.database import GameModel, PlayerModel, utcnow_naive

__all__ = ["GameRepo", "PhaseInputsChangedError", "StaleGameError"]


def _stamp_phase_start(row: GameModel, new_phase_code: str) -> None:
    """Record when a phase began, on the write that changes ``phase_code``.

    Compared against the bot's ``client_timestamp`` on order submission (see
    ``GameModel.phase_started_at``). Stamped whenever the code actually changes,
    and also when the column is still ``NULL`` (a game created before the
    column existed gets a value on its next write of any kind), never on a
    same-phase rewrite such as ``concede`` -- a power leaving mid-phase does
    not make everyone else's in-flight orders stale.
    """
    if row.phase_started_at is None or row.phase_code != new_phase_code:
        row.phase_started_at = utcnow_naive()


def _pending(row: GameModel) -> dict[str, list[str]]:
    return {k: list(v) for k, v in dict(row.pending_orders or {}).items()}


class StaleGameError(RuntimeError):
    """Raised by ``GameRepo.save_state`` when ``expected_phase_code`` no longer
    matches the persisted row: another process advanced the phase after this
    caller loaded its state (concurrent ``process_turn``). Multiple uvicorn workers
    each have their own in-process ``asyncio.Lock``, so that lock alone cannot
    prevent two workers from adjudicating the same phase; this is the cross-process
    guard, checked at the point of writing the result back."""


class PhaseInputsChangedError(StaleGameError):
    """``save_state`` was told which board and ``pending_orders`` the adjudication
    used, and one changed before the write: an order arrived, or a power
    conceded, mid-adjudication. The phase has not moved, so the caller should
    adjudicate again rather than drop the change."""


class GameRepo:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # -- lookups ----------------------------------------------------------

    def _row(self, session: Any, game_id: str, *, lock: bool = False) -> Optional[GameModel]:
        """The game's row. ``lock=True`` takes it ``FOR UPDATE`` for the rest of
        the transaction: a check-then-write on ``phase_code`` is only a guard if
        no other transaction can change the row between the check and the write
        -- a plain read let two workers both pass the check and both write."""
        query = session.query(GameModel)
        if lock:
            query = query.with_for_update()
        row = query.filter_by(game_id=str(game_id)).first()
        if row is None:
            try:
                row = query.filter_by(id=int(game_id)).first()
            except (ValueError, TypeError):
                row = None
        return row

    def exists(self, game_id: str) -> bool:
        with self._session_factory() as session:
            return self._row(session, game_id) is not None

    def get_state_json(self, game_id: str) -> Optional[dict[str, Any]]:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            return dict(row.state_json) if row is not None and row.state_json else None

    def get_pending_orders(self, game_id: str) -> dict[str, list[str]]:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            return {} if row is None else _pending(row)

    def modify_pending_orders(
        self,
        game_id: str,
        change: Callable[[dict[str, list[str]]], dict[str, list[str]]],
        *,
        expected_phase_code: Optional[str] = None,
    ) -> dict[str, list[str]]:
        """Replace ``pending_orders`` with ``change(current)``, atomically.

        One locked read-modify-write. A read in one transaction and a write in
        another lost whichever of two concurrent
        submissions wrote first -- two players ordering at the same moment, and
        one's orders were gone. ``expected_phase_code`` refuses (``StaleGameError``)
        orders validated against a phase that has since been processed, which
        would otherwise land in the next one. Returns the new value.
        """
        with self._session_factory() as session:
            row = self._locked_row(session, game_id, expected_phase_code)
            updated = change(_pending(row))
            row.pending_orders = updated
            session.commit()
            return updated

    def modify_draw_votes(
        self,
        game_id: str,
        change: Callable[[dict[str, str]], dict[str, str]],
        *,
        expected_phase_code: Optional[str] = None,
    ) -> dict[str, str]:
        """``draw_votes`` = ``change(current)`` in one locked transaction (see
        ``modify_pending_orders``: two votes cast together lost one)."""
        with self._session_factory() as session:
            row = self._locked_row(session, game_id, expected_phase_code)
            current = {k: str(v) for k, v in dict(row.draw_votes or {}).items()}
            updated = change(current)
            row.draw_votes = updated
            session.commit()
            return updated

    def _locked_row(self, session: Any, game_id: str, expected_phase_code: Optional[str]) -> GameModel:
        row = self._row(session, game_id, lock=True)
        if row is None:
            raise ValueError(f"game {game_id} not found")
        if expected_phase_code is not None and row.phase_code != expected_phase_code:
            raise StaleGameError(
                f"game {game_id} has moved on from {expected_phase_code} to {row.phase_code}"
            )
        return row

    def get_draw_votes(self, game_id: str) -> dict[str, str]:
        """Current phase's ``{power: "yes"}`` draw votes (empty if none cast)."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None or not row.draw_votes:
                return {}
            return {k: str(v) for k, v in dict(row.draw_votes).items()}

    def get_last_resolution(self, game_id: str) -> Optional[dict[str, Any]]:
        """The most recent adjudication result, or ``None`` if the game has not yet
        processed a turn."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None or not row.last_resolution:
                return None
            return dict(row.last_resolution)

    def get_order_history(self, game_id: str) -> dict[str, dict[str, list[str]]]:
        """Per-turn submitted-order history ``{turn: {power: [order_str]}}`` (empty
        before the first processed turn)."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None or not row.order_history:
                return {}
            return {k: dict(v) for k, v in dict(row.order_history).items()}

    def get_resolution_history(self, game_id: str) -> dict[str, dict[str, Any]]:
        """Per-turn adjudication results ``{turn: resolution_dict}`` (empty before
        the first processed turn, and for turns processed before this column
        existed)."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None or not row.resolution_history:
                return {}
            return {k: dict(v) for k, v in dict(row.resolution_history).items()}

    def get_meta(self, game_id: str) -> Optional[dict[str, Any]]:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                return None
            return {
                "game_id": row.game_id,
                "map_name": row.map_name,
                "phase_code": row.phase_code,
                "status": row.status,
                "deadline": row.deadline,
                "phase_length_seconds": row.phase_length_seconds,
                "phase_started_at": row.phase_started_at,
                "current_turn": int(row.current_turn or 0),
                "dummy_powers": sorted(row.dummy_powers or []),
                "created_by_user_id": row.created_by_user_id,
                "auto_process": bool(row.auto_process),
                "wait_flags": sorted(p for p, on in (row.wait_flags or {}).items() if on),
                # W8: whether joining needs a password -- never the hash itself.
                "private": row.join_password_hash is not None,
            }

    def players(self, game_id: str) -> dict[str, dict[str, Any]]:
        """power -> {user_id, is_active} from the players table."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                return {}
            out: dict[str, dict[str, Any]] = {}
            for p in session.query(PlayerModel).filter_by(game_id=row.id).all():
                out[p.power_name] = {
                    "user_id": p.user_id,
                    "is_active": getattr(p, "is_active", True),
                }
            return out

    # -- writes -----------------------------------------------------------

    def create(
        self,
        map_name: str,
        state_json: dict[str, Any],
        phase_code: str,
        game_id: Optional[str] = None,
        phase_length_seconds: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        dummy_powers: Optional[list[str]] = None,
        auto_process: bool = False,
        join_password_hash: Optional[str] = None,
    ) -> str:
        """Insert a new game row and return its ``game_id`` string.

        When ``game_id`` is not given it defaults to the integer primary key (as a
        string), keeping ids stable and numeric for callers.
        """
        with self._session_factory() as session:
            row = GameModel(
                game_id=str(game_id) if game_id is not None else "",
                map_name=map_name,
                state_json=state_json,
                pending_orders={},
                draw_votes={},
                phase_code=phase_code,
                status="active",
                current_turn=0,
                current_year=state_json.get("year", 1901),
                current_season=str(state_json.get("season", "SPRING")).capitalize(),
                current_phase=str(state_json.get("phase_type", "MOVEMENT")).capitalize(),
                phase_started_at=utcnow_naive(),
                phase_length_seconds=phase_length_seconds,
                created_by_user_id=created_by_user_id,
                dummy_powers=sorted(dummy_powers or []),
                auto_process=auto_process,
                wait_flags={},
                join_password_hash=join_password_hash,
            )
            session.add(row)
            session.flush()  # assign the integer PK
            if game_id is None:
                row.game_id = str(row.id)
            session.commit()
            return row.game_id

    def save_state(
        self,
        game_id: str,
        state_json: dict[str, Any],
        *,
        phase_code: str,
        status: str,
        expected_phase_code: Optional[str] = None,
        expected_pending_orders: Optional[dict[str, list[str]]] = None,
        expected_state_json: Optional[dict[str, Any]] = None,
        last_resolution: Optional[dict[str, Any]] = None,
        order_history_entry: Optional[dict[str, list[str]]] = None,
        resolution_history_entry: Optional[dict[str, Any]] = None,
    ) -> None:
        """Persist the next ``GameState`` and bump the phase counter. When given, the
        adjudication ``last_resolution`` is stored for later resolution-map rendering,
        and ``order_history_entry`` (the just-adjudicated ``{power: [order_str]}``) is
        appended to ``order_history`` under the turn number being left behind.

        ``expected_phase_code``, when given, must match the row's current
        ``phase_code`` or a ``StaleGameError`` is raised instead of writing --
        the optimistic-concurrency check that keeps two concurrent
        ``process_turn`` calls (e.g. from two uvicorn workers) from both adjudicating
        the same phase and one silently clobbering the other's result. The row is
        locked for the check, so a concurrent writer waits and then sees the new
        phase instead of the one it loaded.

        ``expected_pending_orders`` and ``expected_state_json``, when given, must
        equal what is stored or ``PhaseInputsChangedError`` is raised: an order
        accepted (or a concession written) after the caller read them would
        otherwise be cleared or overwritten unadjudicated.

        A phase transition ends everything scoped to the old phase, so
        ``pending_orders``, ``draw_votes`` and ``wait_flags`` are cleared in this same
        transaction -- clearing them in a later one wiped orders already
        submitted for the *new* phase in between."""
        guarded = (
            expected_phase_code is not None
            or expected_pending_orders is not None
            or expected_state_json is not None
        )
        with self._session_factory() as session:
            row = self._row(session, game_id, lock=guarded)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            if expected_phase_code is not None and row.phase_code != expected_phase_code:
                raise StaleGameError(
                    f"game {game_id}: expected phase {expected_phase_code!r} but the "
                    f"persisted phase is {row.phase_code!r} -- already processed "
                    "concurrently"
                )
            if (expected_pending_orders is not None and _pending(row) != expected_pending_orders) or (
                expected_state_json is not None and row.state_json != expected_state_json
            ):
                raise PhaseInputsChangedError(
                    f"game {game_id}: orders or the board changed while the turn was being adjudicated"
                )
            row.pending_orders = {}
            row.draw_votes = {}
            row.wait_flags = {}
            row.state_json = state_json
            _stamp_phase_start(row, phase_code)
            row.phase_code = phase_code
            row.status = status
            if last_resolution is not None:
                row.last_resolution = last_resolution
            turn_key = str(int(row.current_turn or 0))
            if order_history_entry:
                history = dict(row.order_history or {})
                history[turn_key] = order_history_entry
                row.order_history = history
            if resolution_history_entry is not None:
                # Keyed by the turn being *left behind*, exactly like
                # ``order_history`` -- so ``order_history[t]`` and
                # ``resolution_history[t]`` are the orders and their outcomes for
                # the same turn. ``last_resolution`` still holds the newest one;
                # this is the one that survives the next turn.
                resolutions = dict(row.resolution_history or {})
                resolutions[turn_key] = resolution_history_entry
                row.resolution_history = resolutions
            row.current_turn = int(row.current_turn or 0) + 1
            row.current_year = state_json.get("year", row.current_year)
            row.current_season = str(state_json.get("season", "SPRING")).capitalize()
            row.current_phase = str(state_json.get("phase_type", "MOVEMENT")).capitalize()
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def restore_state(
        self, game_id: str, state_json: dict[str, Any], *, phase_code: str
    ) -> None:
        """Overwrite the live ``state_json``/``phase_code`` from a snapshot.

        An explicit, caller-decided rollback -- unlike ``save_state`` there is no
        staleness check; the caller has already chosen to discard whatever is
        currently live. Also clears ``pending_orders``, ``draw_votes`` and ``wait_flags`` (all
        were submitted against whatever phase was live before the restore, not
        the restored one) and takes ``status`` from the state itself, so a
        finished game restored or imported is still listed as finished.
        """
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.state_json = state_json
            _stamp_phase_start(row, phase_code)
            row.phase_code = phase_code
            row.status = str(state_json.get("status", "ACTIVE")).lower()
            row.pending_orders = {}
            row.draw_votes = {}
            row.wait_flags = {}
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def set_histories(
        self,
        game_id: str,
        *,
        order_history: Optional[dict[str, Any]] = None,
        resolution_history: Optional[dict[str, Any]] = None,
        current_turn: Optional[int] = None,
        last_resolution: Optional[dict[str, Any]] = None,
    ) -> None:
        """Overwrite the per-turn histories wholesale, for importing a saved game.

        Not part of normal play -- ``save_state`` appends one turn at a time.
        ``current_turn`` is restored alongside them so the next processed turn
        keys its history entry correctly rather than overwriting turn 0, and
        ``last_resolution`` so "what happened last turn" still has an answer.
        """
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            if order_history is not None:
                row.order_history = dict(order_history)
            if resolution_history is not None:
                row.resolution_history = dict(resolution_history)
            if current_turn is not None:
                row.current_turn = int(current_turn)
            if last_resolution is not None:
                row.last_resolution = dict(last_resolution)
            session.commit()

    def get_join_password_hash(self, game_id: str) -> Optional[str]:
        """W8: the bcrypt hash, for verifying a join. Deliberately not in ``get_meta``."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            return None if row is None else row.join_password_hash

    def set_join_password_hash(self, game_id: str, password_hash: Optional[str]) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.join_password_hash = password_hash
            session.commit()

    def set_auto_process(self, game_id: str, enabled: bool) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.auto_process = enabled
            session.commit()

    def modify_wait_flags(
        self,
        game_id: str,
        change: Callable[[set[str]], set[str]],
        *,
        expected_phase_code: Optional[str] = None,
    ) -> list[str]:
        """``wait_flags`` = ``change(current)`` in one locked transaction, refused
        (``StaleGameError``) once ``expected_phase_code`` is no longer live. Two
        flags raised together lost one -- and the turn could then auto-process
        past a player who had asked it to wait. Returns the powers now waiting."""
        with self._session_factory() as session:
            row = self._locked_row(session, game_id, expected_phase_code)
            current = {p for p, on in (row.wait_flags or {}).items() if on}
            updated = sorted(change(current))
            row.wait_flags = {p: True for p in updated}
            session.commit()
            return updated

    def set_dummy_powers(self, game_id: str, powers: list[str]) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.dummy_powers = sorted(powers)
            session.commit()

    def update_state_json(
        self,
        game_id: str,
        state_json: dict[str, Any],
        *,
        phase_code: str,
        status: str,
        expected_phase_code: Optional[str] = None,
    ) -> None:
        """Overwrite ``state_json``/``phase_code``/``status`` in place, without the
        turn-counter bump or ``pending_orders`` clearing ``save_state`` does.

        For out-of-band state mutations that are not a phase transition --
        currently only ``GameService.concede`` (a power leaving mid-phase must
        not disturb the other powers' already-submitted orders for this phase,
        nor advance the turn counter the way a real ``process_turn`` does).

        ``expected_phase_code`` guards it like ``save_state``: a concession
        computed from phase X must not be written over a board a concurrent
        ``process_turn`` already moved to phase Y -- that rolled the game back.
        """
        with self._session_factory() as session:
            row = self._row(session, game_id, lock=expected_phase_code is not None)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            if expected_phase_code is not None and row.phase_code != expected_phase_code:
                raise StaleGameError(
                    f"game {game_id}: expected phase {expected_phase_code!r} but the "
                    f"persisted phase is {row.phase_code!r} -- changed concurrently"
                )
            row.state_json = state_json
            _stamp_phase_start(row, phase_code)
            row.phase_code = phase_code
            row.status = status
            row.updated_at = datetime.now(timezone.utc)
            session.commit()
