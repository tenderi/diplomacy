"""``client_timestamp``: when a player actually did the thing they are asking for.

The Telegram bot runs on a VPS and reaches this API over a tunnel to a home
server. When the tunnel is down the bot does not drop a player's orders or
messages; it queues them and delivers later. What arrives here may therefore be
minutes or hours old, and two things must survive that delay:

1. A message should be stored with the time it was *written*, so the recipient
   and the game log see "sent 14:02", not "sent 16:37 when the link came back".
2. Orders composed for a phase that has since been adjudicated must not be
   applied to the next phase's board (``routes/orders.py`` refuses them, using
   ``games.phase_started_at``).

Both hinge on trusting the timestamp within reason. It is clamped rather than
rejected outright: a clock a few minutes fast is common and harmless, a value
far in the future is a bug (or mischief) and is pulled back to *now*; a value
older than ``MAX_AGE`` is refused, because nothing legitimate is queued for a
month and a plausible-looking ancient timestamp would put a message in the
wrong place in a game's history.

All values are normalised to **naive UTC**, the convention for every datetime
column in this schema (``persistence.database.utcnow_naive``).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from persistence.database import utcnow_naive

# A composed-at time this far *ahead* of the server clock is clamped to now.
FUTURE_TOLERANCE = timedelta(minutes=5)
# A composed-at time older than this is refused (HTTP 400).
MAX_AGE = timedelta(days=30)
# Delays shorter than this are not worth mentioning to the recipient.
LATE_THRESHOLD = timedelta(seconds=90)


def normalize_client_timestamp(value: Optional[datetime]) -> datetime:
    """Return ``value`` as naive UTC, clamped/validated; ``now`` when absent."""
    now = utcnow_naive()
    if value is None:
        return now
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    if value > now + FUTURE_TOLERANCE:
        return now
    if value < now - MAX_AGE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"client_timestamp {value.isoformat()} is more than {MAX_AGE.days} days old; "
                "refusing to backdate this far."
            ),
        )
    return value


def sent_at_suffix(sent_at: datetime, now: Optional[datetime] = None) -> str:
    """``" (sent 14:02 UTC)"`` when ``sent_at`` is noticeably earlier than now, else ``""``.

    Appended to the notification text for messages that were delayed on the
    way in, so the recipient knows the sender wrote it earlier than it looks.
    """
    now = now or utcnow_naive()
    if now - sent_at < LATE_THRESHOLD:
        return ""
    if sent_at.date() == now.date():
        return f" (sent {sent_at:%H:%M} UTC)"
    return f" (sent {sent_at:%Y-%m-%d %H:%M} UTC)"
