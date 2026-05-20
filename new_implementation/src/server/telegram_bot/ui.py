"""
UI and menu helpers for the Telegram bot.
"""
import logging
import requests

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_get
from .games import register, games, show_available_games, wait
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
    """Show map menu for user's games or default map if not in any games"""
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


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /rules command - show basic Diplomacy rules and order syntax."""
    rules_text = """
📜 *Diplomacy Rules & Order Syntax*

*🎯 Basic Rules:*
• 7 powers compete for control of Europe
• Each turn has 3 phases: Movement, Retreat, Builds
• Control supply centers to build units
• Eliminate other powers to win

*📝 Order Types:*
• **Move:** `A PAR - BUR` (Army moves from Paris to Burgundy)
• **Hold:** `A PAR H` (Army holds position)
• **Support:** `A MAR S A PAR - BUR` (Army in Marseilles supports move from Paris to Burgundy)
• **Convoy:** `F NTH C A LON - BEL` (Fleet in North Sea convoys Army from London to Belgium)
• **Move via Convoy:** `A LON - BEL VIA CONVOY` (Army moves via convoy chain)

*🏗️ Build Phase Orders:*
• **Build:** `BUILD A PAR` (Build army in Paris)
• **Destroy:** `DESTROY A MUN` (Destroy army in Munich)

*📋 Order Format:*
• Use abbreviations: `A`, `F`, `H`, `S`, `C`
• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`
• **Important:** Don't mix abbreviations and full names in the same order
• Examples: `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅ or `A Berlin HOLD` ❌

*🔄 Game Phases:*
• **Movement** (Spring/Autumn): Submit movement, support, convoy orders
• **Retreat**: Retreat dislodged units to adjacent provinces
• **Builds**: Build or destroy units based on supply center control

*💡 Tips:*
• Units can't move into occupied provinces (except with support)
• Support can help attacks or defenses
• Convoy chains allow armies to cross water
• Supply centers control persists even if units leave
    """
    await update.message.reply_text(rules_text, parse_mode='Markdown')


async def examples(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /examples command - show order syntax examples."""
    examples_text = """
📚 *Order Syntax Examples*

*🎯 Movement Orders:*
• `A Vienna - Trieste` - Army moves from Vienna to Trieste
• `F London - North Sea` - Fleet moves from London to North Sea
• `A Berlin - Kiel` - Army moves from Berlin to Kiel

*🛡️ Hold Orders:*
• `A Paris H` - Army holds in Paris
• `F London H` - Fleet holds in London

*🤝 Support Orders:*
• `A Marseilles S A Paris - Burgundy` - Army in Marseilles supports move from Paris to Burgundy
• `F Brest S F English Channel - Mid Atlantic` - Fleet in Brest supports fleet move
• `A Munich S A Berlin` - Army in Munich supports hold in Berlin

*🚢 Convoy Orders:*
• `F North Sea C A London - Belgium` - Fleet convoys army from London to Belgium
• `A London - Belgium VIA CONVOY` - Army moves via convoy (requires convoying fleet)

*🏗️ Build Phase Orders:*
• `BUILD A Paris` - Build army in Paris (requires supply center control)
• `BUILD F Brest` - Build fleet in Brest
• `DESTROY A Munich` - Destroy army in Munich (if you have too many units)

*📝 Multiple Orders:*
Separate multiple orders with semicolons:
• `A Paris - Burgundy; F Brest - English Channel; A Marseilles H`

*💡 Common Patterns:*
• **Attack:** `A Vienna - Trieste`
• **Defend:** `A Vienna H`
• **Support Attack:** `A Budapest S A Vienna - Trieste`
• **Support Defense:** `A Budapest S A Vienna`
• **Convoy Attack:** `F North Sea C A London - Belgium` + `A London - Belgium VIA CONVOY`
    """
    await update.message.reply_text(examples_text, parse_mode='Markdown')


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
        [InlineKeyboardButton("🎬 Run Perfect Demo Game", callback_data="run_automated_demo")]
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

