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
from typing import Any, Optional

from persistence.database import GameModel, PlayerModel

__all__ = ["GameRepo", "StaleGameError"]


class StaleGameError(RuntimeError):
    """Raised by ``GameRepo.save_state`` when ``expected_phase_code`` no longer
    matches the persisted row: another process advanced the phase after this
    caller loaded its state (concurrent ``process_turn``). Multiple uvicorn workers
    each have their own in-process ``asyncio.Lock``, so that lock alone cannot
    prevent two workers from adjudicating the same phase; this is the cross-process
    guard, checked at the point of writing the result back."""


class GameRepo:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # -- lookups ----------------------------------------------------------

    def _row(self, session: Any, game_id: str) -> Optional[GameModel]:
        row = session.query(GameModel).filter_by(game_id=str(game_id)).first()
        if row is None:
            try:
                row = session.query(GameModel).filter_by(id=int(game_id)).first()
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
            if row is None or not row.pending_orders:
                return {}
            return {k: list(v) for k, v in dict(row.pending_orders).items()}

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
        last_resolution: Optional[dict[str, Any]] = None,
        order_history_entry: Optional[dict[str, list[str]]] = None,
    ) -> None:
        """Persist the next ``GameState`` and bump the phase counter. When given, the
        adjudication ``last_resolution`` is stored for later resolution-map rendering,
        and ``order_history_entry`` (the just-adjudicated ``{power: [order_str]}``) is
        appended to ``order_history`` under the turn number being left behind.

        ``expected_phase_code``, when given, must match the row's current
        ``phase_code`` or a ``StaleGameError`` is raised instead of writing --
        the optimistic-concurrency check that keeps two concurrent
        ``process_turn`` calls (e.g. from two uvicorn workers) from both adjudicating
        the same phase and one silently clobbering the other's result."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            if expected_phase_code is not None and row.phase_code != expected_phase_code:
                raise StaleGameError(
                    f"game {game_id}: expected phase {expected_phase_code!r} but the "
                    f"persisted phase is {row.phase_code!r} -- already processed "
                    "concurrently"
                )
            row.state_json = state_json
            row.phase_code = phase_code
            row.status = status
            if last_resolution is not None:
                row.last_resolution = last_resolution
            if order_history_entry:
                turn_key = str(int(row.current_turn or 0))
                history = dict(row.order_history or {})
                history[turn_key] = order_history_entry
                row.order_history = history
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
        currently live. Also clears ``pending_orders`` and ``draw_votes`` (both
        were submitted against whatever phase was live before the restore, not
        the restored one) and marks the game ``active`` (a restore always
        targets a playable phase).
        """
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.state_json = state_json
            row.phase_code = phase_code
            row.status = "active"
            row.pending_orders = {}
            row.draw_votes = {}
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def set_pending_orders(self, game_id: str, pending: dict[str, list[str]]) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.pending_orders = pending
            session.commit()

    def set_draw_votes(self, game_id: str, votes: dict[str, str]) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.draw_votes = votes
            session.commit()

    def update_state_json(
        self, game_id: str, state_json: dict[str, Any], *, phase_code: str, status: str
    ) -> None:
        """Overwrite ``state_json``/``phase_code``/``status`` in place, without the
        turn-counter bump or ``pending_orders`` clearing ``save_state`` does.

        For out-of-band state mutations that are not a phase transition --
        currently only ``GameService.concede`` (a power leaving mid-phase must
        not disturb the other powers' already-submitted orders for this phase,
        nor advance the turn counter the way a real ``process_turn`` does).
        """
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.state_json = state_json
            row.phase_code = phase_code
            row.status = status
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def list_game_ids(self) -> list[str]:
        with self._session_factory() as session:
            return [r.game_id for r in session.query(GameModel).all()]
