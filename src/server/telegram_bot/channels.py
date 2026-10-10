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


def format_historical_timeline(
    game_state: Dict[str, Any],
    turn_history: Optional[List[Dict[str, Any]]] = None,
    previous_powers: Optional[Dict[str, Dict[str, Any]]] = None
) -> str:
    """
    Format historical timeline from game events.
    
    Args:
        game_state: Current game state dictionary
        turn_history: List of turn history entries
        previous_powers: Previous power states for comparison (power -> power_state dict)
        
    Returns:
        Formatted historical timeline string
    """
    # Extract game info
    game_id = game_state.get("game_id", "Unknown")
    current_year = game_state.get("current_year", game_state.get("currentYear", 1901))
    current_season = game_state.get("current_season", game_state.get("currentSeason", "Spring"))
    
    header = f"📜 *HISTORICAL TIMELINE - GAME {game_id}*\n\n"
    
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
    
    timeline_events = []
    
    # Get current powers
    current_powers = game_state.get("powers", {})
    current_supply_centers = game_state.get("supply_centers", {})
    
    # Check for eliminations
    if previous_powers:
        for power_name, prev_state in previous_powers.items():
            prev_eliminated = prev_state.get("is_eliminated", False)
            curr_state = current_powers.get(power_name, {})
            curr_eliminated = curr_state.get("is_eliminated", False) if isinstance(curr_state, dict) else False
            
            if not prev_eliminated and curr_eliminated:
                emoji = power_emoji.get(power_name, "")
                timeline_events.append(f"• {emoji} {power_name} eliminated")
    
    # Check for major supply center changes (captures of 2+ centers in a turn)
    if previous_powers and current_supply_centers:
        for power_name, curr_state in current_powers.items():
            if isinstance(curr_state, dict):
                curr_centers = len(curr_state.get("controlled_supply_centers", []))
                prev_state = previous_powers.get(power_name, {})
                prev_centers = len(prev_state.get("controlled_supply_centers", []))
                change = curr_centers - prev_centers
                
                if change >= 2:
                    emoji = power_emoji.get(power_name, "")
                    timeline_events.append(f"• {emoji} {power_name} gains {change} supply centers")
                elif change <= -2:
                    emoji = power_emoji.get(power_name, "")
                    timeline_events.append(f"• {emoji} {power_name} loses {abs(change)} supply centers")
    
    # Check for victory condition
    for power_name, power_state in current_powers.items():
        if isinstance(power_state, dict):
            centers = len(power_state.get("controlled_supply_centers", []))
            if centers >= 18:
                emoji = power_emoji.get(power_name, "")
                timeline_events.append(f"• 🏆 {emoji} {power_name} achieves victory with {centers} supply centers")
    
    # Build timeline text
    timeline_text = header
    
    # Group events by turn/season if available
    if timeline_events:
        phase_label = f"{current_season} {current_year}"
        timeline_text += f"*{phase_label}:*\n"
        timeline_text += "\n".join(timeline_events) + "\n\n"
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
    
