"""
Messaging commands for the Telegram bot.
"""
import logging
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post, api_get

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


async def messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View messages for a specific game."""
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
        messages = result.get("messages", [])
        if not messages:
            await update.message.reply_text("No messages found for this game.")
            return
        lines = [f"Messages for game {game_id}:"]
        for m in messages:
            ts = m["timestamp"]
            recipient = m["recipient_power"] or "ALL"
            lines.append(f"[{ts}] To {recipient}: {m['text']}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving messages: {e}")


async def show_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show messages menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        try:
            user_games_response = api_get(f"/users/{user_id}/games")
            # Extract games list from API response
            user_games = user_games_response.get("games", []) if user_games_response else []
        except requests.exceptions.HTTPError as e:
            # Handle 404 (user not found) gracefully - treat as no games
            if e.response is not None and e.response.status_code == 404:
                user_games = []
            else:
                raise  # Re-raise other HTTP errors

        # Handle different response types safely
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            # Create helpful keyboard for users not in games
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")],
                [InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "💬 *No Active Games*\n\n"
                "🎮 You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse games and pick one to join\n"
                "⏳ Join the waiting list for auto-matching\n"
                "🗺️ Check out the game board first",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        keyboard = []
        # Safely handle list slicing
        games_to_show = user_games[:10] if len(user_games) > 10 else user_games
        for game in games_to_show:
            if isinstance(game, dict):
                game_id = game.get('game_id', 'Unknown')
                power = game.get('power', 'Unknown')
                state = game.get('state', 'Unknown')
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

