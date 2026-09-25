"""
Telegram Diplomacy Bot - Main entry point

This module provides the main entry point for the Telegram bot.
All command handlers are organized in the telegram_bot package.
"""
import asyncio
import logging
import sys

from telegram import BotCommand, BotCommandScopeAllGroupChats, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, ApplicationHandlerStop, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

# Import directly from modules
from server.telegram_bot.config import TELEGRAM_TOKEN, API_URL
from server.telegram_bot.api_client import (
    wait_for_api_health, _validate_api_url,
)
from server.telegram_bot.help_text import DEMO_EXAMPLE_ORDERS, DEMO_UNITS, ORDER_FORMAT_NOTES
from server.telegram_bot.maps import send_default_map, send_game_map, map_command, replay
from server.telegram_bot.games import (
    start, register, show_power_selection, join, join_from_button,
    quit, replace, wait, leave_waiting_list, status, players, draw, nodraw, deadline, dummy,
    ready, notready, autoprocess,
)
from server.telegram_bot.hub import (
    cancel, find_game, game_command, games, games_list_callback, handle_game_callback,
)
from server.telegram_bot.orders import (
    order, orders, myorders, clearorders, clear, orderhistory, processturn, viewmap, selectunit,
    show_possible_moves, show_convoy_options, show_convoy_destinations,
    show_support_options, show_support_choices, submit_interactive_order,
    resolve_pending_order, run_process_turn,
    orderall, active_walk, record_walk_choice, show_walk_step, handle_walk_action
)
from server.telegram_bot.messages import message, broadcast, messages
from server.telegram_bot.ui import (
    show_main_menu, show_help, refresh_keyboard, handle_menu_buttons,
    rules, examples
)
from server.telegram_bot.admin import start_demo_game, debug_command
from server.telegram_bot.notifications import (
    queue_status, start_background_loops, stop_background_loops,
)
from server.telegram_bot.channel_commands import (
    link_channel, unlink_channel, channel_info, channel_settings, newgame, linkgroup, unlinkgroup,
)
from server.telegram_bot.link_account import link_account

logger = logging.getLogger("diplomacy.telegram_bot.main")

# Registered with Telegram via ``set_my_commands`` (see ``_post_init`` below)
# so they show up in the "/" autocomplete menu. Curated and ordered by
# usefulness, not a dump of every handler: most actions are buttons in the
# game menu (/game), so the menu lists the commands worth typing. Left off,
# but still working: aliases (/order, /clear, /wait, /unwait), /register
# (/start registers), /processturn (the game creator's "Process turn now"
# button), game-creator settings (/dummy, /autoprocess), rarely used commands
# (/orderhistory, /replay, /refresh, /examples, /cancel, /players, /replace)
# and admin/channel commands.
BOT_COMMANDS: list[BotCommand] = [
    BotCommand("start", "Main menu"),
    BotCommand("games", "Your games"),
    BotCommand("game", "Open a game's menu: /game [id]"),
    BotCommand("orderall", "Order all your units, one by one"),
    BotCommand("selectunit", "Order a single unit"),
    BotCommand("orders", "Type orders, e.g. /orders A PAR - BUR"),
    BotCommand("myorders", "Show your orders this turn"),
    BotCommand("status", "Phase, deadline, and who has ordered"),
    BotCommand("viewmap", "The current map"),
    BotCommand("messages", "Messages in your game"),
    BotCommand("message", "Message a power: /message FRANCE hello"),
    BotCommand("broadcast", "Message every player"),
    BotCommand("notready", "Ask the table to wait before auto-processing"),
    BotCommand("ready", "Stop waiting; let the turn auto-process"),
    BotCommand("deadline", "Show or change a game's deadline"),
    BotCommand("draw", "Vote to end the game as a draw"),
    BotCommand("nodraw", "Withdraw your draw vote"),
    BotCommand("findgame", "Open games, the queue, and the demo"),
    BotCommand("join", "Join a game: /join <id> [power]"),
    BotCommand("leavequeue", "Leave the queue for a new game"),
    BotCommand("quit", "Leave a game"),
    BotCommand("queue", "Orders/messages waiting for the game server"),
    BotCommand("link", "Link this Telegram account to a browser account"),
    BotCommand("help", "Commands and how to write orders"),
    BotCommand("rules", "Basic Diplomacy rules and order syntax"),
]


# The "/" menu inside a group: only what belongs there. Everything else is
# refused in groups (``group_command_guard``).
GROUP_BOT_COMMANDS: list[BotCommand] = [
    BotCommand("newgame", "Start a game for this group"),
    BotCommand("linkgroup", "Attach one of your games to this group"),
    BotCommand("unlinkgroup", "Detach a game from this group"),
    BotCommand("status", "A game's phase and who has ordered"),
    BotCommand("viewmap", "A game's current map"),
    BotCommand("help", "How playing in a group works"),
]

GROUP_CHAT_TYPES = ("group", "supergroup", "channel")

# Commands that make sense in a group chat. Orders, messages, joining and the
# game menu are private: in a group, everyone would see them (and press their
# buttons).
GROUP_COMMANDS = {
    "start", "help", "rules", "examples", "newgame", "linkgroup", "unlinkgroup",
    "status", "viewmap", "map", "players",
    "link_channel", "unlink_channel", "channel_info", "channel_settings",
}


async def group_command_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs before every command handler (handler group -1). In a group chat a
    private command gets a pointer to a private chat instead of an answer."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None or chat.type not in GROUP_CHAT_TYPES or not message.text:
        return
    command = message.text.split()[0][1:].split("@", 1)[0].lower()
    if command in GROUP_COMMANDS:
        if command == "help":
            await start(update, context)  # the group explanation
            raise ApplicationHandlerStop
        return
    await message.reply_text(
        f"🤫 /{command} is private -- in a group, everyone would see it. Send it to me in a private chat.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(
            "💬 Open a private chat", url=f"https://t.me/{context.bot.username}?start=group"
        )]]),
    )
    raise ApplicationHandlerStop


async def _post_init(app: Application) -> None:
    """Register ``BOT_COMMANDS`` with Telegram and start the background loops.

    Runs once during ``Application.initialize()`` -- wired in via
    ``ApplicationBuilder().post_init(_post_init)`` in ``main()`` below. The
    loops (``notifications.py``) are what deliver server notifications to
    players and replay the durable outbox; they need the running event loop,
    which is why they start here and not in ``main()``.
    """
    await app.bot.set_my_commands(BOT_COMMANDS)
    await app.bot.set_my_commands(GROUP_BOT_COMMANDS, scope=BotCommandScopeAllGroupChats())
    start_background_loops(app)


async def _post_shutdown(app: Application) -> None:
    await stop_background_loops(app)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks from inline keyboards"""
    query = update.callback_query
    chat = query.message.chat if query.message is not None else None
    if chat is not None and chat.type in GROUP_CHAT_TYPES:
        # Nothing the bot posts in a group has callback buttons (only links to a
        # private chat); a button pressed there is one someone forwarded.
        await query.answer("Use me in a private chat -- in a group, everyone sees it.", show_alert=True)
        return
    await query.answer()  # Acknowledge the callback

    data = query.data
    user_id = str(query.from_user.id)

    if data.startswith("g|"):
        await handle_game_callback(query, context, data)

    elif data.startswith("select_game_"):
        game_id = data.split("_")[2]
        await show_power_selection(update, game_id)

    elif data.startswith("join_game_"):
        parts = data.split("_")
        await join_from_button(query, context, parts[2], parts[3])

    elif data in ("back_to_games", "show_games_list", "find_game"):
        await find_game(update, context)

    elif data in ("my_games", "show_orders_menu", "retry_orders_menu", "show_map_menu",
                  "show_messages_menu", "back_to_orders_menu"):
        # The last four are buttons of the pre-game-menu screens, still under
        # old messages in players' chats: they all lead to the games list now.
        await games_list_callback(query)

    elif data.startswith(("orders_menu_", "submit_orders_", "view_messages_")):
        # Old per-game menu buttons (``orders_menu_{game}_{power}`` ...): the game menu.
        await handle_game_callback(query, context, f"g|{data.split('_')[2]}|hub")

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

    elif data == "back_to_main_menu":
        await show_main_menu(update, context)

    elif data == "join_waiting_list":
        await wait(update, context)
    
    elif data.startswith("demo_orders_"):
        # Buttons under demo games started before the game menu existed.
        await handle_game_callback(query, context, f"g|{data.split('_')[2]}|all")

    elif data.startswith("demo_help_"):
        game_id = data.split("_")[2]
        help_text = (
            f"ℹ️ *Demo Game Help* (ID: {game_id})\n\n"
            "🇩🇪 *You are Germany* - You control:\n"
            f"{DEMO_UNITS}\n\n"
            f"*Example Orders:* (prefix each with `/orders`)\n"
            f"{DEMO_EXAMPLE_ORDERS}\n\n"
            f"{ORDER_FORMAT_NOTES}\n\n"
            "🤖 The other six powers are played by a simple computer player.\n"
            "⚡ The turn is processed as soon as all your units have orders."
        )
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Game menu", callback_data=f"g|{game_id}|hub")]]),
            parse_mode='Markdown',
        )

    # Interactive Order Input Callbacks -- "|"-delimited, distinct from the
    # "_"-delimited legacy prefixes above. Order text itself is never carried
    # in callback_data (Telegram's 64-byte cap); "ord|{game}|{menu}|{idx}" names
    # the menu and an index into it (orders.order_buttons). A button from any
    # menu but the game's newest one has expired.
    elif data.startswith("selunit|"):
        _, game_id, unit_key = data.split("|", 2)
        await show_possible_moves(query, context, game_id, unit_key)

    elif data.startswith("supopt|"):
        _, game_id, unit_key = data.split("|", 2)
        await show_support_options(query, context, game_id, unit_key)

    elif data.startswith("suporig|"):
        _, game_id, unit_key, target = data.split("|", 3)
        await show_support_choices(query, context, game_id, unit_key, target)

    elif data.startswith("cvopt|"):
        _, game_id, unit_key = data.split("|", 2)
        await show_convoy_options(query, context, game_id, unit_key)

    elif data.startswith("cvorig|"):
        _, game_id, unit_key, origin = data.split("|", 3)
        await show_convoy_destinations(query, context, game_id, unit_key, origin)

    elif data.startswith("ord|"):
        parts = data.split("|")
        game_id = parts[1]
        try:
            # A three-part "ord|{game}|{idx}" is from before menus were named:
            # it cannot be matched to a menu, so it has expired too.
            order_text = (
                resolve_pending_order(context, game_id, int(parts[2]), int(parts[3]))
                if len(parts) == 4
                else None
            )
        except ValueError:
            order_text = None
        if order_text is None:
            await query.edit_message_text(
                "⚠️ This order selection has expired. Open the game again with /game."
            )
        elif active_walk(context, game_id) is not None:
            # /orderall (Z2): remember this unit's order and show the next one;
            # everything is submitted together from the summary.
            record_walk_choice(context, game_id, order_text)

            async def send_step(text: str, reply_markup=None) -> None:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

            await show_walk_step(send_step, context, game_id)
        else:
            await submit_interactive_order(query, game_id, order_text)

    elif data.startswith("wlk|"):
        _, game_id, action = data.split("|", 2)
        await handle_walk_action(query, context, game_id, action)

    elif data.startswith("cancelunit|"):
        _, game_id = data.split("|", 1)
        context.user_data.get("pending_orders", {}).pop(game_id, None)
        context.user_data.get("order_walk", {}).pop(game_id, None)
        await query.edit_message_text(f"❌ Selection cancelled for game {game_id}.")

    # /processturn confirmation gate (E3e): "ptforce|" runs the same
    # adjudication + summary /processturn would have run directly had every
    # power already submitted; "ptcancel|" just backs out.
    elif data.startswith("ptforce|"):
        _, game_id = data.split("|", 1)

        async def _edit(text: str, reply_markup=None, parse_mode=None) -> None:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

        await run_process_turn(_edit, game_id, user_id)

    elif data.startswith("ptcancel|"):
        _, game_id = data.split("|", 1)
        await query.edit_message_text(
            f"❌ Process turn cancelled for game {game_id}. No orders were changed."
        )

    elif data.startswith("view_orders_"):
        # Old per-game menu buttons: the game menu's own screens replace them.
        await handle_game_callback(query, context, f"g|{data.split('_')[2]}|view")

    elif data.startswith("clear_orders_"):
        await handle_game_callback(query, context, f"g|{data.split('_')[2]}|clr")

    elif data.startswith("order_history_"):
        await handle_game_callback(query, context, f"g|{data.split('_')[2]}|hist")


def main():
    """Main entry point for the Telegram bot.

    The bot must come up -- and stay up -- whether or not the API is reachable.
    The API is a separate container that restarts on every deploy; if the bot
    refused to start until the API answered, an API outage at the wrong moment
    would take the bot down too and nothing would queue anything. So the
    startup health check is informational: it logs, and the bot starts
    regardless. Reads fail with a clear message until the link returns;
    writes go to the durable outbox and are delivered when it does.
    """
    if not TELEGRAM_TOKEN:
        sys.exit("Error: TELEGRAM_BOT_TOKEN environment variable not set.")

    try:
        _validate_api_url(API_URL)
    except ValueError as e:
        sys.exit(f"Error: {e}")
    try:
        wait_for_api_health(max_attempts=3)
    except RuntimeError as e:
        logger.warning("API not reachable at startup (%s); starting anyway and queuing writes", e)

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # Register command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(MessageHandler(filters.COMMAND & ~filters.ChatType.PRIVATE, group_command_guard), group=-1)
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("linkgroup", linkgroup))
    app.add_handler(CommandHandler("unlinkgroup", unlinkgroup))
    app.add_handler(CommandHandler("games", games))
    app.add_handler(CommandHandler("game", game_command))
    app.add_handler(CommandHandler("findgame", find_game))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("players", players))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CommandHandler("nodraw", nodraw))
    app.add_handler(CommandHandler("quit", quit))
    app.add_handler(CommandHandler("orders", orders))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("processturn", processturn))
    app.add_handler(CommandHandler("deadline", deadline))
    app.add_handler(CommandHandler("dummy", dummy))
    app.add_handler(CommandHandler("orderall", orderall))
    app.add_handler(CommandHandler("autoprocess", autoprocess))
    app.add_handler(CommandHandler("notready", notready))
    app.add_handler(CommandHandler("ready", ready))
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
    app.add_handler(CommandHandler("unwait", leave_waiting_list))
    app.add_handler(CommandHandler("leavequeue", leave_waiting_list))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(CommandHandler("refresh", refresh_keyboard))
    app.add_handler(CommandHandler("help", show_help))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("examples", examples))
    app.add_handler(CommandHandler("link", link_account))
    app.add_handler(CommandHandler("queue", queue_status))
    app.add_handler(CommandHandler("link_channel", link_channel))
    app.add_handler(CommandHandler("unlink_channel", unlink_channel))
    app.add_handler(CommandHandler("channel_info", channel_info))
    app.add_handler(CommandHandler("channel_settings", channel_settings))

    # Add handlers for interactive features
    app.add_handler(CallbackQueryHandler(button_callback))
    # Private chats only: the bot also sits in linked game channels (groups),
    # where other people's chatter is not addressed to it.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_menu_buttons))

    logging.basicConfig(level=logging.INFO, force=True)
    # httpx logs the full request URL at INFO, and python-telegram-bot's
    # base URL embeds the bot token (https://api.telegram.org/bot<token>/...) --
    # left at INFO this prints the live token on every API call.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger.info("Diplomacy bot starting; API at %s", API_URL)

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

    print("Starting Telegram bot polling...")
    run_bot()

if __name__ == "__main__":
    main()
