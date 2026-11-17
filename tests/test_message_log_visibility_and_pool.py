"""``GET /games/{id}/messages`` and the archive export (DN1).

Who sees which message is unchanged: every broadcast, plus a seated player's
private messages sent to or from them; anyone without a seat sees broadcasts
only. And reading the log returns every database connection it checked out:
``get_messages_by_game_id`` once handed back a lazy ``Query`` from a closed
session, so each read left a pooled connection "idle in transaction" until
garbage collection, and a few open game pages exhausted the pool.
"""
from __future__ import annotations

import gc
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.bot_client import BotTestClient

from server._api_module import app
from server.api.shared import ADMIN_TOKEN
from server.api.shared import db_service
from tests.conftest import _get_db_url
from tests.test_anonymous_games import _BOT, _as, _game, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return BotTestClient(app)


@pytest.fixture
def board(client: TestClient) -> Iterator[tuple[str, str, str, str]]:
    """Anna FRANCE, Bert GERMANY, Carl ITALY; four messages, in this order:
    Anna's broadcast, Anna to GERMANY, Bert to FRANCE, Anna to ITALY."""
    game_id, anna, bert, _ = _game(client, anonymous=False)
    carl, _ = _telegram_user(client, "Carl")
    r = client.post(f"/games/{game_id}/join", json=_as(carl, power="ITALY"))
    assert r.status_code == 200 and r.json()["status"] == "ok", r.text
    for sender, path, body in (
        (anna, "broadcast", {"text": "pub"}),
        (anna, "message", {"recipient_power": "GERMANY", "text": "a2g"}),
        (bert, "message", {"recipient_power": "FRANCE", "text": "b2f"}),
        (anna, "message", {"recipient_power": "ITALY", "text": "a2i"}),
    ):
        r = client.post(f"/games/{game_id}/{path}", json=_as(sender, **body))
        assert r.status_code == 200, r.text
    yield game_id, anna, bert, carl


def _texts(client: TestClient, game_id: str, telegram_id: str | None = None) -> list[str]:
    if telegram_id is None:
        r = client.get(f"/games/{game_id}/messages")
    else:
        r = client.get(f"/games/{game_id}/messages", params={"telegram_id": telegram_id}, headers=_BOT)
    assert r.status_code == 200, r.text
    return [m["text"] for m in r.json()["messages"]]


class TestWhoSeesWhat:
    def test_a_player_sees_broadcasts_and_their_own_private_messages_in_order(self, client: TestClient, board: tuple[str, str, str, str]) -> None:
        game_id, anna, bert, carl = board
        assert _texts(client, game_id, anna) == ["pub", "a2g", "b2f", "a2i"]
        assert _texts(client, game_id, bert) == ["pub", "a2g", "b2f"]
        assert _texts(client, game_id, carl) == ["pub", "a2i"]

    def test_a_user_without_a_seat_sees_broadcasts_only(self, client: TestClient, board: tuple[str, str, str, str]) -> None:
        game_id = board[0]
        outsider, _ = _telegram_user(client, "Olga")
        assert _texts(client, game_id, outsider) == ["pub"]

    def test_an_anonymous_reader_sees_broadcasts_only(self, client: TestClient, board: tuple[str, str, str, str]) -> None:
        assert _texts(client, board[0]) == ["pub"]

    def test_the_admin_export_holds_every_message(self, client: TestClient, board: tuple[str, str, str, str]) -> None:
        r = client.get(f"/games/{board[0]}/export", headers={"X-Admin-Token": ADMIN_TOKEN})
        assert r.status_code == 200, r.text
        assert [m["text"] for m in r.json()["messages"]] == ["pub", "a2g", "b2f", "a2i"]


class TestConnectionsAreReturned:
    def test_reading_the_log_leaves_no_connection_checked_out(self, client: TestClient, board: tuple[str, str, str, str]) -> None:
        """More reads than the pool holds (size + overflow), each checked: a
        leaked connection shows at once instead of as a pool timeout. GC is off
        so a leak can't be hidden by a collection returning it."""
        game_id, anna, _, _ = board
        pool = db_service.session_factory.kw["bind"].pool
        reads = pool.size() + pool._max_overflow + 1
        gc.collect()
        baseline = pool.checkedout()
        gc.disable()
        try:
            for i in range(reads):
                _texts(client, game_id, anna if i % 2 else None)
                assert pool.checkedout() == baseline, f"read {i + 1} left a connection checked out"
                r = client.get(f"/games/{game_id}/export", headers={"X-Admin-Token": ADMIN_TOKEN})
                assert r.status_code == 200, r.text
                assert pool.checkedout() == baseline, f"export {i + 1} left a connection checked out"
        finally:
            gc.enable()
