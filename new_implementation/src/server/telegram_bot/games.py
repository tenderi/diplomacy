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
    """Handle /register command - register user with the bot."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Registration failed: No user context.")
        return
    user_id = str(user.id)
    full_name = f"{user.first_name} {user.last_name}".strip() if user.last_name else user.first_name
    username = user.username or ""
    try:
        result = api_post("/users/persistent_register", {
            "telegram_id": user_id,
            "full_name": full_name,
            "username": username
        })
        if result.get("status") == "ok":
            await update.message.reply_text(
                f"✅ *Registration Successful!*\n\n"
                f"Welcome, {full_name}!\n\n"
                f"🎮 You can now:\n"
                f"• Join games with /join\n"
                f"• View available games with /games\n"
                f"• Join the waiting list with /wait",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"Registration error: {result.get('message', 'Unknown error')}")
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
            f"🎲 Browse available games\n"
            f"🏠 Return to main menu",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - get current game status, phase, and deadline."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Status command failed: No user context.")
        return
    
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    
    try:
        # Get user's games
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games:
            await update.message.reply_text(
                "❌ You're not in any games!\n\n"
                "💡 Join a game first with /join or /games"
            )
            return
        
        # If game_id provided, show status for that game
        if args:
            game_id = args[0]
            # Find the game
            target_game = None
            for g in user_games:
                if str(g.get('game_id')) == str(game_id):
                    target_game = g
                    break
            
            if not target_game:
                await update.message.reply_text(f"You are not in game {game_id}.")
                return
            
            # Get detailed game state
            game_state = api_get(f"/games/{game_id}/state")
            if not game_state:
                await update.message.reply_text(f"Could not retrieve status for game {game_id}.")
                return
            
            power = target_game.get('power', 'Unknown')
            year = game_state.get('year', 1901)
            season = game_state.get('season', 'Spring')
            phase = game_state.get('phase', 'Movement')
            phase_code = game_state.get('phase_code', 'S1901M')
            deadline = game_state.get('deadline')
            
            status_text = (
                f"📊 *Game {game_id} Status*\n\n"
                f"🎯 **You are:** {power}\n"
                f"📅 **Turn:** {year} {season}\n"
                f"🔄 **Phase:** {phase}\n"
                f"📝 **Phase Code:** {phase_code}\n"
            )
            
            if deadline:
                status_text += f"⏰ **Deadline:** {deadline}\n"
            
            # Get order submission status
            orders_data = api_get(f"/games/{game_id}/orders")
            if orders_data:
                submitted_powers = list(orders_data.get('orders', {}).keys())
                if power in submitted_powers:
                    status_text += f"\n✅ **Your orders:** Submitted"
                else:
                    status_text += f"\n⏳ **Your orders:** Not yet submitted"
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
        else:
            # Show status for all user's games
            if len(user_games) == 1:
                # Auto-select if only one game
                game_id = str(user_games[0].get('game_id'))
                # Recursively call with game_id
                context.args = [game_id]
                await status(update, context)
            else:
                # Show list of games
                lines = [f"📊 *Your Games Status* ({len(user_games)})\n"]
                for g in user_games:
                    game_id = str(g.get('game_id', 'Unknown'))
                    power = g.get('power', 'Unknown')
                    state = g.get('state', 'Unknown')
                    lines.append(f"🏰 **Game {game_id}** ({power}) - {state}")
                    lines.append(f"   Use `/status {game_id}` for details")
                
                await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"Error retrieving status: {e}")


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /players command - list all players in current game with their powers."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Players command failed: No user context.")
        return
    
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    
    try:
        # Get user's games
        user_games_response = api_get(f"/users/{user_id}/games")
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games:
            await update.message.reply_text(
                "❌ You're not in any games!\n\n"
                "💡 Join a game first with /join or /games"
            )
            return
        
        # Determine which game to show players for
        if args:
            game_id = args[0]
            # Verify user is in this game
            target_game = None
            for g in user_games:
                if str(g.get('game_id')) == str(game_id):
                    target_game = g
                    break
            
            if not target_game:
                await update.message.reply_text(f"You are not in game {game_id}.")
                return
        else:
            # Use first game if only one
            if len(user_games) == 1:
                game_id = str(user_games[0].get('game_id'))
            else:
                await update.message.reply_text(
                    f"Please specify a game ID:\n\n"
                    + "\n".join([f"• `/players {g.get('game_id')}` - Game {g.get('game_id')} ({g.get('power')})" 
                                for g in user_games]),
                    parse_mode='Markdown'
                )
                return
        
        # Get game state and players
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await update.message.reply_text(f"Could not retrieve game {game_id}.")
            return
        
        # Get players from API
        players_data = api_get(f"/games/{game_id}/players")
        if not players_data:
            await update.message.reply_text(f"Could not retrieve players for game {game_id}.")
            return
        
        players_list = players_data.get('players', [])
        if not players_list:
            await update.message.reply_text(f"No players found in game {game_id}.")
            return
        
        # Format player list
        lines = [f"👥 *Players in Game {game_id}*\n"]
        for player in players_list:
            power = player.get('power', 'Unknown')
            user_info = player.get('user', {})
            username = user_info.get('username') or user_info.get('full_name', 'Unknown')
            is_active = player.get('is_active', True)
            status_emoji = "✅" if is_active else "❌"
            lines.append(f"{status_emoji} **{power}** - {username}")
        
        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"Error retrieving players: {e}")


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
    query = update.callback_query
    if not query:
        return
    
    try:
        # Get game state to see available powers
        game_state = api_get(f"/games/{game_id}/state")
        if not game_state:
            await query.edit_message_text(f"Could not retrieve game {game_id}.")
            return
        
        # Get players to see which powers are taken
        players_data = api_get(f"/games/{game_id}/players")
        taken_powers = set()
        if players_data:
            for player in players_data.get('players', []):
                taken_powers.add(player.get('power'))
        
        # Create keyboard with available powers
        keyboard = []
        for power in POWERS:
            if power not in taken_powers:
                button_text = f"Join as {power}"
                callback_data = f"join_game_{game_id}_{power}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        if not keyboard:
            await query.edit_message_text(f"Game {game_id} is full. All powers are taken.")
            return
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_games")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎮 *Select Power for Game {game_id}*\n\n"
            f"Available powers:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    except Exception as e:
        await query.edit_message_text(f"Error: {str(e)}")


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join command - join a game as a specific power."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Join command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text("Usage: /join <game_id> <power>")
        return
    game_id = args[0]
    power = args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/join", {"telegram_id": user_id, "game_id": int(game_id), "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"🎉 Successfully joined Game {game_id} as {power}!")
        elif result.get("status") == "already_joined":
            await update.message.reply_text(f"You are already in Game {game_id} as {power}.")
        else:
            await update.message.reply_text(f"Failed to join: {result.get('message', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Join error: {e}")


async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quit command - quit a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Quit command failed: No user context.")
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
            await update.message.reply_text(f"You have left Game {game_id}.")
        elif result.get("status") == "not_in_game":
            await update.message.reply_text(f"You are not in Game {game_id}.")
        else:
            await update.message.reply_text(f"Failed to quit: {result.get('message', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Quit error: {e}")


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
    game_id = args[0]
    power = args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/replace", {"telegram_id": user_id, "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"✅ Successfully replaced player for {power} in Game {game_id}!")
        else:
            await update.message.reply_text(f"Failed to replace: {result.get('message', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"Replace error: {e}")


async def wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Process the waiting list: if enough players, create a game, assign powers, and notify users.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Wait command failed: No user context.")
        return
    
    user_id = str(user.id)
    full_name = f"{user.first_name} {user.last_name}".strip() if user.last_name else user.first_name
    
    # Check if user is already in waiting list
    if any(uid == user_id for uid, _ in WAITING_LIST):
        await update.message.reply_text("⏳ You're already on the waiting list!")
        return
    
    # Add to waiting list
    WAITING_LIST.append((user_id, full_name))
    await update.message.reply_text(
        f"⏳ Added to waiting list! ({len(WAITING_LIST)}/{WAITING_LIST_SIZE} players)\n\n"
        f"When {WAITING_LIST_SIZE} players join, a new game will be created automatically."
    )
    
    # If enough players, create a new game
    if len(WAITING_LIST) >= WAITING_LIST_SIZE:
        players = WAITING_LIST[:WAITING_LIST_SIZE]
        random.shuffle(players)
        assigned_powers = list(zip(players, POWERS))
        
        try:
            # Create game
            game_resp = api_post("/games/create", {"map_name": "standard"})
            game_id = game_resp.get("game_id")
            
            # Add all players
            for (player_id, player_name), power in assigned_powers:
                api_post(
                    f"/games/{game_id}/join",
                    {"telegram_id": player_id, "game_id": int(game_id), "power": power}
                )
            
            # Clear waiting list
            WAITING_LIST.clear()
            
            # Notify all players (would need bot instance)
            logger.info(f"Created game {game_id} with {len(assigned_powers)} players from waiting list")
            
        except Exception as e:
            logger.error(f"Error creating game from waiting list: {e}")
            await update.message.reply_text(f"Error creating game: {e}")
