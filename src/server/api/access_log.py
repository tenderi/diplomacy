"""Keep healthy health checks and empty bot polls out of uvicorn's access log.

Before this, 91% of the API's access-log lines were the bot's empty
``GET /bot/outbox`` polls, and the Docker healthcheck's ``/healthz`` added
more. Neither says anything while it succeeds. Dropped, when the status is
below 400:

* ``/healthz`` and ``/health``;
* ``GET /bot/outbox`` that returned no rows (``X-Outbox-Count: 0``).

Every error on those paths is still logged, and so is a poll that handed the
bot something.

uvicorn writes the access line inside the ``send`` of ``http.response.start``
and passes only client, method, path, HTTP version and status, so the record
cannot say whether a poll was empty. ``QuietAccessLogMiddleware`` (the
outermost middleware) reads the route's ``X-Outbox-Count`` header from that
message and marks the current context just for the duration of the ``send``;
``QuietAccessLogFilter`` on the ``uvicorn.access`` logger reads the mark.
The filter is installed from the app module, so it applies however uvicorn
is started.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

OUTBOX_COUNT_HEADER = "X-Outbox-Count"
OUTBOX_PATH = "/bot/outbox"
QUIET_PATHS = frozenset({"/healthz", "/health"})

_empty_outbox_poll: ContextVar[bool] = ContextVar("empty_outbox_poll", default=False)


class QuietAccessLogMiddleware:
    """Marks an empty ``GET /bot/outbox`` response for ``QuietAccessLogFilter``."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "GET" or scope.get("path") != OUTBOX_PATH:
            await self.app(scope, receive, send)
            return

        async def mark_empty(message: Message) -> None:
            if message["type"] != "http.response.start":
                await send(message)
                return
            header = OUTBOX_COUNT_HEADER.lower().encode()
            empty = any(k.lower() == header and v == b"0" for k, v in message.get("headers", []))
            token = _empty_outbox_poll.set(empty)
            try:
                await send(message)
            finally:
                _empty_outbox_poll.reset(token)

        await self.app(scope, receive, mark_empty)


class QuietAccessLogFilter(logging.Filter):
    """Drops successful health checks and empty outbox polls from ``uvicorn.access``."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn's format: '%s - "%s %s HTTP/%s" %d' (client, method, path, version, status)
        if not isinstance(args, tuple) or len(args) != 5:
            return True
        _client, method, path_with_query, _version, status = args
        if not isinstance(status, int) or status >= 400:
            return True
        path = str(path_with_query).split("?", 1)[0]
        if path in QUIET_PATHS:
            return False
        if method == "GET" and path == OUTBOX_PATH and _empty_outbox_poll.get():
            return False
        return True


def install_access_log_filter() -> None:
    """Attach ``QuietAccessLogFilter`` to ``uvicorn.access`` (once)."""
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, QuietAccessLogFilter) for f in access.filters):
        access.addFilter(QuietAccessLogFilter())
