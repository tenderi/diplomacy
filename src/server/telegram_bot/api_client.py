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

# HTTP statuses that mean "the server is not able to answer right now": a
# gateway (nginx, Caddy) answering for an API that is down or restarting. These
# and transport errors keep a queued write in the queue for as long as the
# outage lasts.
TRANSIENT_STATUSES = frozenset({502, 503, 504})

# Any other 5xx is the API answering with an error of its own (a database blip,
# a bug). It is retried too -- ``server.api.idempotency`` never stores a 5xx
# under the key, so the retry runs the request again -- but only this many
# times (no answer and a gateway's 502/503/504 in between neither count nor
# reset the count): the queue is strictly ordered across every chat, so an entry
# that a route answers with 500 every time would hold back every player's
# orders behind it. With the outbox's backoff (5, 10, 20, 40, 60, 60, 60 s)
# eight answers take about four minutes, enough to outlast a database restart.
# A 4xx is a definitive answer and is never retried.
MAX_SERVER_ERRORS = 8

UNREACHABLE_MESSAGE = (
    "⚠️ The game server is unreachable right now (it may be restarting after "
    "an update). Orders and messages you send are queued and delivered "
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
    except ValueError as e:
        raise ValueError(f"Invalid DIPLOMACY_API_URL: {e}") from e
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid DIPLOMACY_API_URL: '{url}'")


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
            except requests.RequestException as e:
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


def _error_message(resp: requests.Response) -> str:
    """The player-facing text for an error response: never the URL.

    ``requests.HTTPError``'s own text ends ``"... for url: <url>"``, and a URL
    can carry query parameters that must not reach a chat. So the message is
    built only from the response: a string ``detail`` as the server worded it,
    a FastAPI validation error (``detail`` a list of ``{"msg": ...}``) as its
    messages joined, otherwise a generic line naming the status code.
    """
    try:
        body = resp.json()
    except ValueError:
        body = None
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, list):
        msgs = [str(item["msg"]) for item in detail if isinstance(item, dict) and item.get("msg")]
        if msgs:
            return "The request was not valid: " + "; ".join(msgs) + "."
    code = resp.status_code
    if code >= 500:
        return f"The server had a problem (HTTP {code}). Please try again shortly."
    return f"The server refused the request (HTTP {code})."


def _raise_for_status(resp: requests.Response) -> None:
    """Like ``resp.raise_for_status()``, but raises :class:`ApiError` whose
    message is :func:`_error_message`: the server's reason, never the request
    URL that ``HTTPError``'s own text would include."""
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise ApiError(_error_message(resp), response=resp, request=resp.request) from exc


def api_post(endpoint: str, json_data: dict) -> dict:
    """Make a POST request to the API.

    The bot secret travels only in the ``X-Bot-Secret`` header
    (``_bot_headers()``), which also vouches for a ``telegram_id`` in the
    body; it is never put in the body.
    """
    try:
        resp = requests.post(
            f"{API_URL}{endpoint}", json=json_data, headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT
        )
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ApiUnreachableError(e) from e
    _raise_for_status(resp)
    return resp.json()


def api_delete(endpoint: str) -> dict:
    """Make a DELETE request to the API, with the bot's X-Bot-Secret header."""
    try:
        resp = requests.delete(f"{API_URL}{endpoint}", headers=_bot_headers(), timeout=DEFAULT_API_TIMEOUT)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise ApiUnreachableError(e) from e
    _raise_for_status(resp)
    return resp.json()


def api_get(endpoint: str, telegram_id: Optional[str] = None, timeout: float = DEFAULT_API_TIMEOUT) -> dict:
    """Make a GET request to the API.

    A GET has no body, so routes that need telegram-id auth on a GET (e.g.
    ``GET /games/{id}/orders/{power}``) take ``telegram_id`` as a query param;
    passing it here adds it. The secret that vouches for it goes only in the
    ``X-Bot-Secret`` header (``_bot_headers()``), never in the URL, which ends
    up in access logs and error text. ``timeout`` is for a long-poll, which
    must outlast its ``wait``.
    """
    params: dict = {}
    if telegram_id is not None:
        params["telegram_id"] = telegram_id
    try:
        resp = requests.get(
            f"{API_URL}{endpoint}", headers=_bot_headers(), params=params, timeout=timeout
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

DeliveryStatus = Literal["delivered", "queued", "rejected", "failed"]


@dataclass
class DeliveryResult:
    """What became of one outbox entry after a delivery attempt.

    ``delivered``: the server accepted it; ``response`` is its JSON body.
    ``queued``: the server could not be reached, or answered with a 5xx; the
    entry stays in the outbox and ``drain_outbox_once`` will retry.
    ``server_error`` tells the two apart (true for a 5xx other than 502/503/504).
    ``rejected``: the server answered with a 4xx; ``error`` is its ``detail``.
    ``failed``: the server answered a 5xx ``MAX_SERVER_ERRORS`` times
    and the bot stopped trying. Only the replayer can see it: the first attempt
    is at most the first such answer.
    """
    status: DeliveryStatus
    entry: OutboxEntry
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    server_error: bool = False


def attempt_delivery(entry: OutboxEntry) -> DeliveryResult:
    """One delivery attempt for ``entry``; records the outcome in the outbox.

    Adds the two fields that make a replay safe: ``client_timestamp`` (when the
    player composed it -- the entry's ``created_at``, *not* now) in the body,
    and ``Idempotency-Key`` in the headers. The bot secret goes only in the
    ``X-Bot-Secret`` header, read at send time, so the stored entry never holds
    it and a write queued before a secret rotation replays with the current
    one. A ``bot_secret`` in the stored payload is dropped.
    """
    outbox = get_outbox()
    outbox.mark_inflight(entry.id)
    payload = {k: v for k, v in entry.payload.items() if k != "bot_secret"}
    payload.setdefault("client_timestamp", entry.created_at.isoformat())
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
    if resp.status_code >= 500:
        error = f"HTTP {resp.status_code}"
        server_errors = entry.server_errors + 1
        if server_errors >= MAX_SERVER_ERRORS:
            outbox.mark_failed(entry.id, f"{error}, {server_errors} server errors")
            logger.error("Outbox #%d got %s (%d server errors); giving up", entry.id, error, server_errors)
            return DeliveryResult("failed", outbox.get(entry.id) or entry, error=error, server_error=True)
        outbox.mark_retry(entry.id, error, server_error=True)
        logger.warning("Outbox #%d got %s (%d server errors); will retry", entry.id, error, server_errors)
        return DeliveryResult("queued", outbox.get(entry.id) or entry, error=error, server_error=True)
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
    caller gets back one of ``delivered`` / ``queued`` / ``rejected`` (never
    ``failed``, which takes ``MAX_SERVER_ERRORS`` attempts)
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
    if outcome.server_error:
        reason = "had an error just now"
        when = "I will retry it for a few minutes"
    else:
        reason = "is unreachable right now"
        when = "It will be delivered automatically, in order, as soon as the server is back"
    return (
        f"📮 The game server {reason}, so I have queued your "
        f"{entry.description}\n\n"
        f"Sent at {entry.sent_at_label()}. {when}, and I will message you with the "
        f"result. /queue shows what is waiting."
    )


def drain_outbox_once(limit: int = 100) -> list[DeliveryResult]:
    """Retry every due entry, in id order, stopping at the first that is still
    unreachable (or answered with a 5xx) so nothing overtakes an older write.
    Returns the results of the entries that *finished* (delivered, rejected or
    failed) so the caller can
    report them to their players.
    """
    finished: list[DeliveryResult] = []
    for entry in get_outbox().due(limit=limit):
        result = attempt_delivery(entry)
        if result.status == "queued":
            break
        finished.append(result)
    return finished

