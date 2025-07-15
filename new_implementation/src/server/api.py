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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from server.server import Server
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

app = FastAPI(title="Diplomacy Server API", version="0.1.0")

# In-memory server instance (replace with persistent storage for production)
server = Server()

# On startup, create tables if not exist
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True, future=True)
Base.metadata.create_all(bind=engine)

# --- Models ---
class CreateGameRequest(BaseModel):
    map_name: str = "standard"

class AddPlayerRequest(BaseModel):
    game_id: str
    power: str

class SetOrdersRequest(BaseModel):
    game_id: str
    power: str
    orders: list[str]

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
        db.add(game)
        db.commit()
        db.refresh(game)
        game_id = str(game.id)
        # Now create the game in the in-memory server with the same game_id
        if game_id not in server.games:
            from engine.game import Game
            g = Game()
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
    """Set orders for a player in a game. Replaces any existing orders for the current turn. Returns per-order validation results."""
    db: Session = SessionLocal()
    results = []
    try:
        player = db.query(PlayerModel).filter_by(game_id=int(req.game_id), power=req.power).first()
        print(f"DEBUG: set_orders: player found: {player is not None}, player_id: {getattr(player, 'id', None) if player else None}")
        game = db.query(GameModel).filter_by(id=int(req.game_id)).first()
        # Default to turn 0 if not found
        turn = 0
        if game and isinstance(game.state, dict):
            turn = game.state.get("turn", 0)
        elif game and hasattr(game.state, "get"):
            turn = game.state.get("turn", 0)
        if player:
            db.query(OrderModel).filter_by(player_id=player.id).delete()
        for order in req.orders:
            result = server.process_command(f"SET_ORDERS {req.game_id} {req.power} {order}")
            if result.get("status") == "ok":
                if player:
                    db.add(OrderModel(player_id=player.id, order_text=order, turn=turn))
                    print(f"DEBUG: set_orders: added order '{order}' for player_id {player.id} turn {turn}")
                results.append({"order": order, "success": True, "error": None})
            else:
                results.append({"order": order, "success": False, "error": result.get("error", "Order error")})
        # Update game state in DB to reflect in-memory state
        if game and req.game_id in server.games:
            state = server.games[req.game_id].get_state()
            if not isinstance(state, dict):
                state = dict(state)
            # Remove non-serializable objects
            if 'map_obj' in state:
                del state['map_obj']
            try:
                game.state = state  # This should work since state column is JSON
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

@app.post("/games/process_turn")
def process_turn(req: ProcessTurnRequest) -> Dict[str, str]:
    """Process the current turn for a game and update the database state."""
    result = server.process_command(f"PROCESS_TURN {req.game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    db: Session = SessionLocal()
    try:
        game = db.query(GameModel).filter_by(id=int(req.game_id)).first()
        if game and req.game_id in server.games:
            state = server.games[req.game_id].get_state()
            if not isinstance(state, dict):
                state = dict(state)
            # Remove non-serializable objects
            if 'map_obj' in state:
                del state['map_obj']
            try:
                game.state = state  # type: ignore  # SQLAlchemy dynamic attribute, Pyright false positive
            except Exception as e:
                print(f"DEBUG: process_turn: failed to assign game.state: {e}")
        db.commit()
        return {"status": "ok"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/games/{game_id}/state")
def get_game_state(game_id: str) -> Dict[str, Any]:
    """Get the current state of a game."""
    result = server.process_command(f"GET_GAME_STATE {game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail=result.get("error", "Game not found"))
    return result

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
        players = db.query(PlayerModel).filter(PlayerModel.game_id == int(game_id)).all()
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
                turn = order.turn
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
        player = db.query(PlayerModel).filter_by(game_id=int(game_id), power=power).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        orders = db.query(OrderModel).filter_by(player_id=player.id).all()
        order_list = [order.order_text for order in orders]
        return {"power": power, "orders": order_list}
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/{game_id}/orders/{power}/clear")
def clear_orders_for_power(game_id: str, power: str) -> Dict[str, str]:
    """Delete all orders for a specific power in a game (current turn only)."""
    db: Session = SessionLocal()
    try:
        player = db.query(PlayerModel).filter_by(game_id=int(game_id), power=power).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
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
            if player.telegram_id:
                try:
                    requests.post(
                        "http://localhost:8081/notify",
                        json={"telegram_id": int(player.telegram_id), "message": message},
                        timeout=2,
                    )
                    scheduler_logger.info(f"Notified telegram_id {player.telegram_id} for game {game_id}: {message}")
                except Exception as e:
                    scheduler_logger.error(f"Failed to notify telegram_id {player.telegram_id}: {e}")
    finally:
        db.close()

def process_due_deadlines(now: datetime) -> None:
    """
    Process all games with deadlines <= now. Used by the scheduler and for testing.
    """
    db: Session = SessionLocal()
    try:
        games = db.query(GameModel).filter(GameModel.deadline != None, GameModel.is_active == True).all()  # type: ignore
        for game in games:
            deadline = getattr(game, 'deadline', None)  # type: ignore
            game_id = getattr(game, 'id', None)  # type: ignore
            if game_id is None:
                continue  # skip games with no id
            if deadline is not None:
                # Ensure both deadline and now are timezone-aware (UTC)
                if deadline.tzinfo is None or deadline.tzinfo.utcoffset(deadline) is None:
                    deadline = deadline.replace(tzinfo=pytz.UTC)
                if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
                    now = now.replace(tzinfo=pytz.UTC)
                if deadline <= now:
                    scheduler_logger.warning(f"Missed or due deadline detected for game {game_id} (deadline was {deadline}, now {now}). Processing turn immediately.")
                    server.process_command(f"PROCESS_TURN {game_id}")
                    # Direct SQL update to set deadline to NULL for cross-session visibility
                    db.execute(
                        text("UPDATE games SET deadline = NULL WHERE id = :game_id"),
                        {"game_id": game_id}
                    )
                    db.commit()  # type: ignore
                    notify_players(game_id, f"The turn has been processed for game {game_id} due to a missed or due deadline. View the new board state and submit your next orders.")  # type: ignore
                    reminder_sent[game_id] = False  # Reset for next turn
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
            games = db.query(GameModel).filter(GameModel.deadline != None, GameModel.is_active == True).all()  # type: ignore
            for game in games:
                deadline = getattr(game, 'deadline', None)  # type: ignore
                game_id = getattr(game, 'id', None)  # type: ignore
                if game_id is None:
                    continue  # skip games with no id
                if deadline is not None:
                    # Send reminder 10 minutes before deadline
                    if deadline - now <= timedelta(minutes=10) and deadline > now:
                        if not reminder_sent.get(game_id):
                            notify_players(game_id, f"Reminder: The deadline for submitting orders in game {game_id} is in 10 minutes.")  # type: ignore
                            scheduler_logger.info(f"Sent 10-minute reminder for game {game_id} (deadline: {deadline})")
                            reminder_sent[game_id] = True
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

# --- New User Endpoints for Persistent Registration and Multi-Game Support ---
class RegisterPersistentUserRequest(BaseModel):
    telegram_id: str
    full_name: Optional[str] = None

@app.post("/users/persistent_register")
def persistent_register_user(req: RegisterPersistentUserRequest) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        user = db.query(UserModel).filter_by(telegram_id=req.telegram_id).first()
        if not user:
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
        if not user:
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
        if not user:
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
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if not player:
            return {"status": "not_in_game"}
        db.delete(player)
        db.commit()
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
        if not user:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if not player:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game
        if not req.recipient_power:
            raise HTTPException(status_code=400, detail="Recipient power required for private message")
        recipient_player = db.query(PlayerModel).filter_by(game_id=game_id, power=req.recipient_power).first()
        if not recipient_player:
            raise HTTPException(status_code=404, detail="Recipient power not found in game")
        msg = MessageModel(game_id=game_id, sender_user_id=user.id, recipient_power=req.recipient_power, text=req.text)
        db.add(msg)
        db.commit()
        db.refresh(msg)
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
        if not user:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db.query(PlayerModel).filter_by(game_id=game_id, user_id=user.id).first()
        if not player:
            raise HTTPException(status_code=403, detail="Sender not in game")
        msg = MessageModel(game_id=game_id, sender_user_id=user.id, recipient_power=None, text=req.text)
        db.add(msg)
        db.commit()
        db.refresh(msg)
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

if __name__ == "__main__":
    uvicorn.run("server.api:app", host="0.0.0.0", port=8000, reload=True)
