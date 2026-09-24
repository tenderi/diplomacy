"""Saved-game export and import (``routes/archive.py``): a played game survives the
round trip, and the routes stay admin-only because an export holds every private
message."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ADMIN = {"X-Admin-Token": ADMIN_TOKEN}
BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def played_game(client: TestClient) -> tuple[str, str, str]:
    """FRANCE and GERMANY seated, one turn played, one private message, one snapshot."""
    fr, de = _telegram_user(client, "Archive France"), _telegram_user(client, "Archive Germany")
    game_id = str(client.post("/games/create", json=_as(fr, map_name="standard"), headers=BOT).json()["game_id"])
    for tg, power in ((fr, "FRANCE"), (de, "GERMANY")):
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power=power)).status_code == 200
    client.post("/games/set_orders", json=_as(fr, game_id=game_id, power="FRANCE", orders=["A PAR - BUR"]))
    client.post("/games/set_orders", json=_as(de, game_id=game_id, power="GERMANY", orders=["A MUN - RUH"]))
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    sent = client.post(f"/games/{game_id}/message", json=_as(fr, recipient_power="GERMANY", text="Belgium is yours"))
    assert sent.status_code == 200, sent.text
    return game_id, fr, de


def test_a_played_game_round_trips_under_a_new_id(client: TestClient, played_game: tuple[str, str, str]) -> None:
    game_id, _, _ = played_game
    exported = client.get(f"/games/{game_id}/export", headers=ADMIN)
    assert exported.status_code == 200
    doc = exported.json()
    assert (doc["format"], doc["game"]["phase_code"], doc["game"]["current_turn"]) == ("diplomacy.game.v1", "F1901M", 1)
    assert doc["order_history"]["0"] == {"FRANCE": ["A PAR - BUR"], "GERMANY": ["A MUN - RUH"]}
    assert [(m["sender_power"], m["recipient_power"], m["text"]) for m in doc["messages"]] == [("FRANCE", "GERMANY", "Belgium is yours")]

    imported = client.post("/games/import", json=doc, headers=ADMIN)
    assert imported.status_code == 200, imported.text
    report = imported.json()
    new_id = report["game_id"]
    assert new_id != game_id
    assert (report["players_linked"], report["players_unlinked"]) == (2, 0)
    assert (report["messages_restored"], report["messages_skipped"]) == (1, 0)
    assert report["snapshots_restored"] == len(doc["snapshots"])

    original, restored = game_service.view(game_id), game_service.view(new_id)
    for key in ("phase", "units_by_power", "ownership"):
        assert restored[key] == original[key], key
    again = client.get(f"/games/{new_id}/export", headers=ADMIN).json()
    for key in ("state", "order_history", "resolution_history"):
        assert again[key] == doc[key], key
    assert again["game"]["current_turn"] == 1  # the next turn will not overwrite turn 0's history
    # Seat rows come back in no guaranteed order.
    assert sorted((p["power"], p["telegram_id"]) for p in again["players"]) == sorted((p["power"], p["telegram_id"]) for p in doc["players"])


def test_people_without_an_account_here_are_reported_not_invented(client: TestClient, played_game: tuple[str, str, str]) -> None:
    game_id, _, _ = played_game
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    for p in doc["players"]:
        p["telegram_id"] = "no-such-account-" + p["power"]
    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    assert (report["players_linked"], report["players_unlinked"]) == (0, 2)
    # With nobody seated, the message has no sender to attribute it to.
    assert (report["messages_restored"], report["messages_skipped"]) == (0, 1)


def test_a_bare_board_is_enough_to_set_up_a_position(client: TestClient) -> None:
    board = game_service.state_json(str(client.post("/games/create", json={"map_name": "standard"}, headers=BOT).json()["game_id"]))
    report = client.post("/games/import", json={"state": board}, headers=ADMIN).json()
    assert game_service.view(report["game_id"])["phase"] == "S1901M"


@pytest.mark.parametrize(("body", "detail"), [
    ({"format": "diplomacy.game.v0", "state": {}}, "Unsupported export format"),
    ({"state": {"not": "a board"}}, "Malformed state"),
])
def test_bad_documents_are_400_and_create_nothing(client: TestClient, body: dict, detail: str) -> None:
    games_before = len(client.get("/games", headers=BOT).json()["games"])
    resp = client.post("/games/import", json=body, headers=ADMIN)
    assert resp.status_code == 400 and detail in resp.json()["detail"]
    assert len(client.get("/games", headers=BOT).json()["games"]) == games_before


def test_both_routes_are_admin_only(client: TestClient, played_game: tuple[str, str, str]) -> None:
    game_id, _, _ = played_game
    # No X-Admin-Token at all is FastAPI's missing-header 422; a wrong one is 403.
    for headers, code in (({}, 422), (BOT, 422), ({"X-Admin-Token": "wrong"}, 403)):
        assert client.get(f"/games/{game_id}/export", headers=headers).status_code == code
        assert client.post("/games/import", json={"state": {}}, headers=headers).status_code == code
    assert client.get("/games/999999999/export", headers=ADMIN).status_code == 404
