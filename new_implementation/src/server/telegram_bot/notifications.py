"""The bot's two background loops, and the ``/queue`` command.

This module used to be a FastAPI app on port 8081 that the API ``POST``ed
player notifications at. That worked only because both processes shared one
host; across the VPS/home split it would have lost every DM sent while the
tunnel was down, and it made the bot the one component that needed an inbound
port. It is gone. Nothing listens here any more. Instead:

**Notification loop** (server -> player). Every ``NOTIFY_POLL_SECONDS`` the
bot asks the API for undelivered rows (``GET /bot/outbox``), sends each to its
Telegram chat, and acks the ones Telegram accepted (``POST /bot/outbox/ack``).
The server commits every notification to Postgres first, so a tunnel outage
of any length only delays them; when the link returns, one poll drains the
backlog in order. A notification delivered noticeably late is prefixed with
the time it was created so the player can tell.

**Replay loop** (player -> server). Every ``OUTBOX_POLL_SECONDS`` the bot
retries whatever is in its own durable queue (``outbox.py``) -- orders and
messages that could not be delivered when the player sent them -- and DMs
each player the result of each entry that finished: what was delivered (with
the original send time) or why the server refused it.

Both loops touch ``HEARTBEAT_PATH`` on every tick; the container healthcheck
watches that file's age.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from telegram import Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import Application, ContextTypes

from .api_client import ApiUnreachableError, DeliveryResult, api_get, api_post, drain_outbox_once
from .outbox import get_outbox

logger = logging.getLogger("diplomacy.telegram_bot.notifications")

NOTIFY_POLL_SECONDS = float(os.environ.get("DIPLOMACY_NOTIFY_POLL_SECONDS", "3"))
OUTBOX_POLL_SECONDS = float(os.environ.get("DIPLOMACY_OUTBOX_POLL_SECONDS", "5"))
HEARTBEAT_PATH = Path(os.environ.get("DIPLOMACY_BOT_HEARTBEAT", "/tmp/diplomacy-bot-heartbeat"))  # nosec B108
# A notification older than this when delivered gets its creation time prefixed.
LATE_THRESHOLD = timedelta(seconds=90)
# Telegram permanently rejects these (chat gone, bot blocked); do not retry.
_PERMANENT_TELEGRAM_ERRORS = (Forbidden, BadRequest)
# These mean "Telegram is not reachable/ready right now"; retry next tick.
_TRANSIENT_TELEGRAM_ERRORS = (NetworkError, TimedOut, RetryAfter)

# Connectivity state, so the logs say "unreachable" once and "back" once
# rather than every three seconds.
_api_reachable: Optional[bool] = None


def _note_reachability(reachable: bool) -> None:
    global _api_reachable
    if _api_reachable is reachable:
        return
    _api_reachable = reachable
    if reachable:
        logger.info("API reachable again; %d queued write(s) waiting", get_outbox().count_pending())
    else:
        logger.warning("API unreachable; player writes are being queued locally")


def api_reachable() -> Optional[bool]:
    """Last observed connectivity (None until the first poll)."""
    return _api_reachable


def touch_heartbeat() -> None:
    try:
        HEARTBEAT_PATH.touch()
    except OSError as e:  # /tmp missing in some odd sandbox: not worth dying for
        logger.debug("Could not touch heartbeat %s: %s", HEARTBEAT_PATH, e)


# ---------------------------------------------------------------------------
# Server -> player
# ---------------------------------------------------------------------------

def render_notification(item: dict[str, Any], now: Optional[datetime] = None) -> str:
    """The text to send for one outbox row, with a "delayed" prefix when late."""
    text = item.get("message", "")
    created_raw = item.get("created_at")
    if not created_raw:
        return text
    try:
        created = datetime.fromisoformat(created_raw)
    except ValueError:
        return text
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now - created < LATE_THRESHOLD:
        return text
    if created.date() == now.date():
        stamp = f"{created:%H:%M} UTC"
    else:
        stamp = f"{created:%Y-%m-%d %H:%M} UTC"
    return f"⏱ Delayed notification (from {stamp}):\n{text}"


async def deliver_pending_notifications(bot: Any, limit: int = 50) -> tuple[int, int]:
    """One poll: fetch, send, ack. Returns ``(delivered, permanently_failed)``.

    A transient Telegram error stops the batch (the remaining rows are not
    acked and come back next poll) so ordering is preserved. A permanent one
    is reported in the ack as failed so the server stops offering the row.
    """
    try:
        page = await asyncio.to_thread(api_get, f"/bot/outbox?limit={limit}")
    except ApiUnreachableError:
        _note_reachability(False)
        return 0, 0
    _note_reachability(True)
    items = page.get("items", []) if page else []
    if not items:
        return 0, 0

    delivered: list[int] = []
    failed: dict[int, str] = {}
    for item in items:
        chat_id = int(item["telegram_id"])
        try:
            await bot.send_message(chat_id=chat_id, text=render_notification(item))
        except _PERMANENT_TELEGRAM_ERRORS as e:
            failed[int(item["id"])] = f"{type(e).__name__}: {e}"
            logger.warning("Notification #%s to %s permanently undeliverable: %s", item["id"], chat_id, e)
        except _TRANSIENT_TELEGRAM_ERRORS as e:
            logger.warning("Telegram not reachable while delivering #%s: %s; will retry", item["id"], e)
            break
        else:
            delivered.append(int(item["id"]))

    if delivered or failed:
        try:
            await asyncio.to_thread(
                api_post, "/bot/outbox/ack", {"delivered": delivered, "failed": failed}
            )
        except ApiUnreachableError:
            # Sent but not acked: the rows come back next poll and the players
            # may see them twice. At-least-once is the correct side of this.
            logger.warning("Delivered %d notification(s) but could not ack them; they may repeat", len(delivered))
    return len(delivered), len(failed)


async def notification_loop(app: Application) -> None:
    while True:
        touch_heartbeat()
        try:
            await deliver_pending_notifications(app.bot)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # keep polling no matter what one tick does
            logger.error("Notification poll failed: %s", e)
        await asyncio.sleep(NOTIFY_POLL_SECONDS)


# ---------------------------------------------------------------------------
# Player -> server
# ---------------------------------------------------------------------------

def format_delivery_report(result: DeliveryResult) -> str:
    """The DM a player gets when a queued write finally finishes."""
    entry = result.entry
    when = entry.sent_at_label()
    if result.status == "delivered":
        lines = [f"📬 Delivered (queued since {when}): {entry.description}"]
        results = (result.response or {}).get("results")
        if isinstance(results, list) and results:
            from .orders import format_order_results  # local: orders imports api_client
            lines.append(format_order_results(results))
        return "\n".join(lines)
    return (
        f"❌ Not delivered (queued since {when}): {entry.description}\n"
        f"The server refused it: {result.error}"
    )


async def replay_outbox(bot: Any) -> list[DeliveryResult]:
    finished = await asyncio.to_thread(drain_outbox_once)
    for result in finished:
        try:
            await bot.send_message(chat_id=result.entry.chat_id, text=format_delivery_report(result))
        except _PERMANENT_TELEGRAM_ERRORS as e:
            logger.warning("Could not report outbox #%d to chat %s: %s", result.entry.id, result.entry.chat_id, e)
        except _TRANSIENT_TELEGRAM_ERRORS as e:
            logger.warning("Telegram not reachable while reporting outbox #%d: %s", result.entry.id, e)
    return finished


async def outbox_replay_loop(app: Application) -> None:
    tick = 0
    while True:
        touch_heartbeat()
        try:
            await replay_outbox(app.bot)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Outbox replay failed: %s", e)
        tick += 1
        if tick % 720 == 0:  # roughly hourly at the default 5 s
            try:
                get_outbox().purge_finished()
            except Exception as e:
                logger.warning("Outbox purge failed: %s", e)
        await asyncio.sleep(OUTBOX_POLL_SECONDS)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

_tasks: list[asyncio.Task] = []


def start_background_loops(app: Application) -> list[asyncio.Task]:
    """Start both loops on the running event loop (call from ``post_init``)."""
    loop = asyncio.get_running_loop()
    _tasks[:] = [
        loop.create_task(notification_loop(app), name="diplomacy-notifications"),
        loop.create_task(outbox_replay_loop(app), name="diplomacy-outbox-replay"),
    ]
    logger.info(
        "Background loops started (notifications every %.0fs, outbox replay every %.0fs); %d queued write(s)",
        NOTIFY_POLL_SECONDS, OUTBOX_POLL_SECONDS, get_outbox().count_pending(),
    )
    return list(_tasks)


async def stop_background_loops(app: Application) -> None:
    for task in _tasks:
        task.cancel()
    for task in _tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _tasks.clear()


# ---------------------------------------------------------------------------
# /queue
# ---------------------------------------------------------------------------

async def queue_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show this player's queued writes and the last few finished ones."""
    user = update.effective_user
    if not user or not update.message:
        return
    outbox = get_outbox()
    pending = outbox.pending(chat_id=user.id)
    recent = outbox.recent(chat_id=user.id, limit=5)

    reachable = api_reachable()
    if reachable is None:
        link = "unknown (no poll yet)"
    else:
        link = "✅ reachable" if reachable else "⚠️ unreachable -- writes are being queued"
    lines = [f"🔗 Game server: {link}"]

    if pending:
        lines.append(f"\n📮 Queued ({len(pending)}), oldest first:")
        for e in pending:
            detail = f" -- {e.attempts} attempt{'s' if e.attempts != 1 else ''}" if e.attempts else ""
            lines.append(f"• #{e.id} {e.sent_at_label()}: {e.description}{detail}")
    else:
        lines.append("\n📮 Nothing queued.")

    if recent:
        lines.append("\n🕘 Recently finished:")
        for e in recent:
            mark = "✅" if e.state == "delivered" else "❌"
            lines.append(f"• {mark} #{e.id} {e.sent_at_label()}: {e.description}")

    await update.message.reply_text("\n".join(lines))
