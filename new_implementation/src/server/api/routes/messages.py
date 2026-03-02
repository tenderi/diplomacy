"""
Messaging API routes.

This module contains all endpoints related to private and broadcast messaging between players.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional
import requests

from .auth import resolve_user_or_telegram, get_current_user_optional, http_bearer
from ..shared import db_service, scheduler_logger, logger, NOTIFY_URL, notify_players
from engine.database import MessageModel

router = APIRouter()

# --- Request Models ---
class SendMessageRequest(BaseModel):
    telegram_id: Optional[str] = None
    recipient_power: Optional[str] = None
    text: str

class SendBroadcastRequest(BaseModel):
    telegram_id: Optional[str] = None
    text: str

# --- Message Endpoints ---
@router.post("/games/{game_id}/message")
def send_private_message(
    game_id: str,
    req: SendMessageRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id)
        # Get game model to get numeric ID for database operations
        game_model = db_service.get_game_by_game_id(str(game_id))
        if not game_model:
            raise HTTPException(status_code=404, detail="Game not found")
        # Validate sender is in the game (use numeric game.id)
        player = db_service.get_player_by_game_id_and_user_id(game_id=int(game_model.id), user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game
        if req.recipient_power is None or req.recipient_power == "":  # type: ignore
            raise HTTPException(status_code=400, detail="Recipient power required for private message")
        recipient_player = db_service.get_player_by_game_id_and_power(game_id=str(game_id), power=req.recipient_power)
        if not recipient_player:
            raise HTTPException(status_code=404, detail="Recipient power not found in game")
        msg = db_service.create_message(game_id=int(game_model.id), sender_user_id=int(user.id), recipient_power=req.recipient_power, text=req.text)  # type: ignore
        # Private message notification
        try:
            recipient_user_id = getattr(recipient_player, "user_id", None)
            if recipient_player is not None and recipient_user_id is not None:
                recipient_user = db_service.get_user_by_id(recipient_user_id)
                recipient_telegram_id = getattr(recipient_user, "telegram_id", None) if recipient_user is not None else None
                if recipient_telegram_id is not None:
                    try:
                        telegram_id_int = int(recipient_telegram_id)
                        requests.post(
                            NOTIFY_URL,
                            json={"telegram_id": telegram_id_int, "message": f"New private message in game {game_id} from {user.full_name or getattr(user, 'telegram_id', None)}: {req.text}"},
                            timeout=2,
                        )
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify private message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/broadcast")
def send_broadcast_message(
    game_id: int,
    req: SendBroadcastRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id)
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        msg = db_service.create_message(game_id=game_id, sender_user_id=int(user.id), recipient_power=None, text=req.text)  # type: ignore
        # Broadcast message notification
        try:
            notify_players(game_id, f"Broadcast in game {game_id} from {user.full_name or getattr(user, 'telegram_id', None)}: {req.text}")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify broadcast message: {e}")
        
        # Channel integration: Forward broadcast to channel
        try:
            from ..telegram_bot.channels import should_auto_post_broadcast, post_broadcast_to_channel
            
            if should_auto_post_broadcast(str(game_id)):
                channel_info = db_service.get_game_channel_info(str(game_id))
                if channel_info:
                    post_broadcast_to_channel(
                        channel_id=channel_info.get("channel_id"),
                        game_id=str(game_id),
                        message=req.text,
                        power=player.power_name if player else None
                    )
        except Exception as e:
            logger.debug(f"Channel integration check failed for broadcast: {e}")
        
        return {"status": "ok", "message_id": msg.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/messages")
def get_game_messages(
    game_id: str,
    telegram_id: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    try:
        user = get_current_user_optional(credentials)
        if user is None and telegram_id:
            user = db_service.get_user_by_telegram_id(telegram_id)
        # Get game model to get numeric ID
        game_model = db_service.get_game_by_game_id(str(game_id))
        if not game_model:
            raise HTTPException(status_code=404, detail="Game not found")
        # Retrieve all messages for the game, filter private messages to only those sent to or from the user
        query = db_service.get_messages_by_game_id(int(game_model.id))
        if user:
            # Show broadcasts and private messages sent to or from this user
            player = db_service.get_player_by_game_id_and_user_id(game_id=int(game_model.id), user_id=int(user.id))  # type: ignore
            if player:
                power = player.power_name
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        MessageModel.recipient_power.is_(None),
                        MessageModel.recipient_power == power,
                        MessageModel.sender_user_id == user.id,
                    )
                )
            else:
                query = query.filter(MessageModel.recipient_power.is_(None))  # Only broadcasts
        messages = query.order_by(MessageModel.timestamp.asc()).all()
        result = [
            {
                "id": m.id,
                "sender_user_id": m.sender_user_id,
                "recipient_power": m.recipient_power,
                "text": m.text,
                "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, 'isoformat') else str(m.timestamp)
            }
            for m in messages
        ]
        return {"messages": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

