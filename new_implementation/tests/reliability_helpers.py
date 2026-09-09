"""Shared helpers for tests of the split-deployment reliability paths.

``OutboxProbe`` -- server side. Notifications are no longer HTTP calls that a
test can mock; they are rows in ``bot_outbox``. The probe records the highest
row id when entered and reads back every row queued after that, so a test can
ask "who was notified by this action" the same way it used to ask a patched
``requests.post``.

``delivered`` / ``queued`` / ``rejected`` -- bot side. Build a ``DeliveryResult``
for tests that patch ``api_post_reliable`` on a handler module.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from server.api import shared as api_shared
from server.telegram_bot.api_client import DeliveryResult
from server.telegram_bot.outbox import OutboxEntry


class OutboxProbe:
    def __enter__(self) -> "OutboxProbe":
        self.since = api_shared.db_service.max_bot_outbox_id()
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def rows(self) -> list[dict[str, Any]]:
        return api_shared.db_service.fetch_pending_bot_notifications(limit=500, after_id=self.since)

    def recipients(self) -> set[str]:
        return {str(r["telegram_id"]) for r in self.rows()}

    def by_recipient(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for r in self.rows():
            out.setdefault(str(r["telegram_id"]), []).append(r["message"])
        return out

    def messages(self) -> list[str]:
        return [r["message"] for r in self.rows()]


def _entry(description: str = "test write", chat_id: int = 12345) -> OutboxEntry:
    return OutboxEntry(
        id=1, key="test-key", chat_id=chat_id, endpoint="/test", payload={},
        description=description, created_at=datetime.now(timezone.utc), state="pending",
    )


def delivered(response: Optional[dict[str, Any]] = None, **kw: Any) -> DeliveryResult:
    return DeliveryResult("delivered", _entry(**kw), response=response if response is not None else {})


def queued(error: str = "ConnectionError", **kw: Any) -> DeliveryResult:
    return DeliveryResult("queued", _entry(**kw), error=error)


def rejected(error: str = "Not authenticated", **kw: Any) -> DeliveryResult:
    return DeliveryResult("rejected", _entry(**kw), error=error)
