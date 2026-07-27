"""DATC section 6.C — circular movement.

Outcomes cross-checked against the DATC document (Kruijswijk) and the
reference resolver in old_implementation (semantics only; no code copied).
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6c1_three_army_circular_movement():
    """6.C.1 THREE ARMY CIRCULAR MOVEMENT.

    Turkey: F Ankara - Constantinople; A Constantinople - Smyrna;
    A Smyrna - Ankara. Three units can rotate places, even in Spring 1901.
    All three moves succeed.
    """
    h = Harness()
    h.units("TURKEY", "F ANK", "A CON", "A SMY")
    h.orders("TURKEY", "F ANK - CON", "A CON - SMY", "A SMY - ANK")
    h.adjudicate()
    h.assert_success("F ANK")
    h.assert_success("A CON")
    h.assert_success("A SMY")
    assert h.unit_powers_at("ANK") == "TURKEY"
    assert h.unit_powers_at("CON") == "TURKEY"
    assert h.unit_powers_at("SMY") == "TURKEY"


def test_6c2_three_army_circular_movement_with_support():
    """6.C.2 THREE ARMY CIRCULAR MOVEMENT WITH SUPPORT.

    Turkey: F Ankara - Constantinople; A Constantinople - Smyrna;
    A Smyrna - Ankara; A Bulgaria Supports F Ankara - Constantinople.
    The rotation still succeeds even with one move supported -- a case
    known to confuse naive adjudicators.
    """
    h = Harness()
    h.units("TURKEY", "F ANK", "A CON", "A SMY", "A BUL")
    h.orders(
        "TURKEY",
        "F ANK - CON",
        "A CON - SMY",
        "A SMY - ANK",
        "A BUL S F ANK - CON",
    )
    h.adjudicate()
    h.assert_success("F ANK")
    h.assert_success("A CON")
    h.assert_success("A SMY")
    h.assert_success("A BUL")
    assert h.unit_powers_at("ANK") == "TURKEY"
    assert h.unit_powers_at("CON") == "TURKEY"
    assert h.unit_powers_at("SMY") == "TURKEY"
    assert h.unit_powers_at("BUL") == "TURKEY"


def test_6c3_a_disrupted_three_army_circular_movement():
    """6.C.3 A DISRUPTED THREE ARMY CIRCULAR MOVEMENT.

    Turkey: F Ankara - Constantinople; A Constantinople - Smyrna;
    A Smyrna - Ankara; A Bulgaria - Constantinople.
    Bulgaria's competing move on Constantinople bounces, and that bounce
    disrupts the whole rotation: every unit keeps its place.
    """
    h = Harness()
    h.units("TURKEY", "F ANK", "A CON", "A SMY", "A BUL")
    h.orders(
        "TURKEY",
        "F ANK - CON",
        "A CON - SMY",
        "A SMY - ANK",
        "A BUL - CON",
    )
    h.adjudicate()
    h.assert_bounce("F ANK")
    h.assert_bounce("A CON")
    h.assert_bounce("A SMY")
    h.assert_bounce("A BUL")
    assert h.unit_powers_at("ANK") == "TURKEY"
    assert h.unit_powers_at("CON") == "TURKEY"
    assert h.unit_powers_at("SMY") == "TURKEY"
    assert h.unit_powers_at("BUL") == "TURKEY"


def test_6c4_a_circular_movement_with_attacked_convoy():
    """6.C.4 A CIRCULAR MOVEMENT WITH ATTACKED CONVOY.

    Austria: A Trieste - Serbia; A Serbia - Bulgaria.
    Turkey: A Bulgaria - Trieste, convoyed by F Aegean/F Ionian/F Adriatic.
    Italy: F Naples - Ionian Sea.
    The convoying fleet in the Ionian Sea is attacked but not dislodged
    (Naples' attack bounces). Attacks on convoys must be resolved before
    circular movement is calculated, so the circular movement still
    succeeds and both armies advance.
    """
    h = Harness()
    h.units("AUSTRIA", "A TRI", "A SER")
    h.units("TURKEY", "A BUL", "F AEG", "F ION", "F ADR")
    h.units("ITALY", "F NAP")
    h.orders("AUSTRIA", "A TRI - SER", "A SER - BUL")
    h.orders(
        "TURKEY",
        "A BUL - TRI",
        "F AEG C A BUL - TRI",
        "F ION C A BUL - TRI",
        "F ADR C A BUL - TRI",
    )
    h.orders("ITALY", "F NAP - ION")
    h.adjudicate()
    h.assert_success("A TRI")
    h.assert_success("A SER")
    h.assert_success("A BUL")
    h.assert_success("F AEG")
    h.assert_success("F ION")
    h.assert_success("F ADR")
    h.assert_bounce("F NAP")
    assert h.unit_powers_at("TRI") == "TURKEY"
    assert h.unit_powers_at("SER") == "AUSTRIA"
    assert h.unit_powers_at("BUL") == "AUSTRIA"
    assert h.unit_powers_at("AEG") == "TURKEY"
    assert h.unit_powers_at("ION") == "TURKEY"
    assert h.unit_powers_at("ADR") == "TURKEY"
    assert h.unit_powers_at("NAP") == "ITALY"


def test_6c5_a_disrupted_circular_movement_due_to_dislodged_convoy():
    """6.C.5 A DISRUPTED CIRCULAR MOVEMENT DUE TO DISLODGED CONVOY.

    Same as 6.C.4, but Italy now supports Naples' attack on the Ionian Sea
    (F Tunis Supports F Naples - Ionian Sea), which dislodges the
    convoying fleet. Convoy disruption must be resolved before circular
    movement, so the whole rotation fails: all Austrian and Turkish armies
    stay put, and the convoy orders resolve NO_CONVOY (the dislodged fleet
    itself is DISLODGED).
    """
    h = Harness()
    h.units("AUSTRIA", "A TRI", "A SER")
    h.units("TURKEY", "A BUL", "F AEG", "F ION", "F ADR")
    h.units("ITALY", "F NAP", "F TUN")
    h.orders("AUSTRIA", "A TRI - SER", "A SER - BUL")
    h.orders(
        "TURKEY",
        "A BUL - TRI",
        "F AEG C A BUL - TRI",
        "F ION C A BUL - TRI",
        "F ADR C A BUL - TRI",
    )
    h.orders("ITALY", "F NAP - ION", "F TUN S F NAP - ION")
    h.adjudicate()
    h.assert_bounce("A TRI")
    h.assert_bounce("A SER")
    h.assert_result("A BUL", ResultCode.NO_CONVOY)
    h.assert_result("F AEG", ResultCode.NO_CONVOY)
    h.assert_dislodged("F ION")
    h.assert_result("F ADR", ResultCode.NO_CONVOY)
    h.assert_success("F NAP")
    h.assert_success("F TUN")
    assert h.unit_powers_at("TRI") == "AUSTRIA"
    assert h.unit_powers_at("SER") == "AUSTRIA"
    assert h.unit_powers_at("BUL") == "TURKEY"
    assert h.unit_powers_at("AEG") == "TURKEY"
    assert h.unit_powers_at("ION") == "ITALY"
    assert h.unit_powers_at("ADR") == "TURKEY"
    assert h.unit_powers_at("NAP") is None
    assert h.unit_powers_at("TUN") == "ITALY"


def test_6c6_two_armies_with_two_convoys():
    """6.C.6 TWO ARMIES WITH TWO CONVOYS.

    England: F North Sea Convoys A London - Belgium; A London - Belgium.
    France: F English Channel Convoys A Belgium - London; A Belgium -
    London. Two armies can swap places via separate convoy routes even
    though they are not adjacent. Both convoys succeed.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("FRANCE", "F ENG", "A BEL")
    h.orders("ENGLAND", "F NTH C A LON - BEL", "A LON - BEL")
    h.orders("FRANCE", "F ENG C A BEL - LON", "A BEL - LON")
    h.adjudicate()
    h.assert_success("F NTH")
    h.assert_success("A LON")
    h.assert_success("F ENG")
    h.assert_success("A BEL")
    assert h.unit_powers_at("NTH") == "ENGLAND"
    assert h.unit_powers_at("BEL") == "ENGLAND"
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("LON") == "FRANCE"


def test_6c7_disrupted_unit_swap():
    """6.C.7 DISRUPTED UNIT SWAP.

    Same as 6.C.6, plus France: A Burgundy - Belgium. The third move onto
    Belgium bounces both convoyed armies (Belgium's move fails, and by the
    swap dependency London's move fails too), and Burgundy itself also
    bounces since Belgium's occupant does not vacate. None of the moving
    units end up moving.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("FRANCE", "F ENG", "A BEL", "A BUR")
    h.orders("ENGLAND", "F NTH C A LON - BEL", "A LON - BEL")
    h.orders(
        "FRANCE",
        "F ENG C A BEL - LON",
        "A BEL - LON",
        "A BUR - BEL",
    )
    h.adjudicate()
    h.assert_success("F NTH")
    h.assert_bounce("A LON")
    h.assert_success("F ENG")
    h.assert_bounce("A BEL")
    h.assert_bounce("A BUR")
    assert h.unit_powers_at("NTH") == "ENGLAND"
    assert h.unit_powers_at("LON") == "ENGLAND"
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("BEL") == "FRANCE"
    assert h.unit_powers_at("BUR") == "FRANCE"
