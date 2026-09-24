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

from engine.map_loader import load_standard_map
from engine.serialization import state_to_dict
from engine.types import Hold, PhaseType, Season, STANDARD_POWERS
from persistence.game_repo import GameRepo
from server.daide import clauses
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


def _payload_tokens(payload: bytes) -> list[Token]:
    """A `DiplomacyMessage.payload` (already stripped of the DCSP header by
    `wire.read_message`) -> its token stream."""
    return [Token.from_bytes(payload[i : i + 2]) for i in range(0, len(payload), 2)]


async def _send_command(writer: asyncio.StreamWriter, *tokens_: Token) -> None:
    await wire.write_message(writer, wire.DiplomacyMessage(payload=b"".join(bytes(tok) for tok in tokens_)))


async def _recv(reader: asyncio.StreamReader) -> wire.DiplomacyMessage:
    msg = await asyncio.wait_for(wire.read_message(reader), timeout=5)
    assert isinstance(msg, wire.DiplomacyMessage)
    return msg


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


# ---------------------------------------------------------------------------
# D5 -- full end-to-end raw-socket round trip, one continuous connection
# ---------------------------------------------------------------------------


class TestEndToEndOneFullTurnOverOneSocket:
    """Track D's D5: proof the whole wire protocol composes correctly end to
    end over one continuous real TCP session, against a real
    `GameService`/Postgres-backed game -- not each layer tested in isolation
    (that's D1-D4's job; see the module docstring and `test_daide_session.py`).

    Deliberately does *not* pre-create the game (`DaideServer(..., game_id=None)`)
    -- the game is minted by this test's own `NME`, exactly as a real DAIDE bot
    connecting to the real listener would trigger it.
    """

    async def test_full_wire_round_trip_and_post_turn_notification(self, service: GameService) -> None:
        server = DaideServer(service, host="127.0.0.1", port=0)
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            try:
                # -- 1. IM -> RM -------------------------------------------------
                await wire.write_message(writer, wire.InitialMessage())
                rm = await asyncio.wait_for(wire.read_message(reader), timeout=5)
                assert isinstance(rm, wire.RepresentationMessage)

                # -- 2. NME (bot) (1.0) -> HLO -----------------------------------
                await _send_command(writer, t.NME, *text_clause("e2e-bot"), *text_clause("1.0"))
                hlo = await _recv(reader)
                hlo_tokens = _payload_tokens(hlo.payload)
                assert hlo_tokens[0] == t.HLO
                assert hlo_tokens[1] == t.OPEN_PAREN
                power = t.engine_power_name(hlo_tokens[2])
                assert power in STANDARD_POWERS  # a real power was assigned, not garbage
                assert hlo_tokens[3] == t.CLOSE_PAREN

                game_id = server.current_game_id
                assert game_id is not None  # NME minted the game lazily, as designed

                # -- 3. MAP -------------------------------------------------------
                await _send_command(writer, t.MAP)
                map_resp = await _recv(reader)
                map_tokens = _payload_tokens(map_resp.payload)
                assert map_tokens[0] == t.MAP
                map_name = "".join(tok.text for tok in map_tokens[2:-1])
                assert map_name == "standard"

                # -- 4. MDF (coarse shape + non-trivial size only, per the task
                #    brief -- full adjacency decoding is D1-D4's tested territory) --
                await _send_command(writer, t.MDF)
                mdf_resp = await _recv(reader)
                mdf_tokens = _payload_tokens(mdf_resp.payload)
                assert mdf_tokens[0] == t.MDF
                assert len(mdf_resp.payload) > 800  # a real map def, not an empty/error frame
                assert len(mdf_tokens) > 400

                # -- 5. SCO ---------------------------------------------------------
                await _send_command(writer, t.SCO)
                sco_resp = await _recv(reader)
                sco_tokens = _payload_tokens(sco_resp.payload)
                assert sco_tokens[0] == t.SCO
                assert sco_tokens[1] == t.OPEN_PAREN  # at least one (power centre ...) group
                assert t.UNO in sco_tokens  # standard start always has unowned/neutral centres

                # -- 6. NOW -- and cross-check this power's starting units against
                #    engine.map_loader's own standard-map data ------------------------
                await _send_command(writer, t.NOW)
                now_resp = await _recv(reader)
                now_tokens = _payload_tokens(now_resp.payload)
                assert now_tokens[0] == t.NOW

                season, phase_type, year = clauses.turn_from_clause(now_tokens[1:5])
                assert (season, phase_type, year) == (Season.SPRING, PhaseType.MOVEMENT, 1901)

                map_data = load_standard_map()
                rest = now_tokens[5:]
                units = []
                i = 0
                while i < len(rest):
                    unit, consumed = clauses.unit_from_clause(rest[i:], map=map_data)
                    units.append(unit)
                    i += consumed
                units_for_power = {u for u in units if u.power == power}
                expected_units = {u for u in map_data.starting_units if u.power == power}
                assert units_for_power == expected_units  # NOW's wire data matches the real starting position
                assert expected_units  # sanity: every standard power has starting units

                view_before = service.view(game_id)
                assert view_before is not None
                prev_phase = view_before["phase"]
                assert prev_phase == "S1901M"

                # -- 7. SUB a real, legal opening order for one of `power`'s own
                #    units -- Hold is legal from every starting position regardless
                #    of which power got assigned, so this doesn't need per-power
                #    adjacency logic. -------------------------------------------------
                one_unit = sorted(expected_units, key=lambda u: u.province)[0]
                hold_order = Hold(power=power, unit=one_unit.location)
                order_clause = clauses.encode_order(hold_order, phase_type=PhaseType.MOVEMENT, map=map_data)
                await _send_command(writer, t.SUB, *order_clause)
                thx = await _recv(reader)
                thx_tokens = _payload_tokens(thx.payload)
                assert thx_tokens[0] == t.THX
                assert thx_tokens[1 : 1 + len(order_clause)] == list(order_clause)  # echoes the submitted order
                assert thx_tokens[-3:] == [t.OPEN_PAREN, t.MBV, t.CLOSE_PAREN]  # (MBV) = accepted, not rejected

                # -- 8. Trigger turn processing the way the HTTP route / deadline
                #    scheduler would: GameService.process_turn directly, then the
                #    same broadcast hook _api_module.py calls. ------------------------
                service.process_turn(game_id)
                await server.notify_game_processed(game_id, resolved_phase=prev_phase)

                # -- 9. Read the resulting notification off the SAME socket -------
                notif_now = await _recv(reader)
                now2_tokens = _payload_tokens(notif_now.payload)
                assert now2_tokens[0] == t.NOW  # notify_game_processed sends NOW first

                new_season, new_phase_type, new_year = clauses.turn_from_clause(now2_tokens[1:5])
                view_after = service.view(game_id)
                assert view_after is not None
                assert view_after["phase"] != prev_phase  # the phase actually advanced
                assert (new_season, new_phase_type, new_year) != (season, phase_type, year)

                notif_ord = await _recv(reader)
                ord_tokens = _payload_tokens(notif_ord.payload)
                assert ord_tokens[0] == t.ORD  # ORD follows NOW, one per adjudicated order

                await wire.write_message(writer, wire.FinalMessage())
            finally:
                writer.close()
        finally:
            await server.stop()
