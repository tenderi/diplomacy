"""Driver-authored mechanics tests exercising the resolver's hard paths:
circular movement, head-to-head, beleaguered garrison, convoy + disruption.

These pin the cycle-detection / backup-rule and convoy-path machinery before the
full DATC sections are authored.
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_three_army_circular_movement_succeeds():
    # A cycle of three land moves with no external attacker all succeed.
    h = Harness()
    h.units("RUSSIA", "A MOS", "A UKR", "A WAR")
    h.orders("RUSSIA", "A MOS - UKR", "A UKR - WAR", "A WAR - MOS")
    h.adjudicate()
    h.assert_success("A MOS")
    h.assert_success("A UKR")
    h.assert_success("A WAR")
    assert h.unit_powers_at("UKR") == "RUSSIA"
    assert h.unit_powers_at("WAR") == "RUSSIA"
    assert h.unit_powers_at("MOS") == "RUSSIA"


def test_head_to_head_both_bounce():
    # Two equal-strength units swapping provinces both bounce (no swap).
    h = Harness()
    h.units("FRANCE", "A PAR")
    h.units("GERMANY", "A BUR")
    h.orders("FRANCE", "A PAR - BUR")
    h.orders("GERMANY", "A BUR - PAR")
    h.adjudicate()
    h.assert_bounce("A PAR")
    h.assert_bounce("A BUR")
    h.assert_not_dislodged("A PAR")
    h.assert_not_dislodged("A BUR")


def test_head_to_head_supported_side_wins():
    # Supported side of a head-to-head dislodges the other.
    h = Harness()
    h.units("FRANCE", "A PAR", "A GAS")
    h.units("GERMANY", "A BUR")
    h.orders("FRANCE", "A PAR - BUR", "A GAS S A PAR - BUR")
    h.orders("GERMANY", "A BUR - PAR")
    h.adjudicate()
    h.assert_success("A PAR")
    h.assert_dislodged("A BUR")


def test_beleaguered_garrison_holds():
    # Two equally-supported attackers on Holland stand each other off; the
    # defender survives (classic beleaguered garrison).
    h = Harness()
    h.units("ENGLAND", "F NTH", "F HEL")  # attack + support from the sea
    h.units("GERMANY", "A RUH", "A KIE")  # attack + support from the land
    h.units("FRANCE", "A HOL")            # the garrison
    h.orders("ENGLAND", "F NTH - HOL", "F HEL S F NTH - HOL")
    h.orders("GERMANY", "A RUH - HOL", "A KIE S A RUH - HOL")
    h.orders("FRANCE", "A HOL H")
    h.adjudicate()
    h.assert_bounce("F NTH")
    h.assert_bounce("A RUH")
    h.assert_not_dislodged("A HOL")


def test_simple_convoy_succeeds():
    h = Harness()
    h.units("ENGLAND", "A LON", "F NTH")
    h.orders("ENGLAND", "A LON - NWY", "F NTH C A LON - NWY")
    h.adjudicate()
    h.assert_success("A LON")
    assert h.unit_powers_at("NWY") == "ENGLAND"


def test_convoy_disrupted_by_dislodging_the_fleet():
    # The convoying fleet is dislodged, so the army's convoy fails (NO_CONVOY).
    h = Harness()
    h.units("ENGLAND", "A LON", "F NTH")
    h.units("GERMANY", "F SKA", "F DEN")
    h.orders("ENGLAND", "A LON - NWY", "F NTH C A LON - NWY")
    h.orders("GERMANY", "F SKA - NTH", "F DEN S F SKA - NTH")
    h.adjudicate()
    h.assert_dislodged("F NTH")
    from engine.types import ResultCode
    h.assert_result("A LON", ResultCode.NO_CONVOY)
    h.assert_empty("NWY")


def _fleet_dislodged_from_bothnia() -> Harness:
    h = Harness()
    h.units("RUSSIA", "F BOT")
    h.units("GERMANY", "F BAL", "F SWE")
    h.orders("GERMANY", "F BAL - BOT", "F SWE S F BAL - BOT")
    h.adjudicate()
    h.assert_dislodged("F BOT")
    assert h.retreat_options_at("BOT") == {"FIN", "LVN", "STP"}
    return h


def test_a_fleet_retreats_onto_the_coast_it_can_reach():
    h = _fleet_dislodged_from_bothnia()
    h.retreats("RUSSIA", "F BOT R STP/SC")
    h.adjudicate_retreats()
    h.assert_retreat_ok("F BOT")
    assert h.retreat_state.unit_at("STP").location.coast == "SC"


def test_a_fleet_retreat_naming_the_unreachable_coast_disbands():
    h = _fleet_dislodged_from_bothnia()
    h.retreats("RUSSIA", "F BOT R STP/NC")
    h.adjudicate_retreats()
    h.assert_disbanded("F BOT")
    assert h.final_at("STP") is None


@pytest.mark.parametrize("reverse", [False, True])
def test_a_support_against_ones_own_moving_unit_still_defends_head_to_head(reverse):
    """Found by the determinism property: the result used to depend on submission order.

    French A SYR and Austrian A ARM swap head-to-head. Russia supports SYR -> ARM; France
    itself supports ARM -> SYR. By DATC strengths: SYR -> ARM attacks with 2 against ARM's
    defend strength of 2 (the French support counts for defence) and bounces; ARM -> SYR
    then attacks a French unit that stays, the French support does not count against it,
    and 1 vs 1 bounces too. Nobody is dislodged. The engine used to call the French
    support void whenever SYR stayed -- and whether SYR stays hinges on that support.
    """
    h = Harness()
    h.units("FRANCE", "A SYR", "A SMY")
    h.units("AUSTRIA", "A ARM")
    h.units("RUSSIA", "A SEV")
    orders = [("FRANCE", "A SYR - ARM"), ("FRANCE", "A SMY S A ARM - SYR"),
              ("AUSTRIA", "A ARM - SYR"), ("RUSSIA", "A SEV S A SYR - ARM")]
    for power, order in reversed(orders) if reverse else orders:
        h.orders(power, order)
    h.adjudicate()
    h.assert_bounce("A SYR")
    h.assert_bounce("A ARM")
    h.assert_not_dislodged("A SYR")
    h.assert_not_dislodged("A ARM")
    h.assert_result("A SMY", ResultCode.VOID)  # reported: it would help dislodge its own unit
