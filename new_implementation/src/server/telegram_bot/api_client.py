"""
API client utilities for communicating with the Diplomacy API server.
"""
import logging
import random
import time
import requests
from typing import Optional
from urllib.parse import urlparse

from .config import API_URL

logger = logging.getLogger("diplomacy.telegram_bot.api_client")


def _validate_api_url(url: str) -> None:
    """Validate that the API URL is properly formatted."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid DIPLOMACY_API_URL: '{url}'")
    except Exception as e:
        raise ValueError(f"Invalid DIPLOMACY_API_URL: {e}")


def wait_for_api_health(max_attempts: int = 10, base_delay: float = 0.5) -> None:
    """Block until the API health endpoint responds OK or raise after retries.

    Tries /healthz first, then /health. Uses exponential backoff with jitter.
    """
    _validate_api_url(API_URL)
    endpoints = ["/healthz", "/health"]
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        for ep in endpoints:
            try:
                resp = requests.get(f"{API_URL}{ep}", timeout=2)
                if resp.ok:
                    logger.info(f"API health check succeeded on {ep} (attempt {attempt})")
                    return
                last_error = Exception(f"HTTP {resp.status_code} on {ep}")
            except Exception as e:
                last_error = e
        delay = base_delay * (2 ** (attempt - 1))
        # Add jitter up to 200ms
        delay += random.uniform(0, 0.2)
        logger.warning(f"API not healthy yet ({last_error}). Retrying in {delay:.2f}s...")
        time.sleep(delay)
    raise RuntimeError(
        f"Failed to reach API health endpoint at {API_URL} after {max_attempts} attempts: {last_error}"
    )


def api_post(endpoint: str, json_data: dict) -> dict:
    """Make a POST request to the API."""
    resp = requests.post(f"{API_URL}{endpoint}", json=json_data)
    resp.raise_for_status()
    return resp.json()


def api_get(endpoint: str) -> dict:
    """Make a GET request to the API."""
    resp = requests.get(f"{API_URL}{endpoint}")
    resp.raise_for_status()
    return resp.json()

