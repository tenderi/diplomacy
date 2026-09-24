"""
Telegram bot commands for channel management.

This module provides commands for linking games to Telegram channels,
managing channel settings, and controlling channel integration.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .api_client import api_delete, api_get, api_post
from .game_context import GameContextError, fetch_user_games, resolve_game_and_power, set_current_game
from .games import ensure_registered
from .utils import escape_markdown

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
        # Only a player may: the bot calls the API with its own secret, which the API
        # trusts. (An admin uses the API's admin token, not a Telegram id here.)
        user_id = str(user.id)
        if not any(str(g["game_id"]) == game_id for g in fetch_user_games(user_id)):
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
        user_id = str(user.id)
        if not any(str(g["game_id"]) == game_id for g in fetch_user_games(user_id)):
            await update.message.reply_text(
                f"You must be a player in game {game_id} to unlink a channel."
            )
            return
        
        # Unlink channel (the route needs the bot's secret since v3.0.2)
        result = api_delete(f"/games/{game_id}/channel/unlink")
        
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
        # Channel name is set by whoever administers the Telegram channel --
        # not trusted input -- and this reply is sent with parse_mode='Markdown'.
        channel_name = escape_markdown(channel_info.get('channel_name')) or 'N/A'
        info_text = (
            f"📢 *Channel Information - Game {game_id}*\n\n"
            f"Channel ID: `{channel_info.get('channel_id')}`\n"
            f"Channel Name: {channel_name}\n\n"
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



# --- Playing in a Telegram group (v3.0.2) -----------------------------------------
#
# A game can belong to a group: the group gets turn results with the map,
# deadline reminders and players' broadcasts, and only its members can see or
# join the game (games.may_join). Orders and private messages always go to the
# bot in a private chat; app.py refuses those commands inside a group.


def _join_button(bot_username: str, game_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        "🎮 Join this game (private chat)", url=f"https://t.me/{bot_username}?start=join_{game_id}"
    )]])


async def _in_group(update: Update, command: str) -> bool:
    """Is this a group chat? If not, say where the command belongs."""
    chat = update.effective_chat
    if chat is not None and chat.type in ("group", "supergroup"):
        return True
    await update.message.reply_text(
        f"/{command} works inside a Telegram group: add me to your group and send it there."
    )
    return False


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/newgame (in a group) -- a game for this group; members join with a button.

    The sender becomes the game's creator (they may leave seats to civil
    disorder with /dummy, and end a turn early). Turns are processed as soon as
    every order is in (auto-process; anyone can ask the table to wait).
    """
    user, chat = update.effective_user, update.effective_chat
    if not user or not update.message or not await _in_group(update, "newgame"):
        return
    try:
        ensure_registered(user)
        game_id = str(api_post("/games/create", {
            "map_name": "standard", "telegram_id": str(user.id), "auto_process": True,
        })["game_id"])
        api_post(f"/games/{game_id}/channel/link", {"channel_id": str(chat.id), "channel_name": chat.title})
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Could not create a game: {e}")
        return
    set_current_game(str(user.id), game_id)
    await update.message.reply_text(
        f"🎮 *Game {game_id} for this group!*\n\n"
        f"Tap the button to pick your power -- it opens a private chat with me, where "
        f"you'll also send your orders. The game begins when all seven powers are taken; "
        f"with fewer players, the creator can leave seats to civil disorder "
        f"(/dummy {game_id} <power> in the private chat).\n\n"
        f"Turn results, the map and deadline reminders will appear here.",
        reply_markup=_join_button(context.bot.username, game_id),
        parse_mode='Markdown',
    )


async def linkgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/linkgroup [game_id] (in a group) -- attach one of your games to this group."""
    user, chat = update.effective_user, update.effective_chat
    if not user or not update.message or not await _in_group(update, "linkgroup"):
        return
    args = context.args or []
    try:
        game_id, _power = resolve_game_and_power(str(user.id), args[0] if args else None)
        api_post(f"/games/{game_id}/channel/link", {"channel_id": str(chat.id), "channel_name": chat.title})
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Could not link the game: {e}")
        return
    await update.message.reply_text(
        f"✅ Game {game_id} now belongs to this group: turn results with the map, deadline "
        f"reminders and players' broadcasts will be posted here, and only this group's "
        f"members can see or join it. Orders go to me in a private chat.",
        reply_markup=_join_button(context.bot.username, game_id),
    )


async def unlinkgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unlinkgroup [game_id] (in a group) -- detach a game from this group."""
    user, chat = update.effective_user, update.effective_chat
    if not user or not update.message or not await _in_group(update, "unlinkgroup"):
        return
    args = context.args or []
    try:
        game_id, _power = resolve_game_and_power(str(user.id), args[0] if args else None)
        info = api_get(f"/games/{game_id}/channel") or {}
        if str(info.get("channel_id")) != str(chat.id):
            await update.message.reply_text(f"Game {game_id} isn't linked to this group.")
            return
        api_delete(f"/games/{game_id}/channel/unlink")
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Could not unlink the game: {e}")
        return
    await update.message.reply_text(f"Game {game_id} is no longer linked to this group.")
