"""Tests for the DAIDE TCP listener (Track D, D4).

Two things this file proves that `test_daide_session.py` can't (it dispatches
directly against `DaideSession`, no socket, no listener):

1. A real `asyncio` TCP client can complete the IM -> RM -> NME -> HLO
   handshake against a running `DaideServer` -- proof the listener actually
   accepts connections end to end. Not the full multi-turn scenario (that's
   D5's byte-level e2e test); just proof the socket path works.
2. `DaideServer.notify_game_processed` broadcasts `NOW`/`ORD` to every
   session on a game, not just whichever session triggered the turn.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace

import pytest
from sqlalchemy.orm import sessionmaker

from engine.serialization import state_to_dict
from persistence.game_repo import GameRepo
from server.daide import tokens as t
from server.daide import wire
from server.daide.server import DaideServer
from server.daide.session import DaideSession, text_clause
from server.daide.tokens import Token
from server.game_service import GameService

pytestmark = pytest.mark.database


@pytest.fixture
def service(temp_db) -> GameService:
    session_factory = sessionmaker(bind=temp_db)
    return GameService(GameRepo(session_factory))


def _new_game(service: GameService) -> str:
    gid = f"daide-srv-{uuid.uuid4().hex[:8]}"
    service.create_game(gid)
    return gid


def _decode_frame(frame: bytes) -> list[Token]:
    payload = frame[4:]
    return [Token.from_bytes(payload[i : i + 2]) for i in range(0, len(payload), 2)]


class FakeWriter:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Real raw-socket smoke test
# ---------------------------------------------------------------------------


class TestRealSocketHandshake:
    async def test_im_rm_nme_hlo_over_a_real_tcp_connection(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, host="127.0.0.1", port=0, game_id=gid)
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            try:
                await wire.write_message(writer, wire.InitialMessage())
                rm = await wire.read_message(reader)
                assert isinstance(rm, wire.RepresentationMessage)

                nme_payload = b"".join(
                    bytes(tok) for tok in (t.NME, *text_clause("DumbBot"), *text_clause("1.0"))
                )
                await wire.write_message(writer, wire.DiplomacyMessage(payload=nme_payload))

                hlo = await wire.read_message(reader)
                assert isinstance(hlo, wire.DiplomacyMessage)
                tokens_ = [
                    Token.from_bytes(hlo.payload[i : i + 2]) for i in range(0, len(hlo.payload), 2)
                ]
                assert tokens_[0] == t.HLO
                assert t.AUS in tokens_

                await wire.write_message(writer, wire.FinalMessage())
            finally:
                writer.close()
        finally:
            await server.stop()

    async def test_start_binds_an_ephemeral_port_and_creates_no_game(self) -> None:
        """`start()` must not touch `game_service`/the database at all -- see
        its docstring. This repo auto-deploys to production on every merge to
        `main` (`systemctl restart diplomacy-api`, per `CLAUDE.md`); if
        `start()` created a game whenever no ``game_id`` was supplied, every
        single deploy would mint a permanent orphan row, whether or not a
        DAIDE client ever connects."""
        session_factory = sessionmaker(bind=_bare_sqlite_engine())
        gs = GameService(GameRepo(session_factory))
        server = DaideServer(gs, host="127.0.0.1", port=0)
        await server.start()
        try:
            assert server.port != 0
            assert server.current_game_id is None
            with pytest.raises(RuntimeError):
                _ = server.game_id
        finally:
            await server.stop()

    async def test_first_successful_nme_creates_the_game_lazily(self) -> None:
        """A game is only ever created once a real client identifies itself
        (`NME`) -- not by `start()`, and not merely by accepting a TCP
        connection that never sends anything."""
        session_factory = sessionmaker(bind=_bare_sqlite_engine())
        gs = GameService(GameRepo(session_factory))
        server = DaideServer(gs, host="127.0.0.1", port=0)
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            try:
                await wire.write_message(writer, wire.InitialMessage())
                await wire.read_message(reader)  # RepresentationMessage
                assert server.current_game_id is None  # handshake alone creates nothing

                nme_payload = b"".join(
                    bytes(tok) for tok in (t.NME, *text_clause("DumbBot"), *text_clause("1.0"))
                )
                await wire.write_message(writer, wire.DiplomacyMessage(payload=nme_payload))
                hlo = await wire.read_message(reader)
                assert isinstance(hlo, wire.DiplomacyMessage)

                assert server.current_game_id is not None
                assert gs.exists(server.current_game_id)
            finally:
                writer.close()
        finally:
            await server.stop()


def _bare_sqlite_engine():
    # A throwaway in-memory schema so this one test doesn't need the Postgres
    # test database just to prove "start() creates a game when none is given".
    from sqlalchemy import create_engine

    from persistence.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Cross-session broadcast
# ---------------------------------------------------------------------------


class TestNotifyGameProcessed:
    async def test_now_and_ord_reach_every_session_on_the_game(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)

        w_aus, w_eng = FakeWriter(), FakeWriter()
        s_aus = DaideSession(None, w_aus, server)
        s_aus.power = "AUSTRIA"
        server.register(gid, "AUSTRIA", s_aus)
        s_eng = DaideSession(None, w_eng, server)
        s_eng.power = "ENGLAND"
        server.register(gid, "ENGLAND", s_eng)

        prev_view = service.view(gid)
        assert prev_view is not None
        prev_phase = prev_view["phase"]

        service.submit_orders(gid, "AUSTRIA", ["A BUD H"])
        service.process_turn(gid)

        await server.notify_game_processed(gid, resolved_phase=prev_phase)

        for writer in (w_aus, w_eng):
            frames = [_decode_frame(f) for f in writer.sent]
            assert any(f[0] == t.NOW for f in frames)
            assert any(f[0] == t.ORD for f in frames)

    async def test_out_is_sent_for_a_newly_eliminated_power(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w_aus = FakeWriter()
        s_aus = DaideSession(None, w_aus, server)
        s_aus.power = "AUSTRIA"
        server.register(gid, "AUSTRIA", s_aus)

        # Force a real elimination directly: strip TURKEY's units and hand
        # its home centers to AUSTRIA (GameService.concede deliberately leaves
        # ownership untouched, so it alone can't produce an elimination here
        # -- Game.eliminated_powers() requires *both* no units and no
        # centers). What this test actually exercises is that
        # notify_game_processed's eliminated-powers diff fires OUT once
        # Game.eliminated_powers() changes, and doesn't repeat it.
        game = service.load(gid)
        state = game.state
        new_units = frozenset(u for u in state.units if u.power != "TURKEY")
        new_ownership = {p: ("AUSTRIA" if o == "TURKEY" else o) for p, o in state.ownership.items()}
        new_state = replace(state, units=new_units, ownership=new_ownership)
        service.restore_snapshot(gid, state_to_dict(new_state), phase_code=new_state.phase_name)

        await server.notify_game_processed(gid)
        turkey_out = any(
            _decode_frame(f) == [t.OUT, t.OPEN_PAREN, t.TUR, t.CLOSE_PAREN] for f in w_aus.sent
        )
        assert turkey_out

        w_aus.sent.clear()
        await server.notify_game_processed(gid)
        # Already reported once -- no duplicate OUT on a second call with no
        # newly-eliminated power.
        assert not any(_decode_frame(f)[0] == t.OUT for f in w_aus.sent)

    async def test_no_sessions_on_the_game_is_a_no_op(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        # No exception, nothing to assert beyond "doesn't crash".
        await server.notify_game_processed(gid)
