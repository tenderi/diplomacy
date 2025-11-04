"""
Telegram channel integration for Diplomacy games.

This module handles posting game content to Telegram channels:
- Automated map posting
- Broadcast message forwarding
- Turn notifications
"""
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime

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
    power: Optional[str] = None
) -> Optional[int]:
    """
    Post a broadcast message to a Telegram channel.
    
    Args:
        channel_id: Telegram channel ID
        game_id: Game ID for context
        message: Message text to post
        power: Optional power name for formatting
        
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
        
        # Post to channel
        posted_message = _telegram_bot.send_message(
            chat_id=channel_id,
            text=formatted_message,
            parse_mode='Markdown'
        )
        
        logger.info(f"Posted broadcast to channel {channel_id} for game {game_id}")
        return posted_message.message_id
        
    except TelegramError as e:
        logger.error(f"Telegram error posting broadcast to channel {channel_id}: {e}")
        return None
    except Exception as e:
        logger.exception(f"Error posting broadcast to channel {channel_id}: {e}")
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

