"""
Telegram Diplomacy Bot - Main entry point

This module provides the main entry point for the Telegram bot.
All command handlers are organized in the telegram_bot package.
"""
import asyncio
import logging
import os
import threading
import time
import uvicorn
from datetime import datetime

import requests
from telegram import BotCommand, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Import directly from modules
from server.telegram_bot.config import TELEGRAM_TOKEN, API_URL
from server.telegram_bot.api_client import api_post, api_get, wait_for_api_health, _validate_api_url
from server.telegram_bot.help_text import DEMO_EXAMPLE_ORDERS, DEMO_UNITS, ORDER_FORMAT_NOTES
from server.telegram_bot.maps import send_default_map, send_game_map, map_command, replay
from server.telegram_bot.games import (
    start, register, games, show_available_games, show_power_selection,
    join, quit, replace, wait, status, players, draw, nodraw
)
from server.telegram_bot.orders import (
    order, orders, myorders, clearorders, clear, orderhistory, processturn, viewmap, selectunit,
    show_possible_moves, show_convoy_options, show_convoy_destinations, submit_interactive_order,
    show_my_orders_menu, resolve_pending_order, run_process_turn
)
from server.telegram_bot.messages import message, broadcast, messages, show_messages_menu
from server.telegram_bot.ui import (
    show_main_menu, show_map_menu, show_help, refresh_keyboard, handle_menu_buttons,
    rules, examples
)
from server.telegram_bot.admin import start_demo_game, run_automated_demo, debug_command
from server.telegram_bot.notifications import fastapi_app, notify
from server.telegram_bot.channel_commands import link_channel, unlink_channel, channel_info, channel_settings
from server.telegram_bot.channels import set_telegram_bot
from server.telegram_bot.link_account import link_account

logger = logging.getLogger("diplomacy.telegram_bot.main")

# Registered with Telegram via ``set_my_commands`` (see ``_post_init`` below)
# so they show up in the "/" autocomplete menu -- previously nothing called
# ``set_my_commands`` anywhere in the package, so none of the ~27 commands
# handled below were discoverable unless a player already knew the name.
# Deliberately curated and ordered by usefulness rather than a dump of all
# 27: aliases (``/clear``), admin/debug commands, and rarely-used commands
# (``/orderhistory``, ``/replay``, ``/refresh``, ``/examples``, channel
# management) are left off this menu -- they still work as commands, they're
# just not advertised here.
BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Welcome message and main menu"),
    BotCommand("register", "Register yourself with the bot"),
    BotCommand("help", "Show all available commands"),
    BotCommand("games", "List the games you are in"),
    BotCommand("join", "Join a game"),
    BotCommand("status", "Phase, deadline, and who has submitted orders"),
    BotCommand("players", "List players in a game and their powers"),
    BotCommand("selectunit", "Interactive order entry"),
    BotCommand("order", "Submit orders, e.g. A PAR - BUR"),
    BotCommand("myorders", "Show your submitted orders"),
    BotCommand("clearorders", "Clear your submitted orders"),
    BotCommand("processturn", "Adjudicate the current phase"),
    BotCommand("draw", "Vote yes to end the game as a draw"),
    BotCommand("nodraw", "Withdraw a draw vote you cast"),
    BotCommand("viewmap", "View the current game map"),
    BotCommand("message", "Send a private message to a power"),
    BotCommand("broadcast", "Message all players in a game"),
    BotCommand("messages", "View messages for a game"),
    BotCommand("wait", "Join the waiting list for auto-matching"),
    BotCommand("quit", "Leave a game"),
    BotCommand("link", "Link this Telegram account to a browser account"),
    BotCommand("rules", "Basic Diplomacy rules and order syntax"),
]


async def _post_init(app: Application) -> None:
    """Register ``BOT_COMMANDS`` with Telegram so the "/" menu is populated.

    Runs once during ``Application.initialize()`` -- wired in via
    ``ApplicationBuilder().post_init(_post_init)`` in ``main()`` below.
    """
    await app.bot.set_my_commands(BOT_COMMANDS)


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
        except requests.HTTPError as e:
            hint = ""
            if getattr(e, "response", None) is not None and e.response.status_code == 401:
                hint = "\n\n💡 Try /register first."
            await query.edit_message_text(f"❌ Failed to join: {str(e)}{hint}")
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
        await query.edit_message_text("🗺️ Fetching standard Diplomacy map...")
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
    
    elif data.startswith("vote_proposal_"):
        # Handle proposal voting: vote_proposal_<game_id>_<vote_type>
        parts = data.split("_")
        if len(parts) >= 4:
            game_id = parts[2]
            vote_type = parts[3]  # support, oppose, undecided
            
            # Acknowledge vote
            vote_emoji = {"support": "👍", "oppose": "👎", "undecided": "🤔"}.get(vote_type, "✅")
            await query.answer(f"Voted {vote_emoji} on proposal")
            
            # Update message with vote count (simplified - will be enhanced with database)
            try:
                # Extract current vote counts if present
                # For now, just acknowledge the vote
                # Full implementation will track votes in database
                await query.edit_message_reply_markup(reply_markup=query.message.reply_markup)
            except Exception as e:
                logger.warning(f"Error updating vote: {e}")

    elif data.startswith("demo_orders_"):
        game_id = data.split("_")[2]
        await query.edit_message_text(f"📋 Demo Orders for Game {game_id}\n\nUse /orders {game_id} <your orders> to submit moves for Germany!\n\n💡 Try /selectunit for interactive order selection!")

    elif data.startswith("demo_help_"):
        game_id = data.split("_")[2]
        help_text = (
            f"ℹ️ *Demo Game Help* (ID: {game_id})\n\n"
            "🇩🇪 *You are Germany* - You control:\n"
            f"{DEMO_UNITS}\n\n"
            f"*Example Orders:* (prefix each with `/orders {game_id}`)\n"
            f"{DEMO_EXAMPLE_ORDERS}\n\n"
            f"{ORDER_FORMAT_NOTES}\n\n"
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

    # Interactive Order Input Callbacks -- "|"-delimited, distinct from the
    # "_"-delimited legacy prefixes above. Order text itself is never carried
    # in callback_data (Telegram's 64-byte cap); "ord|" carries only an index
    # into the per-game cache orders.py populated in context.user_data.
    elif data.startswith("selunit|"):
        _, game_id, unit_key = data.split("|", 2)
        await show_possible_moves(query, context, game_id, unit_key)

    elif data.startswith("cvopt|"):
        _, game_id, unit_key = data.split("|", 2)
        await show_convoy_options(query, context, game_id, unit_key)

    elif data.startswith("cvorig|"):
        _, game_id, unit_key, origin = data.split("|", 3)
        await show_convoy_destinations(query, context, game_id, unit_key, origin)

    elif data.startswith("ord|"):
        _, game_id, idx_str = data.split("|", 2)
        try:
            order_text = resolve_pending_order(context, game_id, int(idx_str))
        except ValueError:
            order_text = None
        if order_text is None:
            await query.edit_message_text(
                "⚠️ This order selection has expired. Please run /selectunit again."
            )
        else:
            await submit_interactive_order(query, game_id, order_text)

    elif data.startswith("cancelunit|"):
        _, game_id = data.split("|", 1)
        context.user_data.get("pending_orders", {}).pop(game_id, None)
        await query.edit_message_text(f"❌ Selection cancelled for game {game_id}.")

    # /processturn confirmation gate (E3e): "ptforce|" runs the same
    # adjudication + summary /processturn would have run directly had every
    # power already submitted; "ptcancel|" just backs out.
    elif data.startswith("ptforce|"):
        _, game_id = data.split("|", 1)

        async def _edit(text: str, reply_markup=None, parse_mode=None) -> None:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

        await run_process_turn(_edit, game_id)

    elif data.startswith("ptcancel|"):
        _, game_id = data.split("|", 1)
        await query.edit_message_text(
            f"❌ Process turn cancelled for game {game_id}. No orders were changed."
        )

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
            api_post("/games/set_orders", {
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

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(_post_init).build()
    
    # Set telegram bot instance for channel posting
    set_telegram_bot(app.bot)

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("nodraw", nodraw))
    app.add_handler(CommandHandler("quit", quit))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("processturn", processturn))
    app.add_handler(CommandHandler("viewmap", viewmap))
    app.add_handler(CommandHandler("selectunit", selectunit))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("clearorders", clearorders))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("orderhistory", orderhistory))
    app.add_handler(CommandHandler("message", message))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("messages", messages))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(CommandHandler("replay", replay))
    app.add_handler(CommandHandler("replace", replace))
    app.add_handler(CommandHandler("wait", wait))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("refresh", refresh_keyboard))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("examples", examples))
    app.add_handler(CommandHandler("link", link_account))
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

    def start_notify_server():
        """Start the notification API server in a separate thread."""
        try:
            # Bind loopback-only by default: the API's NOTIFY_URL default is
            # http://localhost:8081/notify (server/api/shared.py), both systemd units
            # (diplomacy-api, diplomacy-bot) run on the same EC2 host, and the /notify
            # endpoint (notifications.py) has no auth -- unlike _api_module.py (behind
            # nginx) and daide/server.py (needs external DAIDE clients), this one has no
            # reason to accept connections from outside the host. Override via env if a
            # future deployment genuinely splits the two processes across hosts.
            notify_host = os.environ.get("DIPLOMACY_NOTIFY_HOST", "127.0.0.1")
            uvicorn.run(fastapi_app, host=notify_host, port=8081, log_level="info")
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.warning(f"Port 8081 already in use, notification server not started: {e}")
                logger.info("Notification endpoint may be available on main API server")
            else:
                logger.error(f"Failed to start notification server: {e}")
                raise

    def run_bot():
        """Run the telegram bot with proper error handling."""
        # Ensure we have a fresh event loop before starting
        # This prevents issues when restarting the service where a closed loop might exist
        # run_polling() will create its own loop, but it fails if a closed loop is already set
        try:
            # Check if there's a running loop (shouldn't be in this context)
            asyncio.get_running_loop()
            logger.warning("Event loop is already running, this shouldn't happen")
        except RuntimeError:
            # No running loop, which is expected. Check if there's a closed loop set
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    logger.info("Found closed event loop, replacing with a fresh one")
                    asyncio.set_event_loop(asyncio.new_event_loop())
            except RuntimeError:
                # No event loop is set, which is fine - run_polling() will create one
                pass
        
        try:
            # Use close_loop=False to prevent event loop closure issues during shutdown
            app.run_polling(close_loop=False)
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                logger.warning("Event loop was closed during shutdown, attempting to recover")
                # Try to create a fresh loop and retry once
                try:
                    logger.info("Creating a fresh event loop and retrying")
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    app.run_polling(close_loop=False)
                except Exception as retry_e:
                    logger.error(f"Failed to recover after event loop closure: {retry_e}")
                    return
            else:
                logger.error(f"RuntimeError during bot execution: {e}")
                raise
        except KeyboardInterrupt:
            logger.info("Bot stopped by keyboard interrupt")
        except Exception as e:
            logger.error(f"Unexpected error during bot execution: {e}")
            raise

    if bot_only:
        # BOT_ONLY mode: Run telegram bot + notification API (main API runs separately)
        print("Starting in BOT_ONLY mode")

        notify_thread = threading.Thread(target=start_notify_server, daemon=True)
        notify_thread.start()

        # Wait a bit for the server to start
        time.sleep(2)

        # Start telegram bot polling - this will block
        run_bot()
    else:
        # When BOT_ONLY=false, main API is running separately
        # Only start notification server if explicitly requested
        start_notify = os.environ.get("START_NOTIFY_SERVER", "false").lower() == "true"
        
        if start_notify:
            print("Starting in standalone mode with notification server")
            # Start notification server in background thread
            notify_thread = threading.Thread(target=start_notify_server, daemon=True)
            notify_thread.start()
            # Wait a bit for the server to start
            time.sleep(2)
        else:
            print("Starting in standalone mode (notification server disabled - main API handles notifications)")
            logger.info("Notification server not started (main API should handle /notify endpoint)")

        # Start telegram bot polling in main thread - this will block
        print("Starting Telegram bot polling...")
        run_bot()


if __name__ == "__main__":
    main()
