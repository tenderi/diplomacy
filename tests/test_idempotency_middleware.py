"""What ``IdempotencyMiddleware`` refuses to store (BH3) and how it holds a key
while its request runs (CP3).

``tests/test_idempotency.py`` drives the middleware through real routes against
Postgres; a route that *returns* a 5xx or a non-JSON body, or raises, is not
something the real API offers on demand, so these run it over a small app and a
fake store that records every call.
"""
from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.testclient import TestClient

from server.api.idempotency import MAX_KEY_LENGTH, REPLAYED_HEADER, IdempotencyMiddleware

pytestmark = [pytest.mark.unit]

SECRET = "middleware-test-secret"
BOT = {"X-Bot-Secret": SECRET}


class _Store:
    """Mirrors ``DatabaseService``'s reserve / store / release contract."""

    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.pending: dict[str, int] = {}  # key -> the holder's token
        self.lookups: list[str] = []
        self.released: list[str] = []
        self._tokens = 0

    def reserve_idempotency_key(self, key: str, endpoint: str) -> dict[str, Any]:
        self.lookups.append(key)
        if key in self.rows:
            return self.rows[key]
        if key in self.pending:
            return {"pending": True}
        self._tokens += 1
        self.pending[key] = self._tokens
        return {"reserved": self._tokens}

    def release_idempotency_key(self, key: str, token: int) -> None:
        assert self.pending.get(key) == token
        self.released.append(key)
        del self.pending[key]

    def store_idempotent_response(
        self, key: str, endpoint: str, status: int, body: Any, token: Optional[int] = None
    ) -> bool:
        assert self.pending.pop(key) == token
        self.rows[key] = {"status_code": status, "response_json": body, "endpoint": endpoint}
        return True


@pytest.fixture
def setup() -> tuple[TestClient, _Store, dict[str, int]]:
    store, runs = _Store(), {"n": 0}
    app = FastAPI()

    @app.post("/ok")
    def ok() -> dict[str, int]:
        runs["n"] += 1
        return {"run": runs["n"]}

    @app.post("/fail")
    def fail() -> JSONResponse:
        runs["n"] += 1
        return JSONResponse({"detail": "storage unavailable"}, status_code=503)

    @app.post("/text")
    def text() -> PlainTextResponse:
        runs["n"] += 1
        # A body that happens to parse as JSON: only the content type says no.
        return PlainTextResponse(str(runs["n"]))

    @app.post("/boom")
    def boom() -> dict[str, int]:
        runs["n"] += 1
        raise RuntimeError("route crashed")

    app.add_middleware(IdempotencyMiddleware, get_db=lambda: store, get_secret=lambda: SECRET)
    return TestClient(app, raise_server_exceptions=False), store, runs


def test_a_json_success_is_stored_and_replayed(setup: tuple[TestClient, _Store, dict[str, int]]) -> None:
    client, store, runs = setup
    first = client.post("/ok", headers={**BOT, "Idempotency-Key": "k-ok"})
    second = client.post("/ok", headers={**BOT, "Idempotency-Key": "k-ok"})
    assert (first.json(), second.json()) == ({"run": 1}, {"run": 1})
    assert second.headers.get(REPLAYED_HEADER) == "true"
    assert runs["n"] == 1
    assert store.rows == {"k-ok": {"status_code": 200, "response_json": {"run": 1}, "endpoint": "/ok"}}
    assert store.pending == {} and store.released == []


def test_a_5xx_response_is_not_stored(setup: tuple[TestClient, _Store, dict[str, int]]) -> None:
    client, store, runs = setup
    for _ in range(2):
        resp = client.post("/fail", headers={**BOT, "Idempotency-Key": "k-fail"})
        assert resp.status_code == 503
        assert resp.json() == {"detail": "storage unavailable"}
        assert resp.headers.get(REPLAYED_HEADER) is None
    assert runs["n"] == 2
    assert store.rows == {}
    assert store.pending == {} and store.released == ["k-fail", "k-fail"]


def test_a_route_that_raises_releases_its_reservation(setup: tuple[TestClient, _Store, dict[str, int]]) -> None:
    """CP3: an exception in the route must not leave the key reserved, or the
    bot's retry would get "still being processed" until the reservation went
    stale."""
    client, store, runs = setup
    for _ in range(2):
        resp = client.post("/boom", headers={**BOT, "Idempotency-Key": "k-boom"})
        assert resp.status_code == 500
    assert runs["n"] == 2
    assert store.rows == {} and store.pending == {}
    assert store.released == ["k-boom", "k-boom"]


def test_a_request_whose_key_is_reserved_gets_a_retryable_503(
    setup: tuple[TestClient, _Store, dict[str, int]],
) -> None:
    """CP3: while another request holds the key the route does not run; the
    503 is one of the bot's transient statuses, so the write stays queued."""
    client, store, runs = setup
    store.pending["k-busy"] = 99
    resp = client.post("/ok", headers={**BOT, "Idempotency-Key": "k-busy"})
    assert resp.status_code == 503
    assert resp.json() == {"detail": "A request with this Idempotency-Key is still being processed; retry later."}
    assert resp.headers.get("Retry-After") == "5"
    assert runs["n"] == 0
    # The holder's reservation is untouched.
    assert store.pending == {"k-busy": 99} and store.released == []


def test_a_non_json_response_is_not_stored(setup: tuple[TestClient, _Store, dict[str, int]]) -> None:
    client, store, runs = setup
    texts = [client.post("/text", headers={**BOT, "Idempotency-Key": "k-text"}).text for _ in range(2)]
    assert texts == ["1", "2"]
    assert store.rows == {} and store.pending == {}


def test_an_over_long_key_bypasses_the_middleware(setup: tuple[TestClient, _Store, dict[str, int]]) -> None:
    client, store, runs = setup
    longest, too_long = "a" * MAX_KEY_LENGTH, "a" * (MAX_KEY_LENGTH + 1)
    assert MAX_KEY_LENGTH == 128
    for _ in range(2):
        resp = client.post("/ok", headers={**BOT, "Idempotency-Key": too_long})
        assert resp.headers.get(REPLAYED_HEADER) is None
    assert runs["n"] == 2
    assert store.lookups == [] and store.rows == {}
    # One character shorter is a valid key.
    client.post("/ok", headers={**BOT, "Idempotency-Key": longest})
    assert list(store.rows) == [longest]
