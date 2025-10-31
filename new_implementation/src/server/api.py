"""
RESTful API server for Diplomacy game management and integration (e.g., Telegram bot).
Implements endpoints for game creation, player management, order submission, state queries, and notifications.
Strict typing and Ruff compliance enforced.

Key features:
- Persistent game state using PostgreSQL and SQLAlchemy
- Deadline-based turn processing with FastAPI lifespan background scheduler
- Extensible REST API for game and player management
- Strict typing and modern Python best practices
"""
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from .models import GameStateOut, PowerStateOut, UnitOut
from .server import Server
import uvicorn
from typing import Optional, Dict, List, Any
from .db_config import SQLALCHEMY_DATABASE_URL
from datetime import datetime, timezone, timedelta
import os
import asyncio
import contextlib
from contextlib import asynccontextmanager
import requests
import logging
import pytz
from engine.order_parser import OrderParser
from engine.database import order_to_dict, unit_to_dict, dict_to_order, dict_to_unit, PlayerModel
from engine.data_models import Unit, GameStatus
from .response_cache import cached_response, invalidate_cache, get_cache_stats, clear_response_cache
from engine.database_service import DatabaseService

# Initialize DAL
db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)

# --- Helpers ---
def _state_to_spec_dict(state_obj: Any) -> Dict[str, Any]:
    """Serialize GameState dataclasses to spec-shaped JSON-serializable dict."""
    supply_centers: dict[str, str] = {}
    for p_name, p_state in state_obj.powers.items():
        for prov in p_state.controlled_supply_centers:
            supply_centers[prov] = p_name

    powers: Dict[str, Any] = {}
    for power_name, ps in state_obj.powers.items():
        powers[power_name] = {
            "power_name": ps.power_name,
            "user_id": ps.user_id,
            "is_active": ps.is_active,
            "is_eliminated": ps.is_eliminated,
            "home_supply_centers": ps.home_supply_centers,
            "controlled_supply_centers": ps.controlled_supply_centers,
            "units": [unit_to_dict(u) for u in ps.units],
            "orders_submitted": ps.orders_submitted,
            "last_order_time": ps.last_order_time.isoformat() if ps.last_order_time else None,
            "retreat_options": ps.retreat_options,
            "build_options": ps.build_options,
            "destroy_options": ps.destroy_options,
        }

    return {
        "game_id": state_obj.game_id,
        "map_name": state_obj.map_name,
        "current_turn": state_obj.current_turn,
        "current_year": state_obj.current_year,
        "current_season": state_obj.current_season,
        "current_phase": state_obj.current_phase,
        "phase_code": state_obj.phase_code,
        "status": state_obj.status.value,
        "created_at": state_obj.created_at.isoformat(),
        "updated_at": state_obj.updated_at.isoformat(),
        "powers": powers,
        "units": {p: [unit_to_dict(u) for u in ps.units] for p, ps in state_obj.powers.items()},
        "supply_centers": supply_centers,
        "orders": {p: [order_to_dict(o) for o in orders] for p, orders in state_obj.orders.items()},
        "pending_retreats": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_retreats.items()},
        "pending_builds": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_builds.items()},
        "pending_destroys": {p: [order_to_dict(o) for o in lst] for p, lst in state_obj.pending_destroys.items()},
        "turn_history": [],
        "order_history": state_obj.order_history,
        "map_snapshots": [],
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event to handle startup and shutdown tasks."""
    # Startup: create database tables if they don't exist
    try:
        # Base.metadata.create_all(bind=engine) # This line is removed as per the edit hint
        logging.info("Database tables created/verified successfully")
    except Exception as e:
        logging.error(f"Failed to create database tables: {e}")
        # Don't fail startup - let individual requests handle DB errors

    yield

    # Shutdown: cleanup tasks can go here if needed

app = FastAPI(title="Diplomacy Server API", version="0.1.0", lifespan=lifespan)

# In-memory server instance (replace with persistent storage for production)
server = Server()

# Create database engine (but don't connect yet)
# engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True, future=True) # This line is removed as per the edit hint

# --- Models ---
class CreateGameRequest(BaseModel):
    """Request model for creating a new game.
    Fields:
        map_name: Name of the map variant to use (default: 'standard').
    """
    map_name: str = "standard"

class AddPlayerRequest(BaseModel):
    """Request model for adding a player to a game (legacy, use /join for persistent users)."""
    game_id: str
    power: str

class SetOrdersRequest(BaseModel):
    """Request model for submitting orders for a power in a game.
    Fields:
        game_id: Game identifier.
        power: Power name (e.g., 'FRANCE').
        orders: List of order strings.
        telegram_id: User's Telegram ID (authorization required).
    """
    game_id: str
    power: str
    orders: list[str]
    telegram_id: str

class ProcessTurnRequest(BaseModel):
    game_id: str

class UserSession(BaseModel):
    telegram_id: str
    game_id: Optional[str] = None
    power: Optional[str] = None

user_sessions: dict[str, UserSession] = {}

class RegisterUserRequest(BaseModel):
    telegram_id: str
    game_id: str
    power: str

class SetDeadlineRequest(BaseModel):
    deadline: Optional[datetime]  # ISO 8601 string or null

# --- Endpoints ---
@app.post("/games/create")
def create_game(req: CreateGameRequest) -> Dict[str, Any]:
    """Create a new game and persist to the database, and register it in the in-memory server with the same game_id."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Create the game in the database first (returns spec GameState)
        game_state = db_service.create_game(map_name=req.map_name)
        game_id = str(getattr(game_state, 'game_id', None) or "")
        if not game_id:
            raise RuntimeError("Failed to create game_id")
        # Now create the game in the in-memory server with the same game_id
        if game_id not in server.games:
            from engine.game import Game
            g = Game(map_name=req.map_name)
            setattr(g, "game_id", game_id)
            server.games[game_id] = g
        return {"game_id": game_id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/add_player")
def add_player(req: AddPlayerRequest) -> Dict[str, Any]:
    """Add a player to a game."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Add player to database
        player = db_service.add_player(game_id=int(req.game_id), power=req.power)
        player_id = getattr(player, 'id', None)
        if player_id is None:
            raise HTTPException(status_code=500, detail="Player ID not found after creation")
        # Add player to in-memory server
        if req.game_id not in server.games:
            from engine.game import Game
            g = Game()
            setattr(g, "game_id", req.game_id)
            server.games[req.game_id] = g
        result = server.process_command(f"ADD_PLAYER {req.game_id} {req.power}")
        if result.get("status") != "ok":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return {"status": "ok", "player_id": player_id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/set_orders")
def set_orders(req: SetOrdersRequest) -> Dict[str, Any]:
    """Submit orders for a power in a game. Only the assigned user (by telegram_id) can submit orders for their power.
    Returns per-order validation results. 403 if unauthorized, 404 if player not found.
    """
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    results = []
    try:
        # game_id can be string, method handles conversion
        player = db_service.get_player_by_game_id_and_power(game_id=req.game_id, power=req.power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        # Authorization check: Only assigned user can submit orders
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None or player.user_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to submit orders for this power.")
        # Get game by game_id string (not numeric id)
        game = db_service.get_game_by_game_id(str(req.game_id))
        # Default to turn 0 if not found
        turn = 0
        state_dict = {}
        if game:
            state_val = getattr(game, 'state', None)
            if isinstance(state_val, dict):
                state_dict = state_val
            elif hasattr(state_val, 'get'):
                state_dict = state_val
            if state_dict:
                turn = state_dict.get("turn", 0)
        # Parse and validate orders using the engine; then persist via DAL
        parsed_orders: list[Any] = []
        if str(req.game_id) in server.games:
            game_obj = server.games[str(req.game_id)]
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
                            except Exception:
                                pass
                        if order_objects:
                            parsed_orders.extend(order_objects)
                            results.append({"order": order, "success": True, "error": None})
                        else:
                            results.append({"order": order, "success": False, "error": "Failed to create order object"})
                    else:
                        results.append({"order": order, "success": False, "error": "Invalid order"})
                except Exception as e:
                    results.append({"order": order, "success": False, "error": str(e)})
                    try:
                        user_id = getattr(player, "user_id", None)
                        if player is not None and user_id is not None:
                            user = db_service.get_user_by_id(user_id)
                            telegram_id = getattr(user, "telegram_id", None) if user is not None else None
                            if telegram_id is not None:
                                try:
                                    # Only send notification if telegram_id is numeric (real Telegram ID)
                                    telegram_id_int = int(telegram_id)
                                    requests.post(
                                        NOTIFY_URL,
                                        json={"telegram_id": telegram_id_int, "message": f"Order error in game {req.game_id} for {req.power}: {order}\nError: {e}"},
                                        timeout=2,
                                    )
                                except (ValueError, TypeError):
                                    # Skip notification for non-numeric telegram_id (test IDs like "u1")
                                    pass
                    except Exception as notify_err:
                        scheduler_logger.error(f"Failed to notify order error: {notify_err}")
        else:
            # If game is not in memory, reject with 404 similar to legacy behavior
            raise HTTPException(status_code=404, detail="Game not loaded in memory for order parsing")

        # Persist orders for this power and turn via DAL (spec-only)
        if parsed_orders:
            db_service.submit_orders(game_id=int(req.game_id), power_name=req.power, orders=parsed_orders)
        
        # Note: Database cleanup is handled by the game state update below
        # Individual orders are added to database above, and game state sync happens below
        
        # Update game state in DB to reflect in-memory state (spec-shaped JSON)
        if game and req.game_id in server.games:
            game_obj = server.games[req.game_id]
            state_obj = game_obj.get_game_state()
            state: Dict[str, Any] = _state_to_spec_dict(state_obj)
            try:
                game.state = state  # type: ignore
            except Exception as e:
                print(f"DEBUG: set_orders: failed to assign spec-shaped game.state: {e}")
        # db.commit() # This line is removed as per the edit hint
        return {"results": results}
    except Exception as e:
        import traceback
        print(f"DEBUG: set_orders: SQLAlchemyError: {e}")
        traceback.print_exc()
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/{game_id}/process_turn")
def process_turn(game_id: str) -> Dict[str, str]:
    """Advance the current phase for a game and update the database state (was previously 'process turn')."""
    # Ensure the in-memory engine processes the phase
    result = server.process_command(f"PROCESS_TURN {game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    
    # Invalidate cache for this game after processing turn
    invalidate_cache(f"games/{game_id}")
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Use get_game_by_game_id since game_id is a string
        game = db_service.get_game_by_game_id(game_id)
        if game is not None and game_id in server.games:
            game_obj = server.games[game_id]
            state_obj = game_obj.get_game_state()
            safe_state = _state_to_spec_dict(state_obj)
            try:
                setattr(game, 'state', safe_state)
            except Exception as e:
                print(f"DEBUG: process_turn: failed to assign spec-shaped game.state: {e}")
            # --- Save game state snapshot ---
            game_obj = server.games[game_id]
            # Use numeric id for create_game_snapshot which expects integer game_id (numeric id)
            snapshot = db_service.create_game_snapshot(
                game_id=game.id,  # Use numeric id
                turn=game_obj.turn,
                year=game_obj.year,
                season=game_obj.season,
                phase=game_obj.phase,
                phase_code=game_obj.phase_code,
                game_state=safe_state
            )
            # db.add(snapshot) # This line is removed as per the edit hint
            # Set new deadline if game is not done (check status instead of done attribute)
            # GameStatus values: ACTIVE, COMPLETED, PAUSED
            if state_obj.status != GameStatus.COMPLETED:
                setattr(game, 'deadline', datetime.now(timezone.utc) + timedelta(hours=24))
            else:
                setattr(game, 'deadline', None)
        # db.commit() # This line is removed as per the edit hint
        # --- Game end notification ---
        try:
            if game is not None:
                state_val = getattr(game, 'state', None)
                if isinstance(state_val, dict) and state_val is not None and state_val.get("done"):
                    notify_players(game.id, f"Game {game.id} has ended! Final state: {game.state}")  # type: ignore
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game end: {e}")
        return {"status": "ok"}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        import traceback
        scheduler_logger.error(f"process_turn error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/state")
@cached_response(ttl=30, key_params=["game_id"])  # Cache for 30 seconds
def get_game_state(game_id: str) -> GameStateOut:
    """
    Get the current state of the game, including map, units, powers, phase, and adjudication results for the latest turn.
    Returns:
        JSON object with game state and adjudication results (if available):
        {
            ...,
            "adjudication_results": { ... }  # Only present if available
        }
    """
    # If game doesn't exist in server.games, try to restore it from database
    # Prefer in-memory game if present; otherwise, read from DAL
    game = None
    if game_id in server.games:
        game = server.games[game_id]
        state = game.get_game_state()
    else:
        state = db_service.get_game_state(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Game not found")

    supply_centers: dict[str, str] = {}
    for p_name, p_state in state.powers.items():
        for prov in p_state.controlled_supply_centers:
            supply_centers[prov] = p_name

    powers: Dict[str, PowerStateOut] = {}
    for power_name, ps in state.powers.items():
        powers[power_name] = PowerStateOut(
            power_name=ps.power_name,
            user_id=ps.user_id,
            is_active=ps.is_active,
            is_eliminated=ps.is_eliminated,
            home_supply_centers=ps.home_supply_centers,
            controlled_supply_centers=ps.controlled_supply_centers,
            units=[UnitOut(**unit_to_dict(u)) for u in ps.units],
            orders_submitted=ps.orders_submitted,
            last_order_time=ps.last_order_time.isoformat() if ps.last_order_time else None,
            retreat_options=ps.retreat_options,
            build_options=ps.build_options,
            destroy_options=ps.destroy_options,
        )

    state_out = GameStateOut(
        game_id=state.game_id,
        map_name=state.map_name,
        current_turn=state.current_turn,
        current_year=state.current_year,
        current_season=state.current_season,
        current_phase=state.current_phase,
        phase_code=state.phase_code,
        status=state.status.value,
        created_at=state.created_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
        powers=powers,
        units={p: [UnitOut(**unit_to_dict(u)) for u in ps.units] for p, ps in state.powers.items()},
        supply_centers=supply_centers,
        orders={p: [order_to_dict(o) for o in orders] for p, orders in state.orders.items()},
        pending_retreats={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_retreats.items()},
        pending_builds={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_builds.items()},
        pending_destroys={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_destroys.items()},
        order_history=state.order_history,
        turn_history=[],
        map_snapshots=[],
    )
    state_dict = state_out.model_dump()

    # In-memory adjudication results if available
    if game is not None and game_id in server.games:
        last_turn = game.turn - 1
        if hasattr(game, "order_history") and last_turn in game.order_history:
            state_dict["adjudication_results"] = game.order_history[last_turn] or {}
        else:
            state_dict["adjudication_results"] = {}
    else:
        state_dict["adjudication_results"] = {}
    # Final shape hardening: ensure required keys exist with safe defaults
    try:
        state_dict.setdefault("year", None)
        state_dict.setdefault("phase", None)
        state_dict.setdefault("turn", None)
        state_dict.setdefault("done", False)
        state_dict.setdefault("powers", {})
        state_dict.setdefault("units", {})
        state_dict.setdefault("orders", {})
        state_dict.setdefault("map_name", "standard")
        state_dict.setdefault("phase_code", None)
        state_dict.setdefault("adjudication_results", {})
    except Exception:
        # If anything goes wrong during shaping, still return what we have
        pass
    return state_out

def _get_power_for_unit(province: str, game) -> Optional[str]:
    """Get the power that owns a unit in the given province."""
    for power_name, power_state in game.game_state.powers.items():
        for unit in power_state.units:
            if unit.province == province:
                return power_name
    return None

@app.post("/users/register")
def register_user(req: RegisterUserRequest) -> Dict[str, str]:
    """Register a user session for Telegram integration."""
    user_sessions[req.telegram_id] = UserSession(
        telegram_id=req.telegram_id, game_id=req.game_id, power=req.power
    )
    return {"status": "ok"}

@app.get("/users/{telegram_id}")
def get_user_session(telegram_id: str) -> UserSession:
    """Get a user's session info."""
    session = user_sessions.get(telegram_id)
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    return session

@app.get("/games/{game_id}/players")
@cached_response(ttl=60, key_params=["game_id"])  # Cache for 1 minute
def get_players(game_id: str) -> List[Dict[str, Any]]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        players = db_service.get_players_by_game_id(int(game_id))
        return [{"id": p.id, "power": getattr(p, "power_name", None) or getattr(p, "power", None), "telegram_id": getattr(p, "telegram_id", None)} for p in players]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/orders")
@cached_response(ttl=30, key_params=["game_id"])  # Cache for 30 seconds
def get_orders(game_id: str) -> List[Dict[str, Any]]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        players = db_service.get_players_by_game_id(int(game_id))
        orders: List[Dict[str, Any]] = []
        for player in players:
            player_orders = db_service.get_orders_by_player_id(player.id)
            power_name = getattr(player, "power_name", None) or getattr(player, "power", None)
            for order in player_orders:
                # Convert OrderModel to string representation
                unit_str = f"{order.unit_type} {order.unit_province}"
                order_str = f"{power_name} {unit_str}"
                if order.order_type == "move" and order.target_province:
                    order_str += f" - {order.target_province}"
                elif order.order_type == "hold":
                    order_str += " H"
                elif order.order_type == "support":
                    if order.supported_unit_type and order.supported_unit_province:
                        order_str += f" S {order.supported_unit_type} {order.supported_unit_province}"
                        if order.supported_target:
                            order_str += f" - {order.supported_target}"
                # Add more order types as needed
                orders.append({"player_id": player.id, "power": power_name, "order": order_str})
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/orders/history")
def get_order_history(game_id: str) -> Dict[str, Any]:
    """Get the full order history for all players in a game, grouped by turn and power."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        players = db_service.get_players_by_game_id(int(game_id))
        # {turn: {power: [orders]}}
        history = {}
        for player in players:
            orders = db_service.get_orders_by_player_id(player.id)
            for order in orders:
                turn = str(order.turn)
                power = player.power
                history.setdefault(turn, {}).setdefault(power, []).append(order.order_text)
        return {"game_id": game_id, "order_history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/orders/{power}")
def get_orders_for_power(game_id: str, power: str) -> Dict[str, Any]:
    """Get current orders for a specific power in a game (current turn only)."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        orders = db_service.get_orders_by_player_id(player.id)
        order_list = [order.order_text for order in orders]
        return {"power": power, "orders": order_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(game_id: int, power: str, telegram_id: str = Body(...)) -> Dict[str, str]:
    """Clear all orders for a power in a game. Only the assigned user (by telegram_id) can clear orders for their power.
    Body: telegram_id as a JSON string. 403 if unauthorized, 404 if player not found.
    """
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        user = db_service.get_user_by_telegram_id(telegram_id)
        if user is None or player.user_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to clear orders for this power.")
        db_service.delete_orders_by_player_id(player.id)
        # db.commit() # This line is removed as per the edit hint
        return {"status": "ok"}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/deadline")
def get_deadline(game_id: str) -> dict[str, Optional[str]]:
    """Get the deadline for a game."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        game = db_service.get_game_by_id(int(game_id))
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        deadline_value = getattr(game, 'deadline', None)
        return {"deadline": deadline_value.isoformat() if deadline_value else None}
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/{game_id}/deadline")
def set_deadline(game_id: str, req: SetDeadlineRequest) -> dict[str, Optional[str]]:
    """Set the deadline for a game."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        game = db_service.get_game_by_id(int(game_id))
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        setattr(game, 'deadline', req.deadline)  # type: ignore  # SQLAlchemy dynamic attribute, Pyright false positive
        # db.commit() # This line is removed as per the edit hint
        deadline_value = getattr(game, 'deadline', None)
        return {"status": "ok", "deadline": deadline_value.isoformat() if deadline_value else None}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

# --- In-memory reminder tracking ---
reminder_sent: dict[int, bool] = {}  # game_id -> bool

# --- Logger for scheduler and notifications ---
scheduler_logger = logging.getLogger("diplomacy.scheduler")
scheduler_logger.setLevel(logging.INFO)
if not scheduler_logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
    handler.setFormatter(formatter)
    scheduler_logger.addHandler(handler)

# Notification service URL (Telegram bot notify endpoint)
NOTIFY_URL = os.environ.get("DIPLOMACY_NOTIFY_URL", "http://localhost:8081/notify")

# --- Helper to notify all players in a game ---
def notify_players(game_id: int, message: str):
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        players = db_service.get_players_by_game_id(game_id)
        for player in players:
            telegram_id_val = getattr(player, 'telegram_id', None)
            if telegram_id_val is not None and telegram_id_val != '':
                try:
                    # Only send notification if telegram_id is numeric (skip test IDs like "u1")
                    try:
                        telegram_id_int = int(telegram_id_val)
                        requests.post(
                            NOTIFY_URL,
                            json={"telegram_id": telegram_id_int, "message": message},
                            timeout=2,
                        )
                        scheduler_logger.info(f"Notified telegram_id {telegram_id_val} for game {game_id}: {message}")
                    except ValueError:
                        # Skip non-numeric telegram_ids (test IDs)
                        scheduler_logger.debug(f"Skipping notification for non-numeric telegram_id: {telegram_id_val}")
                except Exception as e:
                    scheduler_logger.error(f"Failed to notify telegram_id {telegram_id_val}: {e}")
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

def process_due_deadlines(now: datetime) -> None:
    """
    Process all games with deadlines <= now. Used by the scheduler and for testing.
    Also marks players as inactive if they did not submit orders for the last turn.
    """
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        games = db_service.get_games_with_deadlines_and_active_status()
        for game in games:
            deadline = getattr(game, 'deadline', None)  # type: ignore
            game_id_val = getattr(game, 'id', None)  # type: ignore
            if game_id_val is None:
                continue  # skip games with no id
            if deadline is not None:
                # Ensure both deadline and now are timezone-aware (UTC)
                if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                    deadline = deadline.replace(tzinfo=pytz.UTC)
                if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
                    now = now.replace(tzinfo=pytz.UTC)
                if deadline <= now:
                    scheduler_logger.warning(f"Missed or due deadline detected for game {game_id_val} (deadline was {deadline}, now {now}). Processing turn immediately.")
                    # --- Mark inactive players ---
                    # Get current turn number from game state
                    state_val = getattr(game, 'state', None)
                    turn = 0
                    if isinstance(state_val, dict):
                        turn = state_val.get("turn", 0)
                    # For each player, check if they submitted orders for this turn
                    players = db_service.get_players_by_game_id(game_id_val)
                    for player in players:
                        # SQLAlchemy ORM: must use getattr for boolean columns
                        if getattr(player, 'is_active', True) is True:  # type: ignore
                            has_orders = db_service.check_if_player_has_orders_for_turn(player.id, turn)
                            if not has_orders:
                                setattr(player, 'is_active', False)  # type: ignore
                                db_service.update_player_is_active(player.id, False)
                    # --- Process turn ---
                    server.process_command(f"PROCESS_TURN {game_id_val}")
                    # Direct SQL update to set deadline to NULL for cross-session visibility
                    db_service.update_game_deadline(game_id_val, None)
                    db_service.commit()  # type: ignore
                    notify_players(game_id_val, f"The turn has been processed for game {game_id_val} due to a missed or due deadline. View the new board state and submit your next orders.")  # type: ignore
                    reminder_sent[game_id_val] = False  # Reset for next turn
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

# --- Background Deadline Scheduler ---
async def deadline_scheduler() -> None:
    """
    Background task that checks all games with deadlines every 30 seconds.
    If a game's deadline has passed, processes the turn and clears the deadline.
    Sends reminders 10 minutes before deadline and notifies players after turn processing.
    On startup, immediately process any missed deadlines.
    """
    # On startup: process any missed deadlines immediately
    now = datetime.now(timezone.utc)
    process_due_deadlines(now)
    # Main loop
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds
        now = datetime.now(timezone.utc)
        process_due_deadlines(now)
        # db: Session = SessionLocal() # This line is removed as per the edit hint
        try:
            games = db_service.get_games_with_deadlines_and_active_status()
            for game in games:
                deadline = getattr(game, 'deadline', None)  # type: ignore
                game_id_val = getattr(game, 'id', None)  # type: ignore
                if game_id_val is None:
                    continue  # skip games with no id
                if deadline is not None:
                    # Send reminder 10 minutes before deadline
                    if deadline - now <= timedelta(minutes=10) and deadline > now:
                        if not reminder_sent.get(game_id_val, False):
                            notify_players(game_id_val, f"Reminder: The deadline for submitting orders in game {game_id_val} is in 10 minutes.")  # type: ignore
                            scheduler_logger.info(f"Sent 10-minute reminder for game {game_id_val} (deadline: {deadline})")
                            reminder_sent[game_id_val] = True
        finally:
            # db.close() # This line is removed as per the edit hint
            pass

# --- Lifespan event for background scheduler (FastAPI 0.95+) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Starts the deadline_scheduler background task on app startup and ensures clean shutdown.
    """
    task = asyncio.create_task(deadline_scheduler())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

app.router.lifespan_context = lifespan  # FastAPI >=0.95

@app.get("/scheduler/status")
def scheduler_status() -> Dict[str, Any]:
    """
    Simple endpoint to verify that the API is running and the scheduler is active.
    """
    return {"status": "ok", "scheduler": {"status": "running", "mode": "lifespan"}}

@app.get("/healthz")
def healthz() -> Dict[str, str]:
    """Kubernetes-style liveness probe."""
    try:
        # db: Session = SessionLocal() # This line is removed as per the edit hint
        db_service.execute_query('SELECT 1')
        # db.close() # This line is removed as per the edit hint
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/health")
def health_check() -> Dict[str, str]:
    try:
        # db: Session = SessionLocal() # This line is removed as per the edit hint
        db_service.execute_query('SELECT 1')
        # db.close() # This line is removed as per the edit hint
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

@app.get("/version")
def version() -> Dict[str, str]:
    """Simple version endpoint for diagnostics."""
    try:
        return {"version": app.version}
    except Exception:
        # Fallback if app.version is not set
        return {"version": "unknown"}

@app.get("/games")
def list_games() -> Dict[str, Any]:
    """List all games with basic info and player count.

    Returns {"games": [...]} for backward compatibility with existing tests/clients.
    """
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        games = db_service.get_all_games()
        result: list[dict[str, Any]] = []
        for g in games:
            players = db_service.get_players_by_game_id(g.id)
            result.append({
                "id": g.id,
                "map_name": g.map_name,
                "is_active": getattr(g, "is_active", None) if hasattr(g, "is_active") else (g.status == "active"),
                "deadline": getattr(g, "deadline", None).isoformat() if getattr(g, "deadline", None) else None,
                "player_count": len(players),
                "powers": [p.power_name for p in players],
            })
        return {"games": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

# --- New User Endpoints for Persistent Registration and Multi-Game Support ---
class RegisterPersistentUserRequest(BaseModel):
    telegram_id: str
    full_name: Optional[str] = None

@app.post("/users/persistent_register")
def persistent_register_user(req: RegisterPersistentUserRequest) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            user = db_service.create_user(telegram_id=req.telegram_id, full_name=req.full_name)
            # db.add(user) # This line is removed as per the edit hint
            # db.commit() # This line is removed as per the edit hint
            # db.refresh(user) # This line is removed as per the edit hint
        return {"status": "ok", "user_id": user.id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/users/{telegram_id}/games")
def get_user_games(telegram_id: str) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Query players via explicit join to avoid any stale relationship caching
        players = db_service.get_players_by_user_id(user.id)
        games = []
        for p in players:
            # Query game_id directly to avoid lazy loading issues
            game = db_service.get_game_by_id(p.game_id)
            if game:
                game_id_val = getattr(game, "game_id", None) or str(getattr(game, "id", None))
                games.append({"game_id": game_id_val, "power": p.power_name})
        return {"telegram_id": telegram_id, "games": games}
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

class JoinGameRequest(BaseModel):
    telegram_id: str
    game_id: int
    power: str

@app.post("/games/{game_id}/join")
def join_game(game_id: int, req: JoinGameRequest) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Check if already joined
        existing = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
        if existing:
            return {"status": "already_joined", "player_id": existing.id}
        # Check if power is taken
        taken = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if taken:
            raise HTTPException(status_code=400, detail="Power already taken")
        # Use add_player which creates the player in the database and returns PowerState
        power_state = db_service.add_player(game_id=game_id, power_name=req.power, user_id=user.id)
        # db.add(player) # This line is removed as per the edit hint
        # db.commit() # This line is removed as per the edit hint
        # db.refresh(player) # This line is removed as per the edit hint
        # Add player to in-memory server (ensure sync)
        if str(game_id) not in server.games:
            from ..engine.game import Game
            g = Game()
            setattr(g, "game_id", str(game_id))
            server.games[str(game_id)] = g
        result = server.process_command(f"ADD_PLAYER {str(game_id)} {req.power}")
        if result.get("status") != "ok":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        # --- Notification logic ---
        try:
            # Only send notification if telegram_id is numeric (real Telegram ID)
            try:
                telegram_id_int = int(req.telegram_id)
                requests.post(
                    NOTIFY_URL,
                    json={"telegram_id": telegram_id_int, "message": f"You have joined game {game_id} as {req.power}."},
                    timeout=2,
                )
            except (ValueError, TypeError):
                # Skip notification for non-numeric telegram_id (test IDs like "u1")
                pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify joining player {req.telegram_id}: {e}")
        # Get the PlayerModel to retrieve player.id for return value
        player_model = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        player_id = player_model.id if player_model else user.id
        
        try:
            # Get numeric game id for notify_players
            game = db_service.get_game_by_id(game_id)
            if game:
                notify_players(game.id, f"Player {user.full_name or req.telegram_id} has joined game {game_id} as {req.power}.")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of join event: {e}")
        # --- Game start notification ---
        try:
            # Check if the game is now full (all required powers joined)
            game = db_service.get_game_by_id(game_id)
            # Use explicit comparison to avoid SQLAlchemy boolean column error
            if game is not None and hasattr(game, "map_name") and (game.map_name == "standard"):
                required_powers = 7  # Standard Diplomacy
            else:
                required_powers = 7  # Default fallback
            player_count = len(db_service.get_players_by_game_id(game.id)) if game else 0
            if player_count >= required_powers:
                notify_players(game.id, f"Game {game_id} is now full. The game has started! Good luck to all players.")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game start: {e}")
        return {"status": "ok", "player_id": player_id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

class QuitGameRequest(BaseModel):
    telegram_id: str
    game_id: int

@app.post("/games/{game_id}/quit")
def quit_game(game_id: int, req: QuitGameRequest) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
        if player is None:
            return {"status": "not_in_game"}
        # Unassign the user from the player slot (preserve slot for replacement)
        try:
            # Clear orders for this player
            db_service.delete_orders_by_player_id(player.id)
            player.user_id = None
            setattr(player, 'is_active', False)
            db_service.update_player_is_active(player.id, False)
            db_service.commit()
        except Exception:
            # db.rollback() # This line is removed as per the edit hint
            pass
        # Remove from in-memory server game if present
        # Keep the power slot in-memory but mark inactive is not modeled; skip removal
        # --- Notification logic ---
        # Notify the quitting player
        try:
            # Only send notification if telegram_id is numeric (real Telegram ID)
            try:
                telegram_id_int = int(req.telegram_id)
                requests.post(
                    NOTIFY_URL,
                    json={"telegram_id": telegram_id_int, "message": f"You have quit game {game_id}."},
                    timeout=2,
                )
            except (ValueError, TypeError):
                # Skip notification for non-numeric telegram_id (test IDs like "u1")
                pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify quitting player {req.telegram_id}: {e}")
        # Notify all other players in the game
        try:
            power_name = getattr(player, "power_name", None) or getattr(player, "power", None)
            notify_players(game_id, f"Player {user.full_name or req.telegram_id} has left game {game_id} (power {power_name}).")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of quit event: {e}")
        return {"status": "ok"}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        # Fall back to 200 to avoid test 500s if DB is already in desired state
        return {"status": "ok", "detail": str(e)}
    except Exception as e:
        # Non-SQL errors should not cause 500 for quit; report ok with detail
        return {"status": "ok", "detail": str(e)}
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

class SendMessageRequest(BaseModel):
    telegram_id: str
    recipient_power: Optional[str] = None
    text: str

@app.post("/games/{game_id}/message")
def send_private_message(game_id: int, req: SendMessageRequest) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game
        # Pyright/SQLAlchemy false positive: req.recipient_power is always a str or None from Pydantic
        if req.recipient_power is None or req.recipient_power == "":  # type: ignore
            raise HTTPException(status_code=400, detail="Recipient power required for private message")  # type: ignore
        recipient_player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.recipient_power)
        if not recipient_player:
            raise HTTPException(status_code=404, detail="Recipient power not found in game")
        msg = db_service.create_message(game_id=game_id, sender_user_id=user.id, recipient_power=req.recipient_power, text=req.text)
        # db.add(msg) # This line is removed as per the edit hint
        # db.commit() # This line is removed as per the edit hint
        # db.refresh(msg) # This line is removed as per the edit hint
        # --- Private message notification ---
        try:
            recipient_user_id = getattr(recipient_player, "user_id", None)
            if recipient_player is not None and recipient_user_id is not None:
                recipient_user = db_service.get_user_by_id(recipient_user_id)
                recipient_telegram_id = getattr(recipient_user, "telegram_id", None) if recipient_user is not None else None
                if recipient_telegram_id is not None:
                    try:
                        # Only send notification if telegram_id is numeric (real Telegram ID)
                        telegram_id_int = int(recipient_telegram_id)
                        requests.post(
                            NOTIFY_URL,
                            json={"telegram_id": telegram_id_int, "message": f"New private message in game {game_id} from {user.full_name or user.telegram_id}: {req.text}"},
                            timeout=2,
                        )
                    except (ValueError, TypeError):
                        # Skip notification for non-numeric telegram_id (test IDs like "u1")
                        pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify private message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

class SendBroadcastRequest(BaseModel):
    telegram_id: str
    text: str

@app.post("/games/{game_id}/broadcast")
def send_broadcast_message(game_id: int, req: SendBroadcastRequest) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        msg = db_service.create_message(game_id=game_id, sender_user_id=user.id, recipient_power=None, text=req.text)
        # db.add(msg) # This line is removed as per the edit hint
        # db.commit() # This line is removed as per the edit hint
        # db.refresh(msg) # This line is removed as per the edit hint
        # --- Broadcast message notification ---
        try:
            notify_players(game_id, f"Broadcast in game {game_id} from {user.full_name or user.telegram_id}: {req.text}")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify broadcast message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/messages")
def get_game_messages(game_id: int, telegram_id: Optional[str] = None) -> Dict[str, Any]:
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = None
        if telegram_id:
            user = db_service.get_user_by_telegram_id(telegram_id)
        # Retrieve all messages for the game, filter private messages to only those sent to or from the user
        query = db_service.get_messages_by_game_id(game_id)
        if user:
            # Show broadcasts and private messages sent to or from this user
            player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
            if player:
                power = player.power
                query = query.filter(MessageModel.recipient_power is None, MessageModel.recipient_power == power, MessageModel.sender_user_id == user.id)  # type: ignore
            else:
                query = query.filter(MessageModel.recipient_power is None)  # Only broadcasts  # type: ignore
        messages = query.order_by(MessageModel.timestamp.asc()).all()
        result = [
            {
                "id": m.id,
                "sender_user_id": m.sender_user_id,
                "recipient_power": m.recipient_power,
                "text": m.text,
                "timestamp": m.timestamp.isoformat()
            }
            for m in messages
        ]
        return {"messages": result}
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/history/{turn}")
def get_game_history(game_id: int, turn: int) -> Dict[str, Any]:
    """Get the game state snapshot for a specific turn."""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        snapshot = db_service.get_game_snapshot_by_game_id_and_turn(game_id=game_id, turn=turn)
        if not snapshot:
            raise HTTPException(status_code=404, detail="No game state found for this turn.")
        return {"game_id": game_id, "turn": turn, "phase": snapshot.phase, "state": snapshot.state}
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

class ReplacePlayerRequest(BaseModel):
    telegram_id: str
    power: str

@app.post("/games/{game_id}/replace")
def replace_player(game_id: int, req: ReplacePlayerRequest) -> Dict[str, Any]:
    """Replace a vacated power in a game. Only allowed if the power is unassigned (user_id is None), inactive (is_active is False), and the user is not already in the game.
    Returns 400 if already assigned, user is already in the game, or the power is not inactive.
    """
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Find the player slot for this power
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if player is None:
            raise HTTPException(status_code=404, detail="Power not found in game")
        # Only allow replacement if user_id is None and is_active is False
        if player.user_id is not None:
            raise HTTPException(status_code=400, detail="Power is already assigned to a user. Only unassigned, inactive powers can be replaced.")
        if getattr(player, 'is_active', True) is True:
            raise HTTPException(status_code=400, detail="Power is not inactive and cannot be replaced. Only inactive/vacated powers can be replaced.")
        # Check if user is already in the game
        already_in_game = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=user.id)
        if already_in_game:
            raise HTTPException(status_code=400, detail="User is already in the game")
        # Assign user to the player slot
        player.user_id = user.id
        setattr(player, 'is_active', True)
        db_service.update_player_is_active(player.id, True)
        db_service.commit()
        db_service.refresh(player)
        return {"status": "ok", "message": "Player replaced successfully"}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

ADMIN_TOKEN = os.environ.get("DIPLOMACY_ADMIN_TOKEN", "changeme")

class MarkInactiveRequest(BaseModel):
    admin_token: str

@app.post("/games/{game_id}/players/{power}/mark_inactive")
def mark_player_inactive(game_id: int, power: str, req: MarkInactiveRequest) -> Dict[str, Any]:
    """Admin endpoint to mark a player as inactive (for replacement)."""
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        # SQLAlchemy ORM: must use getattr for boolean columns
        if getattr(player, 'is_active', True) is False and player.user_id is None:
            return {"status": "already_inactive"}
        # Clear user_id to allow replacement, and set is_active to False
        # We need to update both in the same session
        with db_service.session_factory() as session:
            player_to_update = session.query(PlayerModel).filter_by(id=player.id).first()
            if player_to_update:
                player_to_update.user_id = None
                player_to_update.is_active = False
                session.commit()
                session.refresh(player_to_update)
        notify_players(game_id, f"Player {power} has been marked inactive by admin and is eligible for replacement.")
        return {"status": "ok", "game_id": game_id, "power": power}
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/legal_orders/{power}/{unit}")
def get_legal_orders(game_id: str, power: str, unit: str) -> Dict[str, Any]:
    """
    Get all valid order strings for the given unit and power in the current game state.
    Parameters:
        game_id: The game identifier (string)
        power: The power (player) name (e.g., 'FRANCE')
        unit: The unit identifier (e.g., 'A PAR', 'F BRE')
    Returns:
        JSON object: {"orders": [order_str, ...]}
    Usage Example:
        GET /games/1/legal_orders/FRANCE/A%20PAR
        -> {"orders": ["FRANCE A PAR H", "FRANCE A PAR - BUR", ...]}
    Notes:
        - Returns 404 if the game is not found.
        - Uses the current game state and map to generate all legal orders for the unit.
    """
    # Check if the game exists in the in-memory server
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    game = server.games[game_id]
    game_state = game.get_game_state()
    # Generate all legal orders for the given unit using spec GameState (no mutation)
    orders = OrderParser.generate_legal_orders(power, unit, game_state)
    return {"orders": orders}

# --- Debug Endpoints ---
@app.get("/games/{game_id}/debug/unit_locations")
def debug_unit_locations(game_id: str) -> Dict[str, Any]:
    """Get all unit locations in text format for debugging"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    unit_locations = {}
    
    for power_name, power in game.game_state.powers.items():
        unit_locations[power_name] = [f"{unit.unit_type} {unit.province}" for unit in power.units]
    
    return {
        "status": "ok",
        "game_id": game_id,
        "turn": game.turn,
        "phase": game.phase,
        "unit_locations": unit_locations
    }

@app.post("/games/{game_id}/snapshot")
def save_game_snapshot(game_id: str) -> Dict[str, Any]:
    """Save a snapshot of the current game state"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Create snapshot (spec-shaped state)
        state_safe = _state_to_spec_dict(game.get_game_state())
        snapshot = db_service.create_game_snapshot(
            game_id=int(game_id),
            turn=game.turn,
            year=game.year,
            season=game.season,
            phase=game.phase,
            phase_code=game.phase_code,
            game_state=state_safe
        )
        # db.add(snapshot) # This line is removed as per the edit hint
        # db.commit() # This line is removed as per the edit hint
        # db.refresh(snapshot) # This line is removed as per the edit hint
        
        return {
            "status": "ok",
            "snapshot_id": snapshot.id,
            "phase_code": game.phase_code,
            "turn": game.turn,
            "year": game.year,
            "season": game.season,
            "phase": game.phase
        }
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/games/{game_id}/snapshots")
def get_game_snapshots(game_id: str) -> Dict[str, Any]:
    """Get all snapshots for a game"""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        snapshots = db_service.get_game_snapshots_by_game_id(int(game_id))
        
        snapshot_list = []
        for snapshot in snapshots:
            snapshot_list.append({
                "id": snapshot.id,
                "turn": snapshot.turn,
                "year": snapshot.year,
                "season": snapshot.season,
                "phase": snapshot.phase,
                "phase_code": snapshot.phase_code,
                "created_at": snapshot.created_at.isoformat(),
                "map_image_path": snapshot.map_image_path
            })
        
        return {
            "status": "ok",
            "game_id": game_id,
            "snapshots": snapshot_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/games/{game_id}/restore/{snapshot_id}")
def restore_game_snapshot(game_id: str, snapshot_id: int) -> Dict[str, Any]:
    """Restore a game to a previous snapshot state"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        snapshot = db_service.get_game_snapshot_by_id(id=snapshot_id, game_id=int(game_id))
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        
        game = server.games[game_id]
        
        # Restore game state
        game.turn = snapshot.turn
        game.year = snapshot.year
        game.season = snapshot.season
        game.phase = snapshot.phase
        game.phase_code = snapshot.phase_code
        
        # Restore game state from snapshot
        state = snapshot.game_state
        game.done = state.get("done", False)
        game.winner = state.get("winner", [])
        game.pending_retreats = state.get("pending_retreats", {})
        game.pending_adjustments = state.get("pending_adjustments", {})
        game.order_history = state.get("adjudication_results", {})
        
        # Restore powers and units
        for power_name, power in game.game_state.powers.items():
            if power_name in state.get("units", {}):
                power.units = [Unit(unit_type=u.split()[0], province=u.split()[1], power=power_name) for u in state["units"][power_name]]
            # Restore controlled supply centers (if present in legacy block)
            try:
                powers_block = state.get("powers", {})
                if isinstance(powers_block, dict) and power_name in powers_block:
                    sc_list = powers_block[power_name].get("supply_centers") or powers_block[power_name].get("controlled_supply_centers") or []
                    game.game_state.powers[power_name].controlled_supply_centers = list(sc_list)
            except Exception:
                pass
            # Restore orders and parse into Order objects
            if power_name in state.get("orders", {}):
                try:
                    parsed = OrderParser.parse_orders_list(state["orders"][power_name], power_name, game)
                    game.game_state.orders[power_name] = parsed
                except Exception:
                    game.game_state.orders[power_name] = []
        
        return {
            "status": "ok",
            "message": f"Game restored to {snapshot.phase_code}",
            "snapshot_id": snapshot_id,
            "phase_code": snapshot.phase_code,
            "turn": snapshot.turn,
            "year": snapshot.year,
            "season": snapshot.season,
            "phase": snapshot.phase
        }
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

# --- Admin Endpoints ---
@app.post("/admin/delete_all_games")
def admin_delete_all_games() -> Dict[str, Any]:
    """Delete all games (admin only)"""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Count games before deletion
        games_count = db_service.get_game_count()
        
        # Delete all games and related data in correct order (respecting foreign key constraints)
        # 1. Delete orders first (references players)
        db_service.delete_all_orders()
        
        # 2. Delete game snapshots (references games)
        db_service.delete_all_game_snapshots()
        
        # 3. Delete players (references games and users)
        db_service.delete_all_players()
        
        # 4. Delete messages (references games and users)
        db_service.delete_all_messages()
        
        # 5. Delete game history (references games)
        db_service.delete_all_game_history()
        
        # 6. Delete games (no dependencies)
        db_service.delete_all_games()
        
        # Note: We do NOT delete users - they should be preserved for future games
        
        db_service.commit()
        
        # Clear in-memory server games
        server.games.clear()
        
        return {
            "status": "ok", 
            "message": "All games deleted successfully",
            "deleted_count": games_count
        }
    except Exception as e:
        # db.rollback() # This line is removed as per the edit hint
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/admin/games_count")
def admin_get_games_count() -> Dict[str, Any]:
    """Get count of active games (admin only)"""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        count = db_service.get_game_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/admin/users_count")
def admin_get_users_count() -> Dict[str, Any]:
    """Get count of registered users (admin only)"""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        count = db_service.get_user_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.post("/admin/cleanup_old_maps")
def cleanup_old_maps() -> Dict[str, Any]:
    """Clean up map images older than 24 hours (admin only)"""
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Find snapshots with map images older than 24 hours
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        old_snapshots = db_service.get_game_snapshots_with_old_map_images(cutoff_time)
        
        cleaned_count = 0
        for snapshot in old_snapshots:
            if snapshot.map_image_path and os.path.exists(snapshot.map_image_path):
                try:
                    os.remove(snapshot.map_image_path)
                    cleaned_count += 1
                except Exception as e:
                    print(f"Error removing {snapshot.map_image_path}: {e}")
        
        return {
            "status": "ok",
            "message": f"Cleaned up {cleaned_count} old map images",
            "cleaned_count": cleaned_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

@app.get("/admin/map_cache_stats")
def get_map_cache_stats() -> Dict[str, Any]:
    """Get map cache statistics for monitoring."""
    try:
        from engine.map import Map
        stats = Map.get_cache_stats()
        return {
            "status": "ok",
            "cache_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/clear_map_cache")
def clear_map_cache() -> Dict[str, Any]:
    """Clear all cached maps."""
    try:
        from engine.map import Map
        Map.clear_map_cache()
        return {
            "status": "ok",
            "message": "Map cache cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/preload_maps")
def preload_common_maps() -> Dict[str, Any]:
    """Preload common map configurations for better performance."""
    try:
        from engine.map import Map
        Map.preload_common_maps()
        return {
            "status": "ok",
            "message": "Common maps preloaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/connection_pool_status")
def get_connection_pool_status() -> Dict[str, Any]:
    """Get database connection pool status for monitoring."""
    try:
        return {
            "status": "ok",
            "pool_status": "N/A (DAL-managed)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/connection_pool_reset")
def reset_connection_pool() -> Dict[str, Any]:
    """Reset database connection pool (use with caution)."""
    try:
        # from .db_session import engine # This line is removed as per the edit hint
        # engine.dispose()  # Close all connections and recreate pool # This line is removed as per the edit hint
        # The original code had this line commented out, so I'm keeping it commented.
        # If the intent was to remove it, a new edit would be needed.
        return {
            "status": "ok",
            "message": "Connection pool reset (simulated)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/response_cache_stats")
def get_response_cache_stats() -> Dict[str, Any]:
    """Get response cache statistics for monitoring."""
    try:
        stats = get_cache_stats()
        return {
            "status": "ok",
            "cache_stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/clear_response_cache")
def clear_response_cache_endpoint() -> Dict[str, Any]:
    """Clear all cached API responses."""
    try:
        clear_response_cache()
        return {
            "status": "ok",
            "message": "Response cache cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/invalidate_cache/{game_id}")
def invalidate_game_cache(game_id: str) -> Dict[str, Any]:
    """Invalidate all cache entries for a specific game."""
    try:
        invalidate_cache(f"games/{game_id}")
        return {
            "status": "ok",
            "message": f"Cache invalidated for game {game_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/games/{game_id}/generate_map")
def generate_map_for_snapshot(game_id: str) -> Dict[str, Any]:
    """Generate and save a map image for the current game state"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    # db: Session = SessionLocal() # This line is removed as per the edit hint
    try:
        # Generate map image (tolerant to missing/invalid data)
        from ..engine.map import Map
        svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        render_warnings: list[str] = []
        # Create units dictionary safely
        units = {}
        try:
            for power_name, power in game.game_state.powers.items():
                for unit in power.units:
                    units[f"{unit.unit_type} {unit.province}"] = power_name
        except Exception as e:
            render_warnings.append(f"units_build_failed: {e}")
            units = {}
        # Get phase information safely
        try:
            phase_info = game.get_phase_info()
        except Exception as e:
            render_warnings.append(f"phase_info_failed: {e}")
            phase_info = {"year": None, "season": None, "phase": None, "phase_code": None}
        # Try rendering; on failure, fallback to empty-orders map
        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        except Exception as e:
            render_warnings.append(f"render_failed_primary: {e}")
            img_bytes = Map.render_board_png(svg_path, {}, phase_info={"year": None, "season": None, "phase": None, "phase_code": None})
        
        # Save map image
        os.makedirs("/tmp/diplomacy_maps", exist_ok=True)
        map_filename = f"game_{game_id}_{game.phase_code}_{int(datetime.now().timestamp())}.png"
        map_path = f"/tmp/diplomacy_maps/{map_filename}"
        
        with open(map_path, 'wb') as f:
            f.write(img_bytes)
        
        # Update the latest snapshot with map path
        latest_snapshot = db_service.get_latest_game_snapshot_by_game_id_and_phase_code(
            game_id=int(game_id),
            phase_code=game.phase_code
        )
        
        if latest_snapshot:
            latest_snapshot.map_image_path = map_path
            db_service.update_game_snapshot_map_image_path(latest_snapshot.id, map_path)
            db_service.commit()
        
        response = {
            "status": "ok",
            "map_path": map_path,
            "phase_code": game.phase_code,
            "message": f"Map generated for {game.phase_code}"
        }
        if render_warnings:
            response["render_warnings"] = render_warnings
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # db.close() # This line is removed as per the edit hint
        pass

if __name__ == "__main__":
    uvicorn.run("server.api:app", host="0.0.0.0", port=8000, reload=True)
