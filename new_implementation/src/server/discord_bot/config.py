"""
Discord bot configuration.
"""
import logging
import os

logger = logging.getLogger("diplomacy.discord_bot.config")

# Token from env; if not set, Discord bot will not start
DISCORD_BOT_TOKEN = os.environ.get("DIPLOMACY_DISCORD_BOT_TOKEN", "").strip()
API_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000").rstrip("/")

# Command prefix for text commands (e.g. !games, !status)
COMMAND_PREFIX = os.environ.get("DIPLOMACY_DISCORD_PREFIX", "!").strip() or "!"
