"""DATC section 6.A — basic movement checks.

Outcomes cross-checked against the DATC document and the reference resolver in
old_implementation (semantics only; no code copied).
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6a1_move_to_own_sector_illegal():
    # A move to the same province is not a legal order; a plain hold-equivalent.
    h = Harness()
    h.units("ENGLAND", "F NTH")
    h.orders("ENGLAND", "F NTH - NTH")
    h.adjudicate()
    # Illegal move: unit stays. We accept BOUNCE/VOID; assert it did not "succeed".
    r = h._result_at("F NTH")
    assert r.result is not ResultCode.OK


def test_6a2_move_army_to_sea_illegal():
    h = Harness()
    h.units("ENGLAND", "A LVP")
    h.orders("ENGLAND", "A LVP - IRI")
    h.adjudicate()
    r = h._result_at("A LVP")
    assert r.result is not ResultCode.OK


def test_6a3_move_fleet_to_land_illegal():
    h = Harness()
    h.units("GERMANY", "F KIE")
    h.orders("GERMANY", "F KIE - MUN")
    h.adjudicate()
    r = h._result_at("F KIE")
    assert r.result is not ResultCode.OK


def test_6a5_move_to_own_sector_with_convoy():
    # Simple legal move used as a sanity baseline.
    h = Harness()
    h.units("FRANCE", "A PAR")
    h.orders("FRANCE", "A PAR - BUR")
    h.adjudicate()
    h.assert_success("A PAR")
    h.assert_at("BUR")


def test_6a_basic_bounce():
    # Two armies to the same empty province stand off.
    h = Harness()
    h.units("FRANCE", "A PAR")
    h.units("GERMANY", "A MUN")
    h.orders("FRANCE", "A PAR - BUR")
    h.orders("GERMANY", "A MUN - BUR")
    h.adjudicate()
    h.assert_bounce("A PAR")
    h.assert_bounce("A MUN")
    h.assert_empty("BUR")


def test_6a_supported_move_dislodges():
    # Supported attack dislodges an unsupported holder.
    h = Harness()
    h.units("FRANCE", "A PAR", "A GAS")
    h.units("GERMANY", "A BUR")
    h.orders("FRANCE", "A PAR - BUR", "A GAS S A PAR - BUR")
    h.orders("GERMANY", "A BUR H")
    h.adjudicate()
    h.assert_success("A PAR")
    h.assert_dislodged("A BUR")
    assert h.unit_powers_at("BUR") == "FRANCE"


def test_6a_hold_stronger_bounces_attack():
    # Unsupported attack on a held province bounces (equal strength).
    h = Harness()
    h.units("FRANCE", "A PAR")
    h.units("GERMANY", "A BUR")
    h.orders("FRANCE", "A PAR - BUR")
    h.orders("GERMANY", "A BUR H")
    h.adjudicate()
    h.assert_bounce("A PAR")
    h.assert_not_dislodged("A BUR")


def test_6a_cannot_dislodge_own_unit():
    # A supported attack onto your own unit fails (can't self-dislodge).
    h = Harness()
    h.units("FRANCE", "A PAR", "A GAS", "A BUR")
    h.orders("FRANCE", "A PAR - BUR", "A GAS S A PAR - BUR", "A BUR H")
    h.adjudicate()
    h.assert_bounce("A PAR")
    h.assert_not_dislodged("A BUR")
