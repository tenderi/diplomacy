"""
Map generation and display functions for the Telegram bot.
"""
import logging
import os
from io import BytesIO
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from engine.map import Map
from .api_client import api_get

logger = logging.getLogger("diplomacy.telegram_bot.maps")

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

    # Generate map image (no supply center control for default empty map)
    return Map.render_board_png(svg_path, units, phase_info=phase_info, supply_center_control=None)


async def send_default_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the standard Diplomacy map without any units"""
    try:
        # Try to get cached map first
        img_bytes = get_cached_default_map()

        if img_bytes is None:
            # Cache miss - generate the map (expensive operation)
            logger.info("Generating default map (first time)")
            img_bytes = generate_default_map()
            set_cached_default_map(img_bytes)
            logger.info("Default map generated and cached permanently")
        else:
            logger.info("Using permanently cached default map")

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


async def send_demo_map(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str) -> None:
    """Send the demo map with all units in starting positions"""
    try:
        # Get game state
        game_state = api_get(f"/games/{game_id}/state")

        # Generate map with units
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

        # Get supply center control for demo map
        supply_center_control = {}
        if "supply_centers" in game_state:
            supply_center_control = game_state["supply_centers"]
        elif "powers" in game_state:
            for power_name, power_data in game_state.get("powers", {}).items():
                if isinstance(power_data, dict) and "controlled_supply_centers" in power_data:
                    for sc in power_data["controlled_supply_centers"]:
                        supply_center_control[sc] = power_name

        # Render the map with supply center control
        img_bytes = map_instance.render_board_png(
            units, f"/tmp/demo_map_{game_id}.png", 
            phase_info=phase_info, supply_center_control=supply_center_control
        )

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

        # Get supply center control (includes both occupied and unoccupied controlled supply centers)
        supply_center_control = {}
        if "supply_centers" in game_state:
            supply_center_control = game_state["supply_centers"]
        elif "powers" in game_state:
            # Build from powers if supply_centers not directly available
            for power_name, power_data in game_state.get("powers", {}).items():
                if isinstance(power_data, dict) and "controlled_supply_centers" in power_data:
                    for sc in power_data["controlled_supply_centers"]:
                        supply_center_control[sc] = power_name

        # Render the map with units and supply center control
        svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        img_bytes = Map.render_board_png(
            svg_path, units, output_path=f"/tmp/game_map_{game_id}.png", 
            phase_info=phase_info, supply_center_control=supply_center_control
        )

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


async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /map command to display a game map."""
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
        # Get supply center control
        supply_center_control = {}
        if "supply_centers" in game_state:
            supply_center_control = game_state["supply_centers"]
        elif "powers" in game_state:
            for power_name, power_data in game_state.get("powers", {}).items():
                if isinstance(power_data, dict) and "controlled_supply_centers" in power_data:
                    for sc in power_data["controlled_supply_centers"]:
                        supply_center_control[sc] = power_name

        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info, supply_center_control=supply_center_control)
        except Exception as e:
            await update.message.reply_text(f"Error rendering map: {e}")
            return
        await update.message.reply_photo(photo=BytesIO(img_bytes), caption=f"Board for game {game_id}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def replay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /replay command to show a historical game state."""
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

        # Get supply center control from state
        supply_center_control = {}
        if "supply_centers" in state:
            supply_center_control = state["supply_centers"]
        elif "powers" in state:
            for power_name, power_data in state.get("powers", {}).items():
                if isinstance(power_data, dict) and "controlled_supply_centers" in power_data:
                    for sc in power_data["controlled_supply_centers"]:
                        supply_center_control[sc] = power_name

        base_map_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg").replace("standard.svg", "")
        svg_path = f"{base_map_path}{map_name}.svg"
        if not os.path.isfile(svg_path):
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info, supply_center_control=supply_center_control)
        except Exception as e:
            await update.message.reply_text(f"Error rendering map: {e}")
            return
        await update.message.reply_photo(photo=BytesIO(img_bytes), caption=f"Board for game {game_id}, turn {turn}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


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

