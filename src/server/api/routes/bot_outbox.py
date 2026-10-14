"""The bot's pull endpoint for player notifications (the server-side outbox).

Server code never talks to Telegram and never talks to the bot. It writes a
row to ``bot_outbox`` (``api/shared.notify_user``) and returns. The bot, from
its own container, long-polls here:

    GET  /bot/outbox?limit=50&wait=25 -> undelivered rows, oldest first; with
                                         ``wait``, held until a row exists or
                                         ``wait`` seconds pass (then ``[]``)
    POST /bot/outbox/ack             -> {"delivered": [ids], "failed": {id: error}}

Pull rather than push, deliberately. Push needs the *server* to know where the
bot is and to retry on its own schedule; pull needs nothing but the API to
be up at some point, and the same poll that delivers a fresh notification
drains everything that accumulated while the link was down. It also means the
API exposes no notification-shaped surface at all -- the bot is the
only caller, authenticated by ``X-Bot-Secret`` (``require_bot_secret``; a
browser JWT is not accepted).

Delivery is at-least-once: a row is acked only after Telegram has accepted the
message, so a crash between send and ack can repeat a DM. That is the right
side to err on for "no message is ever lost".

The long-poll (``long_poll.py``) only changes *when* the response is sent:
rows are read the same way, and nothing is marked until the ack. The response
carries ``X-Outbox-Count`` so the access-log filter (``access_log.py``) can
drop the empty polls and keep the ones that delivered something.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from persistence.database_service import add_bot_outbox_listener

from .auth import require_bot_secret
from ..access_log import OUTBOX_COUNT_HEADER
from ..long_poll import wait_for_rows, wake_waiters
from ..shared import db_service, logger

# Longest ``wait`` accepted. The bot asks for less (``NOTIFY_WAIT_SECONDS``).
MAX_WAIT_SECONDS = 60

add_bot_outbox_listener(wake_waiters)

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
async def get_outbox(
    response: Response,
    limit: int = Query(50, ge=1, le=500),
    after_id: int = Query(0, ge=0),
    wait: float = Query(0, ge=0, le=MAX_WAIT_SECONDS),
    _: None = Depends(require_bot_secret),
) -> Dict[str, Any]:
    """Undelivered notifications, oldest first.

    ``wait`` > 0 makes it a long-poll: when nothing is pending, the request
    is held (without a database connection) until a row is committed or
    ``wait`` seconds pass, and then returns what is there (``[]`` on timeout).
    """
    items = await wait_for_rows(
        lambda: db_service.fetch_pending_bot_notifications(limit=limit, after_id=after_id), wait
    )
    response.headers[OUTBOX_COUNT_HEADER] = str(len(items))
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
