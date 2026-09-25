"""Log every server error the API returns, so none goes unnoticed.

An exception a route does not catch is logged by uvicorn, but a route that
catches one and raises ``HTTPException(500, detail=str(e))`` -- a common shape
here -- produces a 500 that no log line records. This middleware logs both at
ERROR, which puts them in the journal and, when ``DIPLOMACY_ADMIN_TELEGRAM_ID``
is set, in the maintainer's Telegram (``shared.install_admin_alerts``).
"""
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("diplomacy.server.errors")


class ServerErrorLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status: dict[str, int] = {}

        async def record_status(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = int(message["status"])
            await send(message)

        where = f"{scope.get('method', '?')} {scope.get('path', '?')}"
        try:
            await self.app(scope, receive, record_status)
        except Exception:  # logged and re-raised: Starlette still turns it into the 500
            logger.exception("Unhandled error on %s", where)
            raise
        if status.get("code", 0) >= 500:
            logger.error("HTTP %d on %s", status["code"], where)
