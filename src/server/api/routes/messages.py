"""
Messaging API routes.

This module contains all endpoints related to private and broadcast messaging between players.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

from .auth import resolve_user_or_telegram, get_current_user, http_bearer
from ..client_timestamp import normalize_client_timestamp, sent_at_suffix
from ..shared import (
    db_service, game_service, scheduler_logger, logger, notify_players, notify_user,
    is_anonymous, power_label,
)
from persistence.database import MessageModel

router = APIRouter()


def _phase_code_for(game_id: str, numeric_game_id: int, sent_at: datetime) -> Optional[str]:
    """The phase a message written at ``sent_at`` belongs to.

    Normally the game's current phase. For a message the bot queued while the
    API was unreachable, ``sent_at`` can predate the current phase, and the
    snapshot trail says which phase was live then (``get_phase_code_at``) -- so
    a delayed message is filed under the phase the player was looking at, not
    the one it happened to arrive in. Best-effort: a failure here must not fail
    the message, it just leaves the column NULL.
    """
    try:
        view = game_service.view(str(game_id))
        current = view["phase"] if view else None
        historical = db_service.get_phase_code_at(numeric_game_id, sent_at)
        return historical or current
    except Exception as e:
        logger.debug(f"Could not resolve the phase for a message in game {game_id}: {e}")
        return None

# The longest text a message, broadcast or rumour may carry, in UTF-16 code
# units -- the unit Telegram counts its 4096-character limit in, and the one a
# browser's ``maxLength`` counts, so an emoji costs the same everywhere. Every
# message reaches someone as a Telegram DM or group post with a heading in
# front ("⏱ Delayed notification (from ...):" + "New private message in game
# N from FRANCE (<24-character nickname>) (sent ... UTC): "), at most about
# 160 units; 3500 leaves room for that with a wide margin.
# ``tests/test_message_reads_and_limits.py`` sends a message of exactly this length
# with the longest heading the code can produce and checks it fits.
MAX_MESSAGE_LENGTH = 3500


def text_length(text: str) -> int:
    """``text``'s length as Telegram (and a browser) counts it: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def check_message_text(text: str) -> None:
    """400 for a message nobody should receive: blank, or too long to deliver."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="A message cannot be empty.")
    length = text_length(text)
    if length > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"A message can be at most {MAX_MESSAGE_LENGTH} characters long (this one is {length}).",
        )


# --- Request Models ---
class SendMessageRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    recipient_power: Optional[str] = None
    text: str
    # When the sender actually composed the message (ISO-8601, UTC). Sent by
    # the bot for every message so one that waited in its offline queue is
    # stored -- and shown to the recipient -- with the time it was written,
    # not the time the tunnel came back. See ``server.api.client_timestamp``.
    client_timestamp: Optional[datetime] = None

class SendBroadcastRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    text: str
    client_timestamp: Optional[datetime] = None
    # A rumour: the broadcast goes to the same people, but names nobody. The
    # sender is stored for the record and never shown to anyone else.
    anonymous: bool = False

# --- Message Endpoints ---
@router.post("/games/{game_id}/message")
def send_private_message(
    game_id: str,
    req: SendMessageRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        check_message_text(req.text)
        # Get game model to get numeric ID for database operations
        game_model = db_service.get_game_by_game_id(str(game_id))
        if not game_model:
            raise HTTPException(status_code=404, detail="Game not found")
        # Validate sender is in the game (use numeric game.id)
        player = db_service.get_player_by_game_id_and_user_id(game_id=int(game_model.id), user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        # Validate recipient power exists in game and has a player assigned
        if req.recipient_power is None or req.recipient_power == "":  # type: ignore
            raise HTTPException(status_code=400, detail="Recipient power required for private message")
        recipient_power = req.recipient_power.upper()
        if recipient_power == str(player.power_name).upper():
            raise HTTPException(
                status_code=400,
                detail=f"You play {recipient_power}: a private message goes to another power.",
            )
        recipient_player = db_service.get_player_by_game_id_and_power(game_id=str(game_id), power=recipient_power)
        # A seat whose player quit still has a row, with no user: nobody would
        # ever read the message, so say so instead of storing it silently.
        if recipient_player is None or recipient_player.user_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot send a private message to {recipient_power}: no player is assigned to that power.",
            )
        sent_at = normalize_client_timestamp(req.client_timestamp)
        msg = db_service.create_message(
            game_id=int(game_model.id),  # type: ignore
            sender_user_id=int(user.id),  # type: ignore
            recipient_power=recipient_power,
            text=req.text,
            timestamp=sent_at,
            phase_code=_phase_code_for(str(game_id), int(game_model.id), sent_at),  # type: ignore
        )
        # Private message notification
        try:
            recipient_user_id = getattr(recipient_player, "user_id", None)
            if recipient_player is not None and recipient_user_id is not None:
                recipient_user = db_service.get_user_by_id(recipient_user_id)
                recipient_telegram_id = getattr(recipient_user, "telegram_id", None) if recipient_user is not None else None
                if recipient_telegram_id is not None:
                    # The sender is named by power -- and, in a public game, by name.
                    notify_user(
                        recipient_telegram_id,
                        f"New private message in game {game_id} from "
                        f"{power_label(game_id, str(player.power_name), user)}"
                        f"{sent_at_suffix(sent_at)}: {req.text}",
                    )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify private message: {e}")
        return {"status": "ok", "message_id": msg.id, "timestamp": msg.timestamp.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/broadcast")
def send_broadcast_message(
    game_id: str,
    req: SendBroadcastRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """A message to every player in the game, and to its linked group.

    ``game_id`` is the public id; the player lookup and the message row use
    the game's numeric primary key. With ``anonymous`` it is a rumour: the DMs
    and the group post name no power and no player.
    """
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        check_message_text(req.text)
        game_model = db_service.get_game_by_game_id(str(game_id))
        if not game_model:
            raise HTTPException(status_code=404, detail="Game not found")
        numeric_id = int(game_model.id)  # type: ignore
        # Validate sender is in the game
        player = db_service.get_player_by_game_id_and_user_id(game_id=numeric_id, user_id=int(user.id))  # type: ignore
        if player is None:
            raise HTTPException(status_code=403, detail="Sender not in game")
        sent_at = normalize_client_timestamp(req.client_timestamp)
        msg = db_service.create_message(
            game_id=numeric_id,
            sender_user_id=int(user.id),  # type: ignore
            recipient_power=None,
            text=req.text,
            timestamp=sent_at,
            phase_code=_phase_code_for(str(game_id), numeric_id, sent_at),
            anonymous=req.anonymous,
        )
        if req.anonymous:
            dm_heading = f"🕵️ Rumour in game {game_id}"
            group_heading = f"🕵️ Rumour in game {game_id}"
        else:
            sender = power_label(game_id, str(player.power_name), user)
            dm_heading = f"Broadcast in game {game_id} from {sender}"
            group_heading = f"📢 Broadcast in game {game_id} from {sender}"
        # Broadcast message notification. The sender is excluded: they have
        # the bot's own "Broadcast sent" confirmation (or, for a queued
        # broadcast, its "delivered" report), and hearing their own words back
        # as a DM was noise.
        try:
            notify_players(
                numeric_id,
                f"{dm_heading}{sent_at_suffix(sent_at)}: {req.text}",
                exclude_telegram_id=getattr(user, "telegram_id", None),
            )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify broadcast message: {e}")
        
        # Channel integration: forward the broadcast to a linked channel, via
        # bot_outbox like every other player-facing notification -- calling
        # straight into telegram_bot.channels here silently did nothing (it
        # only has a live Bot instance inside the bot's own container; see
        # api.shared._post_turn_to_channel's docstring for the full story).
        try:
            channel_info = db_service.get_game_channel_info(str(game_id))
            if channel_info and (channel_info.get("settings") or {}).get("auto_post_broadcasts", True):
                db_service.enqueue_bot_notification(
                    channel_info.get("channel_id"),
                    f"{group_heading}: {req.text}",
                    kind="channel_text",
                )
        except Exception as e:
            logger.debug(f"Channel integration check failed for broadcast: {e}")
        
        return {"status": "ok", "message_id": msg.id, "timestamp": msg.timestamp.isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/messages")
def get_game_messages(
    game_id: str,
    telegram_id: Optional[str] = None,
    bot_secret: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """The messages the caller may see: every broadcast, plus a player's own
    private messages (sent or received).

    No credentials at all is an anonymous reader, who sees broadcasts only.
    Credentials that are present but don't check out -- an invalid or expired
    Bearer token, or a ``telegram_id`` without the bot secret -- are a 401, not
    a silent fallback to the anonymous view: that fallback is how the bot once
    showed every player a log with their private messages missing.
    """
    try:
        user = None
        if credentials:
            user = get_current_user(credentials)  # 401 unless valid
        elif telegram_id:
            user = resolve_user_or_telegram(None, telegram_id, bot_secret=bot_secret)
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
        else:
            # Unauthenticated: only return public broadcast messages (no private messages)
            query = query.filter(MessageModel.recipient_power.is_(None))
        messages = query.order_by(MessageModel.timestamp.asc()).all()
        # Who sent each message, by the seat they hold now: ``sender_power``
        # always, ``sender_name`` in a public game only. An anonymous game hides
        # ``sender_user_id`` too -- a public game's player list maps it to a name.
        anonymous = is_anonymous(game_id)
        power_of: Dict[int, str] = {}
        name_of: Dict[int, Optional[str]] = {}
        for seat in db_service.get_players_by_game_id(int(game_model.id)):  # type: ignore
            if seat.user_id is not None:
                power_of[int(seat.user_id)] = str(seat.power_name)
                if not anonymous:
                    sender = db_service.get_user_by_id(int(seat.user_id))
                    name_of[int(seat.user_id)] = getattr(sender, "nickname", None) if sender else None
        reader_id = int(user.id) if user is not None else None  # type: ignore

        def hidden(m: MessageModel) -> bool:
            # A rumour names its sender to nobody but the sender themself, so
            # their own log still reads as theirs.
            return bool(m.anonymous) and (reader_id is None or int(m.sender_user_id) != reader_id)

        result = [
            {
                "id": m.id,
                "sender_user_id": None if anonymous or hidden(m) else m.sender_user_id,
                "sender_power": None if hidden(m) else power_of.get(int(m.sender_user_id)) if m.sender_user_id is not None else None,
                "sender_name": None if hidden(m) else name_of.get(int(m.sender_user_id)) if m.sender_user_id is not None else None,
                "anonymous": bool(m.anonymous),
                "recipient_power": m.recipient_power,
                "text": m.text,
                "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, 'isoformat') else str(m.timestamp),
                # The phase the message was written in; NULL for messages
                # predating this column. Lets a client group a game log by phase.
                "phase_code": m.phase_code,
            }
            for m in messages
        ]
        return {"messages": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

