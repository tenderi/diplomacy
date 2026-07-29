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

from typing import Any, Iterable, Optional

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
    ResultCode.DISLODGED: "dislodged",
    ResultCode.DISBAND: "success",
    ResultCode.BUILD: "success",
    ResultCode.WAIVE: "success",
}

# Merging a convoy chain can combine fleets with different individual statuses
# (e.g. one fleet dislodged, its siblings reporting NO_CONVOY once the chain
# breaks). The merged entry gets a single status: the worst one present, so a
# dislodged fleet's marker isn't hidden by a merely-"failed" sibling.
_CONVOY_STATUS_PRIORITY: dict[str, int] = {"success": 0, "bounced": 1, "failed": 2, "dislodged": 3}


def _merge_convoy_status(statuses: Iterable[str]) -> str:
    return max(statuses, key=lambda s: _CONVOY_STATUS_PRIORITY.get(s, 0))


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


def _merge_convoy_group(
    group: list[tuple[Convoy, str]],
    kind_by_province: Optional[dict[str, str]],
) -> Optional[dict[str, Any]]:
    """Build one merged viz entry for a group of ``Convoy`` orders that share the
    same ``(origin, dest)`` -- i.e. every fleet convoying the same army on the
    same route, possibly owned by different powers.

    ``convoy_chain`` lists the fleets in the order they appear in the input list.
    A true route order (army -> fleet -> fleet -> ... -> dest) would need the sea
    adjacency graph to walk the chain, but that lives in ``engine.map_loader``'s
    ``MapData`` -- this module only ever sees ``Order`` objects, never the map, so
    a topological ordering isn't derivable here. Insertion order is what callers
    already control (they build the order list), so it's the best available
    approximation without threading ``MapData`` through this module.
    """
    first_order, _ = group[0]
    merged_status = _merge_convoy_status(status for _, status in group)
    viz = order_to_viz(first_order, merged_status, kind_by_province)
    if viz is None:
        return None
    viz["convoy_chain"] = [order.unit.province for order, _ in group]
    return viz


def orders_by_power_to_viz(
    orders_by_power: dict[str, list[Order]],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """Pre-adjudication orders (all ``pending``/``success``) → renderer structure.

    ``Convoy`` orders sharing an (origin, dest) -- possibly submitted by different
    powers escorting the same army -- are merged into one multi-fleet chain entry,
    filed under the first such order's power (the renderer picks convoy arrow color
    from ``visualization_config``, not the power color, so the filing power only
    affects which power's order list the entry lives in).
    """
    out: dict[str, list[dict[str, Any]]] = {}
    convoy_groups: dict[tuple[str, str], list[tuple[Convoy, str]]] = {}
    for power, orders in orders_by_power.items():
        for o in orders:
            if isinstance(o, Convoy):
                convoy_groups.setdefault((o.origin.province, o.dest.province), []).append((o, "success"))
                continue
            viz = order_to_viz(o, "success", kind_by_province)
            if viz is not None:
                out.setdefault(power, []).append(viz)
    for group in convoy_groups.values():
        viz = _merge_convoy_group(group, kind_by_province)
        if viz is not None:
            out.setdefault(group[0][0].power, []).append(viz)
    return out


def resolution_dict_to_viz(
    resolution: dict[str, Any],
    kind_by_province: Optional[dict[str, str]] = None,
) -> dict[str, list[dict[str, Any]]]:
    """A persisted ``resolution_to_dict`` → renderer structure, one arrow per order
    with the status coloured by its ``OrderResult`` code.

    ``Convoy`` orders sharing an (origin, dest) are merged the same way as in
    ``orders_by_power_to_viz`` -- see ``_merge_convoy_group`` for the chain-order
    caveat and ``_merge_convoy_status`` for how a mixed-status group collapses to
    one status.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    convoy_groups: dict[tuple[str, str], list[tuple[Convoy, str]]] = {}
    for result_dict in resolution.get("results", []):
        result = OrderResult(
            order=order_from_dict(result_dict["order"]),
            result=ResultCode(result_dict["result"]),
            dislodged=result_dict.get("dislodged", False),
            retreat_options=(),
        )
        status = _STATUS_BY_CODE.get(result.result, "success")
        order = result.order
        if isinstance(order, Convoy):
            convoy_groups.setdefault((order.origin.province, order.dest.province), []).append((order, status))
            continue
        viz = order_to_viz(order, status, kind_by_province)
        if viz is not None:
            out.setdefault(order.power, []).append(viz)
    for group in convoy_groups.values():
        viz = _merge_convoy_group(group, kind_by_province)
        if viz is not None:
            out.setdefault(group[0][0].power, []).append(viz)
    return out
