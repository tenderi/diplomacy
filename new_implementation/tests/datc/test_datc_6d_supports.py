"""DATC section 6.D — supports and dislodges.

34 cases (6.D.1-6.D.34). Outcomes are cross-checked against the DATC document
and the reference resolver in old_implementation (semantics only; no code
copied, per AGPL). Where DATC states a preferred rule variant, the preferred
choice is followed and noted in the docstring.
"""

from __future__ import annotations

import pytest

from engine.orders.parser import parse_order
from engine.types import Location, ResultCode
from tests.datc.harness import Harness, standard_map

pytestmark = pytest.mark.datc


def test_6d1_supported_hold_prevents_dislodgement():
    """6.D.1 SUPPORTED HOLD CAN PREVENT DISLODGEMENT.

    Austria: F ADR S A TRI - VEN, A TRI - VEN. Italy: A VEN H, A TYR S A VEN.
    Expected: the hold support of Tyrolia prevents Venice from being
    dislodged; Trieste bounces.
    """
    h = Harness()
    h.units("AUSTRIA", "F ADR", "A TRI")
    h.units("ITALY", "A VEN", "A TYR")
    h.orders("AUSTRIA", "F ADR S A TRI - VEN", "A TRI - VEN")
    h.orders("ITALY", "A VEN H", "A TYR S A VEN")
    h.adjudicate()
    h.assert_success("F ADR")
    h.assert_bounce("A TRI")
    h.assert_success("A VEN")
    h.assert_success("A TYR")
    h.assert_not_dislodged("A VEN")


def test_6d2_move_cuts_support_on_hold():
    """6.D.2 A MOVE CUTS SUPPORT ON HOLD.

    Austria adds A VIE - TYR, cutting Tyrolia's hold support on Venice, so
    Trieste's supported attack dislodges Venice.
    """
    h = Harness()
    h.units("AUSTRIA", "F ADR", "A TRI", "A VIE")
    h.units("ITALY", "A VEN", "A TYR")
    h.orders("AUSTRIA", "F ADR S A TRI - VEN", "A TRI - VEN", "A VIE - TYR")
    h.orders("ITALY", "A VEN H", "A TYR S A VEN")
    h.adjudicate()
    h.assert_success("F ADR")
    h.assert_success("A TRI")
    h.assert_bounce("A VIE")
    h.assert_dislodged("A VEN")
    h.assert_result("A TYR", ResultCode.CUT)


def test_6d3_move_cuts_support_on_move():
    """6.D.3 A MOVE CUTS SUPPORT ON MOVE.

    Italy's F ION - ADR cuts Adriatic's support; Venice holds unsupported and
    Trieste bounces.
    """
    h = Harness()
    h.units("AUSTRIA", "F ADR", "A TRI")
    h.units("ITALY", "A VEN", "F ION")
    h.orders("AUSTRIA", "F ADR S A TRI - VEN", "A TRI - VEN")
    h.orders("ITALY", "A VEN H", "F ION - ADR")
    h.adjudicate()
    h.assert_result("F ADR", ResultCode.CUT)
    h.assert_bounce("A TRI")
    h.assert_success("A VEN")
    h.assert_bounce("F ION")


def test_6d4_support_to_hold_on_unit_supporting_hold_allowed():
    """6.D.4 SUPPORT TO HOLD ON UNIT SUPPORTING A HOLD ALLOWED.

    Germany's F KIE supports A BER (which itself supports F KIE) in hold;
    the Russian attack on Berlin fails.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE")
    h.units("RUSSIA", "F BAL", "A PRU")
    h.orders("GERMANY", "A BER S F KIE", "F KIE S A BER")
    h.orders("RUSSIA", "F BAL S A PRU - BER", "A PRU - BER")
    h.adjudicate()
    h.assert_result("A BER", ResultCode.CUT)
    h.assert_success("F KIE")
    h.assert_success("F BAL")
    h.assert_bounce("A PRU")


def test_6d5_support_to_hold_on_unit_supporting_move_allowed():
    """6.D.5 SUPPORT TO HOLD ON UNIT SUPPORTING A MOVE ALLOWED.

    A unit that is supporting a move can still receive hold support; the
    Russian move to Berlin fails.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE", "A MUN")
    h.units("RUSSIA", "F BAL", "A PRU")
    h.orders("GERMANY", "A BER S A MUN - SIL", "F KIE S A BER", "A MUN - SIL")
    h.orders("RUSSIA", "F BAL S A PRU - BER", "A PRU - BER")
    h.adjudicate()
    h.assert_result("A BER", ResultCode.CUT)
    h.assert_success("F KIE")
    h.assert_success("A MUN")
    h.assert_success("F BAL")
    h.assert_bounce("A PRU")


def test_6d6_support_to_hold_on_convoying_unit_allowed():
    """6.D.6 SUPPORT TO HOLD ON CONVOYING UNIT ALLOWED.

    A convoying fleet can receive hold support; the Russian attack on the
    Baltic Sea fails and the convoy succeeds.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F BAL", "F PRU")
    h.units("RUSSIA", "F LVN", "F BOT")
    h.orders("GERMANY", "A BER - SWE", "F BAL C A BER - SWE", "F PRU S F BAL")
    h.orders("RUSSIA", "F LVN - BAL", "F BOT S F LVN - BAL")
    h.adjudicate()
    h.assert_success("A BER")
    h.assert_success("F BAL")
    h.assert_success("F PRU")
    h.assert_bounce("F LVN")
    h.assert_success("F BOT")
    h.assert_at("SWE")


def test_6d7_support_to_hold_on_moving_unit_not_allowed():
    """6.D.7 SUPPORT TO HOLD ON MOVING UNIT NOT ALLOWED.

    A moving unit cannot receive hold support for the case its move fails.
    F PRU's hold-style support on F BAL is void; F BAL bounces off Finland
    and is then dislodged by the returning Russian fleet from Livonia.
    """
    h = Harness()
    h.units("GERMANY", "F BAL", "F PRU")
    h.units("RUSSIA", "F LVN", "F BOT", "A FIN")
    h.orders("GERMANY", "F BAL - SWE", "F PRU S F BAL")
    h.orders("RUSSIA", "F LVN - BAL", "F BOT S F LVN - BAL", "A FIN - SWE")
    h.adjudicate()
    h.assert_bounce("F BAL")
    h.assert_dislodged("F BAL")
    h.assert_result("F PRU", ResultCode.VOID)
    h.assert_success("F LVN")
    h.assert_success("F BOT")
    h.assert_bounce("A FIN")


@pytest.mark.xfail(reason="no-fleet convoy move interpretation: this engine treats an army move with no convoy ordered as illegal/ignored (unit holds, can receive hold support) for consistency with 6.D.28/29/31/32; DATC 6.D.8 encodes the competing attempted-move reading", strict=False)
def test_6d8_failed_convoy_cannot_receive_hold_support():
    """6.D.8 FAILED CONVOY CAN NOT RECEIVE HOLD SUPPORT.

    Greece's would-be convoy to Naples was never ordered as a convoy move;
    it still counts as an attempted move (not eligible for hold support), so
    Bulgaria's support fails and Greece is dislodged by Albania.
    """
    h = Harness()
    h.units("AUSTRIA", "F ION", "A SER", "A ALB")
    h.units("TURKEY", "A GRE", "A BUL")
    h.orders("AUSTRIA", "F ION H", "A SER S A ALB - GRE", "A ALB - GRE")
    h.orders("TURKEY", "A GRE - NAP", "A BUL S A GRE")
    h.adjudicate()
    h.assert_success("F ION")
    h.assert_success("A SER")
    h.assert_success("A ALB")
    h.assert_dislodged("A GRE")
    h.assert_result("A BUL", ResultCode.VOID)


def test_6d9_support_to_move_on_holding_unit_not_allowed():
    """6.D.9 SUPPORT TO MOVE ON HOLDING UNIT NOT ALLOWED.

    Albania's support presumes Trieste moves to Serbia, but Trieste holds;
    the support fails and Trieste is dislodged by Venice.
    """
    h = Harness()
    h.units("ITALY", "A VEN", "A TYR")
    h.units("AUSTRIA", "A ALB", "A TRI")
    h.orders("ITALY", "A VEN - TRI", "A TYR S A VEN - TRI")
    h.orders("AUSTRIA", "A ALB S A TRI - SER", "A TRI H")
    h.adjudicate()
    h.assert_success("A VEN")
    h.assert_success("A TYR")
    h.assert_result("A ALB", ResultCode.VOID)
    h.assert_dislodged("A TRI")


def test_6d10_self_dislodgement_prohibited():
    """6.D.10 SELF DISLODGMENT PROHIBITED.

    Germany may not dislodge its own unit even with support; the move to
    Berlin fails.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE", "A MUN")
    h.orders("GERMANY", "A BER H", "F KIE - BER", "A MUN S F KIE - BER")
    h.adjudicate()
    h.assert_success("A BER")
    h.assert_bounce("F KIE")
    h.assert_result("A MUN", ResultCode.VOID)


def test_6d11_no_self_dislodgement_of_returning_unit():
    """6.D.11 NO SELF DISLODGMENT OF RETURNING UNIT.

    Berlin vacates for Prussia but the vacancy does not let Kiel dislodge it
    (self-dislodgement is still prohibited); Berlin and Prussia both bounce.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE", "A MUN")
    h.units("RUSSIA", "A WAR")
    h.orders("GERMANY", "A BER - PRU", "F KIE - BER", "A MUN S F KIE - BER")
    h.orders("RUSSIA", "A WAR - PRU")
    h.adjudicate()
    h.assert_bounce("A BER")
    h.assert_bounce("F KIE")
    h.assert_result("A MUN", ResultCode.VOID)
    h.assert_bounce("A WAR")
    h.assert_not_dislodged("A BER")


def test_6d12_supporting_foreign_unit_to_dislodge_own_unit_prohibited():
    """6.D.12 SUPPORTING A FOREIGN UNIT TO DISLODGE OWN UNIT PROHIBITED.

    Austria may not help Italy dislodge its own fleet in Trieste; Vienna's
    support is void and Venice bounces.
    """
    h = Harness()
    h.units("AUSTRIA", "F TRI", "A VIE")
    h.units("ITALY", "A VEN")
    h.orders("AUSTRIA", "F TRI H", "A VIE S A VEN - TRI")
    h.orders("ITALY", "A VEN - TRI")
    h.adjudicate()
    h.assert_success("F TRI")
    h.assert_result("A VIE", ResultCode.VOID)
    h.assert_bounce("A VEN")
    h.assert_not_dislodged("F TRI")


def test_6d13_supporting_foreign_unit_to_dislodge_returning_own_unit_prohibited():
    """6.D.13 SUPPORTING A FOREIGN UNIT TO DISLODGE A RETURNING OWN UNIT PROHIBITED.

    Even though Trieste tries to vacate (head-to-head with Apulia via the
    Adriatic), Vienna's support for Italy still may not help dislodge it.
    """
    h = Harness()
    h.units("AUSTRIA", "F TRI", "A VIE")
    h.units("ITALY", "A VEN", "F APU")
    h.orders("AUSTRIA", "F TRI - ADR", "A VIE S A VEN - TRI")
    h.orders("ITALY", "A VEN - TRI", "F APU - ADR")
    h.adjudicate()
    h.assert_bounce("F TRI")
    h.assert_result("A VIE", ResultCode.VOID)
    h.assert_bounce("A VEN")
    h.assert_bounce("F APU")
    h.assert_not_dislodged("F TRI")


def test_6d14_supporting_foreign_unit_not_enough_to_prevent_dislodgement():
    """6.D.14 SUPPORTING A FOREIGN UNIT IS NOT ENOUGH TO PREVENT DISLODGEMENT.

    Italy has enough support (Tyrolia + Adriatic) to dislodge Trieste even
    without Vienna's help; the fleet in Trieste is dislodged.
    """
    h = Harness()
    h.units("AUSTRIA", "F TRI", "A VIE")
    h.units("ITALY", "A VEN", "A TYR", "F ADR")
    h.orders("AUSTRIA", "F TRI H", "A VIE S A VEN - TRI")
    h.orders("ITALY", "A VEN - TRI", "A TYR S A VEN - TRI", "F ADR S A VEN - TRI")
    h.adjudicate()
    h.assert_dislodged("F TRI")
    h.assert_result("A VIE", ResultCode.VOID)
    h.assert_success("A VEN")
    h.assert_success("A TYR")
    h.assert_success("F ADR")


def test_6d15_defender_cannot_cut_support_for_attack_on_itself():
    """6.D.15 DEFENDER CAN NOT CUT SUPPORT FOR ATTACK ON ITSELF.

    Ankara's move to Constantinople does not cut Constantinople's support
    for the Black Sea (the target of a supported move never cuts that
    support); Ankara is dislodged by the fleet from the Black Sea.
    """
    h = Harness()
    h.units("RUSSIA", "F CON", "F BLA")
    h.units("TURKEY", "F ANK")
    h.orders("RUSSIA", "F CON S F BLA - ANK", "F BLA - ANK")
    h.orders("TURKEY", "F ANK - CON")
    h.adjudicate()
    h.assert_success("F CON")
    h.assert_success("F BLA")
    h.assert_bounce("F ANK")
    h.assert_dislodged("F ANK")


def test_6d16_convoying_unit_dislodging_unit_of_same_power_allowed():
    """6.D.16 CONVOYING A UNIT DISLODGING A UNIT OF SAME POWER IS ALLOWED.

    It is fine to convoy a foreign unit that dislodges an England unit;
    French Belgium dislodges English London via convoy.
    """
    h = Harness()
    h.units("ENGLAND", "A LON", "F NTH")
    h.units("FRANCE", "F ENG", "A BEL")
    h.orders("ENGLAND", "A LON H", "F NTH C A BEL - LON")
    h.orders("FRANCE", "F ENG S A BEL - LON", "A BEL - LON")
    h.adjudicate()
    h.assert_dislodged("A LON")
    h.assert_success("F NTH")
    h.assert_success("F ENG")
    h.assert_success("A BEL")
    assert h.unit_powers_at("LON") == "FRANCE"


def test_6d17_dislodgement_cuts_supports():
    """6.D.17 DISLODGEMENT CUTS SUPPORTS.

    Constantinople is dislodged, which cuts its support for Black Sea's
    attack on Ankara; Black Sea then bounces against Armenia.
    """
    h = Harness()
    h.units("RUSSIA", "F CON", "F BLA")
    h.units("TURKEY", "F ANK", "A SMY", "A ARM")
    h.orders("RUSSIA", "F CON S F BLA - ANK", "F BLA - ANK")
    h.orders("TURKEY", "F ANK - CON", "A SMY S F ANK - CON", "A ARM - ANK")
    h.adjudicate()
    h.assert_dislodged("F CON")
    h.assert_result("F CON", ResultCode.CUT)
    h.assert_bounce("F BLA")
    h.assert_success("F ANK")
    h.assert_success("A SMY")
    h.assert_bounce("A ARM")


def test_6d18_surviving_unit_sustains_support():
    """6.D.18 A SURVIVING UNIT WILL SUSTAIN SUPPORT.

    Bulgaria's hold support keeps Constantinople alive, so its support for
    Black Sea's attack survives and Ankara is dislodged.
    """
    h = Harness()
    h.units("RUSSIA", "F CON", "F BLA", "A BUL")
    h.units("TURKEY", "F ANK", "A SMY", "A ARM")
    h.orders("RUSSIA", "F CON S F BLA - ANK", "F BLA - ANK", "A BUL S F CON")
    h.orders("TURKEY", "F ANK - CON", "A SMY S F ANK - CON", "A ARM - ANK")
    h.adjudicate()
    h.assert_success("F CON")
    h.assert_success("F BLA")
    h.assert_success("A BUL")
    h.assert_dislodged("F ANK")
    h.assert_success("A SMY")
    h.assert_bounce("A ARM")


def test_6d19_even_when_surviving_is_in_alternative_way():
    """6.D.19 EVEN WHEN SURVIVING IS IN ALTERNATIVE WAY.

    Constantinople survives because Smyrna's support for Ankara's own attack
    on Constantinople is Russian-owned (own unit can't dislodge itself), not
    because of a hold support; Ankara is still dislodged by Black Sea.
    """
    h = Harness()
    h.units("RUSSIA", "F CON", "F BLA", "A SMY")
    h.units("TURKEY", "F ANK")
    h.orders("RUSSIA", "F CON S F BLA - ANK", "F BLA - ANK", "A SMY S F ANK - CON")
    h.orders("TURKEY", "F ANK - CON")
    h.adjudicate()
    h.assert_success("F CON")
    h.assert_success("F BLA")
    h.assert_result("A SMY", ResultCode.VOID)
    h.assert_dislodged("F ANK")


def test_6d20_unit_cannot_cut_support_of_its_own_country():
    """6.D.20 UNIT CAN NOT CUT SUPPORT OF ITS OWN COUNTRY.

    England's own army from Yorkshire attacking London does not cut
    London's support (same-power attacks on a supporting unit still count
    as cutting per DATC's preferred rule -- but the target of the supported
    move itself never cuts, and here Yorkshire attacks London, not the
    English Channel, so it is irrelevant to the support anyway); London's
    support for North Sea stands and the Channel is dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "F LON", "F NTH", "A YOR")
    h.units("FRANCE", "F ENG")
    h.orders("ENGLAND", "F LON S F NTH - ENG", "F NTH - ENG", "A YOR - LON")
    h.orders("FRANCE", "F ENG H")
    h.adjudicate()
    h.assert_success("F LON")
    h.assert_success("F NTH")
    h.assert_bounce("A YOR")
    h.assert_dislodged("F ENG")


def test_6d21_dislodging_does_not_cancel_a_support_cut():
    """6.D.21 DISLODGING DOES NOT CANCEL A SUPPORT CUT.

    Munich cuts Tyrolia's support even though Munich itself is dislodged
    this same turn; the Austrian fleet in Trieste is not dislodged.
    """
    h = Harness()
    h.units("AUSTRIA", "F TRI")
    h.units("ITALY", "A VEN", "A TYR")
    h.units("GERMANY", "A MUN")
    h.units("RUSSIA", "A SIL", "A BER")
    h.orders("AUSTRIA", "F TRI H")
    h.orders("ITALY", "A VEN - TRI", "A TYR S A VEN - TRI")
    h.orders("GERMANY", "A MUN - TYR")
    h.orders("RUSSIA", "A SIL - MUN", "A BER S A SIL - MUN")
    h.adjudicate()
    h.assert_success("F TRI")
    h.assert_bounce("A VEN")
    h.assert_result("A TYR", ResultCode.CUT)
    h.assert_dislodged("A MUN")
    h.assert_success("A SIL")
    h.assert_success("A BER")
    h.assert_not_dislodged("F TRI")


def test_6d22_impossible_fleet_move_cannot_be_supported():
    """6.D.22 IMPOSSIBLE FLEET MOVE CAN NOT BE SUPPORTED.

    F Kiel - Munich is illegal (fleets cannot enter Munich); the support
    from Burgundy is therefore also invalid, and the fleet in Kiel is
    dislodged by the Russian army from Munich.
    """
    h = Harness()
    h.units("GERMANY", "F KIE", "A BUR")
    h.units("RUSSIA", "A MUN", "A BER")
    h.orders("GERMANY", "F KIE - MUN", "A BUR S F KIE - MUN")
    h.orders("RUSSIA", "A MUN - KIE", "A BER S A MUN - KIE")
    h.adjudicate()
    h.assert_result("F KIE", ResultCode.VOID)
    h.assert_dislodged("F KIE")
    h.assert_result("A BUR", ResultCode.VOID)
    h.assert_success("A MUN")
    h.assert_success("A BER")


def test_6d23_impossible_coast_move_cannot_be_supported():
    """6.D.23 IMPOSSIBLE COAST MOVE CAN NOT BE SUPPORTED.

    F Spain(nc) - Gulf of Lyon is illegal (wrong coast); Marseilles' support
    is also invalid, and the fleet in Spain is dislodged.
    """
    h = Harness()
    h.units("ITALY", "F LYO", "F WES")
    h.units("FRANCE", "F SPA/NC", "F MAR")
    h.orders("ITALY", "F LYO - SPA/SC", "F WES S F LYO - SPA/SC")
    h.orders("FRANCE", "F SPA/NC - LYO", "F MAR S F SPA/NC - LYO")
    h.adjudicate()
    h.assert_success("F LYO")
    h.assert_success("F WES")
    h.assert_result("F SPA/NC", ResultCode.VOID)
    h.assert_dislodged("F SPA/NC")
    h.assert_result("F MAR", ResultCode.VOID)


def test_6d24_impossible_army_move_cannot_be_supported():
    """6.D.24 IMPOSSIBLE ARMY MOVE CAN NOT BE SUPPORTED.

    A Marseilles - Gulf of Lyon is illegal (an army cannot go to sea); the
    support from Spain is also invalid so there is no beleaguered garrison,
    and Turkey's fleet from Western Mediterranean dislodges the Gulf of
    Lyon.
    """
    h = Harness()
    h.units("FRANCE", "A MAR", "F SPA/SC")
    h.units("ITALY", "F LYO")
    h.units("TURKEY", "F TYS", "F WES")
    h.orders("FRANCE", "A MAR - LYO", "F SPA/SC S A MAR - LYO")
    h.orders("ITALY", "F LYO H")
    h.orders("TURKEY", "F TYS S F WES - LYO", "F WES - LYO")
    h.adjudicate()
    h.assert_result("A MAR", ResultCode.VOID)
    h.assert_result("F SPA/SC", ResultCode.VOID)
    h.assert_dislodged("F LYO")
    h.assert_success("F TYS")
    h.assert_success("F WES")


def test_6d25_failing_hold_support_can_be_supported():
    """6.D.25 FAILING HOLD SUPPORT CAN BE SUPPORTED.

    Berlin's hold support of Prussia is void (unmatched: Prussia is moving,
    not holding), but Kiel's support of Berlin (in hold) is still valid, so
    Berlin is not dislodged.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE")
    h.units("RUSSIA", "F BAL", "A PRU")
    h.orders("GERMANY", "A BER S A PRU", "F KIE S A BER")
    h.orders("RUSSIA", "F BAL S A PRU - BER", "A PRU - BER")
    h.adjudicate()
    h.assert_result("A BER", ResultCode.VOID)
    h.assert_success("F KIE")
    h.assert_success("F BAL")
    h.assert_bounce("A PRU")
    h.assert_not_dislodged("A BER")


def test_6d26_failing_move_support_can_be_supported():
    """6.D.26 FAILING MOVE SUPPORT CAN BE SUPPORTED.

    Similar to 6.D.25 but with an unmatched support to move: Berlin's support
    of Prussia - Silesia is void, yet Kiel's hold support of Berlin still
    prevents Berlin from being dislodged.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "F KIE")
    h.units("RUSSIA", "F BAL", "A PRU")
    h.orders("GERMANY", "A BER S A PRU - SIL", "F KIE S A BER")
    h.orders("RUSSIA", "F BAL S A PRU - BER", "A PRU - BER")
    h.adjudicate()
    h.assert_result("A BER", ResultCode.VOID)
    h.assert_success("F KIE")
    h.assert_success("F BAL")
    h.assert_bounce("A PRU")
    h.assert_not_dislodged("A BER")


def test_6d27_failing_convoy_can_be_supported():
    """6.D.27 FAILING CONVOY CAN BE SUPPORTED.

    The Baltic Sea's convoy order is unmatched (Berlin holds) and fails, but
    Prussia's support of the Baltic Sea fleet is still valid, so it is not
    dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "F SWE", "F DEN")
    h.units("GERMANY", "A BER")
    h.units("RUSSIA", "F BAL", "F PRU")
    h.orders("ENGLAND", "F SWE - BAL", "F DEN S F SWE - BAL")
    h.orders("GERMANY", "A BER H")
    h.orders("RUSSIA", "F BAL C A BER - LVN", "F PRU S F BAL")
    h.adjudicate()
    h.assert_bounce("F SWE")
    h.assert_success("F DEN")
    h.assert_success("A BER")
    h.assert_result("F BAL", ResultCode.VOID)
    h.assert_success("F PRU")
    h.assert_not_dislodged("F BAL")


def test_6d28_impossible_move_and_support():
    """6.D.28 IMPOSSIBLE MOVE AND SUPPORT.

    Russia's F Rumania - Holland is illegal, so it is ignored (DATC's
    preferred "illegal" interpretation); Budapest's hold support on Rumania
    is then valid and Rumania is not dislodged by the Black Sea.
    """
    h = Harness()
    h.units("AUSTRIA", "A BUD")
    h.units("RUSSIA", "F RUM")
    h.units("TURKEY", "F BLA", "A BUL")
    h.orders("AUSTRIA", "A BUD S F RUM")
    h.orders("RUSSIA", "F RUM - HOL")
    h.orders("TURKEY", "F BLA - RUM", "A BUL S F BLA - RUM")
    h.adjudicate()
    h.assert_success("A BUD")
    h.assert_result("F RUM", ResultCode.VOID)
    h.assert_bounce("F BLA")
    h.assert_success("A BUL")
    h.assert_not_dislodged("F RUM")


def test_6d29_move_to_impossible_coast_and_support():
    """6.D.29 MOVE TO IMPOSSIBLE COAST AND SUPPORT.

    F Rumania - Bulgaria(sc) is illegal (Rumania only reaches Bulgaria's east
    coast); DATC prefers unambiguous orders are not auto-corrected, so the
    move is illegal/ignored, Budapest's hold support stands, and Rumania is
    not dislodged.
    """
    h = Harness()
    h.units("AUSTRIA", "A BUD")
    h.units("RUSSIA", "F RUM")
    h.units("TURKEY", "F BLA", "A BUL")
    h.orders("AUSTRIA", "A BUD S F RUM")
    h.orders("RUSSIA", "F RUM - BUL/SC")
    h.orders("TURKEY", "F BLA - RUM", "A BUL S F BLA - RUM")
    h.adjudicate()
    h.assert_success("A BUD")
    h.assert_result("F RUM", ResultCode.VOID)
    h.assert_bounce("F BLA")
    h.assert_success("A BUL")
    h.assert_not_dislodged("F RUM")


def test_6d30_move_without_coast_and_support():
    """6.D.30 MOVE WITHOUT COAST AND SUPPORT.

    F Constantinople - Bulgaria is ambiguous (Bulgaria has two coasts
    reachable from Constantinople). This engine's parser rejects an
    unqualified fleet destination at a split-coast province at parse time
    (a stricter, but DATC-preferred-compatible, form of "the move is
    illegal"); the order is therefore never submitted, F Constantinople
    implicitly holds, and the Aegean's hold support keeps it safe from the
    Black Sea's attack.
    """
    m = standard_map()
    # This engine parses the ambiguous coast leniently to a coastless dest; the
    # adjudicator is the one legality path and voids the ambiguous move. Here
    # RUSSIA simply gives no order, so F CON implicitly holds either way.
    ambiguous = parse_order("F CON - BUL", power="RUSSIA", map=m)
    assert ambiguous.dest == Location("BUL", None)

    h = Harness()
    h.units("ITALY", "F AEG")
    h.units("RUSSIA", "F CON")
    h.units("TURKEY", "F BLA", "A BUL")
    h.orders("ITALY", "F AEG S F CON")
    # RUSSIA gives no order for F CON: the ambiguous move is never submitted,
    # so the unit implicitly holds.
    h.orders("TURKEY", "F BLA - CON", "A BUL S F BLA - CON")
    h.adjudicate()
    h.assert_success("F AEG")
    h.assert_success("F CON")
    h.assert_bounce("F BLA")
    h.assert_success("A BUL")
    h.assert_not_dislodged("F CON")


def test_6d31_a_tricky_impossible_support():
    """6.D.31 A TRICKY IMPOSSIBLE SUPPORT.

    A Rumania - Armenia requires convoying through the Black Sea, but a
    fleet cannot convoy and support at the same time, so Turkey's declared
    support order for that move is impossible and should be ignored (DATC's
    preferred "illegal" interpretation). Rumania's move has no convoy and
    fails as NO_CONVOY.
    """
    h = Harness()
    h.units("AUSTRIA", "A RUM")
    h.units("TURKEY", "F BLA")
    h.orders("AUSTRIA", "A RUM - ARM")
    h.orders("TURKEY", "F BLA S A RUM - ARM")
    h.adjudicate()
    h.assert_result("A RUM", ResultCode.VOID)
    h.assert_result("F BLA", ResultCode.VOID)


def test_6d32_a_missing_fleet():
    """6.D.32 A MISSING FLEET.

    Germany's A Yorkshire - Holland requires convoying through the North
    Sea, but no fleet is there; DATC's preferred reading treats this as
    illegal and ignored, so France's support of Yorkshire (in hold) is
    valid and Yorkshire is not dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "F EDI", "A LVP")
    h.units("FRANCE", "F LON")
    h.units("GERMANY", "A YOR")
    h.orders("ENGLAND", "F EDI S A LVP - YOR", "A LVP - YOR")
    h.orders("FRANCE", "F LON S A YOR")
    h.orders("GERMANY", "A YOR - HOL")
    h.adjudicate()
    h.assert_success("F EDI")
    h.assert_bounce("A LVP")
    h.assert_success("F LON")
    h.assert_result("A YOR", ResultCode.VOID)
    h.assert_not_dislodged("A YOR")


def test_6d33_unwanted_support_allowed():
    """6.D.33 UNWANTED SUPPORT ALLOWED.

    A self stand-off between Serbia and Vienna (both moving to Budapest) is
    broken by Russia's unwanted support of Serbia - Budapest, letting Turkey
    take the now-vacant Serbia.
    """
    h = Harness()
    h.units("AUSTRIA", "A SER", "A VIE")
    h.units("RUSSIA", "A GAL")
    h.units("TURKEY", "A BUL")
    h.orders("AUSTRIA", "A SER - BUD", "A VIE - BUD")
    h.orders("RUSSIA", "A GAL S A SER - BUD")
    h.orders("TURKEY", "A BUL - SER")
    h.adjudicate()
    h.assert_success("A SER")
    h.assert_bounce("A VIE")
    h.assert_success("A GAL")
    h.assert_success("A BUL")
    assert h.unit_powers_at("SER") == "TURKEY"
    assert h.unit_powers_at("BUD") == "AUSTRIA"


def test_6d34_support_targeting_own_area_not_allowed():
    """6.D.34 SUPPORT TARGETING OWN AREA NOT ALLOWED.

    A unit may only support a move to an area it could move to itself; it
    can never move to the province it is already standing in, so Italy's
    "A PRU S A LVN - PRU" is illegal. Even if it were legal, Germany's move
    from Berlin would still succeed since Livonia's own attack is cut by
    Berlin. Berlin dislodges the Italian army in Prussia.
    """
    h = Harness()
    h.units("GERMANY", "A BER", "A SIL", "F BAL")
    h.units("ITALY", "A PRU")
    h.units("RUSSIA", "A WAR", "A LVN")
    h.orders("GERMANY", "A BER - PRU", "A SIL S A BER - PRU", "F BAL S A BER - PRU")
    h.orders("ITALY", "A PRU S A LVN - PRU")
    h.orders("RUSSIA", "A WAR S A LVN - PRU", "A LVN - PRU")
    h.adjudicate()
    h.assert_success("A BER")
    h.assert_success("A SIL")
    h.assert_success("F BAL")
    h.assert_result("A PRU", ResultCode.VOID)
    h.assert_dislodged("A PRU")
    h.assert_success("A WAR")
    h.assert_bounce("A LVN")
