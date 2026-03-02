"""
Discord bot for Diplomacy - cross-platform companion to the Telegram bot.

Uses the same backend API (DIPLOMACY_API_URL). Enable with DIPLOMACY_DISCORD_BOT_TOKEN.
"""
from .bot import run_discord_bot

__all__ = ["run_discord_bot"]
