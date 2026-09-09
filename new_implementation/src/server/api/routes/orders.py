"""Order management API routes (new engine).

Orders are validated by the engine and stored per power in ``games.pending_orders``
via ``GameService``; they are consumed and cleared when the turn is processed.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from .auth import get_current_user_optional, resolve_user_or_telegram, http_bearer
from ..client_timestamp import normalize_client_timestamp
from ..shared import db_service, game_service, logger, BOT_SECRET

router = APIRouter()


class SetOrdersRequest(BaseModel):
    """Request model for submitting orders for a power in a game."""
    game_id: str
    power: str
    orders: list[str]
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None
    # When the player composed these orders (ISO-8601 UTC). The bot sends it on
    # every submission; see ``_refuse_if_stale``.
    client_timestamp: Optional[datetime] = None


def _refuse_if_stale(game_id: str, client_timestamp: Optional[datetime]) -> None:
    """Refuse an order write composed before the current phase began.

    The bot queues order submissions while the home server is unreachable and
    replays them later. If the deadline passed in between, the turn was
    adjudicated without those orders, and replaying them now would submit
    last phase's intentions against this phase's board -- most would fail
    validation on a moved unit, but a hold or a support for a unit that
    stayed put would be silently accepted for a turn the player never saw.

    So: if the request carries a ``client_timestamp`` older than
    ``games.phase_started_at``, reject it with 409 and a message the bot can
    show verbatim. The player loses nothing silently -- they are told exactly
    which orders did not make it and why. Requests without a timestamp (the
    browser, older clients) are unaffected, as are games whose
    ``phase_started_at`` is still NULL (created before the column existed).
    """
    if client_timestamp is None:
        return
    composed_at = normalize_client_timestamp(client_timestamp)
    row = db_service.get_game_by_game_id(game_id)
    started = getattr(row, "phase_started_at", None) if row is not None else None
    if started is None or composed_at >= started:
        return
    raise HTTPException(
        status_code=409,
        detail=(
            f"These orders were composed at {composed_at:%Y-%m-%d %H:%M} UTC, but the "
            f"turn was processed at {started:%Y-%m-%d %H:%M} UTC and game {game_id} is "
            f"now in phase {getattr(row, 'phase_code', '?')}. They were NOT applied -- "
            f"check the new board and submit fresh orders."
        ),
    )


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
    _refuse_if_stale(str(req.game_id), req.client_timestamp)
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
    client_timestamp: Optional[datetime] = None


@router.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(
    game_id: int,
    power: str,
    req: ClearOrdersRequest = Body(...),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, str]:
    """Clear a power's pending orders. Only the assigned user may clear them."""
    _authorize_power(credentials, str(game_id), power, req.telegram_id, req.bot_secret)
    # A queued "clear" that arrives after the phase moved on would wipe orders
    # the player entered for the *new* phase (e.g. from the browser).
    _refuse_if_stale(str(game_id), req.client_timestamp)
    game_service.clear_orders(str(game_id), power)
    return {"status": "ok"}
