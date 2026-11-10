"""Track DD1 and DD2: who "the caller" is, and which phase a manual process processes.

DD1: the player-action routes leave the caller out of the DM fan-out (they get the
outcome in their response). The excluded id used to be the request body's
``telegram_id`` whenever one was sent, even when the request authenticated with a
Bearer token -- which ``resolve_user_or_telegram`` ignores the body id for. A seated
web player could name another player's Telegram id there and that player got no DM.

DD2: ``POST /games/{id}/process_turn`` read the phase and then processed whatever
phase was stored by the time it got there. A deadline processing S1901M in between
meant the creator's press adjudicated F1901M with nobody's orders.
"""
from __future__ import annotations

import itertools
import time
from typing import Any, Callable
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe

pytestmark = [pytest.mark.integration, pytest.mark.database]

POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]
_seq = itertools.count(1)


def _register(client: TestClient, tag: str) -> tuple[dict, str]:
    stamp = f"{int(time.time() * 1000000)}_{tag}_{next(_seq)}"
    telegram_id = str(abs(hash(stamp)) % 10**9)
    resp = client.post("/auth/register", json={"email": f"dd_{stamp}@example.com", "password": "testpass123"})
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    user_id = int(client.get("/auth/me", headers=headers).json()["id"])
    api_shared.db_service.set_user_telegram_id(user_id, telegram_id)
    return headers, telegram_id


def _seeded_game(client: TestClient) -> tuple[str, list[tuple[dict, str]]]:
    """A game created by ENGLAND's user, every power held by a Telegram-linked web user."""
    users = [_register(client, p) for p in POWERS]
    resp = client.post("/games/create", json={"map_name": "standard"}, headers=users[0][0])
    assert resp.status_code == 200, resp.text
    game_id = str(resp.json()["game_id"])
    for power, (headers, _tg) in zip(POWERS, users):
        r = client.post(f"/games/{game_id}/join", json={"game_id": int(game_id), "power": power}, headers=headers)
        assert r.status_code == 200, f"join {power}: {r.text}"
    return game_id, users


def _propose(client: TestClient, game_id: str, headers: dict) -> None:
    r = client.post(f"/games/{game_id}/deadline/propose", json={"power": "FRANCE", "hours": 24}, headers=headers)
    assert r.status_code == 200, r.text


# (route, body, setup run before the probe)
_ROUTES: list[tuple[str, dict[str, Any], Callable[[TestClient, str, list], None]]] = [
    ("wait", {"power": "ENGLAND", "waiting": True}, lambda c, g, u: None),
    ("draw_vote", {"power": "ENGLAND", "vote": True}, lambda c, g, u: None),
    ("concede", {"power": "ENGLAND"}, lambda c, g, u: None),
    ("deadline/propose", {"power": "ENGLAND", "hours": 48}, lambda c, g, u: None),
    ("deadline/vote", {"power": "ENGLAND", "vote": True}, lambda c, g, u: _propose(c, g, u[1][0])),
]


@pytest.mark.parametrize(("route", "body", "setup"), _ROUTES, ids=[r[0] for r in _ROUTES])
def test_a_web_player_cannot_name_someone_else_as_the_caller(
    route: str, body: dict[str, Any], setup: Callable[[TestClient, str, list], None]
) -> None:
    """DD1: ENGLAND (Bearer) puts GERMANY's Telegram id in the body. GERMANY must
    still be told; ENGLAND, the real caller, must not be."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    setup(client, game_id, users)
    caller_headers, caller_tg = users[0]
    victim_tg = users[2][1]

    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/{route}", json={**body, "telegram_id": victim_tg}, headers=caller_headers)
    assert resp.status_code == 200, resp.text

    everyone = {tg for _h, tg in users}
    assert probe.recipients() == everyone - {caller_tg}


def test_manual_process_pins_the_phase_it_read() -> None:
    """DD2: the deadline processes S1901M between the route's read and its process
    call. The press must be a 409, not an adjudication of F1901M."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    real = api_shared.game_service.process_turn
    calls: list[Any] = []

    def deadline_first(gid: str, expected_phase_code: Any = None) -> dict[str, Any]:
        calls.append(expected_phase_code)
        real(gid, expected_phase_code="S1901M")  # the scheduler commits first
        return real(gid, expected_phase_code=expected_phase_code)

    with patch.object(api_shared.game_service, "process_turn", side_effect=deadline_first):
        resp = client.post(f"/games/{game_id}/process_turn", headers=users[0][0])
    assert calls == ["S1901M"]
    assert resp.status_code == 409, resp.text
    assert resp.headers["X-Error-Code"] == "phase_moved"
    assert resp.json()["detail"] == (
        "Phase S1901M has already been processed: the game is now in F1901M. "
        "Nothing was processed; check the new board."
    )
    assert api_shared.game_service.view(game_id)["phase"] == "F1901M"


def test_a_client_that_saw_an_older_phase_gets_409() -> None:
    """DD2: the web and the bot's confirm button send the phase they showed."""
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    creator = users[0][0]
    first = client.post(f"/games/{game_id}/process_turn", json={"expected_phase_code": "S1901M"}, headers=creator)
    assert first.status_code == 200, first.text
    assert first.json()["phase"] == "F1901M"

    stale = client.post(f"/games/{game_id}/process_turn", json={"expected_phase_code": "S1901M"}, headers=creator)
    assert stale.status_code == 409, stale.text
    assert stale.headers["X-Error-Code"] == "phase_moved"
    assert stale.json()["detail"] == (
        "Phase S1901M has already been processed: the game is now in F1901M. "
        "Nothing was processed; check the new board."
    )
    assert api_shared.game_service.view(game_id)["phase"] == "F1901M"
