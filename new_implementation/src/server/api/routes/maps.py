"""Map generation API routes.

Renders game states to PNG. The SVG→PNG pipeline (``rendering.map.Map``) takes simple
text units (``{power: ["A PAR", "F BRE", ...]}``) plus supply-center control, so it
is fed directly from the new-engine ``GameService.view`` — no old data models.
(The physical relocation of the renderer to ``src/rendering/`` is M6 checkpoint D;
functionally it already runs on the new engine here.)
"""
import os
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..shared import db_service, game_service
from rendering.map import Map

router = APIRouter()


def _svg_path_for_map_name(map_name: str) -> str:
    if map_name == "standard-v2":
        base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
        svg_path = os.path.join(base_dir, "v2.svg")
        if not os.path.exists(svg_path):
            svg_path = base_path
        return svg_path
    return os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")


def _units_for_render(view: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build the renderer's ``{power: ["A PAR", "F STP", ...]}`` (coast stripped)."""
    out: Dict[str, List[str]] = {}
    for power, units in view.get("units_by_power", {}).items():
        out[power] = [f"{u['kind']} {u['location'].split('/')[0]}" for u in units]
    return out


def _phase_info(view: Dict[str, Any], turn: int) -> Dict[str, Any]:
    return {
        "turn": turn,
        "year": view["year"],
        "season": view["season"],
        "phase": view["phase_type"],
        "phase_code": view["phase"],
    }


def _turn_of(game_id: str) -> int:
    row = db_service.get_game_by_game_id(game_id)
    return int(getattr(row, "current_turn", 0) or 0) if row is not None else 0


@router.get("/games/{game_id}/map", response_class=Response)
def get_game_map_png(game_id: str) -> Response:
    """Return the current game state as a PNG map."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svg_path = _svg_path_for_map_name(view["map_name"])
    try:
        img_bytes = Map.render_board_png(
            svg_path,
            _units_for_render(view),
            phase_info=_phase_info(view, _turn_of(game_id)),
            supply_center_control=dict(view["ownership"]),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Map render failed: {e}")
    return Response(content=img_bytes, media_type="image/png")


def _render_and_save(game_id: str, view: Dict[str, Any], suffix: str = "") -> Dict[str, Any]:
    svg_path = _svg_path_for_map_name(view["map_name"])
    render_warnings: List[str] = []
    try:
        img_bytes = Map.render_board_png(
            svg_path,
            _units_for_render(view),
            phase_info=_phase_info(view, _turn_of(game_id)),
            supply_center_control=dict(view["ownership"]),
        )
    except Exception as e:
        render_warnings.append(f"render_failed_primary: {e}")
        img_bytes = Map.render_board_png(
            svg_path, {}, phase_info={"year": None, "season": None, "phase": None, "phase_code": None},
            supply_center_control=None,
        )
    os.makedirs("/tmp/diplomacy_maps", exist_ok=True)
    phase_code = view["phase"]
    part = f"_{suffix}" if suffix else ""
    map_path = f"/tmp/diplomacy_maps/game_{game_id}{part}_{phase_code}_{int(datetime.now().timestamp())}.png"
    with open(map_path, "wb") as f:
        f.write(img_bytes)
    resp: Dict[str, Any] = {
        "status": "ok",
        "map_path": map_path,
        "phase_code": phase_code,
        "message": f"Map generated for {phase_code}",
    }
    if render_warnings:
        resp["render_warnings"] = render_warnings
    return resp


@router.post("/games/{game_id}/generate_map")
def generate_map_for_snapshot(game_id: str) -> Dict[str, Any]:
    """Generate and save a map image for the current game state."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    resp = _render_and_save(game_id, view)
    # Attach the image to the latest snapshot for this phase, if one exists.
    try:
        row = db_service.get_game_by_game_id(game_id)
        latest = db_service.get_latest_game_snapshot_by_game_id_and_phase_code(
            game_id=int(row.id), phase_code=view["phase"]
        )
        if latest:
            db_service.update_game_snapshot_map_image_path(int(latest.id), resp["map_path"])
            db_service.commit()
    except Exception:
        pass
    return resp


@router.post("/games/{game_id}/generate_map/orders")
def generate_orders_map(game_id: str) -> Dict[str, Any]:
    """Generate an orders map. Order-arrow overlays are pending the M6 rendering
    rework (checkpoint D); this currently renders the board for the phase."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _render_and_save(game_id, view, suffix="orders")


@router.post("/games/{game_id}/generate_map/resolution")
def generate_resolution_map(game_id: str) -> Dict[str, Any]:
    """Generate a resolution map. Resolution overlays are pending checkpoint D;
    this currently renders the board for the phase."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return _render_and_save(game_id, view, suffix="resolution")
