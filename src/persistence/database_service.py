"""
Database service for Diplomacy game engine.

This module provides database operations using the new data models and schema
to ensure proper data integrity and consistency.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy import func as sa_func
import logging
from .database import (
    GameModel, PlayerModel, OrderModel, TurnHistoryModel, MapSnapshotModel, MessageModel, UserModel, LinkCodeModel, PasswordResetTokenModel,
    TournamentModel, TournamentGameModel, TournamentPlayerModel,
    SpectatorModel, WaitingListModel, BotOutboxModel, IdempotencyKeyModel,
    get_session_factory,
    utcnow_naive,
)

# How long a stored idempotent response and a delivered outbox row are kept
# before the scheduler purges them. A queued bot request older than this has
# long since been delivered or reported as failed to the player.
IDEMPOTENCY_RETENTION_DAYS = 7
OUTBOX_DELIVERED_RETENTION_DAYS = 7



@dataclass(frozen=True)
class DeadlineProposalChange:
    """What ``modify_deadline_proposal``'s callback decided: the proposal to
    store (``None`` clears it), the caller's ``result`` to hand back, and
    whether to set the game's deadline and to what (``None`` clears it)."""

    proposal: Optional[Dict[str, Any]]
    result: Dict[str, Any]
    set_deadline: bool = False
    deadline: Optional[datetime] = None


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Naive UTC for a ``TIMESTAMP`` column (see ``update_game_deadline``)."""
    if value is not None and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

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

    # --- Waiting list (automatic game matching) ---
    def add_to_waiting_list(self, telegram_id: str, full_name: Optional[str] = None) -> bool:
        """Queue a player. Returns ``False`` if they were already queued.

        ``telegram_id`` is UNIQUE, so this is idempotent by construction: a
        repeated ``/wait`` cannot claim two slots in the same game.
        """
        with self.session_factory() as session:
            existing = (
                session.query(WaitingListModel)
                .filter_by(telegram_id=str(telegram_id))
                .first()
            )
            if existing is not None:
                return False
            session.add(
                WaitingListModel(
                    telegram_id=str(telegram_id),
                    full_name=full_name,
                    joined_at=utcnow_naive(),
                )
            )
            session.commit()
            return True

    def remove_from_waiting_list(self, telegram_id: str) -> bool:
        """Dequeue a player. Returns ``False`` if they weren't queued."""
        with self.session_factory() as session:
            deleted = (
                session.query(WaitingListModel)
                .filter_by(telegram_id=str(telegram_id))
                .delete(synchronize_session=False)
            )
            session.commit()
            return bool(deleted)

    def get_waiting_list(self) -> List[Tuple[str, Optional[str]]]:
        """Everyone queued, longest-waiting first, as ``(telegram_id, full_name)``."""
        with self.session_factory() as session:
            rows = (
                session.query(WaitingListModel.telegram_id, WaitingListModel.full_name)
                .order_by(WaitingListModel.joined_at, WaitingListModel.id)
                .all()
            )
        return [(str(r[0]), r[1]) for r in rows]

    def count_waiting_list(self) -> int:
        with self.session_factory() as session:
            return session.query(WaitingListModel).count()

    def claim_waiting_list_entries(self, count: int) -> List[Tuple[str, Optional[str]]]:
        """Atomically remove and return the ``count`` longest-waiting entries.

        Returns ``[]`` (claiming nothing) unless at least ``count`` are queued.

        **This is the fix for G5's orphan-game bug.** The old bot-side code read
        ``waiting_list[:required_size]``, created a game, joined players in a
        loop, and only then ``clear()``ed the list -- so any failure inside the
        loop left an orphan game with a partial roster *and* an uncleared queue,
        and the next ``/wait`` tripped the threshold again and minted another
        orphan. Claiming first means a failure downstream can re-queue exactly
        the players it took (see ``requeue_waiting_list_entries``) and can never
        mint a second game from the same entries. ``clear()`` also dropped an 8th
        queued player; taking exactly ``count`` holds them for the next game.

        ``FOR UPDATE`` serialises two workers racing to fill the same queue: the
        loser sees the rows already gone and claims nothing.
        """
        if count <= 0:
            return []
        with self.session_factory() as session:
            rows = (
                session.query(WaitingListModel)
                .order_by(WaitingListModel.joined_at, WaitingListModel.id)
                .limit(count)
                .with_for_update()
                .all()
            )
            if len(rows) < count:
                session.rollback()
                return []
            claimed = [(str(r.telegram_id), r.full_name) for r in rows]
            for row in rows:
                session.delete(row)
            session.commit()
        return claimed

    def requeue_waiting_list_entries(
        self, entries: List[Tuple[str, Optional[str]]]
    ) -> None:
        """Put claimed entries back after a failed game creation.

        Re-inserted at the *front* of the queue (``joined_at`` preserved is not
        possible once deleted, so the original wait is approximated by backdating
        below the current minimum) so players who were nearly in a game are not
        sent to the back of the line for a server-side failure.
        """
        if not entries:
            return
        with self.session_factory() as session:
            earliest = session.query(
                sa_func.min(WaitingListModel.joined_at)
            ).scalar()
            base = earliest or utcnow_naive()
            for offset, (telegram_id, full_name) in enumerate(entries):
                already = (
                    session.query(WaitingListModel)
                    .filter_by(telegram_id=str(telegram_id))
                    .first()
                )
                if already is not None:
                    continue
                session.add(
                    WaitingListModel(
                        telegram_id=str(telegram_id),
                        full_name=full_name,
                        # microseconds before the current head, order preserved
                        joined_at=base - timedelta(microseconds=len(entries) - offset),
                    )
                )
            session.commit()

    def clear_waiting_list(self) -> int:
        """Empty the queue. Returns how many entries were removed (admin/test use)."""
        with self.session_factory() as session:
            deleted = session.query(WaitingListModel).delete(synchronize_session=False)
            session.commit()
            return int(deleted)

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
        """Get player by game_id (can be numeric id or string game_id) and power.

        ``power`` is matched case-insensitively: ``create_player`` stores it
        upper-cased, and every route that takes a power from a request body
        (orders, draw vote, concede, private message) resolves the seat through
        here, so ``"france"`` must find FRANCE rather than "Player not found".
        """
        power = power.upper()
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


    def assign_player_seat(self, player_id: int, user_id: Optional[int], is_active: bool) -> bool:
        """Set who holds a power's seat, in one committed session.

        ``(None, False)`` vacates it (quit, admin mark-inactive). Filling a
        vacant seat goes through ``claim_vacant_seat``, which cannot take one
        somebody else just filled. Returns ``False`` if no such player row.

        Exists because both ``/quit`` and ``/replace`` used to assign
        ``player.user_id`` on the *detached* row ``get_player_by_game_id_and_power``
        returns and then call the no-op ``commit()`` -- so ``is_active`` (written
        through the since-removed ``update_player_is_active``) changed and ``user_id`` silently did
        not. A quitter therefore still held the power (orders, votes, concede all
        authorized), the seat could never be replaced ("already assigned"), and a
        replacement would have flipped ``is_active`` without taking the seat.
        """
        with self.session_factory() as session:
            player = session.query(PlayerModel).filter_by(id=player_id).first()
            if player is None:
                return False
            player.user_id = user_id
            player.is_active = is_active
            session.commit()
            return True

    def claim_vacant_seat(self, player_id: int, user_id: int) -> bool:
        """Give a vacant seat to ``user_id`` -- only if it is still vacant.

        One conditional ``UPDATE ... WHERE user_id IS NULL``: two players taking
        the same vacated seat at once both used to succeed (check, then an
        unconditional ``assign_player_seat``), the second silently replacing the
        first, who had been told they joined. Returns whether this call got it.
        """
        with self.session_factory() as session:
            claimed = (
                session.query(PlayerModel)
                .filter(PlayerModel.id == player_id, PlayerModel.user_id.is_(None))
                .update({PlayerModel.user_id: user_id, PlayerModel.is_active: True}, synchronize_session=False)
            )
            session.commit()
            return claimed == 1

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

    def update_game_phase_length(self, game_id: int, phase_length_seconds: Optional[int]) -> None:
        """Set the phase length a caller can arm a deadline from via
        ``POST /games/{id}/deadline`` (seconds; NULL = 24 h default). Does not
        itself touch ``deadline`` -- nothing re-arms one automatically."""
        with self.session_factory() as session:
            game = session.query(GameModel).filter_by(id=game_id).first()
            if game is None:
                return
            game.phase_length_seconds = phase_length_seconds
            session.commit()

    def get_pending_deadline_proposal(self, game_id: str) -> Optional[Dict[str, Any]]:
        """The in-flight deadline-change proposal for this game, or ``None`` if
        there isn't one (or the game doesn't exist)."""
        with self.session_factory() as session:
            game_model = self._get_game_model_by_game_id_string(session, game_id)
            if not game_model:
                return None
            return game_model.pending_deadline_proposal

    def modify_deadline_proposal(
        self,
        game_id: str,
        change: Callable[[Optional[Dict[str, Any]]], "DeadlineProposalChange"],
    ) -> "DeadlineProposalChange":
        """Apply ``change`` to the pending deadline proposal in one transaction,
        on the game row locked ``FOR UPDATE``; anything ``change`` raises rolls
        it back.

        Reading the proposal and writing it back in separate transactions lost
        one of two votes cast together (so a majority could be missed), and let
        two proposals both see "none pending". ``change`` returns the new
        proposal and, for an accepted one, the deadline to set -- written here in
        the same transaction, since a second write to the locked row from
        another session would wait on this one forever.
        """
        with self.session_factory() as session:
            found = self._get_game_model_by_game_id_string(session, game_id)
            if not found:
                raise ValueError(f"game {game_id} not found")
            # populate_existing: ``found`` is already in this session's identity
            # map, and without it the locked read hands back that stale copy.
            game_model = (
                session.query(GameModel).filter_by(id=found.id).with_for_update().populate_existing().one()
            )
            outcome = change(game_model.pending_deadline_proposal)
            game_model.pending_deadline_proposal = outcome.proposal
            if outcome.set_deadline:
                game_model.deadline = _naive_utc(outcome.deadline)
            session.commit()
            return outcome

    def get_games_with_pending_deadline_proposals(self) -> List[GameModel]:
        """Every game with a deadline proposal currently in flight. For the
        scheduler's expiry sweep -- most games return here empty, most of the
        time."""
        with self.session_factory() as session:
            return (
                session.query(GameModel)
                .filter(GameModel.pending_deadline_proposal.isnot(None))
                .all()
            )

    def get_phase_code_at(self, game_id: int, when: datetime) -> Optional[str]:
        """The phase this game was in at ``when``, or None if undeterminable.

        Used to stamp ``messages.phase_code`` from the time a message was
        *composed* rather than the time it arrived -- the bot queues messages
        while the home server is unreachable, so the two can be different phases
        (see ``api.client_timestamp``).

        Derived from the snapshot trail: every processed turn writes a
        ``MapSnapshotModel`` whose ``phase_code`` is the phase that *began* then,
        so the phase in effect at ``when`` is the newest snapshot at or before it.
        With no snapshot that old, the message predates the first processed turn
        and belongs to the game's opening phase, which is what the caller passes
        as the current phase when this returns None for a fresh game.
        """
        if when.tzinfo is not None:
            when = when.astimezone(timezone.utc).replace(tzinfo=None)
        with self.session_factory() as session:
            snap = (
                session.query(MapSnapshotModel)
                .filter(MapSnapshotModel.game_id == game_id)
                .filter(MapSnapshotModel.created_at <= when)
                .order_by(MapSnapshotModel.created_at.desc(), MapSnapshotModel.id.desc())
                .first()
            )
            return str(snap.phase_code) if snap is not None else None

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
        deadline = _naive_utc(deadline)
        with self.session_factory() as session:
            game = session.query(GameModel).filter_by(id=game_id).first()
            if game:
                game.deadline = deadline
                session.commit()
    

    # --- Orders ---
    def delete_all_orders(self) -> None:
        with self.session_factory() as session:
            session.query(OrderModel).delete()
            session.commit()

    # --- Messages ---
    def create_message(
        self,
        game_id: int,
        sender_user_id: int,
        recipient_power: Optional[str],
        text: str,
        timestamp: Optional[datetime] = None,
        phase_code: Optional[str] = None,
    ):
        """Store a diplomatic message.

        ``timestamp`` is the moment the message was *composed*, when the caller
        knows it -- the bot passes the time a player typed the message, which
        can be much earlier than now if it sat in the bot's offline queue while
        the API was unreachable. Defaults to now. Must be naive UTC
        (see ``utcnow_naive``); an aware value is normalised here so no caller
        can store a shifted time.

        ``phase_code`` is the game phase the message was written in, so a game
        log can be read phase by phase. Callers resolve it from ``timestamp`` via
        ``get_phase_code_at``.
        """
        if timestamp is None:
            timestamp = utcnow_naive()
        elif timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        with self.session_factory() as session:
            msg = MessageModel(
                game_id=game_id,
                sender_user_id=sender_user_id,
                recipient_power=recipient_power,
                text=text,
                timestamp=timestamp,
                phase_code=phase_code,
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

    def delete_game(self, game_id: int) -> bool:
        """Delete one game and everything that hangs off it, in one transaction.

        The live schema does not match the models here: ``players`` and
        ``messages`` reference ``games`` with ``ON DELETE NO ACTION`` (the models
        say CASCADE; the migrations never did), as do ``game_history`` and
        ``game_snapshots`` -- tables the initial migration created that no code
        reads or writes any more. Those are cleared explicitly; everything else
        (snapshots, turn history, channel rows, spectators, the unused
        units/orders/supply_centers) cascades. Returns False if there was no
        such game.
        """
        with self.session_factory() as session:
            if session.query(GameModel.id).filter_by(id=game_id).first() is None:
                return False
            session.query(MessageModel).filter_by(game_id=game_id).delete()
            session.query(PlayerModel).filter_by(game_id=game_id).delete()
            session.execute(text("DELETE FROM game_history WHERE game_id = :gid"), {"gid": game_id})
            session.execute(text("DELETE FROM game_snapshots WHERE game_id = :gid"), {"gid": game_id})
            session.query(GameModel).filter_by(id=game_id).delete()
            session.commit()
        return True

    def delete_all_games(self) -> None:
        with self.session_factory() as session:
            session.query(GameModel).delete()
            session.commit()

    # --- Channel Analytics ---
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

    # --- Bot outbox (server -> bot notifications) ---
    #
    # See ``BotOutboxModel``: every player DM is committed here and pulled by the
    # bot, so a bot or tunnel outage delays notifications instead of dropping them.

    def enqueue_bot_notification(
        self,
        telegram_id: str | int,
        message: str,
        *,
        kind: str = "dm",
        payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Queue one notification for the bot to deliver. Returns the row id."""
        with self.session_factory() as session:
            row = BotOutboxModel(
                kind=kind,
                telegram_id=str(telegram_id),
                message=message,
                payload=payload,
                created_at=utcnow_naive(),
            )
            session.add(row)
            session.commit()
            return int(row.id)

    def fetch_pending_bot_notifications(
        self, limit: int = 50, *, after_id: int = 0
    ) -> List[Dict[str, Any]]:
        """Undelivered notifications, oldest first.

        ``after_id`` lets a caller page past rows it already holds (and lets
        tests scope themselves to rows created after a checkpoint).
        """
        with self.session_factory() as session:
            rows = (
                session.query(BotOutboxModel)
                .filter(BotOutboxModel.delivered_at.is_(None))
                .filter(BotOutboxModel.id > int(after_id))
                .order_by(BotOutboxModel.id)
                .limit(max(1, min(int(limit), 500)))
                .all()
            )
            return [
                {
                    "id": int(r.id),
                    "kind": r.kind,
                    "telegram_id": r.telegram_id,
                    "message": r.message,
                    "payload": r.payload,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "attempts": int(r.attempts or 0),
                }
                for r in rows
            ]

    def max_bot_outbox_id(self) -> int:
        """Highest outbox id so far (0 when empty). A checkpoint for tests."""
        with self.session_factory() as session:
            value = session.query(sa_func.max(BotOutboxModel.id)).scalar()
            return int(value or 0)

    def ack_bot_notifications(
        self,
        delivered_ids: List[int],
        failed: Optional[Dict[int, str]] = None,
    ) -> int:
        """Mark rows delivered.

        ``failed`` maps id -> error for rows Telegram rejected *permanently*
        (user blocked the bot, chat not found). They are marked delivered too --
        retrying cannot help -- but keep ``last_error`` so the failure is
        auditable rather than silently absorbed. Transient failures are simply
        not acked and come back on the next pull. Returns rows updated.
        """
        failed = failed or {}
        ids = {int(i) for i in delivered_ids} | {int(i) for i in failed}
        if not ids:
            return 0
        now = utcnow_naive()
        with self.session_factory() as session:
            rows = (
                session.query(BotOutboxModel)
                .filter(BotOutboxModel.id.in_(ids))
                .filter(BotOutboxModel.delivered_at.is_(None))
                .all()
            )
            for row in rows:
                row.delivered_at = now
                row.attempts = int(row.attempts or 0) + 1
                error = failed.get(int(row.id))
                if error:
                    row.last_error = error[:2000]
            session.commit()
            return len(rows)

    def record_bot_notification_attempt(self, notification_id: int, error: str) -> None:
        """Note a transient delivery failure without acking the row."""
        with self.session_factory() as session:
            row = session.get(BotOutboxModel, int(notification_id))
            if row is None:
                return
            row.attempts = int(row.attempts or 0) + 1
            row.last_error = error[:2000]
            session.commit()

    def purge_delivered_bot_notifications(
        self, older_than_days: int = OUTBOX_DELIVERED_RETENTION_DAYS
    ) -> int:
        cutoff = utcnow_naive() - timedelta(days=older_than_days)
        with self.session_factory() as session:
            n = (
                session.query(BotOutboxModel)
                .filter(BotOutboxModel.delivered_at.isnot(None))
                .filter(BotOutboxModel.delivered_at < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(n)

    # --- Idempotency keys (bot -> server retried writes) ---
    #
    # See ``IdempotencyKeyModel`` and ``server.api.idempotency``.

    def get_idempotent_response(self, key: str) -> Optional[Dict[str, Any]]:
        """The stored ``{status_code, response_json, endpoint}`` for ``key``, or None."""
        with self.session_factory() as session:
            row = session.get(IdempotencyKeyModel, key)
            if row is None:
                return None
            return {
                "status_code": int(row.status_code),
                "response_json": row.response_json,
                "endpoint": row.endpoint,
            }

    def store_idempotent_response(
        self, key: str, endpoint: str, status_code: int, response_json: Any
    ) -> bool:
        """Store the first response for ``key``. Returns False if one already
        exists (a concurrent duplicate won the race; the stored one stands)."""
        from sqlalchemy.exc import IntegrityError
        with self.session_factory() as session:
            session.add(
                IdempotencyKeyModel(
                    key=key,
                    endpoint=endpoint[:255],
                    status_code=int(status_code),
                    response_json=response_json,
                    created_at=utcnow_naive(),
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
            return True

    def purge_idempotency_keys(self, older_than_days: int = IDEMPOTENCY_RETENTION_DAYS) -> int:
        cutoff = utcnow_naive() - timedelta(days=older_than_days)
        with self.session_factory() as session:
            n = (
                session.query(IdempotencyKeyModel)
                .filter(IdempotencyKeyModel.created_at < cutoff)
                .delete(synchronize_session=False)
            )
            session.commit()
            return int(n)

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
