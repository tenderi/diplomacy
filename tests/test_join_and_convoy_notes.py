"""BV4: seating a table DMs nobody per join, and a non-adjacent army move says it needs a convoy."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.bot_client import BotTestClient

from server._api_module import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_anonymous_games import _BOT, _as, _telegram_user
from tests.test_draw_concede_notifications import GROUP

pytestmark = [pytest.mark.integration, pytest.mark.database]

POWERS = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]


def _seat_all(client: TestClient, *, group: bool) -> tuple[str, dict[str, str], OutboxProbe]:
    users = {p: _telegram_user(client, p[:3].title())[0] for p in POWERS}
    created = client.post("/games/create", json={"map_name": "standard", **_as(users["AUSTRIA"])}, headers=_BOT)
    game_id = str(created.json()["game_id"])
    if group:
        api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    with OutboxProbe() as probe:
        for p in POWERS:
            assert client.post(f"/games/{game_id}/join", json=_as(users[p], power=p)).status_code == 200
    return game_id, users, probe


def test_seating_seven_players_dms_each_one_confirmation_and_the_start_only() -> None:
    client = BotTestClient(app)
    game_id, users, probe = _seat_all(client, group=True)
    dms = [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "dm"]
    for p, tg in users.items():
        mine = [m for t, m in dms if t == tg]
        assert mine[0] == f"You have joined game {game_id} as {p}."
        assert mine[1:] == [
            f"Game {game_id} has started! You play {p}. It is Spring 1901 movement: orders are due."
        ]
    assert len(dms) == 14
    group = [r["message"] for r in probe.rows() if r["kind"] == "channel_text"]
    joins = [m for m in group if "has joined" in m]
    assert len(joins) == 7
    assert joins[2].endswith(f"has joined game {game_id} as FRANCE.")


def test_a_join_without_a_group_is_not_announced_to_the_table() -> None:
    client = BotTestClient(app)
    _game_id, _users, probe = _seat_all(client, group=False)
    assert not any("has joined" in r["message"] for r in probe.rows())


def test_a_vacated_seat_filled_mid_game_is_dmed_to_the_table() -> None:
    client = BotTestClient(app)
    game_id, users, _probe = _seat_all(client, group=False)
    assert client.post(f"/games/{game_id}/quit", json=_as(users["FRANCE"], power="FRANCE")).status_code == 200
    newcomer = _telegram_user(client, "Neu")[0]
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/join", json=_as(newcomer, power="FRANCE")).status_code == 200
    joined = [r["telegram_id"] for r in probe.rows() if r["kind"] == "dm" and "has joined" in r["message"]]
    others = {tg for p, tg in users.items() if p != "FRANCE"}
    assert set(joined) == others and len(joined) == 6


def test_a_non_adjacent_army_move_is_accepted_with_a_convoy_note() -> None:
    client = BotTestClient(app)
    game_id, users, _probe = _seat_all(client, group=False)
    body = _as(users["ITALY"], game_id=game_id, power="ITALY")
    resp = client.post("/games/set_orders", json={**body, "orders": ["A VEN - TUN", "A ROM - APU", "F NAP - ION"]})
    results = resp.json()["results"]
    assert [r["success"] for r in results] == [True, True, True]
    # No fleet stands at sea on the opening board, so no convoy can carry it (#460).
    no_route = "A VEN - TUN cannot succeed this turn: no chain of fleets at sea reaches from VEN to TUN, so no convoy can carry it"
    assert results[0]["note"] == no_route
    assert results[0]["notes"] == [{"kind": "impossible", "code": "no_convoy_route", "text": no_route}]
    assert results[1].get("note") is None
    assert results[2].get("note") is None
    assert resp.json()["notes"] == []  # all three Italian units have an order


def test_order_notes_explain_a_draft_and_show_only_the_players_own_orders() -> None:
    """#460: the read route explains a draft before submitting, and another power's
    pending orders change nothing in it."""
    client = TestClient(app)
    game_id, users, _probe = _seat_all(client, group=False)
    italy = _as(users["ITALY"], game_id=game_id, power="ITALY")
    austria = _as(users["AUSTRIA"], game_id=game_id, power="AUSTRIA")
    url = f"/games/{game_id}/orders/ITALY/notes"

    before = client.post(url, json={**italy, "orders": ["A VEN - TRI", "A ROM - VEN"]})
    assert before.status_code == 200
    # Austria orders its fleet out of Trieste: secret, so Italy's notes must not change.
    assert client.post("/games/set_orders", json={**austria, "orders": ["F TRI - ALB"]}).status_code == 200
    after = client.post(url, json={**italy, "orders": ["A VEN - TRI", "A ROM - VEN"]})
    assert after.json() == before.json()
    assert after.json()["power"] == "ITALY"
    assert after.json()["notes"] == [{"kind": "warning", "code": "unordered", "text": "F NAP has no order, so it will hold"}]

    # merge lays a pick over the stored orders, as the bot submits it.
    assert client.post("/games/set_orders", json={**italy, "orders": ["A VEN H", "A ROM H", "F NAP H"]}).status_code == 200
    merged = client.post(url, json={**italy, "orders": ["A ROM S A VEN - TUS"], "merge": True}).json()
    assert [e["order"] for e in merged["orders"]] == ["A VEN H", "F NAP H", "A ROM S A VEN - TUS"]
    assert merged["orders"][2]["notes"][0]["text"] == "A ROM supports A VEN - TUS, but A VEN is ordered to hold"
    stored = client.post(url, json=italy).json()
    assert [e["order"] for e in stored["orders"]] == ["A VEN H", "A ROM H", "F NAP H"]

    # Only the power's own player may ask.
    assert client.post(url, json={**austria, "orders": ["A VEN H"]}).status_code == 403


def test_a_support_onto_the_supporters_own_unit_is_accepted_with_a_note() -> None:
    """CA4: legal, but void unless that unit moves away -- said at submission."""
    client = BotTestClient(app)
    game_id, users, _probe = _seat_all(client, group=False)
    body = _as(users["AUSTRIA"], game_id=game_id, power="AUSTRIA")
    resp = client.post("/games/set_orders", json={**body, "orders": ["A VIE S A VEN - TRI", "A BUD S A VIE - GAL"]})
    results = resp.json()["results"]
    assert [r["success"] for r in results] == [True, True]
    assert results[0]["note"] == "your own F TRI is there: this support has no effect unless it moves away"
    assert results[1].get("note") is None
