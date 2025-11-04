"""
Notification endpoint for the Telegram bot.
"""
import logging

from fastapi import FastAPI
from pydantic import BaseModel
from telegram.ext import Application

logger = logging.getLogger("diplomacy.telegram_bot.notifications")

# FastAPI app for notification endpoint
fastapi_app = FastAPI()


class NotifyRequest(BaseModel):
    """Request model for notification endpoint."""
    telegram_id: int
    message: str


@fastapi_app.post("/notify")
async def notify(req: NotifyRequest):
    """Send a notification message to a Telegram user."""
    try:
        # Send message using the running Telegram bot application
        if not hasattr(notify, "telegram_app"):
            return {"status": "error", "detail": "Bot not initialized"}
        telegram_app: Application = notify.telegram_app
        await telegram_app.bot.send_message(chat_id=req.telegram_id, text=req.message)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {"status": "error", "detail": str(e)}

