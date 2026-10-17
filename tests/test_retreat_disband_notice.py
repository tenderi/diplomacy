"""BJ1: a retreat phase's removals are announced to their power and the group.

Two units retreating into one province both bounce and are disbanded; a dislodged
unit left without an order though it had somewhere to go is disbanded by civil
disorder. Both used to be recorded as a plain disband and told to nobody: the DM
only named the next phase. A disband the power chose is still not announced.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import DislodgedUnit, GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_dm_addresses_you import _dms
from tests.test_draw_concede_notifications import GROUP, POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _dislodged(power: str, prov: str, retreats: list[str]) -> DislodgedUnit:
    return DislodgedUnit(
        unit=Unit(UnitKind.ARMY, power, Location(prov)),
        attacker_origin=None,
        retreats=tuple(Location(p) for p in retreats),
    )


def _retreats_owed(game_id: str) -> None:
    """FRANCE and ITALY can both retreat to PIE; RUSSIA's A WAR and GERMANY's A MUN
    could retreat too."""
    state = GameState(
        1901, Season.SPRING, PhaseType.RETREAT,
        units=frozenset({Unit(UnitKind.ARMY, "AUSTRIA", Location("VIE"))}),
        # Every power keeps a centre: a board that eliminated all but AUSTRIA
        # would end the game with it as the last power standing (BL6).
        ownership={
            "VIE": "AUSTRIA", "LON": "ENGLAND", "PAR": "FRANCE", "BER": "GERMANY",
            "ROM": "ITALY", "MOS": "RUSSIA", "ANK": "TURKEY",
        },
        dislodged=(
            _dislodged("FRANCE", "MAR", ["PIE", "GAS"]),
            _dislodged("ITALY", "VEN", ["PIE", "TUS"]),
            _dislodged("RUSSIA", "WAR", ["LVN", "UKR"]),
            _dislodged("GERMANY", "MUN", ["KIE"]),
        ),
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="S1901R")


def test_a_bounced_retreat_and_an_unordered_unit_are_announced() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    _retreats_owed(game_id)
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    # RUSSIA sends nothing; GERMANY chooses its disband.
    api_shared.game_service.submit_orders(game_id, "FRANCE", ["A MAR R PIE"])
    api_shared.game_service.submit_orders(game_id, "ITALY", ["A VEN R PIE"])
    api_shared.game_service.submit_orders(game_id, "GERMANY", ["D A MUN"])
    with OutboxProbe() as probe:
        api_shared.game_service.process_turn(game_id)
        api_shared.finish_processed_turn(game_id, row_id, prev_phase_code="S1901R", trigger="deadline")

    head = (
        f"The turn has been processed for game {game_id} because its deadline passed."
        " Orders are due for Fall 1901 movement."
    )
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    expected = {tg: [head] for tg in by_power.values()}
    expected[by_power["FRANCE"]] = [
        head + "\nA MAR's retreat to PIE bounced (FRANCE and ITALY both retreated there): it was disbanded."
    ]
    expected[by_power["ITALY"]] = [
        head + "\nA VEN's retreat to PIE bounced (FRANCE and ITALY both retreated there): it was disbanded."
    ]
    expected[by_power["RUSSIA"]] = [head + "\nA WAR had no retreat order and was disbanded (civil disorder)."]
    assert _dms(probe) == expected
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (
            GROUP,
            f"🔔 Turn Processed - Game {game_id}\n"
            "The turn has been processed. Fall 1901 movement: new orders are due -- send them to me in private.\n"
            "FRANCE: A MAR's retreat to PIE bounced (FRANCE and ITALY both retreated there): it was disbanded.\n"
            "ITALY: A VEN's retreat to PIE bounced (FRANCE and ITALY both retreated there): it was disbanded.\n"
            "RUSSIA: A WAR had no retreat order and was disbanded (civil disorder).",
        )
    ]
    # The web results list reads the same marks.
    results = api_shared.game_service.last_resolution_view(game_id)["results"]
    assert [(r["order_str"], r["result"], r["civil_disorder"]) for r in results] == [
        ("A MAR R PIE", "BOUNCE", False),
        ("A VEN R PIE", "BOUNCE", False),
        ("D A WAR", "DISBAND", True),
        ("D A MUN", "DISBAND", False),
    ]


def test_one_power_bouncing_two_of_its_own_units() -> None:
    client = TestClient(app)
    game_id, _users = _seeded_game(client)
    state = GameState(
        1901, Season.SPRING, PhaseType.RETREAT,
        units=frozenset(),
        dislodged=(_dislodged("FRANCE", "MAR", ["PIE"]), _dislodged("FRANCE", "TUS", ["PIE"])),
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="S1901R")
    api_shared.game_service.submit_orders(game_id, "FRANCE", ["A MAR R PIE", "A TUS R PIE"])
    api_shared.game_service.process_turn(game_id)
    turn = int(api_shared.game_service.meta(game_id)["current_turn"]) - 1
    assert api_shared.game_service.retreat_disbands(game_id, turn) == {
        "FRANCE": [
            "A MAR's retreat to PIE bounced (FRANCE retreated 2 units there): it was disbanded.",
            "A TUS's retreat to PIE bounced (FRANCE retreated 2 units there): it was disbanded.",
        ]
    }
    assert api_shared.game_service.civil_disorder_disbands(game_id, turn) == {}
