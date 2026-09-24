"""The game menu ("hub"): everything about one game, one tap away.

Before this the bot had two navigation systems that did not meet -- a reply
keyboard of global menus (My Orders / View Map / Messages ...) and forty-odd
commands, most taking a game id -- and neither was organised around a game,
which is how people play ("what's happening in game 3?"). Button menus also
dropped the game they were opened from: "Submit Interactive Orders" called
``/selectunit`` with no game id, which failed for anyone in two games.

Now:

- ``/games`` (the 🎮 My games key) lists your games; one tap opens a game's
  menu, and with a single game it opens straight away.
- The menu (``g|{game_id}|hub``) shows the game's status and buttons for every
  action on it: order all units / one unit, your orders, map, messages,
  deadline, ready/not ready and -- for the game's creator -- process now.
- Every button carries its game id (``g|{game_id}|{action}[|arg]``), and
  opening a game makes it your *current game*, so bare commands (``/orderall``,
  ``/status``, ...) act on it without an id (``game_context``).
- Server notifications ("turn processed", "deadline in 10 minutes") carry the
  same ``g|`` buttons, built by ``api.shared.game_buttons``.
- A message to another power is written as a plain chat message after tapping
  its name, not as ``/message 3 FRANCE ...``; a private game's password is
  asked for the same way (``handle_awaited_text``).
"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import Any, Optional

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .api_client import api_get, api_get_bytes, api_post_reliable, queued_reply
from .game_context import GameContextError, current_game, fetch_user_games, resolve_game_and_power
from .games import (
    AWAITING, POWERS, is_group_member, format_deadline, join_game, propose_deadline, set_wait_flag, status_text,
    vote_deadline, withdraw_deadline, _format_proposal,
)
from .messages import recent_messages_text, send_diplomatic_message
from .orders import (
    Sender, my_orders_text, orderhistory_text, run_process_turn, show_unit_picker, start_order_walk,
)

logger = logging.getLogger("diplomacy.telegram_bot.hub")

# Deadline lengths offered as buttons; any other value is still /deadline's job.
DEADLINE_CHOICES = (12, 24, 48)


def _btn(text: str, game_id: str, action: str, arg: Optional[str] = None) -> InlineKeyboardButton:
    data = f"g|{game_id}|{action}" + (f"|{arg}" if arg is not None else "")
    return InlineKeyboardButton(text, callback_data=data)


def _back(game_id: str) -> list[InlineKeyboardButton]:
    return [_btn("⬅️ Game menu", game_id, "hub")]


# -- the games list -------------------------------------------------------------

def _games_list_view(user_id: str) -> tuple[str, InlineKeyboardMarkup]:
    games = fetch_user_games(user_id)
    if not games:
        return (
            "🎮 *You're not in any games yet.*\n\nFind one to join, queue for the next, or try a solo demo.",
            InlineKeyboardMarkup([[InlineKeyboardButton("🎲 Find a game", callback_data="find_game")]]),
        )
    current = current_game(user_id)
    rows = []
    for g in games[:20]:
        game_id = str(g["game_id"])
        star = "⭐ " if game_id == current else ""
        rows.append([_btn(f"{star}Game {game_id} · {g['power']}", game_id, "hub")])
    rows.append([InlineKeyboardButton("🎲 Find another game", callback_data="find_game")])
    return f"🎮 *Your games* ({len(games)})\n\nOpen one to order, see the map or message players.", InlineKeyboardMarkup(rows)


async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/games (and the 🎮 My games key): your games; with just one, its menu."""
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    send = _replier(update)
    try:
        listed = fetch_user_games(user_id)
    except requests.RequestException as e:
        await update.message.reply_text(f"Could not load your games: {e}")
        return
    if len(listed) == 1:
        await show_hub(send, user_id, str(listed[0]["game_id"]))
        return
    text, markup = _games_list_view(user_id)
    await send(text, reply_markup=markup)


async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/game [id] -- open a game's menu (and make it your current game)."""
    user = update.effective_user
    if not user or not update.message:
        return
    args = context.args or []
    user_id = str(user.id)
    send = _replier(update)
    try:
        game_id, _power = resolve_game_and_power(user_id, args[0] if args else None)
    except GameContextError as e:
        if args:
            await update.message.reply_text(e.message)
            return
        try:
            text, markup = _games_list_view(user_id)
        except requests.RequestException as err:
            await update.message.reply_text(f"Could not load your games: {err}")
            return
        await send(text, reply_markup=markup)
        return
    except requests.RequestException as e:
        await update.message.reply_text(f"Could not load your games: {e}")
        return
    await show_hub(send, user_id, game_id)


# -- the game menu --------------------------------------------------------------

def _hub_keyboard(game_id: str, power: str, state: dict, orders_status: Optional[dict], is_creator: bool) -> InlineKeyboardMarkup:
    if str(state.get("status", "")).upper() in ("COMPLETED", "FINISHED", "DRAWN", "ENDED"):
        return InlineKeyboardMarkup([
            [_btn("🗺 Final map", game_id, "map"), _btn("📜 Order history", game_id, "hist")],
            [_btn("💬 Messages", game_id, "msgs")],
            [InlineKeyboardButton("⬅️ All games", callback_data="my_games")],
        ])
    rows = [
        [_btn("📝 Order all units", game_id, "all"), _btn("🎯 One unit", game_id, "one")],
        [_btn("📋 My orders", game_id, "view"), _btn("🗺 Map", game_id, "map")],
        [_btn("💬 Messages", game_id, "msgs"), _btn("⏰ Deadline", game_id, "dl")],
    ]
    if orders_status and orders_status.get("auto_process"):
        if power in (orders_status.get("waiting") or []):
            rows.append([_btn("✅ I'm ready (let the turn run)", game_id, "rd")])
        else:
            rows.append([_btn("✋ Wait for me before processing", game_id, "nr")])
    if is_creator:
        rows.append([_btn("⚙️ Process turn now", game_id, "pt")])
    rows.append([_btn("🔄 Refresh", game_id, "hub"), InlineKeyboardButton("⬅️ All games", callback_data="my_games")])
    return InlineKeyboardMarkup(rows)


async def show_hub(send: Sender, user_id: str, game_id: str) -> None:
    """Show ``game_id``'s menu: its status, and a button for every action on it."""
    try:
        game_id, power = resolve_game_and_power(user_id, game_id)
        games_list = fetch_user_games(user_id)
        text = status_text(game_id, power, user_id, title=f"🎮 *Game {game_id} · {power}*")
        state = api_get(f"/games/{game_id}/state") or {}
    except GameContextError as e:
        await send(e.message)
        return
    except requests.RequestException as e:
        await send(f"Could not load game {game_id}: {e}")
        return
    try:
        orders_status = api_get(f"/games/{game_id}/orders_status", telegram_id=user_id)
    except requests.RequestException:
        orders_status = None
    is_creator = any(str(g["game_id"]) == game_id and g.get("is_creator") for g in games_list)
    await send(text, reply_markup=_hub_keyboard(game_id, power, state, orders_status, is_creator))


# -- the g| callback router -------------------------------------------------------

async def handle_game_callback(query: Any, context: ContextTypes.DEFAULT_TYPE, data: str) -> None:
    """``g|{game_id}|{action}[|arg]`` -- every game-menu button, and the buttons on
    server notifications. Resolving the game also makes it the current game."""
    parts = data.split("|")
    game_id, action = parts[1], parts[2]
    arg = parts[3] if len(parts) > 3 else None
    user_id = str(query.from_user.id)

    async def edit(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = 'Markdown') -> None:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    async def reply(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = 'Markdown') -> None:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    # A button under a server notification (``|n``, see api.shared.game_buttons)
    # answers in a new message, so the notification ("turn processed in game 3")
    # stays readable; menu buttons edit their menu in place.
    send = edit
    if arg == "n":
        send, arg = reply, None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id)
    except GameContextError as e:
        await send(e.message, parse_mode=None)
        return
    except requests.RequestException as e:
        await send(f"Could not load game {game_id}: {e}", parse_mode=None)
        return

    if action == "hub":
        await show_hub(send, user_id, game_id)
    elif action == "all":
        await start_order_walk(send, context, user_id, game_id)
    elif action == "one":
        await show_unit_picker(send, context, user_id, game_id)
    elif action == "view":
        await send(
            my_orders_text(game_id, power, user_id),
            reply_markup=InlineKeyboardMarkup([
                [_btn("🗑 Clear my orders", game_id, "clr"), _btn("📜 History", game_id, "hist")],
                _back(game_id),
            ]),
            parse_mode=None,
        )
    elif action == "clr":
        await send(
            f"Clear all your orders in game {game_id} for this turn?",
            reply_markup=InlineKeyboardMarkup([[_btn("🗑 Yes, clear them", game_id, "clrok")], _back(game_id)]),
            parse_mode=None,
        )
    elif action == "clrok":
        await send(_clear_orders(query.from_user.id, user_id, game_id, power), reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=None)
    elif action == "hist":
        await send(orderhistory_text(game_id), reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=None)
    elif action == "map":
        await _send_map(query, game_id)
    elif action == "msgs":
        await _show_messages(send, user_id, game_id, power)
    elif action == "msg":
        context.user_data[AWAITING] = {"kind": "compose", "game_id": game_id, "recipient": arg}
        who = "everyone" if arg == "ALL" else arg
        await send(
            f"✏️ Type your message to {who} (game {game_id}) and send it. /cancel to stop.",
            parse_mode=None,
        )
    elif action == "dl":
        await _show_deadline(send, game_id, power)
    elif action == "dlp":
        hours = None if arg == "clear" else float(arg or 24)
        text, mode = propose_deadline(game_id, power, user_id, hours)
        await send(text, reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=mode)
    elif action == "dlv":
        text, mode = vote_deadline(game_id, power, user_id, arg == "yes")
        await send(text, reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=mode)
    elif action == "dlw":
        await send(withdraw_deadline(game_id, power, user_id), reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=None)
    elif action in ("nr", "rd"):
        await send(
            set_wait_flag(game_id, power, user_id, action == "nr"),
            reply_markup=InlineKeyboardMarkup([_back(game_id)]),
            parse_mode=None,
        )
    elif action == "pt":
        await _process_turn(send, user_id, game_id)


def _clear_orders(chat_id: int, user_id: str, game_id: str, power: str) -> str:
    outcome = api_post_reliable(
        f"/games/{game_id}/orders/{power}/clear",
        {"telegram_id": user_id},
        chat_id=chat_id,
        description=f"clearing orders for game {game_id} ({power})",
    )
    if outcome.status == "queued":
        return queued_reply(outcome)
    if outcome.status == "rejected":
        return f"Error clearing orders: {outcome.error}"
    return f"🗑 Your orders in game {game_id} for this turn have been cleared."


async def _send_map(query: Any, game_id: str) -> None:
    """The board as a new photo message, with buttons to act on it."""
    try:
        img = api_get_bytes(f"/games/{game_id}/map")
    except requests.RequestException as e:
        await query.message.reply_text(f"❌ Could not draw the map for game {game_id}: {e}")
        return
    await query.message.reply_photo(
        photo=BytesIO(img),
        caption=f"🗺 Game {game_id}",
        reply_markup=InlineKeyboardMarkup([[_btn("📝 Enter orders", game_id, "all"), _btn("🎮 Game menu", game_id, "hub")]]),
    )


async def _show_messages(send: Sender, user_id: str, game_id: str, power: str) -> None:
    """Recent messages, and a button per power to write to (or to everyone)."""
    text = recent_messages_text(game_id, user_id, limit=10)
    try:
        players = api_get(f"/games/{game_id}/players") or []
    except requests.RequestException:
        players = []
    seated = sorted({p["power"] for p in players if p.get("user_id") is not None and p.get("power") != power})
    buttons = [_btn(f"✉️ {p.title()}", game_id, "msg", p) for p in seated if p in POWERS]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([_btn("📣 Everyone", game_id, "msg", "ALL")])
    rows.append(_back(game_id))
    if len(text) > 3500:
        text = "…" + text[-3500:]
    await send(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode=None)


async def _show_deadline(send: Sender, game_id: str, power: str) -> None:
    """The deadline, and buttons to put a change to a vote (or vote on one)."""
    try:
        data = api_get(f"/games/{game_id}/deadline") or {}
    except requests.RequestException as e:
        await send(f"Could not read the deadline for game {game_id}: {e}", reply_markup=InlineKeyboardMarkup([_back(game_id)]), parse_mode=None)
        return
    current = data.get("deadline")
    lines = [f"⏰ *Deadline for game {game_id}:* " + (format_deadline(current) if current else "none")]
    proposal = data.get("pending_proposal")
    rows: list[list[InlineKeyboardButton]] = []
    if proposal:
        lines.append("")
        lines.append(_format_proposal(game_id, proposal))
        voted = set(proposal.get("yes_votes") or []) | set(proposal.get("no_votes") or [])
        if power not in voted:
            rows.append([_btn("✅ Vote yes", game_id, "dlv", "yes"), _btn("❌ Vote no", game_id, "dlv", "no")])
        if proposal.get("proposed_by") == power:
            rows.append([_btn("↩️ Withdraw my proposal", game_id, "dlw")])
    else:
        lines.append("\nPropose a new deadline; it applies when a majority of players agree:")
        rows.append([_btn(f"{h}h", game_id, "dlp", str(h)) for h in DEADLINE_CHOICES])
        if current:
            rows.append([_btn("No deadline", game_id, "dlp", "clear")])
    rows.append(_back(game_id))
    await send("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def _process_turn(send: Sender, user_id: str, game_id: str) -> None:
    """The creator's "Process turn now": confirm first if orders are missing."""
    try:
        status = api_get(f"/games/{game_id}/orders_status", telegram_id=user_id) or {}
    except requests.RequestException:
        status = {}
    missing = status.get("missing") or []
    if missing:
        await send(
            f"⚠️ Still waiting on: {', '.join(missing)}. Their units will hold if you process now.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Process anyway", callback_data=f"ptforce|{game_id}")],
                _back(game_id),
            ]),
            parse_mode=None,
        )
        return
    async def plain(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = None) -> None:
        await send(text, reply_markup=reply_markup, parse_mode=parse_mode)

    await run_process_turn(plain, game_id, user_id)


# -- Find a game --------------------------------------------------------------------

async def find_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/findgame (and the 🎲 Find a game key): open games, the queue, the demo."""
    send = _replier(update)
    user = update.effective_user
    try:
        listing = api_get("/games") or {}
        mine = {str(g["game_id"]) for g in fetch_user_games(str(user.id))} if user else set()
    except requests.RequestException as e:
        await send(f"❌ Could not load games: {e}", parse_mode=None)
        return
    games_list = listing.get("games", []) if isinstance(listing, dict) else listing
    rows = []
    for g in games_list:
        game_id = str(g.get("id"))
        if game_id in mine or g.get("map_name") == "demo" or str(g.get("status", "active")).lower() != "active":
            continue
        players, seats = g.get("player_count", 0), g.get("max_players", 7)
        if players >= seats:
            continue
        # A group's games are for its members only (games.may_join).
        if g.get("channel_id") and (user is None or not await is_group_member(context.bot, g["channel_id"], user.id)):
            continue
        lock = "🔒 " if g.get("private") else ""
        group = "👥 " if g.get("channel_id") else ""
        rows.append([InlineKeyboardButton(f"{lock}{group}Game {game_id} · {players}/{seats} players", callback_data=f"select_game_{game_id}")])
        if len(rows) == 8:
            break
    rows.append([InlineKeyboardButton("⏳ Queue for the next new game", callback_data="join_waiting_list")])
    rows.append([InlineKeyboardButton("🎮 Solo demo (you play Germany)", callback_data="start_demo_game")])
    intro = "Join an open game:" if len(rows) > 2 else "No open games right now."
    await send(
        f"🎲 *Find a game*\n\n{intro}\n\n"
        "👥 = a game of one of your Telegram groups.\n"
        "⏳ The queue starts a new game when 7 players are in it.\n"
        "🎮 The demo is a solo game against simple computer opponents.",
        reply_markup=InlineKeyboardMarkup(rows),
    )


# -- typed replies --------------------------------------------------------------------

async def handle_awaited_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """If the bot asked this player for text (a message to write, a password),
    take this message as the answer. Returns whether it did."""
    awaiting = context.user_data.get(AWAITING)
    if not awaiting or not update.message or not update.effective_user:
        return False
    context.user_data.pop(AWAITING, None)
    user = update.effective_user
    text = update.message.text or ""
    game_id = awaiting["game_id"]
    if awaiting["kind"] == "join_password":
        try:
            await update.message.delete()  # keep the password out of the chat history
        except TelegramError:
            pass
        await update.effective_chat.send_message(join_game(user, game_id, awaiting["power"], text))
        return True
    recipient = awaiting.get("recipient")
    reply = send_diplomatic_message(str(user.id), user.id, game_id, None if recipient == "ALL" else recipient, text)
    await update.message.reply_text(
        reply,
        reply_markup=InlineKeyboardMarkup([[_btn("💬 Messages", game_id, "msgs"), _btn("🎮 Game menu", game_id, "hub")]]),
    )
    return True


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cancel -- stop whatever the bot was waiting for you to type."""
    if not update.message:
        return
    if context.user_data.pop(AWAITING, None):
        await update.message.reply_text("OK, cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


def _replier(update: Update) -> Sender:
    """A ``send(text, reply_markup=None, parse_mode='Markdown')`` for this update:
    a reply to a command, or an edit of the message whose button was pressed."""
    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None, parse_mode: Optional[str] = 'Markdown') -> None:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    return send


async def games_list_callback(query: Any) -> None:
    """The "⬅️ All games" button."""
    try:
        text, markup = _games_list_view(str(query.from_user.id))
    except requests.RequestException as e:
        await query.edit_message_text(f"Could not load your games: {e}")
        return
    await query.edit_message_text(text, reply_markup=markup, parse_mode='Markdown')
