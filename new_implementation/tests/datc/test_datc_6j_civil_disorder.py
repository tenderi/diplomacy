"""DATC section 6.J — civil disorder / removals (winter adjustment removals).

Outcomes cross-checked against the DATC document and the reference resolver in
old_implementation (semantics only; no code copied).

Home supply centers (maps/standard.map): FRANCE = BRE MAR PAR;
RUSSIA = MOS SEV STP WAR; ITALY = NAP ROM VEN.
"""

from __future__ import annotations

import pytest

from engine.types import PhaseType, ResultCode, Season
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6j_1_too_many_remove_orders():
    """6.J.1. TEST CASE, TOO MANY REMOVE ORDERS.

    France has to disband one, has armies in Paris and Picardy, and is given
    three disband orders (fleet Gulf of Lyon does not exist, Picardy, Paris).
    Orders are handled one by one: F LYO fails (no such unit), A PIC succeeds,
    A PAR fails (the removal quota is already met).
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("FRANCE", "A PIC", "A PAR")
    h.owns("FRANCE", "PAR")  # 1 center, 2 units -> must remove 1
    h.orders("FRANCE", "F LYO D", "A PIC D", "A PAR D")
    h.adjudicate_adjustments()

    h.assert_result_post("F LYO", ResultCode.VOID)
    h.assert_disbanded("A PIC")
    h.assert_result_post("A PAR", ResultCode.VOID)

    assert h.final_at("PAR") == "FRANCE"
    assert h.final_at("PIC") is None
    assert h.unit_count("FRANCE") == 1


def test_6j_2_removing_the_same_unit_twice():
    """6.J.2. TEST CASE, REMOVING THE SAME UNIT TWICE.

    France has to disband two, has an army in Paris, and orders "Remove A
    Paris" twice. The program removes Paris once (the duplicate is void) and
    makes up the remaining deficit via civil disorder. France's other units
    are A Picardy (distance 1 from BRE/PAR) and F North Atlantic Ocean
    (distance 2, via MAO to BRE) -- the fleet is farther, so it is the one
    auto-removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("FRANCE", "A PIC", "A PAR", "F NAO")
    h.owns("FRANCE", "PAR")  # 1 center, 3 units -> must remove 2
    h.orders("FRANCE", "A PAR D", "A PAR D")
    h.adjudicate_adjustments()

    par_results = [
        r
        for r in h.retreat_resolution.results
        if getattr(r.order, "unit", None) is not None
        and r.order.unit.province == "PAR"
    ]
    assert len(par_results) == 2
    assert {r.result for r in par_results} == {ResultCode.DISBAND, ResultCode.VOID}

    assert h.final_at("PAR") is None
    assert h.final_at("PIC") == "FRANCE"
    assert h.final_at("NAO") is None
    assert h.unit_count("FRANCE") == 1


def test_6j_3_civil_disorder_two_armies_different_distance():
    """6.J.3. TEST CASE, CIVIL DISORDER TWO ARMIES WITH DIFFERENT DISTANCE.

    Russia has to remove one, has armies in Livonia and Sweden, and does not
    order a disband. The army with the greater distance from a home supply
    center (Sweden) is removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "A LVN", "A SWE")
    h.owns("RUSSIA", "SWE")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("LVN") == "RUSSIA"
    assert h.final_at("SWE") is None


def test_6j_4_civil_disorder_two_armies_equal_distance():
    """6.J.4. TEST CASE, CIVIL DISORDER TWO ARMIES WITH EQUAL DISTANCE.

    Russia has to remove one, has armies in Livonia and Ukraine (both
    distance one from a home center), and does not order a disband. Ties are
    broken alphabetically: Livonia is removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "A LVN", "A UKR")
    h.owns("RUSSIA", "STP")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("LVN") is None
    assert h.final_at("UKR") == "RUSSIA"


def test_6j_5_civil_disorder_two_fleets_different_distance():
    """6.J.5. TEST CASE, CIVIL DISORDER TWO FLEETS WITH DIFFERENT DISTANCE.

    Russia has to remove one, has fleets in Skagerrak and Berlin, and does
    not order a disband. Fleets cannot cross land: Berlin's fleet-only
    distance to a home center is greater than Skagerrak's, so Berlin is
    removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "F SKA", "F BER")
    h.owns("RUSSIA", "BER")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("SKA") == "RUSSIA"
    assert h.final_at("BER") is None


def test_6j_6_civil_disorder_two_fleets_equal_distance():
    """6.J.6. TEST CASE, CIVIL DISORDER TWO FLEETS WITH EQUAL DISTANCE.

    Russia has to remove one, has fleets in Berlin and Helgoland Bight
    (equal fleet-only distance to a home center, since fleets cannot cross
    land via Warsaw), and does not order a disband. Ties are broken
    alphabetically: Berlin is removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "F BER", "F HEL")
    h.owns("RUSSIA", "BER")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("BER") is None
    assert h.final_at("HEL") == "RUSSIA"


def test_6j_7_civil_disorder_two_fleets_and_army_equal_distance():
    """6.J.7. TEST CASE, CIVIL DISORDER TWO FLEETS AND ARMY WITH EQUAL DISTANCE.

    Russia has to remove one, has an army in Bohemia and fleets in Skagerrak
    and the North Sea, all at equal distance from a home center, and does
    not order a disband. Fleets take precedence over the army for removal;
    between the two fleets, North Sea is alphabetically first and is
    removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "A BOH", "F SKA", "F NTH")
    h.owns("RUSSIA", "STP", "MOS")  # 2 centers, 3 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("BOH") == "RUSSIA"
    assert h.final_at("SKA") == "RUSSIA"
    assert h.final_at("NTH") is None


def test_6j_8_civil_disorder_fleet_shorter_distance_than_army():
    """6.J.8. TEST CASE, CIVIL DISORDER A FLEET WITH SHORTER DISTANCE THEN THE ARMY.

    Russia has to remove one, has an army in Tyrolia and a fleet in the
    Baltic Sea, and does not order a disband. The army's distance to Warsaw
    is greater than the fleet's distance to St Petersburg, so the army is
    removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "A TYR", "F BAL")
    h.owns("RUSSIA", "STP")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("TYR") is None
    assert h.final_at("BAL") == "RUSSIA"


def test_6j_9_civil_disorder_counted_from_both_coasts():
    """6.J.9. TEST CASE, CIVIL DISORDER MUST BE COUNTED FROM BOTH COASTS.

    Distance must be calculated from both coasts of a split-coast home
    center.

    a) Russia has to remove one, has an army in Tyrolia and a fleet in the
       Baltic Sea, and does not order a disband. The fleet's distance to St
       Petersburg(sc) (two) is shorter than to St Petersburg(nc) (three),
       and the minimum must be used: the army in Tyrolia is removed.

    b) Russia has to remove one, has an army in Tyrolia and a fleet in
       Skagerrak, and does not order a disband. The fleet's distance to St
       Petersburg(nc) (two) is shorter than to St Petersburg(sc) (three),
       and the minimum must be used: the army in Tyrolia is removed.
    """
    # a)
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "A TYR", "F BAL")
    h.owns("RUSSIA", "STP")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("TYR") is None
    assert h.final_at("BAL") == "RUSSIA"

    # b)
    h2 = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h2.units("RUSSIA", "A TYR", "F SKA")
    h2.owns("RUSSIA", "STP")  # 1 center, 2 units -> must remove 1
    h2.adjudicate_adjustments()

    assert h2.final_at("TYR") is None
    assert h2.final_at("SKA") == "RUSSIA"


def test_6j_10_civil_disorder_counting_convoying_distance():
    """6.J.10. TEST CASE, CIVIL DISORDER COUNTING CONVOYING DISTANCE.

    Italy has to remove one, has a fleet in the Ionian Sea and armies in
    Greece and Silesia, and does not order a disband. For an army, the
    distance calculation must allow sea steps (as if convoyed), so Greece is
    close to home via the Ionian Sea; Silesia's land-only route is farther
    and it is removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("ITALY", "F ION", "A GRE", "A SIL")
    h.owns("ITALY", "GRE", "NAP")  # 2 centers, 3 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("ION") == "ITALY"
    assert h.final_at("GRE") == "ITALY"
    assert h.final_at("SIL") is None


def test_6j_11_civil_disorder_counting_distance_without_convoying_fleet():
    """6.J.11. TEST CASE, CIVIL DISORDER COUNTING DISTANCE WITHOUT CONVOYING FLEET.

    Italy has to remove one, has armies in Greece and Silesia (no convoying
    fleet present), and does not order a disband. Even without an actual
    fleet, sea steps still count as one hop toward home for distance
    purposes, so Greece is closer than Silesia and Silesia is removed.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("ITALY", "A GRE", "A SIL")
    h.owns("ITALY", "GRE")  # 1 center, 2 units -> must remove 1
    h.adjudicate_adjustments()

    assert h.final_at("GRE") == "ITALY"
    assert h.final_at("SIL") is None
