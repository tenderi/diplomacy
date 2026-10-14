"""BJ1: how a retreat phase reports the units it removes.

A chosen ``D A MUN`` is a plain ``DISBAND``. Two retreats into one province both
``BOUNCE`` (each unit is removed all the same), and a unit left without an order
while it had somewhere to go is a ``DISBAND`` marked ``civil_disorder`` that keeps
the retreats it had -- so neither reads like a disband its power chose. A trapped
unit (no retreat at all) is a plain ``DISBAND``: no order could have saved it.
"""
from __future__ import annotations

from engine.adjudicator.retreats import adjudicate_retreats
from engine.map_loader import load_standard_map
from engine.orders.parser import parse_order
from engine.serialization import resolution_from_dict, resolution_to_dict
from engine.types import (
    Disband,
    DislodgedUnit,
    GameState,
    Location,
    OrderResult,
    PhaseType,
    Resolution,
    ResultCode,
    Retreat,
    Season,
    Unit,
    UnitKind,
)

_MAP = load_standard_map()
_VIE = Unit(UnitKind.ARMY, "AUSTRIA", Location("VIE"))


def _dislodged(power: str, prov: str, retreats: list[str]) -> DislodgedUnit:
    return DislodgedUnit(
        unit=Unit(UnitKind.ARMY, power, Location(prov)),
        attacker_origin=None,
        retreats=tuple(Location(p) for p in retreats),
    )


def _resolve() -> tuple[Resolution, GameState]:
    state = GameState(
        year=1901,
        season=Season.SPRING,
        phase_type=PhaseType.RETREAT,
        units=frozenset({_VIE}),
        dislodged=(
            _dislodged("FRANCE", "MAR", ["PIE", "GAS"]),
            _dislodged("ITALY", "VEN", ["PIE", "TUS"]),
            _dislodged("RUSSIA", "WAR", ["LVN", "UKR"]),
            _dislodged("GERMANY", "MUN", ["KIE"]),
            _dislodged("TURKEY", "SMY", []),
        ),
    )
    orders = [
        parse_order("A MAR R PIE", power="FRANCE", map=_MAP),
        parse_order("A VEN R PIE", power="ITALY", map=_MAP),
        parse_order("D A MUN", power="GERMANY", map=_MAP),
    ]
    return adjudicate_retreats(_MAP, state, orders)


def test_each_removal_says_why_it_happened() -> None:
    resolution, new_state = _resolve()
    assert list(resolution.results) == [
        OrderResult(Retreat("FRANCE", Location("MAR"), Location("PIE")), ResultCode.BOUNCE),
        OrderResult(Retreat("ITALY", Location("VEN"), Location("PIE")), ResultCode.BOUNCE),
        OrderResult(
            Disband("RUSSIA", Location("WAR")),
            ResultCode.DISBAND,
            retreat_options=(Location("LVN"), Location("UKR")),
            civil_disorder=True,
        ),
        OrderResult(Disband("GERMANY", Location("MUN")), ResultCode.DISBAND),
        OrderResult(Disband("TURKEY", Location("SMY")), ResultCode.DISBAND),
    ]
    # Every dislodged unit is gone; only the unit that was never dislodged stays.
    assert new_state.units == frozenset({_VIE})


def test_the_marks_survive_serialization() -> None:
    resolution, _ = _resolve()
    as_dict = resolution_to_dict(resolution)
    assert [(r["result"], r["civil_disorder"], r["retreat_options"]) for r in as_dict["results"]] == [
        ("BOUNCE", False, []),
        ("BOUNCE", False, []),
        ("DISBAND", True, ["LVN", "UKR"]),
        ("DISBAND", False, []),
        ("DISBAND", False, []),
    ]
    assert resolution_from_dict(as_dict) == resolution


def test_a_result_stored_before_the_marks_still_reads() -> None:
    # A retreat result persisted before BJ1 has no ``civil_disorder`` key at all.
    old = {
        "results": [
            {
                "order": {"type": "DISBAND", "power": "RUSSIA", "unit": "WAR"},
                "result": "DISBAND",
                "dislodged": False,
                "retreat_options": [],
            }
        ]
    }
    assert resolution_from_dict(old).results == (
        OrderResult(Disband("RUSSIA", Location("WAR")), ResultCode.DISBAND),
    )
