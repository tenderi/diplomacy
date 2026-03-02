"""
API client for Discord bot - calls the same Diplomacy backend as the Telegram bot.
"""
import logging
import requests
from typing import Any, Optional

from .config import API_URL

logger = logging.getLogger("diplomacy.discord_bot.api_client")


def api_get(endpoint: str) -> Any:
    """GET request to the Diplomacy API."""
    url = f"{API_URL}{endpoint}" if endpoint.startswith("/") else f"{API_URL}/{endpoint}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"API GET {endpoint}: {e}")
        raise


def api_post(endpoint: str, json_data: dict) -> Any:
    """POST request to the Diplomacy API."""
    url = f"{API_URL}{endpoint}" if endpoint.startswith("/") else f"{API_URL}/{endpoint}"
    try:
        resp = requests.post(url, json=json_data, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning(f"API POST {endpoint}: {e}")
        raise
