"""Map generation API routes.

Renders game states to PNG. The SVG→PNG pipeline (``rendering.map.Map``) takes simple
text units (``{power: ["A PAR", "F BRE", ...]}``) plus supply-center control, so it
is fed directly from the new-engine ``GameService.view`` — no old data models.
(The physical relocation of the renderer to ``src/rendering/`` is M6 checkpoint D;
functionally it already runs on the new engine here.)
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import SQLAlchemyError

from ..shared import db_service, game_service, is_bot_secret, resolve_turn
from .auth import get_current_user_optional, http_bearer, require_bot_or_user, require_bot_secret
from rendering.map import Map
from rendering.order_overlay import orders_by_power_to_viz, resolution_dict_to_viz, standoff_provinces
from rendering.view_adapter import phase_info, retreat_options_for_render, svg_path_for_map_name, units_for_render

logger = logging.getLogger(__name__)

# What drawing the overlays can raise for odd data (a missing province, a bad coordinate,
# an unreadable asset). Anything else is a bug and propagates.
_RENDER_ERRORS = (OSError, ValueError, TypeError, KeyError, IndexError)

router = APIRouter()

# Map names the renderer actually knows how to draw. ``svg_path_for_map_name``
# silently falls back to the standard SVG for anything it doesn't recognize
# (it never raises), so the 404 boundary for an unsupported map name lives here.
_KNOWN_MAP_NAMES = frozenset({"standard"})


def _kind_by_province(view: Dict[str, Any]) -> Dict[str, str]:
    """province -> "A"/"F" for the current units, so overlay arrows label units
    with their real type (cosmetic; placement uses the province only)."""
    out: Dict[str, str] = {}
    for units in view.get("units_by_power", {}).values():
        for u in units:
            out[u["location"].split("/")[0]] = u["kind"]
    return out


_SEASON_BY_CODE = {"S": "SPRING", "F": "FALL", "W": "WINTER"}
_PHASE_TYPE_BY_CODE = {"M": "MOVEMENT", "R": "RETREAT", "A": "ADJUSTMENT"}


def _view_from_snapshot(map_name: str, snapshot: Any) -> Dict[str, Any]:
    """Reconstruct a minimal view-shaped dict from a persisted ``MapSnapshotModel``.

    ``map_snapshots`` (written after every ``process_turn``, see ``routes/games.py``)
    stores only ``units`` (the flat ``GameService.view()["units"]`` list),
    ``supply_centers`` and ``phase_code`` — there are no ``year``/``season``/
    ``phase_type`` columns, so they are decoded from the phase code (e.g.
    ``"S1901M"``: season letter, year digits, phase-type letter). ``map_name``
    doesn't vary across a game's turns, so it comes from the ``games`` row instead.
    """
    phase_code = str(snapshot.phase_code)
    season = _SEASON_BY_CODE.get(phase_code[:1], "SPRING")
    phase_type = _PHASE_TYPE_BY_CODE.get(phase_code[-1:], "MOVEMENT")
    year = int(phase_code[1:-1])
    units_by_power: Dict[str, List[Dict[str, Any]]] = {}
    for u in snapshot.units or []:
        units_by_power.setdefault(u["power"], []).append(u)
    state_json = getattr(snapshot, "state_json", None) or {}
    return {
        "map_name": map_name,
        "year": year,
        "season": season,
        "phase_type": phase_type,
        "phase": phase_code,
        "units_by_power": units_by_power,
        "ownership": dict(snapshot.supply_centers or {}),
        # Only a retreat-phase board has any; older snapshots have no state_json.
        "dislodged": list(state_json.get("dislodged") or []),
    }


def _turn_of(game_id: str) -> int:
    row = db_service.get_game_by_game_id(game_id)
    return int(getattr(row, "current_turn", 0) or 0) if row is not None else 0


@router.get("/maps/{map_name}/provinces")
def get_map_provinces(map_name: str) -> Dict[str, Any]:
    """Province metadata for ``map_name``: code → full name, type, supply-centre flag.

    The one server-side source of province *display* names, so no client ships a
    name table of its own (G2). Both the web client and the bot read it once and
    cache; the payload is static per map name.

    **Codes stay the wire format.** These names are for display only -- order
    strings posted back to the API must remain canonical codes, because the
    grammar does not accept full names (see G1's decision in `fix_plan.md`: 26 of
    them are multi-word and `parser._tokenize` splits on whitespace). Substituting
    a name into an order string produces `unknown province: 'BERLIN'`.

    G2 asked for this to extend "whatever the map/metadata endpoint already
    returns", but there was no such endpoint -- every other `/maps/*` route
    returns a PNG -- so this is a new one rather than a field bolted onto the
    per-game state view, which would ship 75 entries on every poll.
    """
    if map_name not in _KNOWN_MAP_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown map: {map_name}")
    map_data = game_service.map
    provinces = {
        code: {
            "name": map_data.display_names.get(code, code),
            "type": map_data.province_types[code].value,
            "is_supply_center": code in map_data.supply_centers,
            "coasts": list(map_data.coasts_of(code)),
        }
        for code in sorted(map_data.provinces)
    }
    return {"map_name": map_name, "provinces": provinces}


@router.get("/maps/{map_name}/preview.png", response_class=Response)
def get_map_preview_png(map_name: str) -> Response:
    """Return a unit-less, ownership-less board PNG for ``map_name``.

    This is the "sample map" shown to bot users who aren't in a game yet -- the
    bare board, no units, no supply-center coloring. Its output depends only on
    ``map_name``, so it never changes; rather than adding a second cache here,
    it leans on ``Map.render_board_png``'s own byte cache (``MapCache``, disk-backed
    at ``/tmp/diplomacy_map_cache``, keyed by ``(svg_path, units, phase_info)``):
    calling it with fixed empty ``units``/``phase_info`` means every request for
    the same map name after the first is a cache hit there. Ops can bust it via
    the existing ``POST /admin/clear_map_cache``.
    """
    if map_name not in _KNOWN_MAP_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown map: {map_name}")
    svg_path = svg_path_for_map_name(map_name)
    img_bytes = Map.render_board_png(svg_path, {}, supply_center_control=None)
    return Response(content=img_bytes, media_type="image/png")


@router.get("/games/{game_id}/map", response_class=Response)
def get_game_map_png(game_id: str) -> Response:
    """Return the current game state as a PNG map."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svg_path = svg_path_for_map_name(view["map_name"])
    img_bytes = Map.render_board_png(
        svg_path,
        units_for_render(view),
        phase_info=phase_info(view, _turn_of(game_id)),
        supply_center_control=dict(view["ownership"]),
        retreat_options=retreat_options_for_render(view),
    )
    return Response(content=img_bytes, media_type="image/png")


def _own_pending_orders(
    game_id: str,
    credentials: Optional[HTTPAuthorizationCredentials],
    telegram_id: Optional[str],
    bot_secret: Optional[str],
) -> Dict[str, Any]:
    """The caller's own power's pending orders, parsed (``{power: [Order]}``).

    Pending orders are secret until the turn is processed, so an orders map
    shows only the caller's: a Bearer user, or the bot passing ``telegram_id``
    and ``bot_secret`` as query parameters (GET has no body), seated in the
    game. Anyone else gets 403.
    """
    user = get_current_user_optional(credentials)
    if user is None and telegram_id and is_bot_secret(bot_secret):
        user = db_service.get_user_by_telegram_id(telegram_id)
    row = db_service.get_game_by_game_id(game_id)
    player = (
        db_service.get_player_by_game_id_and_user_id(game_id=int(row.id), user_id=int(user.id))
        if user is not None and row is not None
        else None
    )
    if player is None:
        raise HTTPException(
            status_code=403, detail="Only a player in this game can see their pending orders on the map."
        )
    power = str(player.power_name)
    pending = game_service.pending_orders_parsed(game_id).get(power)
    return {power: pending} if pending else {}


@router.get("/games/{game_id}/map/orders", response_class=Response)
def get_game_orders_map_png(
    game_id: str,
    telegram_id: Optional[str] = None,
    bot_secret: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Response:
    """Stream the orders-overlay PNG (board + arrows for the caller's own pending
    orders) as bytes. Players in the game only -- see ``_own_pending_orders``.

    Mirrors ``GET /games/{game_id}/map`` -- same view lookup, same rendering
    inputs, same disk-backed ``Map.render_board_png*``-internal cache instead of
    a second caching layer here (see ``get_map_preview_png``'s docstring) -- but
    with order arrows drawn on top. The only prior way to get this image was
    ``POST .../generate_map/orders``, which returns a server-filesystem path
    that only a process on the same host can read; that route is left in place
    for callers that still use it (e.g. the bot's channel auto-post), but a
    browser needs actual bytes.
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    svg_path = svg_path_for_map_name(view["map_name"])
    order_viz = orders_by_power_to_viz(
        _own_pending_orders(game_id, credentials, telegram_id, bot_secret), _kind_by_province(view)
    )
    img_bytes = Map.render_board_png_orders(
        svg_path,
        units_for_render(view),
        order_viz,
        phase_info=phase_info(view, _turn_of(game_id)),
        supply_center_control=dict(view["ownership"]),
    )
    return Response(content=img_bytes, media_type="image/png")


def _last_processed_turn(game_id: str) -> Optional[int]:
    """The number of the most recent processed turn, or ``None`` before the first."""
    turns = [int(t) for t in game_service.resolution_history(game_id)]
    return max(turns) if turns else None


def _turn_board(game_id: str, row: Any, turn: int) -> Dict[str, Any]:
    """The board turn ``turn`` was played on: snapshot ``turn`` (taken when the turn
    began; ``create_game`` records turn 0), or the opening position for turn 0 of a
    game created before that snapshot was recorded."""
    snapshot = db_service.get_game_snapshot_by_game_id_and_turn(game_id=int(row.id), turn=turn)
    if snapshot is not None:
        return _view_from_snapshot(str(row.map_name), snapshot)
    if turn == 0:
        return game_service.opening_view(str(row.map_name))
    raise HTTPException(status_code=404, detail="No board recorded for the start of this turn.")


def _render_turn(board: Dict[str, Any], resolution: Dict[str, Any], turn: int) -> bytes:
    """A processed turn's orders, each drawn with its outcome, on ``board``."""
    return Map.render_board_png_resolution(
        svg_path_for_map_name(board["map_name"]),
        units_for_render(board),
        resolution_dict_to_viz(resolution, _kind_by_province(board)),
        {"conflicts": [{"province": prov, "result": "standoff"} for prov in standoff_provinces(resolution)]},
        phase_info=phase_info(board, turn),
        supply_center_control=dict(board["ownership"]),
    )


@router.get("/games/{game_id}/map/resolution", response_class=Response)
def get_game_resolution_map_png(game_id: str) -> Response:
    """Stream the picture of the last processed turn: its orders, each drawn with its
    outcome, on the board they were given on -- the same picture as
    ``/map/turn/{turn}/orders`` for that turn.

    It used to draw those arrows over the board the turn *produced*, where the unit
    in a province is often not the one that gave or received the order there: a won
    attack's winner wore the loser's dislodged ring. Falls back to the current board
    before any turn has been processed.
    """
    row = db_service.get_game_by_game_id(game_id)
    view = game_service.view(game_id) if row is not None else None
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    turn = _last_processed_turn(game_id)
    if turn is None:
        img_bytes = Map.render_board_png(
            svg_path_for_map_name(view["map_name"]),
            units_for_render(view),
            phase_info=phase_info(view, _turn_of(game_id)),
            supply_center_control=dict(view["ownership"]),
            retreat_options=retreat_options_for_render(view),
        )
    else:
        img_bytes = _render_turn(_turn_board(game_id, row, turn), game_service.resolution_history(game_id)[str(turn)], turn)
    return Response(content=img_bytes, media_type="image/png")


@router.get("/games/{game_id}/map/history/{turn}", response_class=Response)
def get_game_map_history_png(game_id: str, turn: str) -> Response:
    """Return the rendered PNG for a historical turn (``_turn_board``).

    Historical state comes from ``map_snapshots`` (``MapSnapshotModel``), written
    when a game is created (turn 0), automatically after each ``process_turn`` and by the manual
    ``POST /games/{game_id}/generate_map`` snapshot path (see ``routes/games.py``
    and ``database_service.create_game_snapshot``). ``_view_from_snapshot`` bridges
    that persisted shape back to the view shape the renderer helpers expect.
    """
    row = db_service.get_game_by_game_id(game_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    turn_no = resolve_turn(row, turn)
    hist_view = _turn_board(game_id, row, turn_no)
    svg_path = svg_path_for_map_name(hist_view["map_name"])
    img_bytes = Map.render_board_png(
        svg_path,
        units_for_render(hist_view),
        phase_info=phase_info(hist_view, turn_no),
        supply_center_control=dict(hist_view["ownership"]),
        retreat_options=retreat_options_for_render(hist_view),
    )
    return Response(content=img_bytes, media_type="image/png")


@router.get("/games/{game_id}/map/turn/{turn}/orders", response_class=Response)
def get_turn_orders_map_png(game_id: str, turn: str) -> Response:
    """The orders of processed turn ``turn`` on the board they were given on, each
    arrow coloured by what it did, with standoffs marked.

    Turn numbering is ``/history/{turn}``'s: the board is snapshot ``turn`` (taken when
    that turn began), or the opening position for turn 0, which has no snapshot. The
    board after the turn is ``/map/history/{turn + 1}``. The group gets both after
    every processed turn (``api.shared._post_turn_to_channel``) -- fetched by turn
    number, so a post delivered late still shows the turn it announces.
    """
    row = db_service.get_game_by_game_id(game_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    turn_no = resolve_turn(row, turn)
    resolution = game_service.resolution_history(game_id).get(str(turn_no))
    if not resolution:
        raise HTTPException(status_code=404, detail="No orders recorded for this turn.")
    board = _turn_board(game_id, row, turn_no)
    img_bytes = _render_turn(board, resolution, turn_no)
    return Response(content=img_bytes, media_type="image/png")


def _render_and_save(
    game_id: str,
    view: Dict[str, Any],
    suffix: str = "",
    order_viz: Optional[Dict[str, Any]] = None,
    resolution_data: Optional[Dict[str, Any]] = None,
    board: Optional[Dict[str, Any]] = None,
    board_turn: Optional[int] = None,
) -> Dict[str, Any]:
    """Render the current board and save it under ``/tmp/diplomacy_maps``.

    When ``order_viz`` is given, move/support/convoy arrows are drawn over the board
    (orders map). When ``resolution_data`` is also given, standoff/conflict markers
    are drawn too (resolution map), on ``board`` (turn ``board_turn``) when given --
    the board those orders were played on. On any render error, falls back to a
    plain board.
    """
    drawn = board if board is not None else view
    svg_path = svg_path_for_map_name(drawn["map_name"])
    units = units_for_render(drawn)
    phase_info_dict = phase_info(drawn, board_turn if board_turn is not None else _turn_of(game_id))
    scc = dict(drawn["ownership"])
    render_warnings: List[str] = []
    try:
        if resolution_data is not None:
            img_bytes = Map.render_board_png_resolution(
                svg_path, units, order_viz or {}, resolution_data,
                phase_info=phase_info_dict, supply_center_control=scc,
            )
        elif order_viz is not None:
            img_bytes = Map.render_board_png_orders(
                svg_path, units, order_viz,
                phase_info=phase_info_dict, supply_center_control=scc,
            )
        else:
            img_bytes = Map.render_board_png(
                svg_path, units, phase_info=phase_info_dict, supply_center_control=scc,
                retreat_options=retreat_options_for_render(drawn),
            )
    except _RENDER_ERRORS as e:  # degrade to a plain board; a programming bug (other types) still raises
        logger.warning("Overlay render failed for game %s, drawing a plain board: %s", game_id, e)
        render_warnings.append(f"render_failed_primary: {e}")
        img_bytes = Map.render_board_png(
            svg_path, {}, phase_info={"year": None, "season": None, "phase": None, "phase_code": None},
            supply_center_control=None,
        )
    # nosec B108 -- fixed, documented map-render scratch dir; single-tenant container,
    # no other local users, so no multi-user /tmp collision/symlink risk.
    os.makedirs("/tmp/diplomacy_maps", exist_ok=True)  # nosec B108
    phase_code = view["phase"]
    part = f"_{suffix}" if suffix else ""
    ts = int(datetime.now().timestamp())
    map_path = f"/tmp/diplomacy_maps/game_{game_id}{part}_{phase_code}_{ts}.png"  # nosec B108
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
def generate_map_for_snapshot(game_id: str, _: None = Depends(require_bot_or_user)) -> Dict[str, Any]:
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
    except SQLAlchemyError as e:  # the snapshot link is a convenience; the render already succeeded
        logger.warning("Could not attach the map to game %s's snapshot: %s", game_id, e)
    return resp


@router.post("/games/{game_id}/generate_map/orders")
def generate_orders_map(game_id: str, _: None = Depends(require_bot_secret)) -> Dict[str, Any]:
    """Generate an orders map: the board plus arrows for every power's pending orders.

    Renders a plain board when no orders have been submitted yet. Bot secret
    only: the picture shows orders that are secret until the turn is processed.
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    order_viz = orders_by_power_to_viz(
        game_service.pending_orders_parsed(game_id), _kind_by_province(view)
    )
    return _render_and_save(game_id, view, suffix="orders", order_viz=order_viz)


@router.post("/games/{game_id}/generate_map/resolution")
def generate_resolution_map(game_id: str, _: None = Depends(require_bot_or_user)) -> Dict[str, Any]:
    """Generate a resolution map: the last processed turn's orders, each drawn with
    its outcome, on the board they were given on (as ``GET .../map/resolution``).

    Falls back to a plain board when no turn has been processed yet.
    """
    row = db_service.get_game_by_game_id(game_id)
    view = game_service.view(game_id) if row is not None else None
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    turn = _last_processed_turn(game_id)
    if turn is None:
        return _render_and_save(game_id, view, suffix="resolution")
    resolution = game_service.resolution_history(game_id)[str(turn)]
    board = _turn_board(game_id, row, turn)
    resolution_data = {
        "conflicts": [{"province": prov, "result": "standoff"} for prov in standoff_provinces(resolution)],
    }
    return _render_and_save(
        game_id, view, suffix="resolution",
        order_viz=resolution_dict_to_viz(resolution, _kind_by_province(board)),
        resolution_data=resolution_data, board=board, board_turn=turn,
    )
