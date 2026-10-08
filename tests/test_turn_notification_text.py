"""BA4: the "turn processed" DM names the new phase and says what each player owes.

It used to tell every player "Your next orders are due" whatever the phase: in a
retreat phase six powers with nothing to do were asked for orders, and the
dislodged power was not told which unit was dislodged or where it could go; in
a winter, nobody was told their build or disband count.
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


def _by_power(probe: OutboxProbe, users: list[tuple[dict, str]]) -> dict[str, list[str]]:
    by_tg = probe.by_recipient()
    return {power: by_tg.get(tg, []) for power, (_h, tg) in zip(REQUIRED_POWERS, users)}


def _board(game_id: str, **changes: Any) -> dict[str, Any]:
    board = game_service.state_json(game_id)
    assert board is not None
    board.update(changes)
    return board


def test_a_movement_phase_names_itself(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    game_id, _row, users = _seeded_game(client)
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=users[0][0]).status_code == 200
    messages = _by_power(probe, users)
    assert messages["ENGLAND"] == []  # the caller has the result in the response
    for power in REQUIRED_POWERS[1:]:
        assert messages[power] == [f"The turn has been processed for game {game_id}. Orders are due for Fall 1901 movement."]
    assert posted == ["The turn has been processed. Fall 1901 movement: new orders are due -- send them to me in private."]


def test_a_retreat_phase_tells_the_dislodged_their_options_and_the_rest_to_wait(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1901M: France takes BUR from Germany, Germany takes BEL from England.
    England (the creator) processes the turn and is dislodged, so it is told too."""
    game_id, _row, users = _seeded_game(client)
    board = game_service.state_json(game_id)
    extra = [
        {"kind": "A", "power": "GERMANY", "location": "BUR"},
        {"kind": "A", "power": "GERMANY", "location": "RUH"},
        {"kind": "A", "power": "GERMANY", "location": "HOL"},
        {"kind": "A", "power": "ENGLAND", "location": "BEL"},
    ]
    game_service.restore_snapshot(
        game_id, _board(game_id, season="FALL", units=board["units"] + extra), "F1901M"
    )
    tg = dict(zip(REQUIRED_POWERS, (t for _h, t in users)))
    for power, orders in [
        ("FRANCE", ["A PAR - BUR", "A MAR S A PAR - BUR"]),
        ("GERMANY", ["A RUH - BEL", "A HOL S A RUH - BEL"]),
    ]:
        resp = client.post(
            "/games/set_orders",
            json={"game_id": game_id, "power": power, "orders": orders, "telegram_id": tg[power], "bot_secret": BOT_SECRET},
        )
        assert resp.status_code == 200, resp.text

    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        assert client.post(f"/games/{game_id}/process_turn", headers=users[0][0]).status_code == 200
    assert client.get(f"/games/{game_id}/state").json()["phase"] == "F1901R"

    head = f"The turn has been processed for game {game_id}. Fall 1901 retreats:"
    messages = _by_power(probe, users)
    assert messages["ENGLAND"] == [
        f"{head} your orders are due.\nYour A BEL was dislodged: it may retreat to PIC, or disband."
    ]
    assert messages["GERMANY"] == [
        f"{head} your orders are due.\n"
        "Your A BUR was dislodged: it may retreat to GAS, PIC, RUH, or disband."
    ]
    for power in ("FRANCE", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"):
        assert messages[power] == [f"{head} you have nothing to order this phase; wait for the other powers."]
    assert posted == [
        "The turn has been processed. Fall 1901 retreats: orders are due from ENGLAND, GERMANY"
        " -- send them to me in private."
    ]


def test_an_adjustment_phase_gives_each_power_its_count(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """W1901A: France is three centres up with two free home centres, Austria one
    down, Italy one up with every home centre occupied (nothing it can do)."""
    game_id, row, users = _seeded_game(client)
    board = game_service.state_json(game_id)
    units = [u for u in board["units"] if u["power"] != "FRANCE"] + [
        {"kind": "A", "power": "FRANCE", "location": "BUR"},
        {"kind": "A", "power": "FRANCE", "location": "SPA"},
        {"kind": "F", "power": "FRANCE", "location": "BRE"},
    ]
    ownership = {**board["ownership"], "SPA": "FRANCE", "POR": "FRANCE", "BEL": "FRANCE", "TRI": "ITALY"}
    game_service.restore_snapshot(
        game_id, _board(game_id, season="WINTER", phase_type="ADJUSTMENT", units=units, ownership=ownership), "W1901A"
    )
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        api_shared.notify_turn_processed(
            game_id, row, trigger="deadline", next_deadline_text="2026-10-05 16:00 UTC"
        )

    head = f"The turn has been processed for game {game_id} because its deadline passed. Winter 1901 builds:"
    due = " Next deadline: 2026-10-05 16:00 UTC."
    messages = _by_power(probe, users)
    assert messages["FRANCE"] == [
        f"{head} your orders are due.\nYou may build 2 units (1 more waived: no free home supply centre).{due}"
    ]
    assert messages["AUSTRIA"] == [f"{head} your orders are due.\nYou must disband 1 unit.{due}"]
    for power in ("ENGLAND", "GERMANY", "ITALY", "RUSSIA", "TURKEY"):
        assert messages[power] == [f"{head} you have nothing to order this phase; wait for the other powers.{due}"]
    assert posted == [
        "The turn has been processed. Winter 1901 builds: orders are due from AUSTRIA, FRANCE"
        f" -- send them to me in private.{due}"
    ]


def test_a_retreat_unit_with_nowhere_to_go_must_disband() -> None:
    text = api_shared.turn_message(
        "Head.", "Fall 1901 retreats", "RETREAT", {"ITALY": {"retreats": [{"unit": "F ION", "options": []}]}}
    )
    assert text == (
        "Head. Fall 1901 retreats: your orders are due.\n"
        "Your F ION was dislodged and has nowhere to retreat: it must disband."
    )


def test_a_player_holding_two_powers_is_told_which_line_is_whose() -> None:
    """BD4: the DM says "you"; only a player owing orders for two powers is told
    which power each line is about."""
    retreats = api_shared.turn_message(
        "Head.",
        "Fall 1901 retreats",
        "RETREAT",
        {
            "ITALY": {"retreats": [{"unit": "F ION", "options": ["TUN"]}]},
            "AUSTRIA": {"retreats": [{"unit": "A VIE", "options": []}]},
        },
    )
    assert retreats == (
        "Head. Fall 1901 retreats: your orders are due for AUSTRIA and ITALY.\n"
        "Your A VIE (AUSTRIA) was dislodged and has nowhere to retreat: it must disband.\n"
        "Your F ION (ITALY) was dislodged: it may retreat to TUN, or disband."
    )
    builds = api_shared.turn_message(
        "Head.", "Winter 1901 builds", "ADJUSTMENT", {"FRANCE": {"build": 1}, "AUSTRIA": {"disband": 2}}
    )
    assert builds == (
        "Head. Winter 1901 builds: your orders are due for AUSTRIA and FRANCE.\n"
        "As AUSTRIA, you must disband 2 units.\n"
        "As FRANCE, you may build 1 unit."
    )


def test_a_dislodged_dummy_owes_nobody_anything(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A civil-disorder dummy's retreat is played by the engine: the humans are not
    told to wait for it, and the channel does not list it as owing orders."""
    from tests.test_auto_process import _table

    game_id, e, f = _table(client, auto=False)  # GERMANY is a dummy
    dislodged = [
        {"unit": {"kind": "A", "power": "GERMANY", "location": "BUR"}, "attacker_origin": "PAR", "retreats": ["GAS"]}
    ]
    game_service.restore_snapshot(
        game_id, _board(game_id, season="FALL", phase_type="RETREAT", dislodged=dislodged), "F1901R"
    )
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        api_shared.notify_turn_processed(game_id, int(game_id), trigger="manual")

    wait = (
        f"The turn has been processed for game {game_id}. Fall 1901 retreats: "
        "you have nothing to order this phase; wait for the other powers."
    )
    assert probe.by_recipient() == {e: [wait], f: [wait]}
    assert posted == ["The turn has been processed. Fall 1901 retreats: nobody has anything to order."]
