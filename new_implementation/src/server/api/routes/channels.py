"""
Channel management API routes.

This module handles Telegram channel integration for games:
- Linking/unlinking games to channels
- Channel settings management
- Automated content posting to channels
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from datetime import datetime

from .auth import require_bot_or_user
from ..shared import db_service, game_service, logger
from ...response_cache import invalidate_cache

_ALL_POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}


def _legacy_state_dict(game_id: str) -> Optional[Dict[str, Any]]:
    """Build the channel-posting game_state dict from the new engine's view."""
    v = game_service.view(game_id)
    if v is None:
        return None
    sc_by_power: Dict[str, list] = {p: [] for p in _ALL_POWERS}
    for prov, owner in v["ownership"].items():
        sc_by_power.setdefault(owner, []).append(prov)
    units_by_power: Dict[str, list] = {p: [] for p in _ALL_POWERS}
    for p, us in v.get("units_by_power", {}).items():
        units_by_power[p] = [
            {"unit_type": u["kind"], "province": u["location"].split("/")[0],
             "is_dislodged": False, "dislodged_by": None}
            for u in us
        ]
    return {
        "game_id": game_id,
        "current_year": v["year"],
        "current_season": v["season"],
        "current_phase": v["phase_type"],
        "phase_code": v["phase"],
        "supply_centers": sc_by_power,
        "units": units_by_power,
        "orders": {p: v["orders"].get(p, []) for p in _ALL_POWERS},
        "powers": {
            p: {
                "is_eliminated": not units_by_power.get(p) and not sc_by_power.get(p),
                "controlled_supply_centers": sc_by_power.get(p, []),
                "orders_submitted": bool(v["orders"].get(p)),
                "last_order_time": None,
                "is_active": True,
            }
            for p in _ALL_POWERS
        },
    }

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
def link_channel_to_game(
    game_id: str,
    req: LinkChannelRequest,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, Any]:
    """
    Link a Telegram channel to a game.

    This enables automated posting of maps, broadcasts, and notifications to the channel.
    """
    try:
        # Verify game exists
        if not game_service.exists(game_id):
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
        if not game_service.exists(game_id):
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

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

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

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

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

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # Get players data
        players_data = None
        try:
            row = db_service.get_game_by_game_id(game_id)
            players_list = db_service.get_players_by_game_id(int(row.id)) if row else []
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

        # Get channel info
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")

        channel_id = channel_info.get("channel_id")

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # Order history is not retained per-turn under the new engine.
        previous_supply_centers = None
        order_history = None

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


# --- Analytics Endpoints ---
@router.get("/games/{game_id}/channel/analytics")
def get_channel_analytics(
    game_id: str,
    channel_id: Optional[str] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get analytics events for a game's channel.
    
    Query parameters:
    - channel_id: Optional channel ID filter
    - event_type: Optional event type filter ('message_posted', 'player_activity', 'order_submitted', 'vote_cast', 'message_read')
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)
    """
    try:
        # Get channel info if channel_id not provided
        if not channel_id:
            channel_info = db_service.get_game_channel_info(game_id)
            if not channel_info:
                raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
            channel_id = channel_info.get("channel_id")
        
        # Get analytics events
        events = db_service.get_channel_analytics(
            game_id=game_id,
            channel_id=channel_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "status": "ok",
            "game_id": game_id,
            "channel_id": channel_id,
            "event_count": len(events),
            "events": events
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting analytics for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/analytics/summary")
def get_channel_analytics_summary(
    game_id: str,
    channel_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get aggregated analytics summary for a game's channel.
    
    Query parameters:
    - channel_id: Optional channel ID filter
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)
    """
    try:
        # Get channel info if channel_id not provided
        if not channel_id:
            channel_info = db_service.get_game_channel_info(game_id)
            if not channel_info:
                raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
            channel_id = channel_info.get("channel_id")
        
        # Get analytics summary
        summary = db_service.get_channel_analytics_summary(
            game_id=game_id,
            channel_id=channel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            "status": "ok",
            "game_id": game_id,
            "channel_id": channel_id,
            "summary": summary
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting analytics summary for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/analytics/engagement")
def get_channel_engagement_metrics(
    game_id: str,
    channel_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get engagement metrics for a game's channel.
    
    Returns metrics like:
    - Messages per day
    - Active players
    - Engagement rate
    - Response times
    
    Query parameters:
    - channel_id: Optional channel ID filter
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)
    """
    try:
        
        # Get channel info if channel_id not provided
        if not channel_id:
            channel_info = db_service.get_game_channel_info(game_id)
            if not channel_info:
                raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
            channel_id = channel_info.get("channel_id")
        
        # Get analytics summary
        summary = db_service.get_channel_analytics_summary(
            game_id=game_id,
            channel_id=channel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate additional engagement metrics
        total_events = summary.get("total_events", 0)
        message_count = summary.get("message_count", 0)
        player_activity_count = summary.get("player_activity_count", 0)
        unique_users = summary.get("unique_users", 0)
        
        # Calculate messages per day (if date range provided)
        messages_per_day = None
        if start_date and end_date:
            days = (end_date - start_date).days + 1
            if days > 0:
                messages_per_day = round(message_count / days, 2)
        
        # Engagement rate (player activity / total events)
        engagement_rate = None
        if total_events > 0:
            engagement_rate = round((player_activity_count / total_events) * 100, 2)
        
        return {
            "status": "ok",
            "game_id": game_id,
            "channel_id": channel_id,
            "metrics": {
                "total_events": total_events,
                "message_count": message_count,
                "player_activity_count": player_activity_count,
                "unique_users": unique_users,
                "messages_per_day": messages_per_day,
                "engagement_rate": engagement_rate,
                "events_by_type": summary.get("events_by_type", {}),
                "events_by_subtype": summary.get("events_by_subtype", {})
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting engagement metrics for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/analytics/players")
def get_player_activity_stats(
    game_id: str,
    channel_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Get player activity statistics for a game's channel.
    
    Query parameters:
    - channel_id: Optional channel ID filter
    - start_date: Optional start date filter (ISO format)
    - end_date: Optional end date filter (ISO format)
    """
    try:
        # Get channel info if channel_id not provided
        if not channel_id:
            channel_info = db_service.get_game_channel_info(game_id)
            if not channel_info:
                raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
            channel_id = channel_info.get("channel_id")
        
        # Get analytics events filtered by player activity
        events = db_service.get_channel_analytics(
            game_id=game_id,
            channel_id=channel_id,
            event_type='player_activity',
            start_date=start_date,
            end_date=end_date
        )
        
        # Group by user/power
        player_stats: Dict[str, Dict[str, Any]] = {}
        for event in events:
            user_id = event.get("user_id")
            power = event.get("power")
            key = f"user_{user_id}" if user_id else f"power_{power}" if power else "unknown"
            
            if key not in player_stats:
                player_stats[key] = {
                    "user_id": user_id,
                    "power": power,
                    "activity_count": 0,
                    "last_activity": None
                }
            
            player_stats[key]["activity_count"] += 1
            event_time = event.get("created_at")
            if event_time:
                if not player_stats[key]["last_activity"] or event_time > player_stats[key]["last_activity"]:
                    player_stats[key]["last_activity"] = event_time
        
        return {
            "status": "ok",
            "game_id": game_id,
            "channel_id": channel_id,
            "player_count": len(player_stats),
            "players": list(player_stats.values())
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting player activity stats for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

