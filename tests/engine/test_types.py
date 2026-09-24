"""M1 tests for the core value types: immutability, invariants, phase names."""

from __future__ import annotations

import dataclasses

import pytest

from engine.types import (
    GameState,
    Location,
    Move,
    PhaseType,
    Season,
    Unit,
    UnitKind,
)


def test_location_normalizes_case():
    loc = Location("spa", "sc")
    assert loc.province == "SPA"
    assert loc.coast == "SC"
    assert str(loc) == "SPA/SC"


def test_location_rejects_bad_coast():
    with pytest.raises(ValueError):
        Location("SPA", "ZZ")


def test_location_base_strips_coast():
    assert Location("STP", "NC").base == Location("STP", None)
    assert Location("PAR").base == Location("PAR")


def test_location_is_frozen():
    loc = Location("PAR")
    with pytest.raises(dataclasses.FrozenInstanceError):
        loc.province = "BUR"  # type: ignore[misc]


def test_location_hashable():
    assert len({Location("PAR"), Location("PAR"), Location("BUR")}) == 2


def test_army_may_not_carry_coast():
    with pytest.raises(ValueError):
        Unit(UnitKind.ARMY, "FRANCE", Location("SPA", "SC"))


def test_fleet_may_carry_coast():
    u = Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC"))
    assert u.province == "STP"
    assert str(u) == "F STP/SC"


def test_orders_are_frozen():
    mv = Move("FRANCE", Location("PAR"), Location("BUR"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        mv.dest = Location("GAS")  # type: ignore[misc]


def test_phase_name_movement():
    st = GameState(1901, Season.SPRING, PhaseType.MOVEMENT)
    assert st.phase_name == "S1901M"


def test_phase_name_retreat_and_adjustment():
    assert GameState(1901, Season.FALL, PhaseType.RETREAT).phase_name == "F1901R"
    assert GameState(1901, Season.WINTER, PhaseType.ADJUSTMENT).phase_name == "W1901A"


def test_gamestate_queries():
    units = frozenset({
        Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
        Unit(UnitKind.FLEET, "FRANCE", Location("BRE")),
        Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
    })
    st = GameState(
        1901, Season.SPRING, PhaseType.MOVEMENT, units=units,
        ownership={"PAR": "FRANCE", "BRE": "FRANCE", "MUN": "GERMANY"},
    )
    assert len(st.units_of("FRANCE")) == 2
    assert st.unit_at("PAR").kind is UnitKind.ARMY
    assert st.unit_at("LON") is None
    assert st.centers_of("FRANCE") == frozenset({"PAR", "BRE"})
