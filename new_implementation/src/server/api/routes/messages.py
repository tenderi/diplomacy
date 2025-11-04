"""
Messaging API routes.

This module contains all endpoints related to private and broadcast messaging between players.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import requests

from ..shared import db_service, scheduler_logger, NOTIFY_URL, notify_players
from engine.database import MessageModel

router = APIRouter()

# --- Request Models ---
class SendMessageRequest(BaseModel):
    telegram_id: str
    recipient_power: Optional[str] = None
    text: str

class SendBroadcastRequest(BaseModel):
    telegram_id: str
    text: str

# --- Message Endpoints ---
@router.post("/games/{game_id}/message")
def send_private_message(game_id: int, req: SendMessageRequest) -> Dict[str, Any]:
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game
        if req.recipient_power is None or req.recipient_power == "":  # type: ignore
            raise HTTPException(status_code=400, detail="Recipient power required for private message")
        recipient_player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.recipient_power)
        if not recipient_player:
            raise HTTPException(status_code=404, detail="Recipient power not found in game")
        msg = db_service.create_message(game_id=game_id, sender_user_id=int(user.id), recipient_power=req.recipient_power, text=req.text)  # type: ignore
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
                            json={"telegram_id": telegram_id_int, "message": f"New private message in game {game_id} from {user.full_name or user.telegram_id}: {req.text}"},
                            timeout=2,
                        )
                    except (ValueError, TypeError):
                        pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify private message: {e}")
        return {"status": "ok", "message_id": msg.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/broadcast")
def send_broadcast_message(game_id: int, req: SendBroadcastRequest) -> Dict[str, Any]:
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Sender user not found")
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        msg = db_service.create_message(game_id=game_id, sender_user_id=int(user.id), recipient_power=None, text=req.text)  # type: ignore
        # Broadcast message notification
        try:
            notify_players(game_id, f"Broadcast in game {game_id} from {user.full_name or user.telegram_id}: {req.text}")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/messages")
def get_game_messages(game_id: int, telegram_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        user = None
        if telegram_id:
            user = db_service.get_user_by_telegram_id(telegram_id)
        # Retrieve all messages for the game, filter private messages to only those sent to or from the user
        query = db_service.get_messages_by_game_id(game_id)
        if user:
            # Show broadcasts and private messages sent to or from this user
            player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
            if player:
                power = player.power_name
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

