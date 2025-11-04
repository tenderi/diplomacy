"""
Channel management API routes.

This module handles Telegram channel integration for games:
- Linking/unlinking games to channels
- Channel settings management
- Automated content posting to channels
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..shared import db_service, server, logger
from ...response_cache import invalidate_cache

router = APIRouter()


# --- Request Models ---
class LinkChannelRequest(BaseModel):
    channel_id: str
    channel_name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class ChannelSettingsRequest(BaseModel):
    auto_post_maps: Optional[bool] = None
    auto_post_broadcasts: Optional[bool] = None
    auto_post_notifications: Optional[bool] = None
    notification_level: Optional[str] = None  # "all", "important", "none"


class BroadcastMessageRequest(BaseModel):
    telegram_id: str
    message: str
    power: Optional[str] = None


@router.post("/games/{game_id}/channel/link")
def link_channel_to_game(game_id: str, req: LinkChannelRequest) -> Dict[str, Any]:
    """
    Link a Telegram channel to a game.
    
    This enables automated posting of maps, broadcasts, and notifications to the channel.
    """
    try:
        # Verify game exists
        if game_id not in server.games:
            # Try to load from database
            game_state = db_service.get_game_state(game_id)
            if not game_state:
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        # Link channel via database service
        db_service.link_game_to_channel(
            game_id=game_id,
            channel_id=req.channel_id,
            channel_name=req.channel_name,
            settings=req.settings or {}
        )
        
        # Invalidate cache
        invalidate_cache(f"games/{game_id}")
        
        return {
            "status": "ok",
            "message": f"Game {game_id} linked to channel {req.channel_id}",
            "game_id": game_id,
            "channel_id": req.channel_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error linking channel to game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/games/{game_id}/channel/unlink")
def unlink_channel_from_game(game_id: str) -> Dict[str, Any]:
    """Unlink a Telegram channel from a game."""
    try:
        # Verify game exists
        if game_id not in server.games:
            game_state = db_service.get_game_state(game_id)
            if not game_state:
                raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        # Unlink channel
        db_service.unlink_game_from_channel(game_id)
        
        # Invalidate cache
        invalidate_cache(f"games/{game_id}")
        
        return {
            "status": "ok",
            "message": f"Game {game_id} unlinked from channel",
            "game_id": game_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error unlinking channel from game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel")
def get_channel_info(game_id: str) -> Dict[str, Any]:
    """Get channel information for a game."""
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        
        if not channel_info:
            return {
                "status": "ok",
                "linked": False,
                "message": f"Game {game_id} is not linked to a channel"
            }
        
        return {
            "status": "ok",
            "linked": True,
            "channel_id": channel_info.get("channel_id"),
            "channel_name": channel_info.get("channel_name"),
            "settings": channel_info.get("settings", {})
        }
    except Exception as e:
        logger.exception(f"Error getting channel info for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/games/{game_id}/channel/settings")
def update_channel_settings(game_id: str, req: ChannelSettingsRequest) -> Dict[str, Any]:
    """Update channel settings for a game."""
    try:
        # Build settings dict from request
        settings = {}
        if req.auto_post_maps is not None:
            settings["auto_post_maps"] = req.auto_post_maps
        if req.auto_post_broadcasts is not None:
            settings["auto_post_broadcasts"] = req.auto_post_broadcasts
        if req.auto_post_notifications is not None:
            settings["auto_post_notifications"] = req.auto_post_notifications
        if req.notification_level is not None:
            settings["notification_level"] = req.notification_level
        
        # Update settings
        db_service.update_game_channel_settings(game_id, settings)
        
        # Invalidate cache
        invalidate_cache(f"games/{game_id}")
        
        return {
            "status": "ok",
            "message": f"Channel settings updated for game {game_id}",
            "settings": settings
        }
    except Exception as e:
        logger.exception(f"Error updating channel settings for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/map")
def post_map_to_channel(game_id: str) -> Dict[str, Any]:
    """Manually post the current game map to the linked channel."""
    try:
        from .maps import generate_map_for_snapshot
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Generate map
        result = generate_map_for_snapshot(game_id)
        map_path = result.get("map_path")
        
        # Post to channel (implementation will be in telegram_bot/channels.py)
        # For now, return success - actual posting will be implemented in telegram_bot/channels.py
        # message_id = post_map(channel_id, game_id, map_path)
        
        return {
            "status": "ok",
            "message": f"Map generation ready for channel {channel_id}",
            "channel_id": channel_id,
            "map_path": map_path,
            "note": "Channel posting will be implemented in telegram_bot/channels.py"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting map to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/broadcast")
def post_broadcast_to_channel(game_id: str, req: BroadcastMessageRequest) -> Dict[str, Any]:
    """Post a broadcast message to the linked channel."""
    try:
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Post broadcast to channel (implementation will be in telegram_bot/channels.py)
        # For now, return success - actual posting will be implemented in telegram_bot/channels.py
        # message_id = post_broadcast(channel_id, game_id, req.message, req.power)
        
        return {
            "status": "ok",
            "message": f"Broadcast ready for channel {channel_id}",
            "channel_id": channel_id,
            "note": "Channel posting will be implemented in telegram_bot/channels.py"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting broadcast to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

