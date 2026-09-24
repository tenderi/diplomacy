"""Adjustment-phase edge rules the DATC 6.I/6.J cases don't reach: orders that do not
fit the power's position are void, never partly honoured.

Rulebook: a power with as many units as centres adjusts nothing; one owed builds may
build or waive up to the entitlement; one owing removals may only disband.
"""
from __future__ import annotations

from engine.adjudicator.adjustments import adjudicate_adjustments
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.types import GameState, Location, PhaseType, ResultCode, Season, Unit, UnitKind

_MAP = load_standard_map()


def _adjust(units: list[tuple[str, str, str]], owns: dict[str, list[str]], orders: dict[str, list[str]]):
    state = GameState(
        year=1901,
        season=Season.WINTER,
        phase_type=PhaseType.ADJUSTMENT,
        units=frozenset(Unit(UnitKind(kind), power, Location(prov)) for power, kind, prov in units),
        ownership={prov: power for power, provs in owns.items() for prov in provs},
    )
    parsed = [parse_order(s, power=power, map=_MAP) for power, strings in orders.items() for s in strings]
    resolution, new_state = adjudicate_adjustments(_MAP, state, parsed)
    return [(r.order.order_type.name, r.result) for r in resolution.results], new_state


def test_a_balanced_power_can_neither_build_nor_disband() -> None:
    results, new_state = _adjust(
        [("FRANCE", "A", "PAR")], {"FRANCE": ["PAR"]}, {"FRANCE": ["BUILD A MAR", "D A PAR", "WAIVE"]}
    )
    assert results == [("BUILD", ResultCode.VOID), ("DISBAND", ResultCode.VOID), ("WAIVE", ResultCode.VOID)]
    assert {u.province for u in new_state.units} == {"PAR"}


def test_waives_count_against_the_entitlement_and_extras_are_void() -> None:
    # Two builds owed (three centres, one unit); the first waive and the build use both.
    results, new_state = _adjust(
        [("FRANCE", "A", "PIC")], {"FRANCE": ["PAR", "MAR", "BRE"]},
        {"FRANCE": ["WAIVE", "BUILD A PAR", "WAIVE", "BUILD A MAR"]},
    )
    assert results == [
        ("WAIVE", ResultCode.WAIVE), ("BUILD", ResultCode.BUILD),
        ("WAIVE", ResultCode.VOID), ("BUILD", ResultCode.VOID),
    ]
    assert {u.province for u in new_state.units} == {"PIC", "PAR"}


def test_a_disband_while_owed_builds_is_void_and_the_unit_stays() -> None:
    results, new_state = _adjust(
        [("FRANCE", "A", "PIC")], {"FRANCE": ["PAR", "MAR"]}, {"FRANCE": ["D A PIC", "BUILD A PAR"]}
    )
    assert results == [("DISBAND", ResultCode.VOID), ("BUILD", ResultCode.BUILD)]
    assert {u.province for u in new_state.units} == {"PIC", "PAR"}


def test_building_twice_in_one_centre_builds_once() -> None:
    results, new_state = _adjust([], {"RUSSIA": ["STP", "MOS"]}, {"RUSSIA": ["BUILD F STP/NC", "BUILD A STP"]})
    # Two builds owed; the unused one is waived automatically.
    assert results == [("BUILD", ResultCode.BUILD), ("BUILD", ResultCode.VOID), ("WAIVE", ResultCode.WAIVE)]
    assert [(u.kind, u.location) for u in new_state.units] == [(UnitKind.FLEET, Location("STP", "NC"))]


def test_a_power_owing_removals_cannot_build_or_waive_and_disorder_finishes_the_job() -> None:
    # Two units, no centres: both must go. The ordered disband is honoured, the build
    # and waive are void, and civil disorder removes the other unit.
    results, new_state = _adjust(
        [("ITALY", "A", "VEN"), ("ITALY", "F", "ION")], {},
        {"ITALY": ["BUILD A ROM", "WAIVE", "D A VEN"]},
    )
    assert results[:3] == [("BUILD", ResultCode.VOID), ("WAIVE", ResultCode.VOID), ("DISBAND", ResultCode.DISBAND)]
    assert results[3:] == [("DISBAND", ResultCode.DISBAND)]  # the civil-disorder removal of F ION
    assert new_state.units_of("ITALY") == frozenset()


def test_disbanding_another_powers_unit_or_the_same_unit_twice_is_void() -> None:
    results, new_state = _adjust(
        [("ITALY", "A", "VEN"), ("ITALY", "A", "ROM"), ("AUSTRIA", "A", "TRI")],
        {"ITALY": ["ROM"], "AUSTRIA": ["TRI"]},
        {"ITALY": ["D A TRI", "D A VEN", "D A VEN"]},
    )
    assert results == [("DISBAND", ResultCode.VOID), ("DISBAND", ResultCode.DISBAND), ("DISBAND", ResultCode.VOID)]
    assert {u.province for u in new_state.units} == {"ROM", "TRI"}


def test_movement_orders_given_in_the_adjustment_phase_are_ignored() -> None:
    results, new_state = _adjust([("FRANCE", "A", "PIC")], {"FRANCE": ["PAR", "MAR"]}, {"FRANCE": ["A PIC - PAR"]})
    assert results == [("WAIVE", ResultCode.WAIVE)]  # the move is dropped; the owed build is waived
    assert {u.province for u in new_state.units} == {"PIC"}
