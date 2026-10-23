"""BR3: the resolution after a retreat phase also carries the movement phase's results.

An adjustment (or the next movement) follows a retreat phase, and the retreat results
alone ("had no orders recorded") cannot say why a power has builds or disbands.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from persistence.game_repo import GameRepo
from server.game_service import GameService

pytestmark = pytest.mark.database


@pytest.fixture
def service(temp_db):
    return GameService(GameRepo(sessionmaker(bind=temp_db)))


def _dislodging_board() -> GameState:
    """Spring movement: FRANCE's A BUR, supported from RUH, dislodges A MUN."""
    return GameState(
        1901, Season.SPRING, PhaseType.MOVEMENT,
        units=frozenset({
            Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
            Unit(UnitKind.ARMY, "FRANCE", Location("RUH")),
            Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
        }),
        ownership={
            "PAR": "FRANCE", "BER": "GERMANY", "LON": "ENGLAND", "VIE": "AUSTRIA",
            "ROM": "ITALY", "MOS": "RUSSIA", "ANK": "TURKEY",
        },
    )


def test_last_resolution_after_a_retreat_carries_the_movement_results(service) -> None:
    gid = f"br3-{uuid.uuid4().hex[:8]}"
    service.create_game(gid)
    service.restore_snapshot(gid, state_to_dict(_dislodging_board()), phase_code="S1901M")
    service.submit_orders(gid, "FRANCE", ["A BUR - MUN", "A RUH S A BUR - MUN"])
    service.process_turn(gid)
    assert service.view(gid)["phase"] == "S1901R"
    # The last resolution is a movement one: nothing extra.
    after_movement = service.last_resolution_view(gid)
    assert "movement" not in after_movement
    service.submit_orders(gid, "GERMANY", ["A MUN R KIE"])
    service.process_turn(gid)
    view = service.last_resolution_view(gid)
    assert [(r["power"], r["order_str"], r["result"]) for r in view["results"]] == [
        ("GERMANY", "A MUN R KIE", "OK"),
    ]
    assert view["movement"] == {"results": after_movement["results"]}
    assert [(r["order_str"], r["result"]) for r in view["movement"]["results"] if r["power"] == "FRANCE"] == [
        ("A BUR - MUN", "OK"), ("A RUH S A BUR - MUN", "OK"),
    ]
