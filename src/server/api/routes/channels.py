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

from sqlalchemy.exc import IntegrityError

from persistence.database_service import ChannelTakenError

from .auth import get_current_user_optional, http_bearer, require_bot_secret
from ..shared import db_service, game_service, is_admin_token, is_bot_secret, logger, phase_label, player_rows
from ...response_cache import invalidate_cache

_ALL_POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}


def _legacy_state_dict(game_id: str) -> Optional[Dict[str, Any]]:
    """Build the channel-posting game_state dict from the new engine's view.

    It goes to a group, so it says only *whether* each power has submitted
    (as ``/orders_status`` does), never the orders themselves.
    """
    v = game_service.view(game_id)
    pending = game_service.pending_orders_view(game_id)
    if v is None or pending is None:
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
        "powers": {
            p: {
                "is_eliminated": not units_by_power.get(p) and not sc_by_power.get(p),
                "controlled_supply_centers": sc_by_power.get(p, []),
                "orders_submitted": bool(pending.get(p)),
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
    """Who may unlink a game's Telegram group, change its settings or post into
    it: the bot (which checks that the Telegram user is a player before
    calling), an admin, or a web user seated in the game. Linking is stricter
    (``require_bot_or_admin``).

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
    # The Telegram user the bot acts for: a player of the game the group
    # belongs to may move the group's link to this game.
    telegram_id: Optional[str] = None


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


def require_bot_or_admin(
    x_bot_secret: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Who may link a game to a Telegram group: the bot, with the id of the
    group it saw the command in (``/linkgroup``, ``/newgame``, ``/start
    link_<id>``), or an admin. Not a web login, not even a player's: any chat
    id would do, so a player who knows a group's id could squat it with their
    game, and the group's own members could then neither start nor link a game
    there. The web page links a group through the bot (``startgroup``)."""
    if is_bot_secret(x_bot_secret) or is_admin_token(x_admin_token):
        return
    raise HTTPException(
        status_code=403,
        detail="A game is linked to a Telegram group from inside the group: add the bot and send /linkgroup there.",
    )


def link_or_409(
    game_id: str,
    channel_id: str,
    channel_name: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
    *,
    displacer_user_id: Optional[int] = None,
    any_displacer: bool = False,
) -> Optional[str]:
    """Link ``game_id`` to the group (``DatabaseService.link_game_to_channel``)
    and return the game that lost it, or raise 409 when the group belongs to a
    game ``displacer_user_id`` doesn't play. Invalidates both games' caches."""
    try:
        replaced = db_service.link_game_to_channel(
            game_id=game_id,
            channel_id=channel_id,
            channel_name=channel_name,
            settings=settings or {},
            displacer_user_id=displacer_user_id,
            any_displacer=any_displacer,
        )
    except ChannelTakenError as e:
        raise HTTPException(
            status_code=409,
            detail=f"That Telegram group already belongs to game {e.game_id}. "
            f"Only a player of game {e.game_id} can move the group to another game.",
        ) from e
    except IntegrityError as e:  # another game took the group between the lock and the write
        raise HTTPException(status_code=409, detail="The group was linked to another game just now; try again.") from e
    invalidate_cache(f"games/{game_id}")
    if replaced is not None:
        invalidate_cache(f"games/{replaced}")
    return replaced


@router.post("/games/{game_id}/channel/link", dependencies=[Depends(require_bot_or_admin)])
def link_channel_to_game(
    game_id: str,
    req: LinkChannelRequest,
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Link a Telegram group to a game. **Bot or admin only** (``require_bot_or_admin``):
    the bot sends the id of the group the command was typed in, after checking
    that the Telegram user plays this game.

    This enables automated posting of maps, broadcasts, and notifications to the group.
    A group has at most one game: linking another game to it **moves** the link,
    and ``replaced_game_id`` names the game that lost it (null if none did).

    Moving a link is allowed only to a **player of the game that loses it** --
    the Telegram user the bot names in ``telegram_id`` -- or an admin; anyone
    else gets 409 (the game would otherwise drop out of its group, turn up in
    the public list and become joinable from the web).
    """
    try:
        if not game_service.exists(game_id):
            raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

        actor = db_service.get_user_by_telegram_id(req.telegram_id) if req.telegram_id else None
        replaced = link_or_409(
            game_id,
            req.channel_id,
            req.channel_name,
            req.settings,
            displacer_user_id=int(actor.id) if actor is not None else None,
            any_displacer=is_admin_token(x_admin_token),
        )
        return {
            "status": "ok",
            "message": f"Game {game_id} linked to channel {req.channel_id}",
            "game_id": game_id,
            "channel_id": req.channel_id,
            "replaced_game_id": replaced,
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


@router.get("/channels/{channel_id}/game", dependencies=[Depends(require_bot_secret)])
def get_channel_game(channel_id: str) -> Dict[str, Any]:
    """The game a Telegram group belongs to (at most one), for a command typed
    in that group: ``{"linked": true, "game_id", "channel_name"}`` or
    ``{"linked": false}``. Bot only: which game a group plays is for its
    members, and only the bot knows who they are."""
    found = db_service.get_game_by_channel(channel_id)
    if found is None:
        return {"linked": False}
    return {"linked": True, **found}


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
    """Queue the current board for the linked group, now (the same post every
    processed turn makes on its own; see ``api.shared._post_turn_to_channel``). The bot
    fetches the image from ``payload.path`` when it sends."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")
    channel_info = db_service.get_game_channel_info(game_id)
    if not channel_info:
        raise HTTPException(status_code=404, detail=f"Game {game_id} is not linked to a channel")
    channel_id = channel_info.get("channel_id")
    outbox_id = db_service.enqueue_bot_notification(
        channel_id,
        f"🗺️ Game {game_id} · {phase_label(view['phase'])}: the board now",
        kind="channel_map",
        payload={"game_id": game_id, "path": f"/games/{game_id}/map"},
    )
    return {
        "status": "queued",
        "message": f"Map queued for channel {channel_id}",
        "channel_id": channel_id,
        "outbox_id": outbox_id,
    }


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
            # Names (public games only) ride along with each power.
            players_data = player_rows(row) if row else []
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


# --- Analytics Endpoints ---