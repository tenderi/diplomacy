"""
Shared dependencies and utilities for API route modules.

This module provides shared instances and utilities that are used across
multiple route modules to avoid circular imports and ensure consistency.
"""
import asyncio
import logging
import os
import requests
import pytz
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from ..db_config import SQLALCHEMY_DATABASE_URL
from persistence.database_service import DatabaseService
from persistence.game_repo import GameRepo
from ..server import Server
from ..game_service import GameService

_shared_logger = logging.getLogger(__name__)

# Shared service instances
db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)
# New engine: all game state/adjudication goes through GameService (over GameRepo).
game_service = GameService(GameRepo(db_service.session_factory))
server = Server()

# Shared loggers
logger = logging.getLogger("diplomacy.server.api")
scheduler_logger = logging.getLogger("diplomacy.scheduler")
scheduler_logger.setLevel(logging.INFO)
if not scheduler_logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    scheduler_logger.addHandler(handler)

# Notification service URL
NOTIFY_URL = os.environ.get("DIPLOMACY_NOTIFY_URL", "http://localhost:8081/notify")

# In-memory reminder tracking
reminder_sent: dict[int, bool] = {}  # game_id -> bool

# Admin token
_ADMIN_TOKEN_DEFAULT = "changeme"
ADMIN_TOKEN = os.environ.get("DIPLOMACY_ADMIN_TOKEN", _ADMIN_TOKEN_DEFAULT)
if ADMIN_TOKEN == _ADMIN_TOKEN_DEFAULT:
    _shared_logger.error(
        "SECURITY: DIPLOMACY_ADMIN_TOKEN is set to the default value 'changeme'. "
        "Set it before deploying to production."
    )
    if os.environ.get("DIPLOMACY_ENVIRONMENT") == "production":
        raise RuntimeError(
            "DIPLOMACY_ADMIN_TOKEN must be set to a strong secret in production. "
            "Refusing to start with the default value."
        )

# Bot secret: used to authenticate Telegram bot calls that use telegram_id instead of Bearer token
BOT_SECRET = os.environ.get("DIPLOMACY_BOT_SECRET", "")

# Per-game asyncio locks to prevent concurrent PROCESS_TURN calls
_process_turn_locks: Dict[str, asyncio.Lock] = {}


def get_process_turn_lock(game_id: str) -> asyncio.Lock:
    """Return (creating if needed) the per-game asyncio Lock for PROCESS_TURN."""
    if game_id not in _process_turn_locks:
        _process_turn_locks[game_id] = asyncio.Lock()
    return _process_turn_locks[game_id]


# Allowed services for dashboard (moved to dashboard.py route module)
# ALLOWED_SERVICES = ["diplomacy", "diplomacy-bot"]


def game_view(game_id: str) -> Optional[Dict[str, Any]]:
    """The new-engine, GameState-native API view of a game (or None if missing)."""
    return game_service.view(str(game_id))


def notify_players(game_id: int, message: str) -> None:
    """Notify all players in a game."""
    players = db_service.get_players_by_game_id(game_id)
    for player in players:
        telegram_id_val = getattr(player, 'telegram_id', None)
        if telegram_id_val is not None and telegram_id_val != '':
            try:
                # Only send notification if telegram_id is numeric (skip test IDs like "u1")
                telegram_id_int = int(telegram_id_val)
                requests.post(
                    NOTIFY_URL,
                    json={"telegram_id": telegram_id_int, "message": message},
                    timeout=2,
                )
                scheduler_logger.info(f"Notified telegram_id {telegram_id_val} for game {game_id}: {message}")
            except ValueError:
                # Skip non-numeric telegram_ids (test IDs)
                scheduler_logger.debug(f"Skipping notification for non-numeric telegram_id: {telegram_id_val}")
            except Exception as e:
                scheduler_logger.error(f"Failed to notify telegram_id {telegram_id_val}: {e}")


def process_due_deadlines(now: datetime) -> None:
    """
    Process all games with deadlines <= now. Used by the scheduler and for testing.
    Also marks players as inactive if they did not submit orders for the last turn.
    """
    try:
        games = db_service.get_games_with_deadlines_and_active_status()
        for game in games:
            deadline = getattr(game, 'deadline', None)  # type: ignore
            game_id_val = getattr(game, 'id', None)  # type: ignore
            if game_id_val is None:
                continue  # skip games with no id
            if deadline is not None:
                # Ensure both deadline and now are timezone-aware (UTC)
                if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                    deadline = deadline.replace(tzinfo=pytz.UTC)
                if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
                    now = now.replace(tzinfo=pytz.UTC)
                if deadline <= now:
                    scheduler_logger.warning(f"Missed or due deadline detected for game {game_id_val} (deadline was {deadline}, now {now}). Processing turn immediately.")
                    # --- Process turn (with per-game lock to prevent double-processing) ---
                    game_id_str = str(getattr(game, 'game_id', None) or game_id_val)
                    lock = get_process_turn_lock(game_id_str)
                    if lock.locked():
                        scheduler_logger.warning(
                            "PROCESS_TURN for game %s already in progress (scheduler), skipping.",
                            game_id_str,
                        )
                    else:
                        try:
                            game_service.process_turn(game_id_str)
                        except Exception as e:
                            scheduler_logger.error(f"Failed to process turn for game {game_id_str}: {e}")
                    # Direct SQL update to set deadline to NULL for cross-session visibility
                    db_service.update_game_deadline(game_id_val, None)
                    db_service.commit()  # type: ignore
                    notify_players(game_id_val, f"The turn has been processed for game {game_id_val} due to a missed or due deadline. View the new board state and submit your next orders.")  # type: ignore
                    reminder_sent[game_id_val] = False  # Reset for next turn
                    
                    # Channel integration: Auto-post map and notification after deadline processing
                    try:
                        from ..telegram_bot.channels import (
                            should_auto_post_map, should_auto_post_notification,
                            post_map_to_channel, post_notification_to_channel
                        )
                        from ..api.routes.maps import generate_map_for_snapshot
                        
                        game_id_str = str(getattr(game, 'game_id', None) or game_id_val)
                        
                        # Post notification
                        if should_auto_post_notification(game_id_str, "turn_start"):
                            channel_info = db_service.get_game_channel_info(game_id_str)
                            if channel_info:
                                post_notification_to_channel(
                                    channel_id=channel_info.get("channel_id"),
                                    game_id=game_id_str,
                                    notification_type="turn_start",
                                    title=f"Turn Processed - Game {game_id_str}",
                                    message="The turn has been processed. New orders are due."
                                )
                        
                        # Post map
                        if should_auto_post_map(game_id_str):
                            channel_info = db_service.get_game_channel_info(game_id_str)
                            if channel_info:
                                try:
                                    result = generate_map_for_snapshot(game_id_str)
                                    map_path = result.get("map_path")
                                    if map_path:
                                        post_map_to_channel(
                                            channel_id=channel_info.get("channel_id"),
                                            game_id=game_id_str,
                                            map_path=map_path
                                        )
                                except Exception as e:
                                    scheduler_logger.warning(f"Failed to auto-post map to channel: {e}")
                    except Exception as e:
                        scheduler_logger.debug(f"Channel integration check failed: {e}")
    except Exception as e:
        scheduler_logger.error(f"Error processing deadlines: {e}")


async def deadline_scheduler() -> None:
    """
    Background task that checks all games with deadlines every 30 seconds.
    If a game's deadline has passed, processes the turn and clears the deadline.
    Sends reminders 10 minutes before deadline and notifies players after turn processing.
    On startup, immediately process any missed deadlines.
    """
    # On startup: process any missed deadlines immediately
    now = datetime.now(timezone.utc)
    process_due_deadlines(now)
    # Main loop
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        now = datetime.now(timezone.utc)
        process_due_deadlines(now)
        try:
            games = db_service.get_games_with_deadlines_and_active_status()
            for game in games:
                deadline = getattr(game, 'deadline', None)  # type: ignore
                game_id_val = getattr(game, 'id', None)  # type: ignore
                if game_id_val is None:
                    continue  # skip games with no id
                if deadline is not None:
                    # Send reminder 10 minutes before deadline
                    if deadline - now <= timedelta(minutes=10) and deadline > now:
                        if not reminder_sent.get(game_id_val, False):
                            notify_players(game_id_val, f"Reminder: The deadline for submitting orders in game {game_id_val} is in 10 minutes.")  # type: ignore
                            scheduler_logger.info(f"Sent 10-minute reminder for game {game_id_val} (deadline: {deadline})")
                            reminder_sent[game_id_val] = True
        except Exception as e:
            scheduler_logger.error(f"Error in deadline scheduler: {e}")

