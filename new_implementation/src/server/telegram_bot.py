"""
Telegram Diplomacy Bot - Initial scaffold

This bot will handle registration, order submission, and notifications for Diplomacy games.
"""
import logging
import os
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from io import BytesIO
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from telegram.ext import Application
from src.engine.map import Map
import random
import json
from typing import Dict, List, Tuple, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.constants import ParseMode
import uvicorn
import threading
import time

# Global cache for the default map image (permanent since map never changes)
_DEFAULT_MAP_CACHE = None

def get_cached_default_map() -> Optional[bytes]:
    """Get the cached default map image, or None if not cached."""
    global _DEFAULT_MAP_CACHE
    return _DEFAULT_MAP_CACHE

def set_cached_default_map(img_bytes: bytes) -> None:
    """Cache the default map image permanently."""
    global _DEFAULT_MAP_CACHE
    _DEFAULT_MAP_CACHE = img_bytes

def generate_default_map() -> bytes:
    """Generate the default map image (expensive operation)."""
    # Use standard map with no units (empty game state)
    # Use configurable path for maps directory
    svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard_fixed.svg")
    
    # Empty units dictionary for clean map display
    units = {}
    
    # Generate map image
    return Map.render_board_png(svg_path, units)

logging.basicConfig(level=logging.INFO)

# Handle AWS Secrets Manager JSON format for Telegram token
def get_telegram_token() -> str:
    raw_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not raw_token:
        return ""

    # Check if token is in JSON format (from AWS Secrets Manager)
    if raw_token.startswith("{") and "TELEGRAM_BOT_TOKEN" in raw_token:
        try:
            import json
            token_data = json.loads(raw_token)
            return token_data.get("TELEGRAM_BOT_TOKEN", "")
        except json.JSONDecodeError:
            logging.warning(f"Failed to parse TELEGRAM_BOT_TOKEN as JSON: {raw_token}")
            return raw_token

    return raw_token

TELEGRAM_TOKEN = get_telegram_token()
API_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000")

# Debug token extraction for troubleshooting
logging.info(f"🔑 Raw TELEGRAM_BOT_TOKEN: '{os.environ.get('TELEGRAM_BOT_TOKEN', 'NOT_SET')[:50]}...'")
logging.info(f"🔑 Extracted TELEGRAM_TOKEN: '{TELEGRAM_TOKEN[:20] if TELEGRAM_TOKEN else 'EMPTY'}...'")
logging.info(f"🔑 Token format valid: {TELEGRAM_TOKEN.count(':') == 1 and len(TELEGRAM_TOKEN) > 20}")

# --- Helper functions for API calls ---
def api_post(endpoint: str, json: dict) -> dict:
    resp = requests.post(f"{API_URL}{endpoint}", json=json)
    resp.raise_for_status()
    return resp.json()

def api_get(endpoint: str) -> dict:
    resp = requests.get(f"{API_URL}{endpoint}")
    resp.raise_for_status()
    return resp.json()

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    # Create main menu keyboard
    keyboard = [
        [KeyboardButton("🎯 Register"), KeyboardButton("🎮 My Games")],
        [KeyboardButton("🎲 Join Game"), KeyboardButton("⏳ Join Waiting List")],
        [KeyboardButton("📋 My Orders"), KeyboardButton("🗺️ View Map")],
        [KeyboardButton("💬 Messages"), KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, 
                                       one_time_keyboard=False)

    await update.message.reply_text(
        "🏛️ *Welcome to Diplomacy!*\n\n"
        "I'm your diplomatic assistant. Use the menu below or type commands:\n\n"
        "🎯 Start with *Register* if you're new\n"
        "🎮 Check *My Games* to see your current games\n"
        "🎲 *Join Game* to enter a specific game\n"
        "⏳ *Join Waiting List* for automatic game matching",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Registration failed: No user context.")
        return
    user_id = str(user.id)
    full_name = getattr(user, 'full_name', None)
    try:
        api_post("/users/persistent_register", {"telegram_id": user_id, "full_name": full_name})

        # Show main menu after successful registration
        keyboard = [
            [KeyboardButton("🎯 Register"), KeyboardButton("🎮 My Games")],
            [KeyboardButton("🎲 Join Game"), KeyboardButton("⏳ Join Waiting List")],
            [KeyboardButton("📋 My Orders"), KeyboardButton("🗺️ View Map")],
            [KeyboardButton("💬 Messages"), KeyboardButton("ℹ️ Help")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

        await update.message.reply_text(
            f"🎉 *Registration successful!*\n\n"
            f"Welcome {full_name or 'Unknown'} (ID: {user_id})\n\n"
            f"🎲 Use *Join Game* to select from available games\n"
            f"⏳ Or use *Join Waiting List* for auto-matching",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"Registration error: {e}")

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    try:
        # List all games the user is in
        user_games = api_get(f"/users/{user_id}/games")

        # Handle different response formats safely
        if not user_games or not isinstance(user_games, (list, dict)):
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")],
                [InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎮 *No Active Games*\n\n"
                "You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse available games\n"
                "⏳ Join the waiting list for auto-matching\n"
                "🗺️ See what Diplomacy looks like",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        # Handle both list format and dict format with 'games' key
        if isinstance(user_games, dict):
            games_list = user_games.get("games", [])
        else:
            games_list = user_games

        if not games_list or len(games_list) == 0:
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")],
                [InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎮 *No Active Games*\n\n"
                "You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse available games to join\n"
                "⏳ Join the waiting list for auto-matching\n"
                "🗺️ See what the Diplomacy board looks like",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        # Format games with better information
        lines = [f"🎮 *Your Active Games* ({len(games_list)})\n"]
        for g in games_list:
            if isinstance(g, dict):
                game_id = g.get('game_id', 'Unknown')
                power = g.get('power', 'Unknown')
                state = g.get('state', 'Unknown')
                turn = g.get('turn', 'N/A')
                lines.append(f"🏰 **Game {game_id}** - Playing as **{power}**")
                lines.append(f"   📊 Status: {state} | Turn: {turn}")

        # Add action buttons
        keyboard = [
            [InlineKeyboardButton("📋 Manage Orders", callback_data="show_orders_menu")],
            [InlineKeyboardButton("🗺️ View Game Maps", callback_data="show_map_menu")],
            [InlineKeyboardButton("💬 View Messages", callback_data="show_messages_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⚠️ *Can't Load Your Games*\n\n"
            f"🔧 Unable to retrieve your game status.\n"
            f"This is usually temporary.\n\n"
            f"💡 *Try:*\n"
            f"• Browse available games directly\n"
            f"• Return to main menu and try again\n\n"
            f"*Error:* {str(e)[:100]}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# Interactive game selection with buttons
async def show_available_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available games with inline buttons"""
    try:
        games = api_get("/games")
        if not games:
            await update.message.reply_text("🎮 No games available. Use /wait to join the waiting list.")
            return

        # Create inline keyboard with available games
        keyboard = []
        for game in games[:10]:  # Limit to 10 games
            game_id = game.get('id', 'Unknown')
            status = game.get('state', 'Unknown')
            players = game.get('player_count', 0)
            max_players = game.get('max_players', 7)

            game_text = f"Game {game_id} | {status} | {players}/{max_players} players"
            keyboard.append([InlineKeyboardButton(game_text, callback_data=f"select_game_{game_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🎲 *Select a game to join:*", reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        await update.message.reply_text(f"❌ Error loading games: {str(e)}")

async def show_power_selection(update, game_id):
    """Show available powers for a specific game"""
    try:
        # Get available powers for the game
        available_powers = ["Austria", "England", "France", "Germany", "Italy", "Russia", "Turkey"]

        keyboard = []
        for i in range(0, len(available_powers), 2):  # 2 buttons per row
            row = []
            for j in range(2):
                if i + j < len(available_powers):
                    power = available_powers[i + j]
                    row.append(InlineKeyboardButton(f"🏰 {power}", callback_data=f"join_game_{game_id}_{power}"))
            keyboard.append(row)

        # Add back button
        keyboard.append([InlineKeyboardButton("⬅️ Back to Games", callback_data="back_to_games")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        message = f"🏰 *Select your power for Game {game_id}:*"

        if update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        error_msg = f"❌ Error loading powers: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

# Handle callback queries from inline buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards"""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    data = query.data
    user_id = str(query.from_user.id)

    if data.startswith("select_game_"):
        game_id = data.split("_")[2]
        await show_power_selection(update, game_id)

    elif data.startswith("join_game_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]

        try:
            result = api_post(f"/games/{game_id}/join", {
                "telegram_id": user_id,
                "game_id": int(game_id),
                "power": power
            })
            await query.edit_message_text(f"🎉 Successfully joined Game {game_id} as {power}!")
        except Exception as e:
            await query.edit_message_text(f"❌ Failed to join: {str(e)}")

    elif data == "back_to_games":
        # Show games list again
        await show_available_games(update, context)

    elif data.startswith("orders_menu_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]

        # Create orders action menu for specific game
        keyboard = [
            [InlineKeyboardButton("📝 Submit Orders", callback_data=f"submit_orders_{game_id}_{power}")],
            [InlineKeyboardButton("👁️ View My Orders", callback_data=f"view_orders_{game_id}_{power}")],
            [InlineKeyboardButton("🗑️ Clear Orders", callback_data=f"clear_orders_{game_id}_{power}")],
            [InlineKeyboardButton("📜 Order History", callback_data=f"order_history_{game_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_orders_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"📋 *Orders Menu - Game {game_id} ({power})*", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("view_map_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"🗺️ Generating map for Game {game_id}...\n\n(Live game map functionality coming soon!)")

    elif data == "view_default_map":
        await query.edit_message_text("🗺️ Generating standard Diplomacy map...")
        await send_default_map(update, context)

    elif data == "back_to_main_menu":
        # Show the main start message again
        await show_main_menu(update, context)

    elif data == "show_games_list":
        await show_available_games(update, context)

    elif data == "join_waiting_list":
        # Simulate the wait command
        await wait(update, context)

    elif data == "retry_orders_menu":
        await show_my_orders_menu(update, context)

    elif data == "about_diplomacy":
        await query.edit_message_text(
            "💬 *About Diplomacy Messages*\n\n"
            "🎭 Diplomacy is all about negotiation and alliances!\n\n"
            "*📨 Message Types:*\n"
            "• **Private messages** to specific players\n"
            "• **Public broadcasts** to all players\n"
            "• **Alliance proposals** and deals\n"
            "• **Coordination** for joint moves\n\n"
            "*🎯 Strategy Tips:*\n"
            "• Build trust early in the game\n"
            "• Coordinate attacks and defenses\n"
            "• Sometimes betrayal is necessary\n"
            "• Information is power - share wisely\n\n"
                         "🎲 *Ready to start negotiating?*\n"
             "Join a game and make your first alliance!",
             parse_mode='Markdown'
         )

    elif data == "show_orders_menu":
        # Redirect to the orders menu
        await show_my_orders_menu(update, context)

    elif data == "show_map_menu":
        # Redirect to the map menu
        await show_map_menu(update, context)

    elif data == "show_messages_menu":
        # Redirect to the messages menu
        await show_messages_menu(update, context)

    elif data.startswith("view_messages_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"💬 Loading messages for Game {game_id}...\n\n(Messages functionality coming soon!)")

    elif data.startswith("submit_orders_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]
        # Create order format help with action buttons
        keyboard = [
            [InlineKeyboardButton("📋 View Current Orders", callback_data=f"view_orders_{game_id}_{power}")],
            [InlineKeyboardButton("🗑️ Clear All Orders", callback_data=f"clear_orders_{game_id}_{power}")],
            [InlineKeyboardButton("📜 View Order History", callback_data=f"order_history_{game_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_orders_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📝 *Submit Orders - Game {game_id} ({power})*\n\n"
            f"💡 *How to submit orders:*\n"
            f"Type: `/orders {game_id} <your orders>`\n\n"
            f"*📋 Order Examples:*\n"
            f"• `A Vienna - Trieste` (Army move)\n"
            f"• `F London - North Sea` (Fleet move)\n"
            f"• `A Berlin S A Munich - Kiel` (Support)\n"
            f"• `F English Channel C A London - Brest` (Convoy)\n"
            f"• `A Paris H` (Hold position)\n\n"
            f"*💡 Tips:*\n"
            f"• Separate multiple orders with semicolons\n"
            f"• Orders are processed simultaneously each turn\n"
            f"• You can update orders until the deadline",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# Handle menu button presses
async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle presses of menu keyboard buttons"""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if text == "🎯 Register":
        await register(update, context)
    elif text == "🎮 My Games":
        await games(update, context)
    elif text == "🎲 Join Game":
        await show_available_games(update, context)
    elif text == "⏳ Join Waiting List":
        await wait(update, context)
    elif text == "📋 My Orders":
        await show_my_orders_menu(update, context)
    elif text == "🗺️ View Map":
        await show_map_menu(update, context)
    elif text == "💬 Messages":
        await show_messages_menu(update, context)
    elif text == "ℹ️ Help":
        await show_help(update, context)

async def show_my_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show orders menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        user_games = api_get(f"/users/{user_id}/games")

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
                "📋 *No Active Games*\n\n"
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
                button_text = f"📋 Game {game_id} ({power}) - {state}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"orders_menu_{game_id}_{power}")])

        if not keyboard:
            # Fallback if games exist but are malformed
            keyboard = [[InlineKeyboardButton("🎲 Browse Games Instead", callback_data="show_games_list")]]
            await update.message.reply_text(
                "📋 *Games Data Issue*\n\n"
                "🔧 Your games data seems corrupted. Try browsing available games instead.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"📋 *Select game to manage orders:* ({len(games_to_show)} active)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        # More helpful error message with recovery options
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", callback_data="retry_orders_menu")],
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
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

async def show_map_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show map menu for user's games or default map if not in any games"""
    try:
        user_id = str(update.effective_user.id)
        user_games = api_get(f"/users/{user_id}/games")

        # Handle different response types safely
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            # Show default map for users not in any games
            keyboard = [
                [InlineKeyboardButton("🗺️ View Standard Diplomacy Map", callback_data="view_default_map")],
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🗺️ *No Game Maps Yet*\n\n"
                "🎮 You're not in any active games!\n\n"
                "💡 *Options:*\n"
                "🗺️ View the standard Diplomacy board\n"
                "🎲 Browse games and join one for live maps\n"
                "⏳ Join waiting list for auto-matching",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        # User has games - show their game maps
        keyboard = []
        games_to_show = user_games[:10] if len(user_games) > 10 else user_games
        for game in games_to_show:
            if isinstance(game, dict):
                game_id = game.get('game_id', 'Unknown')
                power = game.get('power', 'Unknown')
                state = game.get('state', 'Unknown')
                keyboard.append([InlineKeyboardButton(f"🗺️ Game {game_id} Map ({power}) - {state}", callback_data=f"view_map_{game_id}")])

        # Also add option to see default map
        keyboard.append([InlineKeyboardButton("🗺️ Standard Reference Map", callback_data="view_default_map")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🗺️ *Select map to view:* ({len(games_to_show)} games)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🗺️ View Standard Map", 
                                 callback_data="view_default_map")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⚠️ *Can't Load Game Maps*\n\n"
            f"🔧 Unable to access your game maps right now.\n\n"
            f"💡 *You can still:*\n"
            f"🗺️ View the standard reference map\n"
            f"🏠 Return to main menu\n\n"
            f"*Error:* {str(e)[:100]}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def show_messages_menu(update: Update, 
                            context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show messages menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        user_games = api_get(f"/users/{user_id}/games")

        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", 
                                     callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", 
                                     callback_data="join_waiting_list")],
                [InlineKeyboardButton("ℹ️ About Diplomacy Messages", 
                                     callback_data="about_diplomacy")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "💬 *No Game Messages*\n\n"
                "🎮 You need to join a game first to send and receive diplomatic messages!\n\n"
                "💡 *In Diplomacy:*\n"
                "• Form alliances with other powers\n"
                "• Negotiate support and coordination\n"
                "• Send private messages to specific players\n"
                "• Broadcast public announcements\n\n"
                "🎲 Join a game to start your diplomatic career!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        keyboard = []
        games_to_show = user_games[:10] if len(user_games) > 10 else user_games
        for game in games_to_show:
            if isinstance(game, dict):
                game_id = game.get('game_id', 'Unknown')
                power = game.get('power', 'Unknown')
                state = game.get('state', 'Unknown')
                keyboard.append([InlineKeyboardButton(f"💬 Game {game_id} Messages ({power}) - {state}", callback_data=f"view_messages_{game_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"💬 *Select game to view messages:* ({len(games_to_show)} games)",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"⚠️ *Messages Unavailable*\n\n"
            f"🔧 Can't access game messages right now.\n"
            f"This is usually temporary.\n\n"
            f"💡 *Try:*\n"
            f"• Browse and join games directly\n"
            f"• Return to main menu and try again later\n\n"
            f"*Error:* {str(e)[:100]}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help with available commands"""
    help_text = """
🏛️ *Diplomacy Bot Commands*

*🎯 Getting Started:*
• Register - Register as a player
• My Games - View your current games
• Join Game - Join a specific game
• Join Waiting List - Auto-match with others

*🎮 During Games:*
• My Orders - Submit/view your orders
• View Map - See current game state
• Messages - View/send diplomatic messages

*📝 Text Commands:*
• `/orders <game_id> <orders>` - Submit orders
• `/message <game_id> <power> <text>` - Send message
• `/broadcast <game_id> <text>` - Message all players

*🗺️ Order Format Examples:*
• `A Vienna - Trieste` (Army move)
• `F London - North Sea` (Fleet move)
• `A Berlin S A Munich - Kiel` (Support)
• `F English Channel C A London - Brest` (Convoy)

*💡 Tip:* Use the menu buttons for easier navigation!
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def send_default_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the standard Diplomacy map without any units"""
    try:
        # Try to get cached map first
        img_bytes = get_cached_default_map()
        
        if img_bytes is None:
            # Cache miss - generate the map (expensive operation)
            logging.info("Generating default map (first time)")
            img_bytes = generate_default_map()
            set_cached_default_map(img_bytes)
            logging.info("Default map generated and cached permanently")
        else:
            logging.info("Using permanently cached default map")

        # Send the map with descriptive caption
        caption = (
            "🗺️ *Standard Diplomacy Map*\n\n"
            "This is the classic Diplomacy board showing:\n"
            "🏰 *7 Great Powers:* Austria, England, France, Germany, Italy, Russia, Turkey\n"
            "🏙️ *Supply Centers:* Cities that provide military units\n"
            "🌊 *Seas & Land:* Different movement rules for fleets vs armies\n\n"
            "🎲 *Ready to play?* Use the menu to join a game!"
        )

        if update.callback_query:
            # If called from inline button, send new photo message
            await update.callback_query.message.reply_photo(
                photo=BytesIO(img_bytes),
                caption=caption,
                parse_mode='Markdown'
            )
        else:
            # If called directly, send photo to message
            await update.message.reply_photo(
                photo=BytesIO(img_bytes),
                caption=caption,
                parse_mode='Markdown'
            )

    except Exception as e:
        error_msg = f"❌ Error generating default map: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the main menu keyboard"""
    keyboard = [
        [KeyboardButton("🎯 Register"), KeyboardButton("🎮 My Games")],
        [KeyboardButton("🎲 Join Game"), KeyboardButton("⏳ Join Waiting List")],
        [KeyboardButton("📋 My Orders"), KeyboardButton("🗺️ View Map")],
        [KeyboardButton("💬 Messages"), KeyboardButton("ℹ️ Help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    main_text = (
        "🏛️ *Welcome to Diplomacy!*\n\n"
        "I'm your diplomatic assistant. Use the menu below:\n\n"
        "🎯 *Register* if you're new\n"
        "🎮 *My Games* to see your current games\n"
        "🎲 *Join Game* to enter a specific game\n"
        "⏳ *Join Waiting List* for automatic matching"
    )

    if update.callback_query:
        # If called from callback, send new message with keyboard
        await update.callback_query.message.reply_text(
            main_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # If called directly, reply to message
        await update.message.reply_text(
            main_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Game joining failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /join <game_id> <power>")
        return
    game_id, power = args[0], args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/join", 
                         {"telegram_id": user_id, "game_id": int(game_id), "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have joined game {game_id} as {power}.")
        elif result.get("status") == "already_joined":
            await update.message.reply_text(f"You are already in game {game_id} as {power}.")
        else:
            await update.message.reply_text(f"Join failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to join game: {e}")

async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Quit failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /quit <game_id>")
        return
    game_id = args[0]
    try:
        result = api_post(f"/games/{game_id}/quit", 
                         {"telegram_id": user_id, "game_id": int(game_id)})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have quit game {game_id}.")
        elif result.get("status") == "not_in_game":
            await update.message.reply_text(f"You are not in game {game_id}.")
        else:
            await update.message.reply_text(f"Quit failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to quit game: {e}")

# Update order-related commands to accept game_id as an argument
async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Order submission failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /orders <game_id> <order1>; <order2>; ...")
        return
    game_id = args[0]
    order_text = " ".join(args[1:])
    try:
        user_games = api_get(f"/users/{user_id}/games")
        power = None
        games_list = user_games.get("games", [])
        for g in games_list:
            if str(g["game_id"]) == str(game_id):
                power = g["power"]
                break
        if not power:
            await update.message.reply_text(f"You are not in game {game_id}.")
            return
        orders = [o.strip() for o in order_text.split(";") if o.strip()]
        if not orders:
            await update.message.reply_text("No orders found in your message.")
            return
        result = api_post("/games/set_orders", 
                         {"game_id": game_id, "power": power, "orders": orders})
        results = result.get("results", [])
        if not results:
            await update.message.reply_text("No orders were processed.")
            return
        response_lines = []
        for r in results:
            if r["success"]:
                response_lines.append(f"✅ {r['order']}")
            else:
                response_lines.append(f"❌ {r['order']}\n   Error: {r['error']}")
        await update.message.reply_text("Order results:\n" + "\n".join(response_lines))
    except Exception as e:
        await update.message.reply_text(f"Order error: {e}")

async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve orders: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        power = session["power"]
        result = api_get(f"/games/{game_id}/orders/{power}")
        orders = result.get("orders", [])
        if not orders:
            await update.message.reply_text("You have not submitted any orders for this turn.")
        else:
            await update.message.reply_text("Your current orders:\n" + "\n".join(orders))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving orders: {e}")

async def clearorders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not clear orders: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        power = session["power"]
        api_post(f"/games/{game_id}/orders/{power}/clear", {})
        await update.message.reply_text("Your orders for this turn have been cleared.")
    except Exception as e:
        await update.message.reply_text(f"Error clearing orders: {e}")

async def orderhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Could not retrieve order history: No user context.")
        return
    user_id = str(user.id)
    try:
        session = api_get(f"/users/{user_id}")
        game_id = session["game_id"]
        result = api_get(f"/games/{game_id}/orders/history")
        history = result.get("order_history", {})
        if not history:
            await update.message.reply_text("No order history found for this game.")
            return
        lines = [f"Order history for game {game_id}:"]
        for turn in sorted(history.keys(), key=lambda x: int(x)):
            lines.append(f"\nTurn {turn}:")
            for power, orders in history[turn].items():
                lines.append(f"  {power}:")
                for order in orders:
                    lines.append(f"    {order}")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error retrieving order history: {e}")

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Map command failed: No user context.")
        return
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /map <game_id>")
        return
    game_id = args[0]
    try:
        # Fetch game state from API or server
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state or "units" not in game_state:
            await update.message.reply_text(f"Game {game_id} not found or no units present.")
            return
        units = game_state["units"]  # {power: ["A PAR", "F LON", ...]}
        map_name = game_state.get("map", "standard")
        base_map_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg").replace("standard.svg", "")
        svg_path = f"{base_map_path}{map_name}.svg"
        if not os.path.isfile(svg_path):
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        try:
            img_bytes = Map.render_board_png(svg_path, units)
        except Exception as e:
            await update.message.reply_text(f"Error rendering map: {e}")
            return
        await update.message.reply_photo(photo=BytesIO(img_bytes), caption=f"Board for game {game_id}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def replay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        # Fetch game state snapshot for the specified turn
        result = api_get(f"/games/{game_id}/history/{turn}")
        state = result.get("state")
        if not state or "units" not in state:
            await update.message.reply_text(f"No board state found for game {game_id} turn {turn}.")
            return
        units = state["units"]
        map_name = state.get("map", "standard")
        base_map_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg").replace("standard.svg", "")
        svg_path = f"{base_map_path}{map_name}.svg"
        if not os.path.isfile(svg_path):
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        try:
            img_bytes = Map.render_board_png(svg_path, units)
        except Exception as e:
            await update.message.reply_text(f"Error rendering map: {e}")
            return
        await update.message.reply_photo(photo=BytesIO(img_bytes), caption=f"Board for game {game_id}, turn {turn}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def replace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Replace command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /replace <game_id> <power>")
        return
    game_id, power = args[0], args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/replace", {"telegram_id": user_id, "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have replaced {power} in game {game_id}.")
        else:
            await update.message.reply_text(f"Replace failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to replace player: {e}")

async def refresh_map_cache(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to refresh the default map cache"""
    user = update.effective_user
    if not user or not update.message:
        return
    
    # Check if user is admin (you can customize this logic)
    # For now, allow anyone to refresh the cache
    try:
        await update.message.reply_text("🔄 Refreshing default map cache...")
        
        # Generate new map
        img_bytes = generate_default_map()
        set_cached_default_map(img_bytes)
        
        await update.message.reply_text("✅ Default map cache refreshed successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to refresh map cache: {str(e)}")

# --- In-memory waiting list for automated game creation ---
WAITING_LIST = []  # List of (telegram_id, full_name)
WAITING_LIST_SIZE = 7  # Standard Diplomacy
POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]

def process_waiting_list(waiting_list, waiting_list_size, powers, notify_callback, api_post_func=None):
    """
    Process the waiting list: if enough players, create a game, assign powers, and notify users.
    notify_callback(telegram_id, message) is called for each user.
    Returns (game_id, assignments) if a game was created, else (None, None).
    """
    import random
    if api_post_func is None:
        api_post_func = api_post
    if len(waiting_list) >= waiting_list_size:
        players = waiting_list[:waiting_list_size]
        random.shuffle(players)
        assigned_powers = list(zip(players, powers))
        # Create game
        try:
            game_resp = api_post_func("/games/create", {"map_name": "standard"})
            game_id = game_resp["game_id"]
            # Assign powers
            for (telegram_id, full_name), power in assigned_powers:
                api_post_func(f"/games/{game_id}/join", {"telegram_id": telegram_id, "game_id": int(game_id), "power": power})
            # Notify users
            for (telegram_id, full_name), power in assigned_powers:
                try:
                    notify_callback(telegram_id, f"A new game (ID: {game_id}) has started! You are {power}.")
                except Exception as e:
                    logging.warning(f"Failed to notify {telegram_id}: {e}")
            # Remove assigned users from waiting list
            del waiting_list[:waiting_list_size]
            return game_id, assigned_powers
        except Exception as e:
            logging.error(f"Failed to create game: {e}")
            return None, None
    return None, None

async def wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Wait command failed: No user context.")
        return
    user_id = str(user.id)
    full_name = getattr(user, 'full_name', None) or user_id
    # Check if already in waiting list
    if any(u[0] == user_id for u in WAITING_LIST):
        await update.message.reply_text("You are already in the waiting list for the next game.")
        return
    WAITING_LIST.append((user_id, full_name))
    await update.message.reply_text(
        f"Added to waiting list ({len(WAITING_LIST)}/{WAITING_LIST_SIZE}). "
        f"You will be notified when the game starts.")
    # If enough players, create a new game
    async def telegram_notify_callback(telegram_id, message):
        try:
            await update.get_bot().send_message(chat_id=telegram_id, text=message)
        except Exception as e:
            logging.warning(f"Failed to notify {telegram_id}: {e}")
    # Use a sync wrapper for process_waiting_list
    def sync_notify_callback(telegram_id, message):
        asyncio.create_task(telegram_notify_callback(telegram_id, message))
    process_waiting_list(WAITING_LIST, WAITING_LIST_SIZE, POWERS, sync_notify_callback)

# --- FastAPI notification endpoint ---
fastapi_app = FastAPI()

class NotifyRequest(BaseModel):
    telegram_id: int
    message: str

@fastapi_app.post("/notify")
async def notify(req: NotifyRequest):
    try:
        # Send message using the running Telegram bot application
        if not hasattr(notify, "telegram_app"):
            return {"status": "error", "detail": "Bot not initialized"}
        telegram_app: Application = notify.telegram_app
        await telegram_app.bot.send_message(chat_id=req.telegram_id, text=req.message)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# --- Main entrypoint: run both bot and FastAPI ---
def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("quit", quit))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("clearorders", clearorders))
    app.add_handler(CommandHandler("orderhistory", orderhistory))
    app.add_handler(CommandHandler("message", message))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("messages", messages))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(CommandHandler("replay", replay))
    app.add_handler(CommandHandler("replace", replace))
    app.add_handler(CommandHandler("wait", wait))
    app.add_handler(CommandHandler("refresh_map", refresh_map_cache))

    # Add handlers for interactive features
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons))

    # Attach the running app to the notify endpoint for access
    notify.telegram_app = app

    # Always run the notification API on port 8081 since the main API server depends on it
    # When BOT_ONLY=true, only run telegram bot + notification API (main API runs separately)

    # Enhanced debugging for container environment
    import logging
    logging.basicConfig(level=logging.INFO, force=True)
    logger = logging.getLogger(__name__)

    # Log all environment variables for debugging
    logger.info("=== TELEGRAM BOT STARTUP DEBUG ===")
    logger.info(f"All environment variables containing 'BOT': "
                f"{[(k,v) for k,v in os.environ.items() if 'BOT' in k.upper()]}")

    bot_only_raw = os.environ.get("BOT_ONLY", "NOT_SET")
    bot_only = bot_only_raw.lower() == "true"

    logger.info(f"BOT_ONLY raw value: '{bot_only_raw}'")
    logger.info(f"BOT_ONLY after .lower(): '{bot_only_raw.lower()}'")
    logger.info(f"Final bot_only boolean: {bot_only}")
    logger.info("=== END DEBUG ===")

    # Also print to stdout for container logs
    print(f"🤖 BOT_ONLY environment variable: '{bot_only_raw}'")
    print(f"🤖 Detected bot_only mode: {bot_only}")

    # Pre-generate the default map on startup (permanent cache) - optional
    # Skip pre-generation if it might cause memory issues
    skip_pregen = os.environ.get("SKIP_MAP_PREGEN", "false").lower() == "true"
    if skip_pregen:
        logger.info("Skipping map pre-generation (SKIP_MAP_PREGEN=true)")
    else:
        logger.info("Pre-generating default map for permanent caching...")
        try:
            img_bytes = generate_default_map()
            set_cached_default_map(img_bytes)
            logger.info("Default map pre-generated and cached permanently")
        except Exception as e:
            logger.warning(f"Failed to pre-generate default map: {e}")
            logger.info("Default map will be generated on first request")

    if bot_only:
        # BOT_ONLY mode: Run telegram bot + notification API (main API runs separately)
        print("Starting in BOT_ONLY mode")

        # Start notification API server in a separate thread
        import threading
        def start_notify_server():
            import uvicorn
            uvicorn.run(fastapi_app, host="0.0.0.0", port=8081, log_level="info")

        notify_thread = threading.Thread(target=start_notify_server, daemon=True)
        notify_thread.start()

        # Wait a bit for the server to start
        import time
        time.sleep(2)

        # Start telegram bot polling - this will block
        app.run_polling()
    else:
        # Legacy/standalone mode: Use thread-based approach to avoid event loop conflicts
        print("Starting in standalone mode with thread-based approach")

        # Always use the thread-based approach when running as a service
        # This avoids asyncio.run() conflicts in systemd environment
        import threading
        import time

        def start_notify_server():
            import uvicorn
            uvicorn.run(fastapi_app, host="0.0.0.0", port=8081, log_level="info")

        # Start notification server in background thread
        notify_thread = threading.Thread(target=start_notify_server, daemon=True)
        notify_thread.start()

        # Wait a bit for the server to start
        time.sleep(2)

        # Start telegram bot polling in main thread - this will block
        print("Starting Telegram bot polling...")
        app.run_polling()

if __name__ == "__main__":
    main()
