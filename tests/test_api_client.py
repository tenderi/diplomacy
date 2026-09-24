"""``server.telegram_bot.api_client`` -- the bot's only way to the API. Pure unit tests:
``requests`` is mocked, no network and no API server needed. (The durable-outbox side,
``api_post_reliable``, is in ``test_api_client_reliable.py``.)"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from server.telegram_bot import api_client

pytestmark = pytest.mark.unit


def _ok(body: object = None, content: bytes = b"") -> MagicMock:
    resp = MagicMock(ok=True, status_code=200, content=content)
    resp.json.return_value = body
    return resp


@pytest.fixture
def secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(api_client, "BOT_SECRET", "shh")
    return "shh"


class TestUrlAndHealth:
    @pytest.mark.parametrize("url", ["http://api:8000", "https://diplomacy.example/api"])
    def test_a_full_url_is_accepted(self, url: str) -> None:
        assert api_client._validate_api_url(url) is None  # raises ValueError otherwise

    @pytest.mark.parametrize("url", ["api:8000", "localhost", "", "http://"])
    def test_a_url_without_scheme_and_host_is_refused(self, url: str) -> None:
        with pytest.raises(ValueError, match="Invalid DIPLOMACY_API_URL"):
            api_client._validate_api_url(url)

    def test_health_falls_back_to_health_when_healthz_is_missing(self) -> None:
        missing = MagicMock(ok=False, status_code=404)
        with patch.object(api_client.requests, "get", side_effect=[missing, _ok()]) as get, \
             patch.object(api_client.time, "sleep") as sleep:
            api_client.wait_for_api_health(max_attempts=3)
        assert [c.args[0] for c in get.call_args_list] == [f"{api_client.API_URL}/healthz", f"{api_client.API_URL}/health"]
        sleep.assert_not_called()

    def test_health_backs_off_then_gives_up(self) -> None:
        with patch.object(api_client.requests, "get", side_effect=requests.ConnectionError("refused")), \
             patch.object(api_client.time, "sleep") as sleep, \
             patch.object(api_client.random, "uniform", return_value=0.0):
            with pytest.raises(RuntimeError, match="after 3 attempts: refused"):
                api_client.wait_for_api_health(max_attempts=3, base_delay=0.5)
        assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1.0, 2.0]


class TestRequests:
    def test_get_as_a_player_adds_the_id_and_the_secret_as_query_params(self, secret: str) -> None:
        with patch.object(api_client.requests, "get", return_value=_ok({"orders": []})) as get:
            assert api_client.api_get("/games/1/orders/FRANCE", telegram_id="555") == {"orders": []}
        assert get.call_args.kwargs["params"] == {"telegram_id": "555", "bot_secret": secret}
        assert get.call_args.kwargs["headers"] == {"X-Bot-Secret": secret}

    def test_a_public_get_sends_no_player_params(self, secret: str) -> None:
        with patch.object(api_client.requests, "get", return_value=_ok({})) as get:
            api_client.api_get("/games")
        assert get.call_args.kwargs["params"] == {}

    def test_post_returns_the_json_body(self) -> None:
        with patch.object(api_client.requests, "post", return_value=_ok({"status": "ok"})) as post:
            assert api_client.api_post("/games/1/join", {"telegram_id": "555"}) == {"status": "ok"}
        assert post.call_args.args[0] == f"{api_client.API_URL}/games/1/join"

    def test_delete_carries_the_bot_secret(self, secret: str) -> None:
        with patch.object(api_client.requests, "delete", return_value=_ok({"status": "ok"})) as delete:
            assert api_client.api_delete("/games/1/channel/unlink") == {"status": "ok"}
        assert delete.call_args.kwargs["headers"] == {"X-Bot-Secret": secret}

    @pytest.mark.parametrize("call", [
        lambda: api_client.api_delete("/x"), lambda: api_client.api_get("/x"), lambda: api_client.api_get_bytes("/x"),
    ])
    def test_no_connection_is_the_friendly_unreachable_error(self, call) -> None:
        with patch.object(api_client.requests, "get", side_effect=requests.ConnectionError("refused")), \
             patch.object(api_client.requests, "delete", side_effect=requests.Timeout("slow")):
            with pytest.raises(api_client.ApiUnreachableError):
                call()


class TestBytes:
    def test_returns_raw_content_with_the_bot_secret(self, secret: str) -> None:
        with patch.object(api_client.requests, "get", return_value=_ok(content=b"\x89PNG\r\n")) as get:
            assert api_client.api_get_bytes("/games/1/map") == b"\x89PNG\r\n"
        assert get.call_args.args[0] == f"{api_client.API_URL}/games/1/map"
        assert get.call_args.kwargs["headers"] == {"X-Bot-Secret": secret}

    def test_raises_on_http_error(self) -> None:
        resp = MagicMock(ok=False, status_code=404)
        resp.raise_for_status.side_effect = requests.HTTPError("404")
        resp.json.return_value = {"detail": "Game not found"}
        with patch.object(api_client.requests, "get", return_value=resp):
            with pytest.raises(requests.HTTPError, match="Game not found"):
                api_client.api_get_bytes("/games/1/map")
