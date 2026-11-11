"""
Formatting of the channel posts the API queues for a game's linked Telegram channel.

The API's ``/games/{id}/channel/*`` routes call these with the dict built by
``api.routes.channels._legacy_state_dict`` and queue the text on ``bot_outbox``; the bot
delivers it (``notifications.py``). Nothing here sends anything. Every post goes out with
``parse_mode='Markdown'`` (legacy): bold is ``*single*``.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .utils import escape_markdown

logger = logging.getLogger("diplomacy.telegram_bot.channels")


_SEASONS = {"S": "Spring", "F": "Fall", "W": "Winter"}
_TIMELINE_LIMIT = 3900  # Telegram caps a message at 4096 characters


def _phase_heading(phase_code: str) -> str:
    """``"F1902M"`` -> ``"Fall 1902"``; anything else is returned as is."""
    season = _SEASONS.get(phase_code[:1])
    year = phase_code[1:5]
    return f"{season} {year}" if season and year.isdigit() else phase_code


def _timeline_sections(board_history: List[Dict[str, Any]], power_emoji: Dict[str, str]) -> List[str]:
    """One ``*Fall 1902:*`` block per turn that had an event.

    ``board_history`` is the game's boards oldest first, each
    ``{"phase_code", "centers": {power: n}, "units": {power: n}}`` -- the board a
    phase *began* on. What changed between two boards happened during the earlier
    board's phase, so that is the heading.
    """
    sections: List[str] = []
    for before, after in zip(board_history, board_history[1:]):
        events: List[str] = []
        powers = sorted(set(before["centers"]) | set(before["units"]) | set(after["centers"]) | set(after["units"]))
        for power in powers:
            emoji = power_emoji.get(power, "")
            was = before["centers"].get(power, 0)
            now = after["centers"].get(power, 0)
            if (was or before["units"].get(power, 0)) and not now and not after["units"].get(power, 0):
                events.append(f"• {emoji} {power} eliminated")
            elif now - was >= 2:
                events.append(f"• {emoji} {power} gains {now - was} supply centers")
            elif was - now >= 2:
                events.append(f"• {emoji} {power} loses {was - now} supply centers")
        for power in powers:
            now = after["centers"].get(power, 0)
            if now >= 18 > before["centers"].get(power, 0):
                events.append(f"• 🏆 {power_emoji.get(power, '')} {power} achieves victory with {now} supply centers")
        if events:
            sections.append(f"*{_phase_heading(before['phase_code'])}:*\n" + "\n".join(events) + "\n\n")
    return sections


def format_historical_timeline(
    game_state: Dict[str, Any],
    board_history: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Format the game's timeline: the events of each turn, then the current standings.

    Args:
        game_state: Current game state dictionary
        board_history: the game's boards, oldest first, each
            ``{"phase_code", "centers": {power: count}, "units": {power: count}}``.
            Eliminations, swings of 2+ centres and a win are read from consecutive
            boards. The newest turns are kept if the text would pass Telegram's limit.

    Returns:
        Formatted historical timeline string
    """
    game_id = game_state.get("game_id", "Unknown")
    header = f"📜 *HISTORICAL TIMELINE - GAME {game_id}*\n\n"

    power_emoji = {
        "AUSTRIA": "🇦🇹",
        "ENGLAND": "🇬🇧",
        "FRANCE": "🇫🇷",
        "GERMANY": "🇩🇪",
        "ITALY": "🇮🇹",
        "RUSSIA": "🇷🇺",
        "TURKEY": "🇹🇷"
    }

    current_powers = game_state.get("powers", {})
    sections = _timeline_sections(board_history or [], power_emoji)

    timeline_text = header
    if sections:
        kept: List[str] = []
        size = len(header) + 400  # room for the standings
        for section in reversed(sections):
            if size + len(section) > _TIMELINE_LIMIT:
                break
            kept.append(section)
            size += len(section)
        if len(kept) < len(sections):
            timeline_text += "_Earlier turns left out._\n\n"
        timeline_text += "".join(reversed(kept))
    else:
        timeline_text += "*No major events recorded yet.*\n\n"

    # Add current status summary
    timeline_text += "*Current Status:*\n"
    power_rankings = []
    for power_name, power_state in current_powers.items():
        if isinstance(power_state, dict):
            centers = len(power_state.get("controlled_supply_centers", []))
            emoji = power_emoji.get(power_name, "")
            is_eliminated = power_state.get("is_eliminated", False)
            if not is_eliminated:
                power_rankings.append((power_name, centers, emoji))
    
    # Sort by centers
    power_rankings.sort(key=lambda x: x[1], reverse=True)
    
    for power, centers, emoji in power_rankings[:5]:  # Top 5
        timeline_text += f"• {emoji} {power}: {centers} centers\n"
    
    return timeline_text
    


def format_player_dashboard(game_state: Dict[str, Any], players_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Format player status dashboard for channel posting.
    
    Args:
        game_state: Current game state dictionary
        players_data: Optional list of player data from API (power, user info, etc.)
        
    Returns:
        Formatted player dashboard string
    """
    # Extract game info
    game_id = game_state.get("game_id", "Unknown")
    year = game_state.get("current_year", game_state.get("currentYear", 1901))
    season = game_state.get("current_season", game_state.get("currentSeason", "Spring"))
    phase = game_state.get("current_phase", game_state.get("currentPhase", "Movement"))
    
    header = f"👥 *PLAYER STATUS DASHBOARD - GAME {game_id}*\n"
    header += f"📅 {season} {year} - {phase} Phase\n\n"
    
    # Power emoji mapping
    power_emoji = {
        "AUSTRIA": "🇦🇹",
        "ENGLAND": "🇬🇧",
        "FRANCE": "🇫🇷",
        "GERMANY": "🇩🇪",
        "ITALY": "🇮🇹",
        "RUSSIA": "🇷🇺",
        "TURKEY": "🇹🇷"
    }
    
    # Get orders to check submission status
    orders = game_state.get("orders", {})
    submitted_powers = {power for power, power_orders in orders.items() if power_orders}
    
    # Get power states for order submission info
    powers = game_state.get("powers", {})
    
    # Build player status lists
    submitted_players = []
    pending_players = []
    no_orders_players = []
    
    # Process each power
    for power_name, power_state in powers.items():
        if isinstance(power_state, dict):
            orders_submitted = power_state.get("orders_submitted", False)
            last_order_time = power_state.get("last_order_time")
            is_eliminated = power_state.get("is_eliminated", False)
            
            emoji = power_emoji.get(power_name, "")
            
            # Format time ago
            time_ago = ""
            if last_order_time:
                try:
                    if isinstance(last_order_time, str):
                        last_time = datetime.fromisoformat(last_order_time.replace('Z', '+00:00'))
                    else:
                        last_time = last_order_time
                    now = datetime.now(timezone.utc)
                    if last_time.tzinfo is None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                    delta = now - last_time
                    
                    hours = int(delta.total_seconds() / 3600)
                    days = int(delta.total_seconds() / 86400)
                    
                    if days > 0:
                        time_ago = f"{days}d ago"
                    elif hours > 0:
                        time_ago = f"{hours}h ago"
                    else:
                        minutes = int(delta.total_seconds() / 60)
                        time_ago = f"{minutes}m ago"
                except (ValueError, TypeError):  # an unparsable timestamp shows no "ago"
                    time_ago = ""
            
            # Get user info if available
            user_info = ""
            if players_data:
                for player in players_data:
                    if player.get("power") == power_name:
                        nickname = player.get("nickname")
                        if nickname:
                            user_info = f" ({escape_markdown(nickname)})"  # Markdown post
                        break
            
            player_line = f"{emoji} {power_name}{user_info}"
            
            if is_eliminated:
                player_line += " - Eliminated"
                no_orders_players.append(player_line)
            elif orders_submitted or power_name in submitted_powers:
                if time_ago:
                    player_line += f" - Submitted {time_ago}"
                else:
                    player_line += " - Submitted"
                submitted_players.append(player_line)
            elif last_order_time:
                player_line += f" - Last active {time_ago}"
                pending_players.append(player_line)
            else:
                player_line += " - No orders"
                no_orders_players.append(player_line)
    
    # Build dashboard text
    dashboard_text = header
    
    if submitted_players:
        dashboard_text += "✅ *Orders Submitted:*\n"
        dashboard_text += "\n".join(submitted_players) + "\n\n"
    
    if pending_players:
        dashboard_text += "⏳ *Pending:*\n"
        dashboard_text += "\n".join(pending_players) + "\n\n"
    
    if no_orders_players:
        dashboard_text += "❌ *No Orders:*\n"
        dashboard_text += "\n".join(no_orders_players) + "\n\n"
    
    return dashboard_text
    
