"""DATC section 6.B — coastal issues.

Outcomes cross-checked against the DATC document (Kruijswijk) and the reference
resolver in old_implementation (semantics only; no code copied).

Where DATC's author states a "some adjudicators do X, I prefer Y" split, the
test encodes the *preferred* (Y) outcome, per the task brief.

Note on scope: this repo's rewrite has no adjustment-phase adjudicator yet
(only ``adjudicate_movement`` exists). 6.B.14 is a BUILD-order case, so it is
encoded as a parse-time assertion on ``engine.orders.parser.parse_order``
(reached indirectly through ``Harness.orders``) rather than a full adjudication.
"""

from __future__ import annotations

import pytest

from engine.types import Location, ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6b1_moving_with_unspecified_coast_when_coast_is_necessary():
    """6.B.1 MOVING WITH UNSPECIFIED COAST WHEN COAST IS NECESSARY.

    France: F Portugal - Spain. Portugal is adjacent to *both* coasts of
    Spain, so the coast is significant and must be given. DATC's preferred
    outcome: the move fails (VOID); the fleet stays in Portugal.
    """
    h = Harness()
    h.units("FRANCE", "F POR")
    h.orders("FRANCE", "F POR - SPA")
    h.adjudicate()
    h.assert_result("F POR", ResultCode.VOID)
    h.assert_at("POR")
    h.assert_empty("SPA")


def test_6b2_moving_with_unspecified_coast_when_coast_is_not_necessary():
    """6.B.2 MOVING WITH UNSPECIFIED COAST WHEN COAST IS NOT NECESSARY.

    France: F Gascony - Spain. Only the north coast is reachable from
    Gascony, so DATC's preferred outcome is that the move is attempted (and
    succeeds) to Spain's north coast.
    """
    h = Harness()
    h.units("FRANCE", "F GAS")
    h.orders("FRANCE", "F GAS - SPA")
    h.adjudicate()
    h.assert_success("F GAS")
    assert h.new_state is not None
    assert Location("SPA", "NC") in {u.location for u in h.new_state.units}
    assert Location("SPA", "SC") not in {u.location for u in h.new_state.units}


def test_6b3_moving_with_wrong_coast_when_coast_is_not_necessary():
    """6.B.3 MOVING WITH WRONG COAST WHEN COAST IS NOT NECESSARY.

    France: F Gascony - Spain(sc). Only the north coast is reachable from
    Gascony; naming the south coast is precise and wrong. DATC's preferred
    outcome: the move fails (VOID).
    """
    h = Harness()
    h.units("FRANCE", "F GAS")
    h.orders("FRANCE", "F GAS - SPA/SC")
    h.adjudicate()
    h.assert_result("F GAS", ResultCode.VOID)
    h.assert_at("GAS")
    h.assert_empty("SPA")


def test_6b4_support_to_unreachable_coast_allowed():
    """6.B.4 SUPPORT TO UNREACHABLE COAST ALLOWED.

    France: F Gascony - Spain(nc); F Marseilles Supports F Gascony - Spain(nc).
    Italy: F Western Mediterranean - Spain(sc).
    Marseilles cannot itself reach Spain's north coast, but it can still
    support an order targeting it. The support succeeds, Gascony's move
    succeeds, and the Italian move bounces (Spain can only hold one fleet).
    """
    h = Harness()
    h.units("FRANCE", "F GAS", "F MAR")
    h.units("ITALY", "F WES")
    h.orders("FRANCE", "F GAS - SPA/NC", "F MAR S F GAS - SPA/NC")
    h.orders("ITALY", "F WES - SPA/SC")
    h.adjudicate()
    h.assert_success("F GAS")
    h.assert_success("F MAR")
    h.assert_bounce("F WES")
    assert h.unit_powers_at("SPA") == "FRANCE"
    assert h.unit_powers_at("WES") == "ITALY"


def test_6b5_support_from_unreachable_coast_not_allowed():
    """6.B.5 SUPPORT FROM UNREACHABLE COAST NOT ALLOWED.

    France: F Marseilles - Gulf of Lyon; F Spain(nc) Supports F Marseilles -
    Gulf of Lyon. Italy: F Gulf of Lyon Hold.
    The Gulf of Lyon cannot be reached from Spain's north coast, so the
    support is invalid (VOID) and the Italian fleet is not dislodged.
    """
    h = Harness()
    h.units("FRANCE", "F MAR", "F SPA/NC")
    h.units("ITALY", "F LYO")
    h.orders("FRANCE", "F MAR - LYO", "F SPA/NC S F MAR - LYO")
    h.orders("ITALY", "F LYO H")
    h.adjudicate()
    h.assert_result("F SPA/NC", ResultCode.VOID)
    h.assert_bounce("F MAR")
    h.assert_not_dislodged("F LYO")
    assert h.unit_powers_at("MAR") == "FRANCE"
    assert h.unit_powers_at("SPA") == "FRANCE"
    assert h.unit_powers_at("LYO") == "ITALY"


def test_6b6_support_can_be_cut_with_other_coast():
    """6.B.6 SUPPORT CAN BE CUT WITH OTHER COAST.

    England: F Irish Sea Supports F North Atlantic Ocean - Mid-Atlantic
    Ocean; F North Atlantic Ocean - Mid-Atlantic Ocean.
    France: F Spain(nc) Supports F Mid-Atlantic Ocean; F Mid-Atlantic Ocean
    Hold. Italy: F Gulf of Lyon - Spain(sc).
    An attack on Spain's south coast still cuts a support order given by the
    unit occupying Spain's north coast (the attack targets the province).
    The French fleet in Mid-Atlantic is dislodged by England's fleet.
    """
    h = Harness()
    h.units("ENGLAND", "F IRI", "F NAO")
    h.units("FRANCE", "F SPA/NC", "F MAO")
    h.units("ITALY", "F LYO")
    h.orders("ENGLAND", "F IRI S F NAO - MAO", "F NAO - MAO")
    h.orders("FRANCE", "F SPA/NC S F MAO", "F MAO H")
    h.orders("ITALY", "F LYO - SPA/SC")
    h.adjudicate()
    h.assert_result("F SPA/NC", ResultCode.CUT)
    h.assert_dislodged("F MAO")
    assert h.unit_powers_at("IRI") == "ENGLAND"
    assert h.unit_powers_at("MAO") == "ENGLAND"
    assert h.unit_powers_at("SPA") == "FRANCE"
    assert h.unit_powers_at("LYO") == "ITALY"


def test_6b7_supporting_with_unspecified_coast():
    """6.B.7 SUPPORTING WITH UNSPECIFIED COAST.

    France: F Portugal Supports F Mid-Atlantic Ocean - Spain; F Mid-Atlantic
    Ocean - Spain(nc). Italy: F Gulf of Lyon Supports F Western Mediterranean
    - Spain(sc); F Western Mediterranean - Spain(sc).
    DATC's preferred outcome: coordless support orders are accepted, so
    Portugal's support succeeds and the Italian fleet in the Western
    Mediterranean bounces.

    KNOWN ENGINE LIMITATION: this engine's parser rejects a fleet-typed
    support target naming a split-coast province with no coast at
    *parse time* (``OrderParseError``: "fleet order for split-coast
    province SPA must name a coast") -- it never reaches the adjudicator.
    This test therefore documents the DATC-preferred outcome and is expected
    to fail/error against the current parser.
    """
    h = Harness()
    h.units("FRANCE", "F POR", "F MAO")
    h.units("ITALY", "F LYO", "F WES")
    h.orders("FRANCE", "F POR S F MAO - SPA", "F MAO - SPA/NC")
    h.orders("ITALY", "F LYO S F WES - SPA/SC", "F WES - SPA/SC")
    h.adjudicate()
    h.assert_success("F POR")
    h.assert_success("F LYO")
    h.assert_bounce("F MAO")
    h.assert_bounce("F WES")
    assert h.unit_powers_at("POR") == "FRANCE"
    assert h.unit_powers_at("MAO") == "FRANCE"
    assert h.unit_powers_at("LYO") == "ITALY"
    assert h.unit_powers_at("WES") == "ITALY"
    assert h.unit_powers_at("SPA") is None


def test_6b8_supporting_with_unspecified_coast_when_only_one_coast_possible():
    """6.B.8 SUPPORTING WITH UNSPECIFIED COAST WHEN ONLY ONE COAST IS POSSIBLE.

    France: F Portugal Supports F Gascony - Spain; F Gascony - Spain(nc).
    Italy: F Gulf of Lyon Supports F Western Mediterranean - Spain(sc);
    F Western Mediterranean - Spain(sc).
    DATC's preferred outcome: supporting without a coast is allowed, so
    Portugal's support succeeds and the Italian fleet bounces.

    KNOWN ENGINE LIMITATION: same parse-time rejection as 6.B.7 -- a fleet
    support target naming split-coast Spain with no coast raises
    ``OrderParseError`` before adjudication runs.
    """
    h = Harness()
    h.units("FRANCE", "F POR", "F GAS")
    h.units("ITALY", "F LYO", "F WES")
    h.orders("FRANCE", "F POR S F GAS - SPA", "F GAS - SPA/NC")
    h.orders("ITALY", "F LYO S F WES - SPA/SC", "F WES - SPA/SC")
    h.adjudicate()
    h.assert_success("F POR")
    h.assert_success("F LYO")
    h.assert_bounce("F GAS")
    h.assert_bounce("F WES")
    assert h.unit_powers_at("POR") == "FRANCE"
    assert h.unit_powers_at("GAS") == "FRANCE"
    assert h.unit_powers_at("LYO") == "ITALY"
    assert h.unit_powers_at("WES") == "ITALY"
    assert h.unit_powers_at("SPA") is None


def test_6b9_supporting_with_wrong_coast():
    """6.B.9 SUPPORTING WITH WRONG COAST.

    France: F Portugal Supports F Mid-Atlantic Ocean - Spain(nc); F
    Mid-Atlantic Ocean - Spain(sc). Italy: F Gulf of Lyon Supports F Western
    Mediterranean - Spain(sc); F Western Mediterranean - Spain(sc).
    DATC's preferred outcome: a support naming the wrong coast fails, so the
    French move bounces and the Italian fleet moves successfully.
    """
    h = Harness()
    h.units("FRANCE", "F POR", "F MAO")
    h.units("ITALY", "F LYO", "F WES")
    h.orders("FRANCE", "F POR S F MAO - SPA/NC", "F MAO - SPA/SC")
    h.orders("ITALY", "F LYO S F WES - SPA/SC", "F WES - SPA/SC")
    h.adjudicate()
    h.assert_result("F POR", ResultCode.VOID)
    h.assert_bounce("F MAO")
    h.assert_success("F LYO")
    h.assert_success("F WES")
    assert h.unit_powers_at("POR") == "FRANCE"
    assert h.unit_powers_at("MAO") == "FRANCE"
    assert h.unit_powers_at("SPA") == "ITALY"


def test_6b10_unit_ordered_with_wrong_coast():
    """6.B.10 UNIT ORDERED WITH WRONG COAST.

    France has a fleet on the south coast of Spain and orders
    F Spain(nc) - Gulf of Lyon. The coast named for the *ordering* unit
    itself has no adjudicative purpose; DATC's preferred outcome is that a
    move is attempted (and here it succeeds, since Spain(sc) - Lyon is
    legal).
    """
    h = Harness()
    h.units("FRANCE", "F SPA/SC")
    h.orders("FRANCE", "F SPA/NC - LYO")
    h.adjudicate()
    h.assert_success("F SPA/SC")
    assert h.unit_powers_at("SPA") is None
    assert h.unit_powers_at("LYO") == "FRANCE"


def test_6b11_coast_cannot_be_ordered_to_change():
    """6.B.11 COAST CAN NOT BE ORDERED TO CHANGE.

    France has a fleet on the north coast of Spain and orders
    F Spain(sc) - Gulf of Lyon. The actual unit's coast (north) determines
    legality, and Spain's north coast does not reach the Gulf of Lyon, so
    the move fails (VOID).
    """
    h = Harness()
    h.units("FRANCE", "F SPA/NC")
    h.orders("FRANCE", "F SPA/SC - LYO")
    h.adjudicate()
    h.assert_result("F SPA/NC", ResultCode.VOID)
    assert h.unit_powers_at("SPA") == "FRANCE"
    assert h.unit_powers_at("LYO") is None


def test_6b12_army_movement_with_coastal_specification():
    """6.B.12 ARMY MOVEMENT WITH COASTAL SPECIFICATION.

    France: A Gascony - Spain(nc). Coasts are irrelevant for armies. DATC's
    preferred outcome: a move is attempted (and succeeds) despite the
    superfluous coast.

    KNOWN ENGINE LIMITATION: this engine's parser rejects any coast
    specification on an army order's destination at *parse time*
    (``OrderParseError``: "an army location may not specify a coast") --
    it never reaches the adjudicator.
    """
    h = Harness()
    h.units("FRANCE", "A GAS")
    h.orders("FRANCE", "A GAS - SPA/NC")
    h.adjudicate()
    h.assert_success("A GAS")
    assert h.unit_powers_at("GAS") is None
    assert h.unit_powers_at("SPA") == "FRANCE"


def test_6b13_coastal_crawl_not_allowed():
    """6.B.13 COASTAL CRAWL NOT ALLOWED.

    Turkey: F Bulgaria(sc) - Constantinople; F Constantinople - Bulgaria(ec).
    A head-to-head battle is still a head-to-head battle even when the two
    fleets swap into different coasts of each other's province (the 1971
    rules revision). Both moves fail.
    """
    h = Harness()
    h.units("TURKEY", "F BUL/SC", "F CON")
    h.orders("TURKEY", "F BUL/SC - CON", "F CON - BUL/EC")
    h.adjudicate()
    h.assert_bounce("F BUL/SC")
    h.assert_bounce("F CON")
    assert h.unit_powers_at("BUL") == "TURKEY"
    assert h.unit_powers_at("CON") == "TURKEY"


def test_6b14_building_with_unspecified_coast():
    """6.B.14 BUILDING WITH UNSPECIFIED COAST.

    Russia: Build F St Petersburg. St Petersburg is a split-coast province
    (NC/SC); DATC's preferred outcome (no default coast taken): the build
    fails.

    This engine has no adjustment-phase adjudicator yet (only
    ``adjudicate_movement`` exists), so there is nothing to run the order
    through -- but the DATC-preferred failure already happens one layer
    earlier: the parser raises ``OrderParseError`` for a fleet build target
    naming a split-coast province with no coast, which is a faithful (if
    early) encoding of "the build fails".
    """
    h = Harness()
    with pytest.raises(ValueError):
        h.orders("RUSSIA", "BUILD F STP")
