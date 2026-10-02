"""Adapt engine ``Order``/``Resolution`` data into the renderer's order dicts.

``rendering.overlays`` draws from a ``{power: [order_dict]}`` structure. Every dict
carries the unit's own province (``province``), so each marker is drawn on the unit
that gave the order, plus the outcome:

    {"type": "move", "unit": "A PAR", "province": "PAR", "target": "BUR",
     "result": "ok", "dislodged": False, "status": "success", "convoy_chain": []}

- ``result`` is the engine's ``ResultCode`` in lower case (``ok``, ``bounce``,
  ``cut``, ``void``, ``no_convoy``, ``dislodged``, ``disband``, ``build``), or
  ``pending`` for an order not yet adjudicated.
- ``dislodged`` is ``OrderResult.dislodged``: the unit was knocked out *whatever*
  its own order did. A move that bounced and was then dislodged is ``bounce`` and
  dislodged; reading only the result code drew such a unit as a plain bounce.
- ``status`` is the coarse ``success``/``bounced``/``failed``/``dislodged``/
  ``pending`` word kept for callers that only want pass/fail.

Convoys: the army's ``Move`` carries ``convoy_chain``, the fleets convoying it on
that route, so the move is drawn *through* them; each fleet's ``Convoy`` order is
still its own entry (it is marked on its own fleet, and may be dislodged on its
own). A chain whose army never ordered the move is drawn by its convoys alone.

This module lives in ``rendering`` (not ``engine``) to keep the engine free of
display concerns.
"""
from __future__ import annotations

from typing import Any, Optional

from engine.serialization import order_from_dict
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Move,
    Order,
    Retreat,
    ResultCode,
    SupportHold,
    SupportMove,
)

_STATUS_BY_RESULT: dict[str, str] = {
    "pending": "pending",
    "ok": "success",
    "build": "success",
    "waive": "success",
    "disband": "success",
    "bounce": "bounced",
    "cut": "failed",
    "void": "failed",
    "no_convoy": "failed",
    "dislodged": "dislodged",
}


def _unit_label(province: str, kind_by_province: Optional[dict[str, str]]) -> str:
    """``"A PAR"``/``"F BRE"``. Placement uses only the province; the letter falls
    back to ``A`` when unknown."""
    return f"{(kind_by_province or {}).get(province, 'A')} {province}"


def order_to_viz(
    order: Order,
    result: str = "pending",
    kind_by_province: Optional[dict[str, str]] = None,
    *,
    dislodged: bool = False,
) -> Optional[dict[str, Any]]:
    """One ``Order`` as a renderer order dict, or ``None`` if it draws nothing (a waive)."""
    base: dict[str, Any] = {
        "power": order.power,
        "result": result,
        "status": _STATUS_BY_RESULT.get(result, "failed"),
        "dislodged": dislodged,
    }
    if isinstance(order, Build):
        return {**base, "type": "build", "unit": "", "province": order.location.province,
                "target": order.location.province, "unit_kind": order.kind.value}
    unit = getattr(order, "unit", None)
    if unit is None:  # Waive, and any future order with nothing to draw
        return None
    unit_province = unit.province
    base |= {"unit": _unit_label(unit_province, kind_by_province), "province": unit_province}
    if isinstance(order, Move):
        return {**base, "type": "move", "target": order.dest.province,
                "via_convoy": order.via_convoy, "convoy_chain": []}
    if isinstance(order, Hold):
        return {**base, "type": "hold"}
    if isinstance(order, SupportHold):
        return {**base, "type": "support", "supported_action": "hold",
                "supported_unit_province": order.target.province}
    if isinstance(order, SupportMove):
        return {**base, "type": "support", "supported_action": "move",
                "supported_unit_province": order.origin.province, "supported_target": order.dest.province}
    if isinstance(order, Convoy):
        return {**base, "type": "convoy", "convoyed_army_province": order.origin.province,
                "target": order.dest.province, "convoy_chain": [unit_province]}
    if isinstance(order, Retreat):
        return {**base, "type": "retreat", "target": order.dest.province}
    if isinstance(order, Disband):
        return {**base, "type": "destroy"}
    return None  # pragma: no cover - every unit order is handled above


def _to_viz(
    entries: list[tuple[Order, str, bool]], kind_by_province: Optional[dict[str, str]],
) -> dict[str, list[dict[str, Any]]]:
    """Translate ``(order, result, dislodged)`` triples and wire up convoy chains."""
    out: dict[str, list[dict[str, Any]]] = {}
    chains: dict[tuple[str, str], list[str]] = {}
    for order, _, _ in entries:
        if isinstance(order, Convoy):
            chains.setdefault((order.origin.province, order.dest.province), []).append(order.unit.province)
    for order, result, dislodged in entries:
        viz = order_to_viz(order, result, kind_by_province, dislodged=dislodged)
        if viz is None:
            continue
        key = (viz.get("province", ""), viz.get("target", ""))
        if viz["type"] == "move" and viz["via_convoy"] and key in chains:
            viz["convoy_chain"] = list(chains[key])
        if viz["type"] == "convoy":
            viz["convoy_chain"] = list(chains[(viz["convoyed_army_province"], viz["target"])])
        out.setdefault(order.power, []).append(viz)
    return out


def orders_by_power_to_viz(
    orders_by_power: dict[str, list[Order]],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Orders not yet adjudicated → renderer structure (every result ``pending``)."""
    entries = [(o, "pending", False) for orders in orders_by_power.values() for o in orders]
    return _to_viz(entries, kind_by_province)


def resolution_dict_to_viz(
    resolution: dict[str, Any],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """A persisted ``resolution_to_dict`` → renderer structure, each entry carrying
    its result and whether its unit was dislodged."""
    entries = [
        (order_from_dict(r["order"]), ResultCode(r["result"]).value.lower(), bool(r.get("dislodged", False)))
        for r in resolution.get("results", [])
    ]
    return _to_viz(entries, kind_by_province)


def standoff_provinces(resolution: dict[str, Any]) -> list[str]:
    """Provinces where a standoff happened: two or more moves into them, none of which
    succeeded. Read from the persisted resolution, because the engine keeps its own
    ``contested`` set only through a retreat phase -- after an ordinary turn it is
    already empty, and the resolution map lost every standoff (Spring 1901's PAR/MUN
    bounce in BUR among them)."""
    moves_by_dest: dict[str, list[ResultCode]] = {}
    for result_dict in resolution.get("results", []):
        order = order_from_dict(result_dict["order"])
        if isinstance(order, Move):
            moves_by_dest.setdefault(order.dest.province, []).append(ResultCode(result_dict["result"]))
    return sorted(
        dest for dest, codes in moves_by_dest.items()
        if len(codes) >= 2 and ResultCode.OK not in codes
    )
