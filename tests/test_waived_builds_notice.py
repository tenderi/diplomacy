"""BO2: builds waived because a power sent no adjustment orders are announced.

The power's player and the game's group read that N builds were waived because no
orders came in. A power that chose its outcome (an explicit waive) is not told.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.serialization import state_to_dict
from engine.types import GameState, Location, PhaseType, Season, Unit, UnitKind
from server.api import app
from server.api import shared as api_shared
from tests.reliability_helpers import OutboxProbe
from tests.test_dm_addresses_you import _dms
from tests.test_draw_concede_notifications import GROUP, POWERS, _seeded_game

pytestmark = [pytest.mark.integration, pytest.mark.database]


def _winter_with_builds_owed(game_id: str) -> None:
    """FRANCE owns PAR, MAR, BRE with one army (2 builds owed); ENGLAND owns LON, EDI
    with one army (1 build owed); everyone else is balanced."""
    units = {
        Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
        Unit(UnitKind.ARMY, "ENGLAND", Location("LON")),
        Unit(UnitKind.ARMY, "GERMANY", Location("BER")),
        Unit(UnitKind.ARMY, "ITALY", Location("ROM")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("MOS")),
        Unit(UnitKind.ARMY, "TURKEY", Location("ANK")),
        Unit(UnitKind.ARMY, "AUSTRIA", Location("VIE")),
    }
    state = GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset(units),
        ownership={
            "PAR": "FRANCE", "MAR": "FRANCE", "BRE": "FRANCE", "LON": "ENGLAND", "EDI": "ENGLAND",
            "BER": "GERMANY", "ROM": "ITALY", "MOS": "RUSSIA", "ANK": "TURKEY", "VIE": "AUSTRIA",
        },
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="W1901A")


def test_the_adjustment_dm_names_the_free_home_centres() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    _winter_with_builds_owed(game_id)
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    with OutboxProbe() as probe:
        api_shared.notify_turn_processed(game_id, row_id, trigger="deadline")
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    head = (
        f"The turn has been processed for game {game_id} because its deadline passed."
        " Winter 1901 builds: your orders are due."
    )
    dms = _dms(probe)
    assert dms[by_power["FRANCE"]] == [head + "\nYou may build 2 units (free home centres: BRE, MAR, PAR)."]
    assert dms[by_power["ENGLAND"]] == [head + "\nYou may build 1 unit (free home centres: EDI)."]


def test_builds_waived_for_want_of_orders_are_announced() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    _winter_with_builds_owed(game_id)
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    # ENGLAND chooses to waive; FRANCE sends nothing.
    api_shared.game_service.submit_orders(game_id, "ENGLAND", ["WAIVE"])
    with OutboxProbe() as probe:
        api_shared.game_service.process_turn(game_id)
        api_shared.finish_processed_turn(game_id, row_id, prev_phase_code="W1901A", trigger="deadline")

    head = (
        f"The turn has been processed for game {game_id} because its deadline passed."
        " Orders are due for Spring 1902 movement."
    )
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    expected = {tg: [head] for tg in by_power.values()}
    expected[by_power["FRANCE"]] = [head + "\nYour 2 builds were waived: no orders came in."]
    assert _dms(probe) == expected
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (
            GROUP,
            f"🔔 Turn Processed - Game {game_id}\n"
            "The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private.\n"
            "FRANCE: 2 builds were waived: no orders came in.",
        )
    ]


def test_waived_line_is_singular_for_one_build() -> None:
    assert api_shared.waived_line(1) == "1 build was waived: no orders came in."
