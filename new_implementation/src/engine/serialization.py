"""Canonical JSON (de)serialization for ``GameState``, ``Order`` and ``Resolution``.

One place — used by persistence, the HTTP API and DAIDE — turns the engine's frozen
value types into plain JSON-able dicts and back. Round-tripping is exact:
``state_from_dict(state_to_dict(s)) == s`` for every state the engine produces (a
Hypothesis property pins this).

Locations are encoded as their canonical string (``"PAR"`` / ``"SPA/SC"``); every
enum as its ``.value``; frozensets/tuples as JSON arrays. Decoding reconstructs the
exact frozen dataclasses, so value equality holds regardless of array order for the
set-valued fields (``units``, ``contested``).
"""

from __future__ import annotations

import json
from typing import Any

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
    Order,
    OrderResult,
    OrderType,
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

__all__ = [
    "location_to_str",
    "location_from_str",
    "unit_to_dict",
    "unit_from_dict",
    "order_to_dict",
    "order_from_dict",
    "state_to_dict",
    "state_from_dict",
    "resolution_to_dict",
    "resolution_from_dict",
    "to_json",
    "state_from_json",
    "order_from_json",
    "resolution_from_json",
]


# ---------------------------------------------------------------------------
# Location & Unit
# ---------------------------------------------------------------------------


def location_to_str(loc: Location) -> str:
    return str(loc)


def location_from_str(s: str) -> Location:
    if "/" in s:
        province, coast = s.split("/", 1)
        return Location(province, coast)
    return Location(s)


def unit_to_dict(unit: Unit) -> dict[str, Any]:
    return {
        "kind": unit.kind.value,
        "power": unit.power,
        "location": location_to_str(unit.location),
    }


def unit_from_dict(d: dict[str, Any]) -> Unit:
    return Unit(
        kind=UnitKind(d["kind"]),
        power=d["power"],
        location=location_from_str(d["location"]),
    )


def _dislodged_to_dict(du: DislodgedUnit) -> dict[str, Any]:
    return {
        "unit": unit_to_dict(du.unit),
        "attacker_origin": du.attacker_origin,
        "retreats": [location_to_str(loc) for loc in du.retreats],
    }


def _dislodged_from_dict(d: dict[str, Any]) -> DislodgedUnit:
    return DislodgedUnit(
        unit=unit_from_dict(d["unit"]),
        attacker_origin=d.get("attacker_origin"),
        retreats=tuple(location_from_str(s) for s in d.get("retreats", [])),
    )


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


def order_to_dict(order: Order) -> dict[str, Any]:
    d: dict[str, Any] = {"type": order.order_type.value, "power": order.power}
    if isinstance(order, Hold):
        d["unit"] = location_to_str(order.unit)
    elif isinstance(order, Move):
        d["unit"] = location_to_str(order.unit)
        d["dest"] = location_to_str(order.dest)
        d["via_convoy"] = order.via_convoy
    elif isinstance(order, SupportHold):
        d["unit"] = location_to_str(order.unit)
        d["target"] = location_to_str(order.target)
    elif isinstance(order, SupportMove):
        d["unit"] = location_to_str(order.unit)
        d["origin"] = location_to_str(order.origin)
        d["dest"] = location_to_str(order.dest)
    elif isinstance(order, Convoy):
        d["unit"] = location_to_str(order.unit)
        d["origin"] = location_to_str(order.origin)
        d["dest"] = location_to_str(order.dest)
    elif isinstance(order, Retreat):
        d["unit"] = location_to_str(order.unit)
        d["dest"] = location_to_str(order.dest)
    elif isinstance(order, Disband):
        d["unit"] = location_to_str(order.unit)
    elif isinstance(order, Build):
        d["location"] = location_to_str(order.location)
        d["kind"] = order.kind.value
    elif isinstance(order, Waive):
        pass
    else:  # pragma: no cover - defensive
        raise TypeError(f"cannot serialize order: {order!r}")
    return d


def order_from_dict(d: dict[str, Any]) -> Order:
    t = OrderType(d["type"])
    power = d["power"]
    if t is OrderType.HOLD:
        return Hold(power, location_from_str(d["unit"]))
    if t is OrderType.MOVE:
        return Move(
            power,
            location_from_str(d["unit"]),
            location_from_str(d["dest"]),
            via_convoy=d.get("via_convoy", False),
        )
    if t is OrderType.SUPPORT_HOLD:
        return SupportHold(power, location_from_str(d["unit"]), location_from_str(d["target"]))
    if t is OrderType.SUPPORT_MOVE:
        return SupportMove(
            power,
            location_from_str(d["unit"]),
            location_from_str(d["origin"]),
            location_from_str(d["dest"]),
        )
    if t is OrderType.CONVOY:
        return Convoy(
            power,
            location_from_str(d["unit"]),
            location_from_str(d["origin"]),
            location_from_str(d["dest"]),
        )
    if t is OrderType.RETREAT:
        return Retreat(power, location_from_str(d["unit"]), location_from_str(d["dest"]))
    if t is OrderType.DISBAND:
        return Disband(power, location_from_str(d["unit"]))
    if t is OrderType.BUILD:
        return Build(power, location_from_str(d["location"]), UnitKind(d["kind"]))
    if t is OrderType.WAIVE:
        return Waive(power)
    raise ValueError(f"unknown order type: {d['type']!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------


def state_to_dict(state: GameState) -> dict[str, Any]:
    return {
        "year": state.year,
        "season": state.season.value,
        "phase_type": state.phase_type.value,
        "units": [unit_to_dict(u) for u in state.units],
        "ownership": dict(state.ownership),
        "dislodged": [_dislodged_to_dict(du) for du in state.dislodged],
        "contested": sorted(state.contested),
        "status": state.status.value,
    }


def state_from_dict(d: dict[str, Any]) -> GameState:
    return GameState(
        year=d["year"],
        season=Season(d["season"]),
        phase_type=PhaseType(d["phase_type"]),
        units=frozenset(unit_from_dict(u) for u in d.get("units", [])),
        ownership=dict(d.get("ownership", {})),
        dislodged=tuple(_dislodged_from_dict(x) for x in d.get("dislodged", [])),
        contested=frozenset(d.get("contested", [])),
        status=GameStatus(d.get("status", GameStatus.ACTIVE.value)),
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _order_result_to_dict(r: OrderResult) -> dict[str, Any]:
    return {
        "order": order_to_dict(r.order),
        "result": r.result.value,
        "dislodged": r.dislodged,
        "retreat_options": [location_to_str(loc) for loc in r.retreat_options],
    }


def _order_result_from_dict(d: dict[str, Any]) -> OrderResult:
    return OrderResult(
        order=order_from_dict(d["order"]),
        result=ResultCode(d["result"]),
        dislodged=d.get("dislodged", False),
        retreat_options=tuple(location_from_str(s) for s in d.get("retreat_options", [])),
    )


def resolution_to_dict(resolution: Resolution) -> dict[str, Any]:
    return {"results": [_order_result_to_dict(r) for r in resolution.results]}


def resolution_from_dict(d: dict[str, Any]) -> Resolution:
    return Resolution(tuple(_order_result_from_dict(r) for r in d.get("results", [])))


# ---------------------------------------------------------------------------
# JSON convenience
# ---------------------------------------------------------------------------


def to_json(obj: GameState | Order | Resolution, **kwargs: Any) -> str:
    """Serialize a ``GameState``, ``Order`` or ``Resolution`` to a JSON string."""
    if isinstance(obj, GameState):
        payload = state_to_dict(obj)
    elif isinstance(obj, Resolution):
        payload = resolution_to_dict(obj)
    elif isinstance(obj, Order):
        payload = order_to_dict(obj)
    else:  # pragma: no cover - defensive
        raise TypeError(f"cannot serialize {type(obj).__name__} to JSON")
    return json.dumps(payload, **kwargs)


def state_from_json(s: str) -> GameState:
    return state_from_dict(json.loads(s))


def order_from_json(s: str) -> Order:
    return order_from_dict(json.loads(s))


def resolution_from_json(s: str) -> Resolution:
    return resolution_from_dict(json.loads(s))
