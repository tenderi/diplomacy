"""W11: an admin can delete one game (``DELETE /admin/games/{id}``).

Until this only ``/admin/delete_all_games`` existed. The single delete has to
clear ``players`` and ``messages`` itself: in the live schema their foreign
keys to ``games`` are ``ON DELETE NO ACTION`` (the models claim CASCADE, the
migrations never did), so a plain ``DELETE FROM games`` fails as soon as the
game has a player.
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import db_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _game_with_france, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ADMIN = {"X-Admin-Token": "changeme"}  # conftest's default admin token
BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _lived_in_game(client: TestClient) -> tuple[str, str, str]:
    """FRANCE (``a``) and GERMANY (``b``) seated, a message sent, a turn processed
    (so there is a map snapshot and turn history). Returns ``(game_id, a, b)``."""
    game_id, a = _game_with_france(client)
    b = _telegram_user(client, "germany")
    assert client.post(f"/games/{game_id}/join", json=_as(b, power="GERMANY")).status_code == 200
    sent = client.post(f"/games/{game_id}/message", json=_as(a, recipient_power="GERMANY", text="hello"))
    assert sent.status_code == 200, sent.text
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    return game_id, a, b


def test_deletes_the_game_and_everything_hanging_off_it(client: TestClient) -> None:
    game_id, a, b = _lived_in_game(client)
    other_id, _ = _game_with_france(client)
    numeric = int(game_id)
    assert db_service.get_players_by_game_id(numeric)
    assert db_service.get_game_snapshots_by_game_id(numeric)  # the processed turn left one
    assert client.get(f"/users/{a}/games", headers=BOT).json()["games"]

    with OutboxProbe() as probe:
        resp = client.delete(f"/admin/games/{game_id}", headers=ADMIN)
    assert resp.status_code == 200, resp.text
    assert resp.json()["players_notified"] == 2

    assert client.get(f"/games/{game_id}/state").status_code == 404
    assert db_service.get_players_by_game_id(numeric) == []
    assert db_service.get_game_snapshots_by_game_id(numeric) == []
    # The players' cached game lists drop it at once, and the users themselves stay.
    listed = client.get(f"/users/{a}/games", headers=BOT).json()["games"]
    assert all(str(g["game_id"]) != str(game_id) for g in listed)
    assert db_service.get_user_by_telegram_id(a) is not None
    # Both players were told, and the other game is untouched.
    assert {a, b} <= probe.recipients()
    assert any(f"Game {game_id} has been deleted" in m for m in probe.messages())
    assert client.get(f"/games/{other_id}/state").status_code == 200


def test_requires_the_admin_token(client: TestClient) -> None:
    game_id, a = _game_with_france(client)
    assert client.delete(f"/admin/games/{game_id}").status_code == 422  # header missing
    assert client.delete(f"/admin/games/{game_id}", headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert client.delete(f"/admin/games/{game_id}", headers={"X-Admin-Token": BOT_SECRET}).status_code == 403
    assert client.get(f"/games/{game_id}/state").status_code == 200


def test_unknown_game_is_404(client: TestClient) -> None:
    assert client.delete("/admin/games/999999999", headers=ADMIN).status_code == 404
