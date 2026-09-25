"""Error alerts to the maintainer's Telegram, for the API and the bot alike.

``AdminAlertHandler`` is a ``logging.Handler`` at ERROR: every error either
process logs becomes a Telegram DM to ``DIPLOMACY_ADMIN_TELEGRAM_ID``, so a
problem a beta player hits is known before they report it. Unset, nothing is
installed. How the DM is sent is the caller's: the API queues it in
``bot_outbox`` (``api/shared.py``), the bot sends it itself (``app.py``) -- the
bot's errors are the ones that happen when the API is unreachable.

Stdlib only: the bot image holds nothing but ``server.telegram_bot``, and the
API imports this module from there.

Throttled, because one broken code path fails on every request: an error
alerts at most once per ``per_key_seconds`` for its kind (logger name plus
message with digits blanked, so "game 12" and "game 13" are one kind), and
at most ``max_per_hour`` alerts go out in all. The next alert of a kind says
how many were held back.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from typing import Callable, Optional

MAX_ALERT_CHARS = 1500


class AdminAlertHandler(logging.Handler):
    def __init__(
        self,
        send: Callable[[str], None],
        *,
        source: str,
        per_key_seconds: float = 900.0,
        max_per_hour: int = 20,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(level=logging.ERROR)
        self._send = send
        self._source = source
        self._per_key_seconds = per_key_seconds
        self._max_per_hour = max_per_hour
        self._clock = clock
        self._last_sent: dict[str, float] = {}
        self._held_back: dict[str, int] = {}
        self._recent: deque[float] = deque()
        # Sending may itself log (a failed database write, say). An error logged
        # while an alert is being sent must not start another one.
        self._sending = threading.local()

    @staticmethod
    def kind(record: logging.LogRecord) -> str:
        return f"{record.name}:{re.sub(r'[0-9]+', '#', record.getMessage())[:120]}"

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(self._sending, "active", False):
            return
        now = self._clock()
        kind = self.kind(record)
        with self.lock:  # type: ignore[union-attr]  # createLock() ran in __init__
            while self._recent and now - self._recent[0] >= 3600:
                self._recent.popleft()
            last = self._last_sent.get(kind)
            if (last is not None and now - last < self._per_key_seconds) or len(self._recent) >= self._max_per_hour:
                self._held_back[kind] = self._held_back.get(kind, 0) + 1
                return
            self._last_sent[kind] = now
            self._recent.append(now)
            held_back = self._held_back.pop(kind, 0)
        self._sending.active = True
        try:
            self._send(self.format_alert(record, held_back))
        except Exception:  # a logging handler must never raise into the code that logged
            self.handleError(record)
        finally:
            self._sending.active = False

    def format_alert(self, record: logging.LogRecord, held_back: int = 0) -> str:
        lines = [f"⚠️ {self._source} error", f"{record.name}: {record.getMessage()}"]
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            lines.append(f"{type(exc).__name__}: {exc}")
        if held_back:
            lines.append(f"(+{held_back} more like this since the last alert)")
        text = "\n".join(lines)
        return text if len(text) <= MAX_ALERT_CHARS else text[: MAX_ALERT_CHARS - 1] + "…"


def admin_telegram_id(raw: Optional[str]) -> Optional[int]:
    """``DIPLOMACY_ADMIN_TELEGRAM_ID`` as a chat id, or ``None`` when unset or not a number."""
    try:
        return int(raw) if raw and raw.strip() else None
    except ValueError:
        return None
