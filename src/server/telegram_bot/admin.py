"""
Admin commands for the Telegram bot, and the solo demo game.
"""
import logging
from typing import Optional

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post
from .game_context import set_current_game
from .games import ensure_registered
from .help_text import DEMO_EXAMPLE_ORDERS, ORDER_FORMAT_NOTES

logger = logging.getLogger("diplomacy.telegram_bot.admin")


DEMO_POWER = "GERMANY"
DEMO_OPPONENTS = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]


async def start_demo_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A solo game: the player is Germany, the other six are played by the server.

    The six are civil-disorder seats (W9) in a game whose ``map_name`` is
    ``"demo"`` -- the one kind of game where the server gives its dummies
    ``simple_ai`` moves instead of holding (``GameService._demo_ai_orders``).
    Auto-processing is on, so the turn runs the moment Germany's orders are
    complete, and the player is the game's creator, so "Process turn now" works
    too. (Until this the demo seated six fake "AI" users who never ordered
    anything, and its text said the AI "won't move".)
    """
    user = update.effective_user

    async def send(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    user_id = str(user.id)
    try:
        ensure_registered(user)
        game_id = str(api_post("/games/create", {
            "map_name": "demo",
            "telegram_id": user_id,
            "dummy_powers": DEMO_OPPONENTS,
            "auto_process": True,
        })["game_id"])
        api_post(f"/games/{game_id}/join", {"telegram_id": user_id, "game_id": int(game_id), "power": DEMO_POWER})
    except requests.RequestException as e:
        await send(f"❌ Could not start a demo game: {e}")
        return
    set_current_game(user_id, game_id)

    await send(
        f"🎮 *Demo game {game_id} started!*\n\n"
        "🇩🇪 You are *Germany*. The other six powers are played by a simple computer player.\n"
        "⚡ Each turn is processed as soon as all your units have orders.\n\n"
        "Tap *Enter orders* to order your three units one by one.\n\n"
        "*Or type them:*\n"
        f"{DEMO_EXAMPLE_ORDERS}\n\n"
        f"{ORDER_FORMAT_NOTES}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Enter orders", callback_data=f"g|{game_id}|all|n"),
             InlineKeyboardButton("🗺 Map", callback_data=f"g|{game_id}|map")],
            [InlineKeyboardButton("🎮 Game menu", callback_data=f"g|{game_id}|hub|n"),
             InlineKeyboardButton("ℹ️ Demo help", callback_data=f"demo_help_{game_id}")],
        ]),
    )


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/debug -- who Telegram says you are (your numeric id is what an admin needs)."""
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    # Plain text: a display name may contain Markdown characters.
    await update.message.reply_text(
        f"🔍 Your Telegram account\n\n"
        f"User ID: {user.id}\n"
        f"Username: {user.username or 'none'}\n"
        f"Name: {user.full_name or 'none'}"
    )

