"""The bot authenticates telegram_id writes with the ``X-Bot-Secret`` header alone.

The bot never puts the secret in a request body (its queued writes are stored
on disk). Every write route that takes a ``telegram_id`` reads the header
through ``supplied_bot_secret``; the legacy ``bot_secret`` body field is still
accepted when no header is sent.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies

BOT_SECRET = "test_bot_secret_for_tests"
HEADER = {"X-Bot-Secret": BOT_SECRET}
WRONG = {"X-Bot-Secret": "not-the-secret"}
ROUTES = Path(__file__).resolve().parent.parent / "src" / "server" / "api" / "routes"

needs_db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def seated(client: TestClient) -> tuple[str, str, str]:
    """A started game with FRANCE and GERMANY seated, all set up via the header."""
    stamp = str(int(time.time() * 1_000_000))
    fr, de = f"cv_fr_{stamp}", f"cv_de_{stamp}"
    for tid in (fr, de):
        r = client.post("/users/persistent_register", json={"telegram_id": tid}, headers=HEADER)
        assert r.status_code == 200, r.text
    reg = client.post("/auth/register", json={"email": f"cv_{stamp}@example.com", "password": "testpass123"})
    bearer = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    game = client.post("/games/create", json={"map_name": "standard"}, headers=bearer)
    game_id = str(game.json()["game_id"])
    for tid, power in ((fr, "FRANCE"), (de, "GERMANY")):
        r = client.post(f"/games/{game_id}/join", json={"telegram_id": tid, "power": power}, headers=HEADER)
        assert r.status_code == 200, r.text
    fill_with_dummies(game_id)
    return game_id, fr, de


@needs_db
@pytest.mark.database
class TestHeaderOnly:
    def test_orders_submit_and_clear(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post("/games/set_orders", headers=HEADER, json={
            "game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": fr,
        })
        assert r.status_code == 200, r.text
        assert [o["success"] for o in r.json()["results"]] == [True]
        r = client.post(f"/games/{game_id}/orders/FRANCE/clear", json={"telegram_id": fr}, headers=HEADER)
        assert r.status_code == 200, r.text

    def test_private_message_and_broadcast(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/message", headers=HEADER, json={
            "telegram_id": fr, "recipient_power": "GERMANY", "text": "hello",
        })
        assert r.status_code == 200, r.text
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "text": "all"}, headers=HEADER)
        assert r.status_code == 200, r.text

    def test_wait_draw_vote_and_feedback(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/wait", json={"telegram_id": fr, "power": "FRANCE"}, headers=HEADER)
        assert r.status_code == 200, r.text
        r = client.post(
            f"/games/{game_id}/draw_vote", json={"telegram_id": fr, "power": "FRANCE", "vote": True}, headers=HEADER
        )
        assert r.status_code == 200, r.text
        r = client.post("/feedback", json={"telegram_id": fr, "text": "nice", "source": "telegram"}, headers=HEADER)
        assert r.status_code == 200, r.text

    def test_nickname(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        _, fr, _ = seated
        nick = f"cv{fr[-8:]}"
        r = client.post("/users/nickname", json={"telegram_id": fr, "nickname": nick}, headers=HEADER)
        assert r.status_code == 200, r.text

    def test_a_wrong_header_is_401(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post("/games/set_orders", headers=WRONG, json={
            "game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": fr,
        })
        assert (r.status_code, r.json()["detail"]) == (401, "Not authenticated: bot_secret required for telegram_id auth")
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "text": "x"}, headers=WRONG)
        assert r.status_code == 401
        r = client.post("/users/persistent_register", json={"telegram_id": "cv_nobody"}, headers=WRONG)
        assert r.status_code == 401

    def test_no_secret_at_all_is_401(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "text": "x"})
        assert r.status_code == 401

    def test_the_header_still_only_acts_for_the_callers_own_power(
        self, client: TestClient, seated: tuple[str, str, str]
    ) -> None:
        game_id, fr, _ = seated
        r = client.post("/games/set_orders", headers=HEADER, json={
            "game_id": game_id, "power": "GERMANY", "orders": ["A BER H"], "telegram_id": fr,
        })
        assert (r.status_code, r.json()["detail"]) == (403, "You are not authorized to act for this power.")

    def test_the_header_wins_over_a_stale_body_secret(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        """A write queued before a secret rotation carries the old secret in its body."""
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/broadcast", headers=HEADER, json={
            "telegram_id": fr, "text": "replayed", "bot_secret": "the-old-secret",
        })
        assert r.status_code == 200, r.text

    def test_the_legacy_body_field_alone_still_works(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "text": "x", "bot_secret": BOT_SECRET})
        assert r.status_code == 200, r.text


def test_every_body_secret_read_goes_through_supplied_bot_secret() -> None:
    """A route reading ``req.bot_secret`` directly would ignore the header."""
    stray = [
        f"{path.name}:{n}"
        for path in sorted(ROUTES.glob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if re.search(r"req\.bot_secret", line.replace("supplied_bot_secret(x_bot_secret, req.bot_secret)", ""))
    ]
    assert stray == []
