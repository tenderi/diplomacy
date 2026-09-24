"""The demo opponents' retreat orders (``simple_ai``): self-play rarely dislodges
anything, so this phase is pinned directly."""
from __future__ import annotations

import random

from engine.map_loader import load_standard_map
from engine.orders.validation import validate
from engine.simple_ai import generate_orders
from engine.types import Disband, DislodgedUnit, GameState, Location, PhaseType, Retreat, Season, Unit, UnitKind

_MAP = load_standard_map()


def _retreat_state() -> GameState:
    return GameState(
        1901, Season.SPRING, PhaseType.RETREAT,
        units=frozenset({Unit(UnitKind.ARMY, "GERMANY", Location("BUR"))}),
        dislodged=(
            DislodgedUnit(Unit(UnitKind.ARMY, "FRANCE", Location("PAR")), attacker_origin="BUR",
                          retreats=(Location("GAS"), Location("PIC"))),
            DislodgedUnit(Unit(UnitKind.FLEET, "FRANCE", Location("MAO")), retreats=()),
            DislodgedUnit(Unit(UnitKind.ARMY, "ITALY", Location("VEN")), retreats=(Location("TUS"),)),
        ),
    )


def test_each_dislodged_unit_retreats_to_a_legal_space_or_disbands_if_trapped() -> None:
    state = _retreat_state()
    for seed in range(20):
        orders = generate_orders(_MAP, state, "FRANCE", random.Random(seed))
        by_unit = {o.unit.province: o for o in orders}
        assert set(by_unit) == {"PAR", "MAO"}  # never ITALY's unit
        assert isinstance(by_unit["PAR"], Retreat) and by_unit["PAR"].dest.province in {"GAS", "PIC"}
        assert by_unit["MAO"] == Disband("FRANCE", Location("MAO"))
        assert all(validate(o, state, _MAP).ok for o in orders)


def test_a_power_with_nothing_dislodged_gives_no_retreat_orders() -> None:
    assert generate_orders(_MAP, _retreat_state(), "GERMANY", random.Random(0)) == []
