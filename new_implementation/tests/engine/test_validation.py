"""M2 tests for the single order-validation path."""

from __future__ import annotations

import pytest

from engine.map_loader import load_standard_map
from engine.orders.validation import validate
from engine.types import (
    Build,
    Convoy,
    Disband,
    DislodgedUnit,
    GameState,
    Hold,
    Location,
    Move,
    PhaseType,
    Retreat,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
    Waive,
)

pytestmark = pytest.mark.map


@pytest.fixture(scope="module")
def m():
    return load_standard_map()


def _state(units, *, ownership=None, dislodged=(), phase_type=PhaseType.MOVEMENT):
    return GameState(
        1901,
        Season.SPRING,
        phase_type,
        units=frozenset(units),
        ownership=ownership or {},
        dislodged=tuple(dislodged),
    )


class TestBasicUnitChecks:
    def test_no_unit_at_location(self, m):
        state = _state([])
        order = Hold("FRANCE", Location("PAR"))
        result = validate(order, state, m)
        assert result.ok is False
        assert "no unit" in result.reason

    def test_wrong_power_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "GERMANY", Location("PAR"))])
        order = Hold("FRANCE", Location("PAR"))
        result = validate(order, state, m)
        assert result.ok is False
        assert "GERMANY" in result.reason

    def test_hold_ok(self, m):
        state = _state([Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))])
        order = Hold("FRANCE", Location("PAR"))
        assert validate(order, state, m).ok is True

    def test_coast_mismatch_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC"))])
        order = Hold("RUSSIA", Location("STP", "NC"))
        result = validate(order, state, m)
        assert result.ok is False


class TestMove:
    def test_adjacent_move_ok(self, m):
        state = _state([Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))])
        order = Move("FRANCE", Location("PAR"), Location("BUR"))
        assert validate(order, state, m).ok is True

    def test_non_adjacent_move_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))])
        order = Move("FRANCE", Location("PAR"), Location("MOS"))
        result = validate(order, state, m)
        assert result.ok is False
        assert "adjacent" in result.reason

    def test_fleet_into_split_coast_without_coast_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "RUSSIA", Location("BAR"))])
        order = Move("RUSSIA", Location("BAR"), Location("STP"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_fleet_into_split_coast_with_correct_coast_ok(self, m):
        state = _state([Unit(UnitKind.FLEET, "RUSSIA", Location("BAR"))])
        order = Move("RUSSIA", Location("BAR"), Location("STP", "NC"))
        assert validate(order, state, m).ok is True

    def test_army_via_convoy_between_coastal_provinces_ok(self, m):
        state = _state([Unit(UnitKind.ARMY, "ENGLAND", Location("LON"))])
        order = Move("ENGLAND", Location("LON"), Location("BEL"), via_convoy=True)
        assert validate(order, state, m).ok is True

    def test_fleet_may_not_move_via_convoy(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("NTH"))])
        order = Move("ENGLAND", Location("NTH"), Location("BEL"), via_convoy=True)
        result = validate(order, state, m)
        assert result.ok is False


class TestSupport:
    def test_support_hold_in_range_ok(self, m):
        state = _state(
            [
                Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
                Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            ]
        )
        order = SupportHold("FRANCE", Location("BUR"), Location("PAR"))
        assert validate(order, state, m).ok is True

    def test_support_hold_out_of_range_rejected(self, m):
        state = _state(
            [
                Unit(UnitKind.FLEET, "FRANCE", Location("BRE")),
                Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
            ]
        )
        order = SupportHold("FRANCE", Location("BRE"), Location("MUN"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_support_self_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))])
        order = SupportHold("FRANCE", Location("PAR"), Location("PAR"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_support_move_in_range_ok(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("NTH"))])
        order = SupportMove("ENGLAND", Location("NTH"), Location("PIC"), Location("BEL"))
        assert validate(order, state, m).ok is True

    def test_support_move_out_of_range_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "FRANCE", Location("BRE"))])
        order = SupportMove("FRANCE", Location("BRE"), Location("MOS"), Location("STP"))
        result = validate(order, state, m)
        assert result.ok is False


class TestConvoy:
    def test_convoy_ok(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("NTH"))])
        order = Convoy("ENGLAND", Location("NTH"), Location("LON"), Location("BEL"))
        assert validate(order, state, m).ok is True

    def test_convoy_by_army_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "ENGLAND", Location("YOR"))])
        order = Convoy("ENGLAND", Location("YOR"), Location("LON"), Location("BEL"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_convoy_noncoastal_endpoint_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "GERMANY", Location("BAL"))])
        order = Convoy("GERMANY", Location("BAL"), Location("MUN"), Location("BER"))
        result = validate(order, state, m)
        assert result.ok is False


class TestRetreat:
    def test_retreat_ok(self, m):
        du = DislodgedUnit(
            Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            retreats=(Location("BUR"), Location("GAS"), Location("PIC")),
        )
        state = _state([], dislodged=[du])
        order = Retreat("FRANCE", Location("PAR"), Location("BUR"))
        assert validate(order, state, m).ok is True

    def test_retreat_no_dislodged_unit_rejected(self, m):
        state = _state([])
        order = Retreat("FRANCE", Location("PAR"), Location("BUR"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_retreat_non_adjacent_rejected(self, m):
        du = DislodgedUnit(
            Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            retreats=(Location("BUR"), Location("GAS"), Location("PIC")),
        )
        state = _state([], dislodged=[du])
        order = Retreat("FRANCE", Location("PAR"), Location("MOS"))
        result = validate(order, state, m)
        assert result.ok is False


class TestDisband:
    def test_disband_retreat_phase(self, m):
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("PAR")))
        state = _state(
            [],
            dislodged=[du],
            phase_type=PhaseType.RETREAT,
        )
        order = Disband("FRANCE", Location("PAR"))
        assert validate(order, state, m).ok is True

    def test_disband_adjustment_phase(self, m):
        state = _state(
            [Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))],
            phase_type=PhaseType.ADJUSTMENT,
        )
        order = Disband("FRANCE", Location("PAR"))
        assert validate(order, state, m).ok is True


class TestBuild:
    def test_build_on_home_center_ok(self, m):
        state = _state([], ownership={"PAR": "FRANCE"})
        order = Build("FRANCE", Location("PAR"), UnitKind.ARMY)
        assert validate(order, state, m).ok is True

    def test_build_on_non_home_rejected(self, m):
        state = _state([], ownership={"BEL": "FRANCE"})
        order = Build("FRANCE", Location("BEL"), UnitKind.ARMY)
        result = validate(order, state, m)
        assert result.ok is False
        assert "home" in result.reason

    def test_build_on_occupied_center_rejected(self, m):
        state = _state(
            [Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))], ownership={"PAR": "FRANCE"}
        )
        order = Build("FRANCE", Location("PAR"), UnitKind.ARMY)
        result = validate(order, state, m)
        assert result.ok is False

    def test_build_fleet_needs_coast_on_split_coast_home(self, m):
        state = _state([], ownership={"STP": "RUSSIA"})
        order = Build("RUSSIA", Location("STP"), UnitKind.FLEET)
        result = validate(order, state, m)
        assert result.ok is False

    def test_build_fleet_with_coast_ok(self, m):
        state = _state([], ownership={"STP": "RUSSIA"})
        order = Build("RUSSIA", Location("STP", "SC"), UnitKind.FLEET)
        assert validate(order, state, m).ok is True

    def test_build_fleet_on_landlocked_rejected(self, m):
        state = _state([], ownership={"MOS": "RUSSIA"})
        order = Build("RUSSIA", Location("MOS"), UnitKind.FLEET)
        result = validate(order, state, m)
        assert result.ok is False


class TestWaive:
    def test_waive_always_ok(self, m):
        state = _state([])
        assert validate(Waive("FRANCE"), state, m).ok is True
