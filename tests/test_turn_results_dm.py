"""BW1 (issue #254): the turn-processed DM tells each player what happened to their
own units -- each order's outcome, units that held for want of an order, who
dislodged a unit, and after a Fall turn the centres gained and lost -- and the
group post does not.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_quit_and_replace import BOT_SECRET
from tests.test_turn_notifications import REQUIRED_POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _unit(kind: str, power: str, location: str) -> dict[str, str]:
    return {"kind": kind, "power": power, "location": location}


def _order(client: TestClient, game_id: str, tg: dict[str, str], power: str, orders: list[str]) -> None:
    resp = client.post(
        "/games/set_orders",
        json={"game_id": game_id, "power": power, "orders": orders, "telegram_id": tg[power], "bot_secret": BOT_SECRET},
    )
    assert resp.status_code == 200, resp.text
    assert all(r["success"] for r in resp.json()["results"]), resp.text


def _process(client: TestClient, game_id: str, users: list[tuple[dict, str]], monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, list[str]], list[str]]:
    """Process the turn as ENGLAND (the creator); each power's DMs, and the group posts."""
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        resp = client.post(f"/games/{game_id}/process_turn", headers=users[0][0])
        assert resp.status_code == 200, resp.text
    by_tg = probe.by_recipient()
    return {power: by_tg.get(tg, []) for power, (_h, tg) in zip(REQUIRED_POWERS, users)}, posted


def _restore(game_id: str, phase: str, units: list[dict[str, str]], **changes: Any) -> None:
    board = game_service.state_json(game_id)
    assert board is not None
    board.update(units=units, **changes)
    game_service.restore_snapshot(game_id, board, phase)


def test_movement_then_retreat_results(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """S1901M: France's A PAR - BUR bounces off Germany's A MUN - BUR, its F BRE - MAO
    succeeds and A MAR has no order; Italy's A TYR - TRI, supported, dislodges
    Austria's F TRI, which then retreats to ALB."""
    game_id, _row, users = _seeded_game(client)
    tg = dict(zip(REQUIRED_POWERS, (t for _h, t in users)))
    board = game_service.state_json(game_id)
    assert board is not None
    _restore(game_id, "S1901M", board["units"] + [_unit("A", "ITALY", "TYR")])
    _order(client, game_id, tg, "FRANCE", ["A PAR - BUR", "F BRE - MAO"])
    _order(client, game_id, tg, "GERMANY", ["A MUN - BUR", "A BER H", "F KIE H"])
    _order(client, game_id, tg, "ITALY", ["A TYR - TRI", "A VEN S A TYR - TRI"])
    _order(client, game_id, tg, "AUSTRIA", ["F TRI H"])

    messages, posted = _process(client, game_id, users, monkeypatch)
    head = f"The turn has been processed for game {game_id}. Spring 1901 retreats:"
    wait = f"{head} you have nothing to order this phase; wait for the other powers."
    results = "Your results for Spring 1901 movement:"
    assert messages["FRANCE"] == [
        f"{wait}\n{results}\nF BRE - MAO succeeded.\nA MAR held (no order).\nA PAR - BUR bounced."
    ]
    assert messages["GERMANY"] == [
        f"{wait}\n{results}\nA BER held.\nF KIE held.\nA MUN - BUR bounced."
    ]
    assert messages["ITALY"] == [
        f"{wait}\n{results}\nF NAP held (no order).\nA ROM held (no order).\nA TYR - TRI succeeded.\nA VEN S A TYR - TRI succeeded."
    ]
    assert messages["AUSTRIA"] == [
        f"{head} your orders are due.\n"
        "Your F TRI was dislodged: it may retreat to ADR, ALB, or disband. With no order it is disbanded.\n"
        f"{results}\nA BUD held (no order).\nF TRI was dislodged by A TYR (ITALY).\nA VIE held (no order)."
    ]
    # The group is told what is due, never anyone's results.
    assert posted == [
        "The turn has been processed. Spring 1901 retreats: orders are due from AUSTRIA -- send them to me in private."
    ]

    _order(client, game_id, tg, "AUSTRIA", ["F TRI R ALB"])
    messages, posted = _process(client, game_id, users, monkeypatch)
    assert messages["AUSTRIA"] == [
        f"The turn has been processed for game {game_id}. Orders are due for Fall 1901 movement.\n"
        "Your results for Spring 1901 retreats:\nF TRI retreated to ALB."
    ]
    # Nobody else had a unit in the retreat phase: their DM is unchanged.
    assert messages["FRANCE"] == [f"The turn has been processed for game {game_id}. Orders are due for Fall 1901 movement."]
    assert posted == ["The turn has been processed. Fall 1901 movement: new orders are due -- send them to me in private."]


def test_fall_centres_then_adjustment_results(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """F1901M: France takes BEL and MUN, which Germany left; the winter after it
    builds two and waives the third (its own choice, so not repeated back),
    and Germany disbands one."""
    game_id, _row, users = _seeded_game(client)
    tg = dict(zip(REQUIRED_POWERS, (t for _h, t in users)))
    board = game_service.state_json(game_id)
    assert board is not None
    units = [u for u in board["units"] if u["power"] not in ("FRANCE", "GERMANY")] + [
        _unit("A", "FRANCE", "PIC"),
        _unit("A", "FRANCE", "BUR"),
        _unit("A", "GERMANY", "MUN"),
        _unit("A", "GERMANY", "BER"),
        _unit("F", "GERMANY", "KIE"),
    ]
    _restore(game_id, "F1901M", units, season="FALL")
    _order(client, game_id, tg, "FRANCE", ["A PIC - BEL", "A BUR - MUN"])
    _order(client, game_id, tg, "GERMANY", ["A MUN - SIL"])

    messages, posted = _process(client, game_id, users, monkeypatch)
    head = f"The turn has been processed for game {game_id}. Winter 1901 builds: your orders are due."
    results = "Your results for Fall 1901 movement:"
    assert messages["FRANCE"] == [
        f"{head}\nYou may build 3 units (free home centres: BRE, MAR, PAR).\n"
        f"{results}\nA BUR - MUN succeeded.\nA PIC - BEL succeeded.\nCentres: +BEL, +MUN (now 5)."
    ]
    assert messages["GERMANY"] == [
        f"{head}\nYou must disband 1 unit. With no order, civil disorder picks which units are disbanded.\n"
        f"{results}\nA BER held (no order).\nF KIE held (no order).\nA MUN - SIL succeeded.\nCentres: -MUN (now 2)."
    ]
    assert all("results" not in text and "Centres" not in text for text in posted)

    _order(client, game_id, tg, "FRANCE", ["BUILD A PAR", "BUILD F BRE", "WAIVE"])
    _order(client, game_id, tg, "GERMANY", ["D A SIL"])
    messages, posted = _process(client, game_id, users, monkeypatch)
    head = f"The turn has been processed for game {game_id}. Orders are due for Spring 1902 movement."
    assert messages["FRANCE"] == [
        f"{head}\nYour results for Winter 1901 builds:\nF BRE was built.\nA PAR was built."
    ]
    assert messages["GERMANY"] == [f"{head}\nYour results for Winter 1901 builds:\nA SIL was disbanded."]
    assert posted == ["The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private."]
