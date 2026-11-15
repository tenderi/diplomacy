"""DL4: the exact ``/queue`` text, and the password-reset SMTP conversation."""
from __future__ import annotations

import asyncio
import email
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from server.api.routes import auth
from server.telegram_bot import notifications
from server.telegram_bot.outbox import reset_outbox_for_tests

pytestmark = pytest.mark.unit


def _queue_text(monkeypatch: pytest.MonkeyPatch, chat_id: int = 555) -> str:
    monkeypatch.setattr(notifications, "_api_reachable", True)
    update = Mock()
    update.effective_user = Mock(id=chat_id)
    update.message.reply_text = AsyncMock()
    asyncio.run(notifications.queue_status(update, Mock()))
    return update.message.reply_text.call_args[0][0]


def test_queue_lists_queued_and_finished_entries_exactly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outbox = reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
    old = outbox.enqueue(555, "/a", {}, "order A PAR - BUR")
    delivered = outbox.enqueue(555, "/b", {}, "order F BRE - MAO")
    rejected = outbox.enqueue(555, "/c", {}, "message to ITALY")
    waiting = outbox.enqueue(555, "/d", {}, "order A MUN H")
    outbox.enqueue(777, "/e", {}, "someone else's write")
    outbox.mark_delivered(delivered.id, {"ok": True})
    outbox.mark_rejected(rejected.id, "no such power")
    outbox.mark_inflight(waiting.id)
    outbox.mark_retry(waiting.id, "ConnectionError")
    # `old` was queued on an earlier day: its label carries the date.
    outbox._conn.execute(
        "UPDATE outbox SET created_at = ? WHERE id = ?", ("2026-09-08T14:02:00+00:00", old.id)
    )
    today = {e.id: outbox.get(e.id).sent_at_label() for e in (delivered, rejected, waiting)}
    assert all(len(label) == len("14:02 UTC") for label in today.values())

    assert _queue_text(monkeypatch) == "\n".join(
        [
            "🔗 Game server: ✅ reachable",
            "",
            "📮 Queued (2), oldest first:",
            f"• #{old.id} 2026-09-08 14:02 UTC: order A PAR - BUR",
            f"• #{waiting.id} {today[waiting.id]}: order A MUN H -- 1 attempt",
            "",
            "🕘 Recently finished:",
            f"• ❌ #{rejected.id} {today[rejected.id]}: message to ITALY",
            f"• ✅ #{delivered.id} {today[delivered.id]}: order F BRE - MAO",
        ]
    )


def test_queue_with_nothing_queued(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
    assert _queue_text(monkeypatch) == "🔗 Game server: ✅ reachable\n\n📮 Nothing queued."


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: int = 0) -> None:
        self.calls: list[tuple[str, Any]] = [("connect", (host, port, timeout))]
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        self.calls.append(("quit", None))

    def starttls(self) -> None:
        self.calls.append(("starttls", None))

    def login(self, user: str, password: str) -> None:
        self.calls.append(("login", (user, password)))

    def sendmail(self, from_addr: str, to: list[str], msg: str) -> None:
        self.calls.append(("sendmail", (from_addr, to, msg)))


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    monkeypatch.setattr(auth.smtplib, "SMTP", _FakeSMTP)
    for k in ("PORT", "USE_TLS", "USER", "PASSWORD", "FROM", "FROM_NAME"):
        monkeypatch.delenv(f"DIPLOMACY_SMTP_{k}", raising=False)
    return _FakeSMTP


def test_smtp_starttls_precedes_login_and_message_fields(
    fake_smtp: type[_FakeSMTP], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DIPLOMACY_SMTP_USER", "mailer@example.com")
    monkeypatch.setenv("DIPLOMACY_SMTP_PASSWORD", "s3cret")
    monkeypatch.setenv("DIPLOMACY_SMTP_FROM", "noreply@example.com")
    auth._send_password_reset_email_smtp("player@example.com", "https://x.test/reset?token=abc", "smtp.test")
    (smtp,) = fake_smtp.instances
    assert [c[0] for c in smtp.calls] == ["connect", "starttls", "login", "sendmail", "quit"]
    assert smtp.calls[0][1] == ("smtp.test", 587, 30)
    assert smtp.calls[2][1] == ("mailer@example.com", "s3cret")
    from_addr, recipients, raw = smtp.calls[3][1]
    assert from_addr == "noreply@example.com"
    assert recipients == ["player@example.com"]
    assert "From: Diplomacy <noreply@example.com>" in raw
    assert "To: player@example.com" in raw
    assert "Subject: Password reset - Diplomacy" in raw
    body = email.message_from_string(raw).get_payload(decode=True).decode()
    assert "https://x.test/reset?token=abc" in body


def test_smtp_without_tls_or_credentials_skips_both(fake_smtp: type[_FakeSMTP], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DIPLOMACY_SMTP_USE_TLS", "0")
    monkeypatch.setenv("DIPLOMACY_SMTP_PORT", "25")
    auth._send_password_reset_email_smtp("p@example.com", "https://x.test/r", "smtp.test")
    (smtp,) = fake_smtp.instances
    assert [c[0] for c in smtp.calls] == ["connect", "sendmail", "quit"]
    assert smtp.calls[0][1] == ("smtp.test", 25, 30)
    assert smtp.calls[1][1][0] == "noreply@diplomacy"
