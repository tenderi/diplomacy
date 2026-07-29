"""
Messaging commands for the Telegram bot.
"""
import logging
from typing import Any, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from .game_context import fetch_user_games

logger = logging.getLogger("diplomacy.telegram_bot.messages")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a private message to a specific power in a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Message failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 3:
        await update.message.reply_text("Usage: /message <game_id> <power> <text>")
        return
    game_id, power = args[0], args[1].upper()
    text = " ".join(args[2:])
    try:
        result = api_post(f"/games/{game_id}/message",
                         {"telegram_id": user_id, "recipient_power": power, "text": text})
        if result.get("status") == "ok":
            await update.message.reply_text(f"Message sent to {power} in game {game_id}.")
        else:
            await update.message.reply_text(f"Message failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Message error: {e}")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a broadcast message to all players in a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Broadcast failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /broadcast <game_id> <text>")
        return
    game_id = args[0]
    text = " ".join(args[1:])
    try:
        result = api_post(f"/games/{game_id}/broadcast",
                         {"telegram_id": user_id, "text": text})
        if result.get("status") == "ok":
            await update.message.reply_text(f"Broadcast sent in game {game_id}.")
        else:
            await update.message.reply_text(f"Broadcast failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Broadcast error: {e}")


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
    """View messages for a specific game, with sender attribution.

    Diplomacy is all about negotiation, so knowing *who* sent a message
    matters -- ``[ts] To FRANCE: ...`` alone doesn't say who sent it. Each
    line now reads ``[ts] GERMANY -> FRANCE: ...`` (sender resolved via
    ``_sender_power_map``).
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve messages: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /messages <game_id>")
        return
    game_id = args[0]
    try:
        result = api_get(f"/games/{game_id}/messages?telegram_id={user_id}")
        messages_list = result.get("messages", [])
        if not messages_list:
            await update.message.reply_text("No messages found for this game.")
            return

        sender_power = _sender_power_map(game_id)

        lines = [f"Messages for game {game_id}:"]
        for m in messages_list:
            ts = m["timestamp"]
            recipient = m["recipient_power"] or "ALL"
            sender = sender_power.get(m.get("sender_user_id"), "Unknown")
            lines.append(f"[{ts}] {sender} -> {recipient}: {m['text']}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving messages: {e}")


async def show_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show messages menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        user_games = fetch_user_games(user_id)

        if not user_games:
            # Create helpful keyboard for users not in games
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "💬 *No Active Games*\n\n"
                "🎮 You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse games and pick one to join\n"
                "⏳ Join the waiting list for auto-matching",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        keyboard = []
        # Safely handle list slicing
        games_to_show = user_games[:10] if len(user_games) > 10 else user_games
        for game in games_to_show:
            game_id = game.get('game_id', 'Unknown')
            power = game.get('power', 'Unknown')
            state = game.get('status', 'Unknown')
            # Add more context to button text
            button_text = f"💬 Game {game_id} ({power}) - {state}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_messages_{game_id}")])

        if not keyboard:
            # Fallback if games exist but are malformed
            keyboard = [[InlineKeyboardButton("🎲 Browse Games Instead", callback_data="show_games_list")]]
            await update.message.reply_text(
                "💬 *Games Data Issue*\n\n"
                "🔧 Your games data seems corrupted. Try browsing available games instead.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"💬 *Select game to view messages:* ({len(games_to_show)} active)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"💬 *Select game to view messages:* ({len(games_to_show)} active)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

    except Exception as e:
        # More helpful error message with recovery options
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="retry_messages_menu")],
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⚠️ *Temporary Issue*\n\n"
                f"🔧 Unable to load your games right now.\n"
                f"This usually means the server is starting up.\n\n"
                f"💡 *Try:*\n"
                f"• Wait a moment and try again\n"
                f"• Browse available games directly\n"
                f"• Return to main menu\n\n"
                f"*Technical details:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"⚠️ *Temporary Issue*\n\n"
                f"🔧 Unable to load your games right now.\n"
                f"This usually means the server is starting up.\n\n"
                f"💡 *Try:*\n"
                f"• Wait a moment and try again\n"
                f"• Browse available games directly\n"
                f"• Return to main menu\n\n"
                f"*Technical details:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

