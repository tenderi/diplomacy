"""
Database service for Diplomacy game engine.

This module provides database operations using the new data models and schema
to ensure proper data integrity and consistency.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
from .database import (
    GameModel, PlayerModel, OrderModel, TurnHistoryModel, MapSnapshotModel, MessageModel, UserModel, LinkCodeModel, PasswordResetTokenModel,
    TournamentModel, TournamentGameModel, TournamentPlayerModel,
    SpectatorModel,
    get_session_factory,
    utcnow_naive,
)


class DatabaseService:
    """Service for database operations"""
    
    def __init__(self, database_url: str):
        self.session_factory = get_session_factory(database_url)
        self.logger = logging.getLogger("diplomacy.persistence.database_service")
    
    # --- Users ---
    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[UserModel]:
        with self.session_factory() as session:
            # telegram_id is stored as VARCHAR in database, query as string
            return session.query(UserModel).filter_by(telegram_id=str(telegram_id)).first()

    def get_user_by_id(self, user_id: int) -> Optional[UserModel]:
        with self.session_factory() as session:
            return session.query(UserModel).filter_by(id=user_id).first()

    def create_user(self, telegram_id: str, full_name: Optional[str] = None, username: Optional[str] = None) -> UserModel:
        with self.session_factory() as session:
            user = UserModel(
                telegram_id=str(telegram_id),
                full_name=full_name or str(telegram_id),
                username=username,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        with self.session_factory() as session:
            return session.query(UserModel).filter_by(email=email.strip().lower()).first()

    def create_user_with_password(
        self,
        email: str,
        password_hash: str,
        full_name: Optional[str] = None,
    ) -> UserModel:
        with self.session_factory() as session:
            user = UserModel(
                email=email.strip().lower(),
                password_hash=password_hash,
                full_name=full_name or email.split("@")[0],
                telegram_id=None,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user

    def set_user_telegram_id(self, user_id: int, telegram_id: str) -> None:
        with self.session_factory() as session:
            user = session.query(UserModel).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            user.telegram_id = str(telegram_id)
            session.commit()

    def unlink_telegram(self, user_id: int) -> None:
        """Clear telegram_id for the user (unlink Telegram account)."""
        with self.session_factory() as session:
            user = session.query(UserModel).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            user.telegram_id = None
            session.commit()

    def create_link_code(
        self, user_id: int, ttl_minutes: int = 10, code: Optional[str] = None
    ) -> Tuple[str, datetime]:
        import secrets as _secrets
        with self.session_factory() as session:
            if code is None:
                # 6 bytes → 8 base64url chars (~48 bits entropy)
                code = _secrets.token_urlsafe(6)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
            link_code = LinkCodeModel(
                user_id=user_id,
                code=code,
                expires_at=expires_at,
            )
            session.add(link_code)
            session.commit()
            return code, expires_at

    def consume_link_code(self, code: str) -> Optional[int]:
        with self.session_factory() as session:
            now = datetime.now(timezone.utc)
            link_code = (
                session.query(LinkCodeModel)
                .filter_by(code=code.strip())
                .filter(LinkCodeModel.expires_at > now)
                .first()
            )
            if not link_code:
                return None
            user_id = link_code.user_id
            session.delete(link_code)
            session.commit()
            return user_id

    def create_password_reset_token(self, user_id: int, ttl_minutes: int = 60) -> str:
        """Create a one-time password reset token. Returns the token string."""
        import secrets
        with self.session_factory() as session:
            token = secrets.token_urlsafe(48)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
            record = PasswordResetTokenModel(
                user_id=user_id,
                token=token,
                expires_at=expires_at,
            )
            session.add(record)
            session.commit()
            return token

    def consume_password_reset_token(self, token: str) -> Optional[int]:
        """Validate token, delete it, return user_id or None."""
        with self.session_factory() as session:
            now = datetime.now(timezone.utc)
            record = (
                session.query(PasswordResetTokenModel)
                .filter_by(token=token.strip())
                .filter(PasswordResetTokenModel.expires_at > now)
                .first()
            )
            if not record:
                return None
            user_id = record.user_id
            session.delete(record)
            session.commit()
            return user_id

    def set_user_password(self, user_id: int, password_hash: str) -> None:
        """Update password_hash for the user."""
        with self.session_factory() as session:
            user = session.query(UserModel).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            user.password_hash = password_hash
            session.commit()

    def get_user_count(self) -> int:
        with self.session_factory() as session:
            return session.query(UserModel).count()
    
    # --- Channel Management ---
    def link_game_to_channel(
        self, 
        game_id: str, 
        channel_id: str, 
        channel_name: Optional[str] = None,
        settings: Optional[Dict[str, Any]] = None
    ) -> None:
        """Link a Telegram channel to a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, game_id)
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            game_model.channel_id = channel_id
            if channel_name:
                # Store channel name in settings if needed
                current_settings = game_model.channel_settings or {}
                if settings:
                    current_settings.update(settings)
                current_settings["channel_name"] = channel_name
                game_model.channel_settings = current_settings
            elif settings:
                current_settings = game_model.channel_settings or {}
                current_settings.update(settings)
                game_model.channel_settings = current_settings
            
            game_model.updated_at = datetime.now(timezone.utc)
            session.commit()
    
    def unlink_game_from_channel(self, game_id: str) -> None:
        """Unlink a Telegram channel from a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, game_id)
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            game_model.channel_id = None
            game_model.channel_settings = None
            game_model.updated_at = datetime.now(timezone.utc)
            session.commit()
    
    def get_game_channel_info(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get channel information for a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, game_id)
            if not game_model or not game_model.channel_id:
                return None
            
            settings = game_model.channel_settings or {}
            
            return {
                "channel_id": game_model.channel_id,
                "channel_name": settings.get("channel_name"),
                "settings": settings
            }
    
    def update_game_channel_settings(self, game_id: str, settings: Dict[str, Any]) -> None:
        """Update channel settings for a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, game_id)
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            if not game_model.channel_id:
                raise ValueError(f"Game {game_id} is not linked to a channel")
            
            current_settings = game_model.channel_settings or {}
            current_settings.update(settings)
            game_model.channel_settings = current_settings
            game_model.updated_at = datetime.now(timezone.utc)
            session.commit()

    # --- Players ---
    def create_player(self, game_id: int, power: str, user_id: Optional[int] = None) -> PlayerModel:
        with self.session_factory() as session:
            player = PlayerModel(game_id=game_id, power_name=power, user_id=user_id, is_active=True)
            session.add(player)
            session.commit()
            session.refresh(player)
            return player

    def get_players_by_game_id(self, game_id: int) -> List[PlayerModel]:
        with self.session_factory() as session:
            return session.query(PlayerModel).filter_by(game_id=game_id).all()

    def get_player_telegram_ids(self, game_id: int) -> List[str]:
        """Every linked Telegram ID among a game's players, for notification fan-out.

        ``telegram_id`` lives on ``UserModel``, **not** ``PlayerModel`` -- which is
        exactly the trap that made ``api/shared.py``'s ``notify_players`` a silent
        no-op for the whole life of the notification system: it iterated
        ``PlayerModel`` rows and read ``getattr(player, 'telegram_id', None)``, a
        column that does not exist there, so the guard was unconditionally false
        and no Telegram DM was ever sent for any event. This method exists so no
        caller has to remember the join.

        Players with no linked user, or a user who has not linked Telegram, are
        omitted rather than yielding ``None``.
        """
        with self.session_factory() as session:
            rows = (
                session.query(UserModel.telegram_id)
                .join(PlayerModel, PlayerModel.user_id == UserModel.id)
                .filter(PlayerModel.game_id == game_id)
                .filter(UserModel.telegram_id.isnot(None))
                .all()
            )
        return [str(r[0]) for r in rows if r[0] is not None and str(r[0]) != ""]

    def get_players_by_user_id(self, user_id: int) -> List[PlayerModel]:
        with self.session_factory() as session:
            # Only return active players (user_id is not None and is_active is True)
            return session.query(PlayerModel).filter_by(user_id=user_id, is_active=True).all()

    def get_player_by_game_id_and_user_id(self, game_id: int, user_id: int) -> Optional[PlayerModel]:
        with self.session_factory() as session:
            return session.query(PlayerModel).filter_by(game_id=game_id, user_id=user_id).first()

    def get_player_by_game_id_and_power(self, game_id: int | str, power: str) -> Optional[PlayerModel]:
        """Get player by game_id (can be numeric id or string game_id) and power."""
        with self.session_factory() as session:
            # If game_id is string, look up the numeric id first
            if isinstance(game_id, str):
                from sqlalchemy import text
                # Use raw SQL with explicit cast to ensure string comparison
                result = session.execute(
                    text("SELECT id FROM games WHERE game_id = CAST(:game_id AS VARCHAR)"),
                    {"game_id": game_id}
                ).first()
                if not result:
                    return None
                game_id_int = result.id
            else:
                game_id_int = game_id
            return session.query(PlayerModel).filter_by(game_id=game_id_int, power_name=power).first()

    def get_player_count_by_game_id(self, game_id: int) -> int:
        with self.session_factory() as session:
            return session.query(PlayerModel).filter_by(game_id=game_id).count()

    def update_player_is_active(self, player_id: int, is_active: bool) -> None:
        with self.session_factory() as session:
            player = session.query(PlayerModel).filter_by(id=player_id).first()
            if player is not None:
                player.is_active = is_active
                session.commit()

    # --- Games ---
    def get_game_by_id(self, game_id: int) -> Optional[GameModel]:
        with self.session_factory() as session:
            return session.query(GameModel).filter_by(id=game_id).first()

    def _get_game_model_by_game_id_string(self, session: Session, game_id: str) -> Optional[GameModel]:
        """Helper to get GameModel by game_id string using raw SQL (handles VARCHAR column properly)."""
        from sqlalchemy import text
        game_id_str = str(game_id)
        # Use raw SQL with explicit CAST to ensure string comparison works
        result = session.execute(
            text("SELECT id FROM games WHERE game_id = CAST(:game_id AS VARCHAR)"),
            {"game_id": game_id_str}
        ).first()
        if result:
            # result is a Row object, access by index or column name
            numeric_id = result[0] if hasattr(result, '__getitem__') else getattr(result, 'id', None)
            if numeric_id:
                return session.query(GameModel).filter_by(id=numeric_id).first()
        return None

    def get_game_by_game_id(self, game_id: str | int) -> Optional[GameModel]:
        """Get game by game_id string (not numeric id)."""
        with self.session_factory() as session:
            return self._get_game_model_by_game_id_string(session, str(game_id))
    
    def get_game_current_turn(self, game_id: str | int) -> int:
        """Get the current_turn for a game by game_id string. Returns 0 if not found.
        This method queries fresh to ensure we get the latest committed value."""
        with self.session_factory() as session:
            # Query directly for current_turn column to get fresh value
            result = session.query(GameModel.current_turn).filter(
                GameModel.game_id == str(game_id)
            ).first()
            if result:
                return result[0]
            return 0

    def get_all_games(self) -> List[GameModel]:
        with self.session_factory() as session:
            return session.query(GameModel).all()

    def get_game_count(self) -> int:
        with self.session_factory() as session:
            return session.query(GameModel).count()

    def get_games_with_deadlines_and_active_status(self) -> List[GameModel]:
        """Get all active games that may have deadlines."""
        with self.session_factory() as session:
            return session.query(GameModel).filter_by(status='active').all()

    def update_game_deadline(self, game_id: int, deadline: Optional[datetime]) -> None:
        """
        Update the deadline for a game.

        Args:
            game_id: The game ID to update
            deadline: The new deadline (or None to clear the deadline)

        ``games.deadline`` is a plain ``TIMESTAMP`` (no timezone) column: Postgres
        silently converts a tz-aware value to the connection's session timezone and
        stores it as naive wall-clock time on write. Every reader (the scheduler,
        ``get_deadline``) then reinterprets a naive value as UTC -- correct only if
        it was actually stored as UTC. A non-UTC session timezone (e.g. a local dev
        Postgres defaulting to the machine's zone) would otherwise silently shift
        every deadline by the zone offset. Normalize to naive UTC here so the
        round trip is correct regardless of session timezone configuration.
        """
        if deadline is not None and deadline.tzinfo is not None:
            deadline = deadline.astimezone(timezone.utc).replace(tzinfo=None)
        with self.session_factory() as session:
            game = session.query(GameModel).filter_by(id=game_id).first()
            if game:
                game.deadline = deadline
                session.commit()
    
    def increment_game_current_turn(self, game_id: int | str) -> None:
        """Increment the current_turn for a game. Used for order history tracking.
        
        Args:
            game_id: Can be either the numeric id (int) or game_id string
        """
        with self.session_factory() as session:
            # Try by numeric id first, then by game_id string
            if isinstance(game_id, int):
                game = session.query(GameModel).filter_by(id=game_id).first()
            else:
                game = self._get_game_model_by_game_id_string(session, str(game_id))
            if game:
                old_turn = getattr(game, 'current_turn', 0)
                game.current_turn = old_turn + 1
                session.flush()  # Ensure changes are written before commit
                session.commit()
                self.logger.debug(f"increment_game_current_turn: game_id={game_id}, old_turn={old_turn}, new_turn={game.current_turn}")
            else:
                self.logger.warning(f"increment_game_current_turn: game not found for game_id={game_id}")

    # --- Orders ---
    def get_orders_by_player_id(self, player_id: int) -> List[OrderModel]:
        with self.session_factory() as session:
            player = session.query(PlayerModel).filter_by(id=player_id).first()
            if not player:
                return []
            return session.query(OrderModel).filter_by(game_id=player.game_id, power_name=player.power_name).all()
    
    def get_order_history(self, game_id: str | int) -> List[OrderModel]:
        """Get all orders for a game across all turns."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return []
            return session.query(OrderModel).filter_by(game_id=game_model.id).order_by(OrderModel.turn_number, OrderModel.power_name).all()

    def delete_orders_by_player_id(self, player_id: int) -> None:
        with self.session_factory() as session:
            player = session.query(PlayerModel).filter_by(id=player_id).first()
            if player:
                session.query(OrderModel).filter_by(game_id=player.game_id, power_name=player.power_name).delete()
                session.commit()

    def check_if_player_has_orders_for_turn(self, player_id: int, turn: int) -> bool:
        with self.session_factory() as session:
            player = session.query(PlayerModel).filter_by(id=player_id).first()
            if not player:
                return False
            return session.query(OrderModel).filter_by(game_id=player.game_id, power_name=player.power_name, turn_number=turn).count() > 0

    def delete_all_orders(self) -> None:
        with self.session_factory() as session:
            session.query(OrderModel).delete()
            session.commit()

    # --- Messages ---
    def create_message(self, game_id: int, sender_user_id: int, recipient_power: Optional[str], text: str):
        with self.session_factory() as session:
            msg = MessageModel(
                game_id=game_id,
                sender_user_id=sender_user_id,
                recipient_power=recipient_power,
                text=text,
                timestamp=utcnow_naive(),
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            return msg

    def get_messages_by_game_id(self, game_id: int):
        with self.session_factory() as session:
            return session.query(MessageModel).filter_by(game_id=game_id)

    def delete_all_messages(self) -> None:
        with self.session_factory() as session:
            session.query(MessageModel).delete()
            session.commit()

    # --- Snapshots & History ---
    def create_game_snapshot(
        self,
        game_id: int,
        turn: int,
        year: int,
        season: str,
        phase: str,
        phase_code: str,
        game_state: Dict[str, Any],
        state_json: Optional[Dict[str, Any]] = None,
    ) -> MapSnapshotModel:
        """Record a point-in-time snapshot.

        ``game_state`` is the view shape (used for the ``units``/``supply_centers``
        columns, kept for ``/history`` and ``/replay``). ``state_json``, when given,
        is the raw serialized ``GameState`` (``engine.serialization.state_to_dict``)
        -- the only shape ``restore_game_snapshot`` can rebuild a ``Game`` from.
        """
        units = game_state.get('units', {})
        supply_centers = game_state.get('supply_centers', {})
        with self.session_factory() as session:
            snap = MapSnapshotModel(
                game_id=game_id,
                turn_number=turn,
                phase_code=phase_code,
                units=units,
                supply_centers=supply_centers,
                state_json=state_json,
            )
            # dynamic attribute for compatibility
            setattr(snap, 'phase', phase)
            session.add(snap)
            session.commit()
            session.refresh(snap)
            return snap

    def get_game_snapshot_by_game_id_and_turn(self, game_id: int, turn: int) -> Optional[MapSnapshotModel]:
        with self.session_factory() as session:
            return session.query(MapSnapshotModel).filter_by(game_id=game_id, turn_number=turn).first()

    def get_latest_game_snapshot_by_game_id_and_phase_code(self, game_id: int, phase_code: str) -> Optional[MapSnapshotModel]:
        with self.session_factory() as session:
            return session.query(MapSnapshotModel).filter_by(game_id=game_id, phase_code=phase_code).order_by(MapSnapshotModel.id.desc()).first()

    def update_game_snapshot_map_image_path(self, snapshot_id: int, map_path: str) -> None:
        with self.session_factory() as session:
            snap = session.query(MapSnapshotModel).filter_by(id=snapshot_id).first()
            if snap:
                snap.map_image_path = map_path
                session.commit()

    def get_game_snapshots_by_game_id(self, game_id: int) -> List[MapSnapshotModel]:
        with self.session_factory() as session:
            return session.query(MapSnapshotModel).filter_by(game_id=game_id).all()

    def get_game_snapshot_by_id(self, id: int, game_id: Optional[int] = None) -> Optional[MapSnapshotModel]:
        with self.session_factory() as session:
            q = session.query(MapSnapshotModel).filter_by(id=id)
            if game_id is not None:
                q = q.filter_by(game_id=game_id)
            return q.first()

    def get_game_snapshots_with_old_map_images(self, cutoff_time: datetime) -> List[MapSnapshotModel]:
        """
        Get all game snapshots with map images older than the cutoff time.
        
        Args:
            cutoff_time: Datetime threshold - snapshots older than this will be returned
            
        Returns:
            List of MapSnapshotModel objects with map_image_path older than cutoff_time
        """
        with self.session_factory() as session:
            return session.query(MapSnapshotModel).filter(
                MapSnapshotModel.map_image_path.isnot(None),
                MapSnapshotModel.created_at < cutoff_time
            ).all()

    def delete_all_game_snapshots(self) -> None:
        with self.session_factory() as session:
            session.query(MapSnapshotModel).delete()
            session.commit()

    def delete_all_game_history(self) -> None:
        with self.session_factory() as session:
            session.query(TurnHistoryModel).delete()
            session.commit()

    def delete_all_players(self) -> None:
        with self.session_factory() as session:
            session.query(PlayerModel).delete()
            session.commit()

    def delete_all_games(self) -> None:
        with self.session_factory() as session:
            session.query(GameModel).delete()
            session.commit()

    # --- Channel Analytics ---
    def log_channel_analytics_event(
        self,
        game_id: str | int,
        channel_id: str,
        event_type: str,
        event_subtype: Optional[str] = None,
        user_id: Optional[int] = None,
        power: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an analytics event for channel engagement tracking.
        
        Args:
            game_id: Game ID (string or int)
            channel_id: Telegram channel ID
            event_type: Type of event ('message_posted', 'player_activity', 'order_submitted', 'vote_cast', 'message_read')
            event_subtype: Optional subtype ('map', 'broadcast', 'battle_results', 'dashboard', 'notification')
            user_id: Optional user ID who triggered the event
            power: Optional power associated with the event
            metadata: Optional additional event data (message_id, response_time, etc.)
        """
        from .database import ChannelAnalyticsModel
        
        with self.session_factory() as session:
            # Get game model to ensure it exists
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                self.logger.warning(f"Cannot log analytics: game {game_id} not found")
                return
            
            analytics_event = ChannelAnalyticsModel(
                game_id=game_model.id,
                channel_id=channel_id,
                event_type=event_type,
                event_subtype=event_subtype,
                user_id=user_id,
                power=power,
                event_data=metadata or {}
            )
            
            session.add(analytics_event)
            session.commit()

    def get_channel_analytics(
        self,
        game_id: str | int,
        channel_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get analytics events for a game/channel.
        
        Args:
            game_id: Game ID (string or int)
            channel_id: Optional channel ID filter
            event_type: Optional event type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of analytics event dictionaries
        """
        from .database import ChannelAnalyticsModel
        
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return []
            
            query = session.query(ChannelAnalyticsModel).filter(
                ChannelAnalyticsModel.game_id == game_model.id
            )
            
            if channel_id:
                query = query.filter(ChannelAnalyticsModel.channel_id == channel_id)
            if event_type:
                query = query.filter(ChannelAnalyticsModel.event_type == event_type)
            if start_date:
                query = query.filter(ChannelAnalyticsModel.created_at >= start_date)
            if end_date:
                query = query.filter(ChannelAnalyticsModel.created_at <= end_date)
            
            events = query.order_by(ChannelAnalyticsModel.created_at.desc()).all()
            
            return [
                {
                    "id": event.id,
                    "game_id": str(game_id),
                    "channel_id": event.channel_id,
                    "event_type": event.event_type,
                    "event_subtype": event.event_subtype,
                    "user_id": event.user_id,
                    "power": event.power,
                    "event_data": event.event_data or {},
                    "created_at": event.created_at.isoformat() if event.created_at else None
                }
                for event in events
            ]

    def get_channel_analytics_summary(
        self,
        game_id: str | int,
        channel_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated analytics summary for a game/channel.
        
        Args:
            game_id: Game ID (string or int)
            channel_id: Optional channel ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary with aggregated metrics
        """
        from .database import ChannelAnalyticsModel
        from sqlalchemy import func
        
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return {
                    "total_events": 0,
                    "events_by_type": {},
                    "events_by_subtype": {},
                    "unique_users": 0,
                    "message_count": 0,
                    "player_activity_count": 0
                }
            
            query = session.query(ChannelAnalyticsModel).filter(
                ChannelAnalyticsModel.game_id == game_model.id
            )
            
            if channel_id:
                query = query.filter(ChannelAnalyticsModel.channel_id == channel_id)
            if start_date:
                query = query.filter(ChannelAnalyticsModel.created_at >= start_date)
            if end_date:
                query = query.filter(ChannelAnalyticsModel.created_at <= end_date)
            
            # Total events
            total_events = query.count()
            
            # Events by type
            events_by_type = {}
            type_counts = session.query(
                ChannelAnalyticsModel.event_type,
                func.count(ChannelAnalyticsModel.id).label('count')
            ).filter(
                ChannelAnalyticsModel.game_id == game_model.id
            )
            if channel_id:
                type_counts = type_counts.filter(ChannelAnalyticsModel.channel_id == channel_id)
            if start_date:
                type_counts = type_counts.filter(ChannelAnalyticsModel.created_at >= start_date)
            if end_date:
                type_counts = type_counts.filter(ChannelAnalyticsModel.created_at <= end_date)
            type_counts = type_counts.group_by(ChannelAnalyticsModel.event_type).all()
            
            for event_type, count in type_counts:
                events_by_type[event_type] = count
            
            # Events by subtype
            events_by_subtype = {}
            subtype_counts = session.query(
                ChannelAnalyticsModel.event_subtype,
                func.count(ChannelAnalyticsModel.id).label('count')
            ).filter(
                ChannelAnalyticsModel.game_id == game_model.id,
                ChannelAnalyticsModel.event_subtype.isnot(None)
            )
            if channel_id:
                subtype_counts = subtype_counts.filter(ChannelAnalyticsModel.channel_id == channel_id)
            if start_date:
                subtype_counts = subtype_counts.filter(ChannelAnalyticsModel.created_at >= start_date)
            if end_date:
                subtype_counts = subtype_counts.filter(ChannelAnalyticsModel.created_at <= end_date)
            subtype_counts = subtype_counts.group_by(ChannelAnalyticsModel.event_subtype).all()
            
            for event_subtype, count in subtype_counts:
                events_by_subtype[event_subtype] = count
            
            # Unique users
            unique_users = session.query(
                func.count(func.distinct(ChannelAnalyticsModel.user_id))
            ).filter(
                ChannelAnalyticsModel.game_id == game_model.id,
                ChannelAnalyticsModel.user_id.isnot(None)
            )
            if channel_id:
                unique_users = unique_users.filter(ChannelAnalyticsModel.channel_id == channel_id)
            if start_date:
                unique_users = unique_users.filter(ChannelAnalyticsModel.created_at >= start_date)
            if end_date:
                unique_users = unique_users.filter(ChannelAnalyticsModel.created_at <= end_date)
            unique_users_count = unique_users.scalar() or 0
            
            # Message count (message_posted events)
            message_count = query.filter(
                ChannelAnalyticsModel.event_type == 'message_posted'
            ).count()
            
            # Player activity count
            player_activity_count = query.filter(
                ChannelAnalyticsModel.event_type == 'player_activity'
            ).count()
            
            return {
                "total_events": total_events,
                "events_by_type": events_by_type,
                "events_by_subtype": events_by_subtype,
                "unique_users": unique_users_count,
                "message_count": message_count,
                "player_activity_count": player_activity_count
            }

    # --- Tournaments ---
    def create_tournament(
        self,
        name: str,
        bracket_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Create a new tournament. Returns tournament dict with id, name, status, etc."""
        if not name or not name.strip():
            raise ValueError("Tournament name must be non-empty")
        with self.session_factory() as session:
            t = TournamentModel(
                name=name.strip(),
                status="pending",
                bracket_type=bracket_type,
                start_date=start_date,
                end_date=end_date,
            )
            session.add(t)
            session.commit()
            session.refresh(t)
            return {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "bracket_type": t.bracket_type,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }

    def get_tournament(self, tournament_id: int) -> Optional[Dict[str, Any]]:
        """Get tournament by id. Returns None if not found."""
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                return None
            return {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "bracket_type": t.bracket_type,
                "start_date": t.start_date.isoformat() if t.start_date else None,
                "end_date": t.end_date.isoformat() if t.end_date else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }

    def add_game_to_tournament(
        self,
        tournament_id: int,
        game_id: str | int,
        round_number: int = 1,
        bracket_position: Optional[str] = None,
    ) -> None:
        """Link a game to a tournament. game_id can be string game_id or numeric id."""
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                raise ValueError(f"Tournament {tournament_id} not found")
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            tg = TournamentGameModel(
                tournament_id=tournament_id,
                game_id=game_model.id,
                round_number=round_number,
                bracket_position=bracket_position,
            )
            session.add(tg)
            session.commit()

    def add_player_to_tournament(
        self,
        tournament_id: int,
        user_id: int,
        seed: Optional[int] = None,
    ) -> None:
        """Add a player to a tournament (by user_id)."""
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                raise ValueError(f"Tournament {tournament_id} not found")
            u = session.query(UserModel).filter_by(id=user_id).first()
            if not u:
                raise ValueError(f"User {user_id} not found")
            tp = TournamentPlayerModel(
                tournament_id=tournament_id,
                user_id=user_id,
                seed=seed,
            )
            session.add(tp)
            session.commit()

    def get_tournament_games(self, tournament_id: int) -> List[Dict[str, Any]]:
        """List games in a tournament with round and bracket_position."""
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                return []
            rows = (
                session.query(TournamentGameModel, GameModel)
                .join(GameModel, TournamentGameModel.game_id == GameModel.id)
                .filter(TournamentGameModel.tournament_id == tournament_id)
                .order_by(TournamentGameModel.round_number, TournamentGameModel.id)
                .all()
            )
            return [
                {
                    "game_id": str(g.game_id),
                    "round_number": tg.round_number,
                    "bracket_position": tg.bracket_position,
                }
                for tg, g in rows
            ]

    def get_tournament_players(self, tournament_id: int) -> List[Dict[str, Any]]:
        """List players in a tournament with seed and final_rank."""
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                return []
            rows = (
                session.query(TournamentPlayerModel, UserModel)
                .outerjoin(UserModel, TournamentPlayerModel.user_id == UserModel.id)
                .filter(TournamentPlayerModel.tournament_id == tournament_id)
                .order_by(TournamentPlayerModel.seed, TournamentPlayerModel.id)
                .all()
            )
            return [
                {
                    "user_id": tp.user_id,
                    "seed": tp.seed,
                    "final_rank": tp.final_rank,
                    "full_name": u.full_name if u else None,
                    "email": u.email if u else None,
                }
                for tp, u in rows
            ]

    def get_tournament_bracket(self, tournament_id: int) -> Dict[str, Any]:
        """Get bracket view: tournament info plus games grouped by round."""
        tour = self.get_tournament(tournament_id)
        if not tour:
            return {"error": "Tournament not found"}
        games = self.get_tournament_games(tournament_id)
        players = self.get_tournament_players(tournament_id)
        rounds: Dict[int, List[Dict[str, Any]]] = {}
        for g in games:
            r = g["round_number"]
            if r not in rounds:
                rounds[r] = []
            rounds[r].append(g)
        return {
            "tournament": tour,
            "games_by_round": rounds,
            "players": players,
        }

    def update_tournament_status(self, tournament_id: int, status: str) -> None:
        """Update tournament status (pending, active, completed, cancelled)."""
        allowed = {"pending", "active", "completed", "cancelled"}
        if status not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        with self.session_factory() as session:
            t = session.query(TournamentModel).filter_by(id=tournament_id).first()
            if not t:
                raise ValueError(f"Tournament {tournament_id} not found")
            t.status = status
            session.commit()

    def list_tournaments(
        self,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List tournaments, optionally filtered by status."""
        with self.session_factory() as session:
            q = session.query(TournamentModel).order_by(TournamentModel.id.desc())
            if status:
                q = q.filter(TournamentModel.status == status)
            tournaments = q.all()
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status,
                    "bracket_type": t.bracket_type,
                    "start_date": t.start_date.isoformat() if t.start_date else None,
                    "end_date": t.end_date.isoformat() if t.end_date else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tournaments
            ]

    # --- Spectators ---
    def add_spectator(self, game_id: str | int, user_id: int) -> None:
        """Add a user as spectator to a game. Idempotent if already spectating."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            user = session.query(UserModel).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            existing = (
                session.query(SpectatorModel)
                .filter_by(game_id=game_model.id, user_id=user_id)
                .first()
            )
            if existing:
                return
            spec = SpectatorModel(game_id=game_model.id, user_id=user_id)
            session.add(spec)
            session.commit()

    def remove_spectator(self, game_id: str | int, user_id: int) -> None:
        """Remove a user from spectators for a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            session.query(SpectatorModel).filter_by(
                game_id=game_model.id, user_id=user_id
            ).delete()
            session.commit()

    def get_spectators(self, game_id: str | int) -> List[Dict[str, Any]]:
        """List spectators for a game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return []
            rows = (
                session.query(SpectatorModel, UserModel)
                .join(UserModel, SpectatorModel.user_id == UserModel.id)
                .filter(SpectatorModel.game_id == game_model.id)
                .order_by(SpectatorModel.joined_at)
                .all()
            )
            return [
                {
                    "user_id": s.user_id,
                    "joined_at": s.joined_at.isoformat() if s.joined_at else None,
                    "full_name": u.full_name,
                    "email": u.email,
                }
                for s, u in rows
            ]

    def is_spectator(self, game_id: str | int, user_id: int) -> bool:
        """Return True if user is spectating the game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return False
            return (
                session.query(SpectatorModel)
                .filter_by(game_id=game_model.id, user_id=user_id)
                .first()
                is not None
            )

    def is_player_in_game(self, game_id: str | int, user_id: int) -> bool:
        """Return True if user is a player (has a power) in the game."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, str(game_id))
            if not game_model:
                return False
            return (
                session.query(PlayerModel)
                .filter_by(game_id=game_model.id, user_id=user_id)
                .first()
                is not None
            )

    # --- Misc helpers --- 
    def execute_query(self, sql: str) -> None:
        """Execute a raw SQL query. Used for health checks."""
        with self.session_factory() as session:
            session.execute(text(sql))
            session.commit()

    def commit(self) -> None:
        # Sessions are scoped per method; no global commit required
        return None

    def refresh(self, obj: Any) -> None:
        # Not meaningful with per-method sessions
        return None
