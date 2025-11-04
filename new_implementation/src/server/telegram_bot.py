"""
Telegram Diplomacy Bot - Main entry point

This module provides the main entry point for the Telegram bot.
All command handlers are organized in the telegram_bot package.
"""
import logging
import os
import threading
import time
import uvicorn
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Import directly from modules
from server.telegram_bot.config import TELEGRAM_TOKEN, API_URL, get_telegram_token
from server.telegram_bot.api_client import api_post, api_get, wait_for_api_health, _validate_api_url
from server.telegram_bot.maps import (
    get_cached_default_map, set_cached_default_map, generate_default_map,
    send_default_map, send_game_map, send_demo_map, map_command, replay, refresh_map_cache
)
from server.telegram_bot.games import (
    start, register, games, show_available_games, show_power_selection,
    join, quit, replace, wait
)
from server.telegram_bot.orders import (
    order, orders, myorders, clearorders, orderhistory, processturn, viewmap, selectunit,
    show_possible_moves, show_convoy_options, show_convoy_destinations, submit_interactive_order,
    show_my_orders_menu
)
from server.telegram_bot.messages import message, broadcast, messages, show_messages_menu
from server.telegram_bot.ui import (
    show_main_menu, show_map_menu, show_help, show_admin_menu, refresh_keyboard, handle_menu_buttons
)
from server.telegram_bot.admin import start_demo_game, run_automated_demo, debug_command
from server.telegram_bot.notifications import fastapi_app, notify
from server.telegram_bot.channel_commands import link_channel, unlink_channel, channel_info, channel_settings
from server.telegram_bot.channels import set_telegram_bot

logger = logging.getLogger("diplomacy.telegram_bot.main")


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
        await show_available_games(update, context)

    elif data.startswith("orders_menu_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]

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
        await query.edit_message_text("🎬 Starting perfect demo game...")
        await run_automated_demo(update, context)

    elif data == "back_to_main_menu":
        await show_main_menu(update, context)

    elif data == "show_games_list":
        await show_available_games(update, context)

    elif data == "join_waiting_list":
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
            f"• `/orders {game_id} A Berlin - Kiel`\n"
            f"• `/orders {game_id} A Munich - Bohemia`\n"
            f"• `/orders {game_id} F Kiel - Denmark`\n"
            f"• `/orders {game_id} A Berlin H` (Hold)\n"
            f"• `/orders {game_id} A Berlin S A Munich - Kiel` (Support)\n"
            f"• `/orders {game_id} F Kiel C A Berlin - Denmark` (Convoy)\n\n"
            "*📝 Order Format:*\n"
            "• Use abbreviations: `A`, `F`, `H`, `S`, `C`\n"
            "• Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`\n"
            "• **Don't mix:** `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅\n\n"
            "*Interactive Commands:*\n"
            f"• `/selectunit` - Choose units and orders interactively\n"
            f"• `/processturn {game_id}` - Process the current turn\n"
            f"• `/viewmap {game_id}` - View current game state\n\n"
            "🤖 *Other powers won't move* - they're AI-controlled\n"
            "🗺️ Use 'View Map' to see the current state"
        )
        await query.edit_message_text(help_text, parse_mode='Markdown')

    elif data == "admin_delete_all_games":
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return

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
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return

        try:
            result = api_post("/admin/delete_all_games", {})
            message = (
                "✅ *All games deleted successfully!*\n\n"
                f"🗑️ Result: {result.get('message', 'Games deleted')}\n"
                f"📊 Games deleted: {result.get('deleted_count', 'Unknown')}"
            )
            await query.edit_message_text(message, parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Error deleting games: {str(e)}")

    elif data == "admin_cancel_delete":
        await query.edit_message_text("❌ Delete operation cancelled.")

    elif data == "admin_recreate_admin_user":
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return

        try:
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
        if str(query.from_user.id) != "8019538":
            await query.edit_message_text("❌ Access denied. Admin privileges required.")
            return

        try:
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
        await show_my_orders_menu(update, context)

    elif data == "show_map_menu":
        await show_map_menu(update, context)

    elif data == "show_messages_menu":
        await show_messages_menu(update, context)

    elif data.startswith("view_messages_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"💬 Loading messages for Game {game_id}...\n\nUse `/messages {game_id}` to view messages or `/message {game_id} <power> <text>` to send a message.")

    elif data.startswith("submit_orders_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]
        await query.edit_message_text(f"🎯 Starting interactive order selection for Game {game_id} ({power})...")
        await selectunit(update, context)

    # Interactive Order Input Callbacks
    elif data.startswith("select_unit_"):
        parts = data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"
        await show_possible_moves(query, game_id, unit)

    elif data.startswith("cancel_unit_selection_"):
        game_id = data.split("_")[3]
        await query.edit_message_text(f"❌ Unit selection cancelled for game {game_id}")

    elif data.startswith("move_unit_"):
        parts = data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"
        move_type = parts[5]

        if move_type == "hold":
            await submit_interactive_order(query, game_id, f"{unit} H")
        elif move_type == "move":
            target_province = parts[6]
            await submit_interactive_order(query, game_id, f"{unit} - {target_province}")
        elif move_type == "support":
            await query.edit_message_text(
                f"🔄 Support orders are now fully implemented!\n\n"
                f"Use `/orders <game_id> {unit} S <unit to support>` for support orders.\n\n"
                f"💡 Example: `/orders 123 A Berlin S A Munich - Kiel`"
            )
        elif move_type == "convoy":
            await show_convoy_options(query, game_id, unit)

    elif data.startswith("cancel_move_selection_"):
        game_id = data.split("_")[3]
        await query.edit_message_text(f"❌ Move selection cancelled for game {game_id}")

    elif data.startswith("convoy_select_"):
        parts = data.split("_")
        game_id = parts[2]
        fleet_unit = f"{parts[3]} {parts[4]}"
        army_power = parts[5]
        army_unit = f"{parts[6]} {parts[7]}"
        await show_convoy_destinations(query, game_id, fleet_unit, army_power, army_unit)

    elif data.startswith("convoy_dest_"):
        parts = data.split("_")
        game_id = parts[2]
        fleet_unit = f"{parts[3]} {parts[4]}"
        army_power = parts[5]
        army_unit = f"{parts[6]} {parts[7]}"
        destination = parts[8]
        convoy_order = f"{fleet_unit} C {army_power} {army_unit} - {destination}"
        await submit_interactive_order(query, game_id, convoy_order)

    elif data.startswith("view_orders_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]

        try:
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
        game_id = data.split("_")[2]

        try:
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

                full_text = "\n".join(lines)
                if len(full_text) > 4000:
                    full_text = full_text[:3900] + "\n\n... (truncated)"

                await query.edit_message_text(full_text, parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Error retrieving order history: {e}")

    elif data.startswith("clear_orders_"):
        parts = data.split("_")
        game_id = parts[2]
        power = parts[3]

        try:
            api_post(f"/games/set_orders", {
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


def main():
    """Main entry point for the Telegram bot."""
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Validate and wait for API health before starting the bot
    try:
        _validate_api_url(API_URL)
        wait_for_api_health()
    except Exception as e:
        print(f"Error: API health check failed: {e}")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Set telegram bot instance for channel posting
    set_telegram_bot(app.bot)

    # Register command handlers
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
    app.add_handler(CommandHandler("link_channel", link_channel))
    app.add_handler(CommandHandler("unlink_channel", unlink_channel))
    app.add_handler(CommandHandler("channel_info", channel_info))
    app.add_handler(CommandHandler("channel_settings", channel_settings))

    # Add handlers for interactive features
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons))

    # Attach the running app to the notify endpoint for access
    notify.telegram_app = app

    # Enhanced debugging for container environment
    logging.basicConfig(level=logging.INFO, force=True)

    # Log all environment variables for debugging
    logger.info("=== TELEGRAM BOT STARTUP DEBUG ===")
    logger.info(f"All environment variables containing 'BOT': "
                f"{[(k, v) for k, v in os.environ.items() if 'BOT' in k.upper()]}")

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

    def start_notify_server():
        """Start the notification API server in a separate thread."""
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8081, log_level="info")

    if bot_only:
        # BOT_ONLY mode: Run telegram bot + notification API (main API runs separately)
        print("Starting in BOT_ONLY mode")

        notify_thread = threading.Thread(target=start_notify_server, daemon=True)
        notify_thread.start()

        # Wait a bit for the server to start
        time.sleep(2)

        # Start telegram bot polling - this will block
        app.run_polling()
    else:
        # Legacy/standalone mode: Use thread-based approach to avoid event loop conflicts
        print("Starting in standalone mode with thread-based approach")

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
