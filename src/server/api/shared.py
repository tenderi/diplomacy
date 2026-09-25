"""
Shared dependencies and utilities for API route modules.

This module provides shared instances and utilities that are used across
multiple route modules to avoid circular imports and ensure consistency.
"""
import asyncio
import hmac
import logging
import math
import os
import pytz
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict, Any, Optional, TYPE_CHECKING

from ..db_config import SQLALCHEMY_DATABASE_URL
from persistence.database_service import DatabaseService, DeadlineProposalChange
from persistence.game_repo import GameRepo, StaleGameError
from sqlalchemy.exc import SQLAlchemyError
from ..server import Server
from ..game_service import GameOverError, GameService
from ..response_cache import invalidate_cache

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
# The server's event loop, recorded at startup (``_api_module``'s lifespan), so
# code running in FastAPI's worker threads -- every sync route -- can hand a
# coroutine to it (``_notify_daide_processed``).
main_loop: Optional[asyncio.AbstractEventLoop] = None

# Shared loggers
logger = logging.getLogger("diplomacy.server.api")
scheduler_logger = logging.getLogger("diplomacy.scheduler")
scheduler_logger.setLevel(logging.INFO)
if not scheduler_logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    scheduler_logger.addHandler(handler)

# There is deliberately no NOTIFY_URL any more. Player notifications are not
# pushed at the bot; they are committed to the ``bot_outbox`` table (see
# ``notify_user`` below) and the bot pulls them over ``GET /bot/outbox``.

# In-memory reminder tracking
reminder_sent: dict[int, bool] = {}  # game_id -> bool

# How long a phase lasts when a game does not say (``games.phase_length_seconds``
# is NULL). Used only by the explicit ``POST /games/{id}/deadline`` route as the
# default for ``next_deadline`` below -- nothing arms a deadline from this
# automatically (Track N: deadlines exist only when set explicitly).
DEFAULT_PHASE_LENGTH_SECONDS = 24 * 60 * 60

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


def _matches(supplied: Optional[str], expected: str) -> bool:
    """Constant-time comparison of a supplied secret; an unset one never matches."""
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied.encode(), expected.encode())


def is_admin_token(supplied: Optional[str]) -> bool:
    """Is ``supplied`` the admin token? Every admin check goes through here."""
    return _matches(supplied, ADMIN_TOKEN)


def is_bot_secret(supplied: Optional[str]) -> bool:
    """Is ``supplied`` the bot secret? Every bot-secret check goes through here."""
    return _matches(supplied, BOT_SECRET)

# Per-game asyncio locks to prevent concurrent PROCESS_TURN calls
_process_turn_locks: Dict[str, asyncio.Lock] = {}


def get_process_turn_lock(game_id: str) -> asyncio.Lock:
    """Return (creating if needed) the per-game asyncio Lock for PROCESS_TURN."""
    if game_id not in _process_turn_locks:
        _process_turn_locks[game_id] = asyncio.Lock()
    return _process_turn_locks[game_id]




def game_buttons(game_id: Any, *, ended: bool = False) -> list[list[dict[str, str]]]:
    """Inline buttons for a notification about ``game_id``.

    The bot routes ``g|{game_id}|{action}`` callbacks to its game hub
    (``telegram_bot/hub.py``), so a player can act on a "turn processed" or
    "deadline soon" DM with one tap instead of typing a command and a game id.
    The trailing ``|n`` asks the bot to answer in a *new* message rather than
    editing this one, so the notification itself stays readable.
    """
    if ended:
        return [[{"text": "🗺 Final map", "callback_data": f"g|{game_id}|map|n"}]]
    return [
        [
            {"text": "📝 Enter orders", "callback_data": f"g|{game_id}|all|n"},
            {"text": "🗺 Map", "callback_data": f"g|{game_id}|map|n"},
        ],
        [{"text": "🎮 Game menu", "callback_data": f"g|{game_id}|hub|n"}],
    ]


def notify_user(
    telegram_id: Any, message: str, buttons: Optional[list[list[dict[str, str]]]] = None
) -> Optional[int]:
    """Queue one Telegram DM for the bot to deliver. Returns the outbox row id.

    **This is the only way server code may notify a player.** It writes the
    notification to ``bot_outbox`` -- the same Postgres the game state is in --
    and returns immediately; the bot pulls the row over
    ``GET /bot/outbox`` and acks it once Telegram has accepted the message. So a
    bot restart, a host reboot, or an API outage of any length
    *delays* the DM rather than losing it, and the bot prefixes the original
    time to anything it delivers late.

    The previous mechanism was a ``requests.post`` to a small HTTP server the
    bot ran on port 8081, ``timeout=2``, failure logged and forgotten. That was
    tolerable when both processes shared one host; it is not now that they sit
    on opposite ends of a residential uplink. It also blocked the event loop
    for up to two seconds per player from inside the deadline scheduler.

    Non-numeric ids (test fixtures like ``"u1"``) are skipped, not errored,
    exactly as before. A database failure here is logged and swallowed: the
    caller has already committed a state change, and the notification is not
    the contract (rule 3 in ``docs/specs/architecture.md``).
    """
    try:
        telegram_id_int = int(telegram_id)
    except (TypeError, ValueError):
        scheduler_logger.debug(f"Skipping notification for non-numeric telegram_id: {telegram_id}")
        return None
    try:
        row_id = db_service.enqueue_bot_notification(
            telegram_id_int, message, payload={"buttons": buttons} if buttons else None
        )
    except Exception as e:
        scheduler_logger.error(f"Failed to queue notification for telegram_id {telegram_id}: {e}")
        return None
    scheduler_logger.info(f"Queued notification #{row_id} for telegram_id {telegram_id}: {message}")
    return row_id


def notify_players(
    game_id: int,
    message: str,
    exclude_telegram_id: Optional[str] = None,
    buttons: Optional[list[list[dict[str, str]]]] = None,
) -> None:
    """Notify all players in a game, via ``notify_user`` (the durable outbox).

    ``buttons`` (see ``game_buttons``) ride along as inline buttons on each DM.

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
        notify_user(telegram_id_val, message, buttons)


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
    # A sync route (W10's auto-processing runs from POST /games/set_orders) is on
    # a worker thread: the DAIDE connections belong to the main loop, so the
    # coroutine must run there, not in a fresh loop of this thread's own.
    if main_loop is not None and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            daide_server.notify_game_processed(game_id, resolved_phase=resolved_phase), main_loop
        )
        return
    try:
        asyncio.run(daide_server.notify_game_processed(game_id, resolved_phase=resolved_phase))
    except RuntimeError:
        scheduler_logger.debug("DAIDE notify skipped for %s: no event loop available here", game_id)


def post_to_game_group(game_id: Any, text: str, *, dm_start: Optional[str] = None) -> None:
    """Queue an announcement for the Telegram group linked to ``game_id``, if any
    (and its ``auto_post_notifications`` setting is on). Best-effort, like every
    notification.

    ``dm_start`` adds a button that opens a *private* chat with the bot
    (``https://t.me/<bot>?start=<dm_start>``; the bot knows its own name, the
    API does not). A group must never get order buttons: whatever is pressed
    there, everyone in the group sees.
    """
    try:
        info = db_service.get_game_channel_info(str(game_id))
        if not info or not (info.get("settings") or {}).get("auto_post_notifications", True):
            return
        db_service.enqueue_bot_notification(
            info["channel_id"], text, kind="channel_text", payload={"dm_start": dm_start} if dm_start else None
        )
    except SQLAlchemyError as e:
        scheduler_logger.warning(f"Could not queue a group announcement for game {game_id}: {e}")


_SEASON_NAMES = {"S": "Spring", "F": "Fall", "W": "Winter"}
_PHASE_NAMES = {"M": "movement", "R": "retreats", "A": "builds"}


def phase_label(phase_code: str) -> str:
    """``"S1901M"`` -> ``"Spring 1901 movement"``; anything else is returned as is."""
    season, year, kind = phase_code[:1], phase_code[1:-1], phase_code[-1:]
    if season in _SEASON_NAMES and kind in _PHASE_NAMES and year.isdigit():
        return f"{_SEASON_NAMES[season]} {year} {_PHASE_NAMES[kind]}"
    return phase_code


def _post_turn_to_channel(
    game_id: str,
    message: str,
    processed_turn: Optional[int] = None,
    processed_phase: Optional[str] = None,
) -> None:
    """Queue a turn-start notification and a fresh map for a linked channel.

    Best-effort by design: a Telegram outage must never fail a turn that is
    already committed to Postgres. A cheap no-op for the common case (no
    linked channel).

    **Queued, not sent.** This used to call straight into
    ``telegram_bot.channels``, which only has a live ``Bot`` instance inside
    the bot's own process -- the API and the bot are separate containers, so
    every one of those calls silently did nothing (no exception; the module's
    own ``if not _telegram_bot: return None`` guard ate it). ``POST
    /games/{id}/channel``'s confirmation text has promised "maps will be
    posted after each turn" since that route existed; it never once happened.
    Routed through ``bot_outbox`` instead -- the same durable, polled queue
    every player DM already uses (``notify_user`` above) -- so this actually
    reaches Telegram, and survives an API or bot restart mid-delivery. The
    bot resolves ``channel_map``'s ``payload.game_id`` back into image bytes
    itself via ``GET /games/{id}/map`` (see ``telegram_bot/notifications.py``);
    nothing renders a map file on this side or expects the bot to read one off
    a filesystem the two containers don't share.
    """
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            return
        channel_id = channel_info.get("channel_id")
        settings = channel_info.get("settings") or {}

        if settings.get("auto_post_notifications", True):
            db_service.enqueue_bot_notification(
                channel_id,
                f"🔔 Turn Processed - Game {game_id}\n{message}",
                kind="channel_text",
                # Orders are sent in private; this button opens that chat.
                payload={"dm_start": f"orders_{game_id}"},
            )

        if settings.get("auto_post_maps", True) and processed_turn is not None:
            # Two images per processed turn: the orders on the board they were given
            # on, and the board they produced. Each is fetched by turn number, not
            # "the current map", so a post the bot delivers late -- it was down, or
            # the next turn ran first -- still shows the turn it announces.
            label = phase_label(processed_phase) if processed_phase else f"turn {processed_turn}"
            if game_service.resolution_history(game_id).get(str(processed_turn), {}).get("results"):
                db_service.enqueue_bot_notification(
                    channel_id,
                    f"📝 Game {game_id} · {label}: the orders",
                    kind="channel_map",
                    payload={"game_id": game_id, "path": f"/games/{game_id}/map/turn/{processed_turn}/orders"},
                )
            db_service.enqueue_bot_notification(
                channel_id,
                f"🗺️ Game {game_id} · {label}: the result",
                kind="channel_map",
                payload={"game_id": game_id, "path": f"/games/{game_id}/map/history/{processed_turn + 1}"},
            )
    except Exception as e:
        scheduler_logger.debug(f"Channel integration check failed for game {game_id}: {e}")


def notify_turn_processed(
    game_id: str,
    numeric_game_id: int,
    *,
    trigger: str,
    game_ended: bool = False,
    exclude_telegram_id: Optional[str] = None,
    processed_turn: Optional[int] = None,
    processed_phase: Optional[str] = None,
) -> None:
    """The single fan-out for "a turn was processed". Used by **both** trigger paths.

    ``processed_turn``/``processed_phase`` name the turn just adjudicated; with them
    the game's Telegram group also gets that turn's orders map and result map. (A
    draw ends a game without adjudicating anything, so it passes neither.)

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
    can share it unchanged. Since notifications became outbox inserts
    (``notify_user``) that costs one short database write per player rather
    than the two-second HTTP timeout it used to risk. Every send is
    best-effort and logged.
    """
    if game_ended:
        player_message = f"Game {game_id} has ended!"
    elif trigger == "deadline":
        player_message = (
            f"The turn has been processed for game {game_id} because its deadline passed. "
            f"Your next orders are due."
        )
    else:
        player_message = (
            f"The turn has been processed for game {game_id}. Your next orders are due."
        )

    try:
        notify_players(
            numeric_game_id,
            player_message,
            exclude_telegram_id=exclude_telegram_id,
            buttons=game_buttons(game_id, ended=game_ended),
        )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify players for game {game_id}: {e}")

    # A new turn means the next deadline gets its own 10-minute reminder.
    reminder_sent[numeric_game_id] = False

    if not game_ended:
        _post_turn_to_channel(
            game_id, "The turn has been processed. New orders are due -- send them to me in private.",
            processed_turn, processed_phase,
        )
    else:
        _post_turn_to_channel(game_id, f"Game {game_id} has ended.", processed_turn, processed_phase)


def next_deadline(
    phase_length_seconds: Optional[int], now: Optional[datetime] = None
) -> Optional[datetime]:
    """When a phase armed right now should be processed, or ``None`` for never.

    Used only by ``POST /games/{id}/deadline`` when the caller passes
    ``phase_length_seconds`` with no explicit ``deadline`` -- an explicit ask for
    "a deadline this far out", not an automatic re-arm (Track N: nothing arms a
    deadline after a turn is processed on its own). ``None`` length means the
    24 h default; ``0`` (or negative, defensively) means no deadline at all.
    """
    if phase_length_seconds is None:
        phase_length_seconds = DEFAULT_PHASE_LENGTH_SECONDS
    if phase_length_seconds <= 0:
        return None
    return (now or datetime.now(timezone.utc)) + timedelta(seconds=phase_length_seconds)


class DeadlineProposalError(ValueError):
    """A deadline-proposal request that cannot be honoured given the game's
    current state (already one pending, none pending, wrong power, game
    missing). Routes map this to a 400/404; caller identity/authorization is
    checked separately, before any of these functions are called."""


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def deadline_proposal_view(proposal: Dict[str, Any], active: frozenset[str]) -> Dict[str, Any]:
    """The proposal, decorated with tallies against the current active-power set."""
    votes = proposal.get("votes") or {}
    yes = sorted(p for p, v in votes.items() if v == "yes" and p in active)
    no = sorted(p for p, v in votes.items() if v == "no" and p in active)
    return {
        "proposed_by": proposal.get("proposed_by"),
        "value_hours": proposal.get("value_hours"),
        "yes_votes": yes,
        "no_votes": no,
        "active_powers": sorted(active),
        "needed_for_majority": len(active) // 2 + 1 if active else 0,
        "vote_deadline": proposal.get("vote_deadline"),
        "created_at": proposal.get("created_at"),
    }


def _deadline_vote_outcome(votes: Dict[str, str], active: frozenset[str]) -> Optional[str]:
    """``"accepted"``, ``"rejected"``, or ``None`` (still undecided).

    Majority, not unanimity, of ``active`` -- the same population a draw
    vote's quorum uses (non-eliminated, with a unit). "Rejected" fires the
    moment a yes-majority becomes mathematically impossible (enough no-votes
    that the remaining undecided powers voting yes couldn't reach it), so a
    proposal that will obviously never pass doesn't sit pending forever
    without an expiry set.
    """
    n = len(active)
    if n == 0:
        return None
    needed = n // 2 + 1
    yes = sum(1 for p, v in votes.items() if v == "yes" and p in active)
    no = sum(1 for p, v in votes.items() if v == "no" and p in active)
    if yes >= needed:
        return "accepted"
    if no > n - needed:
        return "rejected"
    return None


# Same ceiling the bot's /deadline enforces for both a unilateral set and a
# proposal: 30 days.
MAX_DEADLINE_PROPOSAL_HOURS = 24 * 30


def _check_proposal_hours(name: str, value: Optional[float]) -> None:
    """Refuse a non-finite, non-positive or over-long ``hours``/``vote_hours``.

    Until this check the API took any float: a negative ``hours`` that won its
    vote set a deadline in the past (the scheduler then processed the turn on
    its next tick), and ``NaN``/``Infinity``/``1e12`` raised out of
    ``timedelta`` as a 500 -- for ``hours``, only when the deciding vote came
    in, after the proposal had already been cleared.
    """
    if value is None:
        return
    if not math.isfinite(value) or not 0 < value <= MAX_DEADLINE_PROPOSAL_HOURS:
        raise DeadlineProposalError(
            f"{name} must be more than 0 and at most {MAX_DEADLINE_PROPOSAL_HOURS} (30 days)"
        )


def format_deadline_utc(deadline: Optional[datetime]) -> str:
    """``"2026-09-25 07:33 UTC"``, or ``"no deadline"`` -- for player notifications."""
    if deadline is None:
        return "no deadline"
    aware = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def propose_deadline(
    game_id: str,
    numeric_game_id: int,
    power: str,
    value_hours: Optional[float],
    vote_hours: Optional[float],
) -> Dict[str, Any]:
    """Start a majority vote to change (or, with ``value_hours=None``, clear)
    this game's deadline.

    Only one proposal may be pending per game at a time -- a second attempt is
    refused until the first resolves (majority, its own expiry, or the
    proposer withdrawing it via ``withdraw_deadline_proposal``). The
    proposer's own yes vote is cast automatically, the same way casting the
    deciding draw-vote is the whole action in
    ``GameService.submit_draw_vote`` -- there is no separate "now confirm it"
    step. Unlike a draw vote this needs only a majority, not unanimity, of the
    same active-power population (see ``_deadline_vote_outcome``): a pace
    change should move with most of the table, not require the one holdout to
    agree, the way ending the game outright does.
    """
    power = power.upper()
    active = game_service.active_powers(game_id)
    if active is None:
        raise DeadlineProposalError(f"game {game_id} not found")
    if power not in active:
        raise DeadlineProposalError(f"{power} is not an active power in game {game_id}")

    def propose(current: Optional[Dict[str, Any]]) -> DeadlineProposalChange:
        if current is not None:
            raise DeadlineProposalError(
                f"A deadline proposal is already pending in game {game_id}; it must "
                f"resolve or be withdrawn (/deadline {game_id} withdraw) first."
            )
        _check_proposal_hours("hours", value_hours)
        _check_proposal_hours("vote_hours", vote_hours)
        now = datetime.now(timezone.utc)
        proposal: Dict[str, Any] = {
            "proposed_by": power,
            "value_hours": value_hours,
            "votes": {power: "yes"},
            "vote_deadline": (now + timedelta(hours=vote_hours)).isoformat() if vote_hours else None,
            "created_at": now.isoformat(),
        }
        # A one-active-power edge case resolves on the spot.
        if _deadline_vote_outcome(proposal["votes"], active) == "accepted":
            return _accepted(proposal, active)
        return DeadlineProposalChange(proposal, {"status": "pending", **deadline_proposal_view(proposal, active)})

    return _run_proposal_change(game_id, numeric_game_id, propose)


def _accepted(proposal: Dict[str, Any], active: frozenset[str]) -> DeadlineProposalChange:
    """Clear an accepted proposal and set the deadline it asked for, together."""
    value_hours = proposal.get("value_hours")
    deadline = None if value_hours is None else datetime.now(timezone.utc) + timedelta(hours=value_hours)
    return DeadlineProposalChange(
        None,
        {"status": "accepted", "deadline": _iso(deadline), **deadline_proposal_view(proposal, active)},
        set_deadline=True,
        deadline=deadline,
    )


def _run_proposal_change(
    game_id: str,
    numeric_game_id: int,
    change: Callable[[Optional[Dict[str, Any]]], DeadlineProposalChange],
) -> Dict[str, Any]:
    """Run ``change`` under the row lock (``modify_deadline_proposal``). A new
    deadline gets its own 10-minute reminder, as ``POST .../deadline`` does."""
    try:
        outcome = db_service.modify_deadline_proposal(game_id, change)
    except ValueError as e:
        if isinstance(e, DeadlineProposalError):
            raise
        raise DeadlineProposalError(str(e)) from e
    if outcome.set_deadline:
        reminder_sent[numeric_game_id] = False
    return outcome.result


def vote_on_deadline_proposal(
    game_id: str, numeric_game_id: int, power: str, vote: bool
) -> Dict[str, Any]:
    """Cast (or change) ``power``'s yes/no vote on the pending deadline
    proposal. Resolves immediately once a majority is reached either way:
    ``"accepted"`` applies the proposed deadline and clears the proposal;
    ``"rejected"`` (a yes-majority is no longer mathematically possible)
    clears it with nothing changed.
    """
    power = power.upper()
    active = game_service.active_powers(game_id)
    if active is None:
        raise DeadlineProposalError(f"game {game_id} not found")

    def cast(current: Optional[Dict[str, Any]]) -> DeadlineProposalChange:
        if current is None:
            raise DeadlineProposalError(f"No deadline proposal is pending in game {game_id}")
        if power not in active:
            raise DeadlineProposalError(f"{power} is not an active power in game {game_id}")
        proposal = {**current, "votes": {**(current.get("votes") or {}), power: "yes" if vote else "no"}}
        outcome = _deadline_vote_outcome(proposal["votes"], active)
        if outcome == "accepted":
            return _accepted(proposal, active)
        if outcome == "rejected":
            return DeadlineProposalChange(None, {"status": "rejected", **deadline_proposal_view(proposal, active)})
        return DeadlineProposalChange(proposal, {"status": "pending", **deadline_proposal_view(proposal, active)})

    return _run_proposal_change(game_id, numeric_game_id, cast)


def withdraw_deadline_proposal(game_id: str, power: str) -> Dict[str, Any]:
    """Cancel the pending proposal. Only its original proposer may."""
    power = power.upper()
    active = game_service.active_powers(game_id) or frozenset()

    def withdraw(current: Optional[Dict[str, Any]]) -> DeadlineProposalChange:
        if current is None:
            raise DeadlineProposalError(f"No deadline proposal is pending in game {game_id}")
        if current.get("proposed_by") != power:
            raise DeadlineProposalError(
                f"Only {current.get('proposed_by')}, who proposed it, can withdraw it"
            )
        return DeadlineProposalChange(None, {"status": "withdrawn", **deadline_proposal_view(current, active)})

    return db_service.modify_deadline_proposal(game_id, withdraw).result


def expire_deadline_proposals(now: datetime) -> None:
    """Clear any pending deadline proposal whose own vote window has passed
    without reaching majority.

    Called from the scheduler loop alongside ``process_due_deadlines``:
    failing a stalled vote here is the only way one with no majority yet and
    an expiry set ever resolves on its own. A proposal with no expiry
    (``vote_hours`` omitted at propose time) is untouched -- it simply stays
    pending until it reaches majority or someone withdraws it, same as a draw
    vote never expires on its own either.
    """
    try:
        for game in db_service.get_games_with_pending_deadline_proposals():
            proposal = game.pending_deadline_proposal or {}
            vote_deadline_raw = proposal.get("vote_deadline")
            if not vote_deadline_raw:
                continue
            try:
                vote_deadline = datetime.fromisoformat(vote_deadline_raw)
            except ValueError:
                continue
            if vote_deadline.tzinfo is None:
                vote_deadline = vote_deadline.replace(tzinfo=pytz.UTC)
            if vote_deadline > now:
                continue
            game_id_str = str(game.game_id)

            def expire(current: Optional[Dict[str, Any]], seen: Dict[str, Any] = proposal) -> DeadlineProposalChange:
                # Only the proposal this sweep judged expired: a vote may have
                # decided it, or a new one replaced it, since it was read.
                if current != seen:
                    return DeadlineProposalChange(current, {"expired": False})
                return DeadlineProposalChange(None, {"expired": True})

            if not db_service.modify_deadline_proposal(game_id_str, expire).result["expired"]:
                continue
            try:
                notify_players(
                    int(game.id),
                    f"The deadline proposal in game {game_id_str} (from "
                    f"{proposal.get('proposed_by')}) expired without a majority; nothing changed.",
                )
            except Exception as e:
                scheduler_logger.error(
                    f"Failed to notify expired deadline proposal for game {game_id_str}: {e}"
                )
    except Exception as e:
        scheduler_logger.error(f"Error expiring deadline proposals: {e}")


def finish_processed_turn(
    game_id: str,
    numeric_game_id: int,
    *,
    prev_phase_code: Optional[str],
    trigger: str,
    exclude_telegram_id: Optional[str] = None,
) -> None:
    """Everything that follows a successful ``GameService.process_turn``, for
    **every** trigger: the manual route, the deadline scheduler, and W10's
    auto-processing.

    Each of these steps was once done by only one trigger -- the snapshot (W1),
    the cache invalidation, the notification fan-out (G3) -- and the deadline
    path never told players when its turn ended the game. One function, three
    callers, so they cannot drift again.
    """
    _notify_daide_processed(game_id, prev_phase_code)
    invalidate_cache(f"games/{game_id}")
    view = game_service.view(game_id)
    meta = game_service.meta(game_id) or {}
    if view is not None:
        # Snapshot the new board for /history/{turn} and the bot's /replay.
        try:
            db_service.create_game_snapshot(
                game_id=numeric_game_id,
                turn=int(meta.get("current_turn", 0) or 0),
                year=view["year"],
                season=view["season"],
                phase=view["phase_type"],
                phase_code=view["phase"],
                game_state=view,
                state_json=game_service.state_json(game_id),
            )
        except SQLAlchemyError as e:
            scheduler_logger.error(f"Failed to snapshot game {game_id} after its turn: {e}")
    # A deadline is scoped to the phase it was set for (Track N): spent now,
    # and nothing re-arms one.
    db_service.update_game_deadline(numeric_game_id, None)
    # Wait flags ("don't process *this* phase yet", W10) were cleared with the
    # phase by ``save_state``; clearing them again here wiped flags already
    # raised for the new phase.
    current_turn = int(meta.get("current_turn", 0) or 0)
    notify_turn_processed(
        game_id,
        numeric_game_id,
        trigger=trigger,
        game_ended=view is not None and view["status"] == "COMPLETED",
        exclude_telegram_id=exclude_telegram_id,
        # save_state keys a turn's history by the counter *before* it increments.
        processed_turn=current_turn - 1 if current_turn > 0 else None,
        processed_phase=prev_phase_code,
    )


# Cap on phases one auto-processing call may run back to back. A retreat or
# adjustment phase in which nobody but dummies has anything to do is complete
# the moment it starts, so it runs at once; the cap only stops a pathological
# loop.
MAX_AUTO_PHASES = 6


def maybe_auto_process(game_id: str) -> int:
    """W10: process the turn now if the game has ``auto_process`` on, every power
    that has something to order has submitted, and nobody has asked to wait.
    Repeats while the next phase is complete from the start. Returns how many
    phases were processed (0 almost always).

    Called after every order submission, a wait flag being cleared, auto-process
    being switched on, a seat becoming a dummy, and a turn processed by the
    deadline or by hand (whose next phase may need nothing from anyone). Two last orders arriving
    together both see "ready"; ``expected_phase_code`` in ``save_state`` lets
    exactly one process it and the other gets ``StaleGameError``, which here just
    means "someone else did it".
    """
    processed = 0
    while processed < MAX_AUTO_PHASES and game_service.ready_to_auto_process(game_id):
        prev_phase_code = (game_service.meta(game_id) or {}).get("phase_code")
        try:
            game_service.process_turn(game_id)
        except (StaleGameError, GameOverError):
            break
        processed += 1
        row = db_service.get_game_by_game_id(game_id)
        if row is None:  # deleted between the two calls
            break
        finish_processed_turn(game_id, int(row.id), prev_phase_code=prev_phase_code, trigger="auto")
    return processed


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
                        finish_processed_turn(
                            game_id_str,
                            int(game_id_val),
                            prev_phase_code=prev_phase_code,
                            trigger="deadline",
                        )
                        # The new phase may already be complete (only dummies
                        # retreat or build); with auto-process on it runs now,
                        # not never -- the deadline that would have forced it
                        # was just spent.
                        maybe_auto_process(game_id_str)
                        continue
                    # Processing failed: the deadline is still spent (Track N),
                    # so the scheduler does not retry it every tick.
                    db_service.update_game_deadline(game_id_val, None)
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
                        gid = getattr(game, "game_id", None) or game_id_val
                        notify_players(game_id_val, f"Reminder: The deadline for submitting orders in game {game_id_val} is in 10 minutes.", buttons=game_buttons(gid))  # type: ignore
                        post_to_game_group(gid, f"⏰ Game {gid}: 10 minutes until the deadline. Orders go to me in private.", dm_start=f"orders_{gid}")
                        scheduler_logger.info(f"Sent 10-minute reminder for game {game_id_val} (deadline: {deadline})")
                        reminder_sent[game_id_val] = True
    except Exception as e:
        scheduler_logger.error(f"Error in deadline scheduler: {e}")


# The scheduler loop runs every 30 s; housekeeping every 120th tick (~1 h).
_HOUSEKEEPING_EVERY_TICKS = 120


def run_housekeeping() -> None:
    """Purge delivered outbox rows and expired idempotency keys.

    Both tables only ever grow otherwise. Split out so it can be called
    directly by tests; failures are logged, never raised, because a purge is
    never worth a scheduler crash.
    """
    try:
        purged_outbox = db_service.purge_delivered_bot_notifications()
        purged_keys = db_service.purge_idempotency_keys()
        if purged_outbox or purged_keys:
            scheduler_logger.info(
                "Housekeeping: purged %d delivered notifications, %d idempotency keys",
                purged_outbox, purged_keys,
            )
    except Exception as e:
        scheduler_logger.error(f"Housekeeping failed: {e}")


async def deadline_scheduler() -> None:
    """
    Background task that checks all games with deadlines every 30 seconds.
    If a game's deadline has passed, processes the turn and clears the deadline.
    Sends reminders 10 minutes before deadline and notifies players after turn processing.
    Also expires any deadline-change proposal whose own vote window has passed
    without a majority. On startup, immediately process any missed deadlines.
    Roughly hourly it also runs ``run_housekeeping``.
    """
    # On startup: process any missed deadlines immediately
    now = datetime.now(timezone.utc)
    process_due_deadlines(now)
    expire_deadline_proposals(now)
    tick = 0
    # Main loop
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        now = datetime.now(timezone.utc)
        process_due_deadlines(now)
        check_and_send_reminders(now)
        expire_deadline_proposals(now)
        tick += 1
        if tick % _HOUSEKEEPING_EVERY_TICKS == 0:
            run_housekeeping()

