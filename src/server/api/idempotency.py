"""Replay-safe writes for the bot's durable queue (``Idempotency-Key``).

The bot never drops a player's write. If the API cannot be
reached it stores the request locally and retries until the API answers. That
retry loop is only correct if a request can be repeated without being applied
twice -- and a request *can* be applied yet look undelivered: the API commits
the broadcast, the connection drops before the response gets back, the bot sees a
timeout. Without this middleware the retry would post the broadcast again.

So the bot stamps every queued write with a fresh UUID in an
``Idempotency-Key`` header. The first time the API sees a key it reserves it
(a pending row, inserted on the key's primary key, so of two concurrent
requests exactly one wins), runs the route normally and stores
``(status, JSON body)`` under it; every later request with the same key gets
that stored response back verbatim, marked ``Idempotent-Replayed: true``, and
the route is not run. A same-key request arriving while the first still runs
(the bot timed out and replayed) gets a 503 with ``Retry-After`` and is
retried. A request that stores nothing (a 5xx, a non-JSON body, an exception)
releases its reservation, and one left by a worker that died is taken over
after ``IDEMPOTENCY_STALE_AFTER``. From the bot's side
the retry "succeeds" with the original result and it can report that result
to the player.

Scope rules, each deliberate:

- **Only with the bot secret.** The header is ignored unless ``X-Bot-Secret``
  matches. Otherwise any anonymous client could pre-fill the table, or replay
  a key to read back a response that was not theirs.
- **Only mutating methods.** GETs are already safe to repeat.
- **Only JSON responses below 500.** A 5xx is the API failing, not the request
  being wrong; the bot should retry it and a fresh attempt may well succeed.
  4xx responses *are* stored: "Sender not in game" will not change on retry
  and the bot needs a definitive answer to relay to the player.
- **An in-flight duplicate gets 503, not 409.** The bot treats 502/503/504
  as "still unreachable" (``api_client.TRANSIENT_STATUSES``): the write stays
  queued, no server error is counted, and the next replay gets the stored
  response. A 409 is a definitive answer (a stale phase) that the bot reports
  as rejected, which would tell the player their write failed when it is in
  fact being applied.
- **Keys expire.** ``DatabaseService.purge_idempotency_keys`` runs from the
  deadline scheduler; a queued request older than that has long since been
  either delivered or reported as failed.

The middleware reads the response body to store it, then re-emits it -- the
standard Starlette pattern for body-capturing middleware. Database calls go
through ``run_in_threadpool`` so the sync DAL does not stall the event loop.
"""
from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Callable, Optional

from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("diplomacy.server.api.idempotency")

HEADER = "Idempotency-Key"
REPLAYED_HEADER = "Idempotent-Replayed"
MAX_KEY_LENGTH = 128
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# A same-key request while the first is still running: 503 is one of the bot's
# transient statuses (``api_client.TRANSIENT_STATUSES``), so the write stays
# queued and its retry gets the stored response.
IN_FLIGHT_DETAIL = "A request with this Idempotency-Key is still being processed; retry later."
IN_FLIGHT_RETRY_AFTER_SECONDS = 5


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """See the module docstring."""

    def __init__(self, app: Any, *, get_db: Callable[[], Any], get_secret: Callable[[], str]) -> None:
        super().__init__(app)
        # Resolved lazily so importing this module never imports ``api.shared``
        # (which builds the DB engine) and tests can swap the service.
        self._get_db = get_db
        self._get_secret = get_secret

    def _accepts_key(self, request: Request) -> Optional[str]:
        key = request.headers.get(HEADER)
        if not key or request.method not in _MUTATING:
            return None
        if len(key) > MAX_KEY_LENGTH:
            return None
        secret = self._get_secret()
        supplied = request.headers.get("X-Bot-Secret")
        if not secret or not supplied or not hmac.compare_digest(supplied.encode(), secret.encode()):
            return None
        return key

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        key = self._accepts_key(request)
        if key is None:
            return await call_next(request)

        db = self._get_db()
        try:
            held = await run_in_threadpool(db.reserve_idempotency_key, key, request.url.path)
        except SQLAlchemyError as e:  # DB down: fall through and run the route; it will fail on its own
            logger.error("Idempotency reservation failed for key %s: %s", key, e)
            return await call_next(request)
        if held.get("pending"):
            logger.info("Idempotency-Key %s is still being processed; asked the client to retry", key)
            return JSONResponse(
                {"detail": IN_FLIGHT_DETAIL},
                status_code=503,
                headers={"Retry-After": str(IN_FLIGHT_RETRY_AFTER_SECONDS)},
            )
        if "reserved" not in held:
            logger.info("Replaying stored response for Idempotency-Key %s (%s)", key, held["endpoint"])
            return JSONResponse(
                held["response_json"],
                status_code=held["status_code"],
                headers={REPLAYED_HEADER: "true"},
            )

        # This request holds the key now, under ``token``. Every way out below
        # either stores a response under it or releases it; a release that
        # cannot run (the DB went away, the task was cancelled) leaves a
        # reservation that goes stale after ``IDEMPOTENCY_STALE_AFTER``.
        token = held["reserved"]
        stored = False
        try:
            response = await call_next(request)
            media_type = (response.headers.get("content-type") or "").split(";")[0].strip()
            if response.status_code >= 500 or media_type != "application/json":
                return response
            body = b"".join([chunk async for chunk in response.body_iterator])
            try:
                parsed = json.loads(body) if body else None
            except ValueError:
                parsed = None
            if parsed is not None:
                try:
                    await run_in_threadpool(
                        db.store_idempotent_response, key, request.url.path, response.status_code, parsed, token
                    )
                    stored = True
                except SQLAlchemyError as e:
                    logger.error("Failed to store idempotent response for key %s: %s", key, e)
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(
                content=body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )
        finally:
            if not stored:
                await self._release(db, key, token)

    @staticmethod
    async def _release(db: Any, key: str, token: Any) -> None:
        """Free this request's reservation of ``key`` so a retry runs the route."""
        try:
            await run_in_threadpool(db.release_idempotency_key, key, token)
        except SQLAlchemyError as e:
            logger.error("Failed to release Idempotency-Key %s: %s", key, e)
