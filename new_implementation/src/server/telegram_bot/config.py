"""
Telegram bot configuration and token handling.
"""
import os


def get_telegram_token() -> str:
    """The bot token from ``TELEGRAM_BOT_TOKEN`` (empty string if unset).

    Plain value only. An AWS-Secrets-Manager JSON form used to be accepted
    here, and the raw value was logged at INFO -- the first 50 characters, which
    is the whole token. Both went with the AWS layout (``v2.7.80``); the token
    is never logged.
    """
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


TELEGRAM_TOKEN = get_telegram_token()
API_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000")
