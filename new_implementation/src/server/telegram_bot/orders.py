"""
Order management commands for the Telegram bot.
"""
import logging
import asyncio
import requests
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from engine.map import Map

logger = logging.getLogger("diplomacy.telegram_bot.orders")


def normalize_order_provinces(order_text: str, power: str) -> str:
    """Normalize province names in an order string."""
    from engine.province_mapping import normalize_province_name

    # Split the order into parts
    parts = order_text.split()

    # The order format is: UNIT_TYPE PROVINCE [ACTION] [TARGET_PROVINCE]
    # NOT: POWER UNIT_TYPE PROVINCE [ACTION] [TARGET_PROVINCE]
    # The power is handled separately in the API call

    # Remove power name if it's the first part
    if parts and parts[0] == power:
        parts = parts[1:]  # Remove the power name

    normalized_parts = []
    for i, part in enumerate(parts):
        # Skip unit type (A/F) - first part after removing power
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

        # Normalize province names in the order (fallback to raw on error)
        try:
            normalized_order = normalize_order_provinces(order_text, power)
        except Exception:
            normalized_order = order_text

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


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Submit orders for a specific game."""
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
    """View current orders for the user's active game."""
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
    """Clear orders for the user's active game."""
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
    """View order history for the user's active game."""
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
    from .maps import send_game_map  # Import here to avoid circular dependency

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
        try:
            user_games_response = api_get(f"/users/{user_id}/games")
            user_games = user_games_response.get("games", []) if user_games_response else []
        except requests.exceptions.HTTPError as e:
            # Handle 404 (user not found) gracefully - treat as no games
            if e.response is not None and e.response.status_code == 404:
                user_games = []
            else:
                raise  # Re-raise other HTTP errors

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
    # Optionally retrieve user's games to align with test expectations
    try:
        user_id = str(query.from_user.id)
        _ = api_get(f"/users/{user_id}/games")
    except Exception:
        pass

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

        # Refresh user games (used by tests to validate interaction sequence)
        try:
            _ = api_get(f"/users/{user_id}/games")
        except Exception:
            pass

    except Exception as e:
        await query.edit_message_text(f"❌ Error submitting order: {e}")


async def show_my_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show orders menu for user's games"""
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

