"""
Map display commands for the Telegram bot.

The bot is a thin client over the HTTP API -- it never imports the engine or
the SVG/PNG board-drawing package. Every map image shown here is fetched as
raw PNG bytes from a ``server.api.routes.maps`` endpoint via
``api_client.api_get_bytes``; the server does all unit-shape conversion and
board drawing itself.
"""
import logging
from io import BytesIO

from telegram import Update
from telegram.ext import ContextTypes

from .api_client import api_get_bytes

logger = logging.getLogger("diplomacy.telegram_bot.maps")


async def send_game_map(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Send the live game map with current state, fetched from ``GET /games/{id}/map``."""
    try:
        img_bytes = api_get_bytes(f"/games/{game_id}/map")
    except Exception as e:
        error_msg = f"❌ Error generating game map: {e}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
        return

    caption = f"🗺️ *Game {game_id} Map*"
    if update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=BytesIO(img_bytes), caption=caption, parse_mode='Markdown'
        )
    else:
        await update.message.reply_photo(
            photo=BytesIO(img_bytes), caption=caption, parse_mode='Markdown'
        )


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command to display a game map."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Map command failed: No user context.")
        return
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /map <game_id>")
        return
    await send_game_map(update, context, args[0])


async def replay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /replay command to show a historical game state.

    Fetches ``GET /games/{id}/map/history/{turn}`` -- a PNG rendered server-side
    from the persisted ``map_snapshots`` row for that turn.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Replay command failed: No user context.")
        return
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /replay <game_id> <turn>")
        return
    game_id, turn = args[0], args[1]
    try:
        img_bytes = api_get_bytes(f"/games/{game_id}/map/history/{turn}")
    except Exception as e:
        await update.message.reply_text(f"No board state found for game {game_id} turn {turn}: {e}")
        return
    await update.message.reply_photo(
        photo=BytesIO(img_bytes), caption=f"Board for game {game_id}, turn {turn}"
    )
