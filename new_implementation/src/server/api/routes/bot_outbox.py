"""The bot's pull endpoint for player notifications (the server-side outbox).

Server code never talks to Telegram and never talks to the bot. It writes a
row to ``bot_outbox`` (``api/shared.notify_user``) and returns. The bot, from
its own side of the WireGuard tunnel, polls here every few seconds:

    GET  /bot/outbox?limit=50        -> undelivered rows, oldest first
    POST /bot/outbox/ack             -> {"delivered": [ids], "failed": {id: error}}

Pull rather than push, deliberately. Push needs the *server* to know where the
bot is and to retry on its own schedule; pull needs nothing but the tunnel to
be up at some point, and the same poll that delivers a fresh notification
drains everything that accumulated while the link was down. It also means the
home server exposes no notification-shaped surface at all -- the bot is the
only caller, authenticated by ``X-Bot-Secret`` (``require_bot_secret``; a
browser JWT is not accepted).

Delivery is at-least-once: a row is acked only after Telegram has accepted the
message, so a crash between send and ack can repeat a DM. That is the right
side to err on for "no message is ever lost".
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from .auth import require_bot_secret
from ..shared import db_service, logger

router = APIRouter()


class AckRequest(BaseModel):
    """Rows the bot has finished with.

    ``delivered``: Telegram accepted the message.
    ``failed``: Telegram rejected it *permanently* (blocked, chat not found);
    mapped id -> error. Also marked delivered so it is not retried forever, but
    the error is kept on the row.
    Transient failures are simply not reported; the row comes back next poll.
    """
    delivered: List[int] = []
    failed: Dict[int, str] = {}


@router.get("/bot/outbox")
def get_outbox(
    limit: int = Query(50, ge=1, le=500),
    after_id: int = Query(0, ge=0),
    _: None = Depends(require_bot_secret),
) -> Dict[str, Any]:
    """Undelivered notifications, oldest first."""
    items = db_service.fetch_pending_bot_notifications(limit=limit, after_id=after_id)
    return {"items": items, "count": len(items)}


@router.post("/bot/outbox/ack")
def ack_outbox(
    req: AckRequest,
    _: None = Depends(require_bot_secret),
) -> Dict[str, Any]:
    """Mark rows delivered (or permanently failed)."""
    updated = db_service.ack_bot_notifications(req.delivered, req.failed)
    if req.failed:
        logger.warning(
            "Bot reported %d permanently undeliverable notification(s): %s",
            len(req.failed), req.failed,
        )
    return {"status": "ok", "updated": updated}


@router.get("/bot/outbox/stats")
def outbox_stats(_: None = Depends(require_bot_secret)) -> Dict[str, Optional[int]]:
    """How much is waiting. For the bot's own health reporting."""
    pending = db_service.fetch_pending_bot_notifications(limit=500)
    return {"pending": len(pending), "oldest_id": pending[0]["id"] if pending else None}
