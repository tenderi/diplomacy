"""
User management API routes.

This module contains all endpoints related to user registration and session management.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional

from ..shared import db_service
from ...response_cache import cached_response

router = APIRouter()

# --- Request Models ---
class RegisterUserRequest(BaseModel):
    telegram_id: str
    game_id: str
    power: str

class RegisterPersistentUserRequest(BaseModel):
    telegram_id: str
    full_name: Optional[str] = None

class UserSession(BaseModel):
    telegram_id: str
    game_id: Optional[str] = None
    power: Optional[str] = None

# In-memory user sessions (for bot integration)
user_sessions: dict[str, UserSession] = {}

# --- User Endpoints ---
@router.post("/users/register")
def register_user(req: RegisterUserRequest) -> Dict[str, str]:
    """Register a user session for Telegram integration."""
    user_sessions[req.telegram_id] = UserSession(
        telegram_id=req.telegram_id, game_id=req.game_id, power=req.power
    )
    return {"status": "ok"}

@router.get("/users/{telegram_id}")
def get_user_session(telegram_id: str) -> UserSession:
    """Get a user's session info."""
    session = user_sessions.get(telegram_id)
    if not session:
        raise HTTPException(status_code=404, detail="User session not found")
    return session

@router.post("/users/persistent_register")
def persistent_register_user(req: RegisterPersistentUserRequest) -> Dict[str, Any]:
    """Register a user persistently in the database."""
    try:
        # Check if user already exists
        existing_user = db_service.get_user_by_telegram_id(req.telegram_id)
        if existing_user:
            return {
                "status": "already_registered",
                "user_id": existing_user.id,
                "telegram_id": existing_user.telegram_id,
                "full_name": existing_user.full_name
            }
        
        # Create new user
        user = db_service.create_user(
            telegram_id=req.telegram_id,
            full_name=req.full_name or ""
        )
        
        return {
            "status": "ok",
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "full_name": user.full_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/users/{telegram_id}/games")
@cached_response(ttl=60, key_params=["telegram_id"])
def get_user_games(telegram_id: str) -> Dict[str, Any]:
    """Get all games a user is participating in (only active players)."""
    try:
        user = db_service.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get all players for this user (already filtered by is_active=True and user_id)
        players = db_service.get_players_by_user_id(int(user.id))  # type: ignore
        
        games = []
        for player in players:
            # get_players_by_user_id already filters by is_active=True and user_id, so all returned players are active
            game = db_service.get_game_by_id(int(player.game_id))  # type: ignore
            if game:
                games.append({
                    "game_id": getattr(game, 'id', None),
                    "map_name": game.map_name,
                    "power": player.power_name,
                    "current_turn": getattr(game, 'current_turn', 0),
                    "status": getattr(game, 'status', "active")
                })
        
        return {"games": games}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

