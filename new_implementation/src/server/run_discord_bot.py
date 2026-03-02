#!/usr/bin/env python3
"""
Run the Diplomacy Discord bot. Uses the same API as the Telegram bot.

Requires: DIPLOMACY_DISCORD_BOT_TOKEN (Discord application bot token)
Optional: DIPLOMACY_API_URL (default http://localhost:8000), DIPLOMACY_DISCORD_PREFIX (default "!")
"""
import os
import sys
import logging

# Add project src to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_discord_bot")

if __name__ == "__main__":
    if not os.environ.get("DIPLOMACY_DISCORD_BOT_TOKEN"):
        logger.error("DIPLOMACY_DISCORD_BOT_TOKEN is not set. Set it to your Discord bot token.")
        sys.exit(1)
    from server.discord_bot.bot import run_discord_bot
    run_discord_bot()
