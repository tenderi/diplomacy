"""The DAIDE TCP listener (Track D, D4) -- replaces `server.daide_protocol`.

`DaideServer` is an `asyncio.start_server`-based listener, one instance per
game: it owns the game a session's `NME`/`IAM` resolves against, the registry
of which power a live `DaideSession` occupies, the reusable per-power
passcodes (so `IAM` can reclaim a slot after a dropped connection), and the
cross-session broadcasts (`notify_game_processed`, draw completion, admin
chat, press relay).

Everything here runs on one asyncio event loop (the process's own), so the
registry dicts below need no locking beyond "don't `await` in the middle of a
mutation" -- which none of the mutating methods do.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timezone
from typing import Any, Optional

from engine.serialization import resolution_from_dict
from engine.types import STANDARD_POWERS
from server.daide import clauses
from server.daide import session as session_mod
from server.daide import tokens as t
from server.daide.session import DaideSession
from server.daide.tokens import Token

__all__ = ["DaideServer"]

_logger = logging.getLogger("diplomacy.server.daide")

DEFAULT_PORT = 8432


class DaideServer:
    """Owns the listening socket, the game it serves, and the connection registry.

    ``game_service`` is the sole entry point into the engine (per
    `CLAUDE.md`'s "non-engine code goes through GameService" rule).
    ``db_service`` is optional and used *only* by `deadline_seconds` to mirror
    the existing ``GET /games/{id}/deadline`` route's read path -- no new
    persistence accessor is added for this.
    """

    def __init__(
        self,
        game_service: Any,
        db_service: Optional[Any] = None,
        host: str = "0.0.0.0",
        port: int = DEFAULT_PORT,
        game_id: Optional[str] = None,
    ) -> None:
        self.game_service = game_service
        self.map = game_service.map
        self.db_service = db_service
        self.host = host
        self.port = port
        self._game_id = game_id
        self._server: Optional[asyncio.base_events.Server] = None

        # game_id -> power -> live session
        self._sessions: dict[str, dict[str, DaideSession]] = {}
        # game_id -> power -> passcode (kept across disconnects for IAM reclaim)
        self._passcodes: dict[str, dict[str, int]] = {}
        # game_id -> powers already reported eliminated (diffed each notify)
        self._eliminated_seen: dict[str, frozenset[str]] = {}
        # game_id -> has a completion (DRW or SLO) already been broadcast
        self._completion_notified: dict[str, bool] = {}

    @property
    def game_id(self) -> str:
        """The game this server serves. Raises if none has been created yet --
        use `current_game_id` for a non-raising check, or `ensure_game_id()`
        to create one on demand."""
        if self._game_id is None:
            raise RuntimeError(
                "no game has been created yet -- DaideServer defers game "
                "creation to the first successful NME (ensure_game_id()), "
                "not to start() or accepting a connection; see start()'s "
                "docstring for why"
            )
        return self._game_id

    @property
    def current_game_id(self) -> Optional[str]:
        """Non-raising peek at `game_id` -- `None` until `ensure_game_id()`
        has actually run (or a game_id was supplied at construction)."""
        return self._game_id

    def ensure_game_id(self) -> str:
        """Create this server's game on first real use, if it doesn't exist
        yet. Idempotent -- a second call returns the same id, no second game.

        Called from `session.py`'s `NME` handler, deliberately not from
        `start()` or `_handle_client()` -- see `start()`'s docstring for why
        eager creation there is actively harmful for this repo."""
        if self._game_id is None:
            self._game_id = self.game_service.create_game()
        return self._game_id

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Bind the listening socket. Does **not** touch `game_service` or the
        database.

        Game creation is deliberately deferred to the first successful `NME`
        (`ensure_game_id()`), not done here, because `CLAUDE.md` documents
        that this repo auto-deploys to production on every merge to `main`
        that passes CI (`systemctl restart diplomacy-api`) -- if `start()`
        created a game whenever ``game_id`` wasn't supplied (as it used to),
        every single deploy would mint one permanent orphan game row, whether
        or not a DAIDE client ever connects, and whether or not the socket
        even binds. Creating on first `NME` instead means a listener that
        nobody ever talks to costs nothing.

        ``asyncio.start_server`` wraps a coroutine ``client_connected_cb`` in
        its own `asyncio.Task` per connection automatically -- no extra
        bookkeeping needed here for "one task per session".
        """
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        if self._server.sockets:
            self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Notify every open session (`OFF`) before closing the listener."""
        for sessions in list(self._sessions.values()):
            for daide_session in list(sessions.values()):
                await daide_session.send_off()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        # No game-creation guard here either (see `start()`'s docstring) --
        # a connection that never sends a successful `NME` never mints a
        # game; `DaideSession` tolerates `current_game_id` being `None` until
        # then.
        daide_session = DaideSession(reader, writer, self)
        await daide_session.run()

    # -- registry ---------------------------------------------------------

    def assign_power(self, game_id: str) -> Optional[str]:
        """The next unclaimed standard power (canonical `STANDARD_POWERS` order),
        or ``None`` if all seven are already occupied by a live session."""
        claimed = set(self._sessions.get(game_id, {}))
        for power in STANDARD_POWERS:
            if power not in claimed:
                return power
        return None

    def register(self, game_id: str, power: str, daide_session: DaideSession) -> int:
        """Claim ``power`` for ``daide_session``; returns its passcode (reused
        across a reconnect if one was already issued for this power)."""
        self._sessions.setdefault(game_id, {})[power] = daide_session
        passcodes = self._passcodes.setdefault(game_id, {})
        passcode = passcodes.get(power)
        if passcode is None:
            passcode = random.randint(1, 8191)
            passcodes[power] = passcode
        return passcode

    def try_reclaim(self, game_id: str, power: str, passcode: int, daide_session: DaideSession) -> bool:
        """`IAM (power) (passcode)` on a new connection: reclaim ``power``'s
        slot if the passcode matches what `register` issued and no other live
        session currently holds it."""
        passcodes = self._passcodes.get(game_id, {})
        if passcodes.get(power) != passcode:
            return False
        sessions = self._sessions.setdefault(game_id, {})
        if power in sessions:
            return False  # slot is live under another connection right now
        sessions[power] = daide_session
        return True

    def unregister(self, game_id: Optional[str], power: Optional[str], daide_session: DaideSession) -> None:
        if game_id is None or power is None:
            return
        sessions = self._sessions.get(game_id)
        if sessions and sessions.get(power) is daide_session:
            del sessions[power]

    def sessions_for(self, game_id: str) -> dict[str, DaideSession]:
        return dict(self._sessions.get(game_id, {}))

    def deadline_seconds(self, game_id: str) -> Optional[int]:
        """Seconds remaining until this game's stored deadline, or ``None`` if
        no deadline is set / no `db_service` was supplied. Mirrors the read
        path `GET /games/{id}/deadline` already uses -- no new accessor."""
        if self.db_service is None:
            return None
        row = self.db_service.get_game_by_game_id(game_id)
        deadline = getattr(row, "deadline", None) if row is not None else None
        if deadline is None:
            return None
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(remaining))

    # -- broadcasts -----------------------------------------------------------

    async def broadcast_draw_completion(self, game_id: str) -> None:
        """A `DRW` vote reached quorum: every session on this game gets the
        bare `DRW` completion notification (never `SLO` -- a real solo is only
        ever detected via `notify_game_processed`, see that method's docstring)."""
        self._completion_notified[game_id] = True
        for daide_session in self.sessions_for(game_id).values():
            with contextlib.suppress(ConnectionError, OSError):
                await daide_session._send(t.DRW)

    async def broadcast_admin(
        self, game_id: str, from_name: str, message_tokens: list[Token], exclude: Optional[DaideSession] = None
    ) -> None:
        """Relay an `ADM (name) (message)` to every other session on the game
        (echo, no persistence -- there is no admin-chat table in this codebase)."""
        name_clause = session_mod.text_clause(from_name)
        for daide_session in self.sessions_for(game_id).values():
            if daide_session is exclude:
                continue
            with contextlib.suppress(ConnectionError, OSError):
                await daide_session._send(t.ADM, *name_clause, t.OPEN_PAREN, *message_tokens, t.CLOSE_PAREN)

    async def relay_press(
        self, game_id: str, from_power: str, to_powers: list[str], message_tokens: list[Token]
    ) -> None:
        """Wrap a syntax-checked, opaque press payload in `FRM` and deliver it
        to each recipient's live session. A recipient with no session simply
        doesn't get it -- no offline mailbox (Track D Ground Rules)."""
        from_token = t.POWER_TOKEN_BY_ENGINE_NAME[from_power]
        to_tokens = [t.POWER_TOKEN_BY_ENGINE_NAME[p] for p in to_powers]
        sessions = self.sessions_for(game_id)
        for power in to_powers:
            daide_session = sessions.get(power)
            if daide_session is None:
                continue
            with contextlib.suppress(ConnectionError, OSError):
                await daide_session._send(
                    t.FRM,
                    t.OPEN_PAREN,
                    from_token,
                    t.CLOSE_PAREN,
                    t.OPEN_PAREN,
                    *to_tokens,
                    t.CLOSE_PAREN,
                    t.OPEN_PAREN,
                    *message_tokens,
                    t.CLOSE_PAREN,
                )

    async def notify_game_processed(self, game_id: str, *, resolved_phase: Optional[str] = None) -> None:
        """Push post-turn notifications to every session on ``game_id``.

        Always sends `NOW`. Sends `ORD` (one message per adjudicated order)
        only when ``resolved_phase`` (the phase code -- e.g. ``"S1901M"`` --
        that was *just* adjudicated, captured by the caller before it called
        `GameService.process_turn`) is supplied: `game.state` has already
        advanced past that phase by the time this runs, so without it there is
        no reliable way to know which season/year/phase-type to tag the `ORD`
        turn clause with, and this deliberately doesn't guess. Sends `OUT` for
        any power `Game.eliminated_powers()` newly reports. Sends `SLO` if the
        game just completed via a solo (`Game.winner()` returns a single
        power) and a `DRW` completion wasn't already broadcast for it --
        `Game.draw()` is only ever reached through `submit_draw_vote`, which
        calls `broadcast_draw_completion` itself and marks
        ``_completion_notified`` immediately, so a `COMPLETED` status reaching
        this method un-notified is always a solo, never a multi-power draw.
        """
        sessions = self.sessions_for(game_id)
        if not sessions:
            return
        game = self.game_service.load(game_id)
        if game is None:
            return

        now_tokens = session_mod.build_now_tokens(game.state, self.map)

        ord_messages: list[list[Token]] = []
        if resolved_phase is not None:
            resolution_dict = self.game_service.last_resolution(game_id)
            if resolution_dict:
                resolution = resolution_from_dict(resolution_dict)
                try:
                    season, phase_type, year = session_mod.parse_phase_code(resolved_phase)
                except ValueError:
                    season = phase_type = year = None  # type: ignore[assignment]
                if phase_type is not None:
                    turn_tokens = list(clauses.turn_clause(season, phase_type, year))
                    for r in resolution.results:
                        ord_messages.append(
                            session_mod.build_ord_tokens(
                                r.order, r.result, r.dislodged, phase_type, self.map, turn_tokens
                            )
                        )

        eliminated_now = game.eliminated_powers()
        eliminated_before = self._eliminated_seen.get(game_id, frozenset())
        newly_eliminated = sorted(eliminated_now - eliminated_before)
        self._eliminated_seen[game_id] = eliminated_now

        completed = game.state.status.value == "COMPLETED"
        already_notified = self._completion_notified.get(game_id, False)
        winner = game.winner() if completed and not already_notified else None

        for daide_session in sessions.values():
            with contextlib.suppress(ConnectionError, OSError):
                await daide_session._send(*now_tokens)
                for msg in ord_messages:
                    await daide_session._send(*msg)
                for power in newly_eliminated:
                    await daide_session._send(t.OUT, t.OPEN_PAREN, t.POWER_TOKEN_BY_ENGINE_NAME[power], t.CLOSE_PAREN)
                if winner is not None:
                    await daide_session._send(t.SLO, t.OPEN_PAREN, t.POWER_TOKEN_BY_ENGINE_NAME[winner], t.CLOSE_PAREN)
        if completed:
            self._completion_notified[game_id] = True
