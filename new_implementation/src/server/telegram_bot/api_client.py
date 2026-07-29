"""
API client utilities for communicating with the Diplomacy API server.
"""
import logging
import os
import random
import time
import requests
from typing import Optional
from urllib.parse import urlparse

from .config import API_URL

# BOT_SECRET is used to authenticate telegram_id-based requests to the API.
# Must match DIPLOMACY_BOT_SECRET on the server.
BOT_SECRET = os.environ.get("DIPLOMACY_BOT_SECRET", "")

# Request timeout (seconds) for all outbound calls to the API. A bot request
# that hangs forever on a stuck connection is an availability bug, not just
# lint noise (bandit B113) -- every requests.* call in this module and in
# telegram_bot/channel_commands.py uses this constant.
DEFAULT_API_TIMEOUT = 10

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


def _bot_headers() -> dict:
    """Return X-Bot-Secret header when the secret is configured."""
    if BOT_SECRET:
        return {"X-Bot-Secret": BOT_SECRET}
    return {}


class ApiError(requests.HTTPError):
    """An HTTP error from the API, with the server's ``detail`` message (if
    any) folded into the exception's string.

    FastAPI error responses are shaped ``{"detail": "<human-readable
    reason>"}`` -- "Power already taken", "Sender not in game", "Not
    authenticated", etc (see ``src/server/api/routes/*.py``). Plain
    ``requests.HTTPError.__str__`` only ever produces the generic ``"401
    Client Error: Unauthorized for url: ..."`` line, discarding that reason
    entirely -- and every ``except Exception as e: reply_text(f"...: {e}")``
    handler across the bot package (dozens of them) relies on ``str(e)``
    being something worth showing a player. Subclassing ``HTTPError``
    (rather than a bare ``Exception``) means call sites that already catch
    ``requests.HTTPError`` specifically (``link_account.py``, which reads
    ``e.response.status_code``/``.json()`` itself) keep working unchanged --
    ``.response`` is still populated -- while every generic ``except
    Exception`` at the other ~40 call sites starts showing the real reason
    for free.
    """


def _raise_for_status(resp: requests.Response) -> None:
    """Like ``resp.raise_for_status()``, but raises :class:`ApiError` whose
    message is the server's JSON ``detail`` field when present, falling back
    to the normal ``HTTPError`` text otherwise (non-JSON body, or JSON
    without a ``detail`` key)."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        detail: Optional[str] = None
        try:
            body = resp.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("detail"), str):
            detail = body["detail"]
        message = detail if detail else str(exc)
        raise ApiError(message, response=resp, request=resp.request) from exc


def api_post(endpoint: str, json_data: dict) -> dict:
    """Make a POST request to the API.

    Sends X-Bot-Secret header for server-side auth on management endpoints.
    If the payload includes a ``telegram_id`` field, ``bot_secret`` is also
    injected into the body for telegram_id-based auth flows.
    """
    payload = dict(json_data)
    if "telegram_id" in payload and BOT_SECRET:
        payload.setdefault("bot_secret", BOT_SECRET)
    resp = requests.post(
        f"{API_URL}{endpoint}", json=payload, headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT
    )
    _raise_for_status(resp)
    return resp.json()


def api_get(endpoint: str, telegram_id: Optional[str] = None) -> dict:
    """Make a GET request to the API.

    Mirrors ``api_post``'s ``bot_secret`` injection, but via the query string:
    a GET has no body, so routes that need telegram-id auth on a GET (e.g.
    ``GET /games/{id}/orders/{power}``) read ``telegram_id``/``bot_secret`` as
    query params instead. Passing ``telegram_id`` here adds both to the
    request under those exact names; omit it for endpoints that don't need
    per-user auth (public reads, or ones using the ``X-Bot-Secret`` header
    alone).
    """
    params: dict = {}
    if telegram_id is not None:
        params["telegram_id"] = telegram_id
        if BOT_SECRET:
            params["bot_secret"] = BOT_SECRET
    resp = requests.get(
        f"{API_URL}{endpoint}", headers=_bot_headers(), params=params, timeout=DEFAULT_API_TIMEOUT
    )
    _raise_for_status(resp)
    return resp.json()


def api_get_bytes(endpoint: str) -> bytes:
    """Make a GET request to the API and return the raw response body (e.g. a PNG).

    Mirrors ``api_get``'s auth handling (``X-Bot-Secret`` header via
    ``_bot_headers()``); unlike ``api_get`` the response is not JSON-decoded.
    """
    resp = requests.get(f"{API_URL}{endpoint}", headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT)
    _raise_for_status(resp)
    return resp.content

