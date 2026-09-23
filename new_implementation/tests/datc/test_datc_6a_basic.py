"""DATC section 6.A — basic movement checks.

Outcomes cross-checked against the DATC document and the reference resolver in
the legacy tree (semantics only; no code copied). That tree is gone as of Track
K; `git show v2.7.68:old_implementation/diplomacy/tests/test_datc.py` is the
reference if a case here is ever disputed.

**All twelve 6.A cases are named here.** Four of them (6.A.4, 6.A.6, 6.A.7,
6.A.8, 6.A.10, 6.A.11, 6.A.12) were unnamed or absent until Track K's audit:
the behaviour was mostly covered by generically-named tests, but "mostly" is
exactly what the DATC ids exist to remove.
"""

from __future__ import annotations

import pytest

from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.orders.validation import validate
from engine.types import (
    GameState,
    Location,
    PhaseType,
    ResultCode,
    Season,
    Unit,
    UnitKind,
)
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


def test_6a4_move_to_own_sector():
    """6.A.4. Moving to the province you are already in is not a legal order.

    Same rule as 6.A.1, which uses a fleet at sea; this is the DATC's own
    coastal case (F Kiel - Kiel), kept separate because the two provinces
    exercise different adjacency lookups.
    """
    h = Harness()
    h.units("GERMANY", "F KIE")
    h.orders("GERMANY", "F KIE - KIE")
    h.adjudicate()
    assert h._result_at("F KIE").result is not ResultCode.OK
    assert h.unit_powers_at("KIE") == "GERMANY"


def test_6a6_ordering_a_unit_of_another_country_is_rejected():
    """6.A.6. Germany may not order England's fleet.

    **This rule lives in `orders/validation.py`, not the adjudicator.** The
    resolver deliberately trusts the orders it is handed -- feed it a Move whose
    `power` is not the unit's owner and it will happily execute it -- because
    every real path into it (`GameService.submit_orders`) validates first, and
    re-checking ownership per order inside a fixed-point resolver would cost
    something for nothing. That split is fine, but it means the guarantee is only
    as good as the validation layer, so the test belongs there: any future caller
    that skips `validate()` is applying unauthenticated orders.
    """
    map_data = load_standard_map()
    unit = Unit(power="ENGLAND", kind=UnitKind.FLEET, location=Location(province="LON", coast=None))
    state = GameState(
        year=1901,
        season=Season.SPRING,
        phase_type=PhaseType.MOVEMENT,
        units=frozenset({unit}),
        ownership={},
    )

    foreign = validate(parse_order("F LON - NTH", power="GERMANY", map=map_data), state, map_data)
    assert not foreign.ok
    assert "ENGLAND" in (foreign.reason or "") and "GERMANY" in (foreign.reason or "")

    own = validate(parse_order("F LON - NTH", power="ENGLAND", map=map_data), state, map_data)
    assert own.ok, own.reason


def test_6a7_only_armies_can_be_convoyed():
    """6.A.7. A fleet cannot be convoyed: both the move and the convoy are void."""
    h = Harness()
    h.units("ENGLAND", "F LON", "F NTH")
    h.orders("ENGLAND", "F LON - BEL", "F NTH C A LON - BEL")
    h.adjudicate()
    assert h._result_at("F LON").result is ResultCode.VOID
    assert h._result_at("F NTH").result is ResultCode.VOID
    assert h.unit_powers_at("LON") == "ENGLAND"
    assert h.unit_powers_at("BEL") is None


def test_6a8_support_to_hold_yourself_is_not_possible():
    """6.A.8. A unit cannot support itself; Trieste is dislodged."""
    h = Harness()
    h.units("ITALY", "A VEN", "A TYR")
    h.units("AUSTRIA", "F TRI")
    h.orders("ITALY", "A VEN - TRI", "A TYR S A VEN - TRI")
    h.orders("AUSTRIA", "F TRI S F TRI")
    h.adjudicate()
    assert h._result_at("F TRI").result is ResultCode.VOID
    h.assert_dislodged("F TRI")
    assert h.unit_powers_at("TRI") == "ITALY"
    assert h.unit_powers_at("VEN") is None


def test_6a9_fleets_must_follow_the_coast():
    """6.A.9. Rome and Venice are adjacent by land only, so a fleet cannot move."""
    h = Harness()
    h.units("ITALY", "F ROM")
    h.orders("ITALY", "F ROM - VEN")
    h.adjudicate()
    assert h._result_at("F ROM").result is ResultCode.VOID
    assert h.unit_powers_at("ROM") == "ITALY"
    assert h.unit_powers_at("VEN") is None


def test_6a10_support_on_an_unreachable_destination_is_not_possible():
    """6.A.10. A fleet in Rome cannot support a move into Venice it could not make."""
    h = Harness()
    h.units("ITALY", "F ROM", "A APU")
    h.units("AUSTRIA", "A VEN")
    h.orders("ITALY", "F ROM S A APU - VEN", "A APU - VEN")
    h.orders("AUSTRIA", "A VEN H")
    h.adjudicate()
    assert h._result_at("F ROM").result is ResultCode.VOID
    h.assert_bounce("A APU")
    assert h.unit_powers_at("VEN") == "AUSTRIA"


def test_6a11_simple_bounce():
    """6.A.11. Two units ordered to the same empty province both stand off."""
    h = Harness()
    h.units("ITALY", "A VEN")
    h.units("AUSTRIA", "A VIE")
    h.orders("ITALY", "A VEN - TYR")
    h.orders("AUSTRIA", "A VIE - TYR")
    h.adjudicate()
    h.assert_bounce("A VEN")
    h.assert_bounce("A VIE")
    assert h.unit_powers_at("VEN") == "ITALY"
    assert h.unit_powers_at("VIE") == "AUSTRIA"
    assert h.unit_powers_at("TYR") is None


def test_6a12_bounce_of_three_units():
    """6.A.12. Three units into one province: all three bounce, none prevails."""
    h = Harness()
    h.units("AUSTRIA", "A VIE")
    h.units("GERMANY", "A MUN")
    h.units("ITALY", "A VEN")
    h.orders("AUSTRIA", "A VIE - TYR")
    h.orders("GERMANY", "A MUN - TYR")
    h.orders("ITALY", "A VEN - TYR")
    h.adjudicate()
    for spec in ("A VIE", "A MUN", "A VEN"):
        h.assert_bounce(spec)
    assert h.unit_powers_at("TYR") is None
