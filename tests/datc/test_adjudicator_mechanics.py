"""Driver-authored mechanics tests exercising the resolver's hard paths:
circular movement, head-to-head, beleaguered garrison, convoy + disruption.

These pin the cycle-detection / backup-rule and convoy-path machinery before the
full DATC sections are authored.
"""

from __future__ import annotations

import pytest

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
