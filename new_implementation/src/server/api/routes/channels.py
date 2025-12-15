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
    reply_to_message_id: Optional[int] = None


class CreateThreadRequest(BaseModel):
    topic: str
    phase: Optional[str] = None


class ProposalRequest(BaseModel):
    telegram_id: str
    proposal_text: str
    power: str
    proposal_title: Optional[str] = None


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
    """Post a broadcast message to the linked channel with optional threading."""
    try:
        from ...telegram_bot.channels import post_broadcast_to_channel
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Post broadcast to channel
        message_id = post_broadcast_to_channel(
            channel_id=channel_id,
            game_id=game_id,
            message=req.message,
            power=req.power,
            reply_to_message_id=req.reply_to_message_id
        )
        
        return {
            "status": "ok",
            "message": f"Broadcast posted to channel {channel_id}",
            "channel_id": channel_id,
            "message_id": message_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting broadcast to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/thread")
def create_discussion_thread_endpoint(game_id: str, req: CreateThreadRequest) -> Dict[str, Any]:
    """Create a discussion thread for a specific phase or topic."""
    try:
        from ...telegram_bot.channels import create_discussion_thread
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Create thread
        thread_id = create_discussion_thread(
            channel_id=channel_id,
            game_id=game_id,
            topic=req.topic,
            phase=req.phase
        )
        
        return {
            "status": "ok",
            "message": f"Discussion thread created in channel {channel_id}",
            "channel_id": channel_id,
            "thread_id": thread_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating discussion thread for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/proposal")
def post_proposal(game_id: str, req: ProposalRequest) -> Dict[str, Any]:
    """Post a proposal with voting to the linked channel."""
    try:
        from ...telegram_bot.channels import post_proposal_with_voting
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Post proposal
        message_id = post_proposal_with_voting(
            channel_id=channel_id,
            game_id=game_id,
            proposal_text=req.proposal_text,
            power=req.power,
            proposal_title=req.proposal_title
        )
        
        return {
            "status": "ok",
            "message": f"Proposal posted to channel {channel_id}",
            "channel_id": channel_id,
            "message_id": message_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting proposal to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/proposal/{message_id}")
def get_proposal_results_endpoint(game_id: str, message_id: int) -> Dict[str, Any]:
    """Get voting results for a proposal message."""
    try:
        from ...telegram_bot.channels import get_proposal_results
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Get results
        results = get_proposal_results(channel_id, message_id)
        
        return {
            "status": "ok",
            "results": results
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting proposal results for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/timeline")
def get_timeline(game_id: str) -> Dict[str, Any]:
    """Get historical timeline for the game."""
    try:
        from ...telegram_bot.channels import format_historical_timeline
        
        # Get game state
        if game_id not in server.games:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        game_obj = server.games[game_id]
        current_state = game_obj.get_game_state()
        
        # Convert to dict
        game_state_dict = {
            "game_id": game_id,
            "current_year": current_state.current_year,
            "current_season": current_state.current_season,
            "current_phase": current_state.current_phase,
            "powers": {
                power: {
                    "is_eliminated": power_state.is_eliminated,
                    "controlled_supply_centers": list(power_state.controlled_supply_centers)
                }
                for power, power_state in current_state.powers.items()
            },
            "supply_centers": {
                power: list(power_state.controlled_supply_centers)
                for power, power_state in current_state.powers.items()
            }
        }
        
        # Format timeline
        timeline_text = format_historical_timeline(game_state_dict)
        
        return {
            "status": "ok",
            "timeline": timeline_text
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting timeline for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/timeline")
def post_timeline_update(game_id: str) -> Dict[str, Any]:
    """Manually post timeline update to the linked channel."""
    try:
        from ...telegram_bot.channels import post_timeline_update_to_channel
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Get game state
        if game_id not in server.games:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        game_obj = server.games[game_id]
        current_state = game_obj.get_game_state()
        
        # Convert to dict
        game_state_dict = {
            "game_id": game_id,
            "current_year": current_state.current_year,
            "current_season": current_state.current_season,
            "current_phase": current_state.current_phase,
            "powers": {
                power: {
                    "is_eliminated": power_state.is_eliminated,
                    "controlled_supply_centers": list(power_state.controlled_supply_centers)
                }
                for power, power_state in current_state.powers.items()
            },
            "supply_centers": {
                power: list(power_state.controlled_supply_centers)
                for power, power_state in current_state.powers.items()
            }
        }
        
        # Post timeline
        message_id = post_timeline_update_to_channel(
            channel_id=channel_id,
            game_id=game_id,
            game_state=game_state_dict
        )
        
        return {
            "status": "ok",
            "message": f"Timeline update posted to channel {channel_id}",
            "channel_id": channel_id,
            "message_id": message_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting timeline update to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/dashboard")
def post_player_dashboard(game_id: str) -> Dict[str, Any]:
    """Manually post player status dashboard to the linked channel."""
    try:
        from ...telegram_bot.channels import post_player_dashboard_to_channel
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Get game state
        if game_id not in server.games:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        game_obj = server.games[game_id]
        current_state = game_obj.get_game_state()
        
        # Get players data
        players_data = None
        try:
            players_list = db_service.get_players_by_game_id(int(game_obj.game_id) if hasattr(game_obj, 'game_id') and game_obj.game_id else 0)
            players_data = []
            for p in players_list:
                user = db_service.get_user_by_id(int(p.user_id)) if p.user_id else None
                players_data.append({
                    "power": p.power_name,
                    "user_id": p.user_id,
                    "is_active": getattr(p, 'is_active', True),
                    "telegram_id": getattr(user, 'telegram_id', None) if user else None,
                    "full_name": getattr(user, 'full_name', None) if user else None,
                })
        except Exception as e:
            logger.warning(f"Could not get players data for dashboard: {e}")
        
        # Convert current state to dict
        game_state_dict = {
            "game_id": game_id,
            "current_year": current_state.current_year,
            "current_season": current_state.current_season,
            "current_phase": current_state.current_phase,
            "phase_code": current_state.phase_code,
            "orders": {
                power: []  # Orders are cleared after processing
                for power in current_state.powers.keys()
            },
            "powers": {
                power: {
                    "orders_submitted": power_state.orders_submitted,
                    "last_order_time": power_state.last_order_time.isoformat() if power_state.last_order_time else None,
                    "is_active": power_state.is_active,
                    "is_eliminated": power_state.is_eliminated
                }
                for power, power_state in current_state.powers.items()
            }
        }
        
        # Post dashboard
        message_id = post_player_dashboard_to_channel(
            channel_id=channel_id,
            game_id=game_id,
            game_state=game_state_dict,
            players_data=players_data
        )
        
        return {
            "status": "ok",
            "message": f"Player dashboard posted to channel {channel_id}",
            "channel_id": channel_id,
            "message_id": message_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting player dashboard to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/battle_results")
def post_battle_results(game_id: str) -> Dict[str, Any]:
    """Manually post formatted battle results to the linked channel."""
    try:
        from ...telegram_bot.channels import post_battle_results_to_channel
        from engine.database import order_to_dict
        
        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        
        channel_id = channel_info.get("channel_id")
        
        # Get game state
        if game_id not in server.games:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
        
        game_obj = server.games[game_id]
        current_state = game_obj.get_game_state()
        
        # Get previous supply centers from order history if available
        previous_supply_centers = None
        order_history = None
        
        if hasattr(game_obj.game_state, "order_history") and len(game_obj.game_state.order_history) > 0:
            # Get the last turn's orders
            last_turn_index = game_obj.turn - 1
            if last_turn_index >= 0 and last_turn_index < len(game_obj.game_state.order_history):
                order_history = {
                    power: [order_to_dict(o) for o in orders]
                    for power, orders in game_obj.game_state.order_history[last_turn_index].items()
                }
        
        # Convert current state to dict
        game_state_dict = {
            "current_year": current_state.current_year,
            "current_season": current_state.current_season,
            "current_phase": current_state.current_phase,
            "phase_code": current_state.phase_code,
            "supply_centers": {
                power: list(power_state.controlled_supply_centers)
                for power, power_state in current_state.powers.items()
            },
            "units": {
                power: [{"unit_type": u.unit_type, "province": u.province, 
                        "is_dislodged": u.is_dislodged, "dislodged_by": u.dislodged_by}
                       for u in power_state.units]
                for power, power_state in current_state.powers.items()
            }
        }
        
        # Post battle results
        message_id = post_battle_results_to_channel(
            channel_id=channel_id,
            game_id=game_id,
            game_state=game_state_dict,
            order_history=order_history,
            previous_supply_centers=previous_supply_centers
        )
        
        return {
            "status": "ok",
            "message": f"Battle results posted to channel {channel_id}",
            "channel_id": channel_id,
            "message_id": message_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting battle results to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

