"""Server-side outbox: ``notify_user`` + ``/bot/outbox`` (Track J).

Every player DM is a ``bot_outbox`` row the bot pulls and acks. These tests
pin the contract the bot's notification loop relies on: rows come back oldest
first and undelivered only, acking is idempotent, permanent failures are
recorded but not re-offered, and none of it is reachable without the bot
secret.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from tests.conftest import _get_db_url

pytestmark = [pytest.mark.integration, pytest.mark.database,
              pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": "test_bot_secret_for_tests"}


@pytest.fixture
def client():
    return TestClient(app)


def _since() -> int:
    return api_shared.db_service.max_bot_outbox_id()


def test_notify_user_queues_a_row_and_skips_non_numeric_ids():
    since = _since()
    row_id = api_shared.notify_user("123456", "hello")
    assert row_id is not None and row_id > since
    assert api_shared.notify_user("u1", "test fixture id") is None
    rows = api_shared.db_service.fetch_pending_bot_notifications(after_id=since)
    assert [(r["telegram_id"], r["message"], r["kind"], r["attempts"]) for r in rows] == [
        ("123456", "hello", "dm", 0)
    ]
    assert rows[0]["created_at"]


def test_outbox_endpoints_require_the_bot_secret(client):
    assert client.get("/bot/outbox").status_code == 401
    assert client.get("/bot/outbox", headers={"X-Bot-Secret": "wrong"}).status_code == 401
    assert client.post("/bot/outbox/ack", json={"delivered": []}).status_code == 401
    # A logged-in browser user is not the bot.
    reg = client.post("/auth/register", json={"email": "outbox_user@example.com", "password": "testpass123"})
    if reg.status_code == 200:
        token = reg.json()["access_token"]
        r = client.get("/bot/outbox", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


def test_pull_then_ack_removes_rows_and_ack_is_idempotent(client):
    since = _since()
    a = api_shared.notify_user("9001", "first")
    b = api_shared.notify_user("9002", "second")

    page = client.get(f"/bot/outbox?after_id={since}&limit=10", headers=BOT).json()
    assert [i["id"] for i in page["items"]] == [a, b]
    assert page["items"][0]["message"] == "first"

    r = client.post("/bot/outbox/ack", json={"delivered": [a]}, headers=BOT)
    assert r.status_code == 200 and r.json()["updated"] == 1
    page = client.get(f"/bot/outbox?after_id={since}", headers=BOT).json()
    assert [i["id"] for i in page["items"]] == [b]

    # Acking again is a no-op, not an error (the bot may re-send after a lost ack).
    r = client.post("/bot/outbox/ack", json={"delivered": [a, b]}, headers=BOT)
    assert r.json()["updated"] == 1
    assert client.get(f"/bot/outbox?after_id={since}", headers=BOT).json()["items"] == []


def test_permanent_failure_is_acked_with_the_error_kept(client):
    since = _since()
    row = api_shared.notify_user("9003", "blocked user")
    r = client.post("/bot/outbox/ack", json={"delivered": [], "failed": {str(row): "Forbidden: bot blocked"}}, headers=BOT)
    assert r.status_code == 200 and r.json()["updated"] == 1
    assert client.get(f"/bot/outbox?after_id={since}", headers=BOT).json()["items"] == []
    # Auditable: the row still exists with the error and one attempt.
    from persistence.database import BotOutboxModel
    with api_shared.db_service.session_factory() as session:
        stored = session.get(BotOutboxModel, row)
        assert stored.delivered_at is not None
        assert stored.last_error == "Forbidden: bot blocked"
        assert stored.attempts == 1


def test_transient_attempt_is_recorded_but_row_stays_pending(client):
    since = _since()
    row = api_shared.notify_user("9004", "retry me")
    api_shared.db_service.record_bot_notification_attempt(row, "NetworkError")
    items = client.get(f"/bot/outbox?after_id={since}", headers=BOT).json()["items"]
    assert [(i["id"], i["attempts"]) for i in items] == [(row, 1)]


def test_housekeeping_purges_only_old_delivered_rows():
    from datetime import timedelta
    from persistence.database import BotOutboxModel, utcnow_naive
    since = _since()
    old = api_shared.notify_user("9005", "old delivered")
    fresh = api_shared.notify_user("9006", "fresh delivered")
    pending = api_shared.notify_user("9007", "still pending")
    api_shared.db_service.ack_bot_notifications([old, fresh])
    with api_shared.db_service.session_factory() as session:
        session.get(BotOutboxModel, old).delivered_at = utcnow_naive() - timedelta(days=30)
        session.commit()

    api_shared.run_housekeeping()

    with api_shared.db_service.session_factory() as session:
        assert session.get(BotOutboxModel, old) is None
        assert session.get(BotOutboxModel, fresh) is not None
        assert session.get(BotOutboxModel, pending).delivered_at is None
    assert [i["id"] for i in api_shared.db_service.fetch_pending_bot_notifications(after_id=since)] == [pending]


def test_stats_reports_pending_count(client):
    since = _since()
    api_shared.notify_user("9008", "x")
    stats = client.get("/bot/outbox/stats", headers=BOT).json()
    assert stats["pending"] >= 1 and stats["oldest_id"] is not None
    assert client.get("/bot/outbox/stats").status_code == 401
    _ = since
