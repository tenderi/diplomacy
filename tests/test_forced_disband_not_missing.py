"""BJ2: a dislodged unit with nowhere to retreat needs no order.

The adjudicator disbands it whatever its power says, so a power whose only
dislodged units are trapped owes nothing in the retreat phase: it is not
``missing`` in ``orders_status``, an ``auto_process`` game does not wait for it,
and the group post does not list it as due. Its player is still told the unit
is lost. A power with one unit that can retreat is still waited on.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.api import app
from server.api import shared as api_shared
from server.api.shared import game_service
from tests.conftest import _get_db_url
from tests.reliability_helpers import OutboxProbe
from tests.test_auto_process import _order, _phase, _table

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _dislodged(power: str, prov: str, attacker: str, retreats: list[str]) -> dict[str, Any]:
    return {"unit": {"kind": "A", "power": power, "location": prov}, "attacker_origin": attacker, "retreats": retreats}


def _retreat_phase(game_id: str, dislodged: list[dict[str, Any]]) -> None:
    board = game_service.state_json(game_id)
    assert board is not None
    board.update(season="FALL", phase_type="RETREAT", dislodged=dislodged)
    game_service.restore_snapshot(game_id, board, "F1901R")


def test_a_trapped_unit_owes_nothing_and_auto_process_does_not_wait(client: TestClient) -> None:
    game_id, e, _f = _table(client, auto=True)  # ENGLAND and FRANCE seated, the rest dummies
    _retreat_phase(
        game_id,
        [_dislodged("FRANCE", "BUR", "MUN", []), _dislodged("ENGLAND", "BEL", "RUH", ["PIC"])],
    )
    status = game_service.orders_status(game_id)
    assert status is not None
    assert status["active_powers"] == ["ENGLAND"]
    assert status["missing"] == ["ENGLAND"]
    assert status["nothing_to_do"] == ["FRANCE"]

    # England's retreat is the only order owed: it runs the turn by itself.
    assert _order(client, game_id, e, "ENGLAND", ["A BEL R PIC"])["auto_processed"] == 1
    assert _phase(client, game_id) == "W1901A"


def test_a_power_with_one_real_retreat_is_still_waited_on(client: TestClient) -> None:
    game_id, _e, f = _table(client, auto=True)
    _retreat_phase(
        game_id,
        [_dislodged("FRANCE", "BUR", "MUN", []), _dislodged("FRANCE", "BEL", "RUH", ["PIC"])],
    )
    status = game_service.orders_status(game_id)
    assert status is not None
    assert status["active_powers"] == ["FRANCE"]
    assert status["missing"] == ["FRANCE"]
    assert game_service.ready_to_auto_process(game_id) is False
    # Its one real retreat is all it owes: the trapped A BUR needs no order.
    assert _order(client, game_id, f, "FRANCE", ["A BEL R PIC"])["auto_processed"] == 1
    assert _phase(client, game_id) == "W1901A"


def test_the_trapped_power_is_told_and_not_listed_as_due(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id, e, f = _table(client, auto=False)
    _retreat_phase(
        game_id,
        [_dislodged("FRANCE", "BUR", "MUN", []), _dislodged("ENGLAND", "BEL", "RUH", ["PIC"])],
    )
    posted: list[str] = []
    monkeypatch.setattr(api_shared, "_post_turn_to_channel", lambda _g, text, *_a: posted.append(text))
    with OutboxProbe() as probe:
        api_shared.notify_turn_processed(game_id, int(game_id), trigger="manual")

    head = f"The turn has been processed for game {game_id}. Fall 1901 retreats:"
    assert probe.by_recipient() == {
        e: [f"{head} your orders are due.\nYour A BEL was dislodged: it may retreat to PIC, or disband."],
        f: [
            f"{head} you have nothing to order this phase; wait for the other powers.\n"
            "Your A BUR was dislodged and has nowhere to retreat: it is disbanded, no order needed."
        ],
    }
    assert posted == [
        "The turn has been processed. Fall 1901 retreats: orders are due from ENGLAND -- send them to me in private."
    ]
