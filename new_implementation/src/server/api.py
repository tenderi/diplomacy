"""
RESTful API server for Diplomacy game management and integration (e.g., Telegram bot).
Implements endpoints for game creation, player management, order submission, state queries, and notifications.
Strict typing and Ruff compliance enforced.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from server.server import Server
import uvicorn
from typing import Optional, Dict, List, Any
from .db_session import SessionLocal
from .db_models import Base, GameModel, PlayerModel, OrderModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine
from .db_config import SQLALCHEMY_DATABASE_URL

app = FastAPI(title="Diplomacy Server API", version="0.1.0")

# In-memory server instance (replace with persistent storage for production)
server = Server()

# On startup, create tables if not exist
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True, future=True)
Base.metadata.create_all(bind=engine)

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

@app.post("/games/create")
def create_game(req: CreateGameRequest):
    result = server.process_command(f"CREATE_GAME {req.map_name}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    # Persist to DB
    db: Session = SessionLocal()
    try:
        game = GameModel(map_name=req.map_name, state=result, is_active=True)
        db.add(game)
        db.commit()
        db.refresh(game)
        return {"game_id": game.id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/add_player")
def add_player(req: AddPlayerRequest) -> Dict[str, str | int]:
    result = server.process_command(f"ADD_PLAYER {req.game_id} {req.power}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    db: Session = SessionLocal()
    try:
        player = PlayerModel(game_id=int(req.game_id), power=req.power)
        db.add(player)
        db.commit()
        db.refresh(player)
        player_id = getattr(player, 'id', None)
        if player_id is None:
            raise HTTPException(status_code=500, detail="Player ID not found after creation")
        return {"status": "ok", "player_id": player_id}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/set_orders")
def set_orders(req: SetOrdersRequest):
    db: Session = SessionLocal()
    try:
        for order in req.orders:
            result = server.process_command(f"SET_ORDERS {req.game_id} {req.power} {order}")
            if result.get("status") != "ok":
                raise HTTPException(status_code=400, detail=result.get("error", "Order error"))
            # Find player
            player = db.query(PlayerModel).filter_by(game_id=int(req.game_id), power=req.power).first()
            if player:
                db.add(OrderModel(player_id=player.id, order_text=order))
        db.commit()
        return {"status": "ok"}
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/games/process_turn")
def process_turn(req: ProcessTurnRequest):
    result = server.process_command(f"PROCESS_TURN {req.game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return {"status": "ok"}

@app.get("/games/{game_id}/state")
def get_game_state(game_id: str):
    result = server.process_command(f"GET_GAME_STATE {game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=404, detail=result.get("error", "Game not found"))
    return result

@app.post("/users/register")
def register_user(req: RegisterUserRequest):
    user_sessions[req.telegram_id] = UserSession(
        telegram_id=req.telegram_id, game_id=req.game_id, power=req.power
    )
    return {"status": "ok"}

@app.get("/users/{telegram_id}")
def get_user_session(telegram_id: str):
    session = user_sessions.get(telegram_id)
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    return session

@app.get("/games/{game_id}/players")
def get_players(game_id: str) -> List[Dict[str, Any]]:
    db: Session = SessionLocal()
    try:
        players = db.query(PlayerModel).filter_by(game_id=int(game_id)).all()
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
            player_orders = db.query(OrderModel).filter_by(player_id=player.id).all()
            for order in player_orders:
                orders.append({"player_id": player.id, "power": player.power, "order": order.order_text})
        return orders
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Add more endpoints for user session management, notifications, etc. as needed.

if __name__ == "__main__":
    uvicorn.run("server.api:app", host="0.0.0.0", port=8000, reload=True)
