"""Saved-game export and import (``routes/archive.py``): a played game survives the
round trip, and the routes stay admin-only because an export holds every private
message."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import ADMIN_TOKEN, app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.table_helpers import fill_with_dummies
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
    # Only a full table is processed (BA6); the tests below want the two seats
    # alone, so the other five are dummies just for the turn.
    dummies = fill_with_dummies(game_id)
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    for power in dummies:
        game_service.set_dummy(game_id, power, False)
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
    # Turn 0 (the opening board) is recorded by create_game itself, so only the
    # played turn's snapshot is imported -- and the copy has both, once each.
    assert sorted(s["turn"] for s in doc["snapshots"]) == [0, 1]
    assert report["snapshots_restored"] == 1

    original, restored = game_service.view(game_id), game_service.view(new_id)
    for key in ("phase", "units_by_power", "ownership"):
        assert restored[key] == original[key], key
    again = client.get(f"/games/{new_id}/export", headers=ADMIN).json()
    for key in ("state", "order_history", "resolution_history"):
        assert again[key] == doc[key], key
    assert again["game"]["current_turn"] == 1  # the next turn will not overwrite turn 0's history
    assert sorted((s["turn"], s["phase_code"]) for s in again["snapshots"]) == [(0, "S1901M"), (1, "F1901M")]
    # Seat rows come back in no guaranteed order.
    assert sorted((p["power"], p["telegram_id"]) for p in again["players"]) == sorted((p["power"], p["telegram_id"]) for p in doc["players"])


def test_the_imported_game_keeps_its_settings_and_last_turn(client: TestClient, played_game: tuple[str, str, str]) -> None:
    """Without these the import plays differently: no creator can process early or
    change dummies, dummies become powers everyone waits on, and "what happened
    last turn" is blank."""
    game_id, fr, _ = played_game
    assert client.post(f"/games/{game_id}/dummies", json=_as(fr, power="ITALY", dummy=True)).status_code == 200
    game_service.set_auto_process(game_id, True)
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()

    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    new_id = report["game_id"]
    assert report["creator_linked"] is True
    original, restored = game_service.meta(game_id), game_service.meta(new_id)
    for key in ("created_by_user_id", "dummy_powers", "auto_process"):
        assert restored[key] == original[key], key
    assert restored["dummy_powers"] == ["ITALY"]
    assert game_service.last_resolution(game_id) is not None
    assert game_service.last_resolution(new_id) == game_service.last_resolution(game_id)


def test_a_finished_game_imports_as_finished(client: TestClient, played_game: tuple[str, str, str]) -> None:
    game_id, _, _ = played_game
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    doc["state"]["status"], doc["state"]["winners"] = "COMPLETED", ["FRANCE"]
    new_id = client.post("/games/import", json=doc, headers=ADMIN).json()["game_id"]
    assert game_service.meta(new_id)["status"] == "completed"


def test_people_without_an_account_here_are_reported_not_invented(client: TestClient, played_game: tuple[str, str, str]) -> None:
    game_id, _, _ = played_game
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    for p in doc["players"]:
        p["telegram_id"] = "no-such-account-" + p["power"]
    for m in doc["messages"]:
        m["sender_telegram_id"] = "no-such-account-sender"
    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    assert (report["players_linked"], report["players_unlinked"]) == (0, 2)
    # With nobody seated, the message has no sender to attribute it to.
    assert (report["messages_restored"], report["messages_skipped"]) == (0, 1)


def test_a_message_from_a_player_who_quit_survives_the_round_trip(
    client: TestClient, played_game: tuple[str, str, str]
) -> None:
    """The sender is named by their own Telegram id, not by the seat they held:
    FRANCE quit, so no seat names them, and the export used to carry no sender
    at all -- the import then dropped the message."""
    game_id, fr, _ = played_game
    assert client.post(f"/games/{game_id}/quit", json=_as(fr, power="FRANCE")).status_code == 200
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    assert [(m["sender_power"], m["sender_telegram_id"]) for m in doc["messages"]] == [(None, fr)]

    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    assert (report["messages_restored"], report["messages_skipped"]) == (1, 0)
    again = client.get(f"/games/{report['game_id']}/export", headers=ADMIN).json()
    assert [(m["sender_telegram_id"], m["text"]) for m in again["messages"]] == [(fr, "Belgium is yours")]


def test_an_export_without_sender_ids_still_resolves_senders_by_power(
    client: TestClient, played_game: tuple[str, str, str]
) -> None:
    """Documents exported before ``sender_telegram_id`` existed name the sender
    only by power."""
    game_id, _, _ = played_game
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    for m in doc["messages"]:
        del m["sender_telegram_id"]
    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    assert (report["messages_restored"], report["messages_skipped"]) == (1, 0)


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


def test_the_deadline_schedule_survives_import_and_arms_the_current_phase(client: TestClient, played_game: tuple[str, str, str]) -> None:
    """Without it an imported scheduled game waits on its current phase forever:
    the export carries no deadline, and only a processed turn re-arms one."""
    game_id, fr, _ = played_game
    for power in ("ENGLAND", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"):  # 2 players + 5 dummies: full
        assert client.post(f"/games/{game_id}/dummies", json=_as(fr, power=power, dummy=True)).status_code == 200
    set_resp = client.post(f"/games/{game_id}/deadline/schedule", json=_as(fr, schedule="mon,wed,fri 16:00", timezone="Europe/Helsinki"))
    assert set_resp.status_code == 200, set_resp.text
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    assert doc["game"]["deadline_schedule"] == {
        "timezone": "Europe/Helsinki",
        "slots": [{"day": "MON", "time": "16:00"}, {"day": "WED", "time": "16:00"}, {"day": "FRI", "time": "16:00"}],
    }

    report = client.post("/games/import", json=doc, headers=ADMIN).json()
    new_id = report["game_id"]
    restored = game_service.meta(new_id)
    assert restored["deadline_schedule"] == doc["game"]["deadline_schedule"]
    assert report["deadline"] is not None
    assert restored["deadline"].isoformat() == report["deadline"].removesuffix("+00:00")
    assert f"{restored['deadline']:%H:%M}" in ("13:00", "14:00")  # 16:00 Helsinki, EEST or EET


def test_a_malformed_deadline_schedule_is_400_and_creates_nothing(client: TestClient) -> None:
    board = game_service.state_json(str(client.post("/games/create", json={"map_name": "standard"}, headers=BOT).json()["game_id"]))
    games_before = len(client.get("/games", headers=BOT).json()["games"])
    body = {"state": board, "game": {"deadline_schedule": {"timezone": "UTC", "slots": [{"day": "XYZ", "time": "16:00"}]}}}
    resp = client.post("/games/import", json=body, headers=ADMIN)
    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Malformed deadline_schedule in the export")
    assert len(client.get("/games", headers=BOT).json()["games"]) == games_before


@pytest.mark.parametrize("anonymous", [True, False])
def test_an_anonymous_game_imports_anonymous(client: TestClient, anonymous: bool) -> None:
    """Whether players are known only by their power is carried, or an import of
    an anonymous game would start naming everyone."""
    fr = _telegram_user(client, "Archive Anon")
    created = client.post("/games/create", json=_as(fr, map_name="standard", anonymous=anonymous), headers=BOT)
    game_id = str(created.json()["game_id"])
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    assert doc["game"]["anonymous"] is anonymous
    new_id = client.post("/games/import", json=doc, headers=ADMIN).json()["game_id"]
    assert game_service.meta(str(new_id))["anonymous"] is anonymous


@pytest.mark.parametrize("random_powers", [True, False])
def test_a_random_powers_game_imports_random(client: TestClient, random_powers: bool) -> None:
    """Whether joiners are dealt a random power is carried, or an import would
    let them choose."""
    fr = _telegram_user(client, "Archive Random")
    created = client.post("/games/create", json=_as(fr, map_name="standard", random_powers=random_powers), headers=BOT)
    game_id = str(created.json()["game_id"])
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    assert doc["game"]["random_powers"] is random_powers
    new_id = client.post("/games/import", json=doc, headers=ADMIN).json()["game_id"]
    assert game_service.meta(str(new_id))["random_powers"] is random_powers


def test_a_rumour_round_trips_still_anonymous(client: TestClient, played_game: tuple[str, str, str]) -> None:
    """The export keeps a rumour's sender (it is the admin's full record, like
    every private message in it) and its ``anonymous`` flag, so the imported
    game still hides who spread it."""
    game_id, fr, de = played_game
    sent = client.post(f"/games/{game_id}/broadcast", json=_as(fr, text="Russia is lying", anonymous=True))
    assert sent.status_code == 200, sent.text
    doc = client.get(f"/games/{game_id}/export", headers=ADMIN).json()
    assert [(m["sender_telegram_id"], m["anonymous"], m["text"]) for m in doc["messages"]] == [
        (fr, False, "Belgium is yours"), (fr, True, "Russia is lying"),
    ]
    new_id = client.post("/games/import", json=doc, headers=ADMIN).json()["game_id"]
    logged = client.get(f"/games/{new_id}/messages", params=_as(de)).json()["messages"]
    assert [(m["sender_power"], m["anonymous"], m["text"]) for m in logged] == [
        ("FRANCE", False, "Belgium is yours"), (None, True, "Russia is lying"),
    ]
