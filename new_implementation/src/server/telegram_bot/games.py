"""
Game management commands for the Telegram bot.
"""
import logging
import random
from typing import List, Optional, Tuple

import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from .game_context import GameContextError, fetch_user_games, resolve_game_and_power
from .utils import escape_markdown

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
    """Handle /register command - register user with the bot.

    The API call and the confirmation reply are two separate try blocks on
    purpose. ``full_name`` comes straight from the user's Telegram profile
    (below) and is sent with ``parse_mode='Markdown'`` -- an unescaped ``_``,
    ``*``, `` ` `` or ``[`` in it makes Telegram reject *this* message only.
    If that reply failed while wrapped in the same try/except as the API
    call, the player would see "Registration error" even though the server
    had already registered them. Escaping ``full_name`` below fixes the
    common case; splitting the try blocks means any other reply failure
    (e.g. a transient Telegram API hiccup) can no longer misreport a
    successful registration as failed.
    """
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
    except Exception as e:
        await update.message.reply_text(f"Registration error: {e}")
        return

    if result.get("status") != "ok":
        await update.message.reply_text(f"Registration error: {result.get('message', 'Unknown error')}")
        return

    try:
        await update.message.reply_text(
            f"✅ *Registration Successful!*\n\n"
            f"Welcome, {escape_markdown(full_name)}!\n\n"
            f"🎮 You can now:\n"
            f"• Join games with /join\n"
            f"• View available games with /games\n"
            f"• Join the waiting list with /wait",
            parse_mode='Markdown'
        )
    except Exception as e:
        # Registration itself already succeeded (checked above) -- don't
        # send a message claiming otherwise just because the confirmation
        # reply happened to fail.
        logger.warning(f"Registration succeeded for telegram_id={user_id} but confirmation reply failed: {e}")


async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /games command - list user's active games."""
    user = update.effective_user
    if not user or not update.message:
        return
    user_id = str(user.id)
    try:
        games_list = fetch_user_games(user_id)

        if not games_list:
            keyboard = [
                [InlineKeyboardButton("🎲 Browse Available Games", callback_data="show_games_list")],
                [InlineKeyboardButton("⏳ Join Waiting List", callback_data="join_waiting_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🎮 *No Active Games*\n\n"
                "You're not currently in any games!\n\n"
                "💡 *Get started:*\n"
                "🎲 Browse available games\n"
                "⏳ Join the waiting list for auto-matching",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        # Format games with better information
        lines = [f"🎮 *Your Active Games* ({len(games_list)})\n"]
        for g in games_list:
            game_id = g.get('game_id', 'Unknown')
            power = g.get('power', 'Unknown')
            state = g.get('status', 'Unknown')
            turn = g.get('current_turn', 'N/A')
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

    except Exception:
        keyboard = [
            [InlineKeyboardButton("🎲 Browse Games", callback_data="show_games_list")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "⚠️ *Can't Load Your Games*\n\n"
            "🔧 Unable to retrieve your game status.\n"
            "This is usually temporary.\n\n"
            "💡 *Try:*\n"
            "🎲 Browse available games\n"
            "🏠 Return to main menu",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command - get current game phase, deadline, and per-power
    order submission state (via ``GET /games/{id}/orders_status``; ``GET
    /games/{id}/orders`` only returns the caller's own power, so it can't answer
    "who has submitted")."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Status command failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving status: {e}")
        return

    try:
        view = api_get(f"/games/{game_id}/state")
    except Exception as e:
        await update.message.reply_text(f"Could not retrieve status for game {game_id}: {e}")
        return

    status_text = (
        f"📊 *Game {game_id} Status*\n\n"
        f"🎯 **You are:** {power}\n"
        f"📅 **Turn:** {view.get('year')} {view.get('season')}\n"
        f"🔄 **Phase:** {view.get('phase_type')}\n"
        f"📝 **Phase Code:** {view.get('phase')}\n"
    )

    try:
        deadline_data = api_get(f"/games/{game_id}/deadline")
        deadline = deadline_data.get("deadline") if deadline_data else None
    except Exception:
        deadline = None
    if deadline:
        status_text += f"⏰ **Deadline:** {deadline}\n"

    try:
        orders_status = api_get(f"/games/{game_id}/orders_status", telegram_id=user_id)
    except Exception:
        orders_status = None
    if orders_status:
        submitted = orders_status.get("submitted", [])
        missing = orders_status.get("missing", [])
        status_text += (
            "\n✅ **Submitted:** " + (", ".join(submitted) if submitted else "none") + "\n"
        )
        if missing:
            status_text += "⏳ **Waiting on:** " + ", ".join(missing) + "\n"

    try:
        draw_status = api_get(f"/games/{game_id}/draw_vote_status")
    except Exception:
        draw_status = None
    if draw_status:
        draw_votes = draw_status.get("votes", [])
        draw_required = draw_status.get("required", [])
        if draw_required:
            status_text += (
                f"\n🕊️ **Draw vote:** {len(draw_votes)}/{len(draw_required)} voted for draw"
            )
            if draw_votes:
                status_text += " (" + ", ".join(draw_votes) + ")"
            status_text += "\n"

    await update.message.reply_text(status_text, parse_mode='Markdown')


async def _cast_draw_vote(update: Update, context: ContextTypes.DEFAULT_TYPE, vote: bool) -> None:
    """Shared implementation for ``/draw`` (cast a yes vote) and ``/nodraw``
    (withdraw a previously cast yes vote), via ``POST /games/{id}/draw_vote``.

    Thin client: all quorum logic (who counts, when the game ends) lives in
    ``GameService.submit_draw_vote`` -- this only resolves the caller's
    game/power, posts the vote, and reports the response back.
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Draw vote failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error resolving game: {e}")
        return

    try:
        result = api_post(
            f"/games/{game_id}/draw_vote",
            {"power": power, "vote": vote, "telegram_id": user_id},
        )
    except Exception as e:
        await update.message.reply_text(f"Draw vote failed: {e}")
        return

    if result.get("quorum_reached"):
        winners = result.get("winners") or []
        winners_text = ", ".join(winners) if winners else "the surviving powers"
        await update.message.reply_text(
            f"🕊️ *Draw reached in Game {game_id}!*\n\n"
            f"The vote hit quorum and the game has ended in a draw among: {winners_text}.",
            parse_mode='Markdown',
        )
        return

    votes = result.get("votes", [])
    required = result.get("required", [])
    action = "recorded" if vote else "withdrawn"
    lines = [f"🗳️ Your draw vote for Game {game_id} has been {action}."]
    if required:
        lines.append(f"{len(votes)}/{len(required)} voted for a draw so far.")
        if votes:
            lines.append("Voted yes: " + ", ".join(votes))
    else:
        lines.append("No draw vote is currently possible (fewer than two surviving powers).")
    await update.message.reply_text("\n".join(lines))


async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /draw command - cast this power's yes vote to end the game as a
    draw. If this vote completes quorum (every surviving power has voted
    yes), the game ends immediately."""
    await _cast_draw_vote(update, context, True)


async def nodraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /nodraw command - withdraw this power's previously cast yes
    vote for a draw (no-op if none was cast)."""
    await _cast_draw_vote(update, context, False)


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /players command - list all players in current game with their powers."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Players command failed: No user context.")
        return

    user_id = str(user.id)
    args = context.args if context.args is not None else []
    game_id_arg = args[0] if args else None

    try:
        game_id, _power = resolve_game_and_power(user_id, game_id_arg)
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except Exception as e:
        await update.message.reply_text(f"Error retrieving players: {e}")
        return

    try:
        # GET /games/{id}/players returns a bare list, not {"players": [...]}.
        players_list = api_get(f"/games/{game_id}/players")
    except Exception as e:
        await update.message.reply_text(f"Could not retrieve players for game {game_id}: {e}")
        return

    if not players_list:
        await update.message.reply_text(f"No players found in game {game_id}.")
        return

    # Format player list. `full_name` is user-controlled (the player's Telegram
    # profile name) and this message is sent with parse_mode='Markdown', so it
    # must be escaped -- an unescaped `_`/`*`/`` ` ``/`[` here previously made
    # Telegram reject the whole message with no try/except around this call to
    # catch it, so /players silently did nothing for that player.
    lines = [f"👥 *Players in Game {game_id}*\n"]
    for player in players_list:
        power = player.get('power', 'Unknown')
        username = escape_markdown(player.get('full_name') or 'Unknown')
        is_active = player.get('is_active', True)
        status_emoji = "✅" if is_active else "❌"
        lines.append(f"{status_emoji} **{power}** - {username}")

    try:
        await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
    except Exception as e:
        logger.warning(f"Failed to send /players listing for game {game_id}: {e}")
        await update.message.reply_text(f"Could not display players for game {game_id}: {e}")


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


def _power_selection_prompt(game_id: str) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """Build the "choose a power" text + keyboard for ``game_id``.

    Shared by the inline "Browse Games" callback flow (``show_power_selection``)
    and ``/join <game_id>`` with no power argument -- docs/TELEGRAM_BOT_COMMANDS.md
    documents ``/join <game_id>`` as showing this menu, so both entry points
    into it need to render the same thing. Returns ``(text, None)`` for the
    "game not found" / "game full" cases (nothing to attach a keyboard to).
    """
    game_state = api_get(f"/games/{game_id}/state")
    if not game_state:
        return f"Could not retrieve game {game_id}.", None

    # Bare list, not {"players": [...]}.
    players_data = api_get(f"/games/{game_id}/players")
    taken_powers = {player.get('power') for player in (players_data or [])}

    keyboard = []
    for power in POWERS:
        if power not in taken_powers:
            button_text = f"Join as {power}"
            callback_data = f"join_game_{game_id}_{power}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    if not keyboard:
        return f"Game {game_id} is full. All powers are taken.", None

    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_games")])
    text = f"🎮 *Select Power for Game {game_id}*\n\nAvailable powers:"
    return text, InlineKeyboardMarkup(keyboard)


async def show_power_selection(update: Update, game_id: str) -> None:
    """Show available powers for a specific game (inline-button entry point)."""
    query = update.callback_query
    if not query:
        return
    try:
        text, reply_markup = _power_selection_prompt(game_id)
    except Exception as e:
        await query.edit_message_text(f"Error: {str(e)}")
        return
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join command.

    ``/join <game_id>`` (no power) shows the inline power-selection menu --
    this is what docs/TELEGRAM_BOT_COMMANDS.md documents. ``/join <game_id>
    <power>`` joins directly, for players who already know which power they
    want (e.g. scripted use, or after seeing the menu once).
    """
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Join command failed: No user context.")
        return
    user_id = str(user.id)
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /join <game_id> [power]")
        return
    game_id = args[0]

    if len(args) == 1:
        try:
            text, reply_markup = _power_selection_prompt(game_id)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")
            return
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return

    power = args[1].upper()
    try:
        result = api_post(f"/games/{game_id}/join", {"telegram_id": user_id, "game_id": int(game_id), "power": power})
        if result.get("status") == "ok":
            await update.message.reply_text(f"🎉 Successfully joined Game {game_id} as {power}!")
        elif result.get("status") == "already_joined":
            await update.message.reply_text(f"You are already in Game {game_id} as {power}.")
        else:
            await update.message.reply_text(f"Failed to join: {result.get('message', 'Unknown error')}")
    except requests.HTTPError as e:
        hint = ""
        if getattr(e, "response", None) is not None and e.response.status_code == 401:
            hint = "\n\n💡 Try /register first."
        await update.message.reply_text(f"Join error: {e}{hint}")
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


def process_waiting_list(
    waiting_list: List[Tuple[str, str]],
    required_size: int,
    powers: List[str],
    notify_callback,
    api_post_func=None
) -> Tuple[Optional[str], Optional[List[Tuple[Tuple[str, str], str]]]]:
    """
    Process the waiting list: if enough players, create a game, assign powers, and notify users.
    
    Args:
        waiting_list: List of (telegram_id, full_name) tuples (will be modified - cleared if game created)
        required_size: Number of players required to create a game
        powers: List of power names to assign
        notify_callback: Function(telegram_id: str, message: str) to notify players
        api_post_func: Function(endpoint: str, json: dict) to make API calls (defaults to api_post)
    
    Returns:
        Tuple of (game_id, assignments) if game created, (None, None) otherwise.
        assignments is a list of ((telegram_id, full_name), power) tuples.
    """
    if api_post_func is None:
        from .api_client import api_post
        api_post_func = api_post
    
    # Check if enough players
    if len(waiting_list) < required_size:
        return (None, None)
    
    # Get required number of players
    players = waiting_list[:required_size]
    random.shuffle(players)
    assigned_powers = list(zip(players, powers))
    
    try:
        # Create game
        game_resp = api_post_func("/games/create", {"map_name": "standard"})
        game_id = game_resp.get("game_id")
        
        if not game_id:
            logger.error("Failed to create game: no game_id in response")
            return (None, None)
        
        # Add all players
        for (player_id, player_name), power in assigned_powers:
            api_post_func(
                f"/games/{game_id}/join",
                {"telegram_id": player_id, "game_id": int(game_id), "power": power}
            )
        
        # Notify all players
        for (player_id, player_name), power in assigned_powers:
            try:
                notify_callback(
                    player_id,
                    f"🎮 Game {game_id} created! You've been assigned {power}.\n\nUse /games to see your game."
                )
            except Exception as e:
                logger.warning(f"Failed to notify player {player_id}: {e}")
        
        # Clear waiting list (remove the players we just used)
        waiting_list.clear()
        
        logger.info(f"Created game {game_id} with {len(assigned_powers)} players from waiting list")
        return (game_id, assigned_powers)
        
    except Exception as e:
        logger.error(f"Error creating game from waiting list: {e}")
        return (None, None)


async def wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Add user to waiting list and process if enough players.
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
        def notify_callback(telegram_id: str, message: str) -> None:
            # Notification will be handled by the bot's notification system
            logger.info(f"Would notify {telegram_id}: {message}")
        
        game_id, assignments = process_waiting_list(
            WAITING_LIST,
            WAITING_LIST_SIZE,
            POWERS,
            notify_callback
        )
        
        if game_id:
            # Waiting list is already cleared by process_waiting_list
            await update.message.reply_text(f"🎮 Game {game_id} created! All players have been notified.")
        else:
            await update.message.reply_text("Error creating game from waiting list. Please try again.")
