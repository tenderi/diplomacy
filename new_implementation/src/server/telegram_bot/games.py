"""
Game management commands for the Telegram bot.
"""
import logging
import asyncio
import random
import requests
from typing import List, Tuple, Optional

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from .api_client import api_post, api_get

logger = logging.getLogger("diplomacy.telegram_bot.games")

# --- In-memory waiting list for automated game creation ---
WAITING_LIST: List[Tuple[str, str]] = []  # List of (telegram_id, full_name)
WAITING_LIST_SIZE = 7  # Standard Diplomacy
POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - welcome message and main menu."""
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
    logger.info(f"User ID: {user_id}, Type: {type(user_id)}")
    if user_id == "8019538":
        keyboard.append([KeyboardButton("⚙️ Admin")])
        logger.info("Admin button added to keyboard")
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

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
    """Handle /register command - register a new user."""
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
    """Handle /games command - list user's active games."""
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    try:
        # List all games the user is in
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


async def show_available_games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available games with inline buttons."""
    async def reply_or_edit(text: str, reply_markup=None, parse_mode='Markdown'):
        """Helper function to handle both message and callback query contexts"""
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    try:
        games_resp = api_get("/games")
        # Normalize response: support both {"games": [...]} and plain list
        games = []
        if isinstance(games_resp, dict) and "games" in games_resp:
            games = games_resp.get("games", [])
        elif isinstance(games_resp, list):
            games = games_resp
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


async def show_power_selection(update: Update, game_id: str) -> None:
    """Show available powers for a specific game."""
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


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join command - join a game as a specific power."""
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
        result = api_post(f"/games/{game_id}/join", {"telegram_id": user_id, "game_id": int(game_id), "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have joined game {game_id} as {power}.")
        elif result.get("status") == "already_joined":
            await update.message.reply_text(f"You are already in game {game_id} as {power}.")
        else:
            await update.message.reply_text(f"Join failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to join game: {e}")


async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quit command - quit a game."""
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
        result = api_post(f"/games/{game_id}/quit", {"telegram_id": user_id, "game_id": int(game_id)})
        if result.get("status") == "ok":
            await update.message.reply_text(f"You have quit game {game_id}.")
        elif result.get("status") == "not_in_game":
            await update.message.reply_text(f"You are not in game {game_id}.")
        else:
            await update.message.reply_text(f"Quit failed: {result}")
    except Exception as e:
        await update.message.reply_text(f"Failed to quit game: {e}")


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


def process_waiting_list(
    waiting_list: List[Tuple[str, str]],
    waiting_list_size: int,
    powers: List[str],
    notify_callback,
    api_post_func=None
) -> Tuple[Optional[str], Optional[List[Tuple[Tuple[str, str], str]]]]:
    """
    Process the waiting list: if enough players, create a game, assign powers, and notify users.
    notify_callback(telegram_id, message) is called for each user.
    Returns (game_id, assignments) if a game was created, else (None, None).
    """
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
                api_post_func(
                    f"/games/{game_id}/join",
                    {"telegram_id": telegram_id, "game_id": int(game_id), "power": power}
                )
            # Notify users
            for (telegram_id, full_name), power in assigned_powers:
                try:
                    notify_callback(telegram_id, f"A new game (ID: {game_id}) has started! You are {power}.")
                except Exception as e:
                    logger.warning(f"Failed to notify {telegram_id}: {e}")
            # Remove assigned users from waiting list
            del waiting_list[:waiting_list_size]
            return game_id, assigned_powers
        except Exception as e:
            logger.error(f"Failed to create game: {e}")
            return None, None
    return None, None


async def wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wait command - join the waiting list for automatic game matching."""
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
        f"You will be notified when the game starts."
    )
    # If enough players, create a new game
    async def telegram_notify_callback(telegram_id, message):
        try:
            await update.get_bot().send_message(chat_id=telegram_id, text=message)
        except Exception as e:
            logger.warning(f"Failed to notify {telegram_id}: {e}")

    # Use a sync wrapper for process_waiting_list
    def sync_notify_callback(telegram_id, message):
        asyncio.create_task(telegram_notify_callback(telegram_id, message))

    process_waiting_list(WAITING_LIST, WAITING_LIST_SIZE, POWERS, sync_notify_callback)

