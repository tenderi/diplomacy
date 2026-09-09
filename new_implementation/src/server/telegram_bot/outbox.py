"""The bot's durable outbox: writes that must reach the server, kept until they do.

The bot runs on a VPS; the API runs on a home server across a WireGuard
tunnel that will, sooner or later, be down when a player presses send. The
rule this module exists to enforce is simple: **a player's orders or message
are never lost because the link was down.** They are written *here* -- a
SQLite file on a Docker volume -- before the first delivery attempt, and stay
until the server has either accepted them or definitively rejected them.
Either way the player is told what happened, with the time they originally
sent it.

Why SQLite and not memory: the bot is restarted on every deploy and on every
VPS reboot. Why SQLite and not Postgres: Postgres is on the far side of the
very link whose absence this module handles.

Each entry carries:

- ``key`` -- a UUID sent as ``Idempotency-Key`` so a retry of a request whose
  response was lost is answered from the server's stored response instead of
  applied twice (``server.api.idempotency``).
- ``created_at`` -- when the player did the thing; sent as ``client_timestamp``
  so a message is stored with its real time and stale orders are refused
  (``server.api.client_timestamp``).
- ``chat_id`` and ``description`` -- so the replayer can tell the player, in
  their own chat, what was delivered or refused, and what it was.

States: ``pending`` (waiting for a delivery attempt), ``inflight`` (an attempt
is running in this process), ``delivered`` (server accepted; ``response``
kept), ``rejected`` (server refused with a 4xx; ``last_error`` kept). Transient
failures return an entry to ``pending`` with an exponential ``next_attempt_at``
capped at ``MAX_BACKOFF_SECONDS``. Delivery is strictly in id order across all
chats -- a message must not overtake the orders sent before it -- so the
replayer stops at the first transient failure and resumes from it later.

A second, unrelated table (``user_games_cache``) remembers each user's last
known games-and-powers list so ``/order`` and friends can still resolve which
power a player holds while the server is unreachable (``game_context``).

The default location is ``$DIPLOMACY_BOT_DATA_DIR/outbox.sqlite3``; the
container mounts a named volume at ``/data``.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("diplomacy.telegram_bot.outbox")

PENDING = "pending"
INFLIGHT = "inflight"
DELIVERED = "delivered"
REJECTED = "rejected"

BASE_BACKOFF_SECONDS = 5
MAX_BACKOFF_SECONDS = 60
# Finished entries are kept this long so /queue can show recent history.
FINISHED_RETENTION = timedelta(days=7)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT NOT NULL UNIQUE,
    chat_id         INTEGER NOT NULL,
    endpoint        TEXT NOT NULL,
    payload         TEXT NOT NULL,
    description     TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    state           TEXT NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT,
    next_attempt_at TEXT,
    finished_at     TEXT,
    response        TEXT
);
CREATE INDEX IF NOT EXISTS ix_outbox_state_id ON outbox(state, id);
CREATE INDEX IF NOT EXISTS ix_outbox_chat_state ON outbox(chat_id, state);
CREATE TABLE IF NOT EXISTS user_games_cache (
    user_id     TEXT PRIMARY KEY,
    games_json  TEXT NOT NULL,
    fetched_at  TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dump_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _load_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class OutboxEntry:
    id: int
    key: str
    chat_id: int
    endpoint: str
    payload: dict[str, Any]
    description: str
    created_at: datetime
    state: str
    attempts: int = 0
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    response: Optional[dict[str, Any]] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "OutboxEntry":
        return cls(
            id=int(row["id"]),
            key=row["key"],
            chat_id=int(row["chat_id"]),
            endpoint=row["endpoint"],
            payload=json.loads(row["payload"]),
            description=row["description"],
            created_at=_load_ts(row["created_at"]) or utcnow(),
            state=row["state"],
            attempts=int(row["attempts"] or 0),
            last_error=row["last_error"],
            next_attempt_at=_load_ts(row["next_attempt_at"]),
            finished_at=_load_ts(row["finished_at"]),
            response=json.loads(row["response"]) if row["response"] else None,
        )

    def sent_at_label(self) -> str:
        """``14:02 UTC`` today, else ``2026-09-08 14:02 UTC``."""
        created = self.created_at.astimezone(timezone.utc)
        if created.date() == utcnow().date():
            return f"{created:%H:%M} UTC"
        return f"{created:%Y-%m-%d %H:%M} UTC"


def backoff_seconds(attempts: int) -> int:
    """5, 10, 20, 40, 60, 60, ... -- quick to recover, never a busy loop."""
    return min(MAX_BACKOFF_SECONDS, BASE_BACKOFF_SECONDS * (2 ** max(0, attempts - 1)))


class Outbox:
    """A SQLite-backed queue. Safe to share across threads in one process."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        # WAL: a crash mid-write leaves a consistent file, and readers never
        # block the writer. synchronous=FULL: a committed row survives a power cut.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
        self.reset_inflight()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- writes -------------------------------------------------------------

    def enqueue(
        self, chat_id: int, endpoint: str, payload: dict[str, Any], description: str
    ) -> OutboxEntry:
        """Durably record a write *before* anything is sent."""
        now = utcnow()
        key = str(uuid.uuid4())
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO outbox (key, chat_id, endpoint, payload, description, created_at, state)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, int(chat_id), endpoint, json.dumps(payload), description, _dump_ts(now), PENDING),
            )
            entry = self.get(int(cur.lastrowid))
        assert entry is not None
        logger.info("Outbox #%d queued: %s -> %s", entry.id, description, endpoint)
        return entry

    def mark_inflight(self, entry_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE outbox SET state = ?, attempts = attempts + 1 WHERE id = ?",
                (INFLIGHT, entry_id),
            )

    def mark_delivered(self, entry_id: int, response: Any) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE outbox SET state = ?, finished_at = ?, response = ?, last_error = NULL"
                " WHERE id = ?",
                (DELIVERED, _dump_ts(utcnow()), json.dumps(response), entry_id),
            )

    def mark_rejected(self, entry_id: int, error: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE outbox SET state = ?, finished_at = ?, last_error = ? WHERE id = ?",
                (REJECTED, _dump_ts(utcnow()), error[:2000], entry_id),
            )

    def mark_retry(self, entry_id: int, error: str, *, now: Optional[datetime] = None) -> datetime:
        """Back to ``pending`` with a backoff; returns the next attempt time."""
        now = now or utcnow()
        with self._lock:
            row = self._conn.execute("SELECT attempts FROM outbox WHERE id = ?", (entry_id,)).fetchone()
            attempts = int(row["attempts"]) if row else 1
            next_at = now + timedelta(seconds=backoff_seconds(attempts))
            self._conn.execute(
                "UPDATE outbox SET state = ?, last_error = ?, next_attempt_at = ? WHERE id = ?",
                (PENDING, error[:2000], _dump_ts(next_at), entry_id),
            )
        return next_at

    def reset_inflight(self) -> int:
        """On startup: anything left ``inflight`` by a crash goes back to ``pending``.

        Safe because the server answers a repeated ``Idempotency-Key`` from its
        stored response, so an attempt that actually completed before the crash
        is not applied a second time.
        """
        with self._lock:
            cur = self._conn.execute(
                "UPDATE outbox SET state = ?, next_attempt_at = NULL WHERE state = ?",
                (PENDING, INFLIGHT),
            )
            n = cur.rowcount
        if n:
            logger.warning("Outbox: %d in-flight entr%s reset to pending after restart", n, "y" if n == 1 else "ies")
        return n

    def purge_finished(self, older_than: timedelta = FINISHED_RETENTION) -> int:
        cutoff = _dump_ts(utcnow() - older_than)
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM outbox WHERE state IN (?, ?) AND finished_at < ?",
                (DELIVERED, REJECTED, cutoff),
            )
            return cur.rowcount

    # -- reads --------------------------------------------------------------

    def get(self, entry_id: int) -> Optional[OutboxEntry]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM outbox WHERE id = ?", (entry_id,)).fetchone()
        return OutboxEntry.from_row(row) if row else None

    def due(self, now: Optional[datetime] = None, limit: int = 100) -> list[OutboxEntry]:
        """Pending entries whose backoff has elapsed, oldest first."""
        now = now or utcnow()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM outbox WHERE state = ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?)"
                " ORDER BY id LIMIT ?",
                (PENDING, _dump_ts(now), limit),
            ).fetchall()
        return [OutboxEntry.from_row(r) for r in rows]

    def pending(self, chat_id: Optional[int] = None) -> list[OutboxEntry]:
        """Everything not yet finished (pending or in flight), oldest first."""
        with self._lock:
            if chat_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM outbox WHERE state IN (?, ?) ORDER BY id", (PENDING, INFLIGHT)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM outbox WHERE state IN (?, ?) AND chat_id = ? ORDER BY id",
                    (PENDING, INFLIGHT, int(chat_id)),
                ).fetchall()
        return [OutboxEntry.from_row(r) for r in rows]

    def recent(self, chat_id: int, limit: int = 5) -> list[OutboxEntry]:
        """The most recently finished entries for a chat, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM outbox WHERE state IN (?, ?) AND chat_id = ? ORDER BY id DESC LIMIT ?",
                (DELIVERED, REJECTED, int(chat_id), limit),
            ).fetchall()
        return [OutboxEntry.from_row(r) for r in rows]

    def count_pending(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM outbox WHERE state IN (?, ?)", (PENDING, INFLIGHT)
            ).fetchone()
        return int(row["n"])

    # -- user games cache ---------------------------------------------------

    def cache_user_games(self, user_id: str, games: list[dict[str, Any]]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO user_games_cache (user_id, games_json, fetched_at) VALUES (?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET games_json = excluded.games_json,"
                " fetched_at = excluded.fetched_at",
                (str(user_id), json.dumps(games), _dump_ts(utcnow())),
            )

    def cached_user_games(self, user_id: str) -> Optional[tuple[list[dict[str, Any]], datetime]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT games_json, fetched_at FROM user_games_cache WHERE user_id = ?", (str(user_id),)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["games_json"]), (_load_ts(row["fetched_at"]) or utcnow())


# -- process-wide instance ----------------------------------------------------

_outbox: Optional[Outbox] = None
_outbox_lock = threading.Lock()


def outbox_path() -> Path:
    data_dir = os.environ.get("DIPLOMACY_BOT_DATA_DIR", "bot_data")
    return Path(data_dir) / "outbox.sqlite3"


def get_outbox() -> Outbox:
    """The process-wide outbox, opened on first use at ``outbox_path()``."""
    global _outbox
    with _outbox_lock:
        if _outbox is None:
            _outbox = Outbox(outbox_path())
        return _outbox


def reset_outbox_for_tests(path: Optional[str | os.PathLike[str]] = None) -> Outbox:
    """Close the current instance and open a fresh one (at ``path`` if given)."""
    global _outbox
    with _outbox_lock:
        if _outbox is not None:
            _outbox.close()
        _outbox = Outbox(path) if path is not None else Outbox(outbox_path())
        return _outbox
