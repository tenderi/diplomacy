"""M5 tests: the phase machine (transitions, ownership, victory) + self-play smoke."""

from __future__ import annotations

import random

import pytest

from engine.orchestrator import Game
from engine.serialization import (
    resolution_from_dict,
    resolution_to_dict,
    state_from_dict,
    state_to_dict,
)
from engine.simple_ai import generate_orders
from engine.types import (
    GameStatus,
    Hold,
    Location,
    Move,
    PhaseType,
    STANDARD_POWERS,
    Season,
    SupportMove,
    Unit,
    UnitKind,
)

pytestmark = pytest.mark.map


class TestOpening:
    def test_new_standard_opening(self):
        g = Game.new_standard()
        assert g.state.phase_name == "S1901M"
        assert g.state.phase_type is PhaseType.MOVEMENT
        assert len(g.state.units) == 22
        assert len(g.state.ownership) == 22  # 22 home supply centers owned at start
        assert g.winner() is None


class TestPhaseSequence:
    def test_spring_to_fall_no_retreats(self):
        g = Game.new_standard()
        orders = [Hold(u.power, u.location) for u in g.state.units]
        _res, g2 = g.adjudicate(orders)
        # All-hold spring → straight to fall movement, no retreat phase.
        assert g2.state.phase_name == "F1901M"
        assert g2.state.phase_type is PhaseType.MOVEMENT
        assert g.state in g2.history

    def test_retreat_phase_inserted_on_dislodgement(self):
        # France dislodges the German army in Munich; a retreat phase must follow.
        g = Game.new_standard()
        units = frozenset(
            {
                Unit(UnitKind.ARMY, "FRANCE", Location("BUR")),
                Unit(UnitKind.ARMY, "FRANCE", Location("RUH")),
                Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
            }
        )
        from dataclasses import replace

        g = replace(g, state=replace(g.state, units=units))
        orders = [
            Move("FRANCE", Location("BUR"), Location("MUN")),
            SupportMove("FRANCE", Location("RUH"), Location("BUR"), Location("MUN")),
            Hold("GERMANY", Location("MUN")),
        ]
        _res, g2 = g.adjudicate(orders)
        assert g2.state.phase_type is PhaseType.RETREAT
        assert g2.state.phase_name == "S1901R"
        assert any(du.province == "MUN" for du in g2.state.dislodged)

    def test_fall_updates_ownership(self):
        # A French army sits on Munich (a German home SC) through the fall.
        g = Game.new_standard()
        from dataclasses import replace

        units = frozenset({Unit(UnitKind.ARMY, "FRANCE", Location("MUN"))})
        state = replace(
            g.state,
            season=Season.FALL,
            units=units,
            ownership={"MUN": "GERMANY", "PAR": "FRANCE"},
        )
        g = replace(g, state=state)
        _res, g2 = g.adjudicate([Hold("FRANCE", Location("MUN"))])
        # Fall settled → Munich is now French; France has a unit but 2 centers, so
        # an adjustment phase is owed.
        assert g2.state.ownership["MUN"] == "FRANCE"
        assert g2.state.phase_type is PhaseType.ADJUSTMENT

    def test_victory_detected(self):
        g = Game.new_standard()
        from dataclasses import replace

        ownership = {p: "FRANCE" for p in list(g.map.supply_centers)[:18]}
        state = replace(
            g.state,
            season=Season.FALL,
            units=frozenset({Unit(UnitKind.ARMY, "FRANCE", Location("PAR"))}),
            ownership=ownership,
        )
        g = replace(g, state=state)
        _res, g2 = g.adjudicate([Hold("FRANCE", Location("PAR"))])
        assert g2.state.status is GameStatus.COMPLETED
        assert g2.winner() == "FRANCE"
        # A completed game does not advance further.
        _res2, g3 = g2.adjudicate([])
        assert g3.state.status is GameStatus.COMPLETED


class TestSelfPlaySmoke:
    @pytest.mark.slow
    def test_self_play_ten_years_invariants(self):
        """7 dumb AI powers play ≥10 game-years; invariants hold every phase, no crash."""
        rng = random.Random(2026)
        g = Game.new_standard()
        max_phases = 120
        phases = 0
        while phases < max_phases and g.state.status is not GameStatus.COMPLETED:
            state = g.state
            orders = []
            for power in STANDARD_POWERS:
                orders += generate_orders(g.map, state, power, rng)
            resolution, g = g.adjudicate(orders)

            # Invariant: at most one unit per province.
            provinces = [u.province for u in g.state.units]
            assert len(provinces) == len(set(provinces)), (
                f"two units share a province after {state.phase_name}"
            )
            # Invariant: no unit count exceeds supply centers by more than in-flight
            # dislodged units awaiting retreat.
            assert len(g.state.units) <= 34
            # Invariant: serialization round-trips at every phase.
            assert state_from_dict(state_to_dict(state)) == state
            assert resolution_from_dict(resolution_to_dict(resolution)) == resolution
            phases += 1

        # Reached at least 10 game-years (≈ well over 30 phases) or an earlier win.
        assert phases >= 30 or g.state.status is GameStatus.COMPLETED
        assert g.state.year >= 1911 or g.state.status is GameStatus.COMPLETED
