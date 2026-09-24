"""
User management API routes.

This module contains all endpoints related to user registration and session management.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from typing import Dict, Any, Optional

from .auth import get_current_user, get_current_user_optional, http_bearer
from ..shared import db_service, BOT_SECRET
from ...response_cache import cached_response

router = APIRouter()

# --- Request Models ---
class RegisterPersistentUserRequest(BaseModel):
    telegram_id: str
    full_name: Optional[str] = None
    bot_secret: Optional[str] = None

    @field_validator("telegram_id")
    @classmethod
    def telegram_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("telegram_id is required and cannot be empty or whitespace")
        return v.strip()

# --- User Endpoints ---
@router.post("/users/persistent_register")
def persistent_register_user(req: RegisterPersistentUserRequest) -> Dict[str, Any]:
    """Register a user persistently in the database. Requires bot_secret (only the Telegram bot may call this)."""
    if not BOT_SECRET or req.bot_secret != BOT_SECRET:
        from fastapi import status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
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

def _user_games_response(user: Any) -> Dict[str, Any]:  # noqa: ANN401
    """Build games list for a user (shared by get_user_games and get_me_games)."""
    players = db_service.get_players_by_user_id(int(user.id))  # type: ignore
    games = []
    for player in players:
        game = db_service.get_game_by_id(int(player.game_id))  # type: ignore
        if game:
            games.append({
                "game_id": getattr(game, 'id', None),
                "map_name": game.map_name,
                "power": player.power_name,
                "current_turn": getattr(game, 'current_turn', 0),
                "status": getattr(game, 'status', "active"),
                # The bot offers "process turn now" only to a game's creator,
                # the one Telegram player allowed to end a turn early.
                "is_creator": game.created_by_user_id is not None
                and int(game.created_by_user_id) == int(user.id),
            })
    return {"games": games}


@router.get("/users/me/games")
def get_me_games(current_user: Any = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current user's games (requires Bearer token). Used by browser client."""
    return _user_games_response(current_user)


def require_bot_or_self(
    telegram_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_bot_secret: Optional[str] = Header(None),
) -> None:
    """Dependency: the bot (``X-Bot-Secret``), or a Bearer user whose linked
    telegram id is the one in the path.

    A dependency rather than a check inside the route on purpose: the route is
    wrapped in ``@cached_response``, which answers from cache *before* the
    function body runs, so an in-body check would be skipped for every hit
    after the first. Dependencies run before the wrapper.
    """
    if x_bot_secret and BOT_SECRET and x_bot_secret == BOT_SECRET:
        return
    me = get_current_user_optional(credentials)
    if me is None or str(getattr(me, "telegram_id", None)) != str(telegram_id):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated: X-Bot-Secret, or a Bearer token for this telegram id, required",
        )


@router.get("/users/{telegram_id}/games")
@cached_response(ttl=60, key_params=["telegram_id"])
def get_user_games(telegram_id: str, _: None = Depends(require_bot_or_self)) -> Dict[str, Any]:
    """Get all games a user is participating in (only active players). Uses telegram_id (Telegram bot).

    The bot presents ``X-Bot-Secret`` (``api_get`` always sends it); a browser
    session may read only its own linked telegram id. Anonymous callers get 401
    -- until ``v2.7.79`` (Track T) which games a given Telegram user plays, and
    as which power, was readable by anyone who could guess the id.
    """
    try:
        user = db_service.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _user_games_response(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

