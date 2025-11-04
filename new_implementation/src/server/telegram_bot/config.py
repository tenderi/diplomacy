"""
Telegram bot configuration and token handling.
"""
import logging
import os
import json

logger = logging.getLogger("diplomacy.telegram_bot.config")


def get_telegram_token() -> str:
    """Get Telegram bot token from environment, handling AWS Secrets Manager JSON format."""
    raw_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not raw_token:
        return ""

    # Check if token is in JSON format (from AWS Secrets Manager)
    if raw_token.startswith("{") and "TELEGRAM_BOT_TOKEN" in raw_token:
        try:
            token_data = json.loads(raw_token)
            return token_data.get("TELEGRAM_BOT_TOKEN", "")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse TELEGRAM_BOT_TOKEN as JSON: {raw_token}")
            return raw_token

    return raw_token


TELEGRAM_TOKEN = get_telegram_token()
API_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000")

# Debug token extraction for troubleshooting
logger.info(f"🔑 Raw TELEGRAM_BOT_TOKEN: '{os.environ.get('TELEGRAM_BOT_TOKEN', 'NOT_SET')[:50]}...'")
logger.info(f"🔑 Extracted TELEGRAM_TOKEN: '{TELEGRAM_TOKEN[:20] if TELEGRAM_TOKEN else 'EMPTY'}...'")
logger.info(f"🔑 Token format valid: {TELEGRAM_TOKEN.count(':') == 1 and len(TELEGRAM_TOKEN) > 20}")

