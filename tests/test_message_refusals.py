"""Track DF1: messages refused for the right reason, with a message that says it.

A NUL in the text was a 500 (Postgres refuses it); a conceded power still "received" one; a dummy was "not assigned";
and an unregistered Telegram id got a bare "Not authenticated".
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_seat_guards import _as, _game

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

SENDS = [("message", {"recipient_power": "GERMANY"}), ("broadcast", {})]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.parametrize("endpoint,extra", SENDS)
def test_a_nul_character_is_a_400(client: TestClient, endpoint: str, extra: dict) -> None:
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    r = client.post(f"/games/{game_id}/{endpoint}", json=_as(seats["FRANCE"], text="hi\u0000there", **extra))
    assert (r.status_code, r.json()["detail"]) == (400, "A message cannot contain a NUL (\\u0000) character.")


def test_a_message_to_a_conceded_power_is_refused(client: TestClient) -> None:
    game_id, seats = _game(client, ["FRANCE", "GERMANY", "ITALY"])
    fill_with_dummies(game_id)
    assert client.post(f"/games/{game_id}/concede", json=_as(seats["ITALY"], power="ITALY")).status_code == 200
    r = client.post(f"/games/{game_id}/message", json=_as(seats["FRANCE"], recipient_power="ITALY", text="hello"))
    assert (r.status_code, r.json()["detail"]) == (
        409, f"ITALY has been eliminated from game {game_id}; it can no longer receive messages.",
    )


def test_a_message_to_a_dummy_names_civil_disorder(client: TestClient) -> None:
    game_id, seats = _game(client, ["FRANCE", "GERMANY", "ITALY"])
    fill_with_dummies(game_id)
    r = client.post(f"/games/{game_id}/message", json=_as(seats["FRANCE"], recipient_power="AUSTRIA", text="hello"))
    assert (r.status_code, r.json()["detail"]) == (
        400, "Cannot send a private message to AUSTRIA: it is played by civil disorder, so nobody would read it.",
    )


def test_an_unregistered_telegram_id_is_told_to_start(client: TestClient) -> None:
    game_id, _ = _game(client, ["FRANCE", "GERMANY"])
    r = client.post(f"/games/{game_id}/broadcast", json=_as("424242424242", text="hi"))
    assert (r.status_code, r.json()["detail"]) == (401, "You're not registered yet: send /start to the bot first.")


def test_an_unknown_telegram_id_without_the_secret_stays_generic(client: TestClient) -> None:
    game_id, _ = _game(client, ["FRANCE", "GERMANY"])
    r = client.post(f"/games/{game_id}/broadcast", json={"telegram_id": "424242424242", "text": "hi"})
    assert (r.status_code, r.json()["detail"]) == (401, "Not authenticated: bot_secret required for telegram_id auth")
