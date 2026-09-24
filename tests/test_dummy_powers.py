"""W9: powers left to civil disorder ("dummies") so 3-6 people can play.

A dummy is a seat nobody may join. The engine already plays a power that
submits nothing by the civil-disorder rules (units hold; a dislodged unit or an
owed removal is disbanded), so the server's only jobs are: never wait on a
dummy's orders, never count it in draw-vote quorum or deadline-proposal
majorities, keep it out of /join, and let the game's creator (or an admin)
change the set.
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _register_and_login, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

ADMIN = {"X-Admin-Token": "changeme"}  # conftest's default admin token
BOT = {"X-Bot-Secret": BOT_SECRET}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _create(client: TestClient, headers: dict, dummies: list[str]) -> str:
    resp = client.post("/games/create", json={"map_name": "standard", "dummy_powers": dummies}, headers=headers)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def test_create_records_the_dummies_and_the_creator(client: TestClient) -> None:
    creator = _register_and_login(client, "dmy")
    game_id = _create(client, creator, ["turkey", "AUSTRIA"])
    state = client.get(f"/games/{game_id}/state").json()
    assert state["dummy_powers"] == ["AUSTRIA", "TURKEY"]
    me = client.get("/auth/me", headers=creator).json()
    assert game_service.meta(game_id)["created_by_user_id"] == me["id"]
    listed = next(g for g in client.get("/games").json()["games"] if str(g["id"]) == game_id)
    assert listed["max_players"] == 5 and listed["dummy_powers"] == ["AUSTRIA", "TURKEY"]


@pytest.mark.parametrize(
    "dummies",
    [
        ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"],  # nobody left to play
        ["ATLANTIS"],
    ],
)
def test_create_refuses_an_impossible_dummy_set(client: TestClient, dummies: list[str]) -> None:
    resp = client.post("/games/create", json={"dummy_powers": dummies}, headers=_register_and_login(client, "dmy"))
    assert resp.status_code == 400, resp.text


def test_a_dummy_cannot_be_joined(client: TestClient) -> None:
    game_id = _create(client, _register_and_login(client, "dmy"), ["TURKEY"])
    tg = _telegram_user(client, "joiner")
    resp = client.post(f"/games/{game_id}/join", json=_as(tg, power="TURKEY"))
    assert resp.status_code == 409 and "civil disorder" in resp.json()["detail"]
    assert client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE")).status_code == 200


def test_nobody_waits_on_a_dummy_or_counts_it_in_a_vote(client: TestClient) -> None:
    game_id = _create(client, _register_and_login(client, "dmy"), ["AUSTRIA", "ITALY", "RUSSIA", "TURKEY"])
    status = client.get(f"/games/{game_id}/orders_status").json()
    assert set(status["active_powers"]) == {"ENGLAND", "FRANCE", "GERMANY"}
    assert game_service.active_powers(game_id) == frozenset({"ENGLAND", "FRANCE", "GERMANY"})
    draw = client.get(f"/games/{game_id}/draw_vote_status").json()
    assert set(draw["required"]) == {"ENGLAND", "FRANCE", "GERMANY"}


def test_the_game_is_full_when_humans_and_dummies_cover_every_seat(client: TestClient) -> None:
    game_id = _create(
        client, _register_and_login(client, "dmy"), ["AUSTRIA", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
    )
    a, b = _telegram_user(client, "a"), _telegram_user(client, "b")
    assert client.post(f"/games/{game_id}/join", json=_as(a, power="ENGLAND")).status_code == 200
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/join", json=_as(b, power="FRANCE")).status_code == 200
    assert any("is now full" in m for m in probe.messages())


def test_dummies_play_by_civil_disorder_through_a_real_turn(client: TestClient) -> None:
    game_id = _create(client, _register_and_login(client, "dmy"), ["TURKEY"])
    before = sorted(u["location"] for u in client.get(f"/games/{game_id}/state").json()["units_by_power"]["TURKEY"])
    assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    after = client.get(f"/games/{game_id}/state").json()
    assert after["phase"] == "F1901M"
    assert sorted(u["location"] for u in after["units_by_power"]["TURKEY"]) == before  # held


class TestChangingTheDummySet:
    def test_the_creator_can_add_and_remove_a_dummy(self, client: TestClient) -> None:
        creator = _register_and_login(client, "dmy")
        game_id = _create(client, creator, [])
        with OutboxProbe():
            added = client.post(f"/games/{game_id}/dummies", json={"power": "italy"}, headers=creator)
        assert added.status_code == 200, added.text
        assert added.json()["dummy_powers"] == ["ITALY"]
        removed = client.post(f"/games/{game_id}/dummies", json={"power": "ITALY", "dummy": False}, headers=creator)
        assert removed.json()["dummy_powers"] == []
        tg = _telegram_user(client, "late")
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power="ITALY")).status_code == 200

    def test_the_bot_creator_is_recognised_by_telegram_id(self, client: TestClient) -> None:
        tg = _telegram_user(client, "botcreator")
        resp = client.post("/games/create", json=_as(tg, map_name="standard"), headers=BOT)
        game_id = str(resp.json()["game_id"])
        ok = client.post(f"/games/{game_id}/dummies", json=_as(tg, power="RUSSIA"), headers=BOT)
        assert ok.status_code == 200, ok.text

    def test_anyone_else_is_refused_but_an_admin_is_not(self, client: TestClient) -> None:
        game_id = _create(client, _register_and_login(client, "dmy"), [])
        stranger = _register_and_login(client, "stranger")
        assert client.post(f"/games/{game_id}/dummies", json={"power": "ITALY"}, headers=stranger).status_code == 403
        assert client.post(f"/games/{game_id}/dummies", json={"power": "ITALY"}, headers=ADMIN).status_code == 200

    def test_a_held_seat_cannot_become_a_dummy(self, client: TestClient) -> None:
        creator = _register_and_login(client, "dmy")
        game_id = _create(client, creator, [])
        tg = _telegram_user(client, "holder")
        client.post(f"/games/{game_id}/join", json=_as(tg, power="FRANCE"))
        resp = client.post(f"/games/{game_id}/dummies", json={"power": "FRANCE"}, headers=creator)
        assert resp.status_code == 400 and "held by a player" in resp.json()["detail"]

    def test_an_ownerless_game_is_admin_only(self, client: TestClient) -> None:
        resp = client.post("/games/create", json={"map_name": "standard"}, headers=BOT)  # demo-seeder style
        game_id = str(resp.json()["game_id"])
        assert game_service.meta(game_id)["created_by_user_id"] is None
        someone = _register_and_login(client, "someone")
        assert client.post(f"/games/{game_id}/dummies", json={"power": "ITALY"}, headers=someone).status_code == 403
