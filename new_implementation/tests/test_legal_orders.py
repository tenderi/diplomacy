"""Tests for ``server.legal_orders`` — phase-aware legal order enumeration.

Pure engine + module tests: no DB, no FastAPI app, no fixtures beyond the
bundled standard map. Builds ``GameState``s directly (movement, retreat,
build, disband) the same way ``tests/datc`` does, using the ``Harness``
helper for the retreat case so the dislodgement and its precomputed
``DislodgedUnit.retreats`` come from a real ``adjudicate_movement`` run
rather than being hand-rolled.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.orders.validation import validate
from engine.types import (
    GameState,
    Location,
    PhaseType,
    Season,
    Unit,
    UnitKind,
)
from server.legal_orders import legal_orders_for_power
from tests.datc.harness import Harness

pytestmark = pytest.mark.unit

_MAP = load_standard_map()


def _assert_all_orders_valid(map_, state: GameState, power: str) -> dict:
    data = legal_orders_for_power(map_, state, power)
    for s in data["orders"]:
        order = parse_order(s, power=power, map=map_)
        vr = validate(order, state, map_)
        assert vr.ok, f"{power}: emitted order {s!r} failed validate(): {vr.reason}"
    for key, bucket in data["orders_by_unit"].items():
        for s in bucket:
            order = parse_order(s, power=power, map=map_)
            vr = validate(order, state, map_)
            assert vr.ok, f"{power}: {key} order {s!r} failed validate(): {vr.reason}"
    return data


def _initial_movement_state() -> GameState:
    return GameState(
        year=_MAP.start_year,
        season=_MAP.start_season,
        phase_type=PhaseType.MOVEMENT,
        units=_MAP.starting_units,
        ownership=dict(_MAP.initial_ownership),
    )


def _retreat_state() -> GameState:
    """A retreat-phase state: France's army at Picardy dislodged by Germany.

    ``adjudicate_movement`` alone leaves ``phase_type`` at MOVEMENT — the
    MOVEMENT -> RETREAT transition happens one level up, in
    ``Game._transition`` (``engine/game.py``: ``replace(post,
    phase_type=PhaseType.RETREAT)`` when ``post.dislodged`` is non-empty).
    Reproduce that same transition here so the state handed to
    ``legal_orders_for_power`` looks exactly like a real retreat phase.
    """
    h = Harness()
    h.units("FRANCE", "A PIC")
    h.units("GERMANY", "A BEL", "A BUR")
    h.orders("FRANCE", "A PIC H")
    h.orders("GERMANY", "A BEL S A BUR - PIC", "A BUR - PIC")
    h.adjudicate()
    assert h.dislodged_provinces() == {"PIC"}
    assert h.new_state is not None
    return replace(h.new_state, phase_type=PhaseType.RETREAT)


def _build_state() -> GameState:
    """France: 3 home centers owned, 1 unit on board -> delta = +2."""
    return GameState(
        year=1901,
        season=Season.WINTER,
        phase_type=PhaseType.ADJUSTMENT,
        units=frozenset({Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))}),
        ownership=dict(_MAP.initial_ownership),
    )


def _disband_state() -> GameState:
    """France: 3 home centers owned, 4 units on board -> delta = -1."""
    return GameState(
        year=1901,
        season=Season.WINTER,
        phase_type=PhaseType.ADJUSTMENT,
        units=frozenset(
            {
                Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
                Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
                Unit(UnitKind.FLEET, "FRANCE", Location("BRE")),
                Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
            }
        ),
        ownership=dict(_MAP.initial_ownership),
    )


def _balanced_state() -> GameState:
    """France: 3 home centers owned, 3 units on board -> delta = 0."""
    return GameState(
        year=1901,
        season=Season.WINTER,
        phase_type=PhaseType.ADJUSTMENT,
        units=frozenset(
            {
                Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
                Unit(UnitKind.ARMY, "FRANCE", Location("MAR")),
                Unit(UnitKind.FLEET, "FRANCE", Location("BRE")),
            }
        ),
        ownership=dict(_MAP.initial_ownership),
    )


# ---------------------------------------------------------------------------
# 1. The property test that carries this PR.
# ---------------------------------------------------------------------------


class TestEmittedOrdersAlwaysValidate:
    def test_movement_state_all_powers(self) -> None:
        state = _initial_movement_state()
        for power in sorted({u.power for u in state.units}):
            _assert_all_orders_valid(_MAP, state, power)

    def test_retreat_state_all_powers(self) -> None:
        state = _retreat_state()
        for power in sorted({u.power for u in state.units} | {du.power for du in state.dislodged}):
            _assert_all_orders_valid(_MAP, state, power)

    def test_build_state(self) -> None:
        _assert_all_orders_valid(_MAP, _build_state(), "FRANCE")

    def test_disband_state(self) -> None:
        _assert_all_orders_valid(_MAP, _disband_state(), "FRANCE")


# ---------------------------------------------------------------------------
# 2. Retreat phase: only R/D forms, destinations match DislodgedUnit.retreats.
# ---------------------------------------------------------------------------


class TestRetreatPhase:
    def test_only_retreat_and_disband_forms(self) -> None:
        state = _retreat_state()
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        for s in data["orders"]:
            verb_ok = " R " in s or s.startswith("D ")
            assert verb_ok, f"unexpected non-retreat/disband order in retreat phase: {s!r}"

    def test_destinations_match_precomputed_retreats(self) -> None:
        state = _retreat_state()
        du = state.dislodged_at("PIC")
        assert du is not None
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        emitted_dests = {
            s.split(" R ")[1] for s in data["orders"] if " R " in s
        }
        expected_dests = {str(loc) for loc in du.retreats}
        assert emitted_dests == expected_dests

    def test_disband_offered_for_dislodged_unit(self) -> None:
        state = _retreat_state()
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        assert "D A PIC" in data["orders"]

    def test_units_field_reflects_dislodged_unit(self) -> None:
        state = _retreat_state()
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        assert data["units"] == [
            {"kind": "A", "location": "PIC", "province": "PIC", "coast": None}
        ]


# ---------------------------------------------------------------------------
# 3. Adjustment phase: builds/waive vs disbands vs nothing.
# ---------------------------------------------------------------------------


class TestAdjustmentPhase:
    def test_delta_positive_offers_builds_and_waive_no_disband(self) -> None:
        data = legal_orders_for_power(_MAP, _build_state(), "FRANCE")
        assert data["adjustment"] == {"delta": 2, "action": "build", "slots": 2}
        assert "WAIVE" in data["orders"]
        assert any(o.startswith("BUILD ") for o in data["orders"])
        assert not any(o.startswith("D ") for o in data["orders"])

    def test_delta_negative_offers_only_disbands(self) -> None:
        data = legal_orders_for_power(_MAP, _disband_state(), "FRANCE")
        assert data["adjustment"] == {"delta": -1, "action": "disband", "slots": 1}
        assert data["orders"], "expected disband candidates"
        assert all(o.startswith("D ") for o in data["orders"])
        assert "WAIVE" not in data["orders"]
        assert not any(o.startswith("BUILD ") for o in data["orders"])
        # one D candidate per unit actually on the board
        assert set(data["orders"]) == {
            "D A PAR",
            "D A MAR",
            "D F BRE",
            "D A BUR",
        }

    def test_delta_zero_offers_nothing(self) -> None:
        data = legal_orders_for_power(_MAP, _balanced_state(), "FRANCE")
        assert data["adjustment"] == {"delta": 0, "action": "none", "slots": 0}
        assert data["orders"] == []
        assert data["orders_by_unit"] == {}

    def test_split_coast_home_center_offers_both_coasts(self) -> None:
        """Russia with no units on board: St. Petersburg is a split-coast home
        center, so builds should offer an army and a fleet on each coast."""
        state = GameState(
            year=1901,
            season=Season.WINTER,
            phase_type=PhaseType.ADJUSTMENT,
            units=frozenset(),
            ownership=dict(_MAP.initial_ownership),
        )
        data = _assert_all_orders_valid(_MAP, state, "RUSSIA")
        assert data["adjustment"]["action"] == "build"
        assert "BUILD A STP" in data["orders"]
        assert "BUILD F STP/NC" in data["orders"]
        assert "BUILD F STP/SC" in data["orders"]
        assert "F STP/NC" in data["orders_by_unit"]
        assert "F STP/SC" in data["orders_by_unit"]
        assert "A STP" in data["orders_by_unit"]


# ---------------------------------------------------------------------------
# 4. Coast regression: STP/SC must not leak STP/NC-only destinations.
# ---------------------------------------------------------------------------


class TestCoastRegression:
    def test_fleet_at_split_coast_uses_its_own_coast_adjacency(self) -> None:
        unit = Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC"))
        state = GameState(
            year=1901,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=frozenset({unit}),
            ownership=dict(_MAP.initial_ownership),
        )
        data = legal_orders_for_power(_MAP, state, "RUSSIA")
        moves = {o for o in data["orders"] if o.startswith("F STP/SC - ")}
        move_dests = {o.split(" - ")[1] for o in moves}
        expected = {str(loc) for loc in _MAP.fleet_moves(Location("STP", "SC"))}
        assert move_dests == expected
        # STP/NC-only destinations must not appear via this coast.
        nc_only = {
            str(loc)
            for loc in _MAP.fleet_moves(Location("STP", "NC"))
        } - expected
        assert nc_only, "test fixture assumption: NC and SC should differ"
        assert not (move_dests & nc_only)


# ---------------------------------------------------------------------------
# 5. orders_by_unit key invariant.
# ---------------------------------------------------------------------------


class TestOrdersByUnitKeyInvariant:
    def _check(self, data: dict) -> None:
        """Every key is ``f"{kind} {location}"`` and every string in its bucket
        names that unit.

        For Hold/Move/Support/Convoy/Retreat orders the canonical grammar puts
        the unit first, so the string starts with the key (as the brief
        states). ``Disband``/``Build`` are verb-first in the engine's own
        grammar (``format_order`` renders ``"D A PAR"`` / ``"BUILD F BRE"``) —
        for those the key can only match as a suffix, not a prefix. Accepting
        either keeps the invariant meaningful (the key's exact text names the
        unit the order acts on) without asserting something the canonical
        grammar cannot satisfy.
        """
        for key, bucket in data["orders_by_unit"].items():
            parts = key.split(" ")
            assert len(parts) == 2, f"malformed key: {key!r}"
            assert parts[0] in ("A", "F"), f"malformed key kind: {key!r}"
            for s in bucket:
                assert s.startswith(key) or s.endswith(key), (
                    f"order {s!r} does not name its key {key!r}"
                )

    def test_movement(self) -> None:
        state = _initial_movement_state()
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        self._check(data)
        # Fleet key carries its coast.
        stp_state = GameState(
            year=1901,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=frozenset({Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC"))}),
            ownership=dict(_MAP.initial_ownership),
        )
        stp_data = legal_orders_for_power(_MAP, stp_state, "RUSSIA")
        self._check(stp_data)
        assert "F STP/SC" in stp_data["orders_by_unit"]
        assert "F STP" not in stp_data["orders_by_unit"]

    def test_retreat(self) -> None:
        state = _retreat_state()
        data = legal_orders_for_power(_MAP, state, "FRANCE")
        self._check(data)

    def test_build_and_disband(self) -> None:
        self._check(legal_orders_for_power(_MAP, _build_state(), "FRANCE"))
        self._check(legal_orders_for_power(_MAP, _disband_state(), "FRANCE"))


# ---------------------------------------------------------------------------
# 6. format_order fleet-letter trap: fleets at non-split provinces emit "F".
# ---------------------------------------------------------------------------


class TestFleetLetterTrap:
    @pytest.mark.parametrize("province", ["BRE", "LON"])
    def test_fleet_at_non_split_province_emits_f(self, province: str) -> None:
        unit = Unit(UnitKind.FLEET, "FRANCE", Location(province))
        state = GameState(
            year=1901,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=frozenset({unit}),
            ownership=dict(_MAP.initial_ownership),
        )
        data = legal_orders_for_power(_MAP, state, unit.power)
        assert data["orders"], f"expected some orders for a fleet at {province}"
        for s in data["orders"]:
            assert s.startswith(f"F {province}"), (
                f"fleet at {province} emitted a non-'F'-prefixed order: {s!r}"
            )
        assert not any(s.startswith(f"A {province}") for s in data["orders"])
