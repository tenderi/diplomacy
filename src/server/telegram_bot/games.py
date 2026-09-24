"""
Game management commands for the Telegram bot.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from .game_context import GameContextError, resolve_game_and_power, set_current_game
from .utils import escape_markdown

logger = logging.getLogger("diplomacy.telegram_bot.games")

# The waiting list is **server state**, not bot state (G5). It used to be a
# module global here, which meant every deploy silently dropped a partially
# filled queue and left the queued players waiting for a game that would never
# be created. It now lives in Postgres behind `/waiting_list/*`; this module just
# calls the API, like every other bot command.
WAITING_LIST_SIZE = 7  # Standard Diplomacy; mirrors the server's own constant for display only
POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]


# The reply keyboard under the chat. Three buttons: everything about a game is
# one tap further, in that game's menu (hub.py). The labels are matched by
# ``ui.handle_menu_buttons``, which also still answers the old eight-button
# keyboard's labels for players whose Telegram client kept it.
MENU_MY_GAMES = "🎮 My games"
MENU_FIND_GAME = "🎲 Find a game"
MENU_HELP = "ℹ️ Help"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(MENU_MY_GAMES), KeyboardButton(MENU_FIND_GAME)], [KeyboardButton(MENU_HELP)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def _full_name(user: Any) -> str:
    return f"{user.first_name} {user.last_name}".strip() if user.last_name else user.first_name


def ensure_registered(user: Any) -> None:
    """Register the Telegram user with the server (idempotent).

    Called by /start and before joining, so "register" is never a step a
    player has to know about. Raises ``requests.RequestException`` on failure.
    """
    api_post("/users/persistent_register", {
        "telegram_id": str(user.id),
        "full_name": _full_name(user),
        "username": user.username or "",
    })


WELCOME_TEXT = (
    "🏛️ *Welcome to Diplomacy!*\n\n"
    "Seven great powers, one board, and a lot of talking.\n\n"
    "🎮 *My games* -- your games; open one to order, see the map and message players\n"
    "🎲 *Find a game* -- join an open game, queue for the next one, or try a solo demo\n"
    "ℹ️ *Help* -- commands and how to write orders"
)


GROUP_WELCOME = (
    "🏛️ *Diplomacy in this group*\n\n"
    "• /newgame -- start a game for this group; everyone joins with the button I post\n"
    "• /linkgroup [game id] -- attach an existing game to this group\n\n"
    "Here I post turn results with the map, deadline reminders and players' "
    "broadcasts. *Orders and private messages go to me in a private chat* -- never "
    "in the group, where everyone would see them. Only members of this group can "
    "see or join its games."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start -- register the player (silently) and show the main menu.

    In a group it explains the group commands instead. In a private chat it also
    takes a deep-link payload from a group post's button
    (``t.me/<bot>?start=<payload>``): ``join_<id>`` shows that game's seats,
    ``orders_<id>`` starts entering orders, ``game_<id>`` opens the game menu.
    """
    if not update.message or not update.effective_user:
        return
    chat = update.effective_chat
    if chat is not None and chat.type in ("group", "supergroup"):
        await update.message.reply_text(GROUP_WELCOME, parse_mode='Markdown')
        return
    text = WELCOME_TEXT
    try:
        ensure_registered(update.effective_user)
    except requests.RequestException as e:
        logger.warning("Registration on /start failed for %s: %s", update.effective_user.id, e)
        text += "\n\n⚠️ The game server isn't answering right now; try again in a minute."
    await update.message.reply_text(text, reply_markup=main_keyboard(), parse_mode='Markdown')
    args = context.args if isinstance(context.args, list) else []
    payload = args[0] if args else ""
    kind, _, game_id = payload.partition("_")
    if game_id.isdigit() and kind in ("join", "orders", "game"):
        await _start_deep_link(update, context, kind, game_id)


async def _start_deep_link(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, game_id: str) -> None:
    """Continue from a group post's button in this private chat."""
    from .hub import show_hub  # a late import: hub imports this module
    from .orders import start_order_walk

    user_id = str(update.effective_user.id)

    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = 'Markdown') -> None:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    if kind == "join":
        try:
            if not await may_join(context.bot, game_id, update.effective_user.id):
                await send(NOT_IN_GROUP, parse_mode=None)
                return
            text, markup = _power_selection_prompt(game_id)
        except requests.RequestException as e:
            await send(f"Could not load game {game_id}: {e}", parse_mode=None)
            return
        await send(text, reply_markup=markup)
    elif kind == "orders":
        await start_order_walk(send, context, user_id, game_id)
    else:
        await show_hub(send, user_id, game_id)


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/register -- kept for players who learned it; /start registers already.

    Replies without Markdown: ``full_name`` comes from the player's Telegram
    profile, and an unescaped ``_`` or ``*`` in it made Telegram reject the
    confirmation (reported as a failed registration that had in fact worked).
    """
    user = update.effective_user
    if not user or not update.message:
        return
    try:
        ensure_registered(user)
    except requests.RequestException as e:
        await update.message.reply_text(f"Registration error: {e}")
        return
    await update.message.reply_text(
        f"✅ You're registered, {_full_name(user)}. Tap 🎲 Find a game to start playing.",
        reply_markup=main_keyboard(),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - get current game phase, deadline, and per-power
    order submission state (via ``GET /games/{id}/orders_status``; ``GET
    /games/{id}/orders`` only returns the caller's own power, so it can't answer
    "who has submitted")."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Status command failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving status: {e}")
        return

    try:
        text = status_text(game_id, power, user_id)
    except requests.RequestException as e:
        await update.message.reply_text(f"Could not retrieve status for game {game_id}: {e}")
        return
    await update.message.reply_text(text, parse_mode='Markdown')


def status_text(game_id: str, power: str, user_id: str, *, title: Optional[str] = None) -> str:
    """The /status report for ``game_id``: phase, deadline, who has ordered,
    wait flags and the draw vote. Shared with the game menu (``hub.py``), whose
    header it is. Raises ``requests.RequestException`` only when the game state
    itself can't be read; the other parts are left out if they fail."""
    view = api_get(f"/games/{game_id}/state")

    text = (
        f"{title or f'📊 *Game {game_id} Status*'}\n\n"
        f"🎯 *You are:* {power}\n"
        f"📅 *Turn:* {view.get('year')} {view.get('season')}\n"
        f"🔄 *Phase:* {view.get('phase_type')}\n"
        f"📝 *Phase Code:* {view.get('phase')}\n"
    )

    try:
        deadline_data = api_get(f"/games/{game_id}/deadline")
        deadline = deadline_data.get("deadline") if deadline_data else None
    except Exception:
        deadline = None
    if deadline:
        text += f"⏰ *Deadline:* {format_deadline(deadline)}\n"

    try:
        orders_status = api_get(f"/games/{game_id}/orders_status", telegram_id=user_id)
    except Exception:
        orders_status = None
    if orders_status:
        submitted = orders_status.get("submitted", [])
        missing = orders_status.get("missing", [])
        text += (
            "\n✅ *Submitted:* " + (", ".join(submitted) if submitted else "none") + "\n"
        )
        if missing:
            text += "⏳ *Waiting on:* " + ", ".join(missing) + "\n"
        if orders_status.get("incomplete"):
            text += "✏️ *Only some units ordered:* " + ", ".join(orders_status["incomplete"]) + "\n"
        if orders_status.get("auto_process"):
            text += "⚡ Processes automatically once all orders are in.\n"
        if orders_status.get("waiting"):
            text += "✋ *Asked to wait:* " + ", ".join(orders_status["waiting"]) + "\n"

    try:
        draw_status = api_get(f"/games/{game_id}/draw_vote_status")
    except Exception:
        draw_status = None
    if draw_status:
        draw_votes = draw_status.get("votes", [])
        draw_required = draw_status.get("required", [])
        if draw_required:
            text += (
                f"\n🕊️ *Draw vote:* {len(draw_votes)}/{len(draw_required)} voted for draw"
            )
            if draw_votes:
                text += " (" + ", ".join(draw_votes) + ")"
            text += "\n"
    return text


async def _cast_draw_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, vote: bool) -> None:
    """Shared implementation for ``/draw`` (cast a yes vote) and ``/nodraw``
    (withdraw a previously cast yes vote), via ``POST /games/{id}/draw_vote``.

    Thin client: all quorum logic (who counts, when the game ends) lives in
    ``GameService.submit_draw_vote`` -- this only resolves the caller's
    game/power, posts the vote, and reports the response back.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Draw vote failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error resolving game: {e}")
        return

    try:
        result = api_post(
            f"/games/{game_id}/draw_vote",
            {"power": power, "vote": vote, "telegram_id": user_id},
        )
    except Exception as e:
        await update.message.reply_text(f"Draw vote failed: {e}")
        return

    if result.get("quorum_reached"):
        winners = result.get("winners") or []
        winners_text = ", ".join(winners) if winners else "the surviving powers"
        await update.message.reply_text(
            f"🕊️ *Draw reached in Game {game_id}!*\n\n"
            f"The vote hit quorum and the game has ended in a draw among: {winners_text}.",
            parse_mode='Markdown',
        )
        return

    votes = result.get("votes", [])
    required = result.get("required", [])
    action = "recorded" if vote else "withdrawn"
    lines = [f"🗳️ Your draw vote for Game {game_id} has been {action}."]
    if required:
        lines.append(f"{len(votes)}/{len(required)} voted for a draw so far.")
        if votes:
            lines.append("Voted yes: " + ", ".join(votes))
    else:
        lines.append("No draw vote is currently possible (fewer than two surviving powers).")
    await update.message.reply_text("\n".join(lines))


async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /draw command - cast this power's yes vote to end the game as a
    draw. If this vote completes quorum (every surviving power has voted
    yes), the game ends immediately."""
    await _cast_draw_vote(update, context, True)


async def nodraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nodraw command - withdraw this power's previously cast yes
    vote for a draw (no-op if none was cast)."""
    await _cast_draw_vote(update, context, False)


async def _set_wait_flag(update: Update, context: ContextTypes.DEFAULT_TYPE, waiting: bool) -> None:
    """Shared by ``/notready`` (raise this power's wait flag) and ``/ready``
    (lower it), via ``POST /games/{id}/wait`` (W10)."""
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    args = context.args or []
    try:
        game_id, power = resolve_game_and_power(user_id, args[0] if args else None)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    await update.message.reply_text(set_wait_flag(game_id, power, user_id, waiting))


def set_wait_flag(game_id: str, power: str, user_id: str, waiting: bool) -> str:
    """Raise or lower ``power``'s wait flag; returns the reply for the player.
    Shared with the game menu's Ready / Not ready button."""
    try:
        result = api_post(f"/games/{game_id}/wait", {"power": power, "waiting": waiting, "telegram_id": user_id})
    except requests.RequestException as e:
        return f"Could not update game {game_id}: {e}"
    if waiting:
        return (
            f"✋ Game {game_id} will wait for you before processing this turn automatically. "
            f"Press Ready in the game menu (or /ready) when you are done. (A deadline still applies.)"
        )
    if result.get("auto_processed"):
        return f"✅ Ready -- that was the last hold-up; game {game_id}'s turn has been processed."
    return f"✅ Ready in game {game_id}."


async def notready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/notready [game_id] -- ask the table to wait before auto-processing (W10)."""
    await _set_wait_flag(update, context, True)


async def ready(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ready [game_id] -- lower your wait flag (W10)."""
    await _set_wait_flag(update, context, False)


async def autoprocess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/autoprocess <game_id> on|off -- W10: process each turn as soon as all orders are in."""
    user = update.effective_user
    if not user or not update.message:
        return
    args = context.args or []
    if len(args) != 2 or args[1].lower() not in ("on", "off"):
        await update.message.reply_text(
            "Usage: /autoprocess <game_id> on|off\n"
            "On: each turn is processed as soon as every player has sent orders, "
            "unless someone has used /notready."
        )
        return
    game_id, enabled = args[0], args[1].lower() == "on"
    try:
        result = api_post(f"/games/{game_id}/auto_process", {"enabled": enabled, "telegram_id": str(user.id)})
    except requests.RequestException as e:
        await update.message.reply_text(f"Could not change game {game_id}: {e}")
        return
    if not enabled:
        await update.message.reply_text(f"Game {game_id} no longer processes turns automatically.")
    elif result.get("auto_processed"):
        await update.message.reply_text(f"⚡ Auto-processing is on, and every order was already in: game {game_id}'s turn has been processed.")
    else:
        await update.message.reply_text(f"⚡ Game {game_id} now processes each turn as soon as all orders are in.")


def _accepted_deadline_text(result: dict) -> str:
    """The deadline an accepted proposal set, for the proposer's/voter's reply.

    The API returns the applied ``deadline`` since v2.7.97; ``value_hours`` is
    the fallback for an older API met mid-deploy.
    """
    if result.get("deadline"):
        return format_deadline(result["deadline"])
    if result.get("value_hours") is not None:
        return f"{result['value_hours']}h from now"
    return "no deadline"


def format_deadline(iso: str, now: Optional[datetime] = None) -> str:
    """``2026-09-22 14:00 UTC (in 23h 59m)`` from the API's ISO-8601 deadline.

    The API stores deadlines as naive UTC (see ``DatabaseService.
    update_game_deadline``) and returns them without an offset, so a bare
    timestamp is read as UTC. Falls back to the raw string if it won't parse.
    """
    try:
        when = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    now = now or datetime.now(timezone.utc)
    remaining = when - now
    if remaining <= timedelta(0):
        relative = "passed"
    else:
        total_minutes = int(remaining.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        days, hours = divmod(hours, 24)
        parts = [f"{days}d"] if days else []
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m")
        relative = "in " + " ".join(parts)
    return f"{when:%Y-%m-%d %H:%M} UTC ({relative})"


_DEADLINE_USAGE = (
    "Usage:\n"
    "  /deadline <game_id> <hours> - orders due in that many hours; the turn is "
    "processed automatically when it passes\n"
    "  /deadline <game_id> clear - remove the deadline (process by hand)\n"
    "  /deadline <game_id> - show the current deadline\n"
    "  /deadline <game_id> propose <hours|clear> [vote_hours] - start a majority "
    "vote to change it instead of setting it unilaterally\n"
    "  /deadline <game_id> vote <yes|no> - vote on a pending proposal\n"
    "  /deadline <game_id> withdraw - cancel your own pending proposal"
)


def _format_proposal(game_id: str, proposal: dict) -> str:
    what = f"{proposal['value_hours']}h" if proposal.get("value_hours") is not None else "clearing it"
    needed = proposal["needed_for_majority"]
    yes = proposal["yes_votes"]
    no = proposal["no_votes"]
    lines = [
        f"🗳️ *Deadline proposal for game {game_id}*",
        f"{proposal['proposed_by']} proposes: {what}",
        f"✅ Yes ({len(yes)}/{needed} needed): {', '.join(yes) or 'none'}",
        f"❌ No: {', '.join(no) or 'none'}",
    ]
    if proposal.get("vote_deadline"):
        lines.append(f"⏱ Vote closes: {format_deadline(proposal['vote_deadline'])}")
    lines.append(f"Vote with the buttons in the game menu, or /deadline {game_id} vote yes|no.")
    return "\n".join(lines)


def propose_deadline(
    game_id: str, power: str, user_id: str, hours: Optional[float], vote_hours: Optional[float] = None
) -> Tuple[str, Optional[str]]:
    """Put a deadline change (``hours``, or ``None`` to clear) to a majority vote.
    Returns ``(reply, parse_mode)``. Shared by ``/deadline propose`` and the
    game menu's Deadline buttons."""
    try:
        result = api_post(
            f"/games/{game_id}/deadline/propose",
            {"power": power, "hours": hours, "vote_hours": vote_hours, "telegram_id": user_id},
        )
    except requests.RequestException as e:
        return f"Could not propose a deadline change: {e}", None
    if result.get("status") == "accepted":
        return (
            f"✅ Applied immediately -- {power} is the only active power in game {game_id}. "
            f"Deadline: {_accepted_deadline_text(result)}.",
            None,
        )
    return _format_proposal(game_id, result), 'Markdown'


def vote_deadline(game_id: str, power: str, user_id: str, vote: bool) -> Tuple[str, Optional[str]]:
    """Vote on the pending deadline proposal. Returns ``(reply, parse_mode)``."""
    try:
        result = api_post(
            f"/games/{game_id}/deadline/vote",
            {"power": power, "vote": vote, "telegram_id": user_id},
        )
    except requests.RequestException as e:
        return f"Could not cast your vote: {e}", None
    status = result.get("status")
    if status == "accepted":
        return f"✅ Proposal passed. Game {game_id}'s deadline is now {_accepted_deadline_text(result)}.", None
    if status == "rejected":
        return f"❌ Proposal for game {game_id} was voted down; nothing changed.", None
    return _format_proposal(game_id, result), 'Markdown'


def withdraw_deadline(game_id: str, power: str, user_id: str) -> str:
    """Withdraw ``power``'s own pending deadline proposal."""
    try:
        api_post(f"/games/{game_id}/deadline/withdraw", {"power": power, "telegram_id": user_id})
    except requests.RequestException as e:
        return f"Could not withdraw the proposal: {e}"
    return f"Withdrew {power}'s deadline proposal for game {game_id}."


async def deadline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /deadline -- show, set, clear, or majority-vote-propose a game's
    order deadline.

    The game id is required (unlike ``/draw``), because ``/deadline 12`` would
    be ambiguous between game 12 and twelve hours. Setting goes through
    ``POST /games/{id}/deadline`` with the caller's ``telegram_id``, so the
    server checks membership and tells the other players. Deadlines are never
    imposed by the server (Track N): this command (or a resolved
    ``propose``/``vote``) is the only way a game gets one, and it is spent
    when its phase is processed.

    ``<hours>``/``clear`` set it unilaterally, same as always -- any single
    player still can, nothing here removes that. ``propose``/``vote``/
    ``withdraw`` are the alternative for a table that would rather decide the
    pace together: they need the caller's *power*, not just their telegram id
    (only the assigned player for a power may propose or vote it), so they
    resolve it via ``resolve_game_and_power`` where the plain set/clear path
    above does not bother.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Deadline command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if not args:
        await update.message.reply_text(_DEADLINE_USAGE)
        return

    try:
        game_id, power = resolve_game_and_power(user_id, args[0])
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error resolving game: {e}")
        return

    if len(args) == 1:
        try:
            data = api_get(f"/games/{game_id}/deadline")
        except Exception as e:
            await update.message.reply_text(f"Could not read the deadline for game {game_id}: {e}")
            return
        current = data.get("deadline") if data else None
        if current:
            await update.message.reply_text(f"⏰ Deadline for game {game_id}: {format_deadline(current)}")
        else:
            await update.message.reply_text(
                f"Game {game_id} has no deadline, so the turn waits until every order is in "
                f"(with auto-process on) or the game's creator processes it. Set one with "
                f"/deadline {game_id} <hours>, or propose one for a vote from the game menu "
                f"(/game {game_id})."
            )
        proposal = data.get("pending_proposal") if data else None
        if proposal:
            await update.message.reply_text(_format_proposal(game_id, proposal), parse_mode='Markdown')
        return

    arg = args[1].lower()

    if arg == "propose":
        if len(args) < 3:
            await update.message.reply_text(_DEADLINE_USAGE)
            return
        value_arg = args[2].lower()
        hours: Optional[float] = None
        if value_arg not in ("clear", "none", "off", "remove"):
            try:
                hours = float(value_arg.rstrip("h"))
            except ValueError:
                await update.message.reply_text(_DEADLINE_USAGE)
                return
            if not 0 < hours <= 24 * 30:
                await update.message.reply_text("Hours must be more than 0 and at most 720 (30 days).")
                return
        vote_hours: Optional[float] = None
        if len(args) >= 4:
            try:
                vote_hours = float(args[3].rstrip("h"))
            except ValueError:
                await update.message.reply_text(_DEADLINE_USAGE)
                return
            if not 0 < vote_hours <= 24 * 30:  # also false for nan
                await update.message.reply_text("Vote hours must be more than 0 and at most 720 (30 days).")
                return
        text, mode = propose_deadline(game_id, power, user_id, hours, vote_hours)
        await update.message.reply_text(text, parse_mode=mode)
        return

    if arg == "vote":
        if len(args) < 3 or args[2].lower() not in ("yes", "no", "y", "n"):
            await update.message.reply_text(f"Usage: /deadline {game_id} vote yes|no")
            return
        text, mode = vote_deadline(game_id, power, user_id, args[2].lower() in ("yes", "y"))
        await update.message.reply_text(text, parse_mode=mode)
        return

    if arg == "withdraw":
        await update.message.reply_text(withdraw_deadline(game_id, power, user_id))
        return

    if arg in ("clear", "none", "off", "remove"):
        new_deadline: Optional[datetime] = None
    else:
        try:
            hours = float(arg.rstrip("h"))
        except ValueError:
            await update.message.reply_text(_DEADLINE_USAGE)
            return
        if not 0 < hours <= 24 * 30:
            await update.message.reply_text("Hours must be more than 0 and at most 720 (30 days).")
            return
        new_deadline = datetime.now(timezone.utc) + timedelta(hours=hours)

    try:
        result = api_post(
            f"/games/{game_id}/deadline",
            {"deadline": new_deadline.isoformat() if new_deadline else None, "telegram_id": user_id},
        )
    except Exception as e:
        await update.message.reply_text(f"Could not set the deadline: {e}")
        return

    stored = result.get("deadline") if result else None
    if stored:
        await update.message.reply_text(
            f"⏰ Deadline for game {game_id} set: {format_deadline(stored)}.\n"
            f"The turn is processed automatically when it passes; everyone has been told."
        )
    else:
        await update.message.reply_text(
            f"Deadline for game {game_id} removed; the turn will be processed by hand."
        )


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /players command - list all players in current game with their powers."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Players command failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, _power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving players: {e}")
        return

    try:
        # GET /games/{id}/players returns a bare list, not {"players": [...]}.
        players_list = api_get(f"/games/{game_id}/players")
    except Exception as e:
        await update.message.reply_text(f"Could not retrieve players for game {game_id}: {e}")
        return

    try:
        state = api_get(f"/games/{game_id}/state")
    except requests.RequestException:  # the seat list is still worth showing without them
        state = None
    dummies = (state.get("dummy_powers") or []) if isinstance(state, dict) else []

    if not players_list and not dummies:
        await update.message.reply_text(f"No players found in game {game_id}.")
        return

    # Format player list. `full_name` is user-controlled (the player's Telegram
    # profile name) and this message is sent with parse_mode='Markdown', so it
    # must be escaped -- an unescaped `_`/`*`/`` ` ``/`[` here previously made
    # Telegram reject the whole message with no try/except around this call to
    # catch it, so /players silently did nothing for that player.
    lines = [f"👥 *Players in Game {game_id}*\n"]
    for player in players_list:
        power = player.get('power', 'Unknown')
        username = escape_markdown(player.get('full_name') or 'Unknown')
        is_active = player.get('is_active', True)
        status_emoji = "✅" if is_active else "❌"
        lines.append(f"{status_emoji} *{power}* - {username}")
    for power in dummies:
        lines.append(f"🤖 *{power}* - civil disorder")

    try:
        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
    except Exception as e:
        logger.warning(f"Failed to send /players listing for game {game_id}: {e}")
        await update.message.reply_text(f"Could not display players for game {game_id}: {e}")


_DUMMY_USAGE = (
    "Usage: /dummy <game_id> <power> [off]\n"
    "Leave an empty seat to civil disorder (it holds, and disbands when it must), "
    "or add `off` to open it for a player again. Only the game's creator can."
)


async def dummy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/dummy <game_id> <power> [off] -- W9: leave a seat to civil disorder, or reopen it."""
    user = update.effective_user
    if not user or not update.message:
        return
    args = context.args or []
    if len(args) not in (2, 3) or (len(args) == 3 and args[2].lower() != "off"):
        await update.message.reply_text(_DUMMY_USAGE, parse_mode='Markdown')
        return
    game_id, power = args[0], args[1].upper()
    make_dummy = len(args) == 2
    if power not in POWERS:
        await update.message.reply_text(f"Unknown power {power}. Powers: {', '.join(POWERS)}.")
        return
    try:
        result = api_post(
            f"/games/{game_id}/dummies",
            {"power": power, "dummy": make_dummy, "telegram_id": str(user.id)},
        )
    except requests.RequestException as e:
        await update.message.reply_text(f"Could not change {power} in game {game_id}: {e}")
        return
    now = ", ".join(result.get("dummy_powers") or []) or "none"
    what = "is now played by civil disorder" if make_dummy else "is open for a player again"
    await update.message.reply_text(f"{power} {what} in game {game_id}. Civil-disorder powers: {now}.")


def _power_selection_prompt(game_id: str) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Build the "choose a power" text + keyboard for ``game_id``.

    Shared by the inline "Browse Games" callback flow (``show_power_selection``)
    and ``/join <game_id>`` with no power argument -- docs/TELEGRAM_BOT_COMMANDS.md
    documents ``/join <game_id>`` as showing this menu, so both entry points
    into it need to render the same thing. Returns ``(text, None)`` for the
    "game not found" / "game full" cases (nothing to attach a keyboard to).
    """
    game_state = api_get(f"/games/{game_id}/state")
    if not game_state:
        return f"Could not retrieve game {game_id}.", None

    # Bare list, not {"players": [...]}. A seat whose player quit still has a
    # row but no user_id -- it is open, and /join takes it over.
    players_data = api_get(f"/games/{game_id}/players")
    taken_powers = {
        player.get('power') for player in (players_data or []) if player.get('user_id') is not None
    }
    # Civil-disorder dummies (W9) are not joinable; the game's creator opens them.
    taken_powers |= set(game_state.get("dummy_powers") or [])
    private = bool(game_state.get("private"))
    keyboard = []
    for power in POWERS:
        if power not in taken_powers:
            button_text = f"Join as {power}"
            callback_data = f"join_game_{game_id}_{power}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if not keyboard:
        return f"Game {game_id} is full. All powers are taken.", None

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_games")])
    text = f"🎮 *Select Power for Game {game_id}*\n\nAvailable powers:"
    if private:
        # W8: a button can't carry the password, so choosing a power asks for it.
        text = (
            f"🔒 *Game {game_id} is private.* Choose a power, then send the password "
            f"the game's creator gave you.\n\nAvailable powers:"
        )
    return text, InlineKeyboardMarkup(keyboard)


# ``context.user_data[AWAITING]`` holds what the player's next plain-text message
# answers: a private game's join password here, or a diplomatic message being
# written in the game menu (hub.py). ``hub.handle_awaited_text`` consumes it.
AWAITING = "awaiting_text"


# Chat-member statuses that count as being in a group (a "restricted" member
# still is one; "left" and "kicked" are not).
_IN_GROUP = {"creator", "administrator", "member", "restricted"}
NOT_IN_GROUP = (
    "🔒 That game belongs to a Telegram group you're not in. Ask its players to add you "
    "to the group, then join from there."
)


async def is_group_member(bot: Any, chat_id: Any, user_id: int) -> bool:
    """Is ``user_id`` in the Telegram group ``chat_id``? False when Telegram says
    no, or can't say (the bot was removed from the group, the group is gone)."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
    except TelegramError:
        return False
    status = getattr(member, "status", "")
    return status in _IN_GROUP and getattr(member, "is_member", True) is not False


async def may_join(bot: Any, game_id: str, user_id: int) -> bool:
    """Players see and join only games from groups they're in: a game linked to
    a Telegram group is open to that group's members; any other game to anyone.
    Raises ``requests.RequestException`` if the game's group can't be read."""
    info = api_get(f"/games/{game_id}/channel") or {}
    if not info.get("linked"):
        return True
    return await is_group_member(bot, info.get("channel_id"), user_id)


async def join_from_button(query: Any, context: ContextTypes.DEFAULT_TYPE, game_id: str, power: str) -> None:
    """A "Join as <POWER>" button. A private game asks for its password first."""
    try:
        if not await may_join(context.bot, game_id, query.from_user.id):
            await query.edit_message_text(NOT_IN_GROUP)
            return
        state = api_get(f"/games/{game_id}/state")
    except requests.RequestException as e:
        await query.edit_message_text(f"❌ Failed to join: {e}")
        return
    if (state or {}).get("private"):
        context.user_data[AWAITING] = {"kind": "join_password", "game_id": str(game_id), "power": power}
        await query.edit_message_text(
            f"🔒 Send the password for game {game_id} as your next message "
            f"(I'll delete it from the chat). /cancel to stop."
        )
        return
    await query.edit_message_text(join_game(query.from_user, game_id, power, None))


def join_game(user: Any, game_id: str, power: str, password: Optional[str]) -> str:
    """Register (if needed) and take ``power`` in ``game_id``. Returns the reply."""
    payload: dict = {"telegram_id": str(user.id), "game_id": int(game_id), "power": power}
    if password is not None:
        payload["join_password"] = password
    try:
        ensure_registered(user)
        result = api_post(f"/games/{game_id}/join", payload)
    except requests.RequestException as e:  # an HTTP error's text is the server's detail
        return f"❌ Could not join game {game_id}: {e}"
    if result.get("status") == "already_joined":
        return f"You are already in game {game_id} as {power}."
    if result.get("status") != "ok":
        return f"❌ Could not join game {game_id}: {result.get('message', 'Unknown error')}"
    set_current_game(str(user.id), str(game_id))
    return f"🎉 You joined game {game_id} as {power}! Open it any time with /game {game_id}."


async def show_power_selection(update: Update, game_id: str) -> None:
    """Show available powers for a specific game (inline-button entry point)."""
    query = update.callback_query
    if not query:
        return
    try:
        if not await may_join(query.get_bot(), game_id, query.from_user.id):
            await query.edit_message_text(NOT_IN_GROUP)
            return
        text, reply_markup = _power_selection_prompt(game_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {str(e)}")
        return
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def _join_password_arg(update: Update, args: list[str], index: int) -> Optional[str]:
    """W8: the join password from ``args[index:]`` (it may contain spaces), or None.

    When one is given, the player's message is deleted -- best effort; bots may
    delete incoming messages in private chats -- so the password does not sit
    in the chat history.
    """
    if len(args) <= index:
        return None
    if update.message is not None:
        try:
            await update.message.delete()
        except TelegramError:
            pass
    return " ".join(args[index:])


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join command.

    ``/join <game_id>`` (no power) shows the inline power-selection menu --
    this is what docs/TELEGRAM_BOT_COMMANDS.md documents. ``/join <game_id>
    <power>`` joins directly, for players who already know which power they
    want (e.g. scripted use, or after seeing the menu once).
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Join command failed: No user context.")
        return
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /join <game_id> [power] [password]\n\nOr browse open games with /findgame."
        )
        return
    game_id = args[0]
    try:
        allowed = await may_join(context.bot, game_id, user.id)
    except requests.RequestException as e:
        await update.message.reply_text(f"Join error: {e}")
        return
    if not allowed:
        await update.message.reply_text(NOT_IN_GROUP)
        return

    if len(args) == 1:
        try:
            text, reply_markup = _power_selection_prompt(game_id)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
            return
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    power = args[1].upper()
    password = await _join_password_arg(update, args, 2)
    await update.message.reply_text(join_game(user, game_id, power, password))


async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quit command - quit a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Quit command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /quit <game_id>")
        return
    game_id = args[0]
    try:
        result = api_post(f"/games/{game_id}/quit", {"telegram_id": user_id, "game_id": int(game_id)})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have left Game {game_id}.")
        elif result.get("status") == "not_in_game":
            await update.message.reply_text(f"You are not in Game {game_id}.")
        else:
            await update.message.reply_text(f"Failed to quit: {result.get('message', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Quit error: {e}")


async def replace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /replace command - replace a player in a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Replace command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /replace <game_id> <power> [password]")
        return
    game_id = args[0]
    power = args[1].upper()
    try:
        replace_payload: dict = {"telegram_id": user_id, "power": power}
        replace_password = await _join_password_arg(update, args, 2)
        if replace_password is not None:
            replace_payload["join_password"] = replace_password
        result = api_post(f"/games/{game_id}/replace", replace_payload)
        if result.get("status") == "ok":
            await update.message.reply_text(f"✅ Successfully replaced player for {power} in Game {game_id}!")
        else:
            await update.message.reply_text(f"Failed to replace: {result.get('message', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Replace error: {e}")


async def _answer(update: Update, text: str, parse_mode: Optional[str] = None) -> None:
    """Reply to a command, or replace the message whose button was pressed."""
    if update.message:
        await update.message.reply_text(text, parse_mode=parse_mode)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=parse_mode)


async def wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Join the automatic-matching queue; the server creates a game when it fills.

    Reached from the Find a game screen's "Join the queue" button (and the old
    ``/wait`` command). A thin wrapper over ``POST /waiting_list/join`` (G5).
    Everything this used to do locally -- holding the queue in a module global,
    deciding when it was full, creating the game, assigning powers, and
    "notifying" players through a callback that only wrote a log line -- now
    happens server-side, where the queue survives a restart and filling it is
    atomic. The six players who were already queued are DM'd by the server;
    this reply is only for the one who just tipped it over.

    Until the queue could be joined from a button this only handled a command:
    the button's update has no ``message``, so pressing it did nothing at all.
    """
    user = update.effective_user
    if not user:
        return

    user_id = str(user.id)
    try:
        ensure_registered(user)
        result = api_post(
            "/waiting_list/join", {"telegram_id": user_id, "full_name": _full_name(user)}
        )
    except requests.RequestException as e:
        logger.error(f"Failed to join waiting list for {user_id}: {e}")
        await _answer(update, "❌ Could not join the queue right now. Please try again in a minute.")
        return

    if result.get("game_created"):
        assignments = result.get("assignments") or {}
        your_power = next(
            (power for power, tid in assignments.items() if str(tid) == user_id), None
        )
        if result.get("game_id") is not None:
            set_current_game(user_id, str(result["game_id"]))
        power_line = f"You've been assigned *{your_power}*.\n\n" if your_power else ""
        await _answer(
            update,
            f"🎮 *Game {result.get('game_id')} created!*\n\n"
            f"{power_line}"
            f"All {WAITING_LIST_SIZE} players have been notified.\n"
            f"Open it with /game to enter orders.",
            parse_mode='Markdown',
        )
        return

    size = result.get("size", 0)
    required = result.get("required", WAITING_LIST_SIZE)
    if result.get("status") == "already_queued":
        await _answer(update, f"⏳ You're already in the queue ({size}/{required} players). /leavequeue to leave it.")
        return

    await _answer(
        update,
        f"⏳ You're in the queue ({size}/{required} players).\n\n"
        f"When {required} players have joined, a game starts and you get a message here.\n"
        f"/leavequeue to leave it.",
    )


async def leave_waiting_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Leave the automatic-matching queue (``/leavequeue``, formerly ``/unwait``).

    Added with G5: once the queue is durable, a player who changes their mind
    needs a way out, and previously the only "exit" was the bot restarting.
    """
    user = update.effective_user
    if not user:
        return

    try:
        result = api_post("/waiting_list/leave", {"telegram_id": str(user.id)})
    except requests.RequestException as e:
        logger.error(f"Failed to leave waiting list for {user.id}: {e}")
        await _answer(update, "❌ Could not leave the queue right now.")
        return

    if result.get("status") == "removed":
        await _answer(
            update,
            f"✅ You left the queue. "
            f"({result.get('size', 0)}/{result.get('required', WAITING_LIST_SIZE)} still waiting)",
        )
    else:
        await _answer(update, "You weren't in the queue.")
