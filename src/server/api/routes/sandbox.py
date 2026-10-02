"""The sandbox: order every power on a scratch board and step it through the phases.

A browser-only tool for trying out orders -- a real game's current position or the
opening one -- without touching any game. **Nothing is stored.** The client holds
the serialized ``GameState`` (``engine.serialization.state_to_dict``) and sends it
with every request; ``GameService.sandbox_state`` validates it (it is untrusted
input) and each route answers from it alone:

- ``POST /sandbox/start`` -- the board to begin from: a game's current state, or the
  opening position.
- ``POST /sandbox/legal_orders`` -- ``legal_orders_for_power`` for one power.
- ``POST /sandbox/adjudicate`` -- validate every power's orders, adjudicate, and
  return the next phase's board (retreat and adjustment phases included).
- ``POST /sandbox/map`` -- the board as a PNG: bare, with the orders drawn on it, or
  with those orders adjudicated and coloured by outcome.

Signed-in callers only (``require_bot_or_user``): the routes are stateless, but
adjudicating and rendering cost CPU, so they are not open to anonymous traffic.
"""
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..shared import game_service
from .auth import require_bot_or_user
from engine.types import GameState, GameStatus
from rendering.map import Map
from rendering.order_overlay import orders_by_power_to_viz, resolution_dict_to_viz, standoff_provinces
from rendering.view_adapter import phase_info, retreat_options_for_render, svg_path_for_map_name, units_for_render
from server.game_service import GameOverError, OrderError
from server.legal_orders import legal_orders_for_power

router = APIRouter(dependencies=[Depends(require_bot_or_user)])

# More than any power can have (34 centres' worth of units), so a real board never
# hits it; it only bounds what a hand-made request can make the server parse.
MAX_ORDERS_PER_POWER = 40


class SandboxStartRequest(BaseModel):
    game_id: Optional[str] = None


class SandboxLegalOrdersRequest(BaseModel):
    state: Dict[str, Any]
    power: str


class SandboxOrdersRequest(BaseModel):
    state: Dict[str, Any]
    orders: Dict[str, List[str]] = {}


class SandboxMapRequest(SandboxOrdersRequest):
    overlay: Literal["board", "orders", "resolution"] = "board"


def _state(state_json: Dict[str, Any]) -> GameState:
    try:
        return game_service.sandbox_state(state_json)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid sandbox board: {e}")


def _orders(req: SandboxOrdersRequest) -> Dict[str, List[str]]:
    for power, orders in req.orders.items():
        if len(orders) > MAX_ORDERS_PER_POWER:
            raise HTTPException(status_code=400, detail=f"Too many orders for {power}")
    return req.orders


@router.post("/sandbox/start")
def start_sandbox(req: SandboxStartRequest) -> Dict[str, Any]:
    """The board a sandbox begins from: ``game_id``'s current position (any game's
    board is public, as ``GET /games/{id}/state`` is), or the opening one."""
    if req.game_id:
        state_json = game_service.state_json(req.game_id)
        if state_json is None:
            raise HTTPException(status_code=404, detail="Game not found")
    else:
        state_json = game_service.sandbox_opening()
    state = _state(state_json)
    return {
        "source_game_id": req.game_id or None,
        "state": state_json,
        "view": game_service.sandbox_view(state),
    }


@router.post("/sandbox/legal_orders")
def sandbox_legal_orders(req: SandboxLegalOrdersRequest) -> Dict[str, Any]:
    """Every legal order for ``power`` on the sandbox board, in the shape of
    ``GET /games/{id}/legal_orders/{power}``."""
    state = _state(req.state)
    power = req.power.upper()
    if power not in game_service.map.home_centers:
        raise HTTPException(status_code=400, detail=f"Unknown power {req.power}")
    return legal_orders_for_power(game_service.map, state, power)


@router.post("/sandbox/adjudicate")
def sandbox_adjudicate(req: SandboxOrdersRequest) -> Dict[str, Any]:
    """Resolve every power's orders and advance one phase (see
    ``GameService.sandbox_adjudicate``). A unit with no order holds; an order that
    fails validation is reported in ``order_results`` and left out."""
    state = _state(req.state)
    try:
        return game_service.sandbox_adjudicate(state, _orders(req))
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GameOverError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/sandbox/map", response_class=Response)
def sandbox_map(req: SandboxMapRequest) -> Response:
    """The sandbox board as a PNG. ``overlay``: ``board`` (units only), ``orders``
    (``orders`` drawn as pending arrows) or ``resolution`` (``orders`` adjudicated
    on this board and drawn coloured by outcome, standoffs marked -- the picture
    of a turn on the board it was played on). Illegal orders are left off."""
    state = _state(req.state)
    view = game_service.sandbox_view(state)
    kinds = {u["location"].split("/")[0]: u["kind"] for u in view["units"]}
    try:
        _, parsed = game_service.sandbox_orders(state, _orders(req))
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    svg_path = svg_path_for_map_name(view["map_name"])
    common: Dict[str, Any] = {
        "phase_info": phase_info(view, 0),
        "supply_center_control": dict(view["ownership"]),
    }
    if req.overlay == "orders" and parsed:
        img = Map.render_board_png_orders(
            svg_path, units_for_render(view), orders_by_power_to_viz(parsed, kinds), **common
        )
    elif req.overlay == "resolution" and parsed and state.status is GameStatus.ACTIVE:
        resolution = game_service.sandbox_adjudicate(state, req.orders)["resolution"]
        img = Map.render_board_png_resolution(
            svg_path,
            units_for_render(view),
            resolution_dict_to_viz(resolution, kinds),
            {"conflicts": [{"province": p, "result": "standoff"} for p in standoff_provinces(resolution)]},
            **common,
        )
    else:
        img = Map.render_board_png(svg_path, units_for_render(view), retreat_options=retreat_options_for_render(view), **common)
    return Response(content=img, media_type="image/png")
