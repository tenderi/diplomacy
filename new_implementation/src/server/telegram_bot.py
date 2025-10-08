"""
Telegram Diplomacy Bot - Initial scaffold

This bot will handle registration, order submission, and notifications for Diplomacy games.
"""
import logging
import os
import requests
from datetime import datetime
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
    svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
    
    # Empty units dictionary for clean map display
    units = {}
    
    # Default phase info for empty map
    phase_info = {
        "year": "1901",
        "season": "Spring", 
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    # Generate map image
    return Map.render_board_png(svg_path, units, phase_info=phase_info)

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
    
    # Add admin menu for admin user (ID: 8019538)
    user_id = str(update.effective_user.id)
    logging.info(f"User ID: {user_id}, Type: {type(user_id)}")
    if user_id == "8019538":
        keyboard.append([KeyboardButton("⚙️ Admin")])
        logging.info("Admin button added to keyboard")
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, 
                                       one_time_keyboard=False)

    await update.message.reply_text(
        "🏛️ *Welcome to Diplomacy!*\n\n"
        "I'm your diplomatic assistant. Use the menu below or type commands:\n\n"
        "🎯 Start with *Register* if you're new\n"
        "🎮 Check *My Games* to see your current games\n"
        "🎲 *Join Game* to enter a specific game\n"
        "⏳ *Join Waiting List* for automatic game matching\n\n"
        "💡 *New Features:*\n"
        "• Interactive unit selection with `/selectunit`\n"
        "• Full Diplomacy rules implementation\n"
        "• Convoy chain validation\n"
        "• Multi-phase gameplay (Movement/Retreat/Builds)",
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
        user_games_response = api_get(f"/users/{user_id}/games")
        
        # Extract games list from API response
        user_games = user_games_response.get("games", []) if user_games_response else []

        # Handle different response formats safely
        if not user_games or not isinstance(user_games, list):
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
    async def reply_or_edit(text: str, reply_markup=None, parse_mode='Markdown'):
        """Helper function to handle both message and callback query contexts"""
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    
    try:
        games = api_get("/games")
        if not games:
            await reply_or_edit("🎮 No games available. Use /wait to join the waiting list.")
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
        await reply_or_edit("🎲 *Select a game to join:*", reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        await reply_or_edit(f"❌ Error loading games: {str(e)}")

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
            [InlineKeyboardButton("🎯 Submit Interactive Orders", callback_data=f"submit_orders_{game_id}_{power}")],
            [InlineKeyboardButton("👁️ View My Orders", callback_data=f"view_orders_{game_id}_{power}")],
            [InlineKeyboardButton("🗑️ Clear Orders", callback_data=f"clear_orders_{game_id}_{power}")],
            [InlineKeyboardButton("📜 Order History", callback_data=f"order_history_{game_id}")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_orders_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"📋 *Orders Menu - Game {game_id} ({power})*", reply_markup=reply_markup, parse_mode='Markdown')

    elif data.startswith("view_map_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"🗺️ Generating map for Game {game_id}...")
        await send_game_map(update, context, game_id)

    elif data == "view_default_map":
        await query.edit_message_text("🗺️ Generating standard Diplomacy map...")
        await send_default_map(update, context)

    elif data == "start_demo_game":
        await query.edit_message_text("🎮 Starting demo game as Germany...")
        await start_demo_game(update, context)

    elif data == "run_automated_demo":
        await query.edit_message_text("🎬 Starting automated demo game...")
        await run_automated_demo(update, context)

    elif data == "back_to_main_menu":
        # Show the main start message again
        await show_main_menu(update, context)

    elif data == "show_games_list":
        await show_available_games(update, context)

    elif data == "join_waiting_list":
        # Simulate the wait command
        await wait(update, context)

    elif data.startswith("demo_orders_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"📋 Demo Orders for Game {game_id}\n\nUse /orders {game_id} <your orders> to submit moves for Germany!\n\n💡 Try /selectunit for interactive order selection!")
        
    elif data.startswith("demo_help_"):
        game_id = data.split("_")[2]
        help_text = (
            f"ℹ️ *Demo Game Help* (ID: {game_id})\n\n"
            "🇩🇪 *You are Germany* - You control:\n"
            "• A Berlin (Army in Berlin)\n"
            "• A Munich (Army in Munich)\n"
            "• F Kiel (Fleet in Kiel)\n\n"
            "*Example Orders:*\n"
            "• `/orders {game_id} A Berlin - Kiel`\n"
            "• `/orders {game_id} A Munich - Bohemia`\n"
            "• `/orders {game_id} F Kiel - Denmark`\n"
            "• `/orders {game_id} A Berlin H` (Hold)\n"
            "• `/orders {game_id} A Berlin S A Munich - Kiel` (Support)\n"
            "• `/orders {game_id} F Kiel C A Berlin - Denmark` (Convoy)\n\n"
            "*📝 Order Format:*\n"
            "• Use abbreviations: `A`, `F`, `H`, `S`, `C`\n"
            "• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`\n"
            "• **Don't mix:** `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅\n\n"
            "*Interactive Commands:*\n"
            "• `/selectunit` - Choose units and orders interactively\n"
            "• `/processturn {game_id}` - Process the current turn\n"
            "• `/viewmap {game_id}` - View current game state\n\n"
            "🤖 *Other powers won't move* - they're AI-controlled\n"
            "🗺️ Use 'View Map' to see the current state"
        )
        await query.edit_message_text(help_text, parse_mode='Markdown')

    elif data == "admin_delete_all_games":
        # Check admin authorization
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return
        
        # Show confirmation dialog
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Delete All Games", callback_data="admin_confirm_delete_all")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚠️ *CONFIRMATION REQUIRED*\n\n"
            "🗑️ You are about to delete ALL games!\n\n"
            "This action will:\n"
            "• Remove all active games\n"
            "• Delete all game data\n"
            "• Affect all players\n\n"
            "⚠️ *This action cannot be undone!*\n\n"
            "Are you sure you want to proceed?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif data == "admin_confirm_delete_all":
        # Check admin authorization again
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return
        
        try:
            # Call API to delete all games
            result = api_post("/admin/delete_all_games", {})
            await query.edit_message_text(
                f"✅ *All games deleted successfully!*\n\n"
                f"🗑️ Result: {result.get('message', 'Games deleted')}\n"
                f"📊 Games deleted: {result.get('deleted_count', 'Unknown')}",
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error deleting games: {str(e)}")

    elif data == "admin_cancel_delete":
        await query.edit_message_text("❌ Delete operation cancelled.")

    elif data == "admin_recreate_admin_user":
        # Check admin authorization again
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return
        
        try:
            # Call API to recreate admin user
            result = api_post("/admin/recreate_admin_user", {})
            await query.edit_message_text(
                f"✅ *Admin User Recreated!*\n\n"
                f"👤 Result: {result.get('message', 'User created')}\n"
                f"🆔 User ID: {result.get('user_id', 'Unknown')}\n\n"
                f"💡 You should now be able to access your games again.",
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error recreating admin user: {str(e)}")

    elif data == "admin_system_status":
        # Check admin authorization
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return
        
        try:
            # Get system status
            games_count = len(api_get("/admin/games_count") or [])
            users_count = len(api_get("/admin/users_count") or [])
            
            status_text = (
                "📊 *System Status*\n\n"
                f"🎮 Active Games: {games_count}\n"
                f"👥 Registered Users: {users_count}\n"
                f"🕒 Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⚙️ Admin User: {query.from_user.id}\n\n"
                "✅ System operational"
            )
            await query.edit_message_text(status_text, parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Error getting system status: {str(e)}")

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
        await query.edit_message_text(f"💬 Loading messages for Game {game_id}...\n\nUse `/messages {game_id}` to view messages or `/message {game_id} <power> <text>` to send a message.")

    elif data.startswith("submit_orders_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]
        
        # Start interactive order selection for this specific game
        await query.edit_message_text(f"🎯 Starting interactive order selection for Game {game_id} ({power})...")
        await selectunit(update, context)

    # Interactive Order Input Callbacks
    elif data.startswith("select_unit_"):
        # Handle unit selection for interactive orders
        parts = data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"  # Reconstruct "A BER" format from "A_BER"
        
        await show_possible_moves(query, game_id, unit)
        
    elif data.startswith("cancel_unit_selection_"):
        game_id = data.split("_")[3]
        await query.edit_message_text(f"❌ Unit selection cancelled for game {game_id}")
        
    elif data.startswith("move_unit_"):
        # Handle move selection
        parts = data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"
        move_type = parts[5]  # "hold", "move", "support"
        
        if move_type == "hold":
            await submit_interactive_order(query, game_id, f"{unit} H")
        elif move_type == "move":
            target_province = parts[6]
            await submit_interactive_order(query, game_id, f"{unit} - {target_province}")
        elif move_type == "support":
            # For now, just show a message that support orders need more complex UI
            await query.edit_message_text(
                f"🔄 Support orders are now fully implemented!\n\n"
                f"Use `/orders <game_id> {unit} S <unit to support>` for support orders.\n\n"
                f"💡 Example: `/orders 123 A Berlin S A Munich - Kiel`"
            )
        elif move_type == "convoy":
            # Show convoy options for fleets
            await show_convoy_options(query, game_id, unit)
            
    elif data.startswith("cancel_move_selection_"):
        game_id = data.split("_")[3]
        await query.edit_message_text(f"❌ Move selection cancelled for game {game_id}")
        
    elif data.startswith("convoy_select_"):
        # Handle convoy selection
        parts = data.split("_")
        game_id = parts[2]
        fleet_unit = f"{parts[3]} {parts[4]}"  # e.g., "F NTH"
        army_power = parts[5]  # e.g., "ENGLAND"
        army_unit = f"{parts[6]} {parts[7]}"  # e.g., "A LON"
        
        # Show convoy destination selection
        await show_convoy_destinations(query, game_id, fleet_unit, army_power, army_unit)
        
    elif data.startswith("convoy_dest_"):
        # Handle convoy destination selection
        parts = data.split("_")
        game_id = parts[2]
        fleet_unit = f"{parts[3]} {parts[4]}"  # e.g., "F NTH"
        army_power = parts[5]  # e.g., "ENGLAND"
        army_unit = f"{parts[6]} {parts[7]}"  # e.g., "A LON"
        destination = parts[8]  # e.g., "BEL"
        
        # Create convoy order: Fleet convoys army to destination
        convoy_order = f"{fleet_unit} C {army_power} {army_unit} - {destination}"
        await submit_interactive_order(query, game_id, convoy_order)
        
    elif data.startswith("view_orders_"):
        # Handle view orders button
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]
        
        try:
            # Get current game state to show orders
            game_state = api_get(f"/games/{game_id}/state")
            if not game_state:
                await query.edit_message_text(f"❌ Could not retrieve game state for game {game_id}")
                return
            
            orders = game_state.get("orders", {}).get(power, [])
            
            if not orders:
                await query.edit_message_text(
                    f"📋 *Your Orders - Game {game_id} ({power})*\n\n"
                    f"❌ No orders submitted yet.\n\n"
                    f"Use the Submit Orders button to add orders for this turn.",
                    parse_mode='Markdown'
                )
            else:
                orders_text = "\n".join([f"• {order}" for order in orders])
                await query.edit_message_text(
                    f"📋 *Your Orders - Game {game_id} ({power})*\n\n"
                    f"📝 *Current Orders:*\n{orders_text}\n\n"
                    f"💡 Use Submit Orders to modify or add more orders.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await query.edit_message_text(f"❌ Error retrieving orders: {e}")
            
    elif data.startswith("order_history_"):
        # Handle order history button
        game_id = data.split("_")[2]
        
        try:
            # Get order history from API
            result = api_get(f"/games/{game_id}/orders/history")
            history = result.get("order_history", {})
            
            if not history:
                await query.edit_message_text(
                    f"📜 *Order History - Game {game_id}*\n\n"
                    f"❌ No order history found for this game.\n\n"
                    f"Order history will appear after turns are processed.",
                    parse_mode='Markdown'
                )
            else:
                lines = [f"📜 *Order History - Game {game_id}*\n"]
                for turn in sorted(history.keys(), key=lambda x: int(x)):
                    lines.append(f"\n📅 *Turn {turn}:*")
                    for power, orders in history[turn].items():
                        lines.append(f"\n🛡️ *{power}:*")
                        for order in orders:
                            lines.append(f"  • {order}")
                
                # Telegram has a message length limit, so we might need to truncate
                full_text = "\n".join(lines)
                if len(full_text) > 4000:  # Telegram limit is ~4096 characters
                    full_text = full_text[:3900] + "\n\n... (truncated)"
                
                await query.edit_message_text(full_text, parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Error retrieving order history: {e}")
            
    elif data.startswith("clear_orders_"):
        # Handle clear orders button
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]
        
        try:
            # Clear orders by submitting empty order list
            result = api_post(f"/games/set_orders", {
                "game_id": game_id,
                "power": power,
                "orders": [],
                "telegram_id": user_id
            })
            
            await query.edit_message_text(
                f"🗑️ *Orders Cleared*\n\n"
                f"✅ All orders for {power} in Game {game_id} have been cleared.\n\n"
                f"💡 Use Submit Orders to add new orders.",
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error clearing orders: {e}")

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
    elif text == "⚙️ Admin":
        await show_admin_menu(update, context)

async def show_my_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show orders menu for user's games"""
    try:
        user_id = str(update.effective_user.id)
        user_games_response = api_get(f"/users/{user_id}/games")
        
        # Extract games list from API response
        user_games = user_games_response.get("games", []) if user_games_response else []

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
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"📋 *Select game to manage orders:* ({len(games_to_show)} active)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
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

async def show_map_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show map menu for user's games or default map if not in any games"""
    try:
        user_id = str(update.effective_user.id)
        user_games_response = api_get(f"/users/{user_id}/games")
        
        # Extract games list from API response
        user_games = user_games_response.get("games", []) if user_games_response else []

        # Handle different response types safely
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            # Show default map for users not in any games
            keyboard = [
                [InlineKeyboardButton("🗺️ View Standard Diplomacy Map", callback_data="view_default_map")],
                [InlineKeyboardButton("🎮 Start Demo Game (Germany)", callback_data="start_demo_game")],
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🗺️ *No Game Maps Yet*\n\n"
                "🎮 You're not in any active games!\n\n"
                "💡 *Options:*\n"
                "🗺️ View the standard Diplomacy board\n"
                "🎮 Start a demo game as Germany\n"
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
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"🗺️ *Select map to view:* ({len(games_to_show)} games)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
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
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⚠️ *Can't Load Game Maps*\n\n"
                f"🔧 Unable to access your game maps right now.\n\n"
                f"💡 *You can still:*\n"
                f"🗺️ View the standard reference map\n"
                f"🏠 Return to main menu\n\n"
                f"*Error:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
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
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"💬 *Select game to view messages:* ({len(games_to_show)} games)",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
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
        if update.callback_query:
            await update.callback_query.edit_message_text(
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
        else:
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
• `/order <orders>` - Submit orders (auto-detect game)
• `/selectunit` - Interactive unit selection
• `/processturn <game_id>` - Process current turn
• `/viewmap <game_id>` - View game map
• `/message <game_id> <power> <text>` - Send message
• `/broadcast <game_id> <text>` - Message all players
• `/myorders <game_id>` - View your orders
• `/clearorders <game_id>` - Clear your orders
• `/orderhistory <game_id>` - View order history

*🗺️ Order Types & Examples:*
• `A Vienna - Trieste` (Army move)
• `F London - North Sea` (Fleet move)
• `A Berlin H` (Hold)
• `A Berlin S A Munich - Kiel` (Support)
• `F English Channel C A London - Brest` (Convoy)
• `BUILD A Paris` (Build unit - Builds phase only)
• `DESTROY A Munich` (Destroy unit - Builds phase only)

*📝 Order Format Notes:*
• Use abbreviations: `A`, `F`, `H`, `S`, `C`, `BUILD`, `DESTROY`
• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`, `BUILD`, `DESTROY`
• **Important:** Mix abbreviations and full names in the same order
• Examples: `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅ or `A Berlin HOLD` ❌

*🎯 Game Phases:*
• **Movement** (Spring/Autumn) - Submit movement orders
• **Retreat** - Retreat dislodged units
• **Builds** - Build/destroy units based on supply centers

*💡 Tips:*
• Use `/selectunit` for interactive order selection
• Use menu buttons for easier navigation
• Orders are validated in real-time
• Convoy chains are automatically validated
    """
    
    # Add inline keyboard with demo button
    keyboard = [
        [InlineKeyboardButton("🎬 Run Automated Demo Game", callback_data="run_automated_demo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin menu with administrative functions"""
    # Check if user is admin
    if str(update.effective_user.id) != "8019538":
        await update.message.reply_text("❌ Access denied. Admin privileges required.")
        return
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete All Games", callback_data="admin_delete_all_games")],
        [InlineKeyboardButton("👤 Recreate Admin User", callback_data="admin_recreate_admin_user")],
        [InlineKeyboardButton("📊 System Status", callback_data="admin_system_status")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_text = (
        "⚙️ *Admin Menu*\n\n"
        "🔐 *Authorized User*: Admin access granted\n\n"
        "⚠️ *Warning*: Admin functions can affect all users!\n\n"
        "💡 *Available Actions:*\n"
        "🗑️ Delete all games (destructive action)\n"
        "👤 Recreate admin user account\n"
        "📊 View system status\n"
        "⬅️ Return to main menu"
    )
    
    await update.message.reply_text(
        admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

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

async def start_demo_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a demo game where the user plays as Germany with all units in starting positions"""
    try:
        user_id = str(update.effective_user.id)
        user_name = update.effective_user.full_name or "Demo Player"
        
        # Register the user first (required for joining games)
        try:
            api_post("/users/persistent_register", {
                "telegram_id": user_id,
                "full_name": user_name
            })
        except Exception as e:
            # User might already be registered, continue
            logging.info(f"User registration note: {e}")
        
        # Create a demo game
        game_resp = api_post("/games/create", {"map_name": "demo"})
        game_id = game_resp["game_id"]
        
        # Add the user as Germany
        api_post(f"/games/{game_id}/join", {
            "telegram_id": user_id, 
            "game_id": int(game_id), 
            "power": "GERMANY"
        })
        
        # Add AI players for other powers (they won't submit orders)
        other_powers = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]
        for power in other_powers:
            ai_telegram_id = f"ai_{power.lower()}"
            # Register AI player
            try:
                api_post("/users/persistent_register", {
                    "telegram_id": ai_telegram_id,
                    "full_name": f"AI {power}"
                })
            except Exception as e:
                # AI player might already be registered, continue
                logging.info(f"AI player registration note: {e}")
            
            # Join the game
            api_post(f"/games/{game_id}/join", {
                "telegram_id": ai_telegram_id, 
                "game_id": int(game_id), 
                "power": power
            })
        
        # Generate the map with starting positions
        await send_demo_map(update, context, game_id)
        
        # Show demo game controls
        keyboard = [
            [InlineKeyboardButton("📋 Submit Orders", callback_data=f"demo_orders_{game_id}")],
            [InlineKeyboardButton("🗺️ View Map", callback_data=f"view_map_{game_id}")],
            [InlineKeyboardButton("ℹ️ Demo Help", callback_data=f"demo_help_{game_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        demo_text = (
            f"🎮 *Demo Game Started!* (ID: {game_id})\n\n"
            "🇩🇪 *You are Germany* - Make your moves!\n"
            "🤖 Other powers are AI-controlled (they won't move)\n\n"
            "💡 *Available Commands:*\n"
            "📋 Submit orders for Germany\n"
            "🗺️ View current map state\n"
            "ℹ️ Get help with demo mode\n\n"
            "*Example Orders:*\n"
            "• `A Berlin - Kiel` (Army move)\n"
            "• `A Munich - Bohemia` (Army move)\n"
            "• `F Kiel - Denmark` (Fleet move)\n"
            "• `A Berlin H` (Hold)\n"
            "• `A Berlin S A Munich - Kiel` (Support)\n"
            "• `F Kiel C A Berlin - Denmark` (Convoy)\n\n"
            "*📝 Order Format:*\n"
            "• Use abbreviations: `A`, `F`, `H`, `S`, `C`\n"
            "• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`\n"
            "• **Don't mix:** `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅\n\n"
            "*Interactive Features:*\n"
            "• Use `/selectunit` for guided order selection\n"
            "• Use `/processturn {game_id}` to advance the game\n"
            "• Use `/viewmap {game_id}` to see current state"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                demo_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                demo_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        error_msg = f"❌ Error starting demo game: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

async def run_automated_demo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run the automated demo game script and show results"""
    try:
        import subprocess
        import os
        
        # Get the path to the demo script
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "demo_automated_game.py")
        
        # Check if the script exists
        if not os.path.exists(script_path):
            error_msg = f"❌ Demo script not found at {script_path}"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Run the demo script with proper environment
        result = subprocess.run(
            ["python3", "demo_automated_game.py"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}
        )
        
        if result.returncode == 0:
            # Success - show summary
            success_msg = (
                "🎬 *Automated Demo Game Complete!*\n\n"
                "✅ The demo game ran successfully through multiple phases:\n"
                "• Spring 1901 Movement\n"
                "• Spring 1901 Builds\n"
                "• Autumn 1901 Movement\n"
                "• Autumn 1901 Builds\n"
                "• Spring 1902 Movement\n"
                "• Spring 1902 Builds\n\n"
                "🗺️ Maps have been generated and saved to:\n"
                f"`{os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'test_maps')}/`\n\n"
                "💡 *To run the demo yourself:*\n"
                "```bash\n"
                f"cd {os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}\n"
                "python3 demo_automated_game.py\n"
                "```"
            )
            
            if update.callback_query:
                await update.callback_query.edit_message_text(success_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(success_msg, parse_mode='Markdown')
        else:
            # Error occurred
            error_msg = (
                f"❌ *Demo script failed*\n\n"
                f"**Error:** {result.stderr[:500]}\n\n"
                f"**Output:** {result.stdout[:500]}"
            )
            
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(error_msg, parse_mode='Markdown')
                
    except Exception as e:
        error_msg = f"❌ Error running automated demo: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

async def send_demo_map(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Send the demo map with all units in starting positions"""
    try:
        # Get game state
        game_state = api_get(f"/games/{game_id}/state")
        
        # Generate map with units
        from src.engine.map import Map
        map_instance = Map("standard")
        
        # Create units dictionary from game state
        units = {}
        if "powers" in game_state:
            for power_name, power_data in game_state["powers"].items():
                if "units" in power_data:
                    for unit in power_data["units"]:
                        units[unit] = power_name
        
        # Get phase information
        phase_info = {
            "year": str(game_state.get("year", 1901)),
            "season": game_state.get("season", "Spring"),
            "phase": game_state.get("phase", "Movement"),
            "phase_code": game_state.get("phase_code", "S1901M")
        }
        
        # Render the map
        img_bytes = map_instance.render_board_png(units, f"/tmp/demo_map_{game_id}.png", phase_info=phase_info)
        
        # Send the map
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=img_bytes,
                caption=f"🗺️ *Demo Game Map* (ID: {game_id})\n\nAll units in starting positions!"
            )
        else:
            await update.message.reply_photo(
                photo=img_bytes,
                caption=f"🗺️ *Demo Game Map* (ID: {game_id})\n\nAll units in starting positions!"
            )
            
    except Exception as e:
        error_msg = f"❌ Error generating demo map: {str(e)}"
        if update.callback_query:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

async def send_game_map(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Send the live game map with current state and moves"""
    try:
        # Get game state
        game_state = api_get(f"/games/{game_id}/state")
        
        if not game_state:
            error_msg = f"❌ Game {game_id} not found"
            if update.callback_query:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Get current orders for move visualization
        orders_data = api_get(f"/games/{game_id}/orders")
        orders = orders_data if orders_data else []
        
        # Generate map with units
        from src.engine.map import Map
        map_instance = Map("standard")
        
        # Create units dictionary from game state
        units = {}
        if "units" in game_state:
            # units is already in the correct format: {power: [unit_list]}
            units = game_state["units"]
        
        # Get phase information
        phase_info = {
            "year": str(game_state.get("year", 1901)),
            "season": game_state.get("season", "Spring"),
            "phase": game_state.get("phase", "Movement"),
            "phase_code": game_state.get("phase_code", "S1901M")
        }
        
        # Render the map with moves
        svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        img_bytes = Map.render_board_png_with_moves(svg_path, units, orders, f"/tmp/game_map_{game_id}.png", phase_info=phase_info)
        
        # Get game info for caption
        turn = game_state.get("turn", "Unknown")
        phase = game_state.get("phase", "Unknown")
        
        # Count moves for caption
        move_count = len([o for o in orders if "order" in o and ("-" in o["order"] or "S" in o["order"])])
        
        # Send the map
        caption = (
            f"🗺️ *Game {game_id} Map*\n\n"
            f"📊 Turn: {turn} | Phase: {phase}\n"
            f"🎮 Current game state with all units\n"
            f"📋 {len(orders)} orders submitted ({move_count} moves)"
        )
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=img_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_photo(
                photo=img_bytes,
                caption=caption,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        error_msg = f"❌ Error generating game map: {str(e)}"
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
    
    # Add admin menu for admin user (ID: 8019538)
    user_id = str(update.effective_user.id)
    logging.info(f"show_main_menu - User ID: {user_id}, Type: {type(user_id)}")
    if user_id == "8019538":
        keyboard.append([KeyboardButton("⚙️ Admin")])
        logging.info("show_main_menu - Admin button added to keyboard")
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    main_text = (
        "🏛️ *Welcome to Diplomacy!*\n\n"
        "I'm your diplomatic assistant. Use the menu below:\n\n"
        "🎯 *Register* if you're new\n"
        "🎮 *My Games* to see your current games\n"
        "🎲 *Join Game* to enter a specific game\n"
        "⏳ *Join Waiting List* for automatic matching\n\n"
        "💡 *New Features:*\n"
        "• Interactive unit selection with `/selectunit`\n"
        "• Full Diplomacy rules implementation\n"
        "• Convoy chain validation\n"
        "• Multi-phase gameplay (Movement/Retreat/Builds)"
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

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simplified order command that automatically detects the game and power"""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Order submission failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /order <order>\n\n"
            "Examples:\n"
            "/order A BER - SIL\n"
            "/order F KIE - DEN\n"
            "/order A MUN S A BER - SIL\n\n"
            "This command will automatically detect your game and power."
        )
        return
    
    order_text = " ".join(args)
    
    try:
        # Get user's games
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games:
            await update.message.reply_text(
                "❌ You're not in any games!\n\n"
                "💡 *To submit orders:*\n"
                "1. Join a game first\n"
                "2. Use /orders <game_id> <order> for specific games\n"
                "3. Or use this command when you're in exactly one game"
            )
            return
        
        if len(user_games) > 1:
            await update.message.reply_text(
                f"❌ You're in {len(user_games)} games. Please specify which game:\n\n"
                "Use: /orders <game_id> <order>\n\n"
                "Your games:\n" + 
                "\n".join([f"• Game {g['game_id']} as {g['power']}" for g in user_games])
            )
            return
        
        # User is in exactly one game
        game = user_games[0]
        game_id = str(game["game_id"])
        power = game["power"]
        
        # Normalize province names in the order
        normalized_order = normalize_order_provinces(order_text, power)
        
        # Submit the order
        result = api_post("/games/set_orders", {
            "game_id": game_id,
            "power": power,
            "orders": [normalized_order],
            "telegram_id": user_id
        })
        
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

async def processturn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the current turn/phase for a game"""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Process turn failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /processturn <game_id>\n\n"
            "This command advances the current phase and processes all submitted orders.\n"
            "Use this after all players have submitted their orders for the turn."
        )
        return
    
    game_id = args[0]
    
    try:
        # Check if user is in this game
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        user_in_game = any(str(g["game_id"]) == str(game_id) for g in user_games)
        
        if not user_in_game:
            await update.message.reply_text(f"You are not in game {game_id}.")
            return
        
        # Process the turn via API
        # The API will automatically restore the game from database if needed
        result = api_post(f"/games/{game_id}/process_turn", {})
        
        if result.get("status") == "ok":
            # Get updated game state
            game_state = api_get(f"/games/{game_id}/state")
            
            if game_state:
                turn = game_state.get("turn", "Unknown")
                phase = game_state.get("phase", "Unknown")
                done = game_state.get("done", False)
                
                if done:
                    await update.message.reply_text(
                        f"🎉 *Turn Processed Successfully!*\n\n"
                        f"📊 Turn: {turn} | Phase: {phase}\n"
                        f"🏁 *Game Complete!*\n\n"
                        f"View the final map with /viewmap {game_id}"
                    )
                else:
                    await update.message.reply_text(
                        f"✅ *Turn Processed Successfully!*\n\n"
                        f"📊 Turn: {turn} | Phase: {phase}\n\n"
                        f"🎮 *Next Phase:* Submit your orders for the next turn\n"
                        f"🗺️ View updated map: /viewmap {game_id}\n"
                        f"📋 Submit orders: /order <your orders>"
                    )
            else:
                await update.message.reply_text("✅ Turn processed successfully!")
        else:
            error_msg = result.get("detail", "Unknown error")
            await update.message.reply_text(f"❌ Failed to process turn: {error_msg}")
            
    except Exception as e:
        await update.message.reply_text(f"Process turn error: {e}")

async def viewmap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View the current map for a specific game"""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("View map failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /viewmap <game_id>\n\n"
            "This command shows the current map state for the specified game."
        )
        return
    
    game_id = args[0]
    
    try:
        # Check if user is in this game
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        user_in_game = any(str(g["game_id"]) == str(game_id) for g in user_games)
        
        if not user_in_game:
            await update.message.reply_text(f"You are not in game {game_id}.")
            return
        
        # Send the game map
        await send_game_map(update, context, game_id)
            
    except Exception as e:
        await update.message.reply_text(f"View map error: {e}")

async def selectunit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's units for interactive order selection"""
    user = update.effective_user
    if not user:
        if update.message:
            await update.message.reply_text("Select unit failed: No user context.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Select unit failed: No user context.")
        return
    user_id = str(user.id)
    
    async def reply_or_edit(text: str, reply_markup=None, parse_mode='Markdown'):
        """Helper function to handle both message and callback query contexts"""
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    
    try:
        # Get user's games
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games:
            await reply_or_edit(
                "❌ You're not in any games!\n\n"
                "💡 *To select units:*\n"
                "1. Join a game first\n"
                "2. Use /selectunit when you're in exactly one game"
            )
            return
        
        if len(user_games) > 1:
            await reply_or_edit(
                f"❌ You're in {len(user_games)} games. Please specify which game:\n\n"
                "Use: /selectunit <game_id>\n\n"
                "Your games:\n" + 
                "\n".join([f"• Game {g['game_id']} as {g['power']}" for g in user_games])
            )
            return
        
        # User is in exactly one game
        game = user_games[0]
        game_id = str(game["game_id"])
        power = game["power"]
        
        # Get current game state
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await reply_or_edit(f"❌ Could not retrieve game state for game {game_id}")
            return
        
        # Get user's units
        units = game_state.get("units", {}).get(power, [])
        if not units:
            await reply_or_edit(f"❌ No units found for {power} in game {game_id}")
            return
        
        # Create inline keyboard with unit buttons
        keyboard = []
        for unit in units:
            # unit format: "A BER" or "F KIE"
            unit_type = unit.split()[0]  # A or F
            unit_location = unit.split()[1]  # BER, KIE, etc.
            
            # Create button text with emoji
            emoji = "🛡️" if unit_type == "A" else "🚢"
            button_text = f"{emoji} {unit}"
            
            # Create callback data (replace spaces with underscores)
            callback_data = f"select_unit_{game_id}_{unit.replace(' ', '_')}"
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_unit_selection_{game_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await reply_or_edit(
            f"🎯 *Select a Unit for Orders*\n\n"
            f"📊 Game: {game_id} | Power: {power}\n"
            f"🛡️ Army | 🚢 Fleet\n\n"
            f"Choose a unit to see its possible moves:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await reply_or_edit(f"Select unit error: {e}")

async def show_possible_moves(query, game_id: str, unit: str) -> None:
    """Show possible moves for a selected unit"""
    try:
        # Get game state to determine unit location and type
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await query.edit_message_text(f"❌ Could not retrieve game state for game {game_id}")
            return
        
        # Parse unit info
        unit_parts = unit.split()
        unit_type = unit_parts[0]  # A or F
        unit_location = unit_parts[1]  # BER, KIE, etc.
        
        # Get adjacency data from map
        from src.engine.map import Map
        map_instance = Map("standard")
        
        # Get adjacent provinces
        adjacent_provinces = map_instance.get_adjacency(unit_location)
        
        # Filter adjacent provinces based on unit type
        valid_moves = []
        for province in adjacent_provinces:
            province_info = map_instance.provinces.get(province)
            if province_info:
                # Armies can move to land and coast provinces
                # Fleets can move to water and coast provinces
                if unit_type == "A" and province_info.type in ["land", "coast"]:
                    valid_moves.append(province)
                elif unit_type == "F" and province_info.type in ["water", "coast"]:
                    valid_moves.append(province)
        
        # Create keyboard with move options
        keyboard = []
        
        # Add Hold option
        keyboard.append([InlineKeyboardButton("🛑 Hold", callback_data=f"move_unit_{game_id}_{unit_type}_{unit_location}_hold")])
        
        # Add Move options
        for province in valid_moves:
            button_text = f"➡️ Move to {province}"
            callback_data = f"move_unit_{game_id}_{unit_type}_{unit_location}_move_{province}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add Support option (simplified for now)
        keyboard.append([InlineKeyboardButton("🤝 Support", callback_data=f"move_unit_{game_id}_{unit_type}_{unit_location}_support")])
        
        # Add Convoy option for fleets
        if unit_type == "F":
            keyboard.append([InlineKeyboardButton("🚢 Convoy", callback_data=f"move_unit_{game_id}_{unit_type}_{unit_location}_convoy")])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_move_selection_{game_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Create unit emoji
        emoji = "🛡️" if unit_type == "A" else "🚢"
        
        await query.edit_message_text(
            f"🎯 *Possible Moves for {emoji} {unit}*\n\n"
            f"📍 Location: {unit_location}\n"
            f"📊 Game: {game_id}\n\n"
            f"Choose an action:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error showing possible moves: {e}")

async def show_convoy_options(query, game_id: str, fleet_unit: str) -> None:
    """Show convoy options for a fleet"""
    try:
        # Get game state to find armies that can be convoyed
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await query.edit_message_text(f"❌ Could not retrieve game state for game {game_id}")
            return
        
        # Parse fleet info
        fleet_parts = fleet_unit.split()
        fleet_type = fleet_parts[0]  # Should be 'F'
        fleet_location = fleet_parts[1]  # e.g., 'NTH', 'ENG'
        
        if fleet_type != "F":
            await query.edit_message_text(f"❌ Only fleets can convoy. {fleet_unit} is not a fleet.")
            return
        
        # Get map instance for adjacency data
        from src.engine.map import Map
        map_instance = Map("standard")
        
        # Get provinces adjacent to the fleet's sea area
        adjacent_provinces = map_instance.get_adjacency(fleet_location)
        
        # Get all armies in the game that are adjacent to this fleet's sea area
        all_units = game_state.get("units", {})
        convoyable_armies = []
        
        for power, units in all_units.items():
            for unit in units:
                if unit.startswith("A "):  # Army
                    army_location = unit.split()[1]  # e.g., 'LON', 'PAR'
                    # Only include armies that are adjacent to the fleet's sea area
                    if army_location in adjacent_provinces:
                        convoyable_armies.append((power, unit))
        
        if not convoyable_armies:
            await query.edit_message_text(
                f"❌ No armies found adjacent to {fleet_location} that can be convoyed by {fleet_unit}\n\n"
                f"📍 Adjacent provinces: {', '.join(adjacent_provinces)}"
            )
            return
        
        # Create keyboard with convoy options
        keyboard = []
        
        for power, army_unit in convoyable_armies:
            army_location = army_unit.split()[1]  # e.g., 'LON', 'PAR'
            button_text = f"🚢 Convoy {power} {army_unit}"
            callback_data = f"convoy_select_{game_id}_{fleet_unit.replace(' ', '_')}_{power}_{army_unit.replace(' ', '_')}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_move_selection_{game_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚢 *Convoy Options for {fleet_unit}*\n\n"
            f"📍 Fleet Location: {fleet_location}\n"
            f"📍 Adjacent Provinces: {', '.join(adjacent_provinces)}\n"
            f"📊 Game: {game_id}\n\n"
            f"Select an army to convoy:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error showing convoy options: {e}")

async def show_convoy_destinations(query, game_id: str, fleet_unit: str, army_power: str, army_unit: str) -> None:
    """Show convoy destination options for an army"""
    try:
        # Get game state and map data
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await query.edit_message_text(f"❌ Could not retrieve game state for game {game_id}")
            return
        
        # Parse fleet and army info
        fleet_location = fleet_unit.split()[1]  # e.g., 'NTH', 'ENG'
        army_location = army_unit.split()[1]    # e.g., 'LON', 'PAR'
        
        # Get map instance for adjacency data
        from src.engine.map import Map
        map_instance = Map("standard")
        
        # Get provinces adjacent to the fleet's sea area that can be convoy destinations
        # A convoy can only reach provinces adjacent to the convoying fleet's sea area
        adjacent_provinces = map_instance.get_adjacency(fleet_location)
        
        # Filter to only coastal provinces (armies can only be convoyed to coastal provinces)
        convoy_destinations = []
        for province_name in adjacent_provinces:
            province_info = map_instance.get_province(province_name)
            if province_info and province_info.type == "coast":
                convoy_destinations.append(province_name)
        
        if not convoy_destinations:
            await query.edit_message_text(
                f"❌ No valid convoy destinations found for {fleet_unit}\n\n"
                f"📍 Fleet Location: {fleet_location}\n"
                f"📍 Adjacent Provinces: {', '.join(adjacent_provinces)}\n"
                f"💡 Convoy destinations must be coastal provinces adjacent to the fleet's sea area."
            )
            return
        
        # Create keyboard with convoy destination options
        keyboard = []
        
        for province in convoy_destinations:
            button_text = f"🚢 Convoy to {province}"
            callback_data = f"convoy_dest_{game_id}_{fleet_unit.replace(' ', '_')}_{army_power}_{army_unit.replace(' ', '_')}_{province}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        # Add cancel button
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_move_selection_{game_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚢 *Convoy Destination for {army_unit}*\n\n"
            f"📍 Army Location: {army_location}\n"
            f"🚢 Convoying Fleet: {fleet_unit}\n"
            f"📍 Valid Destinations: {', '.join(convoy_destinations)}\n"
            f"📊 Game: {game_id}\n\n"
            f"Select convoy destination:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Error showing convoy destinations: {e}")

async def submit_interactive_order(query, game_id: str, order_text: str) -> None:
    """Submit an order created through interactive selection"""
    try:
        # Get user info
        user_id = str(query.from_user.id)
        
        # Get user's power in this game
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        power = None
        for g in user_games:
            if str(g["game_id"]) == str(game_id):
                power = g["power"]
                break
        
        if not power:
            await query.edit_message_text(f"❌ You are not in game {game_id}")
            return
        
        # Normalize province names in the order
        normalized_order = normalize_order_provinces(order_text, power)
        
        # Submit the order
        result = api_post("/games/set_orders", {
            "game_id": game_id,
            "power": power,
            "orders": [normalized_order],
            "telegram_id": user_id
        })
        
        results = result.get("results", [])
        if results and results[0]["success"]:
            await query.edit_message_text(
                f"✅ *Order Submitted Successfully!*\n\n"
                f"📋 Order: `{normalized_order}`\n"
                f"🎮 Game: {game_id}\n"
                f"👤 Power: {power}\n\n"
                f"💡 *Next Steps:*\n"
                f"• Submit more orders with /selectunit\n"
                f"• Process turn with /processturn {game_id}\n"
                f"• View map with /viewmap {game_id}\n"
                f"• View orders with /myorders {game_id}\n"
                f"• Clear orders with /clearorders {game_id}",
                parse_mode='Markdown'
            )
        else:
            error_msg = results[0]["error"] if results else "Unknown error"
            await query.edit_message_text(
                f"❌ *Order Failed*\n\n"
                f"📋 Order: `{normalized_order}`\n"
                f"❌ Error: {error_msg}\n\n"
                f"💡 Try selecting a different move or use /orders command",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        await query.edit_message_text(f"❌ Error submitting order: {e}")

def normalize_order_provinces(order_text: str, power: str) -> str:
    """Normalize province names in an order string."""
    from src.engine.province_mapping import normalize_province_name
    
    # Split the order into parts
    parts = order_text.split()
    
    # The order format is: UNIT_TYPE PROVINCE [ACTION] [TARGET_PROVINCE]
    # NOT: POWER UNIT_TYPE PROVINCE [ACTION] [TARGET_PROVINCE]
    # The power is handled separately in the API call
    
    normalized_parts = []
    for i, part in enumerate(parts):
        # Skip unit type (A/F) - first part
        if i == 0 and part in ['A', 'F']:
            normalized_parts.append(part)
            continue
        
        # Check if this part looks like a province name
        # Province names are typically 3-4 characters and uppercase
        if len(part) >= 2 and part.isalpha():
            # This might be a province name
            normalized_province = normalize_province_name(part)
            normalized_parts.append(normalized_province)
        else:
            # This is likely an action word (-, S, H, etc.) or other non-province text
            normalized_parts.append(part)
    
    return " ".join(normalized_parts)

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
        
        # Normalize province names in all orders
        normalized_orders = []
        for order in orders:
            normalized_order = normalize_order_provinces(order, power)
            normalized_orders.append(normalized_order)
        
        result = api_post("/games/set_orders", 
                         {"game_id": game_id, "power": power, "orders": normalized_orders, "telegram_id": user_id})
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
        
        # Get phase information
        phase_info = {
            "year": str(game_state.get("year", 1901)),
            "season": game_state.get("season", "Spring"),
            "phase": game_state.get("phase", "Movement"),
            "phase_code": game_state.get("phase_code", "S1901M")
        }
        
        base_map_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg").replace("standard.svg", "")
        svg_path = f"{base_map_path}{map_name}.svg"
        if not os.path.isfile(svg_path):
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
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
        
        # Get phase information from state
        phase_info = {
            "year": str(state.get("year", 1901)),
            "season": state.get("season", "Spring"),
            "phase": state.get("phase", "Movement"),
            "phase_code": state.get("phase_code", "S1901M")
        }
        
        base_map_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg").replace("standard.svg", "")
        svg_path = f"{base_map_path}{map_name}.svg"
        if not os.path.isfile(svg_path):
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
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
    if not user:
        if update.message:
            await update.message.reply_text("Wait command failed: No user context.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("Wait command failed: No user context.")
        return
    
    async def reply_or_edit(text: str, parse_mode='Markdown'):
        """Helper function to handle both message and callback query contexts"""
        if update.message:
            await update.message.reply_text(text, parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode=parse_mode)
    
    user_id = str(user.id)
    full_name = getattr(user, 'full_name', None) or user_id
    # Check if already in waiting list
    if any(u[0] == user_id for u in WAITING_LIST):
        await reply_or_edit("You are already in the waiting list for the next game.")
        return
    WAITING_LIST.append((user_id, full_name))
    await reply_or_edit(
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
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("processturn", processturn))
    app.add_handler(CommandHandler("viewmap", viewmap))
    app.add_handler(CommandHandler("selectunit", selectunit))
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
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("refresh", refresh_keyboard))

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

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to show user information"""
    if not update.message:
        return
    
    user = update.effective_user
    user_id = str(user.id)
    user_id_int = user.id
    
    debug_text = (
        f"🔍 *Debug Information*\n\n"
        f"👤 User ID (str): `{user_id}`\n"
        f"👤 User ID (int): `{user_id_int}`\n"
        f"📝 User ID Type: `{type(user_id)}`\n"
        f"🔢 Is 8019538?: `{user_id == '8019538'}`\n"
        f"📛 Username: `{user.username or 'None'}`\n"
        f"📛 Full Name: `{user.full_name or 'None'}`\n\n"
        f"⚙️ Admin Access: {'✅ YES' if user_id == '8019538' else '❌ NO'}"
    )
    
    await update.message.reply_text(debug_text, parse_mode='Markdown')

async def refresh_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh the keyboard to show updated buttons (like admin button)"""
    if not update.message:
        return
    
    # Create main menu keyboard
    keyboard = [
        [KeyboardButton("🎯 Register"), KeyboardButton("🎮 My Games")],
        [KeyboardButton("🎲 Join Game"), KeyboardButton("⏳ Join Waiting List")],
        [KeyboardButton("📋 My Orders"), KeyboardButton("🗺️ View Map")],
        [KeyboardButton("💬 Messages"), KeyboardButton("ℹ️ Help")]
    ]
    
    # Add admin menu for admin user (ID: 8019538)
    user_id = str(update.effective_user.id)
    if user_id == "8019538":
        keyboard.append([KeyboardButton("⚙️ Admin")])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        "🔄 *Keyboard Refreshed!*\n\n"
        "Your menu has been updated with the latest buttons.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

if __name__ == "__main__":
    main()
