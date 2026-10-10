"""BF2: `routes/games.py` no longer wraps its handlers in a blanket `except Exception`.

An expected failure keeps its status and message; a programming bug is a plain 500 (with
a traceback in the log) instead of a 500 whose detail is the exception's text.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared

pytestmark = [pytest.mark.integration, pytest.mark.database]


@pytest.fixture
def crash_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_spectating_an_unknown_game_is_404(api_client: TestClient, auth_headers: dict[str, str]) -> None:
    r = api_client.post("/games/no_such_game_bf2/spectate", headers=auth_headers, json={})
    assert r.status_code == 404
    assert r.json() == {"detail": "Game no_such_game_bf2 not found"}


def test_leaving_the_spectators_of_an_unknown_game_is_404(
    api_client: TestClient, auth_headers: dict[str, str]
) -> None:
    r = api_client.request("DELETE", "/games/no_such_game_bf2/spectate", headers=auth_headers, json={})
    assert r.status_code == 404
    assert r.json() == {"detail": "Game no_such_game_bf2 not found"}


def test_players_of_an_unknown_game_is_404(api_client: TestClient) -> None:
    r = api_client.get("/games/no_such_game_bf2/players")
    assert r.status_code == 404
    assert r.json() == {"detail": "Game not found"}


def test_a_bug_in_listing_games_is_a_plain_500(
    crash_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> Any:
        raise TypeError("secret internal detail")

    monkeypatch.setattr(api_shared.db_service, "get_all_games", boom)
    r = crash_client.get("/games")
    assert r.status_code == 500
    assert r.text == "Internal Server Error"


def test_a_bug_while_spectating_is_a_plain_500(
    crash_client: TestClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_: Any) -> None:
        raise TypeError("secret internal detail")

    monkeypatch.setattr(api_shared.db_service, "add_spectator", boom)
    r = crash_client.post("/games/anything/spectate", headers=auth_headers, json={})
    assert r.status_code == 500
    assert r.text == "Internal Server Error"
