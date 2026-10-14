"""The wait behind ``GET /bot/outbox?wait=N`` (the bot's long-poll).

A waiting request holds no database connection. It registers an
``asyncio.Event``, then queries, and between queries it only awaits that
event. Two things end a wait early:

* **An insert in this process.** ``DatabaseService.enqueue_bot_notification``
  calls ``wake_waiters`` after its commit, which sets every registered event
  (thread-safely: the insert may run in a threadpool thread or in another
  event loop than the waiter's).
* **The re-check.** Every ``RECHECK_SECONDS`` the waiter queries again
  anyway. With more than one uvicorn worker, a row committed by another
  worker sets no event here; the re-check finds it within that interval.

Postgres ``LISTEN/NOTIFY`` would wake across workers too, but it needs a
dedicated, always-open listener connection per worker, a thread to poll it
and reconnect logic when it drops. One indexed query every couple of seconds
for the single waiting request (the bot) is cheaper to get right, and its
worst case (a cross-worker row arrives up to ``RECHECK_SECONDS`` late) is still
faster than the fixed 3 s poll it replaces.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Callable, List, TypeVar

T = TypeVar("T")

RECHECK_SECONDS = float(os.environ.get("DIPLOMACY_OUTBOX_RECHECK_SECONDS", "2"))

_lock = threading.Lock()
_waiters: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()


def wake_waiters() -> None:
    """Wake every waiting long-poll in this process (after an outbox insert)."""
    with _lock:
        waiters = list(_waiters)
    for loop, event in waiters:
        try:
            loop.call_soon_threadsafe(event.set)
        except RuntimeError:  # that loop has closed; its waiter is gone with it
            pass


def waiter_count() -> int:
    """How many long-polls are waiting in this process (for tests)."""
    with _lock:
        return len(_waiters)


async def wait_for_rows(
    fetch: Callable[[], List[T]], wait: float, recheck: float | None = None
) -> List[T]:
    """``fetch()`` until it returns rows or ``wait`` seconds have passed.

    ``fetch`` is a blocking database read; it runs in a thread, and the
    connection it uses is back in the pool before the next await.
    """
    if wait <= 0:
        return await asyncio.to_thread(fetch)
    interval = RECHECK_SECONDS if recheck is None else recheck
    loop = asyncio.get_running_loop()
    deadline = loop.time() + wait
    event = asyncio.Event()
    entry = (loop, event)
    # Registered before the first query, so a row committed between that
    # query and the first await still sets the event.
    with _lock:
        _waiters.add(entry)
    try:
        while True:
            event.clear()
            items = await asyncio.to_thread(fetch)
            remaining = deadline - loop.time()
            if items or remaining <= 0:
                return items
            try:
                await asyncio.wait_for(event.wait(), timeout=min(interval, remaining))
            except TimeoutError:
                pass
    finally:
        with _lock:
            _waiters.discard(entry)
