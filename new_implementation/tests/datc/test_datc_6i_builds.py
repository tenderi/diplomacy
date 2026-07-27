"""DATC section 6.I — building.

Outcomes cross-checked against the DATC document and the reference resolver in
old_implementation (semantics only; no code copied).
"""

from __future__ import annotations

import pytest

from engine.types import PhaseType, ResultCode, Season
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6i_1_too_many_build_orders():
    """6.I.1. TEST CASE, TOO MANY BUILD ORDERS.

    Germany owns KIE, MUN, WAR (only 2 real German home SCs among them — WAR
    is a Russian home center) and fields 2 fleets not on any of those
    centers, so entitlement is 3 - 2 = 1 build. Germany orders builds in WAR,
    KIE, and MUN. Orders are handled one by one: WAR fails (not a German home
    SC), KIE succeeds (uses the sole entitlement), MUN fails (no builds left).
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("GERMANY", "F NAO", "F MAO")
    h.owns("GERMANY", "KIE", "MUN", "WAR")
    h.orders("GERMANY", "BUILD A WAR", "BUILD A KIE", "BUILD A MUN")
    h.adjudicate_adjustments()
    h.assert_result_post("A WAR", ResultCode.VOID)
    h.assert_built("A KIE")
    h.assert_result_post("A MUN", ResultCode.VOID)
    assert h.final_at("WAR") is None
    assert h.final_at("KIE") == "GERMANY"
    assert h.final_at("MUN") is None


def test_6i_2_fleets_cannot_be_built_in_land_areas():
    """6.I.2. TEST CASE, FLEETS CAN NOT BE BUILD IN LAND AREAS.

    Russia has one build and Moscow (landlocked) is empty. Building a fleet
    there is physically odd but explicitly disallowed: the build fails.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.owns("RUSSIA", "MOS")
    h.orders("RUSSIA", "BUILD F MOS")
    h.adjudicate_adjustments()
    h.assert_result_post("F MOS", ResultCode.VOID)
    assert h.final_at("MOS") is None


def test_6i_3_supply_center_must_be_empty_for_building():
    """6.I.3. TEST CASE, SUPPLY CENTER MUST BE EMPTY FOR BUILDING.

    Germany may build a unit but already has an army in Berlin. The build
    order there fails because you can't have two units in one sector.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("GERMANY", "A BER")
    h.owns("GERMANY", "MUN", "BER")
    h.orders("GERMANY", "BUILD A BER")
    h.adjudicate_adjustments()
    h.assert_result_post("A BER", ResultCode.VOID)
    assert h.final_at("BER") == "GERMANY"


def test_6i_4_both_coasts_must_be_empty_for_building():
    """6.I.4. TEST CASE, BOTH COASTS MUST BE EMPTY FOR BUILDING.

    Russia has a fleet on St Petersburg(sc). Ordering a build on St
    Petersburg(nc) fails because the province is occupied, regardless of
    which coast the existing unit sits on.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("RUSSIA", "F STP/SC")
    h.owns("RUSSIA", "STP", "MOS")
    h.orders("RUSSIA", "BUILD A STP")
    h.adjudicate_adjustments()
    h.assert_result_post("A STP", ResultCode.VOID)
    assert h.final_at("STP") == "RUSSIA"


def test_6i_5_building_in_home_supply_center_that_is_not_owned():
    """6.I.5. TEST CASE, BUILDING IN HOME SUPPLY CENTER THAT IS NOT OWNED.

    Berlin is Germany's home SC, but Russia currently owns it (captured it in
    Fall, then left it empty). Germany cannot build there because it is not
    owned by Germany.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.owns("GERMANY", "MUN")
    h.owns("RUSSIA", "BER")
    h.orders("GERMANY", "BUILD A BER")
    h.adjudicate_adjustments()
    h.assert_result_post("A BER", ResultCode.VOID)
    assert h.final_at("BER") is None


def test_6i_6_building_in_owned_supply_center_that_is_not_a_home_supply_center():
    """6.I.6. TEST CASE, BUILDING IN OWNED SUPPLY CENTER THAT IS NOT A HOME
    SUPPLY CENTER.

    Germany owns Warsaw (not a German home SC) which is empty, and Germany
    may build one unit. The build fails because Warsaw is not a home supply
    center of Germany.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.units("GERMANY", "A MUN")
    h.owns("GERMANY", "MUN", "WAR")
    h.orders("GERMANY", "BUILD A WAR")
    h.adjudicate_adjustments()
    h.assert_result_post("A WAR", ResultCode.VOID)
    assert h.final_at("WAR") is None


def test_6i_7_only_one_build_in_a_home_supply_center():
    """6.I.7. TEST CASE, ONLY ONE BUILD IN A HOME SUPPLY CENTER.

    Russia owns Moscow (empty) and STP, and may build two units. Russia
    orders a build in Moscow twice; only one build per supply center is
    allowed, so the second order fails.
    """
    h = Harness(season=Season.WINTER, phase_type=PhaseType.ADJUSTMENT)
    h.owns("RUSSIA", "STP", "MOS")
    h.orders("RUSSIA", "BUILD A MOS", "BUILD A MOS")
    h.adjudicate_adjustments()
    mos_results = [
        r
        for r in h.retreat_resolution.results
        if getattr(r.order, "location", None) is not None
        and r.order.location.province == "MOS"
    ]
    assert [r.result for r in mos_results] == [ResultCode.BUILD, ResultCode.VOID]
    assert h.final_at("MOS") == "RUSSIA"
