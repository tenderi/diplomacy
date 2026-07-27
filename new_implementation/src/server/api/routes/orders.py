"""Order management API routes (new engine).

Orders are validated by the engine and stored per power in ``games.pending_orders``
via ``GameService``; they are consumed and cleared when the turn is processed.
"""
from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from .auth import get_current_user_optional, resolve_user_or_telegram, http_bearer
from ..shared import db_service, game_service, logger, BOT_SECRET

router = APIRouter()


class SetOrdersRequest(BaseModel):
    """Request model for submitting orders for a power in a game."""
    game_id: str
    power: str
    orders: list[str]
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None


def _authorize_power(credentials, game_id: str, power: str, telegram_id, bot_secret):
    """Resolve the caller and confirm they hold ``power`` in ``game_id``."""
    user = resolve_user_or_telegram(credentials, telegram_id, bot_secret=bot_secret)
    player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    if int(player.user_id) != int(user.id):  # type: ignore
        raise HTTPException(status_code=403, detail="You are not authorized to act for this power.")
    return user, player


@router.post("/games/set_orders")
def set_orders(
    req: SetOrdersRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Submit orders for a power. Only the assigned user may submit.

    Returns per-order validation results ``{order, success, error}``.
    """
    _authorize_power(credentials, str(req.game_id), req.power, req.telegram_id, req.bot_secret)
    if not game_service.exists(str(req.game_id)):
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        raw = game_service.submit_orders(str(req.game_id), req.power, req.orders)
    except Exception as e:
        logger.exception(f"set_orders failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    results = [{"order": r["order"], "success": r["ok"], "error": r["reason"]} for r in raw]
    return {"results": results}


@router.get("/games/{game_id}/orders")
def get_orders(
    game_id: str,
    telegram_id: Optional[str] = None,
    bot_secret: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> List[Dict[str, Any]]:
    """Current-turn pending orders; authenticated users see only their own power.

    Accepts a Bearer token (browser) or ``telegram_id``+``bot_secret`` query params
    (Telegram bot; GET has no body to carry them in) — same fallback pattern as
    ``GET /games/{game_id}/messages``.
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    user = get_current_user_optional(credentials)
    if user is None and telegram_id and BOT_SECRET and bot_secret == BOT_SECRET:
        user = db_service.get_user_by_telegram_id(telegram_id)
    if user is None:
        return []
    player = db_service.get_player_by_game_id_and_user_id(game_id=int(game_id), user_id=int(user.id))
    if player is None:
        return []
    power = player.power_name
    return [
        {"player_id": player.id, "power": power, "order": o}
        for o in view["orders"].get(power, [])
    ]


@router.get("/games/{game_id}/orders/history")
def get_order_history(game_id: str) -> Dict[str, Any]:
    """Per-turn history of submitted orders, ``{turn: {power: [order_str]}}``.

    Accumulated by ``process_turn`` (the ``GameState`` snapshot itself does not retain
    past orders); empty until the first turn is processed."""
    if not game_service.exists(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"game_id": game_id, "order_history": game_service.order_history(game_id)}


@router.get("/games/{game_id}/orders/{power}")
def get_orders_for_power(
    game_id: str,
    power: str,
    telegram_id: Optional[str] = None,
    bot_secret: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Current pending orders for a power. Only the assigned user may view them.

    Accepts a Bearer token (browser) or ``telegram_id``+``bot_secret`` query params
    (Telegram bot; GET has no body to carry them in) — same fallback pattern as
    ``GET /games/{game_id}/messages``.
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    user = get_current_user_optional(credentials)
    if user is None and telegram_id and BOT_SECRET and bot_secret == BOT_SECRET:
        user = db_service.get_user_by_telegram_id(telegram_id)
    player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
    if player is None:
        raise HTTPException(status_code=404, detail="Player not found")
    if user is None or int(getattr(player, "user_id", -1)) != int(user.id):
        raise HTTPException(status_code=403, detail="You are not authorized to view orders for this power.")
    return {"power": power, "orders": view["orders"].get(power.upper(), [])}


class ClearOrdersRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


@router.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(
    game_id: int,
    power: str,
    req: ClearOrdersRequest = Body(...),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, str]:
    """Clear a power's pending orders. Only the assigned user may clear them."""
    _authorize_power(credentials, str(game_id), power, req.telegram_id, req.bot_secret)
    game_service.clear_orders(str(game_id), power)
    return {"status": "ok"}
