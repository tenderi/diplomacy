"""BV4: seating a table DMs nobody per join, and a non-adjacent army move says it needs a convoy."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.game_service import NEEDS_CONVOY_NOTE
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
    client = TestClient(app)
    game_id, users, probe = _seat_all(client, group=True)
    dms = [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "dm"]
    started = f"Game {game_id} is now full. The game has started! Good luck to all players."
    for p, tg in users.items():
        mine = [m for t, m in dms if t == tg]
        assert mine[0] == f"You have joined game {game_id} as {p}."
        assert len(mine) == 2 and mine[1].startswith(started)
    assert len(dms) == 14
    group = [r["message"] for r in probe.rows() if r["kind"] == "channel_text"]
    joins = [m for m in group if "has joined" in m]
    assert len(joins) == 7
    assert joins[2].endswith(f"has joined game {game_id} as FRANCE.")


def test_a_join_without_a_group_is_not_announced_to_the_table() -> None:
    client = TestClient(app)
    _game_id, _users, probe = _seat_all(client, group=False)
    assert not any("has joined" in r["message"] for r in probe.rows())


def test_a_non_adjacent_army_move_is_accepted_with_a_convoy_note() -> None:
    client = TestClient(app)
    game_id, users, _probe = _seat_all(client, group=False)
    body = _as(users["ITALY"], game_id=game_id, power="ITALY")
    resp = client.post("/games/set_orders", json={**body, "orders": ["A VEN - TUN", "A ROM - APU", "F NAP - ION"]})
    results = resp.json()["results"]
    assert [r["success"] for r in results] == [True, True, True]
    assert results[0]["note"] == NEEDS_CONVOY_NOTE
    assert results[1].get("note") is None
    assert results[2].get("note") is None
