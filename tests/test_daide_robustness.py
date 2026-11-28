"""No client input can raise out of a DAIDE session or into another one (CO1).

Every case runs over a real local TCP connection to a running `DaideServer`:
the DCSP ErrorMessage a framing violation earns, the IM and mid-frame
timeouts, one power per connection, and a dead peer in a fan-out.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from collections.abc import AsyncIterator
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from persistence.database import Base
from engine.types import STANDARD_POWERS
from persistence.game_repo import GameRepo
from server.daide import server as server_mod
from server.daide import session as session_mod
from server.daide import tokens as t
from server.daide import wire
from server.daide.server import DaideServer
from server.daide.session import DaideSession, text_clause
from server.daide.tokens import Token
from server.game_service import GameService

ErrorCode = wire.ErrorCode


@pytest.fixture
async def server() -> AsyncIterator[DaideServer]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    srv = DaideServer(GameService(GameRepo(sessionmaker(bind=engine))), host="127.0.0.1", port=0)
    await srv.start()
    try:
        yield srv
    finally:
        await srv.stop()


Conn = tuple[asyncio.StreamReader, asyncio.StreamWriter]


async def _connect(server: DaideServer, handshake: bool = True) -> Conn:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    if handshake:
        await wire.write_message(writer, wire.InitialMessage())
        assert isinstance(await _read(reader), wire.RepresentationMessage)
    return reader, writer


async def _read(reader: asyncio.StreamReader) -> wire.Message:
    return await asyncio.wait_for(wire.read_message(reader), timeout=5)


async def _send(writer: asyncio.StreamWriter, *tokens_: Token) -> None:
    await wire.write_message(writer, wire.DiplomacyMessage(payload=b"".join(bytes(tok) for tok in tokens_)))


async def _recv_tokens(reader: asyncio.StreamReader) -> list[Token]:
    msg = await _read(reader)
    assert isinstance(msg, wire.DiplomacyMessage)
    return [Token.from_bytes(msg.payload[i : i + 2]) for i in range(0, len(msg.payload), 2)]


async def _assert_closed_after_error(reader: asyncio.StreamReader, code: ErrorCode) -> None:
    msg = await _read(reader)
    assert msg == wire.ErrorMessage(code)
    assert await asyncio.wait_for(reader.read(), timeout=5) == b""  # then a clean EOF


async def _nme(conn: Conn, name: str = "Bot") -> list[Token]:
    """The standard handshake: NME, then YES (MAP ...) once MAP arrives.
    Returns HLO, or the first reply to NME when it is not YES."""
    await _send(conn[1], t.NME, *text_clause(name), *text_clause("1.0"))
    reply = await _recv_tokens(conn[0])
    if reply[0] != t.YES:
        return reply
    map_msg = await _recv_tokens(conn[0])
    assert map_msg[0] == t.MAP
    await _send(conn[1], t.YES, t.OPEN_PAREN, *map_msg, t.CLOSE_PAREN)
    hlo = await _recv_tokens(conn[0])
    assert [(await _recv_tokens(conn[0]))[0], (await _recv_tokens(conn[0]))[0]] == [t.SCO, t.NOW]
    return hlo


def _no_tracebacks(caplog: pytest.LogCaptureFixture) -> None:
    assert [r.getMessage() for r in caplog.records if r.exc_info] == []


# ---------------------------------------------------------------------------
# (a) / (d) framing violations: the right DCSP ErrorMessage, then a clean close
# ---------------------------------------------------------------------------


class TestFramingViolations:
    async def test_unknown_token_in_a_dm_gets_invalid_token(
        self, server: DaideServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        reader, writer = await _connect(server)
        writer.write(bytes((wire.MessageType.DIPLOMACY, 0, 0, 2, 0xFF, 0xFF)))
        await _assert_closed_after_error(reader, ErrorCode.INVALID_TOKEN_IN_DM)
        writer.close()
        assert any("INVALID_TOKEN_IN_DM" in r.getMessage() and "0xFFFF" in r.getMessage() for r in caplog.records)
        _no_tracebacks(caplog)

    async def test_unknown_frame_type_gets_unknown_message_type(
        self, server: DaideServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        reader, writer = await _connect(server)
        writer.write(bytes((9, 0, 0, 0)))
        await _assert_closed_after_error(reader, ErrorCode.UNKNOWN_MESSAGE_TYPE)
        writer.close()
        _no_tracebacks(caplog)

    async def test_client_error_message_with_unknown_code_closes_without_reply(
        self, server: DaideServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING)
        reader, writer = await _connect(server)
        writer.write(bytes((wire.MessageType.ERROR, 0, 0, 2, 0, 0x63)))
        assert await asyncio.wait_for(reader.read(), timeout=5) == b""
        writer.close()
        assert any("0x63" in r.getMessage() for r in caplog.records)
        _no_tracebacks(caplog)

    async def test_a_dm_before_the_im_gets_im_not_first(self, server: DaideServer) -> None:
        reader, writer = await _connect(server, handshake=False)
        await _send(writer, t.MAP)
        await _assert_closed_after_error(reader, ErrorCode.IM_NOT_FIRST_MESSAGE)
        writer.close()

    async def test_a_second_im_gets_multiple_im_sent(self, server: DaideServer) -> None:
        reader, writer = await _connect(server)
        await wire.write_message(writer, wire.InitialMessage())
        await _assert_closed_after_error(reader, ErrorCode.MULTIPLE_IM_SENT)
        writer.close()

    async def test_an_rm_from_the_client_gets_rm_sent_by_client(self, server: DaideServer) -> None:
        reader, writer = await _connect(server)
        await wire.write_message(writer, wire.RepresentationMessage())
        await _assert_closed_after_error(reader, ErrorCode.RM_SENT_BY_CLIENT)
        writer.close()

    async def test_a_failed_session_releases_its_power(self, server: DaideServer) -> None:
        conn = await _connect(server)
        assert (await _nme(conn))[0] == t.HLO
        conn[1].write(bytes((9, 0, 0, 0)))
        await _assert_closed_after_error(conn[0], ErrorCode.UNKNOWN_MESSAGE_TYPE)
        conn[1].close()
        assert server.sessions_for(server.game_id) == {}


# ---------------------------------------------------------------------------
# (c) timeouts
# ---------------------------------------------------------------------------


class TestTimeouts:
    async def test_no_im_within_the_timer_closes_the_connection(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "IM_TIMEOUT_SECONDS", 0.2)
        reader, writer = await _connect(server, handshake=False)
        await _assert_closed_after_error(reader, ErrorCode.IM_TIMER_EXPIRED)
        writer.close()

    async def test_a_frame_stalled_after_its_first_bytes_closes_the_connection(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "FRAME_TIMEOUT_SECONDS", 0.2)
        reader, writer = await _connect(server)
        writer.write(bytes((wire.MessageType.DIPLOMACY, 0)))  # half a header, then nothing
        await _assert_closed_after_error(reader, ErrorCode.MESSAGE_SHORTER_THAN_DECLARED)
        writer.close()

    async def test_an_idle_connection_between_frames_stays_open(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "FRAME_TIMEOUT_SECONDS", 0.1)
        monkeypatch.setattr(session_mod, "IM_TIMEOUT_SECONDS", 0.1)
        conn = await _connect(server)
        await asyncio.sleep(0.3)
        assert (await _nme(conn))[0] == t.HLO
        conn[1].close()


class TestShutdown:
    async def test_stop_closes_a_connection_the_peer_never_hangs_up(self, server: DaideServer) -> None:
        reader, writer = await _connect(server)  # no NME: no session registered, no OFF
        try:
            await asyncio.wait_for(server.stop(), timeout=5)
            assert await asyncio.wait_for(reader.read(), timeout=5) == b""
        finally:
            writer.close()  # so a failing run ends instead of hanging the fixture's stop()


# ---------------------------------------------------------------------------
# (b) one power per connection
# ---------------------------------------------------------------------------


class TestOnePowerPerConnection:
    async def test_a_second_nme_is_rejected(self, server: DaideServer) -> None:
        conn = await _connect(server)
        assert (await _nme(conn))[0] == t.HLO
        reply = await _nme(conn, "Again")
        assert reply[0] == t.REJ
        assert list(server.sessions_for(server.game_id)) == ["AUSTRIA"]
        await wire.write_message(conn[1], wire.FinalMessage())
        assert await asyncio.wait_for(conn[0].read(), timeout=5) == b""
        conn[1].close()
        assert server.sessions_for(server.game_id) == {}

    async def test_iam_on_a_connection_that_holds_a_power_is_rejected(self, server: DaideServer) -> None:
        first = await _connect(server)
        hlo = await _nme(first)
        passcode = int(hlo[hlo.index(t.AUS) + 3])
        second = await _connect(server)
        assert (await _nme(second))[0] == t.HLO  # ENGLAND
        first[1].close()
        await asyncio.sleep(0.1)  # AUSTRIA's session ends and is unregistered
        await _send(second[1], t.IAM, t.OPEN_PAREN, t.AUS, t.CLOSE_PAREN, t.OPEN_PAREN, Token.from_int(passcode), t.CLOSE_PAREN)
        assert (await _recv_tokens(second[0]))[0] == t.REJ
        assert list(server.sessions_for(server.game_id)) == ["ENGLAND"]
        second[1].close()

    async def test_rej_map_gets_off_closes_the_connection_and_frees_the_power(self, server: DaideServer) -> None:
        conn = await _connect(server)
        await _send(conn[1], t.NME, *text_clause("Bot"), *text_clause("1.0"))
        assert (await _recv_tokens(conn[0]))[0] == t.YES
        map_msg = await _recv_tokens(conn[0])
        await _send(conn[1], t.REJ, t.OPEN_PAREN, *map_msg, t.CLOSE_PAREN)
        assert await _recv_tokens(conn[0]) == [t.OFF]
        assert await asyncio.wait_for(conn[0].read(), timeout=5) == b""
        assert server.sessions_for(server.game_id) == {}
        conn[1].close()


# ---------------------------------------------------------------------------
# (b) a dead peer neither raises into the sender nor stops a fan-out
# ---------------------------------------------------------------------------


class DeadWriter:
    """A peer whose transport is gone: uvloop raises `RuntimeError` on write;
    asyncio's own transport reports `is_closing()`."""

    def __init__(self, *, raises: bool) -> None:
        self.raises = raises
        self.closed = False

    def is_closing(self) -> bool:
        return not self.raises or self.closed

    def write(self, data: bytes) -> None:
        raise RuntimeError("unable to perform operation on <TCPTransport closed=True>; the handler is closed")

    async def drain(self) -> None:
        return None

    def get_extra_info(self, name: str) -> Optional[str]:
        return None

    def close(self) -> None:
        self.closed = True


def _seat_dead_peer(server: DaideServer, *, raises: bool) -> DaideSession:
    """Register a dead session as AUSTRIA, *before* the live ones, so a
    fan-out reaches it first."""
    gid = server.ensure_game_id()
    dead = DaideSession(asyncio.StreamReader(), DeadWriter(raises=raises), server)
    dead.game_id, dead.power = gid, "AUSTRIA"
    server.register(gid, "AUSTRIA", dead)
    return dead


@pytest.mark.parametrize("raises", [True, False], ids=["uvloop-runtime-error", "is-closing"])
class TestDeadPeer:
    async def test_adm_reaches_the_live_peers_and_drops_the_dead_one(self, server: DaideServer, raises: bool) -> None:
        dead = _seat_dead_peer(server, raises=raises)
        sender, other = await _connect(server), await _connect(server)
        await _nme(sender)
        await _nme(other)
        await _send(sender[1], t.ADM, *text_clause("me"), *text_clause("hi"))
        assert (await _recv_tokens(other[0]))[0] == t.ADM
        await _send(sender[1], t.MAP)  # the sender's session survived
        assert (await _recv_tokens(sender[0]))[0] == t.MAP
        assert list(server.sessions_for(server.game_id)) == ["ENGLAND", "FRANCE"]
        assert dead.writer.closed is True
        sender[1].close()
        other[1].close()

    async def test_press_to_a_dead_peer_does_not_stop_delivery(self, server: DaideServer, raises: bool) -> None:
        _seat_dead_peer(server, raises=raises)
        sender, other = await _connect(server), await _connect(server)
        await _nme(sender)
        await _nme(other)
        await _send(sender[1], t.SND, t.OPEN_PAREN, t.AUS, t.FRA, t.CLOSE_PAREN, t.OPEN_PAREN, t.PCE, t.CLOSE_PAREN)
        assert (await _recv_tokens(sender[0]))[0] == t.YES
        assert (await _recv_tokens(other[0]))[0] == t.FRM
        assert list(server.sessions_for(server.game_id)) == ["ENGLAND", "FRANCE"]
        sender[1].close()
        other[1].close()

    async def test_turn_fan_out_skips_the_dead_peer(self, server: DaideServer, raises: bool) -> None:
        _seat_dead_peer(server, raises=raises)
        live = await _connect(server)
        await _nme(live)
        await server.notify_game_processed(server.game_id)
        assert (await _recv_tokens(live[0]))[0] == t.NOW
        assert list(server.sessions_for(server.game_id)) == ["ENGLAND"]
        live[1].close()


# ---------------------------------------------------------------------------
# CO4 (c) / (d): a handler's OSError is logged; accepted sockets keep alive
# ---------------------------------------------------------------------------


class TestHandlerOsErrorAndKeepalive:
    async def test_an_oserror_from_a_handler_is_logged_before_the_session_ends(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def broken(self: DaideSession, payload: bytes) -> None:
            raise OSError("disk on fire")

        caplog.set_level(logging.WARNING)
        monkeypatch.setattr(DaideSession, "_handle_diplomacy", broken)
        reader, writer = await _connect(server)
        await _send(writer, t.MAP)
        assert await asyncio.wait_for(reader.read(), timeout=5) == b""
        assert [r.getMessage() for r in caplog.records if "disk on fire" in r.getMessage()] == [
            f"DAIDE {writer.get_extra_info('sockname')} (no power): "
            "session ended handling a message: OSError('disk on fire')"
        ]
        writer.close()

    async def test_an_accepted_socket_has_tcp_keepalive_on(self, server: DaideServer) -> None:
        conn = await _connect(server)
        await _nme(conn)
        sock = server.sessions_for(server.game_id)["AUSTRIA"].writer.get_extra_info("socket")
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
        if hasattr(socket, "TCP_KEEPIDLE"):
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == server_mod.KEEPALIVE_IDLE_SECONDS
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL) == server_mod.KEEPALIVE_INTERVAL_SECONDS
            assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT) == server_mod.KEEPALIVE_PROBES
        conn[1].close()


# ---------------------------------------------------------------------------
# DD1: a client that never reads, IAM guessing, NME and claimed powers, and a
# connection that never takes a power
# ---------------------------------------------------------------------------


def _iam(power: Token, passcode: int) -> list[Token]:
    return [t.IAM, t.OPEN_PAREN, power, t.CLOSE_PAREN, t.OPEN_PAREN, Token.from_int(passcode), t.CLOSE_PAREN]


def _passcode(hlo: list[Token]) -> int:
    return int(hlo[hlo.index(t.OPEN_PAREN, 2) + 1])


async def _stalled_peer(server: DaideServer) -> tuple[Conn, DaideSession]:
    """A seated client that floods `MDF` requests and never reads a reply,
    until its session's own replies back up in the server's write buffer."""
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    sock.connect(("127.0.0.1", server.port))
    sock.setblocking(False)
    reader, writer = await asyncio.open_connection(sock=sock)
    await wire.write_message(writer, wire.InitialMessage())
    assert isinstance(await _read(reader), wire.RepresentationMessage)
    hlo = await _nme((reader, writer))
    power = t.engine_power_name(hlo[2])
    stuck = server.sessions_for(server.game_id)[power]
    mdf = wire.DiplomacyMessage(payload=bytes(t.MDF)).to_bytes()
    for _ in range(200):
        writer.write(mdf * 100)
        await asyncio.sleep(0.01)
        if stuck.writer.transport.get_write_buffer_size() > 0:
            return (reader, writer), stuck
    raise AssertionError("the server never had to buffer a reply to the stalled client")


class TestPeerThatNeverReads:
    """Each test closes its sockets in ``finally``: were delivery to block
    again, the stalled peer would otherwise hang the fixture's ``stop()``."""

    async def test_press_and_the_turn_fan_out_do_not_wait_for_it(self, server: DaideServer) -> None:
        conns: list[Conn] = []
        try:
            conns.append(sender := await _connect(server))
            await _nme(sender)  # AUSTRIA
            stalled, _stuck = await _stalled_peer(server)  # ENGLAND
            conns.append(stalled)
            await _send(sender[1], t.SND, t.OPEN_PAREN, t.ENG, t.CLOSE_PAREN, t.OPEN_PAREN, t.PCE, t.CLOSE_PAREN)
            assert (await _recv_tokens(sender[0]))[0] == t.YES
            await _send(sender[1], t.MAP)  # the sender's session is not stuck either
            assert (await _recv_tokens(sender[0]))[0] == t.MAP
            conns.append(later := await _connect(server))
            await _nme(later)  # FRANCE
            await asyncio.wait_for(server.notify_game_processed(server.game_id), timeout=5)
            assert (await _recv_tokens(sender[0]))[0] == t.NOW
            assert (await _recv_tokens(later[0]))[0] == t.NOW
        finally:
            for conn in conns:
                conn[1].close()

    async def test_its_backlog_overflowing_drops_it(self, server: DaideServer, monkeypatch: pytest.MonkeyPatch) -> None:
        conns: list[Conn] = []
        try:
            conns.append(live := await _connect(server))
            await _nme(live)  # AUSTRIA
            stalled, stuck = await _stalled_peer(server)  # ENGLAND
            conns.append(stalled)
            monkeypatch.setattr(session_mod, "MAX_OUTBOUND_BUFFER_BYTES", 0, raising=False)
            await asyncio.wait_for(server.notify_game_processed(server.game_id), timeout=5)
            assert (await _recv_tokens(live[0]))[0] == t.NOW
            assert list(server.sessions_for(server.game_id)) == ["AUSTRIA"]
            assert stuck.writer.transport.is_closing()
        finally:
            for conn in conns:
                conn[1].close()


class TestIamGuessing:
    async def test_a_failed_iam_gets_rej_and_ends_the_connection(self, server: DaideServer) -> None:
        owner = await _connect(server)
        passcode = _passcode(await _nme(owner))
        owner[1].close()
        await asyncio.sleep(0.1)  # AUSTRIA's session ends; its passcode stays
        guesser = await _connect(server)
        wrong = _iam(t.AUS, passcode % 8191 + 1)
        await _send(guesser[1], *wrong)
        assert await _recv_tokens(guesser[0]) == [t.REJ, t.OPEN_PAREN, *wrong, t.CLOSE_PAREN]
        assert await asyncio.wait_for(guesser[0].read(), timeout=5) == b""
        guesser[1].close()

    async def test_iam_for_a_power_never_issued_ends_the_connection(self, server: DaideServer) -> None:
        seated = await _connect(server)
        await _nme(seated)  # creates the game: AUSTRIA
        guesser = await _connect(server)
        await _send(guesser[1], *_iam(t.TUR, 1))
        assert (await _recv_tokens(guesser[0]))[0] == t.REJ
        assert await asyncio.wait_for(guesser[0].read(), timeout=5) == b""
        seated[1].close()
        guesser[1].close()

    async def test_the_passcode_comes_from_secrets_within_the_integer_token_range(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bounds: list[int] = []

        def randbelow(n: int) -> int:
            bounds.append(n)
            return n - 1

        monkeypatch.setattr(server_mod.secrets, "randbelow", randbelow)
        gid = server.ensure_game_id()
        assert server.register(gid, "AUSTRIA", DaideSession(asyncio.StreamReader(), DeadWriter(raises=False), server)) == 8191
        assert bounds == [8191]


class TestClaimedPowers:
    async def test_nme_does_not_take_a_disconnected_power_but_iam_does(self, server: DaideServer) -> None:
        first = await _connect(server)
        passcode = _passcode(await _nme(first))  # AUSTRIA
        first[1].close()
        await asyncio.sleep(0.1)
        newcomer = await _connect(server)
        hlo = await _nme(newcomer)
        assert hlo[2] == t.ENG
        back = await _connect(server)
        await _send(back[1], *_iam(t.AUS, passcode))
        assert (await _recv_tokens(back[0]))[0] == t.YES
        assert sorted(server.sessions_for(server.game_id)) == ["AUSTRIA", "ENGLAND"]
        newcomer[1].close()
        back[1].close()

    async def test_nme_is_rejected_when_every_power_has_a_passcode(self, server: DaideServer) -> None:
        for _ in STANDARD_POWERS:
            conn = await _connect(server)
            assert (await _nme(conn))[0] == t.HLO
            conn[1].close()
        await asyncio.sleep(0.1)
        assert server.sessions_for(server.game_id) == {}
        late = await _connect(server)
        assert (await _nme(late))[0] == t.REJ
        late[1].close()

    async def test_rej_map_gives_the_power_up_for_good(self, server: DaideServer) -> None:
        conn = await _connect(server)
        await _send(conn[1], t.NME, *text_clause("Bot"), *text_clause("1.0"))
        assert (await _recv_tokens(conn[0]))[0] == t.YES
        map_msg = await _recv_tokens(conn[0])
        await _send(conn[1], t.REJ, t.OPEN_PAREN, *map_msg, t.CLOSE_PAREN)
        assert await _recv_tokens(conn[0]) == [t.OFF]
        conn[1].close()
        again = await _connect(server)
        assert (await _nme(again))[2] == t.AUS
        again[1].close()


class TestSeatTimeout:
    async def test_a_connection_that_never_takes_a_power_is_closed(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "SEAT_TIMEOUT_SECONDS", 0.2, raising=False)
        reader, writer = await _connect(server)
        await _send(writer, t.MAP)  # an unseated command does not reset the clock
        assert (await _recv_tokens(reader))[0] == t.MAP
        assert await asyncio.wait_for(reader.read(), timeout=5) == b""
        writer.close()

    async def test_a_seated_connection_may_idle_past_it(
        self, server: DaideServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(session_mod, "SEAT_TIMEOUT_SECONDS", 0.2, raising=False)
        conn = await _connect(server)
        await _nme(conn)
        await asyncio.sleep(0.4)
        await _send(conn[1], t.MAP)
        assert (await _recv_tokens(conn[0]))[0] == t.MAP
        conn[1].close()
