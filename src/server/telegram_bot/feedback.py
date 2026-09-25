"""/feedback <text> -- tell the maintainer something is wrong (or right).

Sent through the durable queue (``api_post_reliable``) like orders and
messages: a report written while the server is down is exactly the one that
must not be lost. It names the player's current game, if they have one, so
the server can record the phase it was in.
"""
from telegram import Update
from telegram.ext import ContextTypes

from .api_client import api_post_reliable, queued_reply
from .game_context import current_game

USAGE = (
    "💬 Tell the maintainer what happened: /feedback followed by your message, e.g.\n"
    "/feedback the map showed my fleet in the wrong place after the retreat\n\n"
    "Your current game and its phase are attached automatically."
)


async def feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        return
    text = " ".join(context.args or []).strip()
    if not text:
        await update.message.reply_text(USAGE)
        return
    user_id = str(user.id)
    body = {"telegram_id": user_id, "text": text, "source": "telegram", "game_id": current_game(user_id)}
    outcome = api_post_reliable(
        "/feedback", body, chat_id=update.message.chat_id, description=f"feedback: {text[:60]}"
    )
    if outcome.status == "delivered":
        reply = "🙏 Thanks -- your feedback has been sent to the maintainer."
    elif outcome.status == "queued":
        reply = queued_reply(outcome)
    else:
        reply = f"❌ Feedback was not sent: {outcome.error}"
    await update.message.reply_text(reply)
