"""
Telegram bot commands for channel management.

This module provides commands for linking games to Telegram channels,
managing channel settings, and controlling channel integration.
"""
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .api_client import api_delete, api_get, api_post
from .game_context import GROUP_CHAT_TYPES, GameContextError, fetch_user_games, group_game, resolve_game_and_power, set_current_game
from .games import ensure_registered
from .utils import escape_markdown

logger = logging.getLogger("diplomacy.telegram_bot.channel_commands")


LINK_FROM_THE_GROUP = (
    "I link a game to a Telegram group only from inside that group: add me to the group "
    "and send /linkgroup <game id> there."
)


async def link_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/link_channel [game_id] -- the old name of /linkgroup, and like it only in
    the group being linked.

    It used to take any chat id in a private chat, so a player who knew a
    group's id could link their game to a group they aren't in, and that
    group's members could then neither start nor link a game of their own.
    """
    if not update.message:
        return
    chat = update.effective_chat
    if chat is None or chat.type not in GROUP_CHAT_TYPES:
        await update.message.reply_text(LINK_FROM_THE_GROUP)
        return
    await linkgroup(update, context)


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
# A game can belong to a group: the group gets each turn's orders and result maps,
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


def _replaced_note(link_result: Optional[dict]) -> str:
    """A group has one game: linking another moves the link. This names the
    game that lost it (from ``POST /games/{id}/channel/link``), or is empty."""
    replaced = (link_result or {}).get("replaced_game_id")
    return f"\n\nIt replaces Game {replaced}, which no longer belongs to this group." if replaced else ""


def _taken_text(game_id: str) -> str:
    return (
        f"This group already plays Game {game_id}, and a group has one game. "
        f"Only a player of Game {game_id} can replace it."
    )


NEWGAME_MODES = {"anonymous": True, "public": False}

NEWGAME_CHOICE = (
    "Pick how players are named -- it can't be changed once the game exists:\n\n"
    "• /newgame anonymous -- players are known only by their power; I relay "
    "messages and announcements naming the power alone.\n"
    "• /newgame public -- everyone's nickname is shown next to their power.\n\n"
    "Add random (/newgame anonymous random) to deal the powers at random: "
    "players join without choosing, and I seat each one in an open power."
)


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/newgame anonymous|public [random] (in a group) -- a game for this group; members join with a button.

    ``anonymous``: players are known only by their power (the group knows who
    its members are, but not who plays what). ``public``: nicknames are shown with
    powers. There is no default -- the choice is fixed for the game's life, so
    a bare /newgame explains both and creates nothing. ``random`` (optional, in
    either order) deals the powers at random: joiners don't choose one.

    The sender becomes the game's creator (they may leave seats to civil
    disorder with /dummy, and end a turn early). Turns are processed as soon as
    every order is in (auto-process; anyone can ask the table to wait).
    """
    user, chat = update.effective_user, update.effective_chat
    if not user or not update.message or not await _in_group(update, "newgame"):
        return
    args = [a.lower() for a in (context.args or [])]
    random_powers = "random" in args
    modes = [a for a in args if a != "random"]
    if len(modes) != 1 or modes[0] not in NEWGAME_MODES or len(args) != len(set(args)):
        await update.message.reply_text(NEWGAME_CHOICE)
        return
    anonymous = NEWGAME_MODES[modes[0]]
    try:
        # The new game would take the group from its game: only that game's
        # players may (the API refuses anyone else) -- check before creating one.
        current = group_game(chat.id)
        if current is not None and not any(str(g["game_id"]) == current for g in fetch_user_games(str(user.id))):
            await update.message.reply_text(_taken_text(current))
            return
        ensure_registered(user)
        # One call creates the game linked to this group, or nothing (409): a
        # link refused after the game existed used to leave it behind unlinked.
        linked = api_post("/games/create", {
            "map_name": "standard", "telegram_id": str(user.id), "auto_process": True,
            "anonymous": anonymous, "random_powers": random_powers,
            "channel_id": str(chat.id), "channel_name": chat.title,
        })
        game_id = str(linked["game_id"])
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Could not create a game: {e}")
        return
    set_current_game(str(user.id), game_id)
    naming = (
        "🕶️ *Anonymous:* players are known only by their power -- keep your pick to yourself."
        if anonymous
        else "👥 *Public:* everyone's nickname is shown next to their power (set yours with /nickname)."
    )
    pick = (
        "🎲 *Random powers:* tap the button to join and I'll deal you a power at random"
        if random_powers
        else "Tap the button to pick your power"
    )
    await update.message.reply_text(
        f"🎮 *Game {game_id} for this group!*\n\n"
        f"{naming}\n\n"
        f"{pick} -- it opens a private chat with me, where "
        f"you'll also send your orders. The game begins when all seven powers are taken; "
        f"with fewer players, the creator can leave seats to civil disorder "
        f"(/dummy {game_id} <power> in the private chat).\n\n"
        f"After every turn I'll post the orders and the result as maps here, and deadline reminders."
        f"{_replaced_note(linked)}",
        reply_markup=_join_button(context.bot.username, game_id),
        parse_mode='Markdown',
    )


async def linkgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/linkgroup [game_id] (in a group) -- attach one of your games to this group."""
    if not update.effective_user or not update.message or not await _in_group(update, "linkgroup"):
        return
    args = context.args or []
    await link_game_here(update, context, args[0] if args else None)


async def link_game_here(update: Update, context: ContextTypes.DEFAULT_TYPE, wanted: Optional[str]) -> None:
    """Link game ``wanted`` (or the sender's current game) to the group the
    command was typed in, if the sender plays it. The group is the chat's own:
    the only way a game is linked to a group (``/linkgroup``, ``/link_channel``,
    and ``/start link_<id>`` from the web page's "Link a Telegram group")."""
    user, chat = update.effective_user, update.effective_chat
    try:
        game_id, _power = resolve_game_and_power(str(user.id), wanted)
        # ``telegram_id``: the API lets only a player of the group's current
        # game (if it has one) move the group to another game.
        result = api_post(f"/games/{game_id}/channel/link", {
            "channel_id": str(chat.id), "channel_name": chat.title, "telegram_id": str(user.id),
        })
    except GameContextError as e:
        await update.message.reply_text(e.message)
        return
    except requests.RequestException as e:
        await update.message.reply_text(f"❌ Could not link the game: {e}")
        return
    await update.message.reply_text(
        f"✅ Game {game_id} now belongs to this group: after every turn a map of the orders "
        f"and one of the result, deadline reminders and players' broadcasts will be posted here, and only this group's "
        f"members can see or join it. Orders go to me in a private chat.{_replaced_note(result)}",
        reply_markup=_join_button(context.bot.username, game_id),
    )


async def unlinkgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/unlinkgroup [game_id] (in a group) -- detach a game from this group;
    without an id, the group's own game."""
    user, chat = update.effective_user, update.effective_chat
    if not user or not update.message or not await _in_group(update, "unlinkgroup"):
        return
    args = context.args or []
    try:
        wanted = args[0] if args else group_game(chat.id)
        if wanted is None:
            await update.message.reply_text("No game belongs to this group.")
            return
        game_id, _power = resolve_game_and_power(str(user.id), wanted)
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
