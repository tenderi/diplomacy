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
from src.server.server import Server
import uvicorn
from typing import Optional, Dict, List, Any
from .db_session import SessionLocal
from .db_models import Base, GameModel, PlayerModel, OrderModel, UserModel, MessageModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from .db_config import SQLALCHEMY_DATABASE_URL
from datetime import datetime, timezone, timedelta
import asyncio
import contextlib
from contextlib import asynccontextmanager
import requests
from sqlalchemy import or_, text
import logging
import pytz
import os
from src.engine.order import OrderParser

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event to handle startup and shutdown tasks."""
    # Startup: create database tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
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
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True, future=True)

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
    db: Session = SessionLocal()
    try:
        # Create the game in the database first
        game = GameModel(map_name=req.map_name, state={"status": "ok"}, is_active=True)
        # Set default deadline 24 hours from now
        setattr(game, 'deadline', datetime.now(timezone.utc) + timedelta(hours=24))
        db.add(game)
        db.commit()
        db.refresh(game)
        game_id = str(game.id)
        # Now create the game in the in-memory server with the same game_id
        if game_id not in server.games:
            from engine.game import Game
            g = Game(map_name=req.map_name)
            setattr(g, "game_id", game_id)
            server.games[game_id] = g
        return {"game_id": game_id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/add_player")
def add_player(req: AddPlayerRequest) -> Dict[str, Any]:
    """Add a player to a game."""
    db: Session = SessionLocal()
    try:
        # Add player to database
        player = PlayerModel(game_id=int(req.game_id), power=req.power)
        db.add(player)
        db.commit()
        db.refresh(player)
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
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/set_orders")
def set_orders(req: SetOrdersRequest) -> Dict[str, Any]:
    """Submit orders for a power in a game. Only the assigned user (by telegram_id) can submit orders for their power.
    Returns per-order validation results. 403 if unauthorized, 404 if player not found.
    """
    db: Session = SessionLocal()
    results = []
    try:
        player = db.query(PlayerModel).filter_by(game_id=int(req.game_id), power=req.power).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        # Authorization check: Only assigned user can submit orders
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None or player.user_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to submit orders for this power.")
        game = db.query(GameModel).filter_by(id=int(req.game_id)).first()
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
        if player is not None:
            db.query(OrderModel).filter_by(player_id=player.id).delete()
        for order in req.orders:
            result = server.process_command(f"SET_ORDERS {req.game_id} {req.power} {order}")
            if result.get("status") == "ok":
                if player is not None:
                    db.add(OrderModel(player_id=player.id, order_text=order, turn=turn))
                results.append({"order": order, "success": True, "error": None})
            else:
                results.append({"order": order, "success": False, "error": result.get("error", "Order error")})
                # --- Order error notification ---
                try:
                    user_id = getattr(player, "user_id", None)
                    if player is not None and user_id is not None:
                        user = db.query(UserModel).filter_by(id=user_id).first()
                        telegram_id = getattr(user, "telegram_id", None) if user is not None else None
                        if telegram_id is not None:
                            requests.post(
                                "http://localhost:8081/notify",
                                json={"telegram_id": int(telegram_id), "message": f"Order error in game {req.game_id} for {req.power}: {order}\nError: {result.get('error', 'Order error')}"},
                                timeout=2,
                            )
                except Exception as e:
                    scheduler_logger.error(f"Failed to notify order error: {e}")
        # Update game state in DB to reflect in-memory state
        if game and req.game_id in server.games:
            state = server.games[req.game_id].get_state()
            if not isinstance(state, dict):
                state = dict(state)
            # Remove non-serializable objects
            if 'map_obj' in state:
                del state['map_obj']
            try:
                if isinstance(state, dict):
                    game.state = state  # type: ignore
            except Exception as e:
                print(f"DEBUG: set_orders: failed to assign game.state: {e}")
        db.commit()
        return {"results": results}
    except SQLAlchemyError as e:
        import traceback
        print(f"DEBUG: set_orders: SQLAlchemyError: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/{game_id}/process_turn")
def process_turn(game_id: str) -> Dict[str, str]:
    """Advance the current phase for a game and update the database state (was previously 'process turn')."""
    # Ensure the in-memory engine processes the phase
    result = server.process_command(f"PROCESS_TURN {game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    db: Session = SessionLocal()
    try:
        game = db.query(GameModel).filter_by(id=int(game_id)).first()
        if game is not None and game_id in server.games:
            state = server.games[game_id].get_state()
            if not isinstance(state, dict):
                state = dict(state)
            # Remove non-serializable objects
            if 'map_obj' in state:
                del state['map_obj']
            try:
                setattr(game, 'state', state)
            except Exception as e:
                print(f"DEBUG: process_turn: failed to assign game.state: {e}")
            # --- Save game state snapshot to history ---
            from .db_models import GameHistoryModel
            db.add(GameHistoryModel(
                game_id=int(game_id),
                turn=state.get("turn", 0),
                phase=state.get("phase", "unknown"),
                state=state
            ))
            # Set new deadline if game is not done
            if not state.get("done", False):
                setattr(game, 'deadline', datetime.now(timezone.utc) + timedelta(hours=24))
            else:
                setattr(game, 'deadline', None)
        db.commit()
        # --- Game end notification ---
        try:
            state_val = getattr(game, 'state', None)
            if game is not None and isinstance(state_val, dict) and state_val is not None and state_val.get("done"):
                notify_players(int(game.id), f"Game {game.id} has ended! Final state: {game.state}")  # type: ignore
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game end: {e}")
        return {"status": "ok"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/state")
def get_game_state(game_id: str) -> Dict[str, Any]:
    """
    Get the current state of the game, including map, units, powers, phase, and adjudication results for the latest turn.
    Returns:
        JSON object with game state and adjudication results (if available):
        {
            ...,
            "adjudication_results": { ... }  # Only present if available
        }
    """
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    game = server.games[game_id]
    state = game.get_state()
    # Remove non-serializable objects
    if "map_obj" in state:
        del state["map_obj"]
    # Always include adjudication_results in the state, even if empty
    last_turn = game.turn - 1
    if hasattr(game, "order_history") and last_turn in game.order_history:
        results = game.order_history[last_turn]
        state["adjudication_results"] = results if results else {}
    else:
        state["adjudication_results"] = {}
    return state

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
def get_players(game_id: str) -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        players = db.query(PlayerModel).filter(PlayerModel.game_id == int(game_id)).all()
        return [{"id": p.id, "power": p.power, "telegram_id": p.telegram_id} for p in players]
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/orders")
def get_orders(game_id: str) -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        players = db.query(PlayerModel).filter_by(game_id=int(game_id)).all()
        orders: List[Dict[str, Any]] = []
        for player in players:
            player_orders = db.query(OrderModel).filter(OrderModel.player_id == player.id).all()
            for order in player_orders:
                orders.append({"player_id": player.id, "power": player.power, "order": order.order_text})
        return orders
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/orders/history")
def get_order_history(game_id: str) -> Dict[str, Any]:
    """Get the full order history for all players in a game, grouped by turn and power."""
    db: Session = SessionLocal()
    try:
        players = db.query(PlayerModel).filter_by(game_id=int(game_id)).all()
        # {turn: {power: [orders]}}
        history = {}
        for player in players:
            orders = db.query(OrderModel).filter_by(player_id=player.id).all()
            for order in orders:
                turn = str(order.turn)
                power = player.power
                history.setdefault(turn, {}).setdefault(power, []).append(order.order_text)
        return {"game_id": game_id, "order_history": history}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/orders/{power}")
def get_orders_for_power(game_id: str, power: str) -> Dict[str, Any]:
    """Get current orders for a specific power in a game (current turn only)."""
    db: Session = SessionLocal()
    try:
        player = db.query(PlayerModel).filter(PlayerModel.game_id == int(game_id), PlayerModel.power == power).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        orders = db.query(OrderModel).filter_by(player_id=player.id).all()
        order_list = [order.order_text for order in orders]
        return {"power": power, "orders": order_list}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(game_id: int, power: str, telegram_id: str = Body(...)) -> Dict[str, str]:
    """Clear all orders for a power in a game. Only the assigned user (by telegram_id) can clear orders for their power.
    Body: telegram_id as a JSON string. 403 if unauthorized, 404 if player not found.
    """
    db: Session = SessionLocal()
    try:
        player = db.query(PlayerModel).filter(PlayerModel.game_id == int(game_id), PlayerModel.power == power).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Player not found")
        user = db.query(UserModel).filter_by(telegram_id=telegram_id).first()
        if user is None or player.user_id != user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to clear orders for this power.")
        db.query(OrderModel).filter_by(player_id=player.id).delete()
        db.commit()
        return {"status": "ok"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/deadline")
def get_deadline(game_id: str) -> dict[str, Optional[str]]:
    """Get the deadline for a game."""
    db: Session = SessionLocal()
    try:
        game = db.query(GameModel).filter_by(id=int(game_id)).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        deadline_value = getattr(game, 'deadline', None)
        return {"deadline": deadline_value.isoformat() if deadline_value else None}
    finally:
        db.close()

@app.post("/games/{game_id}/deadline")
def set_deadline(game_id: str, req: SetDeadlineRequest) -> dict[str, Optional[str]]:
    """Set the deadline for a game."""
    db: Session = SessionLocal()
    try:
        game = db.query(GameModel).filter_by(id=int(game_id)).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        setattr(game, 'deadline', req.deadline)  # type: ignore  # SQLAlchemy dynamic attribute, Pyright false positive
        db.commit()
        deadline_value = getattr(game, 'deadline', None)
        return {"status": "ok", "deadline": deadline_value.isoformat() if deadline_value else None}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

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

# --- Helper to notify all players in a game ---
def notify_players(game_id: int, message: str):
    db: Session = SessionLocal()
    try:
        players = db.query(PlayerModel).filter_by(game_id=game_id).all()
        for player in players:
            telegram_id_val = getattr(player, 'telegram_id', None)
            if telegram_id_val is not None and telegram_id_val != '':
                try:
                    requests.post(
                        "http://localhost:8081/notify",
                        json={"telegram_id": int(telegram_id_val), "message": message},
                        timeout=2,
                    )
                    scheduler_logger.info(f"Notified telegram_id {telegram_id_val} for game {game_id}: {message}")
                except Exception as e:
                    scheduler_logger.error(f"Failed to notify telegram_id {telegram_id_val}: {e}")
    finally:
        db.close()

def process_due_deadlines(now: datetime) -> None:
    """
    Process all games with deadlines <= now. Used by the scheduler and for testing.
    Also marks players as inactive if they did not submit orders for the last turn.
    """
    db: Session = SessionLocal()
    try:
        games = db.query(GameModel).filter(GameModel.deadline.isnot(None), GameModel.is_active.is_(True)).all()  # type: ignore
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
                    players = db.query(PlayerModel).filter_by(game_id=game_id_val).all()
                    for player in players:
                        # SQLAlchemy ORM: must use getattr for boolean columns
                        if getattr(player, 'is_active', True) is True:  # type: ignore
                            has_orders = db.query(OrderModel).filter_by(player_id=player.id, turn=turn).count() > 0
                            if not has_orders:
                                setattr(player, 'is_active', False)  # type: ignore
                                db.commit()
                                notify_players(game_id_val, f"Player {player.power} has been marked inactive for missing the deadline and is eligible for replacement.")
                    # --- Process turn ---
                    server.process_command(f"PROCESS_TURN {game_id_val}")
                    # Direct SQL update to set deadline to NULL for cross-session visibility
                    db.execute(
                        text("UPDATE games SET deadline = NULL WHERE id = :game_id"),
                        {"game_id": game_id_val}
                    )
                    db.commit()  # type: ignore
                    notify_players(game_id_val, f"The turn has been processed for game {game_id_val} due to a missed or due deadline. View the new board state and submit your next orders.")  # type: ignore
                    reminder_sent[game_id_val] = False  # Reset for next turn
    finally:
        db.close()  # type: ignore

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
        db: Session = SessionLocal()
        try:
            games = db.query(GameModel).filter(GameModel.deadline.isnot(None), GameModel.is_active.is_(True)).all()  # type: ignore
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
            db.close()  # type: ignore

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
def scheduler_status() -> dict[str, str]:
    """
    Simple endpoint to verify that the API is running and the scheduler is active.
    """
    return {"status": "ok", "scheduler": "running (lifespan)"}

@app.get("/health")
def health_check() -> Dict[str, str]:
    try:
        db: Session = SessionLocal()
        db.execute(text('SELECT 1'))
        db.close()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")

# --- New User Endpoints for Persistent Registration and Multi-Game Support ---
class RegisterPersistentUserRequest(BaseModel):
    telegram_id: str
    full_name: Optional[str] = None

@app.post("/users/persistent_register")
def persistent_register_user(req: RegisterPersistentUserRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            user = UserModel(telegram_id=req.telegram_id, full_name=req.full_name)
            db.add(user)
            db.commit()
            db.refresh(user)
        return {"status": "ok", "user_id": user.id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/users/{telegram_id}/games")
def get_user_games(telegram_id: str) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        games = [
            {"game_id": p.game_id, "power": p.power}
            for p in user.players
        ]
        return {"telegram_id": telegram_id, "games": games}
    finally:
        db.close()

class JoinGameRequest(BaseModel):
    telegram_id: str
    game_id: int
    power: str

@app.post("/games/{game_id}/join")
def join_game(game_id: int, req: JoinGameRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Check if already joined
        existing = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if existing:
            return {"status": "already_joined", "player_id": existing.id}
        # Check if power is taken
        taken = db.query(PlayerModel).filter_by(game_id=game_id, power=req.power).first()
        if taken:
            raise HTTPException(status_code=400, detail="Power already taken")
        player = PlayerModel(game_id=game_id, power=req.power, user_id=user.id)
        db.add(player)
        db.commit()
        db.refresh(player)
        # Add player to in-memory server (ensure sync)
        if str(game_id) not in server.games:
            from engine.game import Game
            g = Game()
            setattr(g, "game_id", str(game_id))
            server.games[str(game_id)] = g
        result = server.process_command(f"ADD_PLAYER {game_id} {req.power}")
        if result.get("status") != "ok":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        # --- Notification logic ---
        try:
            requests.post(
                "http://localhost:8081/notify",
                json={"telegram_id": int(req.telegram_id), "message": f"You have joined game {game_id} as {req.power}."},
                timeout=2,
            )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify joining player {req.telegram_id}: {e}")
        try:
            notify_players(game_id, f"Player {user.full_name or req.telegram_id} has joined game {game_id} as {req.power}.")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of join event: {e}")
        # --- Game start notification ---
        try:
            # Check if the game is now full (all required powers joined)
            game = db.query(GameModel).filter_by(id=game_id).first()
            # Use explicit comparison to avoid SQLAlchemy boolean column error
            if game is not None and hasattr(game, "map_name") and (game.map_name == "standard"):
                required_powers = 7  # Standard Diplomacy
            else:
                required_powers = 7  # Default fallback
            player_count = db.query(PlayerModel).filter_by(game_id=game_id).count()
            if player_count == required_powers:
                notify_players(game_id, f"Game {game_id} is now full. The game has started! Good luck to all players.")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game start: {e}")
        return {"status": "ok", "player_id": player.id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class QuitGameRequest(BaseModel):
    telegram_id: str
    game_id: int

@app.post("/games/{game_id}/quit")
def quit_game(game_id: int, req: QuitGameRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if player is None:
            return {"status": "not_in_game"}
        db.delete(player)
        db.commit()
        # --- Notification logic ---
        # Notify the quitting player
        try:
            requests.post(
                "http://localhost:8081/notify",
                json={"telegram_id": int(req.telegram_id), "message": f"You have quit game {game_id}."},
                timeout=2,
            )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify quitting player {req.telegram_id}: {e}")
        # Notify all other players in the game
        try:
            notify_players(game_id, f"Player {user.full_name or req.telegram_id} has left game {game_id} (power {player.power}).")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of quit event: {e}")
        return {"status": "ok"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class SendMessageRequest(BaseModel):
    telegram_id: str
    recipient_power: Optional[str] = None
    text: str

@app.post("/games/{game_id}/message")
def send_private_message(game_id: int, req: SendMessageRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game
        # Pyright/SQLAlchemy false positive: req.recipient_power is always a str or None from Pydantic
        if req.recipient_power is None or req.recipient_power == "":  # type: ignore
            raise HTTPException(status_code=400, detail="Recipient power required for private message")  # type: ignore
        recipient_player = db.query(PlayerModel).filter_by(game_id=game_id, power=req.recipient_power).first()
        if not recipient_player:
            raise HTTPException(status_code=404, detail="Recipient power not found in game")
        msg = MessageModel(game_id=game_id, sender_user_id=user.id, recipient_power=req.recipient_power, text=req.text)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        # --- Private message notification ---
        try:
            recipient_user_id = getattr(recipient_player, "user_id", None)
            if recipient_player is not None and recipient_user_id is not None:
                recipient_user = db.query(UserModel).filter_by(id=recipient_user_id).first()
                recipient_telegram_id = getattr(recipient_user, "telegram_id", None) if recipient_user is not None else None
                if recipient_telegram_id is not None:
                    requests.post(
                        "http://localhost:8081/notify",
                        json={"telegram_id": int(recipient_telegram_id), "message": f"New private message in game {game_id} from {user.full_name or user.telegram_id}: {req.text}"},
                        timeout=2,
                    )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify private message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class SendBroadcastRequest(BaseModel):
    telegram_id: str
    text: str

@app.post("/games/{game_id}/broadcast")
def send_broadcast_message(game_id: int, req: SendBroadcastRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        msg = MessageModel(game_id=game_id, sender_user_id=user.id, recipient_power=None, text=req.text)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        # --- Broadcast message notification ---
        try:
            notify_players(game_id, f"Broadcast in game {game_id} from {user.full_name or user.telegram_id}: {req.text}")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify broadcast message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/messages")
def get_game_messages(game_id: int, telegram_id: Optional[str] = None) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = None
        if telegram_id:
            user = db.query(UserModel).filter_by(telegram_id=telegram_id).first()
        # Retrieve all messages for the game, filter private messages to only those sent to or from the user
        query = db.query(MessageModel).filter_by(game_id=game_id)
        if user:
            # Show broadcasts and private messages sent to or from this user
            player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
            if player:
                power = player.power
                query = query.filter(or_(MessageModel.recipient_power is None, MessageModel.recipient_power == power, MessageModel.sender_user_id == user.id))  # type: ignore
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
        db.close()

@app.get("/games/{game_id}/history/{turn}")
def get_game_history(game_id: int, turn: int) -> Dict[str, Any]:
    """Get the game state snapshot for a specific turn."""
    db: Session = SessionLocal()
    try:
        from .db_models import GameHistoryModel
        snapshot = db.query(GameHistoryModel).filter_by(game_id=game_id, turn=turn).order_by(GameHistoryModel.id.desc()).first()
        if not snapshot:
            raise HTTPException(status_code=404, detail="No game state found for this turn.")
        return {"game_id": game_id, "turn": turn, "phase": snapshot.phase, "state": snapshot.state}
    finally:
        db.close()

class ReplacePlayerRequest(BaseModel):
    telegram_id: str
    power: str

@app.post("/games/{game_id}/replace")
def replace_player(game_id: int, req: ReplacePlayerRequest) -> Dict[str, Any]:
    """Replace a vacated power in a game. Only allowed if the power is unassigned (user_id is None), inactive (is_active is False), and the user is not already in the game.
    Returns 400 if already assigned, user is already in the game, or the power is not inactive.
    """
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Find the player slot for this power
        player = db.query(PlayerModel).filter_by(game_id=game_id, power=req.power).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Power not found in game")
        # Only allow replacement if user_id is None and is_active is False
        if player.user_id is not None:
            raise HTTPException(status_code=400, detail="Power is already assigned to a user. Only unassigned, inactive powers can be replaced.")
        if getattr(player, 'is_active', True) is True:
            raise HTTPException(status_code=400, detail="Power is not inactive and cannot be replaced. Only inactive/vacated powers can be replaced.")
        # Check if user is already in the game
        already_in_game = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if already_in_game:
            raise HTTPException(status_code=400, detail="User is already in the game")
        # Assign user to the player slot
        player.user_id = user.id
        setattr(player, 'is_active', True)
        db.commit()
        db.refresh(player)
        return {"status": "ok", "message": "Player replaced successfully"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

ADMIN_TOKEN = os.environ.get("DIPLOMACY_ADMIN_TOKEN", "changeme")

class MarkInactiveRequest(BaseModel):
    admin_token: str

@app.post("/games/{game_id}/players/{power}/mark_inactive")
def mark_player_inactive(game_id: int, power: str, req: MarkInactiveRequest) -> Dict[str, Any]:
    """Admin endpoint to mark a player as inactive (for replacement)."""
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    db: Session = SessionLocal()
    try:
        player = db.query(PlayerModel).filter_by(game_id=game_id, power=power).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        # SQLAlchemy ORM: must use getattr for boolean columns
        if getattr(player, 'is_active', True) is False:
            return {"status": "already_inactive"}
        setattr(player, 'is_active', False)
        db.commit()
        notify_players(game_id, f"Player {power} has been marked inactive by admin and is eligible for replacement.")
        return {"status": "ok", "game_id": game_id, "power": power}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

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
    game_state = game.get_state()
    # Add map_obj for order generation
    game_state["map_obj"] = game.map
    # Generate all legal orders for the given unit
    orders = OrderParser.generate_legal_orders(power, unit, game_state)
    return {"orders": orders}

if __name__ == "__main__":
    uvicorn.run("server.api:app", host="0.0.0.0", port=8000, reload=True)
