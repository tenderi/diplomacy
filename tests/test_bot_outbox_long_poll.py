"""``GET /bot/outbox?wait=N``: the bot's long-poll (issue #225).

A poll with ``wait`` is held until a notification is committed (then returned
at once) or the wait runs out (then ``[]``). Within one API process the insert
wakes the waiter; a row committed by another uvicorn worker is found by the
periodic re-check. The access-log filter keeps those empty polls, and healthy
health checks, out of uvicorn's access log, and keeps every error.
"""
from __future__ import annotations

import logging
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import requests
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from persistence import database_service as dal
from server.api import app
from server.api import long_poll
from server.api import shared as api_shared
from server.api.access_log import QuietAccessLogFilter
from tests.conftest import _get_db_url

pytestmark = [pytest.mark.integration, pytest.mark.database,
              pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": "test_bot_secret_for_tests"}
NOTHING_EVER = 10**12  # an ``after_id`` no row reaches: the poll is always empty


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _since() -> int:
    return api_shared.db_service.max_bot_outbox_id()


def _notify_later(delay: float, telegram_id: str, text: str) -> threading.Thread:
    thread = threading.Timer(delay, api_shared.notify_user, args=(telegram_id, text))
    thread.start()
    return thread


def test_a_notification_committed_during_the_wait_is_returned_at_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The re-check is pushed past the wait: only the insert's wake-up can end it early.
    monkeypatch.setattr(long_poll, "RECHECK_SECONDS", 60.0)
    since = _since()
    timer = _notify_later(0.5, "77001", "turn processed")
    started = time.monotonic()
    r = client.get(f"/bot/outbox?after_id={since}&wait=20", headers=BOT)
    elapsed = time.monotonic() - started
    timer.join()
    assert r.status_code == 200
    assert [(i["telegram_id"], i["message"]) for i in r.json()["items"]] == [("77001", "turn processed")]
    assert r.headers["X-Outbox-Count"] == "1"
    assert 0.4 < elapsed < 5, elapsed
    assert long_poll.waiter_count() == 0


def test_a_row_from_another_worker_is_found_by_the_recheck(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Another uvicorn worker's insert wakes nobody here: no listeners for this one.
    monkeypatch.setattr(dal, "_bot_outbox_listeners", [])
    monkeypatch.setattr(long_poll, "RECHECK_SECONDS", 0.3)
    since = _since()
    timer = _notify_later(0.5, "77002", "from another worker")
    started = time.monotonic()
    r = client.get(f"/bot/outbox?after_id={since}&wait=20", headers=BOT)
    elapsed = time.monotonic() - started
    timer.join()
    assert [i["message"] for i in r.json()["items"]] == ["from another worker"]
    assert elapsed < 5, elapsed


def test_an_empty_long_poll_returns_nothing_after_the_wait(client: TestClient) -> None:
    started = time.monotonic()
    r = client.get(f"/bot/outbox?after_id={NOTHING_EVER}&wait=1.5", headers=BOT)
    elapsed = time.monotonic() - started
    assert r.status_code == 200
    assert r.json() == {"items": [], "count": 0}
    assert r.headers["X-Outbox-Count"] == "0"
    assert 1.4 < elapsed < 5, elapsed
    assert long_poll.waiter_count() == 0


def test_without_wait_the_poll_answers_at_once(client: TestClient) -> None:
    started = time.monotonic()
    r = client.get(f"/bot/outbox?after_id={NOTHING_EVER}", headers=BOT)
    assert r.json() == {"items": [], "count": 0}
    assert time.monotonic() - started < 1


def test_wait_is_bounded(client: TestClient) -> None:
    assert client.get("/bot/outbox?wait=61", headers=BOT).status_code == 422
    assert client.get("/bot/outbox?wait=-1", headers=BOT).status_code == 422


# ---------------------------------------------------------------------------
# The access log
# ---------------------------------------------------------------------------

def _access_record(method: str, path: str, status: int) -> logging.LogRecord:
    """A record shaped exactly like uvicorn's access line."""
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 0, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", method, path, "1.1", status), None,
    )


def test_the_filter_drops_a_healthy_healthz_and_keeps_its_errors() -> None:
    f = QuietAccessLogFilter()
    assert f.filter(_access_record("GET", "/healthz", 200)) is False
    assert f.filter(_access_record("GET", "/health", 200)) is False
    assert f.filter(_access_record("GET", "/healthz", 500)) is True
    assert f.filter(_access_record("GET", "/health", 503)) is True
    assert f.filter(_access_record("GET", "/games", 200)) is True
    # Not marked empty by the middleware: a poll that delivered something stays.
    assert f.filter(_access_record("GET", "/bot/outbox?limit=50&wait=25", 200)) is True


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(record.getMessage())


@pytest.fixture
def live_api() -> Iterator[str]:
    """The real app under a real uvicorn, so the real access logger runs."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, lifespan="off", log_level="info"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "uvicorn did not start"
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()


def test_uvicorn_logs_errors_and_deliveries_but_not_healthy_noise(
    live_api: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    collect = _Collect()
    access = logging.getLogger("uvicorn.access")
    access.addHandler(collect)
    try:
        assert requests.get(f"{live_api}/healthz", timeout=10).status_code == 200
        empty = requests.get(f"{live_api}/bot/outbox?after_id={NOTHING_EVER}", headers=BOT, timeout=10)
        assert empty.json()["count"] == 0
        since = _since()
        api_shared.notify_user("77003", "for the log")
        full = requests.get(f"{live_api}/bot/outbox?after_id={since}", headers=BOT, timeout=10)
        assert full.json()["count"] == 1

        def broken(_sql: str) -> None:
            raise SQLAlchemyError("database gone")

        monkeypatch.setattr(api_shared.db_service, "execute_query", broken)
        assert requests.get(f"{live_api}/healthz", timeout=10).status_code == 500
    finally:
        access.removeHandler(collect)
    assert [line.split(" - ", 1)[1] for line in collect.lines] == [
        f'"GET /bot/outbox?after_id={since} HTTP/1.1" 200',
        '"GET /healthz HTTP/1.1" 500',
    ]
