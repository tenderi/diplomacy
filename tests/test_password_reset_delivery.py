"""Forgot password: the link actually reaches the player, and can't be used to spam.

Production had no SMTP configured, so every reset link was created and then
dropped. Now a Telegram-linked account gets it from the bot (the durable
outbox) -- Telegram is preferred, email is only the fallback -- and requests
are rate-limited: per IP with a 429, per email silently (a 429 there would
reveal that the address has an account).
"""
import itertools
import smtplib
import time

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

_seq = itertools.count()


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("DIPLOMACY_PASSWORD_RESET_BASE_URL", "https://play.example.com")
    monkeypatch.delenv("DIPLOMACY_SMTP_HOST", raising=False)
    monkeypatch.delenv("DIPLOMACY_DEV_SHOW_RESET_LINK", raising=False)
    return TestClient(app)


def _account(client: TestClient, telegram: bool) -> tuple[str, str | None]:
    email = f"reset_{int(time.time() * 1000)}_{next(_seq)}@example.com"
    assert client.post("/auth/register", json={"email": email, "password": "oldpass123"}).status_code == 200
    tg = None
    if telegram:
        tg = str(int(time.time() * 1000) % 10**9 * 10 + next(_seq) % 10)
        user = db_service.get_user_by_email(email)
        db_service.set_user_telegram_id(int(user.id), tg)
    return email, tg


def test_a_telegram_linked_account_gets_the_link_from_the_bot(client: TestClient) -> None:
    email, tg = _account(client, telegram=True)
    with OutboxProbe() as probe:
        resp = client.post("/auth/forgot_password", json={"email": email})
    assert resp.status_code == 200 and "reset_link" not in resp.json()
    mine = probe.by_recipient().get(tg, [])
    assert len(mine) == 1 and "https://play.example.com/reset-password?token=" in mine[0]


def test_the_link_from_telegram_resets_the_password(client: TestClient) -> None:
    email, tg = _account(client, telegram=True)
    with OutboxProbe() as probe:
        client.post("/auth/forgot_password", json={"email": email})
    token = probe.by_recipient()[tg][0].split("token=")[1].split()[0]
    assert client.post("/auth/reset_password", json={"token": token, "new_password": "newpass456"}).status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": "newpass456"}).status_code == 200


def test_an_unknown_email_looks_exactly_the_same(client: TestClient) -> None:
    email, _ = _account(client, telegram=True)
    known = client.post("/auth/forgot_password", json={"email": email}).json()
    unknown = client.post("/auth/forgot_password", json={"email": "nobody-here@example.com"}).json()
    assert known == unknown


class TestTelegramFirstEmailAsFallback:
    @pytest.fixture
    def mails(self, monkeypatch) -> list[str]:
        """Every email the API tries to send (to whom)."""
        sent: list[str] = []
        monkeypatch.setenv("DIPLOMACY_SMTP_HOST", "smtp.example.com")
        from server.api.routes import auth

        monkeypatch.setattr(auth, "_send_password_reset_email_smtp", lambda to, _link, _host: sent.append(to))
        return sent

    def test_a_linked_account_gets_telegram_and_no_email(self, client: TestClient, mails: list[str]) -> None:
        email, tg = _account(client, telegram=True)
        with OutboxProbe() as probe:
            client.post("/auth/forgot_password", json={"email": email})
        assert probe.by_recipient().get(tg) and mails == []

    def test_an_unlinked_account_gets_email(self, client: TestClient, mails: list[str]) -> None:
        email, _ = _account(client, telegram=False)
        with OutboxProbe() as probe:
            client.post("/auth/forgot_password", json={"email": email})
        assert mails == [email] and not probe.messages()

    def test_email_is_used_when_telegram_cannot_be_queued(self, client: TestClient, mails: list[str], monkeypatch) -> None:
        from server.api.routes import auth

        monkeypatch.setattr(auth, "notify_user", lambda *_a, **_kw: None)  # the outbox write failed
        email, _ = _account(client, telegram=True)
        client.post("/auth/forgot_password", json={"email": email})
        assert mails == [email]

    def test_a_failing_mail_server_is_not_an_error(self, client: TestClient, monkeypatch) -> None:
        monkeypatch.setenv("DIPLOMACY_SMTP_HOST", "smtp.invalid")

        def refuse(*_a, **_kw):
            raise OSError("connection refused")

        monkeypatch.setattr(smtplib, "SMTP", refuse)
        email, _ = _account(client, telegram=False)
        assert client.post("/auth/forgot_password", json={"email": email}).status_code == 200


def test_one_address_gets_at_most_three_links_an_hour_and_nobody_can_tell(client: TestClient) -> None:
    email, tg = _account(client, telegram=True)
    with OutboxProbe() as probe:
        replies = [client.post("/auth/forgot_password", json={"email": email}) for _ in range(5)]
    assert [r.status_code for r in replies] == [200] * 5
    assert len({r.text for r in replies}) == 1
    assert len(probe.by_recipient()[tg]) == 3


def test_one_ip_is_limited_to_ten_requests_an_hour(client: TestClient) -> None:
    codes = [
        client.post("/auth/forgot_password", json={"email": f"x{n}@example.com"}).status_code for n in range(11)
    ]
    assert codes[:10] == [200] * 10 and codes[10] == 429
