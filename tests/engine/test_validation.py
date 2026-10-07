"""M2 tests for the single order-validation path."""

from __future__ import annotations

import pytest

from engine.adjudicator.retreats import compute_retreat_options
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
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

    def test_fleet_move_to_a_split_coast_province_it_cannot_reach_is_not_adjacent(self, m):
        # ANK borders no coast of BUL: that is the problem, not a missing coast.
        state = _state([Unit(UnitKind.FLEET, "TURKEY", Location("ANK"))])
        result = validate(parse_order("F ANK - BUL", power="TURKEY", map=m), state, m)
        assert (result.ok, result.reason) == (False, "BUL is not adjacent to ANK")

    def test_fleet_move_to_the_only_reachable_coast_needs_no_coast(self, m):
        # BLA touches only BUL/EC (the adjudicator infers it, _move_dest_location).
        state = _state([Unit(UnitKind.FLEET, "TURKEY", Location("BLA"))])
        result = validate(parse_order("F BLA - BUL", power="TURKEY", map=m), state, m)
        assert (result.ok, result.reason) == (True, None)

    def test_fleet_move_with_two_reachable_coasts_must_name_one(self, m):
        state = _state([Unit(UnitKind.FLEET, "TURKEY", Location("CON"))])
        result = validate(parse_order("F CON - BUL", power="TURKEY", map=m), state, m)
        assert (result.ok, result.reason) == (
            False, "fleet move into split-coast BUL must name a coast (BUL/EC or BUL/SC)"
        )

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


    def test_army_convoyed_move_without_via_ok(self, m):
        """The rulebook writes a convoyed move as ``A Lon-Bel``: a non-adjacent
        army move between two coasts is convoyed, VIA or not (adjudication.md §6)."""
        state = _state([Unit(UnitKind.ARMY, "ENGLAND", Location("NWY"))])
        result = validate(Move("ENGLAND", Location("NWY"), Location("YOR")), state, m)
        assert (result.ok, result.reason) == (True, None)

    def test_non_adjacent_army_move_from_inland_still_rejected(self, m):
        state = _state([Unit(UnitKind.ARMY, "GERMANY", Location("MUN"))])
        result = validate(Move("GERMANY", Location("MUN"), Location("BEL")), state, m)
        assert (result.ok, result.reason) == (False, "BEL is not adjacent to MUN")

    def test_non_adjacent_fleet_move_still_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "ENGLAND", Location("LON"))])
        result = validate(Move("ENGLAND", Location("LON"), Location("BEL")), state, m)
        assert (result.ok, result.reason) == (False, "BEL is not adjacent to LON")

    @pytest.mark.parametrize("via", [False, True])
    def test_a_move_to_its_own_province_rejected(self, m, via):
        state = _state([Unit(UnitKind.ARMY, "ENGLAND", Location("LON"))])
        result = validate(Move("ENGLAND", Location("LON"), Location("LON"), via_convoy=via), state, m)
        assert (result.ok, result.reason) == (False, "LON cannot move to its own province")


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
        state = _state([
            Unit(UnitKind.FLEET, "ENGLAND", Location("NTH")),
            Unit(UnitKind.ARMY, "ENGLAND", Location("LON")),
        ])
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


    def test_convoy_of_a_fleet_rejected(self, m):
        """``F ION C A ALB - APU`` with an Austrian *fleet* in ALB used to be
        accepted, stored as ``F ION C F ALB - APU`` and 500 the whole batch."""
        state = _state([
            Unit(UnitKind.FLEET, "ITALY", Location("ION")),
            Unit(UnitKind.FLEET, "AUSTRIA", Location("ALB")),
        ])
        result = validate(Convoy("ITALY", Location("ION"), Location("ALB"), Location("APU")), state, m)
        assert (result.ok, result.reason) == (
            False, "the unit at ALB is a fleet; only an army can be convoyed"
        )

    def test_convoy_of_an_empty_province_rejected(self, m):
        state = _state([Unit(UnitKind.FLEET, "ITALY", Location("ION"))])
        result = validate(Convoy("ITALY", Location("ION"), Location("ALB"), Location("APU")), state, m)
        assert (result.ok, result.reason) == (False, "no army at ALB to convoy")

    def test_convoy_of_a_foreign_army_ok(self, m):
        state = _state([
            Unit(UnitKind.FLEET, "ITALY", Location("ION")),
            Unit(UnitKind.ARMY, "AUSTRIA", Location("ALB")),
        ])
        result = validate(Convoy("ITALY", Location("ION"), Location("ALB"), Location("APU")), state, m)
        assert (result.ok, result.reason) == (True, None)


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

    def test_a_fleet_retreating_to_a_split_coast_takes_the_only_reachable_coast(self, m):
        du = DislodgedUnit(Unit(UnitKind.FLEET, "RUSSIA", Location("BOT")), retreats=(Location("STP", "SC"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        bare = validate(Retreat("RUSSIA", Location("BOT"), Location("STP")), state, m)
        assert (bare.ok, bare.reason) == (True, None)
        wrong = validate(Retreat("RUSSIA", Location("BOT"), Location("STP", "NC")), state, m)
        assert (wrong.ok, wrong.reason) == (
            False, "STP/NC is not a legal retreat for F BOT: it is not adjacent to BOT"
        )
        assert validate(Retreat("RUSSIA", Location("BOT"), Location("STP", "SC")), state, m).ok is True

    def test_a_fleet_retreat_with_two_legal_coasts_must_name_one(self, m):
        fleet = Unit(UnitKind.FLEET, "TURKEY", Location("CON"))
        du = DislodgedUnit(fleet, "SMY", compute_retreat_options(m, fleet, "SMY", set(), set()))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("F CON R BUL", power="TURKEY", map=m), state, m)
        assert (result.ok, result.reason) == (
            False, "fleet retreat into split-coast BUL must name a coast (BUL/EC or BUL/SC)"
        )


class TestRetreatRefusalReasons:
    """A refused retreat says why. French A PAR was dislodged from BUR; a German
    army now stands in PIC and GAS stood off: only BRE is open."""

    ARMY = Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))

    @pytest.fixture
    def state(self, m):
        occupied = {"PIC"}
        contested = frozenset({"GAS"})
        du = DislodgedUnit(
            self.ARMY, "BUR", compute_retreat_options(m, self.ARMY, "BUR", occupied, contested)
        )
        assert du.retreats == (Location("BRE"),)
        return GameState(
            1901, Season.SPRING, PhaseType.RETREAT,
            units=frozenset({Unit(UnitKind.ARMY, "GERMANY", Location("PIC"))}),
            ownership={}, dislodged=(du,), contested=contested,
        )

    @pytest.mark.parametrize(
        "text,reason",
        [
            ("A PAR R BUR", "BUR is not a legal retreat for A PAR: "
             "the unit that dislodged it attacked from there"),
            ("A PAR R PIC", "PIC is not a legal retreat for A PAR: another unit stands there"),
            ("A PAR R GAS", "GAS is not a legal retreat for A PAR: "
             "a standoff left it empty this turn, and no unit may retreat there"),
            ("A PAR R MUN", "MUN is not a legal retreat for A PAR: it is not adjacent to PAR"),
            ("A PAR R BRE", None),
        ],
    )
    def test_reason(self, m, state, text, reason):
        result = validate(parse_order(text, power="FRANCE", map=m), state, m)
        assert (result.ok, result.reason) == (reason is None, reason)

    def test_a_retreat_missing_from_a_hand_made_legal_set_has_no_reason_to_give(self, m):
        du = DislodgedUnit(self.ARMY, "BUR", retreats=())
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(Retreat("FRANCE", Location("PAR"), Location("BRE")), state, m)
        assert (result.ok, result.reason) == (False, "BRE is not a legal retreat for A PAR")


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
        state = _state([], phase_type=PhaseType.ADJUSTMENT, ownership={"PAR": "FRANCE"})
        assert validate(Waive("FRANCE"), state, m).ok is True


class TestAdjustmentDirection:
    """A build or waive needs builds owed, a disband needs disbands owed: the
    adjudicator voids anything else, so validation refuses it up front."""

    PAR = Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))
    BUR = Unit(UnitKind.ARMY, "FRANCE", Location("BUR"))

    def test_build_and_waive_at_delta_zero_rejected(self, m):
        state = _state([self.BUR], ownership={"PAR": "FRANCE"}, phase_type=PhaseType.ADJUSTMENT)
        build = validate(Build("FRANCE", Location("PAR"), UnitKind.ARMY), state, m)
        assert (build.ok, build.reason) == (
            False, "FRANCE has no build to make (1 supply centre, 1 unit); it has no adjustment to make"
        )
        waive = validate(Waive("FRANCE"), state, m)
        assert (waive.ok, waive.reason) == (
            False, "FRANCE has no build to waive (1 supply centre, 1 unit); it has no adjustment to make"
        )

    def test_build_while_owing_disbands_rejected(self, m):
        state = _state([self.BUR, Unit(UnitKind.ARMY, "FRANCE", Location("PIC"))],
                       ownership={"PAR": "FRANCE"}, phase_type=PhaseType.ADJUSTMENT)
        result = validate(Build("FRANCE", Location("PAR"), UnitKind.ARMY), state, m)
        assert (result.ok, result.reason) == (
            False, "FRANCE has no build to make (1 supply centre, 2 units); it must disband 1 unit"
        )

    def test_disband_at_delta_zero_or_while_owed_builds_rejected(self, m):
        level = _state([self.BUR], ownership={"PAR": "FRANCE"}, phase_type=PhaseType.ADJUSTMENT)
        result = validate(Disband("FRANCE", Location("BUR")), level, m)
        assert (result.ok, result.reason) == (
            False, "FRANCE has no unit to disband (1 supply centre, 1 unit); it has no adjustment to make"
        )
        up = _state([self.BUR], ownership={"PAR": "FRANCE", "MAR": "FRANCE", "BRE": "FRANCE"},
                    phase_type=PhaseType.ADJUSTMENT)
        result = validate(Disband("FRANCE", Location("BUR")), up, m)
        assert (result.ok, result.reason) == (
            False, "FRANCE has no unit to disband (3 supply centres, 1 unit); it may build 2 units"
        )

    def test_retreat_phase_disband_is_not_counted(self, m):
        du = DislodgedUnit(self.PAR)
        state = _state([self.BUR], ownership={"PAR": "FRANCE"}, dislodged=[du], phase_type=PhaseType.RETREAT)
        assert validate(Disband("FRANCE", Location("PAR")), state, m).ok is True


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

    def test_a_move_by_a_dislodged_unit_hints_at_the_retreat_spelling(self, m):
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("BUR")), "PAR", (Location("RUH"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("A BUR - RUH", power="FRANCE", map=m), state, m)
        assert (result.ok, result.reason) == (
            False,
            "a move order is not accepted during the retreat phase (S1901R); "
            "to retreat, write A BUR R RUH",
        )

    def test_the_retreat_hint_never_suggests_an_illegal_retreat(self, m):
        # RUH is the attacker's origin, not a retreat; the hint lists the legal ones.
        du = DislodgedUnit(
            Unit(UnitKind.ARMY, "FRANCE", Location("BUR")), "RUH", (Location("MUN"), Location("PAR"))
        )
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("A BUR - RUH", power="FRANCE", map=m), state, m)
        assert (result.ok, result.reason) == (
            False,
            "a move order is not accepted during the retreat phase (S1901R); "
            "RUH is not a legal retreat; to retreat, write A BUR R <one of MUN, PAR>",
        )

    def test_the_retreat_hint_offers_disbanding_when_nothing_is_legal(self, m):
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("BUR")), "RUH", ())
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("A BUR - RUH", power="FRANCE", map=m), state, m)
        assert (result.ok, result.reason) == (
            False,
            "a move order is not accepted during the retreat phase (S1901R); "
            "it has no legal retreat; write D A BUR to disband",
        )

    def test_no_retreat_hint_for_another_powers_dislodged_unit(self, m):
        # Germany's army now stands where French A BUR was dislodged; telling
        # Germany to write "A BUR R RUH" would only earn an ownership error.
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("BUR")), "MUN", (Location("RUH"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("A BUR - RUH", power="GERMANY", map=m), state, m)
        assert result.ok is False
        assert result.reason.startswith(
            "a move order is not accepted during the retreat phase (S1901R); only "
        )

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


class TestWrittenUnitKind:
    """An order whose A/F letter is not the real unit's is refused, naming the unit."""

    ROM_ARMY = Unit(UnitKind.ARMY, "ITALY", Location("ROM"))

    @pytest.mark.parametrize("text", ["F ROM - TYS", "F ROM - VEN", "F ROM H", "F ROM S A VEN"])
    def test_a_fleet_order_for_an_army_names_the_army(self, m, text):
        result = validate(parse_order(text, power="ITALY", map=m), _state([self.ROM_ARMY]), m)
        assert (result.ok, result.reason) == (False, "the unit in ROM is an army, not a fleet")

    def test_an_army_order_for_a_fleet_names_the_fleet(self, m):
        state = _state([Unit(UnitKind.FLEET, "ITALY", Location("NAP"))])
        result = validate(parse_order("A NAP - ROM", power="ITALY", map=m), state, m)
        assert (result.ok, result.reason) == (False, "the unit in NAP is a fleet, not an army")

    def test_a_retreat_for_the_wrong_kind_is_refused(self, m):
        du = DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("BUR")), "RUH", (Location("PAR"),))
        state = _state([], dislodged=[du], phase_type=PhaseType.RETREAT)
        result = validate(parse_order("F BUR R PAR", power="FRANCE", map=m), state, m)
        assert (result.ok, result.reason) == (False, "the unit in BUR is an army, not a fleet")

    def test_the_right_kind_and_orders_built_in_code_pass(self, m):
        state = _state([self.ROM_ARMY])
        assert validate(parse_order("A ROM - VEN", power="ITALY", map=m), state, m).ok is True
        assert validate(Move("ITALY", Location("ROM"), Location("VEN")), state, m).ok is True
