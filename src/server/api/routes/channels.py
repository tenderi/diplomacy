"""
Channel management API routes.

This module handles Telegram channel integration for games:
- Linking/unlinking games to channels
- Channel settings management
- Automated content posting to channels
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, Optional
from datetime import datetime

from .auth import get_current_user_optional, http_bearer
from ..shared import db_service, game_service, is_admin_token, is_bot_secret, logger
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


def require_game_player_or_bot(
    game_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_bot_secret: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Who may change a game's linked Telegram group or post into it: the bot
    (which checks that the Telegram user is a player before calling), an admin,
    or a web user seated in the game.

    Until this, linking needed only *some* login and every other write route --
    unlink, settings, and the map/broadcast/thread/timeline/dashboard/results
    posts -- needed nothing at all: anyone could unlink a game's group or make
    the bot post into it.
    """
    if is_bot_secret(x_bot_secret) or is_admin_token(x_admin_token):
        return
    user = get_current_user_optional(credentials)
    row = db_service.get_game_by_game_id(game_id)
    if user is not None and row is not None:
        if db_service.get_player_by_game_id_and_user_id(game_id=int(row.id), user_id=int(user.id)) is not None:
            return
    raise HTTPException(status_code=403, detail="Only a player in this game can change its Telegram group")


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


@router.post("/games/{game_id}/channel/link")
def link_channel_to_game(
    game_id: str,
    req: LinkChannelRequest,
    _: None = Depends(require_game_player_or_bot),
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


@router.delete("/games/{game_id}/channel/unlink", dependencies=[Depends(require_game_player_or_bot)])
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


@router.get("/games/{game_id}/channel", dependencies=[Depends(require_game_player_or_bot)])
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


@router.put("/games/{game_id}/channel/settings", dependencies=[Depends(require_game_player_or_bot)])
@router.post("/games/{game_id}/channel/settings", dependencies=[Depends(require_game_player_or_bot)])
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


@router.post("/games/{game_id}/channel/map", dependencies=[Depends(require_game_player_or_bot)])
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


@router.post("/games/{game_id}/channel/broadcast", dependencies=[Depends(require_game_player_or_bot)])
def post_broadcast_to_channel(game_id: str, req: BroadcastMessageRequest) -> Dict[str, Any]:
    """Queue a broadcast message for the linked channel, with optional threading.

    Queued onto ``bot_outbox``, not posted synchronously -- see
    ``api.shared._post_turn_to_channel``'s docstring for why every channel
    post goes through there now instead of calling ``telegram_bot.channels``
    directly (it only has a live ``Bot`` instance inside the bot's own
    container). No ``message_id`` comes back; the send happens on the bot's
    next poll.
    """
    try:
        from ...telegram_bot.utils import escape_markdown

        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        channel_id = channel_info.get("channel_id")

        # req.message is free text a caller supplied -- escape it before
        # folding it into a Markdown-formatted post, or an unescaped
        # `_`/`*`/`` ` ``/`[` in it 400s the whole send.
        safe_message = escape_markdown(req.message)
        if req.power:
            formatted = f"📢 *{req.power}* → All Powers\n\n{safe_message}"
        else:
            formatted = f"📢 *PUBLIC BROADCAST*\n\n{safe_message}"

        outbox_id = db_service.enqueue_bot_notification(
            channel_id, formatted, kind="channel_text",
            payload={"parse_mode": "Markdown", "reply_to_message_id": req.reply_to_message_id},
        )

        return {
            "status": "queued",
            "message": f"Broadcast queued for channel {channel_id}",
            "channel_id": channel_id,
            "outbox_id": outbox_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting broadcast to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/thread", dependencies=[Depends(require_game_player_or_bot)])
def create_discussion_thread_endpoint(game_id: str, req: CreateThreadRequest) -> Dict[str, Any]:
    """Queue creation of a discussion thread (forum topic) for the linked channel.

    Queued, like every other channel post (see ``/channel/broadcast``'s
    docstring) -- and unlike the others, genuinely fire-and-forget rather than
    just decoupled: creating a forum topic only makes sense from inside the
    bot's own process (nothing here has a ``Bot`` instance to call
    ``create_forum_topic`` on even synchronously), and nothing downstream
    reads a thread id back yet, so none is returned. If a future caller needs
    one, that's a bot-to-server report-back this route doesn't have.
    """
    try:
        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        channel_id = channel_info.get("channel_id")

        title = f"{req.topic} - {req.phase}" if req.phase else req.topic
        outbox_id = db_service.enqueue_bot_notification(
            channel_id, title, kind="channel_create_thread",
        )

        return {
            "status": "queued",
            "message": f"Discussion thread queued for channel {channel_id}",
            "channel_id": channel_id,
            "outbox_id": outbox_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating discussion thread for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/channel/timeline", dependencies=[Depends(require_game_player_or_bot)])
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


@router.post("/games/{game_id}/channel/timeline", dependencies=[Depends(require_game_player_or_bot)])
def post_timeline_update(game_id: str) -> Dict[str, Any]:
    """Queue a timeline update for the linked channel. See ``/channel/broadcast``'s
    docstring for why this queues onto ``bot_outbox`` rather than posting inline."""
    try:
        from ...telegram_bot.channels import format_historical_timeline

        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        channel_id = channel_info.get("channel_id")

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        formatted = format_historical_timeline(game_state_dict)
        outbox_id = db_service.enqueue_bot_notification(
            channel_id, formatted, kind="channel_text", payload={"parse_mode": "Markdown"},
        )

        return {
            "status": "queued",
            "message": f"Timeline update queued for channel {channel_id}",
            "channel_id": channel_id,
            "outbox_id": outbox_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting timeline update to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/dashboard", dependencies=[Depends(require_game_player_or_bot)])
def post_player_dashboard(game_id: str) -> Dict[str, Any]:
    """Queue the player status dashboard for the linked channel. See
    ``/channel/broadcast``'s docstring for why this queues onto ``bot_outbox``
    rather than posting inline."""
    try:
        from ...telegram_bot.channels import format_player_dashboard

        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        channel_id = channel_info.get("channel_id")

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

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

        formatted = format_player_dashboard(game_state_dict, players_data)
        outbox_id = db_service.enqueue_bot_notification(
            channel_id, formatted, kind="channel_text", payload={"parse_mode": "Markdown"},
        )

        return {
            "status": "queued",
            "message": f"Player dashboard queued for channel {channel_id}",
            "channel_id": channel_id,
            "outbox_id": outbox_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting player dashboard to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/channel/battle_results", dependencies=[Depends(require_game_player_or_bot)])
def post_battle_results(game_id: str) -> Dict[str, Any]:
    """Queue formatted battle results for the linked channel. See
    ``/channel/broadcast``'s docstring for why this queues onto ``bot_outbox``
    rather than posting inline."""
    try:
        from ...telegram_bot.channels import format_battle_results

        channel_info = db_service.get_game_channel_info(game_id)
        if not channel_info:
            raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
        channel_id = channel_info.get("channel_id")

        game_state_dict = _legacy_state_dict(game_id)
        if game_state_dict is None:
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        # order_history/previous_supply_centers are left None: game_service now
        # does retain per-turn order/resolution history (Track W, v2.7.90), but
        # its {turn: {power: [order_str]}} shape doesn't match what
        # format_battle_results expects here and adapting it is unstarted --
        # not "the engine doesn't have this" any more, just not plumbed through.
        previous_supply_centers = None
        order_history = None

        formatted = format_battle_results(game_state_dict, order_history, previous_supply_centers)
        outbox_id = db_service.enqueue_bot_notification(
            channel_id, formatted, kind="channel_text", payload={"parse_mode": "Markdown"},
        )

        return {
            "status": "queued",
            "message": f"Battle results queued for channel {channel_id}",
            "channel_id": channel_id,
            "outbox_id": outbox_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error posting battle results to channel for game {game_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Analytics Endpoints ---
@router.get("/games/{game_id}/channel/analytics", dependencies=[Depends(require_game_player_or_bot)])
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


@router.get("/games/{game_id}/channel/analytics/summary", dependencies=[Depends(require_game_player_or_bot)])
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


@router.get("/games/{game_id}/channel/analytics/engagement", dependencies=[Depends(require_game_player_or_bot)])
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


@router.get("/games/{game_id}/channel/analytics/players", dependencies=[Depends(require_game_player_or_bot)])
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

