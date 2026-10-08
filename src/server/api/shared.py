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
from ..nickname import sender_label
from ..game_service import GameOverError, GameService
from .. import deadline_schedule
from ..response_cache import invalidate_cache
from ..telegram_bot.alerting import AdminAlertHandler, admin_telegram_id

if TYPE_CHECKING:
    from ..daide.server import DaideServer

_shared_logger = logging.getLogger(__name__)

# One stream handler, on the root logger, for every logger in the process:
# uvicorn configures only its own loggers, and a root logger with no handler at
# all prints through Python's last-resort handler -- which stops the moment any
# handler is added to the root (``install_admin_alerts`` adds one). The root
# stays at WARNING; ``diplomacy.scheduler`` is at INFO, so its INFO lines print
# as they always have. Set up before ``Server()`` below, whose logger adds a
# handler of its own only when no ancestor has one.
if not logging.getLogger().handlers:
    _stream = logging.StreamHandler()
    _stream.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(_stream)

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

# The Telegram bot's username, without the "@": the web game page builds its
# "Link a Telegram group" link (t.me/<bot>?startgroup=link_<id>) from it.
BOT_USERNAME = os.environ.get("DIPLOMACY_BOT_USERNAME", "").strip().lstrip("@") or "IronChancellorBot"

# The maintainer's Telegram chat: error alerts and player feedback are DMed here
# (through the outbox, like any notification). Unset: neither is sent.
ADMIN_TELEGRAM_ID = admin_telegram_id(os.environ.get("DIPLOMACY_ADMIN_TELEGRAM_ID"))


def install_admin_alerts() -> Optional[AdminAlertHandler]:
    """DM every error this process logs to ``ADMIN_TELEGRAM_ID`` (throttled; see
    ``telegram_bot/alerting.py``). Called once, at app import; a no-op when unset."""
    if ADMIN_TELEGRAM_ID is None:
        return None
    admin_id = ADMIN_TELEGRAM_ID
    handler = AdminAlertHandler(
        lambda text: db_service.enqueue_bot_notification(admin_id, text), source="Diplomacy API"
    )
    logging.getLogger().addHandler(handler)
    return handler


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
    *,
    own: Optional[Callable[[list[str]], Optional[str]]] = None,
) -> None:
    """Notify all players in a game, via ``notify_user`` (the durable outbox).

    ``own``, when given, is called with each recipient's powers and returns the
    text for a reader the message is about -- addressed to them as "you"
    (BD4) -- or ``None`` for the common ``message``.

    ``buttons`` (see ``game_buttons``) ride along as inline buttons on each DM.

    ``exclude_telegram_id`` skips one player: whoever caused the event (a draw
    vote, a concession, a deadline change, ...) and already has the outcome in
    their HTTP response. The turn-processed DM is per player and goes through
    ``notify_user`` directly (see ``notify_turn_processed``).

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
    if own is not None:
        recipients = list(db_service.get_player_powers_by_telegram_id(game_id).items())
    else:
        recipients = [(t, []) for t in db_service.get_player_telegram_ids(game_id)]
    for telegram_id_val, powers in recipients:
        if exclude_telegram_id is not None and str(telegram_id_val) == str(exclude_telegram_id):
            continue
        text = (own(powers) if own is not None else None) or message
        notify_user(telegram_id_val, text, buttons)


# --- Player identity: anonymous and public games ------------------------------
#
# A game is created anonymous or public (``games.anonymous``) and stays that way.
# In an anonymous game players are known only by their power: every announcement
# and relayed message names the power alone, and no API read says who holds a
# seat -- not the name, not the Telegram id, not the numeric user id (which a
# public game's player list would map straight back to a name). In a public game
# the player's name rides along with the power everywhere it is announced.


def is_anonymous(game_id: Any) -> bool:
    """Whether ``game_id`` (the public id or the numeric primary key) is an
    anonymous game. An unknown game reads as public."""
    meta = game_service.meta(str(game_id))
    return bool(meta and meta.get("anonymous"))


def power_label(game_id: Any, power: str, user: Any = None) -> str:
    """How an announcement names ``power``: ``FRANCE`` in an anonymous game,
    ``FRANCE (Alice)`` in a public one.

    ``user`` is the player to name, for a caller that already has them -- or
    whose seat was just vacated, so a lookup would find nobody. Without it the
    seat's current holder is named. A seat nobody holds, or a player with no
    nickname, is the power alone.
    """
    power = power.upper()
    if is_anonymous(game_id):
        return power
    if user is None:
        seat = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        user_id = getattr(seat, "user_id", None) if seat is not None else None
        user = db_service.get_user_by_id(int(user_id)) if user_id is not None else None
    return sender_label(power, user)


def player_rows(game: Any) -> list[dict[str, Any]]:
    """A game's seats as API clients see them (``GET /games/{id}/players``, the
    group dashboard): ``power``, ``seated``, ``is_active`` and, in a public game
    only, ``user_id``/``nickname`` (``None`` when anonymous). Never a Telegram id:
    the route is public, and that id names a real Telegram account."""
    anonymous = bool(getattr(game, "anonymous", False))
    rows: list[dict[str, Any]] = []
    for p in db_service.get_players_by_game_id(int(game.id)):
        user = db_service.get_user_by_id(int(p.user_id)) if p.user_id is not None and not anonymous else None
        rows.append({
            "power": p.power_name,
            "seated": p.user_id is not None,
            "user_id": None if anonymous else p.user_id,
            "is_active": getattr(p, "is_active", True),
            "nickname": getattr(user, "nickname", None) if user is not None else None,
        })
    return rows


def _notify_daide_processed(game_id: str, resolved_phase: Optional[str]) -> None:
    """Bridge `DaideServer.notify_game_processed` (async) into whatever
    context a *synchronous* call site (`process_due_deadlines`, run on a worker
    thread by the scheduler, and directly from tests) happens to run in. No-op when no DAIDE listener is up (`daide_server` is
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
    (``https://t.me/<bot>?start=<dm_start>``; the bot fills in its own name). A group must never get order buttons: whatever is pressed
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
                    f"📝 Game {game_id} · {label}: orders and results",
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


def _join_names(names: list[str]) -> str:
    """``A``, ``A and B``, ``A, B and C``."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def notify_game_drawn(
    game_id: str,
    numeric_game_id: int,
    winners: list[str],
    *,
    exclude_telegram_id: Optional[str] = None,
) -> None:
    """Announce a game that just ended in an agreed draw, naming who shares it.

    A draw is not a processed turn: ``GameService.submit_draw_vote`` ends the game
    inline when the last vote reaches quorum. So this is not
    ``notify_turn_processed``, whose group post is headed "Turn Processed" and
    carries the turn's maps -- both wrong here. Every player but the deciding voter
    (who has the result in their response) gets the DM; the group gets the same
    sentence. Best-effort, like every notification: the draw is already committed.
    """
    def drawn(sharers: list[str], you: bool = False) -> str:
        names = (["you"] if you else []) + [power_label(game_id, power) for power in sharers]
        return f"Game {game_id} has ended in a draw" + (f" shared by {_join_names(names)}" if names else "") + "."

    def own(powers: list[str]) -> Optional[str]:
        # A sharer reads "shared by you, ENGLAND and ITALY" (BD4).
        if not set(powers) & set(winners):
            return None
        return drawn([p for p in winners if p not in powers], you=True)

    text = drawn(list(winners))
    try:
        notify_players(
            numeric_game_id,
            text,
            exclude_telegram_id=exclude_telegram_id,
            buttons=game_buttons(game_id, ended=True),
            own=own,
        )
    except (SQLAlchemyError, OSError) as e:
        scheduler_logger.error(f"Failed to notify players of the draw in game {game_id}: {e}")
    post_to_game_group(game_id, f"🤝 Draw - Game {game_id}\n{text}")


def after_draw_vote(
    game_id: str,
    power: str,
    vote: bool,
    result: dict[str, Any],
    *,
    exclude_telegram_id: Optional[str] = None,
) -> None:
    """Everything that follows a recorded draw vote, whichever surface cast it.

    ``result`` is what ``GameService.submit_draw_vote`` returned. The HTTP route
    (``POST /games/{id}/draw_vote``) and the DAIDE listener (``DRW`` /
    ``NOT (DRW)``, through the ``on_draw_vote`` hook ``_api_module`` gives
    ``DaideServer``) both call this, so a vote notifies the same people
    whichever way it arrives (BD8). ``exclude_telegram_id`` is the voter, who
    has the outcome in their own response; a DAIDE voter has no Telegram id.

    `submit_draw_vote` finalizes the game inline the moment quorum is reached and
    returns the outcome only to the power that cast the deciding vote -- and
    because the game is then COMPLETED, the deadline scheduler skips it
    (`get_games_with_deadlines_and_active_status`), so no later turn-processed
    fan-out covers for it (G3a). Best-effort, like every other notification: a
    Telegram outage must not fail a draw already committed to Postgres.
    """
    invalidate_cache(f"games/{game_id}")
    try:
        row = db_service.get_game_by_game_id(game_id)
        if row is None:
            return
        if result.get("quorum_reached"):
            # A draw ends the game inline, without a turn being processed --
            # there will never be another one, so clear a stale deadline
            # rather than leave it displayed by /status.
            db_service.update_game_deadline(int(row.id), None)
            notify_game_drawn(
                game_id,
                int(row.id),
                list(result.get("winners") or []),
                exclude_telegram_id=exclude_telegram_id,
            )
        elif result.get("changed"):
            # A vote that does *not* end the game is still worth announcing:
            # otherwise a player only discovers a draw is being negotiated by
            # running /status, and a draw is the one outcome every power has a
            # veto over. A withdrawal goes to the same people, or they keep
            # believing the count they were last told. A repeated yes, or a
            # withdrawal with no vote to withdraw, changed nothing: no notice.
            # Both fields are always lists from `GameService.submit_draw_vote`:
            # `votes` is the yes-voters, `required` every power that must agree.
            tally = f"({len(result.get('votes') or [])}/{len(result.get('required') or [])} agreed)"
            label = power_label(game_id, power)
            text = (
                f"{label} has voted to end game {game_id} in a draw {tally}. "
                "Draw votes last until this phase is processed. "
                "Use /draw to agree or /nodraw to withdraw."
                if vote
                else f"{label} has withdrawn its vote to end game {game_id} in a draw {tally}."
            )
            notify_players(int(row.id), text, exclude_telegram_id=exclude_telegram_id)
    except (SQLAlchemyError, OSError) as e:
        scheduler_logger.error(f"Failed to notify draw vote for game {game_id}: {e}")


def notify_turn_processed(
    game_id: str,
    numeric_game_id: int,
    *,
    trigger: str,
    game_ended: bool = False,
    exclude_telegram_id: Optional[str] = None,
    processed_turn: Optional[int] = None,
    processed_phase: Optional[str] = None,
    next_deadline_text: Optional[str] = None,
) -> None:
    """The single fan-out for "a turn was processed". Used by **both** trigger paths.

    ``next_deadline_text`` names the new phase's deadline when the game's weekly
    schedule armed one, and is appended to the DM and the channel post.

    ``processed_turn``/``processed_phase`` name the turn just adjudicated; with them
    the game's Telegram group also gets that turn's orders map and result map.
    ``game_ended`` means the turn ended the game, which only a solo victory does;
    a draw ends one without a turn and goes through ``notify_game_drawn``.

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

    The DM is per player and names the new phase (``turn_message``): in a
    retreat or adjustment phase only the powers ``GameService.phase_duties``
    lists owe orders, and they are told their dislodged units' retreat options
    or their build/disband count; everyone else is told to wait. The caller is
    excluded except when they owe orders in such a phase -- their HTTP response
    carries the resolution, not those options.

    Synchronous on purpose, so the sync scheduler path and the ``async`` route
    can share it unchanged. Since notifications became outbox inserts
    (``notify_user``) that costs one short database write per player rather
    than the two-second HTTP timeout it used to risk. Every send is
    best-effort and logged.
    """
    due = f" Next deadline: {next_deadline_text}." if next_deadline_text and not game_ended else ""
    # A new turn means the next deadline gets its own 10-minute reminder.
    reminder_sent[numeric_game_id] = False

    if game_ended:
        # A processed turn ends a game only by a solo victory (``Game.process``);
        # a draw ends it without a turn and is announced by ``notify_game_drawn``.
        view = game_service.view(game_id) or {}
        ended = f"Game {game_id} has ended"
        winners = view.get("winners") or []
        if len(winners) == 1:
            ended += f": {power_label(game_id, winners[0])} has won with a solo victory"
        try:
            notify_players(
                numeric_game_id,
                f"{ended}.",
                exclude_telegram_id=exclude_telegram_id,
                buttons=game_buttons(game_id, ended=True),
                # The winner is told "you have won" (BD4).
                own=lambda powers: (
                    f"Game {game_id} has ended: you have won with a solo victory."
                    if len(winners) == 1 and winners[0] in powers
                    else None
                ),
            )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players for game {game_id}: {e}")
        _post_turn_to_channel(game_id, f"The turn has been processed. {ended}.", processed_turn, processed_phase)
        return

    duties_view = game_service.phase_duties(game_id) or {"phase": "", "phase_type": "MOVEMENT", "duties": {}}
    label = phase_label(duties_view["phase"])
    phase_type = duties_view["phase_type"]
    duties: dict[str, dict[str, Any]] = duties_view["duties"]
    header = f"The turn has been processed for game {game_id}" + (
        " because its deadline passed." if trigger == "deadline" else "."
    )
    # Units the adjustment just processed removed for a power that ordered too
    # few disbands (BD5): told to that power's player and to the group.
    disorder: dict[str, list[str]] = {}
    try:
        if processed_turn is not None:
            disorder = game_service.civil_disorder_disbands(game_id, processed_turn)
    except SQLAlchemyError as e:
        scheduler_logger.error(f"Failed to read civil-disorder disbands for game {game_id}: {e}")
    try:
        for telegram_id, powers in db_service.get_player_powers_by_telegram_id(numeric_game_id).items():
            mine = [p for p in powers if p in duties]
            removed = {p: disorder[p] for p in sorted(powers) if p in disorder}
            # The caller already has the resolution in their HTTP response -- but
            # not their dislodged units' retreat options or their build count, so
            # in a retreat or adjustment phase they are told too when they owe
            # orders. In a movement phase their own client is already asking.
            # Nor does the response point out which units civil disorder removed.
            if (
                exclude_telegram_id is not None
                and str(telegram_id) == str(exclude_telegram_id)
                and (phase_type == "MOVEMENT" or not mine)
                and not removed
            ):
                continue
            notify_user(
                telegram_id,
                "\n".join(
                    [turn_message(header, label, phase_type, {p: duties[p] for p in mine})]
                    + [
                        civil_disorder_line(f"As {p}, you were" if len(removed) > 1 else "You were", units)
                        for p, units in removed.items()
                    ]
                )
                + due,
                game_buttons(game_id),
            )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify players for game {game_id}: {e}")

    if phase_type == "MOVEMENT":
        channel_text = f"The turn has been processed. {label}: new orders are due -- send them to me in private."
    elif duties:
        channel_text = (
            f"The turn has been processed. {label}: orders are due from {', '.join(sorted(duties))}"
            f" -- send them to me in private."
        )
    else:
        channel_text = f"The turn has been processed. {label}: nobody has anything to order."
    group_lines = [civil_disorder_line(f"{power_label(game_id, p)} was", units) for p, units in sorted(disorder.items())]
    _post_turn_to_channel(game_id, "\n".join([channel_text, *group_lines]) + due, processed_turn, processed_phase)


def civil_disorder_line(subject: str, units: list[str]) -> str:
    """One power's civil-disorder removals (``GameService.civil_disorder_disbands``):
    "You were 2 disbands short, so F KIE and A MUN were disbanded (civil disorder)." in
    its player's DM (``subject="You were"``), "GERMANY was 1 disband short, ..." in the
    group. "Short" counts the removals, so it stays true whether the power sent no
    disband, too few, or ones that were void."""
    short = "1 disband" if len(units) == 1 else f"{len(units)} disbands"
    were = "was" if len(units) == 1 else "were"
    return f"{subject} {short} short, so {_join_names(units)} {were} disbanded (civil disorder)."


def _units(n: int) -> str:
    return f"{n} unit" if n == 1 else f"{n} units"


def turn_message(header: str, label: str, phase_type: str, duties: dict[str, dict[str, Any]]) -> str:
    """The "turn processed" DM for one player, from ``GameService.phase_duties``
    restricted to the powers that player holds and owes orders for.

    Plain text: player DMs are sent without a ``parse_mode``. A movement phase
    says orders are due; a retreat phase names each dislodged unit and where
    it may go; an adjustment phase gives the build or disband count. A player
    with nothing to order in a retreat or adjustment phase is told to wait.

    The DM addresses its reader as "you" (BD4): every power in ``duties`` is
    theirs. Only a player holding more than one power owing orders is told
    which power each line is about.
    """
    if phase_type == "MOVEMENT":
        return f"{header} Orders are due for {label}."
    if not duties:
        return f"{header} {label}: you have nothing to order this phase; wait for the other powers."
    several = len(duties) > 1
    whose = f" for {_join_names(sorted(duties))}" if several else ""
    lines = [f"{header} {label}: your orders are due{whose}."]
    for power in sorted(duties):
        duty = duties[power]
        of = f" ({power})" if several else ""
        as_power = f"As {power}, you" if several else "You"
        for retreat in duty.get("retreats", []):
            if retreat["options"]:
                lines.append(
                    f"Your {retreat['unit']}{of} was dislodged: it may retreat to "
                    f"{', '.join(retreat['options'])}, or disband."
                )
            else:
                lines.append(f"Your {retreat['unit']}{of} was dislodged and has nowhere to retreat: it must disband.")
        if duty.get("build"):
            waived = f" ({duty['waived']} more waived: no free home supply centre)" if duty.get("waived") else ""
            lines.append(f"{as_power} may build {_units(duty['build'])}{waived}.")
        if duty.get("disband"):
            lines.append(f"{as_power} must disband {_units(duty['disband'])}.")
    return "\n".join(lines)


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


def game_schedule(game_id: str) -> Optional[deadline_schedule.DeadlineSchedule]:
    """The game's weekly deadline schedule, or ``None`` if it has none."""
    return deadline_schedule.from_json((game_service.meta(game_id) or {}).get("deadline_schedule"))


def schedule_view(schedule: Optional[deadline_schedule.DeadlineSchedule]) -> Optional[Dict[str, Any]]:
    """The API shape of a schedule: its stored form plus a readable ``description``."""
    if schedule is None:
        return None
    return {**schedule.to_json(), "description": schedule.describe()}


def format_scheduled_deadline(
    deadline: datetime, schedule: Optional[deadline_schedule.DeadlineSchedule]
) -> str:
    """``format_deadline_utc``, plus the schedule's local time when it is not UTC:
    ``"2026-09-28 13:00 UTC (Mon 16:00 Europe/Helsinki)"``."""
    text = format_deadline_utc(deadline)
    if schedule is None or schedule.tz_name == "UTC":
        return text
    aware = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    local = aware.astimezone(pytz.timezone(schedule.tz_name))
    return f"{text} ({local:%a %H:%M} {schedule.tz_name})"


def seats_filled(game_id: str, numeric_game_id: int) -> bool:
    """Whether every power has a seat row or is a dummy: the game has started.

    Counted as a set of powers, not rows plus dummies: a seat its player quit
    keeps its row, and the creator may then make that power a dummy, so adding
    the two counts saw one power twice and declared a game with an empty seat
    "full". A vacated row still counts -- the game started when it was taken.
    """
    return not unseated_powers(game_id, numeric_game_id)


def unseated_powers(game_id: str, numeric_game_id: int) -> list[str]:
    """The powers with neither a seat row nor dummy status, sorted; empty once
    the table is full (see ``seats_filled``).

    Always empty for the DAIDE listener's game: its seats are live DAIDE
    connections held in memory, never seat rows, so it is exempt."""
    if (game_service.meta(game_id) or {}).get("daide"):
        return []
    seated = {str(p.power_name).upper() for p in db_service.get_players_by_game_id(numeric_game_id)}
    taken = seated | set(game_service.dummy_powers(game_id))
    return sorted(set(game_service.map.initial_ownership.values()) - taken)


def unseated_message(unseated: list[str]) -> str:
    """Why a turn of a game that is not full cannot be processed (BA6)."""
    count = len(unseated)
    noun = "power is" if count == 1 else "powers are"
    names = ", ".join(p.title() for p in unseated)
    return f"{count} {noun} unseated ({names}): seat players or mark them as dummies."


def scheduled_deadline(game_id: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """The deadline a phase beginning now gets: the next slot of the game's
    weekly schedule, or ``None`` when it has none (or is over)."""
    meta = game_service.meta(game_id) or {}
    schedule = deadline_schedule.from_json(meta.get("deadline_schedule"))
    if schedule is None or meta.get("status") != "active":
        return None
    return schedule.next_deadline(now or datetime.now(timezone.utc))


def arm_scheduled_deadline(game_id: str, numeric_game_id: int) -> Optional[datetime]:
    """Set the current phase's deadline to the schedule's next slot, when the
    game has a schedule and every seat is filled. Returns what it set, or
    ``None`` (nothing changed)."""
    if not seats_filled(game_id, numeric_game_id):
        return None
    deadline = scheduled_deadline(game_id)
    if deadline is not None:
        db_service.update_game_deadline(numeric_game_id, deadline)
        reminder_sent[numeric_game_id] = False
        invalidate_cache(f"games/{game_id}")
    return deadline


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
                proposer = str(proposal.get("proposed_by")).upper()
                notify_players(
                    int(game.id),
                    f"The deadline proposal in game {game_id_str} (from "
                    f"{power_label(game_id_str, proposer)}) expired without a majority; nothing changed.",
                    # The proposer reads "Your deadline proposal" (BD4).
                    own=lambda powers, mine=proposer, gid=game_id_str: (
                        f"Your deadline proposal in game {gid} expired without a majority; nothing changed."
                        if mine in powers
                        else None
                    ),
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
    # A deadline is scoped to the phase it was set for (Track N): spent now.
    # Only a weekly schedule the players set arms the next one.
    game_ended = view is not None and view["status"] == "COMPLETED"
    next_deadline_at = None if game_ended else scheduled_deadline(game_id)
    db_service.update_game_deadline(numeric_game_id, next_deadline_at)
    # Wait flags ("don't process *this* phase yet", W10) were cleared with the
    # phase by ``save_state``; clearing them again here wiped flags already
    # raised for the new phase.
    current_turn = int(meta.get("current_turn", 0) or 0)
    notify_turn_processed(
        game_id,
        numeric_game_id,
        trigger=trigger,
        game_ended=game_ended,
        exclude_telegram_id=exclude_telegram_id,
        next_deadline_text=(
            format_scheduled_deadline(next_deadline_at, game_schedule(game_id))
            if next_deadline_at is not None
            else None
        ),
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
    that has something to order has submitted, nobody has asked to wait, and
    every power is seated or a dummy (``seats_filled``).
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
    row = db_service.get_game_by_game_id(game_id)
    # A game is not processed until every power is seated or a dummy (BA6).
    # Checked once: no step below unseats a power.
    if row is None or not seats_filled(game_id, int(row.id)):
        return 0
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


def skip_deadline_for_empty_seats(game_id: str, numeric_game_id: int, unseated: list[str]) -> None:
    """A deadline passed in a game with empty seats (BA6): the turn is not
    processed, the deadline is spent -- a weekly schedule moves to its next
    slot, a one-off deadline is cleared -- so the scheduler does not find it
    again every tick, and the players and the game's group are told why
    nothing happened. Filling the last seat arms a scheduled deadline again
    (``arm_scheduled_deadline``)."""
    scheduler_logger.info("Deadline for game %s passed with seats unfilled; not processing.", game_id)
    next_slot = scheduled_deadline(game_id)
    db_service.update_game_deadline(numeric_game_id, next_slot)
    reminder_sent[numeric_game_id] = False
    invalidate_cache(f"games/{game_id}")
    if next_slot is not None:
        after = f"The next deadline is {format_scheduled_deadline(next_slot, game_schedule(game_id))}."
    else:
        after = "Set a new deadline once the table is full."
    text = (
        f"⏰ Game {game_id}: the deadline passed, but the turn waits for a full table. "
        f"{unseated_message(unseated)} {after}"
    )
    notify_players(numeric_game_id, text, buttons=game_buttons(game_id))
    post_to_game_group(game_id, text)


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
                    game_id_str = str(getattr(game, 'game_id', None) or game_id_val)
                    unseated = unseated_powers(game_id_str, int(game_id_val))
                    if unseated:
                        skip_deadline_for_empty_seats(game_id_str, int(game_id_val), unseated)
                        continue
                    scheduler_logger.warning(f"Missed or due deadline detected for game {game_id_val} (deadline was {deadline}, now {now}). Processing turn immediately.")
                    # Process the turn. Double-processing within this worker is
                    # prevented by GameRepo.save_state's expected_phase_code check
                    # (raises StaleGameError, caught below) -- an asyncio.Lock here
                    # would only guard this one process anyway, not a second uvicorn
                    # worker racing to process the same missed deadline, so it isn't
                    # a real guard and has been removed rather than kept for show.
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
                    # so the scheduler does not retry it every tick; a weekly
                    # schedule tries again at its next slot.
                    db_service.update_game_deadline(game_id_val, scheduled_deadline(game_id_str))
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
    # The work is synchronous -- database round trips, adjudication, map
    # rendering for the group posts -- so it runs on a worker thread. Called
    # inline it held the event loop for the whole tick, and every request to the
    # API (and every DAIDE client) waited on a turn being processed.
    # ``_notify_daide_processed`` hands DAIDE news back to ``main_loop`` from
    # there, as it does for the sync routes.
    # On startup: process any missed deadlines immediately
    await asyncio.to_thread(_scheduler_tick, datetime.now(timezone.utc), startup=True)
    tick = 0
    # Main loop
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        tick += 1
        await asyncio.to_thread(
            _scheduler_tick,
            datetime.now(timezone.utc),
            housekeeping=tick % _HOUSEKEEPING_EVERY_TICKS == 0,
        )


def _scheduler_tick(now: datetime, *, startup: bool = False, housekeeping: bool = False) -> None:
    """One pass of ``deadline_scheduler``'s work. At startup: missed deadlines and
    expired proposals only (a reminder for a deadline already past is noise)."""
    process_due_deadlines(now)
    if not startup:
        check_and_send_reminders(now)
    expire_deadline_proposals(now)
    if housekeeping:
        run_housekeeping()

