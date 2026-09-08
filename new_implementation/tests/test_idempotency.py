"""``Idempotency-Key`` replay (``server/api/idempotency.py``, Track J).

A queued write the bot retries must never apply twice. Driven through a real
route -- a broadcast -- because the observable that matters is "one message
row and one set of notifications", not "the middleware ran".
"""
from __future__ import annotations

import itertools
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe

pytestmark = [pytest.mark.integration, pytest.mark.database,
              pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

SECRET = "test_bot_secret_for_tests"
BOT = {"X-Bot-Secret": SECRET}
_seq = itertools.count(1)


@pytest.fixture
def client():
    return TestClient(app)


def _game_with_two_bot_players(client):
    """A game where FRANCE and GERMANY are Telegram-linked bot users."""
    stamp = f"{int(time.time() * 1000000)}_{next(_seq)}"
    digits = f"{int(time.time() * 1000) % 10**7:07d}{next(_seq) % 100:02d}"
    sender, other = f"71{digits}", f"72{digits}"
    for tid, name in ((sender, "Sender"), (other, "Other")):
        r = client.post("/users/persistent_register",
                        json={"telegram_id": tid, "full_name": name, "bot_secret": SECRET})
        assert r.status_code == 200, r.text
    reg = client.post("/auth/register", json={"email": f"idem_{stamp}@example.com", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    game_id = int(client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"},
                              headers=headers).json()["game_id"])
    for tid, power in ((sender, "FRANCE"), (other, "GERMANY")):
        r = client.post(f"/games/{game_id}/join",
                        json={"telegram_id": tid, "bot_secret": SECRET, "game_id": game_id, "power": power})
        assert r.status_code == 200, r.text
    return game_id, sender, other


def _messages(client, game_id, telegram_id):
    r = client.get(f"/games/{game_id}/messages", params={"telegram_id": telegram_id, "bot_secret": SECRET})
    return r.json()["messages"]


def test_same_key_applies_once_and_replays_the_stored_response(client):
    game_id, sender, other = _game_with_two_bot_players(client)
    key = str(uuid.uuid4())
    body = {"telegram_id": sender, "bot_secret": SECRET, "text": "peace in our time"}
    before = len(_messages(client, game_id, sender))

    with OutboxProbe() as probe:
        first = client.post(f"/games/{game_id}/broadcast", json=body, headers={**BOT, "Idempotency-Key": key})
        assert first.status_code == 200, first.text
        second = client.post(f"/games/{game_id}/broadcast", json=body, headers={**BOT, "Idempotency-Key": key})

    assert second.status_code == 200
    assert second.headers.get("Idempotent-Replayed") == "true"
    assert first.headers.get("Idempotent-Replayed") is None
    assert second.json() == first.json()
    assert len(_messages(client, game_id, sender)) == before + 1
    # The other player was told once, not twice; the sender not at all.
    assert probe.by_recipient() == {other: [m for m in probe.messages()]} and len(probe.messages()) == 1


def test_key_is_ignored_without_the_bot_secret_header(client):
    game_id, sender, _other = _game_with_two_bot_players(client)
    key = str(uuid.uuid4())
    body = {"telegram_id": sender, "bot_secret": SECRET, "text": "twice"}
    before = len(_messages(client, game_id, sender))
    # bot_secret in the body authenticates the *route*; the header is what
    # arms idempotency, and it is deliberately absent here.
    for _ in range(2):
        r = client.post(f"/games/{game_id}/broadcast", json=body, headers={"Idempotency-Key": key})
        assert r.status_code == 200
    assert len(_messages(client, game_id, sender)) == before + 2


def test_a_4xx_is_stored_and_replayed_a_5xx_is_not(client):
    game_id, sender, _other = _game_with_two_bot_players(client)
    key = str(uuid.uuid4())
    # Not in the game -> 403, a definitive answer the bot must relay.
    r1 = client.post(f"/games/{game_id}/broadcast",
                     json={"telegram_id": "999999999", "bot_secret": SECRET, "text": "x"},
                     headers={**BOT, "Idempotency-Key": key})
    assert r1.status_code in (401, 403), r1.text
    r2 = client.post(f"/games/{game_id}/broadcast",
                     json={"telegram_id": "999999999", "bot_secret": SECRET, "text": "x"},
                     headers={**BOT, "Idempotency-Key": key})
    assert r2.status_code == r1.status_code and r2.headers.get("Idempotent-Replayed") == "true"
    assert api_shared.db_service.get_idempotent_response(key)["status_code"] == r1.status_code

    # A 500 is the server failing; nothing is stored so a retry runs the route again.
    key2 = str(uuid.uuid4())
    from unittest.mock import patch
    with patch.object(api_shared.db_service, "create_message", side_effect=RuntimeError("db hiccup")):
        r = client.post(f"/games/{game_id}/broadcast",
                        json={"telegram_id": sender, "bot_secret": SECRET, "text": "y"},
                        headers={**BOT, "Idempotency-Key": key2})
    assert r.status_code == 500
    assert api_shared.db_service.get_idempotent_response(key2) is None


def test_get_requests_never_use_the_key(client):
    key = str(uuid.uuid4())
    r = client.get("/games", headers={**BOT, "Idempotency-Key": key})
    assert r.status_code == 200
    assert api_shared.db_service.get_idempotent_response(key) is None


def test_expired_keys_are_purged_by_housekeeping():
    from datetime import timedelta
    from persistence.database import IdempotencyKeyModel, utcnow_naive
    old, fresh = str(uuid.uuid4()), str(uuid.uuid4())
    api_shared.db_service.store_idempotent_response(old, "/x", 200, {"a": 1})
    api_shared.db_service.store_idempotent_response(fresh, "/x", 200, {"a": 2})
    with api_shared.db_service.session_factory() as session:
        session.get(IdempotencyKeyModel, old).created_at = utcnow_naive() - timedelta(days=30)
        session.commit()
    api_shared.run_housekeeping()
    assert api_shared.db_service.get_idempotent_response(old) is None
    assert api_shared.db_service.get_idempotent_response(fresh) == {"status_code": 200, "response_json": {"a": 2}, "endpoint": "/x"}
    # Storing a duplicate key reports False and keeps the first response.
    assert api_shared.db_service.store_idempotent_response(fresh, "/y", 201, {"b": 3}) is False
    assert api_shared.db_service.get_idempotent_response(fresh)["response_json"] == {"a": 2}
