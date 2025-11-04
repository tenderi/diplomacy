"""
Order management API routes.

This module contains all endpoints related to order submission, retrieval, and history.
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, List, Any
import requests

from ..shared import (
    db_service, server, logger, scheduler_logger, NOTIFY_URL,
    _state_to_spec_dict
)
from engine.order_parser import OrderParser
from engine.data_models import MoveOrder, SupportOrder
from ...response_cache import cached_response

router = APIRouter()

# --- Request Models ---
class SetOrdersRequest(BaseModel):
    """Request model for submitting orders for a power in a game."""
    game_id: str
    power: str
    orders: list[str]
    telegram_id: str

def _order_model_to_text(order_model) -> str:
    """Convert OrderModel back to order text string."""
    unit_str = f"{order_model.unit_type} {order_model.unit_province}"
    
    if order_model.order_type == "move":
        return f"{unit_str} - {order_model.target_province}"
    elif order_model.order_type == "hold":
        return f"{unit_str} H"
    elif order_model.order_type == "support":
        if order_model.supported_target:
            return f"{unit_str} S {order_model.supported_unit_type} {order_model.supported_unit_province} - {order_model.supported_target}"
        else:
            return f"{unit_str} S {order_model.supported_unit_type} {order_model.supported_unit_province} H"
    elif order_model.order_type == "convoy":
        return f"{unit_str} C {order_model.convoyed_unit_type} {order_model.convoyed_unit_province} - {order_model.convoyed_target}"
    elif order_model.order_type == "retreat":
        return f"{unit_str} R {order_model.target_province}"
    elif order_model.order_type == "build":
        coast_str = f"/{order_model.build_coast}" if order_model.build_coast else ""
        return f"BUILD {order_model.build_type} {order_model.build_province}{coast_str}"
    elif order_model.order_type == "destroy":
        return f"D {order_model.destroy_unit_type} {order_model.destroy_unit_province}"
    else:
        return f"{unit_str} ({order_model.order_type})"

# --- Order Endpoints ---
@router.post("/games/set_orders")
def set_orders(req: SetOrdersRequest) -> Dict[str, Any]:
    """Submit orders for a power in a game. Only the assigned user (by telegram_id) can submit orders for their power.
    Returns per-order validation results. 403 if unauthorized, 404 if player not found.
    """
    results = []
    try:
        # game_id can be string, method handles conversion
        player = db_service.get_player_by_game_id_and_power(game_id=req.game_id, power=req.power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        # Authorization check: Only assigned user can submit orders
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None or int(player.user_id) != int(user.id):  # type: ignore
            raise HTTPException(status_code=403, detail="You are not authorized to submit orders for this power.")
        # Get game by game_id string (not numeric id) for other operations
        game = db_service.get_game_by_game_id(str(req.game_id))
        # Get current_turn directly from database with refresh to ensure we get the latest value
        turn = db_service.get_game_current_turn(str(req.game_id))
        
        # Parse and validate orders using the engine; then persist via DAL
        parsed_orders: list[Any] = []
        if str(req.game_id) in server.games:
            game_obj = server.games[str(req.game_id)]
            game_state = game_obj.get_game_state()
            for order in req.orders:
                try:
                    parser = OrderParser()
                    parsed = parser.parse_orders(order, req.power)
                    if parsed:
                        # Convert ParsedOrder to Order objects
                        order_objects = []
                        for p in parsed:
                            try:
                                order_obj = parser.create_order_from_parsed(p, game_obj.get_game_state())
                                if order_obj:
                                    order_objects.append(order_obj)
                            except Exception as create_err:
                                logger.warning(f"set_orders: create_order_from_parsed failed for parsed order {p}: {create_err}")
                                pass
                        if order_objects:
                            parsed_orders.extend(order_objects)
                            results.append({"order": order, "success": True, "error": None})
                        else:
                            error_msg = "Failed to create order object"
                            results.append({"order": order, "success": False, "error": error_msg})
                            logger.warning(f"set_orders: {error_msg} for order '{order}'")
                    else:
                        error_msg = "Invalid order"
                        results.append({"order": order, "success": False, "error": error_msg})
                        logger.warning(f"set_orders: {error_msg}: '{order}'")
                except Exception as e:
                    error_msg = str(e)
                    results.append({"order": order, "success": False, "error": error_msg})
                    logger.warning(f"set_orders: Exception parsing order '{order}': {error_msg}")
                    try:
                        user_id = getattr(player, "user_id", None)
                        if player is not None and user_id is not None:
                            user = db_service.get_user_by_id(user_id)
                            telegram_id = getattr(user, "telegram_id", None) if user is not None else None
                            if telegram_id is not None:
                                try:
                                    telegram_id_int = int(telegram_id)
                                    requests.post(
                                        NOTIFY_URL,
                                        json={"telegram_id": telegram_id_int, "message": f"Order error in game {req.game_id} for {req.power}: {order}\nError: {e}"},
                                        timeout=2,
                                    )
                                except (ValueError, TypeError):
                                    pass
                    except Exception as notify_err:
                        scheduler_logger.error(f"Failed to notify order error: {notify_err}")
        else:
            raise HTTPException(status_code=404, detail="Game not loaded in memory for order parsing")

        # Persist orders for this power and turn via DAL
        if parsed_orders:
            db_service.submit_orders(game_id=str(req.game_id), power_name=req.power, orders=parsed_orders, turn_number=turn)
            
            # Also add orders to in-memory game state
            if str(req.game_id) in server.games:
                game_obj = server.games[str(req.game_id)]
                order_strings = [f"{order.unit.unit_type} {order.unit.province} - {order.target_province}" 
                                if hasattr(order, 'target_province') and order.target_province
                                else f"{order.unit.unit_type} {order.unit.province} H"
                                for order in parsed_orders if hasattr(order, 'unit')]
                if order_strings:
                    existing_orders = game_obj.game_state.orders.get(req.power, [])
                    game_obj.game_state.orders[req.power] = existing_orders + parsed_orders
        
        # Update game state in DB to reflect in-memory state
        if game and req.game_id in server.games:
            game_obj = server.games[req.game_id]
            state_obj = game_obj.get_game_state()
            state: Dict[str, Any] = _state_to_spec_dict(state_obj)
            try:
                game.state = state  # type: ignore
            except Exception as e:
                logger.debug(f"set_orders: failed to assign spec-shaped game.state: {e}")
        return {"results": results}
    except Exception as e:
        logger.exception(f"set_orders: SQLAlchemyError: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/orders")
@cached_response(ttl=30, key_params=["game_id"])
def get_orders(game_id: str) -> List[Dict[str, Any]]:
    try:
        players = db_service.get_players_by_game_id(int(game_id))
        orders: List[Dict[str, Any]] = []
        for player in players:
            player_orders = db_service.get_orders_by_player_id(int(player.id))  # type: ignore
            power_name = getattr(player, "power_name", None) or getattr(player, "power", None)
            for order in player_orders:
                unit_str = f"{order.unit_type} {order.unit_province}"
                order_str = f"{power_name} {unit_str}"
                if order.order_type == "move" and getattr(order, 'target_province', None):  # type: ignore
                    order_str += f" - {order.target_province}"
                elif order.order_type == "hold":  # type: ignore
                    order_str += " H"
                elif order.order_type == "support":  # type: ignore
                    supported_type = getattr(order, 'supported_unit_type', None)
                    supported_prov = getattr(order, 'supported_unit_province', None)
                    if supported_type is not None and supported_prov is not None:  # type: ignore
                        order_str += f" S {supported_type} {supported_prov}"
                        supported_target = getattr(order, 'supported_target', None)
                        if supported_target is not None:  # type: ignore
                            order_str += f" - {order.supported_target}"
                orders.append({"player_id": player.id, "power": power_name, "order": order_str})
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/orders/history")
def get_order_history(game_id: str) -> Dict[str, Any]:
    """Get the full order history for all players in a game, grouped by turn and power."""
    try:
        players = db_service.get_players_by_game_id(int(game_id))
        history = {}
        for player in players:
            orders = db_service.get_orders_by_player_id(int(getattr(player, 'id', 0)))  # type: ignore
            for order in orders:
                turn = str(order.turn_number)
                power = player.power_name
                order_text = _order_model_to_text(order)
                history.setdefault(turn, {}).setdefault(power, []).append(order_text)
        return {"game_id": game_id, "order_history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/orders/{power}")
def get_orders_for_power(game_id: str, power: str) -> Dict[str, Any]:
    """Get current orders for a specific power in a game (current turn only)."""
    try:
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        orders = db_service.get_orders_by_player_id(int(getattr(player, 'id', 0)))  # type: ignore
        order_list = [order.order_text for order in orders]
        return {"power": power, "orders": order_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(game_id: int, power: str, telegram_id: str = Body(...)) -> Dict[str, str]:
    """Clear orders for a power. Only the assigned user can clear orders for their power."""
    try:
        # Authorization check
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        user = db_service.get_user_by_telegram_id(telegram_id)
        if user is None or int(player.user_id) != int(user.id):  # type: ignore
            raise HTTPException(status_code=403, detail="You are not authorized to clear orders for this power.")
        
        # Clear orders in database
        db_service.delete_orders_by_player_id(int(player.id))  # type: ignore
        
        # Clear orders in in-memory game state
        if str(game_id) in server.games:
            game = server.games[str(game_id)]
            if power in game.game_state.orders:
                game.game_state.orders[power] = []
        
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

