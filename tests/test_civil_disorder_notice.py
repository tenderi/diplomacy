"""BD5: a civil-disorder disband is announced to its power.

A power that orders too few disbands in an adjustment phase has the rest removed
for it by the civil-disorder distance rule. Nobody used to say which units went:
the turn-processed DM only named the next phase. Now the power's player reads which
of their units were removed, and the game's group reads it too.
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


def _winter_with_removals_owed(game_id: str) -> None:
    """FRANCE owes two removals and GERMANY two; ITALY is balanced."""
    units = {
        Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
        Unit(UnitKind.ARMY, "FRANCE", Location("MUN")),
        Unit(UnitKind.FLEET, "FRANCE", Location("KIE")),
        Unit(UnitKind.ARMY, "GERMANY", Location("BER")),
        Unit(UnitKind.ARMY, "GERMANY", Location("SIL")),
        Unit(UnitKind.ARMY, "GERMANY", Location("PRU")),
        Unit(UnitKind.ARMY, "ITALY", Location("ROM")),
    }
    state = GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset(units),
        ownership={"PAR": "FRANCE", "BER": "GERMANY", "ROM": "ITALY"},
    )
    api_shared.game_service.restore_snapshot(game_id, state_to_dict(state), phase_code="W1901A")


def _process(game_id: str, exclude: str | None = None) -> OutboxProbe:
    row_id = int(api_shared.db_service.get_game_by_game_id(game_id).id)
    api_shared.db_service.link_game_to_channel(game_id, GROUP, any_displacer=True)
    # GERMANY sends one of its two disbands; FRANCE sends none.
    api_shared.game_service.submit_orders(game_id, "GERMANY", ["D A PRU"])
    with OutboxProbe() as probe:
        api_shared.game_service.process_turn(game_id)
        api_shared.finish_processed_turn(
            game_id, row_id, prev_phase_code="W1901A", trigger="deadline", exclude_telegram_id=exclude
        )
    return probe


def test_the_disordered_powers_are_told_which_units_went() -> None:
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    _winter_with_removals_owed(game_id)

    probe = _process(game_id)

    head = (
        f"The turn has been processed for game {game_id} because its deadline passed."
        " Orders are due for Spring 1902 movement."
    )
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}
    expected = {tg: [head] for tg in by_power.values()}
    # F KIE is farther from a French home centre than A MUN; A PAR is home.
    expected[by_power["FRANCE"]] = [
        head + "\nYou ordered no disbands, so F KIE and A MUN were disbanded (civil disorder)."
    ]
    expected[by_power["GERMANY"]] = [
        head + "\nYou ordered 1 of your 2 disbands, so A SIL was disbanded too (civil disorder)."
    ]
    assert _dms(probe) == expected
    assert [(r["telegram_id"], r["message"]) for r in probe.rows() if r["kind"] == "channel_text"] == [
        (
            GROUP,
            f"🔔 Turn Processed - Game {game_id}\n"
            "The turn has been processed. Spring 1902 movement: new orders are due -- send them to me in private.\n"
            "FRANCE ordered no disbands, so F KIE and A MUN were disbanded (civil disorder).\n"
            "GERMANY ordered 1 of its 2 disbands, so A SIL was disbanded too (civil disorder).",
        )
    ]


def test_the_caller_who_processed_the_turn_still_hears_of_their_removals() -> None:
    # The caller is left out of a movement phase's DM (their HTTP response has the
    # resolution), but that response does not point out what civil disorder removed.
    client = TestClient(app)
    game_id, users = _seeded_game(client)
    _winter_with_removals_owed(game_id)
    by_power = {power: tg for power, (_h, tg) in zip(POWERS, users)}

    probe = _process(game_id, exclude=by_power["FRANCE"])

    dms = _dms(probe)
    assert dms[by_power["FRANCE"]] == [
        f"The turn has been processed for game {game_id} because its deadline passed."
        " Orders are due for Spring 1902 movement."
        "\nYou ordered no disbands, so F KIE and A MUN were disbanded (civil disorder)."
    ]
    assert by_power["ITALY"] in dms
