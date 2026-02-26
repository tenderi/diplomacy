"""
Telegram /link command: link this Telegram account to a browser account using a one-time code.
"""
import logging
import requests

from telegram import Update
from telegram.ext import ContextTypes

from .api_client import api_post

logger = logging.getLogger("diplomacy.telegram_bot.link_account")


async def link_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /link <code>. Link this Telegram to the account that generated the code on the web app."""
    if not update.effective_user or not update.effective_message:
        return
    text = (update.effective_message.text or "").strip()
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "Usage: /link <code>\n\n"
            "Get a code from the web app: open the game in your browser, go to \"Link Telegram\", "
            "generate a code, then send it here.\nExample: /link 123456"
        )
        return
    code = parts[1].strip()
    telegram_id = str(update.effective_user.id)
    try:
        result = api_post("/auth/telegram/link", {"telegram_id": telegram_id, "code": code})
        msg = result.get("message", "Telegram linked to your account.")
        await update.message.reply_text(f"✅ {msg}")
    except requests.HTTPError as e:
        if e.response is not None:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = e.response.text or str(e)
        else:
            detail = str(e)
        if e.response is not None and e.response.status_code == 409:
            await update.message.reply_text(f"❌ This Telegram is already linked to another account.")
        else:
            await update.message.reply_text(
                f"❌ Invalid or expired code. Get a new code from the web app (Link Telegram).\nDetails: {detail}"
            )
        logger.warning(f"Link failed for telegram_id={telegram_id}: {detail}")
    except Exception as e:
        logger.exception(f"Link error for telegram_id={telegram_id}: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again or get a new code from the web app.")
