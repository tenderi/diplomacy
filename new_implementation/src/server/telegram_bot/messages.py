"""
Messaging commands for the Telegram bot.
"""
import logging
from typing import Any, Dict, Optional

import requests

from telegram import Update
from telegram.ext import ContextTypes

from .api_client import ApiUnreachableError, api_get, api_post_reliable, queued_reply
from .game_context import GameContextError, fetch_user_games, resolve_game_and_power

logger = logging.getLogger("diplomacy.telegram_bot.messages")


def _target_game(user_id: str, args: list[str]) -> tuple[str, list[str]]:
    """The game a /message or /broadcast is for, and the arguments after it.

    A leading argument that is the id of one of the player's games is the game;
    otherwise the current game (``resolve_game_and_power``). A message starting
    with a number that happens to be one of your game ids is read as that game.

    **With the server unreachable** and no cached game list, a leading number is
    taken as the game id unchecked, so the message still reaches the durable
    queue (Track J: a player write is never lost); the server checks
    membership when the queued message is delivered. Raises
    ``GameContextError`` or ``ApiUnreachableError``.
    """
    try:
        mine = {str(g["game_id"]) for g in fetch_user_games(user_id)}
    except ApiUnreachableError:
        if args and args[0].isdigit():
            return args[0], args[1:]
        raise
    if args and args[0] in mine:
        game_id, _power = resolve_game_and_power(user_id, args[0])
        return game_id, args[1:]
    game_id, _power = resolve_game_and_power(user_id, None)
    return game_id, args


def send_diplomatic_message(
    user_id: str, chat_id: int, game_id: str, recipient_power: Optional[str], text: str
) -> str:
    """Send ``text`` to ``recipient_power`` in ``game_id`` (``None``: to everyone).
    Returns the reply for the sender. Shared by /message, /broadcast and the
    game menu's Messages screen."""
    if recipient_power:
        endpoint, body = f"/games/{game_id}/message", {
            "telegram_id": user_id, "recipient_power": recipient_power, "text": text,
        }
        what, done = f"message to {recipient_power} in game {game_id}", f"Message sent to {recipient_power} in game {game_id}."
    else:
        endpoint, body = f"/games/{game_id}/broadcast", {"telegram_id": user_id, "text": text}
        what, done = f"broadcast in game {game_id}", f"Broadcast sent in game {game_id}."
    # Reliable: the message is written to the durable outbox before the
    # attempt, so an unreachable server queues it rather than losing it.
    outcome = api_post_reliable(endpoint, body, chat_id=chat_id, description=f"{what}: {_excerpt(text)}")
    if outcome.status == "delivered":
        return done
    if outcome.status == "queued":
        return queued_reply(outcome)
    return f"{'Message' if recipient_power else 'Broadcast'} error: {outcome.error}"


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/message [game_id] <power> <text> -- a private message to one power."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Message failed: No user context.")
        return
    user_id = str(user.id)
    try:
        game_id, rest = _target_game(user_id, context.args or [])
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except ApiUnreachableError as e:  # no cached game list, and no game id given
        await update.message.reply_text(str(e))
        return
    if len(rest) < 2:
        await update.message.reply_text(
            "Usage: /message [game_id] <power> <text>\n\n"
            "Or write from the game menu: /game, then 💬 Messages."
        )
        return
    await update.message.reply_text(
        send_diplomatic_message(user_id, user.id, game_id, rest[0].upper(), " ".join(rest[1:]))
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/broadcast [game_id] <text> -- a message to every player in the game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Broadcast failed: No user context.")
        return
    user_id = str(user.id)
    try:
        game_id, rest = _target_game(user_id, context.args or [])
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except ApiUnreachableError as e:  # no cached game list, and no game id given
        await update.message.reply_text(str(e))
        return
    if not rest:
        await update.message.reply_text("Usage: /broadcast [game_id] <text>")
        return
    await update.message.reply_text(send_diplomatic_message(user_id, user.id, game_id, None, " ".join(rest)))


def _excerpt(text: str, limit: int = 60) -> str:
    """A short quote of the message for queue listings and delivery reports."""
    text = " ".join(text.split())
    return f'"{text}"' if len(text) <= limit else f'"{text[: limit - 1]}…"'


def _sender_power_map(game_id: str) -> Dict[Any, str]:
    """``sender_user_id`` (a numeric DB id) -> power name, built from ``GET
    /games/{id}/players``. ``GET /games/{id}/messages`` only returns
    ``sender_user_id`` (see ``src/server/api/routes/messages.py``), not the
    sender's power, so callers that want to show who actually sent a message
    need this lookup -- no new API endpoint required. Returns ``{}`` (rather
    than raising) if the players lookup fails, so a transient failure here
    degrades message attribution to "Unknown" instead of hiding the messages
    entirely.
    """
    try:
        players_list = api_get(f"/games/{game_id}/players")
    except Exception:
        return {}
    return {
        p["user_id"]: p.get("power", "Unknown")
        for p in (players_list or [])
        if p.get("user_id") is not None
    }


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/messages [game_id] -- the game's messages you can see, with senders."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve messages: No user context.")
        return
    user_id = str(user.id)
    args = context.args or []
    try:
        game_id, _power = resolve_game_and_power(user_id, args[0] if args else None)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    await update.message.reply_text(recent_messages_text(game_id, user_id))


def recent_messages_text(game_id: str, user_id: str, limit: Optional[int] = None) -> str:
    """The messages ``user_id`` can see in ``game_id`` (the last ``limit``), with
    sender attribution.

    Diplomacy is all about negotiation, so knowing *who* sent a message
    matters -- ``[ts] To FRANCE: ...`` alone doesn't say who sent it. Each
    line reads ``[ts] GERMANY -> FRANCE: ...`` (sender resolved via
    ``_sender_power_map``).
    """
    try:
        result = api_get(f"/games/{game_id}/messages?telegram_id={user_id}")
    except requests.RequestException as e:
        return f"Error retrieving messages: {e}"
    messages_list = result.get("messages", [])
    if not messages_list:
        return f"No messages in game {game_id} yet."
    if limit is not None:
        messages_list = messages_list[-limit:]
    sender_power = _sender_power_map(game_id)
    lines = [f"Messages for game {game_id}:"]
    for m in messages_list:
        recipient = m["recipient_power"] or "ALL"
        sender = sender_power.get(m.get("sender_user_id"), "Unknown")
        lines.append(f"[{m['timestamp']}] {sender} -> {recipient}: {m['text']}")
    return "\n".join(lines)
