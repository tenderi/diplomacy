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
from typing import Dict, Any, Optional, TYPE_CHECKING

from ..db_config import SQLALCHEMY_DATABASE_URL
from persistence.database_service import DatabaseService
from persistence.game_repo import GameRepo, StaleGameError
from ..server import Server
from ..game_service import GameService

if TYPE_CHECKING:
    from ..daide.server import DaideServer

_shared_logger = logging.getLogger(__name__)

# Shared service instances
db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)
# New engine: all game state/adjudication goes through GameService (over GameRepo).
game_service = GameService(GameRepo(db_service.session_factory))
server = Server()

# The DAIDE TCP listener. None until `_api_module.py`'s lifespan starts it (or
# forever None in test contexts that never trigger lifespan / that have no DB
# configured for it to create a game against). Route modules must read this
# via `shared.daide_server` (module attribute access), never
# `from .shared import daide_server` -- the latter freezes the `None` binding
# captured at import time and never sees the later reassignment below.
daide_server: "Optional[DaideServer]" = None

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


def notify_players(
    game_id: int,
    message: str,
    exclude_telegram_id: Optional[str] = None,
) -> None:
    """Notify all players in a game.

    ``exclude_telegram_id`` skips one player -- used by the manual
    ``process_turn`` route, whose caller already has the resolution in their HTTP
    response and does not need to be told a second time.

    **This function used to send nothing at all, ever.** It iterated
    ``PlayerModel`` rows and read ``getattr(player, 'telegram_id', None)``, but
    ``telegram_id`` is a column on ``UserModel`` (players reference a user by
    ``user_id``), so the value was unconditionally ``None``, the guard never
    passed, and every notification in the system -- turn processed, deadline
    reminder, player joined, game full, broadcast, game ended -- was dead code
    that logged nothing and raised nothing. Found while unifying the two
    ``process_turn`` fan-outs (G3): the two paths did agree, in that neither
    notified anybody. The join now lives in
    ``DatabaseService.get_player_telegram_ids`` so no caller can reintroduce it.
    """
    telegram_ids = db_service.get_player_telegram_ids(game_id)
    for telegram_id_val in telegram_ids:
        if exclude_telegram_id is not None and str(telegram_id_val) == str(exclude_telegram_id):
            continue
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


def _notify_daide_processed(game_id: str, resolved_phase: Optional[str]) -> None:
    """Bridge `DaideServer.notify_game_processed` (async) into whatever
    context a *synchronous* call site (`process_due_deadlines`, run from the
    scheduler's `async def` loop without an `await`, and directly from tests)
    happens to run in. No-op when no DAIDE listener is up (`daide_server` is
    `None` in most test contexts and whenever the listener failed to bind).

    There's no existing sync-calls-async bridge elsewhere in this codebase to
    mirror (`notify_players`, cited as a precedent when this task was scoped,
    turned out to be a sync function called from a sync context -- not an
    actual bridge) -- this is deliberately the smallest one that works both
    with a running loop (schedule a task, don't block it) and without one
    (run to completion via `asyncio.run`, e.g. a script or a sync test calling
    `process_due_deadlines` directly).
    """
    if daide_server is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        loop.create_task(daide_server.notify_game_processed(game_id, resolved_phase=resolved_phase))
        return
    try:
        asyncio.run(daide_server.notify_game_processed(game_id, resolved_phase=resolved_phase))
    except RuntimeError:
        scheduler_logger.debug("DAIDE notify skipped for %s: no event loop available here", game_id)


def _post_turn_to_channel(game_id: str, message: str) -> None:
    """Post a turn-start notification and a freshly rendered map to a linked channel.

    Best-effort by design: a Telegram outage must never fail a turn that is
    already committed to Postgres. Both auto-post checks return ``False`` when a
    game has no linked channel, so this is a cheap no-op for most games.
    """
    try:
        from ..telegram_bot.channels import (
            should_auto_post_map, should_auto_post_notification,
            post_map_to_channel, post_notification_to_channel
        )
        from ..api.routes.maps import generate_map_for_snapshot

        if should_auto_post_notification(game_id, "turn_start"):
            channel_info = db_service.get_game_channel_info(game_id)
            if channel_info:
                post_notification_to_channel(
                    channel_id=channel_info.get("channel_id"),
                    game_id=game_id,
                    notification_type="turn_start",
                    title=f"Turn Processed - Game {game_id}",
                    message=message,
                )

        if should_auto_post_map(game_id):
            channel_info = db_service.get_game_channel_info(game_id)
            if channel_info:
                try:
                    result = generate_map_for_snapshot(game_id)
                    map_path = result.get("map_path")
                    if map_path:
                        post_map_to_channel(
                            channel_id=channel_info.get("channel_id"),
                            game_id=game_id,
                            map_path=map_path,
                        )
                except Exception as e:
                    scheduler_logger.warning(f"Failed to auto-post map to channel: {e}")
    except Exception as e:
        scheduler_logger.debug(f"Channel integration check failed for game {game_id}: {e}")


def notify_turn_processed(
    game_id: str,
    numeric_game_id: int,
    *,
    trigger: str,
    game_ended: bool = False,
    exclude_telegram_id: Optional[str] = None,
) -> None:
    """The single fan-out for "a turn was processed". Used by **both** trigger paths.

    Before this existed the two paths told players wildly different amounts (G3):
    the deadline path DM'd every player, reset the reminder flag and posted a
    notification plus a rendered map to the linked channel, while the manual
    route notified *nobody* unless the game had just ended. So the failure case
    was richly instrumented and the success case was silent. Both now call here,
    so they cannot drift again.

    ``trigger`` is ``"deadline"`` or ``"manual"`` and changes only the *wording*
    of the player DM -- a missed deadline is worth saying out loud, since a
    player who is used to being asked may not have submitted. Which surfaces get
    notified is deliberately identical either way; see the notification matrix in
    ``docs/specs/architecture.md``.

    Synchronous on purpose, so the sync scheduler path and the ``async`` route
    can share it unchanged. It blocks its caller for up to ``timeout=2`` per
    player, which is pre-existing behaviour on both paths (the deadline fan-out
    already ran inside the scheduler's event loop, and the manual route already
    called ``notify_players`` synchronously for game-end) -- not something this
    change introduced. Every send is best-effort and logged.
    """
    if game_ended:
        player_message = f"Game {game_id} has ended!"
    elif trigger == "deadline":
        player_message = (
            f"The turn has been processed for game {game_id} due to a missed or due "
            f"deadline. View the new board state and submit your next orders."
        )
    else:
        player_message = (
            f"The turn has been processed for game {game_id}. View the new board state "
            f"and submit your next orders."
        )

    try:
        notify_players(numeric_game_id, player_message, exclude_telegram_id=exclude_telegram_id)
    except Exception as e:
        scheduler_logger.error(f"Failed to notify players for game {game_id}: {e}")

    # A new turn means the next deadline gets its own 10-minute reminder.
    reminder_sent[numeric_game_id] = False

    if not game_ended:
        _post_turn_to_channel(game_id, "The turn has been processed. New orders are due.")
    else:
        _post_turn_to_channel(game_id, f"Game {game_id} has ended.")


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
                    # Process the turn. Double-processing within this worker is
                    # prevented by GameRepo.save_state's expected_phase_code check
                    # (raises StaleGameError, caught below) -- an asyncio.Lock here
                    # would only guard this one process anyway, not a second uvicorn
                    # worker racing to process the same missed deadline, so it isn't
                    # a real guard and has been removed rather than kept for show.
                    game_id_str = str(getattr(game, 'game_id', None) or game_id_val)
                    prev_view = game_service.view(game_id_str)
                    prev_phase_code = prev_view["phase"] if prev_view else None
                    try:
                        game_service.process_turn(game_id_str)
                    except StaleGameError:
                        scheduler_logger.warning(
                            "PROCESS_TURN for game %s already processed concurrently, skipping.",
                            game_id_str,
                        )
                    except Exception as e:
                        scheduler_logger.error(f"Failed to process turn for game {game_id_str}: {e}")
                    else:
                        _notify_daide_processed(game_id_str, prev_phase_code)
                    # Direct SQL update to set deadline to NULL for cross-session visibility
                    db_service.update_game_deadline(game_id_val, None)
                    db_service.commit()  # type: ignore
                    # Player DMs + channel notification + channel map post, shared
                    # verbatim with the manual `POST /games/{id}/process_turn`
                    # route so the two triggers cannot drift apart again (G3).
                    notify_turn_processed(
                        game_id_str,
                        game_id_val,  # type: ignore[arg-type]
                        trigger="deadline",
                    )
    except Exception as e:
        scheduler_logger.error(f"Error processing deadlines: {e}")


def check_and_send_reminders(now: datetime) -> None:
    """Send a one-time 10-minute-to-deadline reminder for every active game whose
    deadline is due within the next 10 minutes and hasn't already had one sent
    (tracked in-memory via ``reminder_sent``).

    Split out from ``deadline_scheduler`` so it's callable directly -- both by the
    scheduler's own loop and by tests, which would otherwise have no way to
    exercise the reminder branch without sleeping through most of the 10-minute
    window in real time.
    """
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        now = now.replace(tzinfo=pytz.UTC)
    try:
        games = db_service.get_games_with_deadlines_and_active_status()
        for game in games:
            deadline = getattr(game, 'deadline', None)  # type: ignore
            game_id_val = getattr(game, 'id', None)  # type: ignore
            if game_id_val is None:
                continue  # skip games with no id
            if deadline is not None:
                # deadlines are stored as naive UTC (see
                # DatabaseService.update_game_deadline) -- reinterpret as UTC.
                if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                    deadline = deadline.replace(tzinfo=pytz.UTC)
                # Send reminder 10 minutes before deadline
                if deadline - now <= timedelta(minutes=10) and deadline > now:
                    if not reminder_sent.get(game_id_val, False):
                        notify_players(game_id_val, f"Reminder: The deadline for submitting orders in game {game_id_val} is in 10 minutes.")  # type: ignore
                        scheduler_logger.info(f"Sent 10-minute reminder for game {game_id_val} (deadline: {deadline})")
                        reminder_sent[game_id_val] = True
    except Exception as e:
        scheduler_logger.error(f"Error in deadline scheduler: {e}")


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
        check_and_send_reminders(now)

