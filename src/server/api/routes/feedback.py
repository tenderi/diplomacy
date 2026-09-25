"""Player feedback: a report from the bot's ``/feedback`` or the web's feedback
page, stored in ``feedback`` and DMed to the maintainer
(``DIPLOMACY_ADMIN_TELEGRAM_ID``, through the outbox like any notification).

Any signed-in player may send one, as themselves: Bearer, or ``telegram_id``
with the bot secret (``resolve_user_or_telegram``). A report names the game it
is about when the player is in one; the game's phase is recorded with it, so
"the map was wrong" can be matched to the turn. ``GET /admin/feedback`` lists
them.
"""
from datetime import timedelta
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from persistence.database import utcnow_naive
from .admin import require_admin
from .auth import http_bearer, resolve_user_or_telegram
from .. import shared as api_shared
from ..shared import db_service, game_service, notify_user

router = APIRouter()

MAX_FEEDBACK_CHARS = 2000
# Per player, per hour: enough for a bad evening, not enough to flood the DMs.
MAX_FEEDBACK_PER_HOUR = 10


class FeedbackRequest(BaseModel):
    text: str
    game_id: Optional[str] = None
    source: Literal["telegram", "web"] = "web"
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


@router.post("/feedback")
def send_feedback(
    req: FeedbackRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Feedback is empty.")
    if len(text) > MAX_FEEDBACK_CHARS:
        raise HTTPException(
            status_code=400, detail=f"Feedback is limited to {MAX_FEEDBACK_CHARS} characters."
        )
    since = utcnow_naive() - timedelta(hours=1)
    if db_service.count_feedback_since(int(user.id), since) >= MAX_FEEDBACK_PER_HOUR:
        raise HTTPException(
            status_code=429, detail="That is a lot of feedback in one hour -- try again later."
        )
    game_id = req.game_id.strip() if req.game_id and req.game_id.strip() else None
    meta = game_service.meta(game_id) if game_id is not None else None
    phase_code = meta.get("phase_code") if meta is not None else None
    feedback_id = db_service.create_feedback(
        user_id=int(user.id), source=req.source, text=text, game_id=game_id, phase_code=phase_code
    )
    if api_shared.ADMIN_TELEGRAM_ID is not None:
        who = user.full_name or getattr(user, "email", None) or f"user {user.id}"
        where = f", game {game_id}" + (f" ({phase_code})" if phase_code else "") if game_id else ""
        notify_user(api_shared.ADMIN_TELEGRAM_ID, f"💬 Feedback #{feedback_id} from {who} ({req.source}{where}):\n\n{text}")
    return {"status": "ok", "id": feedback_id}


@router.get("/admin/feedback", dependencies=[Depends(require_admin)])
def list_feedback(limit: int = 100) -> Dict[str, Any]:
    return {"feedback": db_service.list_feedback(limit=max(1, min(limit, 500)))}
