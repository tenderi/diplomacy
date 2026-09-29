"""The web sandbox (``routes/sandbox.py``, ``GameService.sandbox_*``): order every
power on a scratch board and step it through movement, retreat and adjustment
phases, with nothing stored -- the client holds the board, so the server must
treat it as untrusted input."""
from __future__ import annotations

import copy
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api.shared import game_service
from tests.conftest import _get_db_url

BOT = {"X-Bot-Secret": "test_bot_secret_for_tests"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

db = pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _unit(kind: str, power: str, location: str) -> dict[str, str]:
    return {"kind": kind, "power": power, "location": location}


def _fall_board() -> dict[str, Any]:
    """F1901M: France can dislodge Germany's A MUN with a supported attack."""
    return {
        "year": 1901,
        "season": "FALL",
        "phase_type": "MOVEMENT",
        "units": [
            _unit("A", "FRANCE", "BUR"),
            _unit("A", "FRANCE", "RUH"),
            _unit("A", "GERMANY", "MUN"),
        ],
        "ownership": {
            "PAR": "FRANCE", "MAR": "FRANCE", "BRE": "FRANCE",
            "MUN": "GERMANY", "BER": "GERMANY", "KIE": "GERMANY",
        },
    }


def _adjudicate(client: TestClient, state: dict[str, Any], orders: dict[str, list[str]]) -> dict[str, Any]:
    resp = client.post("/sandbox/adjudicate", json={"state": state, "orders": orders}, headers=BOT)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.unit
def test_the_sandbox_needs_a_signed_in_caller(client: TestClient) -> None:
    resp = client.post("/sandbox/start", json={})

    assert resp.status_code == 401


@pytest.mark.unit
def test_start_without_a_game_is_the_opening_position(client: TestClient) -> None:
    resp = client.post("/sandbox/start", json={}, headers=BOT)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_game_id"] is None
    assert body["view"]["phase"] == "S1901M"
    assert len(body["view"]["units"]) == 22
    assert body["view"]["powers_to_order"] == [
        "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY",
    ]
    assert body["state"] == game_service.sandbox_opening()


@pytest.mark.unit
def test_legal_orders_for_any_power_on_the_sandbox_board(client: TestClient) -> None:
    state = game_service.sandbox_opening()

    resp = client.post("/sandbox/legal_orders", json={"state": state, "power": "england"}, headers=BOT)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["power"] == "ENGLAND"
    assert sorted(body["orders_by_unit"]) == ["A LVP", "F EDI", "F LON"]
    assert "F LON - ENG" in body["orders_by_unit"]["F LON"]


@pytest.mark.unit
def test_legal_orders_refuse_an_unknown_power(client: TestClient) -> None:
    state = game_service.sandbox_opening()

    resp = client.post("/sandbox/legal_orders", json={"state": state, "power": "NARNIA"}, headers=BOT)

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unknown power NARNIA"


@pytest.mark.unit
def test_adjudicate_resolves_every_power_and_reports_refused_orders(client: TestClient) -> None:
    state = game_service.sandbox_opening()

    body = _adjudicate(client, state, {
        "FRANCE": ["A PAR - BUR", "A MAR S A PAR - BUR"],
        "GERMANY": ["A MUN - BUR"],
        "ENGLAND": ["A LVP - PAR"],
    })

    assert body["order_results"]["ENGLAND"] == [
        {"order": "A LVP - PAR", "ok": False, "reason": "PAR is not adjacent to LVP"}
    ]
    assert all(r["ok"] for r in body["order_results"]["FRANCE"] + body["order_results"]["GERMANY"])
    outcome = {r["order_str"]: (r["power"], r["result"]) for r in body["resolution"]["results"]}
    assert outcome["A PAR - BUR"] == ("FRANCE", "OK")
    assert outcome["A MUN - BUR"] == ("GERMANY", "BOUNCE")
    assert outcome["A LVP H"] == ("ENGLAND", "OK")  # the refused order's unit held
    assert body["view"]["phase"] == "F1901M"
    assert {"kind": "A", "power": "FRANCE", "location": "BUR"} in body["state"]["units"]


@pytest.mark.unit
def test_a_board_steps_through_retreat_and_adjustment_to_the_next_spring(client: TestClient) -> None:
    moved = _adjudicate(client, _fall_board(), {"FRANCE": ["A BUR - MUN", "A RUH S A BUR - MUN"]})

    assert moved["view"]["phase"] == "F1901R"
    assert moved["view"]["powers_to_order"] == ["GERMANY"]
    [dislodged] = moved["view"]["dislodged"]
    assert dislodged["unit"] == _unit("A", "GERMANY", "MUN")
    assert "BUR" not in dislodged["retreats"]  # never back where the attacker came from

    legal = client.post(
        "/sandbox/legal_orders", json={"state": moved["state"], "power": "GERMANY"}, headers=BOT
    ).json()
    assert "A MUN R BOH" in legal["orders_by_unit"]["A MUN"]
    retreated = _adjudicate(client, moved["state"], {"GERMANY": ["A MUN R BOH"]})

    assert retreated["view"]["phase"] == "W1901A"
    assert retreated["view"]["ownership"]["MUN"] == "FRANCE"
    assert retreated["view"]["powers_to_order"] == ["FRANCE", "GERMANY"]
    built = _adjudicate(client, retreated["state"], {"FRANCE": ["A PAR B", "F BRE B"]})

    assert built["order_results"]["FRANCE"] == [
        {"order": "A PAR B", "ok": True, "reason": None},
        {"order": "F BRE B", "ok": True, "reason": None},
    ]
    assert built["view"]["phase"] == "S1902M"
    assert sorted(f"{u['kind']} {u['location']}" for u in built["view"]["units_by_power"]["FRANCE"]) == [
        "A MUN", "A PAR", "A RUH", "F BRE",
    ]
    # Germany gave no build order: civil disorder waives it.
    assert [u["location"] for u in built["view"]["units_by_power"]["GERMANY"]] == ["BOH"]


@pytest.mark.unit
def test_a_finished_board_takes_no_more_orders(client: TestClient) -> None:
    state = {**_fall_board(), "status": "COMPLETED", "winners": ["FRANCE"]}

    resp = client.post("/sandbox/adjudicate", json={"state": state, "orders": {}}, headers=BOT)

    assert resp.status_code == 409
    assert resp.json()["detail"] == "this board's game is over; start again to keep playing"


@pytest.mark.unit
def test_orders_for_an_unknown_power_are_refused(client: TestClient) -> None:
    resp = client.post(
        "/sandbox/adjudicate",
        json={"state": game_service.sandbox_opening(), "orders": {"NARNIA": ["A PAR H"]}},
        headers=BOT,
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unknown power NARNIA"


@pytest.mark.unit
def test_an_oversized_order_list_is_refused(client: TestClient) -> None:
    resp = client.post(
        "/sandbox/adjudicate",
        json={"state": game_service.sandbox_opening(), "orders": {"FRANCE": ["A PAR H"] * 41}},
        headers=BOT,
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Too many orders for FRANCE"


def _with(**changes: Any) -> dict[str, Any]:
    board = copy.deepcopy(_fall_board())
    board.update(changes)
    return board


@pytest.mark.unit
@pytest.mark.parametrize(
    ("board", "reason"),
    [
        ({"season": "FALL"}, "not a game state (KeyError: 'year')"),
        (_with(season="MONSOON"), "not a game state (ValueError: 'MONSOON' is not a valid Season)"),
        (_with(year="1901"), "not a game state (year must be a number)"),
        (_with(units=[_unit("A", "NARNIA", "PAR")]), "unit A PAR: unknown power 'NARNIA'"),
        (_with(units=[_unit("A", "FRANCE", "XXX")]), "unit A XXX: unknown province 'XXX'"),
        (_with(units=[_unit("A", "FRANCE", "NTH")]), "unit A NTH: an army cannot stand at sea"),
        (_with(units=[_unit("F", "FRANCE", "PAR")]), "unit F PAR: a fleet cannot stand there"),
        (_with(units=[_unit("F", "RUSSIA", "STP")]), "unit F STP: a fleet cannot stand there"),
        (
            _with(units=[_unit("A", "FRANCE", "PAR"), _unit("A", "GERMANY", "PAR")]),
            "two units in PAR",
        ),
        (_with(ownership={"BUR": "FRANCE"}), "ownership BUR: FRANCE is not a centre and a power"),
        (_with(contested=["ATLANTIS"]), "unknown province or power in contested/winners"),
        (
            _with(dislodged=[{"unit": _unit("A", "GERMANY", "MUN"), "retreats": ["BOH"]}]),
            "dislodged units outside a retreat phase",
        ),
        (
            _with(phase_type="RETREAT", dislodged=[{"unit": _unit("A", "GERMANY", "MUN"), "retreats": ["XXX"]}]),
            "dislodged unit A MUN: unknown retreat XXX",
        ),
    ],
)
def test_a_board_the_map_cannot_hold_is_refused(client: TestClient, board: dict[str, Any], reason: str) -> None:
    resp = client.post("/sandbox/adjudicate", json={"state": board, "orders": {}}, headers=BOT)

    assert resp.status_code == 400
    assert resp.json()["detail"] == f"Invalid sandbox board: {reason}"


@pytest.mark.unit
def test_a_board_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(ValueError, match=r"^not a game state \(expected an object\)$"):
        game_service.sandbox_state(["not", "a", "board"])


@db
@pytest.mark.unit
def test_a_sandbox_from_a_game_starts_at_its_board_and_leaves_it_untouched(client: TestClient) -> None:
    email = f"sandbox_{int(time.time() * 1000)}@example.com"
    token = client.post("/auth/register", json={"email": email, "password": "testpass123"}).json()["access_token"]
    bearer = {"Authorization": f"Bearer {token}"}
    game_id = str(client.post("/games/create", json={"map_name": "standard"}, headers=bearer).json()["game_id"])

    start = client.post("/sandbox/start", json={"game_id": game_id}, headers=bearer)
    assert start.status_code == 200, start.text
    assert start.json()["source_game_id"] == game_id
    assert start.json()["state"] == game_service.state_json(game_id)
    _adjudicate(client, start.json()["state"], {"FRANCE": ["A PAR - BUR"]})

    assert client.get(f"/games/{game_id}/state").json()["phase"] == "S1901M"
    assert game_service.pending_orders_parsed(game_id) == {}


@db
@pytest.mark.unit
def test_a_sandbox_from_an_unknown_game_is_404(client: TestClient) -> None:
    resp = client.post("/sandbox/start", json={"game_id": "999999999"}, headers=BOT)

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Game not found"


@pytest.mark.map
@pytest.mark.unit
@pytest.mark.parametrize("overlay", ["board", "orders", "resolution"])
def test_the_sandbox_map_renders_each_overlay(client: TestClient, overlay: str) -> None:
    orders = {"FRANCE": ["A BUR - MUN", "A RUH S A BUR - MUN"]}

    resp = client.post(
        "/sandbox/map", json={"state": _fall_board(), "orders": orders, "overlay": overlay}, headers=BOT
    )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    assert resp.content.startswith(PNG_MAGIC)


@pytest.mark.map
@pytest.mark.unit
def test_the_sandbox_map_draws_the_orders(client: TestClient) -> None:
    board = _fall_board()
    orders = {"FRANCE": ["A BUR - MUN", "A RUH S A BUR - MUN"]}

    def render(overlay: str) -> bytes:
        return client.post(
            "/sandbox/map", json={"state": board, "orders": orders, "overlay": overlay}, headers=BOT
        ).content

    assert len({render("board"), render("orders"), render("resolution")}) == 3
