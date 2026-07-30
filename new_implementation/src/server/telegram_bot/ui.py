"""
UI and menu helpers for the Telegram bot.
"""
import logging

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .game_context import fetch_user_games
from .games import register, games, show_available_games, wait
from .help_text import EXAMPLES_TEXT, HELP_TEXT, RULES_TEXT
from .orders import show_my_orders_menu
from .messages import show_messages_menu

logger = logging.getLogger("diplomacy.telegram_bot.ui")


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
    logger.info(f"show_main_menu - User ID: {user_id}, Type: {type(user_id)}")
    if user_id == "8019538":
        keyboard.append([KeyboardButton("⚙️ Admin")])
        logger.info("show_main_menu - Admin button added to keyboard")

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


async def show_map_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show map menu for user's games."""
    try:
        user_id = str(update.effective_user.id)
        user_games = fetch_user_games(user_id)

        if not user_games:
            keyboard = [
                [InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")],
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
            game_id = game.get('game_id', 'Unknown')
            power = game.get('power', 'Unknown')
            state = game.get('status', 'Unknown')
            keyboard.append([InlineKeyboardButton(f"🗺️ Game {game_id} Map ({power}) - {state}", callback_data=f"view_map_{game_id}")])

        # Also offer the unit-less sample board.
        keyboard.append([InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")])

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
            [InlineKeyboardButton("🗺️ View Sample Map", callback_data="view_default_map")],
            [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                f"⚠️ *Can't Load Game Maps*\n\n"
                f"🔧 Unable to access your game maps right now.\n\n"
                f"💡 *You can still:*\n"
                f"🗺️ View the standard board\n"
                f"🎲 Browse available games\n"
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
                f"🗺️ View the standard board\n"
                f"🎲 Browse available games\n"
                f"🏠 Return to main menu\n\n"
                f"*Error:* {str(e)[:100]}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rules command - show basic Diplomacy rules and order syntax."""
    await update.message.reply_text(RULES_TEXT, parse_mode='Markdown')


async def examples(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /examples command - show order syntax examples."""
    await update.message.reply_text(EXAMPLES_TEXT, parse_mode='Markdown')


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help with available commands"""
    # Add inline keyboard with demo button
    keyboard = [
        [InlineKeyboardButton("🎬 Run Perfect Demo Game", callback_data="run_automated_demo")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown', reply_markup=reply_markup)


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

