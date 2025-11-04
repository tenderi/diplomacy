"""
Telegram bot commands for channel management.

This module provides commands for linking games to Telegram channels,
managing channel settings, and controlling channel integration.
"""
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from .api_client import api_post, api_get
from .channels import set_telegram_bot

logger = logging.getLogger("diplomacy.telegram_bot.channel_commands")


async def link_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Link a Telegram channel to a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Link channel failed: No user context.")
        return
    
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /link_channel <game_id> <channel_id>\n\n"
            "Example: /link_channel 42 -1001234567890\n\n"
            "To get the channel ID:\n"
            "1. Forward a message from the channel to @userinfobot\n"
            "2. Or use @getidsbot in the channel"
        )
        return
    
    game_id = args[0]
    channel_id = args[1]
    
    try:
        # Verify user is in the game or is admin
        user_id = str(user.id)
        user_games = api_get(f"/users/{user_id}/games")
        user_in_game = any(str(g["game_id"]) == game_id for g in user_games.get("games", []))
        
        if not user_in_game and user_id != "8019538":  # Admin check
            await update.message.reply_text(
                f"You must be a player in game {game_id} to link a channel."
            )
            return
        
        # Link channel
        result = api_post(
            f"/games/{game_id}/channel/link",
            {"channel_id": channel_id}
        )
        
        if result.get("status") == "ok":
            await update.message.reply_text(
                f"✅ Channel {channel_id} linked to game {game_id}!\n\n"
                f"Automated features:\n"
                f"• Maps will be posted after each turn\n"
                f"• Broadcasts will be forwarded\n"
                f"• Turn notifications will be sent"
            )
        else:
            await update.message.reply_text(f"❌ Failed to link channel: {result}")
            
    except Exception as e:
        logger.exception(f"Error linking channel: {e}")
        await update.message.reply_text(f"Link channel error: {e}")


async def unlink_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unlink a Telegram channel from a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Unlink channel failed: No user context.")
        return
    
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /unlink_channel <game_id>")
        return
    
    game_id = args[0]
    
    try:
        # Verify user is in the game or is admin
        user_id = str(user.id)
        user_games = api_get(f"/users/{user_id}/games")
        user_in_game = any(str(g["game_id"]) == game_id for g in user_games.get("games", []))
        
        if not user_in_game and user_id != "8019538":  # Admin check
            await update.message.reply_text(
                f"You must be a player in game {game_id} to unlink a channel."
            )
            return
        
        # Unlink channel
        from .api_client import api_delete
        import requests
        
        result = requests.delete(
            f"{api_get.__globals__.get('API_URL', 'http://localhost:8000')}/games/{game_id}/channel/unlink"
        ).json()
        
        if result.get("status") == "ok":
            await update.message.reply_text(
                f"✅ Channel unlinked from game {game_id}."
            )
        else:
            await update.message.reply_text(f"❌ Failed to unlink channel: {result}")
            
    except Exception as e:
        logger.exception(f"Error unlinking channel: {e}")
        await update.message.reply_text(f"Unlink channel error: {e}")


async def channel_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get channel information for a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Channel info failed: No user context.")
        return
    
    args = context.args if context.args is not None else []
    if len(args) < 1:
        await update.message.reply_text("Usage: /channel_info <game_id>")
        return
    
    game_id = args[0]
    
    try:
        channel_info = api_get(f"/games/{game_id}/channel")
        
        if not channel_info.get("linked"):
            await update.message.reply_text(
                f"Game {game_id} is not linked to a channel."
            )
            return
        
        settings = channel_info.get("settings", {})
        info_text = (
            f"📢 *Channel Information - Game {game_id}*\n\n"
            f"Channel ID: `{channel_info.get('channel_id')}`\n"
            f"Channel Name: {channel_info.get('channel_name', 'N/A')}\n\n"
            f"*Settings:*\n"
            f"• Auto-post maps: {settings.get('auto_post_maps', True)}\n"
            f"• Auto-post broadcasts: {settings.get('auto_post_broadcasts', True)}\n"
            f"• Auto-post notifications: {settings.get('auto_post_notifications', True)}\n"
            f"• Notification level: {settings.get('notification_level', 'all')}"
        )
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.exception(f"Error getting channel info: {e}")
        await update.message.reply_text(f"Channel info error: {e}")


async def channel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update channel settings for a game."""
    user = update.effective_user
    if not user or not update.message:
        if update.message:
            await update.message.reply_text("Channel settings failed: No user context.")
        return
    
    args = context.args if context.args is not None else []
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /channel_settings <game_id> <setting> <value>\n\n"
            "Settings:\n"
            "• auto_post_maps true/false\n"
            "• auto_post_broadcasts true/false\n"
            "• auto_post_notifications true/false\n"
            "• notification_level all/important/none\n\n"
            "Example: /channel_settings 42 auto_post_maps false"
        )
        return
    
    game_id = args[0]
    setting = args[1]
    value_str = args[2] if len(args) > 2 else None
    
    try:
        # Parse value
        if value_str is None:
            await update.message.reply_text("Please provide a value for the setting.")
            return
        
        # Convert string to appropriate type
        if setting in ["auto_post_maps", "auto_post_broadcasts", "auto_post_notifications"]:
            value = value_str.lower() in ["true", "1", "yes", "on"]
        elif setting == "notification_level":
            if value_str.lower() not in ["all", "important", "none"]:
                await update.message.reply_text(
                    "Notification level must be: all, important, or none"
                )
                return
            value = value_str.lower()
        else:
            await update.message.reply_text(f"Unknown setting: {setting}")
            return
        
        # Update settings
        settings = {setting: value}
        result = api_post(
            f"/games/{game_id}/channel/settings",
            settings
        )
        
        if result.get("status") == "ok":
            await update.message.reply_text(
                f"✅ Channel setting updated: {setting} = {value}"
            )
        else:
            await update.message.reply_text(f"❌ Failed to update settings: {result}")
            
    except Exception as e:
        logger.exception(f"Error updating channel settings: {e}")
        await update.message.reply_text(f"Channel settings error: {e}")

