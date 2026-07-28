"""Adapt ``GameService.view()`` dicts into the renderer's input shapes.

``rendering.map.Map`` speaks a pre-rewrite vocabulary: plain SVG paths, a
``{power: ["A PAR", "F BRE", ...]}`` unit map (coast stripped), and a small
``phase_info`` dict for the on-image phase label. The new engine's view (see
``server.game_service.GameService.view``) is GameState-native — ``units`` is a list
of dicts, powers are grouped separately under ``units_by_power`` — so callers must
convert before handing data to the renderer.

This module is that single conversion point. It is pure: no FastAPI, no DB, no I/O.
Both ``server.api.routes.maps`` and the ``GET /games/{game_id}/map/history/{turn}``
route build on it.
"""
from __future__ import annotations

import os
from typing import Any


def svg_path_for_map_name(map_name: str) -> str:
    """Resolve a map name (``"standard"``, ``"standard-v2"``) to its SVG file path.

    Reads ``DIPLOMACY_MAP_PATH`` (defaulting to ``maps/standard.svg``) for the base
    map; ``standard-v2`` looks for a sibling ``v2.svg`` and falls back to the base
    path if that file is missing.
    """
    if map_name == "standard-v2":
        base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
        svg_path = os.path.join(base_dir, "v2.svg")
        if not os.path.exists(svg_path):
            svg_path = base_path
        return svg_path
    return os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")


def units_for_render(view: dict[str, Any]) -> dict[str, list[str]]:
    """Build the renderer's ``{power: ["A PAR", "F STP", ...]}`` map (coast stripped).

    Reads ``view["units_by_power"]`` — the grouped-by-power shape ``GameService.view``
    already provides. This is the single place that ``GameState``-native units
    (``view["units"]``, a flat list of dicts) become the renderer's flat unit
    strings; callers must not hand the renderer ``view["units"]`` directly.
    """
    out: dict[str, list[str]] = {}
    for power, units in view.get("units_by_power", {}).items():
        out[power] = [f"{u['kind']} {u['location'].split('/')[0]}" for u in units]
    return out


def phase_info(view: dict[str, Any], turn: int) -> dict[str, Any]:
    """Build the renderer's phase-label dict from a view (or view-shaped) dict."""
    return {
        "turn": turn,
        "year": view["year"],
        "season": view["season"],
        "phase": view["phase_type"],
        "phase_code": view["phase"],
    }
