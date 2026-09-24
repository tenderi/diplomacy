"""The server side of the Telegram flow changes.

- Turn-processed notifications carry ``g|`` buttons (Enter orders / Map / Game menu).
- Ending a turn early from Telegram is for the game's creator only.
- ``/users/{id}/games`` says which games the player created.
- In a demo game the civil-disorder powers play ``simple_ai`` moves.
"""
import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET, _as, _telegram_user

pytestmark = [pytest.mark.unit, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]

BOT = {"X-Bot-Secret": BOT_SECRET}
OTHERS = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _created_by(client: TestClient, tg: str, **extra) -> str:
    resp = client.post("/games/create", json=_as(tg, map_name="standard", **extra), headers=BOT)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["game_id"])


def test_a_processed_turn_notification_has_buttons(client: TestClient) -> None:
    creator, other = _telegram_user(client, "creator"), _telegram_user(client, "other")
    game_id = _created_by(client, creator)
    client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE"))
    client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY"))
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200
    rows = [r for r in probe.rows() if str(r["telegram_id"]) == other and "processed" in r["message"]]
    assert rows, probe.messages()
    datas = [b["callback_data"] for row in rows[0]["payload"]["buttons"] for b in row]
    assert datas == [f"g|{game_id}|all|n", f"g|{game_id}|map|n", f"g|{game_id}|hub|n"]


class TestEndingATurnEarlyFromTelegram:
    def test_a_player_who_did_not_create_the_game_is_refused(self, client: TestClient) -> None:
        creator, other = _telegram_user(client, "creator"), _telegram_user(client, "other")
        game_id = _created_by(client, creator)
        client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY"))
        resp = client.post(f"/games/{game_id}/process_turn", json={"telegram_id": other}, headers=BOT)
        assert resp.status_code == 403 and "creator" in resp.json()["detail"]
        assert client.get(f"/games/{game_id}/state").json()["phase"] == "S1901M"

    def test_the_creator_may(self, client: TestClient) -> None:
        creator = _telegram_user(client, "creator")
        game_id = _created_by(client, creator)
        client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE"))
        resp = client.post(f"/games/{game_id}/process_turn", json={"telegram_id": creator}, headers=BOT)
        assert resp.status_code == 200, resp.text

    def test_the_bare_bot_secret_is_still_trusted(self, client: TestClient) -> None:
        game_id = _created_by(client, _telegram_user(client, "creator"))
        assert client.post(f"/games/{game_id}/process_turn", headers=BOT).status_code == 200


def test_the_games_list_marks_the_games_you_created(client: TestClient) -> None:
    creator, other = _telegram_user(client, "creator"), _telegram_user(client, "other")
    game_id = _created_by(client, creator)
    client.post(f"/games/{game_id}/join", json=_as(creator, power="FRANCE"))
    client.post(f"/games/{game_id}/join", json=_as(other, power="GERMANY"))

    def mine(tg: str) -> dict:
        games = client.get(f"/users/{tg}/games", headers=BOT).json()["games"]
        return next(g for g in games if str(g["game_id"]) == game_id)

    assert mine(creator)["is_creator"] is True
    assert mine(other)["is_creator"] is False


class TestDemoGame:
    def _demo(self, client: TestClient) -> tuple[str, str]:
        """What the bot's "Solo demo" creates."""
        tg = _telegram_user(client, "demo")
        resp = client.post("/games/create", json=_as(tg, map_name="demo", dummy_powers=OTHERS, auto_process=True), headers=BOT)
        game_id = str(resp.json()["game_id"])
        assert client.post(f"/games/{game_id}/join", json=_as(tg, power="GERMANY")).status_code == 200
        return game_id, tg

    def test_the_computer_powers_move_and_the_turn_runs_on_the_last_order(self, client: TestClient) -> None:
        game_id, tg = self._demo(client)
        before = client.get(f"/games/{game_id}/state").json()["units_by_power"]
        resp = client.post(
            "/games/set_orders",
            json=_as(tg, game_id=game_id, power="GERMANY", orders=["A BER H", "A MUN H", "F KIE H"], merge=True),
        )
        assert resp.json()["auto_processed"] >= 1
        after = client.get(f"/games/{game_id}/state").json()
        assert after["phase"] != "S1901M"
        moved = [
            p for p in OTHERS
            if sorted(u["location"] for u in before[p]) != sorted(u["location"] for u in after["units_by_power"][p])
        ]
        assert moved, "no computer power moved a unit"
        # Their orders are in the turn's history, so the player can see them.
        first_turn = next(iter(game_service.order_history(game_id).values()))
        assert set(OTHERS) <= set(first_turn) and first_turn["GERMANY"]

    def test_the_same_turn_gets_the_same_moves(self, client: TestClient) -> None:
        a, _ = self._demo(client)
        b, _ = self._demo(client)
        game_a, game_b = game_service.load(a), game_service.load(b)
        assert game_service._demo_ai_orders(a, game_a, {}) == game_service._demo_ai_orders(a, game_a, {})
        assert set(game_service._demo_ai_orders(b, game_b, {})) == set(OTHERS)

    def test_dummies_elsewhere_still_hold(self, client: TestClient) -> None:
        game_id = _created_by(client, _telegram_user(client, "plain"), dummy_powers=OTHERS)
        assert game_service._demo_ai_orders(game_id, game_service.load(game_id), {}) == {}
