"""Reading and writing player messages (fix_plan BB3, BB4).

BB3: the bot's /messages showed no private messages, because it put
``telegram_id`` in the URL, where ``api_get`` adds no bot secret, and the API
quietly answered as if to an anonymous reader. Identity that is present but
doesn't check out is now a 401, and the bot passes ``telegram_id=``.

BB4: blank messages were sent, and one too long to fit a Telegram message
(4096 UTF-16 units, heading included) was dropped by the bot as a permanent
error. Both are a 400 now, with a reason the player sees.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.routes.messages import MAX_MESSAGE_LENGTH, text_length
from server.telegram_bot import api_client
from server.telegram_bot.messages import recent_messages_text
from server.telegram_bot.notifications import render_notification
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_anonymous_games import BOT_SECRET, _as, _game, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

TELEGRAM_MAX = 4096


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _bot_reads_through(client: TestClient) -> Any:
    """``requests.get`` for the bot's ``api_client``, answered by the real API."""
    def get(url: str, headers: dict, params: dict, timeout: int) -> requests.Response:
        path = url.removeprefix(api_client.API_URL)
        r = client.get(path, headers=headers, params=params)
        resp = requests.Response()
        resp.status_code = r.status_code
        resp._content = r.content
        return resp
    return get


class TestReadingMessages:
    def test_the_bot_shows_a_player_their_private_messages(self, client: TestClient) -> None:
        game_id, anna, bert, _ = _game(client, anonymous=True)
        r = client.post(f"/games/{game_id}/message", json=_as(anna, recipient_power="GERMANY", text="Secret pact?"))
        assert r.status_code == 200, r.text
        with patch.object(api_client, "BOT_SECRET", BOT_SECRET), \
             patch.object(api_client.requests, "get", side_effect=_bot_reads_through(client)):
            text = recent_messages_text(game_id, bert)
        assert text.splitlines()[1:] == [f"[{_only_timestamp(client, game_id, bert)}] FRANCE -> GERMANY: Secret pact?"]

    def test_an_invalid_bearer_token_is_401_not_the_public_log(self, client: TestClient) -> None:
        game_id, _, _, _ = _game(client, anonymous=True)
        r = client.get(f"/games/{game_id}/messages", headers={"Authorization": "Bearer not-a-real-token"})
        assert (r.status_code, r.json()["detail"]) == (401, "Invalid or expired token")

    def test_a_telegram_id_without_the_bot_secret_is_401(self, client: TestClient) -> None:
        game_id, anna, _, _ = _game(client, anonymous=True)
        r = client.get(f"/games/{game_id}/messages", params={"telegram_id": anna})
        assert (r.status_code, r.json()["detail"]) == (401, "Not authenticated: bot_secret required for telegram_id auth")

    def test_no_credentials_reads_the_broadcasts_only(self, client: TestClient) -> None:
        game_id, anna, _, _ = _game(client, anonymous=True)
        client.post(f"/games/{game_id}/message", json=_as(anna, recipient_power="GERMANY", text="private"))
        client.post(f"/games/{game_id}/broadcast", json=_as(anna, text="public"))
        r = client.get(f"/games/{game_id}/messages")
        assert r.status_code == 200
        assert [m["text"] for m in r.json()["messages"]] == ["public"]


def _only_timestamp(client: TestClient, game_id: str, reader: str) -> str:
    """The one message's time as the bot shows it: ``5 Oct 14:03`` (UTC)."""
    (m,) = client.get(f"/games/{game_id}/messages", params=_as(reader)).json()["messages"]
    sent = datetime.fromisoformat(m["timestamp"])
    return f"{sent.day} {sent:%b %H:%M}"


SENDS = [
    ("message", {"recipient_power": "GERMANY"}),
    ("broadcast", {}),
    ("broadcast", {"anonymous": True}),
]


class TestMessageText:
    @pytest.mark.parametrize("endpoint,extra", SENDS)
    @pytest.mark.parametrize("text", ["", "   ", "\n\t "])
    def test_a_blank_message_is_refused(self, client: TestClient, endpoint: str, extra: dict, text: str) -> None:
        game_id, anna, _, _ = _game(client, anonymous=True)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/{endpoint}", json=_as(anna, text=text, **extra))
        assert (r.status_code, r.json()["detail"]) == (400, "A message cannot be empty.")
        assert probe.rows() == []
        assert client.get(f"/games/{game_id}/messages", params=_as(anna)).json()["messages"] == []

    @pytest.mark.parametrize("endpoint,extra", SENDS)
    def test_a_message_over_the_limit_is_refused_with_the_limit(self, client: TestClient, endpoint: str, extra: dict) -> None:
        game_id, anna, _, _ = _game(client, anonymous=True)
        with OutboxProbe() as probe:
            r = client.post(f"/games/{game_id}/{endpoint}", json=_as(anna, text="x" * (MAX_MESSAGE_LENGTH + 1), **extra))
        assert (r.status_code, r.json()["detail"]) == (
            400, f"A message can be at most {MAX_MESSAGE_LENGTH} characters long (this one is {MAX_MESSAGE_LENGTH + 1}).",
        )
        assert probe.rows() == []

    def test_the_limit_counts_utf16_units_as_telegram_does(self, client: TestClient) -> None:
        """An emoji outside the BMP is two units to Telegram and to a browser."""
        game_id, anna, _, _ = _game(client, anonymous=True)
        text = "😀" * (MAX_MESSAGE_LENGTH // 2 + 1)
        r = client.post(f"/games/{game_id}/broadcast", json=_as(anna, text=text))
        assert (r.status_code, r.json()["detail"]) == (
            400, f"A message can be at most {MAX_MESSAGE_LENGTH} characters long (this one is {text_length(text)}).",
        )

    def test_a_message_at_the_limit_fits_telegram_with_the_longest_heading(self, client: TestClient) -> None:
        """The worst case the code can produce: a public game, a sender with
        the longest nickname allowed, a message written two days before it
        arrived (" (sent YYYY-MM-DD HH:MM UTC)"), and a DM the bot delivers
        late ("⏱ Delayed notification (from ...):"). Every DM and group post
        it produces must still fit one Telegram message."""
        game_id, anna, bert, _ = _game(client, anonymous=False)
        longest = f"N{int(time.time() * 1000) % 10**9:09d}".ljust(24, "n")
        r = client.post("/users/nickname", json=_as(anna, nickname=longest))
        assert r.status_code == 200, r.text
        r = client.post(f"/games/{game_id}/channel/link", json={"channel_id": "-1004441570002"},
                        headers={"X-Bot-Secret": BOT_SECRET, "X-Admin-Token": ADMIN_TOKEN})  # an admin may take the reused group
        assert r.status_code == 200, r.text
        written = (datetime.now(timezone.utc) - timedelta(days=2)).replace(tzinfo=None).isoformat()
        text = "😀" * (MAX_MESSAGE_LENGTH // 2)
        with OutboxProbe() as probe:
            for endpoint, extra in SENDS:
                r = client.post(f"/games/{game_id}/{endpoint}",
                                json=_as(anna, text=text, client_timestamp=written, **extra))
                assert r.status_code == 200, r.text
        rows = probe.rows()
        # Bert's DM for each of the three, and the group's post for the two broadcasts.
        assert len(rows) == 5
        later = datetime.now(timezone.utc) + timedelta(days=3)
        rendered = [render_notification(row, now=later) for row in rows]
        assert all(t.startswith("⏱ Delayed notification") for t in rendered)
        assert any(longest in t for t in rendered)
        assert max(text_length(t) for t in rendered) <= TELEGRAM_MAX
