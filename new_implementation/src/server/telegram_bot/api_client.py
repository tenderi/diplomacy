"""
API client utilities for communicating with the Diplomacy API server.

Two kinds of call live here:

- ``api_get`` / ``api_post`` / ``api_get_bytes`` -- plain request/response.
  Used for reads and for interactive writes where a player can simply retry
  (joining a game, the waiting list). When the server is unreachable they
  raise ``ApiUnreachableError``, whose ``str()`` is already fit to show.

- ``api_post_reliable`` -- for writes that must **never be lost**: orders and
  diplomatic messages. The request is written to the durable ``outbox`` first,
  then attempted; if the server cannot be reached the player is told it is
  queued, and ``drain_outbox_once`` (run from the bot's background loop)
  delivers it later, in order, with the original ``client_timestamp`` and an
  ``Idempotency-Key`` so a retry can never apply twice.
"""
import logging
import os
import random
import time
import requests
from dataclasses import dataclass
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from .config import API_URL
from .outbox import OutboxEntry, get_outbox

# BOT_SECRET is used to authenticate telegram_id-based requests to the API.
# Must match DIPLOMACY_BOT_SECRET on the server.
BOT_SECRET = os.environ.get("DIPLOMACY_BOT_SECRET", "")

# Request timeout (seconds) for all outbound calls to the API. A bot request
# that hangs forever on a stuck connection is an availability bug, not just
# lint noise (bandit B113) -- every requests.* call in this module and in
# telegram_bot/channel_commands.py uses this constant.
DEFAULT_API_TIMEOUT = 10

logger = logging.getLogger("diplomacy.telegram_bot.api_client")

# HTTP statuses that mean "the server is not able to answer right now", as
# opposed to "the server answered no". Only these (plus transport errors) put
# a queued write back in the queue; anything else is a definitive answer.
TRANSIENT_STATUSES = frozenset({502, 503, 504})

UNREACHABLE_MESSAGE = (
    "⚠️ The game server is unreachable right now (the link to the home server "
    "is down). Orders and messages you send are queued and delivered "
    "automatically when it is back -- see /queue. Everything else will work "
    "again once the server is reachable."
)


class ApiUnreachableError(requests.ConnectionError):
    """The API could not be reached at all (connection refused, DNS, timeout).

    Raised in place of the raw ``requests`` transport error so that every
    ``except Exception as e: reply_text(f"...: {e}")`` handler in the bot shows
    a player something useful instead of a urllib3 stack. Subclasses
    ``requests.ConnectionError`` (hence ``OSError``) so call sites that already
    catch those keep working.
    """

    def __init__(self, cause: BaseException) -> None:
        super().__init__(UNREACHABLE_MESSAGE)
        self.cause = cause

    def __str__(self) -> str:
        return UNREACHABLE_MESSAGE


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
    try:
        resp = requests.post(
            f"{API_URL}{endpoint}", json=payload, headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT
        )
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ApiUnreachableError(e) from e
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
    try:
        resp = requests.get(
            f"{API_URL}{endpoint}", headers=_bot_headers(), params=params, timeout=DEFAULT_API_TIMEOUT
        )
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ApiUnreachableError(e) from e
    _raise_for_status(resp)
    return resp.json()


def api_get_bytes(endpoint: str) -> bytes:
    """Make a GET request to the API and return the raw response body (e.g. a PNG).

    Mirrors ``api_get``'s auth handling (``X-Bot-Secret`` header via
    ``_bot_headers()``); unlike ``api_get`` the response is not JSON-decoded.
    """
    try:
        resp = requests.get(f"{API_URL}{endpoint}", headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ApiUnreachableError(e) from e
    _raise_for_status(resp)
    return resp.content


# ---------------------------------------------------------------------------
# Reliable writes: the durable outbox
# ---------------------------------------------------------------------------

DeliveryStatus = Literal["delivered", "queued", "rejected"]


@dataclass
class DeliveryResult:
    """What became of one outbox entry after a delivery attempt.

    ``delivered``: the server accepted it; ``response`` is its JSON body.
    ``queued``: the server could not be reached (or answered 502/503/504);
    the entry stays in the outbox and ``drain_outbox_once`` will retry.
    ``rejected``: the server answered with a 4xx; ``error`` is its ``detail``.
    """
    status: DeliveryStatus
    entry: OutboxEntry
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None


def attempt_delivery(entry: OutboxEntry) -> DeliveryResult:
    """One delivery attempt for ``entry``; records the outcome in the outbox.

    Adds the two fields that make a replay safe: ``client_timestamp`` (when the
    player composed it -- the entry's ``created_at``, *not* now) in the body,
    and ``Idempotency-Key`` in the headers. ``bot_secret`` is injected exactly
    as ``api_post`` does.
    """
    outbox = get_outbox()
    outbox.mark_inflight(entry.id)
    payload = dict(entry.payload)
    payload.setdefault("client_timestamp", entry.created_at.isoformat())
    if "telegram_id" in payload and BOT_SECRET:
        payload.setdefault("bot_secret", BOT_SECRET)
    headers = {**_bot_headers(), "Idempotency-Key": entry.key}
    try:
        resp = requests.post(
            f"{API_URL}{entry.endpoint}", json=payload, headers=headers, timeout=DEFAULT_API_TIMEOUT
        )
    except (requests.ConnectionError, requests.Timeout) as e:
        error = f"{type(e).__name__}: {e}"
        next_at = outbox.mark_retry(entry.id, error)
        logger.warning("Outbox #%d not delivered (%s); retry after %s", entry.id, type(e).__name__, next_at.isoformat())
        return DeliveryResult("queued", outbox.get(entry.id) or entry, error=error)
    if resp.status_code in TRANSIENT_STATUSES:
        error = f"HTTP {resp.status_code}"
        outbox.mark_retry(entry.id, error)
        logger.warning("Outbox #%d got %s; will retry", entry.id, error)
        return DeliveryResult("queued", outbox.get(entry.id) or entry, error=error)
    try:
        _raise_for_status(resp)
    except ApiError as e:
        outbox.mark_rejected(entry.id, str(e))
        logger.info("Outbox #%d rejected by server: %s", entry.id, e)
        return DeliveryResult("rejected", outbox.get(entry.id) or entry, error=str(e))
    try:
        body = resp.json()
    except ValueError:
        body = {}
    if not isinstance(body, dict):
        body = {"result": body}
    outbox.mark_delivered(entry.id, body)
    if resp.headers.get("Idempotent-Replayed"):
        logger.info("Outbox #%d had already been applied; server replayed its response", entry.id)
    logger.info("Outbox #%d delivered: %s", entry.id, entry.description)
    return DeliveryResult("delivered", outbox.get(entry.id) or entry, response=body)


def api_post_reliable(
    endpoint: str, json_data: dict, *, chat_id: int, description: str
) -> DeliveryResult:
    """POST a write that must never be lost.

    The request is recorded in the durable outbox **before** the attempt, so a
    crash or a dead link at any point leaves it queued rather than gone. The
    caller gets back exactly one of ``delivered`` / ``queued`` / ``rejected``
    and should tell the player which; for ``queued`` the background replayer
    (``drain_outbox_once``) later DMs the player with the eventual result.

    ``description`` is the human phrase used in those messages, e.g.
    ``"orders for game 12 (FRANCE): A PAR - BUR"``.
    """
    entry = get_outbox().enqueue(chat_id, endpoint, json_data, description)
    return attempt_delivery(entry)


def queued_reply(outcome: DeliveryResult) -> str:
    """The reply a player sees when their write had to be queued."""
    entry = outcome.entry
    return (
        f"📮 The game server is unreachable right now, so I have queued your "
        f"{entry.description}\n\n"
        f"Sent at {entry.sent_at_label()}. It will be delivered automatically, in "
        f"order, as soon as the server is back, and I will message you with the "
        f"result. /queue shows what is waiting."
    )


def drain_outbox_once(limit: int = 100) -> list[DeliveryResult]:
    """Retry every due entry, in id order, stopping at the first that is still
    unreachable so nothing overtakes an older write. Returns the results of
    the entries that *finished* (delivered or rejected) so the caller can
    report them to their players.
    """
    finished: list[DeliveryResult] = []
    for entry in get_outbox().due(limit=limit):
        result = attempt_delivery(entry)
        if result.status == "queued":
            break
        finished.append(result)
    return finished

