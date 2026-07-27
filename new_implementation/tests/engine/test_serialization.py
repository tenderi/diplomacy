"""M5 tests: canonical JSON round-trips for orders, states and resolutions."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from engine.serialization import (
    order_from_dict,
    order_from_json,
    order_to_dict,
    resolution_from_dict,
    resolution_to_dict,
    state_from_dict,
    state_from_json,
    state_to_dict,
    to_json,
)
from engine.types import (
    Build,
    Convoy,
    Disband,
    DislodgedUnit,
    GameState,
    GameStatus,
    Hold,
    Location,
    Move,
    OrderResult,
    PhaseType,
    Resolution,
    ResultCode,
    Retreat,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
    Waive,
)

_LOCS = [
    Location("PAR"),
    Location("BUR"),
    Location("BRE"),
    Location("SPA", "SC"),
    Location("STP", "NC"),
    Location("ENG"),
    Location("MAO"),
]


class TestOrderRoundTrip:
    @pytest.mark.parametrize(
        "order",
        [
            Hold("FRANCE", Location("PAR")),
            Move("FRANCE", Location("PAR"), Location("BUR")),
            Move("ENGLAND", Location("LON"), Location("BEL"), via_convoy=True),
            SupportHold("FRANCE", Location("BRE"), Location("PAR")),
            SupportMove("FRANCE", Location("BRE"), Location("PIC"), Location("BEL")),
            Convoy("ENGLAND", Location("NTH"), Location("LON"), Location("BEL")),
            Retreat("FRANCE", Location("PAR"), Location("GAS")),
            Disband("FRANCE", Location("PAR")),
            Build("FRANCE", Location("BRE"), UnitKind.FLEET),
            Build("RUSSIA", Location("STP", "NC"), UnitKind.FLEET),
            Build("FRANCE", Location("PAR"), UnitKind.ARMY),
            Waive("FRANCE"),
        ],
    )
    def test_order_dict_round_trip(self, order):
        assert order_from_dict(order_to_dict(order)) == order

    def test_order_json_round_trip(self):
        o = Move("ENGLAND", Location("LON"), Location("BEL"), via_convoy=True)
        assert order_from_json(to_json(o)) == o


class TestStateRoundTrip:
    def test_full_state_round_trip(self):
        state = GameState(
            year=1901,
            season=Season.FALL,
            phase_type=PhaseType.RETREAT,
            units=frozenset(
                {
                    Unit(UnitKind.ARMY, "FRANCE", Location("PAR")),
                    Unit(UnitKind.FLEET, "RUSSIA", Location("STP", "SC")),
                }
            ),
            ownership={"PAR": "FRANCE", "MOS": "RUSSIA"},
            dislodged=(
                DislodgedUnit(
                    Unit(UnitKind.ARMY, "GERMANY", Location("MUN")),
                    attacker_origin="TYR",
                    retreats=(Location("BER"), Location("KIE")),
                ),
            ),
            contested=frozenset({"BUR", "GAL"}),
            status=GameStatus.ACTIVE,
        )
        assert state_from_dict(state_to_dict(state)) == state
        assert state_from_json(to_json(state)) == state

    def test_empty_state_round_trip(self):
        state = GameState(1905, Season.WINTER, PhaseType.ADJUSTMENT)
        assert state_from_dict(state_to_dict(state)) == state


class TestResolutionRoundTrip:
    def test_resolution_round_trip(self):
        res = Resolution(
            (
                OrderResult(
                    order=Move("FRANCE", Location("PAR"), Location("BUR")),
                    result=ResultCode.OK,
                ),
                OrderResult(
                    order=Hold("GERMANY", Location("MUN")),
                    result=ResultCode.DISLODGED,
                    dislodged=True,
                    retreat_options=(Location("BER"), Location("KIE")),
                ),
            )
        )
        assert resolution_from_dict(resolution_to_dict(res)) == res


# -- Hypothesis property: any generated order round-trips exactly ------------

_provs = st.sampled_from([loc.province for loc in _LOCS])
_locs = st.sampled_from(_LOCS)


@st.composite
def _orders(draw):
    power = draw(st.sampled_from(["FRANCE", "GERMANY", "RUSSIA", "ENGLAND"]))
    kind = draw(
        st.sampled_from(
            [
                "hold",
                "move",
                "support_hold",
                "support_move",
                "convoy",
                "retreat",
                "disband",
                "build",
                "waive",
            ]
        )
    )
    if kind == "hold":
        return Hold(power, draw(_locs))
    if kind == "move":
        return Move(power, draw(_locs), draw(_locs), via_convoy=draw(st.booleans()))
    if kind == "support_hold":
        return SupportHold(power, draw(_locs), draw(_locs))
    if kind == "support_move":
        return SupportMove(power, draw(_locs), draw(_locs), draw(_locs))
    if kind == "convoy":
        return Convoy(power, draw(_locs), draw(_locs), draw(_locs))
    if kind == "retreat":
        return Retreat(power, draw(_locs), draw(_locs))
    if kind == "disband":
        return Disband(power, draw(_locs))
    if kind == "build":
        loc = draw(_locs)
        bk = UnitKind.ARMY if loc.coast is None and draw(st.booleans()) else UnitKind.FLEET
        return Build(power, loc, bk)
    return Waive(power)


@settings(max_examples=300, deadline=None)
@given(order=_orders())
def test_order_round_trip_property(order):
    assert order_from_dict(order_to_dict(order)) == order
    assert order_from_json(to_json(order)) == order
