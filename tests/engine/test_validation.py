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


    @pytest.mark.parametrize(("origin", "dest", "inland"), [("MUN", "BEL", "MUN"), ("LON", "MUN", "MUN")])
    def test_a_convoyed_army_must_embark_and_land_on_a_coast(self, m, origin, dest, inland):
        state = _state([Unit(UnitKind.ARMY, "ENGLAND", Location(origin))])
        result = validate(Move("ENGLAND", Location(origin), Location(dest), via_convoy=True), state, m)
        assert result.ok is False
        assert result.reason.startswith(f"{inland} is not coastal")


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

    def test_convoy_to_an_inland_province_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("NTH"))])
        result = validate(Convoy("ENGLAND", Location("NTH"), Location("LON"), Location("MUN")), state, m)
        assert (result.ok, result.reason) == (False, "MUN is not a coastal province")

    def test_a_fleet_on_a_coast_cannot_convoy(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("LON"))])
        result = validate(Convoy("ENGLAND", Location("LON"), Location("YOR"), Location("BEL")), state, m)
        assert (result.ok, result.reason) == (False, "a convoying fleet must be in a sea space")


class TestRetreat:
    def test_retreat_ok(self, m):
        du = DislodgedUnit(
            Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            retreats=(Location("BUR"), Location("GAS"), Location("PIC")),
        )
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        order = Retreat("FRANCE", Location("PAR"), Location("BUR"))
        assert validate(order, state, m).ok is True

    def test_retreat_no_dislodged_unit_rejected(self, m):
        state = _state([], phase_type=PhaseType.RETREAT)
        order = Retreat("FRANCE", Location("PAR"), Location("BUR"))
        result = validate(order, state, m)
        assert result.ok is False
        assert "no dislodged unit" in result.reason

    def test_retreat_non_adjacent_rejected(self, m):
        du = DislodgedUnit(
            Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
            retreats=(Location("BUR"), Location("GAS"), Location("PIC")),
        )
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        order = Retreat("FRANCE", Location("PAR"), Location("MOS"))
        result = validate(order, state, m)
        assert result.ok is False

    def test_retreating_another_powers_unit_rejected(self, m):
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("PAR")), retreats=(Location("BUR"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(Retreat("GERMANY", Location("PAR"), Location("BUR")), state, m)
        assert (result.ok, result.reason) == (False, "unit at PAR belongs to FRANCE, not GERMANY")

    def test_a_fleet_retreating_to_a_split_coast_must_name_the_legal_coast(self, m):
        du = DislodgedUnit(Unit(UnitKind.FLEET, "RUSSIA", Location("BOT")), retreats=(Location("STP", "SC"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        bare = validate(Retreat("RUSSIA", Location("BOT"), Location("STP")), state, m)
        assert (bare.ok, bare.reason) == (False, "fleet retreat into split-coast STP must name a coast")
        assert validate(Retreat("RUSSIA", Location("BOT"), Location("STP", "NC")), state, m).ok is False
        assert validate(Retreat("RUSSIA", Location("BOT"), Location("STP", "SC")), state, m).ok is True


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

    @pytest.mark.parametrize("phase_type", [PhaseType.RETREAT, PhaseType.ADJUSTMENT])
    def test_disbanding_nothing_rejected(self, m, phase_type):
        state = _state([Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))], phase_type=phase_type)
        result = validate(Disband("FRANCE", Location("MAR")), state, m)
        assert (result.ok, result.reason) == (False, "no unit to disband at MAR")

    def test_disbanding_another_powers_unit_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "GERMANY", Location("MUN"))], phase_type=PhaseType.ADJUSTMENT)
        result = validate(Disband("FRANCE", Location("MUN")), state, m)
        assert (result.ok, result.reason) == (False, "unit at MUN belongs to GERMANY, not FRANCE")


class TestBuild:
    def _state(self, units, ownership):
        return _state(units, ownership=ownership, phase_type=PhaseType.ADJUSTMENT)

    def test_build_on_home_center_ok(self, m):
        state = self._state([], ownership={"PAR": "FRANCE"})
        order = Build("FRANCE", Location("PAR"), UnitKind.ARMY)
        assert validate(order, state, m).ok is True

    def test_build_on_non_home_rejected(self, m):
        state = self._state([], ownership={"BEL": "FRANCE"})
        order = Build("FRANCE", Location("BEL"), UnitKind.ARMY)
        result = validate(order, state, m)
        assert result.ok is False
        assert "home" in result.reason

    def test_build_on_occupied_center_rejected(self, m):
        state = self._state(
            [Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))], ownership={"PAR": "FRANCE"}
        )
        order = Build("FRANCE", Location("PAR"), UnitKind.ARMY)
        result = validate(order, state, m)
        assert result.ok is False
        assert "occupied" in result.reason

    def test_build_fleet_needs_coast_on_split_coast_home(self, m):
        state = self._state([], ownership={"STP": "RUSSIA"})
        order = Build("RUSSIA", Location("STP"), UnitKind.FLEET)
        result = validate(order, state, m)
        assert result.ok is False
        assert "coast" in result.reason

    def test_build_fleet_with_coast_ok(self, m):
        state = self._state([], ownership={"STP": "RUSSIA"})
        order = Build("RUSSIA", Location("STP", "SC"), UnitKind.FLEET)
        assert validate(order, state, m).ok is True

    def test_build_fleet_on_landlocked_rejected(self, m):
        state = self._state([], ownership={"MOS": "RUSSIA"})
        order = Build("RUSSIA", Location("MOS"), UnitKind.FLEET)
        result = validate(order, state, m)
        assert result.ok is False
        assert "landlocked" in result.reason

    def test_build_fleet_naming_a_coast_the_province_lacks_rejected(self, m):
        state = self._state([], ownership={"BRE": "FRANCE"})
        result = validate(Build("FRANCE", Location("BRE", "NC"), UnitKind.FLEET), state, m)
        assert (result.ok, result.reason) == (False, "BRE has no coasts to choose from")


class TestWaive:
    def test_waive_ok_in_adjustment(self, m):
        state = _state([], phase_type=PhaseType.ADJUSTMENT)
        assert validate(Waive("FRANCE"), state, m).ok is True


class TestPhaseGate:
    """An order whose kind has no meaning in the current phase is refused with
    a reason that names the phase -- *before* any unit/topology check, so the
    player is told why instead of having the adjudicator drop it silently."""

    PAR_ARMY = Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))

    @pytest.mark.parametrize(
        "order",
        [
            Hold("FRANCE", Location("PAR")),
            Move("FRANCE", Location("PAR"), Location("BUR")),
            SupportHold("FRANCE", Location("PAR"), Location("BUR")),
            SupportMove("FRANCE", Location("PAR"), Location("BUR"), Location("MUN")),
            Convoy("FRANCE", Location("PAR"), Location("BRE"), Location("LON")),
            Build("FRANCE", Location("PAR"), UnitKind.ARMY),
            Waive("FRANCE"),
        ],
    )
    def test_non_retreat_orders_refused_in_retreat_phase(self, m, order):
        # The unit really is there and the move really is adjacent: only the
        # phase is wrong, and that is what the reason must say.
        state = _state([self.PAR_ARMY], ownership={"PAR": "FRANCE"},
                       phase_type=PhaseType.RETREAT)
        result = validate(order, state, m)
        assert result.ok is False
        assert "retreat phase" in result.reason
        assert "S1901R" in result.reason

    @pytest.mark.parametrize(
        "order",
        [
            Retreat("FRANCE", Location("PAR"), Location("BUR")),
            Disband("FRANCE", Location("PAR")),
            Build("FRANCE", Location("BRE"), UnitKind.FLEET),
            Waive("FRANCE"),
        ],
    )
    def test_non_movement_orders_refused_in_movement_phase(self, m, order):
        # BRE is a vacant, owned home centre, so the build would otherwise pass;
        # PAR holds a French army, so the disband would otherwise pass.
        state = _state([self.PAR_ARMY], ownership={"PAR": "FRANCE", "BRE": "FRANCE"})
        result = validate(order, state, m)
        assert result.ok is False
        assert "movement phase" in result.reason
        assert "S1901M" in result.reason

    @pytest.mark.parametrize(
        "order",
        [
            Hold("FRANCE", Location("PAR")),
            Move("FRANCE", Location("PAR"), Location("BUR")),
            Retreat("FRANCE", Location("PAR"), Location("BUR")),
        ],
    )
    def test_movement_and_retreat_orders_refused_in_adjustment_phase(self, m, order):
        state = _state([self.PAR_ARMY], ownership={"PAR": "FRANCE"},
                       phase_type=PhaseType.ADJUSTMENT)
        result = validate(order, state, m)
        assert result.ok is False
        assert "adjustment phase" in result.reason
        assert "S1901A" in result.reason

    def test_reason_names_the_offending_order_kind(self, m):
        state = _state([self.PAR_ARMY], phase_type=PhaseType.RETREAT)
        result = validate(Move("FRANCE", Location("PAR"), Location("BUR")), state, m)
        assert result.reason.startswith("a move order is not accepted")

    def test_phase_is_checked_before_the_unit(self, m):
        # No unit anywhere: in the right phase that is the complaint; in the
        # wrong phase the phase is, because it is the thing the player can fix.
        empty = _state([], phase_type=PhaseType.ADJUSTMENT)
        result = validate(Hold("FRANCE", Location("PAR")), empty, m)
        assert "adjustment phase" in result.reason
        assert "no unit" not in result.reason
