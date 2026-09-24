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
    try:
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
        
    except Exception as e:
        logger.exception(f"Error formatting historical timeline: {e}")
        return f"📜 *HISTORICAL TIMELINE*\n\nError formatting timeline: {str(e)}"


def format_player_dashboard(game_state: Dict[str, Any], players_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Format player status dashboard for channel posting.
    
    Args:
        game_state: Current game state dictionary
        players_data: Optional list of player data from API (power, user info, etc.)
        
    Returns:
        Formatted player dashboard string
    """
    try:
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
                    except Exception:
                        time_ago = ""
                
                # Get user info if available
                user_info = ""
                if players_data:
                    for player in players_data:
                        if player.get("power") == power_name:
                            full_name = player.get("full_name")
                            telegram_id = player.get("telegram_id")
                            if full_name:
                                user_info = f" ({full_name})"
                            elif telegram_id:
                                user_info = f" (User {telegram_id})"
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
        
    except Exception as e:
        logger.exception(f"Error formatting player dashboard: {e}")
        return f"👥 *PLAYER STATUS DASHBOARD*\n\nError formatting dashboard: {str(e)}"


def format_battle_results(
    game_state: Dict[str, Any], 
    order_history: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    previous_supply_centers: Optional[Dict[str, List[str]]] = None
) -> str:
    """
    Format battle results from game state for channel posting.
    
    Args:
        game_state: Current game state dictionary
        order_history: Orders from the last turn that was just processed (power -> list of orders)
        previous_supply_centers: Previous supply center control (power -> list of provinces)
        
    Returns:
        Formatted battle results string
    """
    try:
        # Extract phase information
        year = game_state.get("current_year", game_state.get("currentYear", 1901))
        season = game_state.get("current_season", game_state.get("currentSeason", "Spring"))
        
        # Build header
        header = f"⚔️ *ADJUDICATION RESULTS - {season.upper()} {year}*\n\n"
        
        successful_attacks = []
        bounced_movements = []
        
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
        
        # Process orders from order history (last turn's orders)
        if order_history:
            for power, power_orders in order_history.items():
                for order in power_orders:
                    if isinstance(order, dict):
                        order_type = order.get("order_type", "").lower()
                        status = order.get("status", "").lower()
                        unit = order.get("unit", {})
                        unit_type = unit.get("unit_type", "A")
                        unit_province = unit.get("province", "")
                        unit_str = f"{unit_type} {unit_province}"
                        
                        if order_type == "move":
                            target = order.get("target_province", "")
                            if status == "success":
                                # Check if unit moved (compare current position)
                                # If target matches current position, it succeeded
                                successful_attacks.append(f"• {unit_str} → {target}")
                            elif status == "bounced" or status == "failed":
                                bounced_movements.append(f"• {unit_str} → {target} (bounced)")
        
        # Also check for dislodged units in current state
        units = game_state.get("units", {})
        dislodged_info = []
        for power, power_units in units.items():
            for unit in power_units:
                if isinstance(unit, dict) and unit.get("is_dislodged", False):
                    unit_type = unit.get("unit_type", "A")
                    province = unit.get("province", "").replace("DISLODGED_", "")
                    dislodged_by = unit.get("dislodged_by", "")
                    if dislodged_by:
                        dislodged_info.append(f"• {unit_type} {province} dislodged by {dislodged_by}")
        
        # Build results text
        results_text = header
        
        # Successful attacks
        if successful_attacks:
            results_text += "🎯 *Successful Attacks:*\n"
            results_text += "\n".join(successful_attacks) + "\n\n"
        
        # Dislodged units
        if dislodged_info:
            results_text += "💥 *Dislodgements:*\n"
            results_text += "\n".join(dislodged_info) + "\n\n"
        
        # Bounced movements
        if bounced_movements:
            results_text += "🔄 *Bounced Movements:*\n"
            results_text += "\n".join(bounced_movements) + "\n\n"
        
        # Supply center changes
        current_supply_centers = {}
        supply_centers = game_state.get("supply_centers", {})
        for power, centers in supply_centers.items():
            if isinstance(centers, list):
                current_supply_centers[power] = centers
            elif isinstance(centers, dict):
                current_supply_centers[power] = list(centers.keys())
        
        if previous_supply_centers and current_supply_centers:
            supply_changes = []
            all_powers = set(list(previous_supply_centers.keys()) + list(current_supply_centers.keys()))
            
            for power in all_powers:
                prev_count = len(previous_supply_centers.get(power, []))
                curr_count = len(current_supply_centers.get(power, []))
                change = curr_count - prev_count
                
                if change != 0:
                    emoji = power_emoji.get(power, "")
                    if change > 0:
                        # Find which center was captured
                        new_centers = set(current_supply_centers.get(power, [])) - set(previous_supply_centers.get(power, []))
                        if new_centers:
                            center_name = list(new_centers)[0]
                            supply_changes.append(f"{emoji} {power}: +{change} ({center_name} captured)")
                        else:
                            supply_changes.append(f"{emoji} {power}: +{change}")
                    else:
                        # Find which center was lost
                        lost_centers = set(previous_supply_centers.get(power, [])) - set(current_supply_centers.get(power, []))
                        if lost_centers:
                            center_name = list(lost_centers)[0]
                            supply_changes.append(f"{emoji} {power}: {change} ({center_name} lost)")
                        else:
                            supply_changes.append(f"{emoji} {power}: {change}")
            
            if supply_changes:
                results_text += "📊 *Supply Center Changes:*\n"
                results_text += "\n".join(supply_changes) + "\n\n"
        
        # Power rankings
        power_rankings = []
        for power, centers in current_supply_centers.items():
            count = len(centers)
            emoji = power_emoji.get(power, "")
            power_rankings.append((power, count, emoji))
        
        # Sort by count (descending)
        power_rankings.sort(key=lambda x: x[1], reverse=True)
        
        if power_rankings:
            results_text += "📈 *Power Rankings:*\n"
            prev_count = None
            rank = 1
            for power, count, emoji in power_rankings:
                # Determine trend arrow
                if previous_supply_centers:
                    prev_count_for_power = len(previous_supply_centers.get(power, []))
                    if count > prev_count_for_power:
                        trend = "↗️"
                    elif count < prev_count_for_power:
                        trend = "↘️"
                    else:
                        trend = "→"
                else:
                    trend = ""
                
                # Handle ties
                if prev_count is not None and count == prev_count:
                    rank_str = f"{rank-1}."
                else:
                    rank_str = f"{rank}."
                    prev_count = count
                    rank += 1
                
                results_text += f"{rank_str} {emoji} {power} ({count} centers) {trend}\n"
        
        return results_text
        
    except Exception as e:
        logger.exception(f"Error formatting battle results: {e}")
        return f"⚔️ *ADJUDICATION RESULTS*\n\nError formatting results: {str(e)}"
