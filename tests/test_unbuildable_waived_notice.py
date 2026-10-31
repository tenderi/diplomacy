"""CA2, end to end: a power owed builds with no free home centre is told they are waived.

A Fall movement turn is processed into a Winter in which ITALY holds a fourth centre (TUN)
but every home centre is occupied. The DM for the adjustment phase must say so, whether
ITALY's player is the caller who processed the turn, and whether the phase is processed
at once because nobody else owes anything (the line then rides in the next phase's DM).
"""
from __future__ import annotations

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_dm_addresses_you import _dms
from tests.test_draw_concede_notifications import POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]

_HOME = {"FRANCE": "PAR", "GERMANY": "BER", "RUSSIA": "MOS", "TURKEY": "ANK", "AUSTRIA": "VIE"}


_RESULTS = "\nYour results for Fall 1901 movement:\nNo orders, so F NAP, A ROM and A VEN held."
_NOT_ORDERED = "\nAUSTRIA, ENGLAND, FRANCE, GERMANY, ITALY, RUSSIA and TURKEY had not ordered: their units held."
_TAIL = _RESULTS + _NOT_ORDERED


def _fall_board(game_id: str, england_owes: bool) -> None:
    """F1901M. ITALY: A ROM, A VEN, F NAP and the centre TUN (no unit there): one build owed,
    all three home centres occupied. ENGLAND: A LON, F EDI, and LVP free if ``england_owes``."""
    units = {
        Unit(UnitKind.ARMY, "ITALY", Location("ROM")),
        Unit(UnitKind.ARMY, "ITALY", Location("VEN")),
        Unit(UnitKind.FLEET, "ITALY", Location("NAP")),
        Unit(UnitKind.ARMY, "ENGLAND", Location("LON")),
        Unit(UnitKind.FLEET, "ENGLAND", Location("EDI")),
    } | {Unit(UnitKind.ARMY, p, Location(h)) for p, h in _HOME.items()}
    ownership = {
        "ROM": "ITALY", "VEN": "ITALY", "NAP": "ITALY", "TUN": "ITALY",
        "LON": "ENGLAND", "EDI": "ENGLAND", "LVP": "ENGLAND", **{h: p for p, h in _HOME.items()},
    }
    if not england_owes:
        units.add(Unit(UnitKind.ARMY, "ENGLAND", Location("LVP")))
    state = GameState(1901, Season.FALL, PhaseType.MOVEMENT, units=frozenset(units), ownership=ownership)
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="F1901M")


def _process(game_id: str, caller: Optional[str]) -> OutboxProbe:
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    with OutboxProbe() as probe:
        api_shared.game_service.process_turn(game_id)
        api_shared.after_turn_processed(
            game_id, row_id, prev_phase_code="F1901M", trigger="deadline", exclude_telegram_id=caller
        )
    return probe


def test_an_unbuildable_power_is_told_while_another_power_still_owes_builds() -> None:
    game_id, users = _seeded_game(TestClient(app))
    _fall_board(game_id, england_owes=True)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    probe = _process(game_id, caller=None)
    head = f"The turn has been processed for game {game_id} because its deadline passed. Winter 1901 builds:"
    dms = _dms(probe)
    assert dms[by_power["ITALY"]] == [
        f"{head} you have nothing to order this phase; wait for the other powers."
        "\nYour 1 build is waived: no free home supply centre." + _TAIL
    ]
    assert dms[by_power["ENGLAND"]] == [
        f"{head} your orders are due.\nYou may build 1 unit (free home centres: LVP).\n"
        "Your results for Fall 1901 movement:\nNo orders, so F EDI and A LON held." + _NOT_ORDERED
    ]


def test_the_caller_whose_power_is_unbuildable_is_still_told() -> None:
    game_id, users = _seeded_game(TestClient(app))
    _fall_board(game_id, england_owes=True)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    probe = _process(game_id, caller=by_power["ITALY"])
    head = f"The turn has been processed for game {game_id} because its deadline passed. Winter 1901 builds:"
    assert _dms(probe)[by_power["ITALY"]] == [
        f"{head} you have nothing to order this phase; wait for the other powers."
        "\nYour 1 build is waived: no free home supply centre." + _TAIL
    ]


def test_a_folded_adjustment_hands_the_line_to_the_next_phase_dm() -> None:
    game_id, users = _seeded_game(TestClient(app))
    _fall_board(game_id, england_owes=False)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    probe = _process(game_id, caller=None)
    assert api_shared.game_service.meta(game_id)["phase_code"] == "S1902M"
    head = f"The turn has been processed for game {game_id} because its deadline passed."
    dms = _dms(probe)
    assert dms[by_power["ITALY"]] == [
        f"{head} Orders are due for Spring 1902 movement."
        + _RESULTS
        + "\nYour 1 build is waived: no free home supply centre."
        + _NOT_ORDERED
    ]
