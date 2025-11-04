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
from fastapi import HTTPException

from ..db_config import SQLALCHEMY_DATABASE_URL
from engine.database_service import DatabaseService
from engine.database import order_to_dict, unit_to_dict
from ..server import Server
from ..models import GameStateOut, PowerStateOut, UnitOut
from engine.data_models import GameState, Unit, GameStatus
from ..response_cache import invalidate_cache

# Shared service instances
db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)
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
ADMIN_TOKEN = os.environ.get("DIPLOMACY_ADMIN_TOKEN", "changeme")

# Allowed services for dashboard (moved to dashboard.py route module)
# ALLOWED_SERVICES = ["diplomacy", "diplomacy-bot"]


def _state_to_spec_dict(state_obj: Any) -> Dict[str, Any]:
    """Serialize GameState dataclasses to spec-shaped JSON-serializable dict."""
    from engine.database import order_to_dict, unit_to_dict
    
    supply_centers: dict[str, str] = {}
    for p_name, p_state in state_obj.powers.items():
        for prov in p_state.controlled_supply_centers:
            supply_centers[prov] = p_name

    powers: Dict[str, Any] = {}
    for power_name, ps in state_obj.powers.items():
        powers[power_name] = {
            "power_name": ps.power_name,
            "user_id": ps.user_id,
            "is_active": ps.is_active,
            "is_eliminated": ps.is_eliminated,
            "home_supply_centers": ps.home_supply_centers,
            "controlled_supply_centers": ps.controlled_supply_centers,
            "units": [unit_to_dict(u) for u in ps.units],
            "orders_submitted": ps.orders_submitted,
            "last_order_time": ps.last_order_time.isoformat() if ps.last_order_time else None,
            "retreat_options": ps.retreat_options,
            "build_options": ps.build_options,
            "destroy_options": ps.destroy_options,
        }

    return {
        "game_id": state_obj.game_id,
        "map_name": state_obj.map_name,
        "current_turn": state_obj.current_turn,
        "current_year": state_obj.current_year,
        "current_season": state_obj.current_season,
        "current_phase": state_obj.current_phase,
        "phase_code": state_obj.phase_code,
        "status": state_obj.status.value,
        "created_at": state_obj.created_at.isoformat(),
        "updated_at": state_obj.updated_at.isoformat(),
        "powers": powers,
        "units": {p: [unit_to_dict(u) for u in ps.units] for p, ps in state_obj.powers.items()},
        "supply_centers": supply_centers,
        "orders": {p: [order_to_dict(o) for o in orders] for p, orders in state_obj.orders.items()},
        "pending_retreats": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_retreats.items()},
        "pending_builds": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_builds.items()},
        "pending_destroys": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_destroys.items()},
        "turn_history": [],
        "order_history": state_obj.order_history,
        "map_snapshots": [],
    }


def _get_power_for_unit(province: str, game) -> Optional[str]:
    """Get the power that owns a unit in the given province."""
    for power_name, power_state in game.game_state.powers.items():
        for unit in power_state.units:
            if unit.province == province:
                return power_name
    return None


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
                    # --- Mark inactive players ---
                    # Get current turn number from game state
                    state_val = getattr(game, 'state', None)
                    turn = 0
                    if isinstance(state_val, dict):
                        turn = state_val.get("turn", 0)
                    # For each player, check if they submitted orders for this turn
                    players = db_service.get_players_by_game_id(game_id_val)
                    for player in players:
                        # SQLAlchemy ORM: must use getattr for boolean columns
                        if getattr(player, 'is_active', True) is True:  # type: ignore
                            has_orders = db_service.check_if_player_has_orders_for_turn(int(player.id), turn)  # type: ignore
                            if not has_orders:
                                setattr(player, 'is_active', False)  # type: ignore
                                db_service.update_player_is_active(int(player.id), False)  # type: ignore
                    # --- Process turn ---
                    game_id_str = str(getattr(game, 'game_id', None) or game_id_val)
                    server.process_command(f"PROCESS_TURN {game_id_str}")
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
                                    message=f"The turn has been processed. New orders are due."
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

