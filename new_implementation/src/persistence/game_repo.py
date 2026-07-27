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

__all__ = ["GameRepo"]


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
    ) -> None:
        """Persist the next ``GameState`` and bump the phase counter."""
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.state_json = state_json
            row.phase_code = phase_code
            row.status = status
            row.current_turn = int(row.current_turn or 0) + 1
            row.current_year = state_json.get("year", row.current_year)
            row.current_season = str(state_json.get("season", "SPRING")).capitalize()
            row.current_phase = str(state_json.get("phase_type", "MOVEMENT")).capitalize()
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def set_pending_orders(self, game_id: str, pending: dict[str, list[str]]) -> None:
        with self._session_factory() as session:
            row = self._row(session, game_id)
            if row is None:
                raise ValueError(f"game {game_id} not found")
            row.pending_orders = pending
            session.commit()

    def list_game_ids(self) -> list[str]:
        with self._session_factory() as session:
            return [r.game_id for r in session.query(GameModel).all()]
