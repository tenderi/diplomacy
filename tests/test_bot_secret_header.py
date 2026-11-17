"""The bot authenticates telegram_id writes with the ``X-Bot-Secret`` header alone.

The bot never puts the secret in a request body (its queued writes are stored
on disk). Every route that takes a ``telegram_id`` reads the header only: 4.0.0
removed the old ``bot_secret`` body field, so a body secret authenticates
nothing, and a ``bot_secret`` query parameter (it would land in access logs) is
ignored too. A write the bot queued on disk before the upgrade still delivers,
because the bot adds the header at send time and drops a stored body secret.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server._api_module import app
from server.telegram_bot import api_client
from server.telegram_bot.outbox import DELIVERED, reset_outbox_for_tests
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

    def test_a_stale_body_secret_is_ignored(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        """A body ``bot_secret`` (an old client's) neither helps nor hurts: the header decides."""
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/broadcast", headers=HEADER, json={
            "telegram_id": fr, "text": "replayed", "bot_secret": "the-old-secret",
        })
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize(("path", "status", "body"), [
        ("/messages", 401, {"detail": "Not authenticated: bot_secret required for telegram_id auth"}),
        ("/orders/FRANCE", 403, {"detail": "You are not authorized to view orders for this power."}),
        ("/orders", 200, []),
        ("/map/orders", 403, {"detail": "Only a player in this game can see their pending orders on the map."}),
    ])
    def test_a_get_ignores_a_query_parameter_secret(
        self, client: TestClient, seated: tuple[str, str, str], path: str, status: int, body: object
    ) -> None:
        """A secret in the URL lands in access logs, so it authenticates nothing:
        the request is answered exactly as one with no secret at all."""
        game_id, fr, _ = seated
        r = client.post("/games/set_orders", headers=HEADER, json={
            "game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": fr,
        })
        assert r.status_code == 200, r.text  # a pending order a leaked read would show
        url = f"/games/{game_id}{path}"
        in_query = client.get(url, params={"telegram_id": fr, "bot_secret": BOT_SECRET})
        no_secret = client.get(url, params={"telegram_id": fr})
        assert (in_query.status_code, in_query.json()) == (status, body)
        assert (no_secret.status_code, no_secret.json()) == (status, body)

    def test_on_a_get_the_header_still_authenticates(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        game_id, fr, _ = seated
        r = client.get(f"/games/{game_id}/orders/FRANCE", params={"telegram_id": fr}, headers=HEADER)
        assert (r.status_code, r.json()["power"]) == (200, "FRANCE")
        r = client.get(f"/games/{game_id}/messages", params={"telegram_id": fr}, headers=HEADER)
        assert r.status_code == 200, r.text

    def test_a_body_secret_alone_is_401(self, client: TestClient, seated: tuple[str, str, str]) -> None:
        """4.0.0 removed the ``bot_secret`` body field: the right secret in a body is no secret."""
        game_id, fr, _ = seated
        r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": fr, "text": "x", "bot_secret": BOT_SECRET})
        assert (r.status_code, r.json()["detail"]) == (401, "Not authenticated: bot_secret required for telegram_id auth")
        r = client.post("/users/persistent_register", json={"telegram_id": "cv_body_only", "bot_secret": BOT_SECRET})
        assert r.status_code == 401

    def test_a_write_queued_on_disk_before_the_upgrade_still_delivers(
        self, client: TestClient, seated: tuple[str, str, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An outbox row written by an older bot holds ``bot_secret`` in its stored
        payload. Replayed through the bot's real delivery path against the real
        API, it is accepted: the header carries the secret, the body never does."""
        game_id, fr, _ = seated
        outbox = reset_outbox_for_tests(tmp_path / "outbox.sqlite3")
        endpoint = "/games/set_orders"
        legacy = {"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": fr,
                  "bot_secret": "the-secret-of-an-older-release"}
        entry = outbox.enqueue(int(time.time()), endpoint, legacy, "orders")
        sent: list[dict[str, Any]] = []

        def via_test_client(url: str, json: dict[str, Any], headers: dict[str, str], timeout: float) -> Any:
            sent.append(json)
            return client.post(url.removeprefix(api_client.API_URL), json=json, headers=headers)

        monkeypatch.setattr(api_client, "BOT_SECRET", BOT_SECRET)
        with patch.object(api_client.requests, "post", side_effect=via_test_client):
            result = api_client.attempt_delivery(entry)
        assert (result.status, result.error) == ("delivered", None)
        assert outbox.get(entry.id).state == DELIVERED
        assert "bot_secret" not in sent[0]
        assert [o["success"] for o in result.response["results"]] == [True]


def test_no_route_reads_a_body_secret() -> None:
    """The ``bot_secret`` body field is gone: no request model declares it and
    no handler reads ``req.bot_secret``, so only the header authenticates."""
    stray = [
        f"{path.name}:{n}"
        for path in sorted(ROUTES.glob("*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if re.search(r"req\.bot_secret|^\s+bot_secret: Optional\[str\] = None$|supplied_bot_secret", line)
    ]
    assert stray == []
