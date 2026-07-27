"""Adapt engine ``Order``/``Resolution`` data into the renderer's order-dict format.

``rendering.map.Map._draw_comprehensive_order_visualization`` draws move/support/
convoy/hold/retreat/build/destroy arrows from a ``{power: [order_dict]}`` structure
whose per-order dicts look like::

    {"type": "move",    "unit": "A PAR", "target": "BUR", "status": "success"}
    {"type": "support", "unit": "F BRE", "supported_action": "move",
     "supported_unit_province": "PIC", "supported_target": "BEL", "status": "success"}

The new engine speaks in frozen ``Order`` dataclasses (locations only, no A/F letter)
and ``OrderResult`` codes, so this module is the single translation point between the
two. It lives in ``rendering`` (not ``engine``) to keep the engine free of display
concerns.
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
    OrderResult,
    Retreat,
    ResultCode,
    SupportHold,
    SupportMove,
)

# ResultCode → the status string the renderer styles arrows by.
_STATUS_BY_CODE: dict[ResultCode, str] = {
    ResultCode.OK: "success",
    ResultCode.BOUNCE: "bounced",
    ResultCode.CUT: "failed",
    ResultCode.VOID: "failed",
    ResultCode.NO_CONVOY: "failed",
    ResultCode.DISLODGED: "success",
    ResultCode.DISBAND: "success",
    ResultCode.BUILD: "success",
    ResultCode.WAIVE: "success",
}


def _unit_label(province: str, kind_by_province: Optional[dict[str, str]]) -> str:
    """``"A PAR"``/``"F BRE"`` for the renderer. Only the province is used for
    placement; the A/F letter is cosmetic, so fall back to ``A`` when unknown."""
    kind = (kind_by_province or {}).get(province, "A")
    return f"{kind} {province}"


def order_to_viz(
    order: Order,
    status: str = "success",
    kind_by_province: Optional[dict[str, str]] = None,
) -> Optional[dict[str, Any]]:
    """Translate one ``Order`` into a renderer order-dict, or ``None`` if it draws
    nothing (a waive)."""
    if isinstance(order, Move):
        return {
            "type": "move",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "target": order.dest.province,
            "status": status,
        }
    if isinstance(order, Hold):
        return {
            "type": "hold",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "status": status,
        }
    if isinstance(order, SupportHold):
        return {
            "type": "support",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "supported_action": "hold",
            "supported_unit_province": order.target.province,
            "status": status,
        }
    if isinstance(order, SupportMove):
        return {
            "type": "support",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "supported_action": "move",
            "supported_unit_province": order.origin.province,
            "supported_target": order.dest.province,
            "status": status,
        }
    if isinstance(order, Convoy):
        return {
            "type": "convoy",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "convoyed_army_province": order.origin.province,
            "target": order.dest.province,
            "convoy_chain": [order.unit.province],
            "status": status,
        }
    if isinstance(order, Retreat):
        return {
            "type": "retreat",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "target": order.dest.province,
            "status": status,
        }
    if isinstance(order, Disband):
        return {
            "type": "destroy",
            "unit": _unit_label(order.unit.province, kind_by_province),
            "status": status,
        }
    if isinstance(order, Build):
        return {
            "type": "build",
            "unit": "",
            "target": order.location.province,
            "status": status,
        }
    # Waive (and any future draw-nothing order) has no visual.
    return None


def orders_by_power_to_viz(
    orders_by_power: dict[str, list[Order]],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Pre-adjudication orders (all ``pending``/``success``) → renderer structure."""
    out: dict[str, list[dict[str, Any]]] = {}
    for power, orders in orders_by_power.items():
        viz = [d for o in orders if (d := order_to_viz(o, "success", kind_by_province))]
        if viz:
            out[power] = viz
    return out


def resolution_dict_to_viz(
    resolution: dict[str, Any],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """A persisted ``resolution_to_dict`` → renderer structure, one arrow per order
    with the status coloured by its ``OrderResult`` code."""
    out: dict[str, list[dict[str, Any]]] = {}
    for result_dict in resolution.get("results", []):
        result = OrderResult(
            order=order_from_dict(result_dict["order"]),
            result=ResultCode(result_dict["result"]),
            dislodged=result_dict.get("dislodged", False),
            retreat_options=(),
        )
        status = _STATUS_BY_CODE.get(result.result, "success")
        viz = order_to_viz(result.order, status, kind_by_province)
        if viz is not None:
            out.setdefault(result.order.power, []).append(viz)
    return out
