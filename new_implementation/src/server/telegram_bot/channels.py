"""
Telegram channel integration for Diplomacy games.

This module handles posting game content to Telegram channels:
- Automated map posting
- Broadcast message forwarding
- Turn notifications
"""
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger("diplomacy.telegram_bot.channels")

# Global bot instance (set by main telegram_bot.py)
_telegram_bot: Optional[Bot] = None


def set_telegram_bot(bot: Bot) -> None:
    """Set the Telegram bot instance for channel posting."""
    global _telegram_bot
    _telegram_bot = bot


def post_map_to_channel(channel_id: str, game_id: str, map_path: str) -> Optional[int]:
    """
    Post a map image to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID (e.g., "-1001234567890")
        game_id: Game ID for context
        map_path: Path to the map image file
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        if not os.path.exists(map_path):
            logger.error(f"Map file not found: {map_path}")
            return None
        
        # Read map image
        with open(map_path, 'rb') as f:
            map_bytes = f.read()
        
        # Post to channel
        message = _telegram_bot.send_photo(
            chat_id=channel_id,
            photo=map_bytes,
            caption=f"🗺️ Game {game_id} - Current Map"
        )
        
        logger.info(f"Posted map to channel {channel_id} for game {game_id}")
        return message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting map to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting map to channel {channel_id}: {e}")
        return None


def post_broadcast_to_channel(
    channel_id: str, 
    game_id: str, 
    message: str, 
    power: Optional[str] = None,
    reply_to_message_id: Optional[int] = None,
    create_thread: bool = False
) -> Optional[int]:
    """
    Post a broadcast message to a Telegram channel with optional threading support.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        message: Message text to post
        power: Optional power name for formatting
        reply_to_message_id: Optional message ID to reply to (for threading)
        create_thread: If True, create a new discussion thread (requires topic/forum channel)
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        # Format message
        if power:
            formatted_message = f"📢 **{power}** → All Powers\n\n{message}"
        else:
            formatted_message = f"📢 **PUBLIC BROADCAST**\n\n{message}"
        
        # Prepare message parameters
        message_params = {
            "chat_id": channel_id,
            "text": formatted_message,
            "parse_mode": 'Markdown'
        }
        
        # Add reply threading if specified
        if reply_to_message_id:
            message_params["reply_to_message_id"] = reply_to_message_id
        
        # Post to channel
        posted_message = _telegram_bot.send_message(**message_params)
        
        logger.info(f"Posted broadcast to channel {channel_id} for game {game_id} (message_id: {posted_message.message_id})")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting broadcast to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting broadcast to channel {channel_id}: {e}")
        return None


def create_discussion_thread(
    channel_id: str,
    game_id: str,
    topic: str,
    phase: Optional[str] = None
) -> Optional[int]:
    """
    Create a discussion thread for a specific phase or topic.
    
    Args:
        channel_id: Telegram channel ID (must be a forum/topic channel)
        game_id: Game ID for context
        topic: Thread topic/title
        phase: Optional phase name (e.g., "Spring 1901 Movement")
        
    Returns:
        Thread/topic message ID, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot create thread.")
        return None
    
    try:
        # Format thread title
        if phase:
            thread_title = f"{topic} - {phase}"
        else:
            thread_title = topic
        
        # Create forum topic (requires forum channel)
        # Note: This requires the channel to be a forum channel with topics enabled
        # For regular channels, we'll use reply threading instead
        try:
            # Try to create a forum topic
            topic_message = _telegram_bot.create_forum_topic(
                chat_id=channel_id,
                name=thread_title
            )
            logger.info(f"Created forum topic in channel {channel_id} for game {game_id}")
            return topic_message.message_thread_id if hasattr(topic_message, 'message_thread_id') else None
        except Exception:
            # If forum topics aren't supported, log and return None
            logger.debug(f"Channel {channel_id} does not support forum topics, using reply threading instead")
            return None
        
    except TelegramError as e:
        logger.error(f"Telegram error creating thread in channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error creating thread in channel {channel_id}: {e}")
        return None


def post_proposal_with_voting(
    channel_id: str,
    game_id: str,
    proposal_text: str,
    power: str,
    proposal_title: Optional[str] = None
) -> Optional[int]:
    """
    Post a proposal message with voting support (using inline keyboard buttons).
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        proposal_text: Proposal text/content
        power: Power proposing
        proposal_title: Optional proposal title
        
    Returns:
        Message ID of the posted proposal, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post proposal.")
        return None
    
    try:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
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
        
        emoji = power_emoji.get(power, "")
        title = proposal_title or "PROPOSAL"
        
        # Format proposal message
        formatted_message = (
            f"📢 **{title}: {proposal_title or 'Diplomatic Proposal'}**\n"
            f"{emoji} **{power}** proposes:\n\n"
            f"{proposal_text}\n\n"
            f"💬 Vote using the buttons below:"
        )
        
        # Create voting buttons
        keyboard = [
            [
                InlineKeyboardButton("👍 Support", callback_data=f"vote_proposal_{game_id}_support"),
                InlineKeyboardButton("👎 Oppose", callback_data=f"vote_proposal_{game_id}_oppose"),
                InlineKeyboardButton("🤔 Undecided", callback_data=f"vote_proposal_{game_id}_undecided")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        logger.info(f"Posted proposal with voting to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting proposal to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting proposal to channel {channel_id}: {e}")
        return None


def get_proposal_results(
    channel_id: str,
    message_id: int
) -> Dict[str, Any]:
    """
    Get voting results for a proposal message.
    
    Args:
        channel_id: Telegram channel ID
        message_id: Message ID of the proposal
        
    Returns:
        Dictionary with vote counts and results
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot get proposal results.")
        return {"error": "Bot not initialized"}
    
    try:
        # Get message reactions (if using native Telegram reactions)
        # Note: This requires the message to have reactions added by users
        # For now, we'll track votes via callback queries instead
        
        # Return placeholder structure
        return {
            "message_id": message_id,
            "votes": {
                "support": 0,
                "oppose": 0,
                "undecided": 0
            },
            "total_votes": 0
        }
        
    except Exception as e:
        logger.exception(f"Error getting proposal results: {e}")
        return {"error": str(e)}


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
        
        header = f"📜 **HISTORICAL TIMELINE - GAME {game_id}**\n\n"
        
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
            timeline_text += f"**{phase_label}:**\n"
            timeline_text += "\n".join(timeline_events) + "\n\n"
        else:
            timeline_text += f"*No major events recorded yet.*\n\n"
        
        # Add current status summary
        timeline_text += "**Current Status:**\n"
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
        return f"📜 **HISTORICAL TIMELINE**\n\nError formatting timeline: {str(e)}"


def post_timeline_update_to_channel(
    channel_id: str,
    game_id: str,
    game_state: Dict[str, Any],
    turn_history: Optional[List[Dict[str, Any]]] = None,
    previous_powers: Optional[Dict[str, Dict[str, Any]]] = None
) -> Optional[int]:
    """
    Format and post historical timeline update to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        game_state: Current game state dictionary
        turn_history: List of turn history entries
        previous_powers: Previous power states for comparison
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        # Format timeline
        formatted_timeline = format_historical_timeline(game_state, turn_history, previous_powers)
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_timeline,
            parse_mode='Markdown'
        )
        
        logger.info(f"Posted timeline update to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting timeline to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting timeline to channel {channel_id}: {e}")
        return None


def post_notification_to_channel(
    channel_id: str,
    game_id: str,
    notification_type: str,
    title: str,
    message: str
) -> Optional[int]:
    """
    Post a notification to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        notification_type: Type of notification ("turn_start", "deadline", "phase_change", etc.)
        title: Notification title
        message: Notification message
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        # Format notification based on type
        emoji_map = {
            "turn_start": "🎮",
            "deadline": "⏰",
            "phase_change": "🔄",
            "adjudication": "⚔️",
            "elimination": "💀",
            "game_end": "🏆"
        }
        
        emoji = emoji_map.get(notification_type, "📢")
        formatted_message = f"{emoji} **{title}**\n\n{message}"
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_message,
            parse_mode='Markdown'
        )
        
        logger.info(f"Posted {notification_type} notification to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting notification to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting notification to channel {channel_id}: {e}")
        return None


def should_auto_post_map(game_id: str) -> bool:
    """Check if maps should be auto-posted for a game based on channel settings."""
    from ...api.shared import db_service
    
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            return False
        
        settings = channel_info.get("settings", {})
        return settings.get("auto_post_maps", True)  # Default to True
    except Exception:
        return False


def should_auto_post_broadcast(game_id: str) -> bool:
    """Check if broadcasts should be auto-posted for a game."""
    from ...api.shared import db_service
    
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            return False
        
        settings = channel_info.get("settings", {})
        return settings.get("auto_post_broadcasts", True)  # Default to True
    except Exception:
        return False


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
        
        header = f"👥 **PLAYER STATUS DASHBOARD - GAME {game_id}**\n"
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
        submitted_powers = set(orders.keys())
        
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
                is_active = power_state.get("is_active", True)
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
                        player_line += f" - Submitted {time_ago} ago"
                    else:
                        player_line += " - Submitted"
                    submitted_players.append(player_line)
                elif last_order_time:
                    player_line += f" - Last active {time_ago} ago"
                    pending_players.append(player_line)
                else:
                    player_line += " - No orders"
                    no_orders_players.append(player_line)
        
        # Build dashboard text
        dashboard_text = header
        
        if submitted_players:
            dashboard_text += "✅ **Orders Submitted:**\n"
            dashboard_text += "\n".join(submitted_players) + "\n\n"
        
        if pending_players:
            dashboard_text += "⏳ **Pending:**\n"
            dashboard_text += "\n".join(pending_players) + "\n\n"
        
        if no_orders_players:
            dashboard_text += "❌ **No Orders:**\n"
            dashboard_text += "\n".join(no_orders_players) + "\n\n"
        
        return dashboard_text
        
    except Exception as e:
        logger.exception(f"Error formatting player dashboard: {e}")
        return f"👥 **PLAYER STATUS DASHBOARD**\n\nError formatting dashboard: {str(e)}"


def post_player_dashboard_to_channel(
    channel_id: str,
    game_id: str,
    game_state: Dict[str, Any],
    players_data: Optional[List[Dict[str, Any]]] = None
) -> Optional[int]:
    """
    Format and post player status dashboard to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        game_state: Current game state dictionary
        players_data: Optional list of player data from API
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        # Format dashboard
        formatted_dashboard = format_player_dashboard(game_state, players_data)
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_dashboard,
            parse_mode='Markdown'
        )
        
        logger.info(f"Posted player dashboard to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting player dashboard to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting player dashboard to channel {channel_id}: {e}")
        return None


def should_auto_post_notification(game_id: str, notification_level: str = "important") -> bool:
    """Check if notifications should be auto-posted for a game."""
    from ...api.shared import db_service
    
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            return False
        
        settings = channel_info.get("settings", {})
        configured_level = settings.get("notification_level", "all")
        
        if configured_level == "none":
            return False
        elif configured_level == "all":
            return True
        elif configured_level == "important":
            return notification_level in ["turn_start", "deadline", "game_end", "elimination"]
        else:
            return False
    except Exception:
        return False


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
        header = f"⚔️ **ADJUDICATION RESULTS - {season.upper()} {year}**\n\n"
        
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
            results_text += "🎯 **Successful Attacks:**\n"
            results_text += "\n".join(successful_attacks) + "\n\n"
        
        # Dislodged units
        if dislodged_info:
            results_text += "💥 **Dislodgements:**\n"
            results_text += "\n".join(dislodged_info) + "\n\n"
        
        # Bounced movements
        if bounced_movements:
            results_text += "🔄 **Bounced Movements:**\n"
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
                results_text += "📊 **Supply Center Changes:**\n"
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
            results_text += "📈 **Power Rankings:**\n"
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
        return f"⚔️ **ADJUDICATION RESULTS**\n\nError formatting results: {str(e)}"


def post_battle_results_to_channel(
    channel_id: str,
    game_id: str,
    game_state: Dict[str, Any],
    order_history: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    previous_supply_centers: Optional[Dict[str, List[str]]] = None
) -> Optional[int]:
    """
    Format and post battle results to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        game_state: Current game state dictionary
        order_history: Orders from the last turn that was just processed
        previous_supply_centers: Previous supply center control for comparison
        
    Returns:
        Message ID of the posted message, or None if failed
    """
    global _telegram_bot
    
    if not _telegram_bot:
        logger.error("Telegram bot not initialized. Cannot post to channel.")
        return None
    
    try:
        # Format battle results
        formatted_results = format_battle_results(game_state, order_history, previous_supply_centers)
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_results,
            parse_mode='Markdown'
        )
        
        logger.info(f"Posted battle results to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting battle results to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting battle results to channel {channel_id}: {e}")
        return None

