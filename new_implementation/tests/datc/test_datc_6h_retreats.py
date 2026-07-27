"""DATC section 6.H — retreating.

Outcomes cross-checked against the DATC document and the reference resolver in
old_implementation (semantics only; no code copied).
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6h_1_no_supports_during_retreat():
    """6.H.1. TEST CASE, NO SUPPORTS DURING RETREAT.

    Supports are not allowed in the retreat phase. Both dislodged fleets try to
    retreat to Albania (with Austria attempting an illegal support order); they
    bounce off each other and both disband.
    """
    h = Harness()
    h.units("AUSTRIA", "F TRI", "A SER")
    h.units("TURKEY", "F GRE")
    h.units("ITALY", "A VEN", "A TYR", "F ION", "F AEG")
    h.orders("AUSTRIA", "F TRI H", "A SER H")
    h.orders("TURKEY", "F GRE H")
    h.orders(
        "ITALY",
        "A VEN S A TYR - TRI",
        "A TYR - TRI",
        "F ION - GRE",
        "F AEG S F ION - GRE",
    )
    h.adjudicate()
    h.assert_dislodged("F TRI")
    h.assert_dislodged("F GRE")

    # Austria's "support" during the retreat phase is illegal and ignored.
    h.retreats("AUSTRIA", "F TRI R ALB", "A SER S F TRI - ALB")
    h.retreats("TURKEY", "F GRE R ALB")
    h.adjudicate_retreats()
    h.assert_disbanded("F TRI")
    h.assert_disbanded("F GRE")


def test_6h_2_no_supports_from_retreating_unit():
    """6.H.2. TEST CASE, NO SUPPORTS FROM RETREATING UNIT.

    Even a retreating (dislodged) unit can not give support. The fleet in
    Holland receives an order but it is a (now-illegal) support, so it
    disbands; the fleets in Norway and Edinburgh bounce at North Sea and also
    disband.
    """
    h = Harness()
    h.units("ENGLAND", "A LVP", "F YOR", "F NWY")
    h.units("GERMANY", "A KIE", "A RUH")
    h.units("RUSSIA", "F EDI", "A SWE", "A FIN", "F HOL")
    h.orders("ENGLAND", "A LVP - EDI", "F YOR S A LVP - EDI", "F NWY H")
    h.orders("GERMANY", "A KIE S A RUH - HOL", "A RUH - HOL")
    h.orders("RUSSIA", "F EDI H", "A SWE S A FIN - NWY", "A FIN - NWY", "F HOL H")
    h.adjudicate()
    h.assert_dislodged("F NWY")
    h.assert_dislodged("F EDI")
    h.assert_dislodged("F HOL")

    h.retreats("ENGLAND", "F NWY R NTH")
    h.retreats("RUSSIA", "F EDI R NTH", "F HOL S F EDI - NTH")
    h.adjudicate_retreats()
    h.assert_disbanded("F NWY")
    h.assert_disbanded("F EDI")
    h.assert_disbanded("F HOL")


def test_6h_3_no_convoy_during_retreat():
    """6.H.3. TEST CASE, NO CONVOY DURING RETREAT.

    Convoys during retreat are not allowed. Holland is not land-adjacent to
    Yorkshire, so the retreat (which relies on an illegal convoy order) fails
    and the army disbands.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A HOL")
    h.units("GERMANY", "F KIE", "A RUH")
    h.orders("ENGLAND", "F NTH H", "A HOL H")
    h.orders("GERMANY", "F KIE S A RUH - HOL", "A RUH - HOL")
    h.adjudicate()
    h.assert_dislodged("A HOL")

    h.retreats("ENGLAND", "A HOL R YOR", "F NTH C A HOL - YOR")
    h.adjudicate_retreats()
    h.assert_disbanded("A HOL")


def test_6h_4_no_other_moves_during_retreat():
    """6.H.4. TEST CASE, NO OTHER MOVES DURING RETREAT.

    You may not order a move for a unit that was not dislodged. The English
    fleet in the North Sea was not dislodged, so its "retreat" order is
    simply not actionable; the army in Holland retreats normally to Belgium.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A HOL")
    h.units("GERMANY", "F KIE", "A RUH")
    h.orders("ENGLAND", "F NTH H", "A HOL H")
    h.orders("GERMANY", "F KIE S A RUH - HOL", "A RUH - HOL")
    h.adjudicate()
    h.assert_dislodged("A HOL")
    h.assert_not_dislodged("F NTH")

    h.retreats("ENGLAND", "A HOL R BEL", "F NTH R NWG")
    h.adjudicate_retreats()
    h.assert_retreat_ok("A HOL")
    assert h.final_at("BEL") == "ENGLAND"
    # F NTH was never dislodged, so its bogus retreat order has no effect.
    assert h.final_at("NTH") == "ENGLAND"
    assert h.final_at("NWG") is None


def test_6h_5_no_retreat_to_attacker_area():
    """6.H.5. TEST CASE, A UNIT MAY NOT RETREAT TO THE AREA FROM WHICH IT IS ATTACKED.

    The fleet in Ankara is dislodged by the fleet from Black Sea and may not
    retreat there.
    """
    h = Harness()
    h.units("RUSSIA", "F CON", "F BLA")
    h.units("TURKEY", "F ANK")
    h.orders("RUSSIA", "F CON S F BLA - ANK", "F BLA - ANK")
    h.orders("TURKEY", "F ANK H")
    h.adjudicate()
    h.assert_dislodged("F ANK")
    assert "BLA" not in h.retreat_options_at("ANK")

    h.retreats("TURKEY", "F ANK R BLA")
    h.adjudicate_retreats()
    h.assert_disbanded("F ANK")


def test_6h_6_no_retreat_to_contested_area():
    """6.H.6. TEST CASE, UNIT MAY NOT RETREAT TO A CONTESTED AREA.

    Bohemia stood off (Munich vs. Silesia) this movement phase, so the
    dislodged Italian army in Vienna may not retreat there.
    """
    h = Harness()
    h.units("AUSTRIA", "A BUD", "A TRI")
    h.units("GERMANY", "A MUN", "A SIL")
    h.units("ITALY", "A VIE")
    h.orders("AUSTRIA", "A BUD S A TRI - VIE", "A TRI - VIE")
    h.orders("GERMANY", "A MUN - BOH", "A SIL - BOH")
    h.orders("ITALY", "A VIE H")
    h.adjudicate()
    h.assert_dislodged("A VIE")
    h.assert_bounce("A MUN")
    h.assert_bounce("A SIL")
    assert "BOH" not in h.retreat_options_at("VIE")

    h.retreats("ITALY", "A VIE R BOH")
    h.adjudicate_retreats()
    h.assert_disbanded("A VIE")


def test_6h_7_multiple_retreat_to_same_area_disbands():
    """6.H.7. TEST CASE, MULTIPLE RETREAT TO SAME AREA WILL DISBAND UNITS.

    There can only be one unit in an area: both Italian armies retreating to
    Tyrolia bounce and disband.
    """
    h = Harness()
    h.units("AUSTRIA", "A BUD", "A TRI")
    h.units("GERMANY", "A MUN", "A SIL")
    h.units("ITALY", "A VIE", "A BOH")
    h.orders("AUSTRIA", "A BUD S A TRI - VIE", "A TRI - VIE")
    h.orders("GERMANY", "A MUN S A SIL - BOH", "A SIL - BOH")
    h.orders("ITALY", "A VIE H", "A BOH H")
    h.adjudicate()
    h.assert_dislodged("A VIE")
    h.assert_dislodged("A BOH")

    h.retreats("ITALY", "A VIE R TYR", "A BOH R TYR")
    h.adjudicate_retreats()
    h.assert_disbanded("A VIE")
    h.assert_disbanded("A BOH")


def test_6h_8_triple_retreat_to_same_area_disbands():
    """6.H.8. TEST CASE, TRIPLE RETREAT TO SAME AREA WILL DISBAND UNITS.

    All three dislodged fleets retreat to the North Sea and all three disband.
    """
    h = Harness()
    h.units("ENGLAND", "A LVP", "F YOR", "F NWY")
    h.units("GERMANY", "A KIE", "A RUH")
    h.units("RUSSIA", "F EDI", "A SWE", "A FIN", "F HOL")
    h.orders("ENGLAND", "A LVP - EDI", "F YOR S A LVP - EDI", "F NWY H")
    h.orders("GERMANY", "A KIE S A RUH - HOL", "A RUH - HOL")
    h.orders("RUSSIA", "F EDI H", "A SWE S A FIN - NWY", "A FIN - NWY", "F HOL H")
    h.adjudicate()
    h.assert_dislodged("F NWY")
    h.assert_dislodged("F EDI")
    h.assert_dislodged("F HOL")

    h.retreats("ENGLAND", "F NWY R NTH")
    h.retreats("RUSSIA", "F EDI R NTH", "F HOL R NTH")
    h.adjudicate_retreats()
    h.assert_disbanded("F NWY")
    h.assert_disbanded("F EDI")
    h.assert_disbanded("F HOL")


def test_6h_9_dislodged_unit_does_not_contest_attackers_area():
    """6.H.9. TEST CASE, DISLODGED UNIT WILL NOT MAKE ATTACKERS AREA CONTESTED.

    Berlin becomes empty because the German army there successfully moved to
    Prussia (not a standoff), so it is not "contested" and the dislodged
    fleet in Kiel can retreat there.
    """
    h = Harness()
    h.units("ENGLAND", "F HEL", "F DEN")
    h.units("GERMANY", "A BER", "F KIE", "A SIL")
    h.units("RUSSIA", "A PRU")
    h.orders("ENGLAND", "F HEL - KIE", "F DEN S F HEL - KIE")
    h.orders("GERMANY", "A BER - PRU", "F KIE H", "A SIL S A BER - PRU")
    h.orders("RUSSIA", "A PRU - BER")
    h.adjudicate()
    h.assert_dislodged("F KIE")
    h.assert_dislodged("A PRU")

    h.retreats("GERMANY", "F KIE R BER")
    h.adjudicate_retreats()
    h.assert_retreat_ok("F KIE")
    assert h.final_at("BER") == "GERMANY"
    # Russia's dislodged army in Prussia was left unordered.
    h.assert_result_post("A PRU", ResultCode.DISBAND)


def test_6h_10_not_retreating_to_attacker_does_not_mean_contested():
    """6.H.10. TEST CASE, NOT RETREATING TO ATTACKER DOES NOT MEAN CONTESTED.

    The English army in Kiel may not retreat to Berlin (its own attacker's
    origin), but that does NOT make Berlin contested for everyone: the German
    army in Prussia (dislodged by a different attacker) retreats there fine.
    """
    h = Harness()
    h.units("ENGLAND", "A KIE")
    h.units("GERMANY", "A BER", "A MUN", "A PRU")
    h.units("RUSSIA", "A WAR", "A SIL")
    h.orders("ENGLAND", "A KIE H")
    h.orders("GERMANY", "A BER - KIE", "A MUN S A BER - KIE", "A PRU H")
    h.orders("RUSSIA", "A WAR - PRU", "A SIL S A WAR - PRU")
    h.adjudicate()
    h.assert_dislodged("A KIE")
    h.assert_dislodged("A PRU")
    assert "BER" not in h.retreat_options_at("KIE")
    assert "BER" in h.retreat_options_at("PRU")

    h.retreats("ENGLAND", "A KIE R BER")
    h.retreats("GERMANY", "A PRU R BER")
    h.adjudicate_retreats()
    h.assert_disbanded("A KIE")
    h.assert_retreat_ok("A PRU")
    assert h.final_at("BER") == "GERMANY"


def test_6h_11_retreat_when_dislodged_by_adjacent_convoy():
    """6.H.11. TEST CASE, RETREAT WHEN DISLODGED BY ADJACENT CONVOY.

    Gascony convoys to Marseilles (an adjacent-place convoy), dislodging the
    Italian army there. Under the 1982/2000 rule (which this engine follows —
    a convoyed attacker's origin does not block retreats), the dislodged
    Italian army may retreat back to Gascony.
    """
    h = Harness()
    h.units("FRANCE", "A GAS", "A BUR", "F MAO", "F WES", "F LYO")
    h.units("ITALY", "A MAR")
    h.orders(
        "FRANCE",
        "A GAS - MAR VIA",
        "A BUR S A GAS - MAR",
        "F MAO C A GAS - MAR",
        "F WES C A GAS - MAR",
        "F LYO C A GAS - MAR",
    )
    h.orders("ITALY", "A MAR H")
    h.adjudicate()
    h.assert_dislodged("A MAR")
    assert "GAS" in h.retreat_options_at("MAR")

    h.retreats("ITALY", "A MAR R GAS")
    h.adjudicate_retreats()
    h.assert_retreat_ok("A MAR")
    assert h.final_at("GAS") == "ITALY"


def test_6h_12_retreat_when_dislodged_by_adjacent_convoy_both_ways():
    """6.H.12. TEST CASE, RETREAT WHEN DISLODGED BY ADJACENT CONVOY WHILE TRYING TO DO THE SAME.

    Both Liverpool and Edinburgh try to swap by adjacent convoy. Liverpool's
    convoy is disrupted (English Channel fleet is diverted to defend against
    France) so Liverpool fails and is dislodged by the (successful) Russian
    army from Edinburgh. Per the 1982/2000 rule, Liverpool may retreat to
    Edinburgh.
    """
    h = Harness()
    h.units("ENGLAND", "A LVP", "F IRI", "F ENG", "F NTH")
    h.units("FRANCE", "F BRE", "F MAO")
    h.units("RUSSIA", "A EDI", "F NWG", "F NAO", "A CLY")
    h.orders(
        "ENGLAND",
        "A LVP - EDI VIA",
        "F IRI C A LVP - EDI",
        "F ENG C A LVP - EDI",
        "F NTH C A LVP - EDI",
    )
    h.orders("FRANCE", "F BRE - ENG", "F MAO S F BRE - ENG")
    h.orders(
        "RUSSIA",
        "A EDI - LVP VIA",
        "F NWG C A EDI - LVP",
        "F NAO C A EDI - LVP",
        "A CLY S A EDI - LVP",
    )
    h.adjudicate()
    h.assert_dislodged("A LVP")
    h.assert_dislodged("F ENG")
    assert "EDI" in h.retreat_options_at("LVP")

    h.retreats("ENGLAND", "A LVP R EDI", "F ENG D")
    h.adjudicate_retreats()
    h.assert_retreat_ok("A LVP")
    h.assert_disbanded("F ENG")
    assert h.final_at("EDI") == "ENGLAND"


def test_6h_13_no_retreat_with_convoy_in_main_phase():
    """6.H.13. TEST CASE, NO RETREAT WITH CONVOY IN MAIN PHASE.

    Legal retreat destinations are computed from movement-phase adjacency
    only; a convoy ordered during the movement phase can not be reused to
    extend retreat options. The dislodged army in Picardy can not retreat to
    London.
    """
    h = Harness()
    h.units("ENGLAND", "A PIC", "F ENG")
    h.units("FRANCE", "A PAR", "A BRE")
    h.orders("ENGLAND", "A PIC H", "F ENG C A PIC - LON")
    h.orders("FRANCE", "A PAR - PIC", "A BRE S A PAR - PIC")
    h.adjudicate()
    h.assert_dislodged("A PIC")
    assert "LON" not in h.retreat_options_at("PIC")

    h.retreats("ENGLAND", "A PIC R LON")
    h.adjudicate_retreats()
    h.assert_disbanded("A PIC")


def test_6h_14_no_retreat_with_support_in_main_phase():
    """6.H.14. TEST CASE, NO RETREAT WITH SUPPORT IN MAIN PHASE.

    A support given in the movement phase has no bearing on the retreat
    phase. Picardy and Burgundy both retreat toward Belgium, collide, and
    both disband — support cannot resolve that collision here.
    """
    h = Harness()
    h.units("ENGLAND", "A PIC", "F ENG")
    h.units("FRANCE", "A PAR", "A BRE", "A BUR")
    h.units("GERMANY", "A MUN", "A MAR")
    h.orders("ENGLAND", "A PIC H", "F ENG S A PIC - BEL")
    h.orders("FRANCE", "A PAR - PIC", "A BRE S A PAR - PIC", "A BUR H")
    h.orders("GERMANY", "A MUN S A MAR - BUR", "A MAR - BUR")
    h.adjudicate()
    h.assert_dislodged("A PIC")
    h.assert_dislodged("A BUR")

    h.retreats("ENGLAND", "A PIC R BEL")
    h.retreats("FRANCE", "A BUR R BEL")
    h.adjudicate_retreats()
    h.assert_disbanded("A PIC")
    h.assert_disbanded("A BUR")


def test_6h_15_no_coastal_crawl_in_retreat():
    """6.H.15. TEST CASE, NO COASTAL CRAWL IN RETREAT.

    The attacker-origin exclusion is a whole-province rule: the English fleet
    dislodged from Portugal by the fleet from Spain(sc) can not retreat to
    Spain(nc) either.
    """
    h = Harness()
    h.units("ENGLAND", "F POR")
    h.units("FRANCE", "F SPA/SC", "F MAO")
    h.orders("ENGLAND", "F POR H")
    h.orders("FRANCE", "F SPA/SC - POR", "F MAO S F SPA/SC - POR")
    h.adjudicate()
    h.assert_dislodged("F POR")
    assert "SPA" not in h.retreat_options_at("POR")

    h.retreats("ENGLAND", "F POR R SPA/NC")
    h.adjudicate_retreats()
    h.assert_disbanded("F POR")


def test_6h_16_contested_for_both_coasts():
    """6.H.16. TEST CASE, CONTESTED FOR BOTH COASTS.

    Spain(nc) stands off (Mid-Atlantic vs. Gascony), which contests the whole
    Spain province — so the French fleet dislodged from Western Mediterranean
    can not retreat to Spain(sc) either.
    """
    h = Harness()
    h.units("FRANCE", "F MAO", "F GAS", "F WES")
    h.units("ITALY", "F TUN", "F TYS")
    h.orders("FRANCE", "F MAO - SPA/NC", "F GAS - SPA/NC", "F WES H")
    h.orders("ITALY", "F TUN S F TYS - WES", "F TYS - WES")
    h.adjudicate()
    h.assert_bounce("F MAO")
    h.assert_bounce("F GAS")
    h.assert_dislodged("F WES")
    assert "SPA" not in h.retreat_options_at("WES")

    h.retreats("FRANCE", "F WES R SPA/SC")
    h.adjudicate_retreats()
    h.assert_disbanded("F WES")
