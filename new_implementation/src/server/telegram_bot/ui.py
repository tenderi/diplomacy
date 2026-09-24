"""
UI and menu helpers for the Telegram bot: the reply keyboard, help texts, and
routing of plain (non-command) text messages.
"""
from telegram import Update
from telegram.ext import ContextTypes

from .games import MENU_FIND_GAME, MENU_HELP, MENU_MY_GAMES, WELCOME_TEXT, main_keyboard
from .help_text import EXAMPLES_TEXT, HELP_TEXT, RULES_TEXT
from .hub import find_game, games, handle_awaited_text


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the welcome text with the main reply keyboard."""
    message = update.callback_query.message if update.callback_query else update.message
    if message is None:
        return
    await message.reply_text(WELCOME_TEXT, reply_markup=main_keyboard(), parse_mode='Markdown')


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rules command - show basic Diplomacy rules and order syntax."""
    await update.message.reply_text(RULES_TEXT, parse_mode='Markdown')


async def examples(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /examples command - show order syntax examples."""
    await update.message.reply_text(EXAMPLES_TEXT, parse_mode='Markdown')


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help with available commands"""
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


async def refresh_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the reply keyboard (e.g. after Telegram drops it)."""
    if not update.message:
        return
    await update.message.reply_text("🔄 Menu refreshed.", reply_markup=main_keyboard())


# Labels of the eight-button keyboard the bot showed before the game menu
# existed. Telegram clients keep a reply keyboard until the bot sends a new
# one, so players who haven't pressed /start since still have these.
_OLD_MY_GAMES = {"🎮 My Games", "📋 My Orders", "🗺️ View Map", "💬 Messages"}
_OLD_FIND_GAME = {"🎲 Join Game", "⏳ Join Waiting List", "🎯 Register"}


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Plain text: an answer the bot asked for (a message being written, a
    password), or a press of the reply keyboard."""
    if not update.message or not update.message.text:
        return
    if await handle_awaited_text(update, context):
        return

    text = update.message.text.strip()
    if text == MENU_MY_GAMES or text in _OLD_MY_GAMES:
        await games(update, context)
    elif text == MENU_FIND_GAME or text in _OLD_FIND_GAME:
        await find_game(update, context)
    elif text in (MENU_HELP, "ℹ️ Help"):
        await show_help(update, context)
    else:
        await update.message.reply_text(
            "I only understand commands and the menu buttons. Tap 🎮 My games, or see /help."
        )
