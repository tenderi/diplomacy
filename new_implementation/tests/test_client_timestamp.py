"""``client_timestamp``: original send times and the stale-order guard (Track J).

Unit tests for the normaliser, then DB-backed tests that a message is stored
with the time it was composed and that an order submission composed before
the current phase began is refused with 409 rather than applied.
"""
from __future__ import annotations

import itertools
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from persistence.database import utcnow_naive
from server.api import app
from server.api import shared as api_shared
from server.api.client_timestamp import FUTURE_TOLERANCE, MAX_AGE, normalize_client_timestamp, sent_at_suffix
from tests.conftest import _get_db_url

SECRET = "test_bot_secret_for_tests"
_seq = itertools.count(1)


@pytest.mark.unit
class TestNormalize:
    def test_none_is_now(self):
        before = utcnow_naive()
        value = normalize_client_timestamp(None)
        assert before <= value <= utcnow_naive() and value.tzinfo is None

    def test_aware_values_become_naive_utc(self):
        aware = datetime(2026, 9, 8, 14, 2, tzinfo=timezone(timedelta(hours=3)))
        assert normalize_client_timestamp(aware) == datetime(2026, 9, 8, 11, 2)

    def test_slightly_fast_clock_is_kept_but_far_future_is_clamped(self):
        soon = utcnow_naive() + timedelta(minutes=1)
        assert normalize_client_timestamp(soon) == soon
        far = utcnow_naive() + FUTURE_TOLERANCE + timedelta(hours=1)
        assert normalize_client_timestamp(far) <= utcnow_naive()

    def test_ancient_values_are_refused(self):
        with pytest.raises(HTTPException) as exc:
            normalize_client_timestamp(utcnow_naive() - MAX_AGE - timedelta(days=1))
        assert exc.value.status_code == 400

    def test_sent_at_suffix_only_when_noticeably_late(self):
        now = datetime(2026, 9, 8, 15, 0)
        assert sent_at_suffix(now - timedelta(seconds=30), now) == ""
        assert sent_at_suffix(now - timedelta(hours=1), now) == " (sent 14:00 UTC)"
        assert sent_at_suffix(now - timedelta(days=1), now) == " (sent 2026-09-07 15:00 UTC)"


# --- DB-backed -----------------------------------------------------------------

pytestmark_db = [pytest.mark.integration, pytest.mark.database,
                 pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


def _seed(client):
    stamp = f"{int(time.time() * 1000000)}_{next(_seq)}"
    digits = f"{int(time.time() * 1000) % 10**7:07d}{next(_seq) % 100:02d}"
    fr, de = f"81{digits}", f"82{digits}"
    for tid, name in ((fr, "F"), (de, "G")):
        assert client.post("/users/persistent_register",
                           json={"telegram_id": tid, "full_name": name, "bot_secret": SECRET}).status_code == 200
    reg = client.post("/auth/register", json={"email": f"ts_{stamp}@example.com", "password": "testpass123"})
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    game_id = str(client.post("/games/create", json={"map_name": "standard", "initial_phase": "Movement"},
                              headers=headers).json()["game_id"])
    for tid, power in ((fr, "FRANCE"), (de, "GERMANY")):
        assert client.post(f"/games/{game_id}/join",
                           json={"telegram_id": tid, "bot_secret": SECRET, "game_id": int(game_id), "power": power}).status_code == 200
    # The browser user takes a power too, so it may call process_turn.
    assert client.post(f"/games/{game_id}/join", json={"game_id": int(game_id), "power": "ENGLAND"},
                       headers=headers).status_code == 200
    return game_id, fr, de, headers


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
class TestMessages:
    def test_message_is_stored_with_the_time_it_was_composed(self):
        client = TestClient(app)
        game_id, fr, de, _h = _seed(client)
        composed = (utcnow_naive() - timedelta(hours=2)).replace(microsecond=0)
        r = client.post(f"/games/{game_id}/message",
                        json={"telegram_id": fr, "bot_secret": SECRET, "recipient_power": "GERMANY",
                              "text": "late", "client_timestamp": composed.isoformat()})
        assert r.status_code == 200, r.text
        assert r.json()["timestamp"] == composed.isoformat()
        msgs = client.get(f"/games/{game_id}/messages", params={"telegram_id": de, "bot_secret": SECRET}).json()["messages"]
        assert [m["timestamp"] for m in msgs if m["text"] == "late"] == [composed.isoformat()]

    def test_recipient_notification_mentions_the_original_time(self):
        from tests.reliability_helpers import OutboxProbe
        client = TestClient(app)
        game_id, fr, de, _h = _seed(client)
        composed = utcnow_naive() - timedelta(hours=1)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/broadcast",
                            json={"telegram_id": fr, "bot_secret": SECRET, "text": "delayed hello",
                                  "client_timestamp": composed.isoformat()})
        assert r.status_code == 200, r.text
        got = probe.by_recipient()
        assert set(got) == {de}, "broadcast should reach the other player and not echo to the sender"
        assert f"(sent {composed:%H:%M} UTC)" in got[de][0]

    def test_message_without_timestamp_is_stamped_now(self):
        client = TestClient(app)
        game_id, fr, _de, _h = _seed(client)
        before = utcnow_naive() - timedelta(seconds=1)
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "bot_secret": SECRET, "text": "now"})
        assert r.status_code == 200
        assert datetime.fromisoformat(r.json()["timestamp"]) >= before


@pytest.mark.integration
@pytest.mark.database
@pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
class TestStaleOrders:
    def test_phase_started_at_is_stamped_on_create_and_on_process_turn(self):
        client = TestClient(app)
        game_id, _fr, _de, headers = _seed(client)
        row = api_shared.db_service.get_game_by_game_id(game_id)
        assert row.phase_started_at is not None
        created_stamp = row.phase_started_at
        time.sleep(0.01)
        assert client.post(f"/games/{game_id}/process_turn", headers=headers).status_code == 200
        row = api_shared.db_service.get_game_by_game_id(game_id)
        assert row.phase_started_at > created_stamp

    def test_orders_composed_before_the_phase_began_are_refused(self):
        client = TestClient(app)
        game_id, fr, _de, headers = _seed(client)
        assert client.post(f"/games/{game_id}/process_turn", headers=headers).status_code == 200
        started = api_shared.db_service.get_game_by_game_id(game_id).phase_started_at

        stale = (started - timedelta(minutes=5)).isoformat()
        r = client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"],
                                                   "telegram_id": fr, "bot_secret": SECRET, "client_timestamp": stale})
        assert r.status_code == 409, r.text
        assert "NOT applied" in r.json()["detail"]
        pending = client.get(f"/games/{game_id}/orders/FRANCE", params={"telegram_id": fr, "bot_secret": SECRET}).json()
        assert pending["orders"] == []

        fresh = (started + timedelta(seconds=1)).isoformat()
        r = client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"],
                                                   "telegram_id": fr, "bot_secret": SECRET, "client_timestamp": fresh})
        assert r.status_code == 200, r.text
        assert r.json()["results"][0]["success"] is True

        # A stale *clear* is refused too, so it cannot wipe the fresh orders.
        r = client.post(f"/games/{game_id}/orders/FRANCE/clear",
                        json={"telegram_id": fr, "bot_secret": SECRET, "client_timestamp": stale})
        assert r.status_code == 409
        pending = client.get(f"/games/{game_id}/orders/FRANCE", params={"telegram_id": fr, "bot_secret": SECRET}).json()
        assert pending["orders"] == ["A PAR H"]

    def test_orders_without_a_timestamp_are_unaffected(self):
        client = TestClient(app)
        game_id, fr, _de, headers = _seed(client)
        assert client.post(f"/games/{game_id}/process_turn", headers=headers).status_code == 200
        r = client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR H"],
                                                   "telegram_id": fr, "bot_secret": SECRET})
        assert r.status_code == 200, r.text
