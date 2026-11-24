"""Track DF1: messages refused for the right reason, with a message that says it.

A NUL in the text was a 500 (Postgres refuses it); a conceded power still "received" one; a dummy was "not assigned";
and an unregistered Telegram id got a bare "Not authenticated".
"""
import pytest
from fastapi.testclient import TestClient

from engine.types import GameStatus
from tests.bot_client import BotTestClient

from server._api_module import app
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
from tests.test_seat_guards import BOT, _as, _game, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

SENDS = [("message", {"recipient_power": "GERMANY"}), ("broadcast", {})]


@pytest.fixture
def client() -> TestClient:
    return BotTestClient(app)


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


def _end(game_id: str) -> None:
    """Mark the game finished: FRANCE has won (restoring a COMPLETED board)."""
    from dataclasses import replace
    from engine.serialization import state_to_dict
    from server.api.shared import game_service

    game = game_service.load(game_id)
    done = replace(game.state, status=GameStatus.COMPLETED, winners=frozenset({"FRANCE"}))
    game_service.restore_snapshot(game_id, state_to_dict(done), phase_code=game_service.view(game_id)["phase"])
    assert game_service.view(game_id)["status"] == "COMPLETED"


def _finished_game(client: TestClient) -> tuple[str, dict[str, str]]:
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    fill_with_dummies(game_id)
    _end(game_id)
    return game_id, seats


@pytest.mark.parametrize("endpoint,extra", SENDS)
def test_a_finished_game_takes_no_messages(client: TestClient, endpoint: str, extra: dict) -> None:
    game_id, seats = _finished_game(client)
    r = client.post(f"/games/{game_id}/{endpoint}", json=_as(seats["FRANCE"], text="gg", **extra))
    assert (r.status_code, r.json()["detail"]) == (
        409, f"Game {game_id} has ended; messages can no longer be sent.",
    )


def test_a_finished_game_refuses_a_rumour_and_keeps_its_history(client: TestClient) -> None:
    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    fill_with_dummies(game_id)
    assert client.post(f"/games/{game_id}/broadcast", json=_as(seats["FRANCE"], text="before")).status_code == 200
    _end(game_id)
    r = client.post(f"/games/{game_id}/broadcast", json=_as(seats["FRANCE"], text="shh", anonymous=True))
    assert (r.status_code, r.json()["detail"]) == (409, f"Game {game_id} has ended; messages can no longer be sent.")
    r = client.get(f"/games/{game_id}/messages", params={"telegram_id": seats["FRANCE"]}, headers=BOT)
    assert [m["text"] for m in r.json()["messages"]] == ["before"]


def test_a_non_member_still_gets_403_not_409_for_a_finished_game(client: TestClient) -> None:
    game_id, _ = _finished_game(client)
    r = client.post(f"/games/{game_id}/broadcast", json=_as(_telegram_user(client), text="hi"))
    assert (r.status_code, r.json()["detail"]) == (403, "Sender not in game")


def test_a_group_broadcast_of_a_finished_game_is_refused(client: TestClient) -> None:
    from server.api.shared import db_service

    game_id, seats = _game(client, ["FRANCE", "GERMANY"])
    fill_with_dummies(game_id)
    db_service.link_game_to_channel(game_id, "-100777", any_displacer=True)
    body = {"telegram_id": seats["FRANCE"], "message": "hi"}
    live = client.post(f"/games/{game_id}/channel/broadcast", headers=BOT, json=body)
    assert live.status_code == 200, live.text
    _end(game_id)
    r = client.post(f"/games/{game_id}/channel/broadcast", headers=BOT, json=body)
    assert (r.status_code, r.json()["detail"]) == (409, f"Game {game_id} has ended; messages can no longer be sent.")
