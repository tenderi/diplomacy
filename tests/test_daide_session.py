"""Tests for the DAIDE session/dispatch logic (Track D, D4).

Per the task's own testing guidance, these exercise `DaideSession`'s command
handlers directly against a real `GameService` (backed by the test Postgres
database, same pattern as `tests/test_game_service.py`) rather than going
through a real socket -- feed a decoded clause/command in, assert the right
`GameService` call happened and the right response tokens came out. A single
real end-to-end raw-socket smoke test lives in `tests/test_daide_server.py`
(full byte-level coverage is D5's job, a separate, later task).
"""

from __future__ import annotations

import uuid

import pytest

from engine.serialization import state_to_dict
from engine.map_loader import load_standard_map
from engine.types import STANDARD_POWERS, DislodgedUnit, GameState, Location, PhaseType, Season, Unit, UnitKind
from persistence.game_repo import GameRepo
from server.daide import tokens as t
from server.daide.server import DaideServer
from server.daide.session import (
    DaideSession,
    _reason_to_note_token,
    build_hlo_tokens,
    build_mdf_tokens,
    build_now_tokens,
    build_sco_tokens,
    build_mis_tokens,
    parse_phase_code,
    text_clause,
)
from server.daide.tokens import Token
from server.game_service import GameService
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.database


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class FakeWriter:
    """Captures every complete DCSP frame `_send` writes, without a socket."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.sent.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def _decode_frame(frame: bytes) -> list[Token]:
    payload = frame[4:]
    return [Token.from_bytes(payload[i : i + 2]) for i in range(0, len(payload), 2)]


async def _dispatch(session: DaideSession, writer: FakeWriter, *tokens_: Token) -> list[list[Token]]:
    before = len(writer.sent)
    payload = b"".join(bytes(tok) for tok in tokens_)
    await session._handle_diplomacy(payload)
    return [_decode_frame(f) for f in writer.sent[before:]]


@pytest.fixture
def service(temp_db) -> GameService:
    session_factory = sessionmaker(bind=temp_db)
    return GameService(GameRepo(session_factory))


def _new_game(service: GameService) -> str:
    gid = f"daide-{uuid.uuid4().hex[:8]}"
    service.create_game(gid)
    return gid


def _identified_session(
    service: GameService, power: str = "AUSTRIA"
) -> tuple[DaideSession, FakeWriter, DaideServer, str]:
    gid = _new_game(service)
    server = DaideServer(service, game_id=gid)
    writer = FakeWriter()
    session = DaideSession(None, writer, server)
    session.power = power
    server.register(gid, power, session)
    return session, writer, server, gid


def _unit_order_clause(power: Token, kind: Token, province: Token, verb: Token, *tail: Token) -> list[Token]:
    return [t.OPEN_PAREN, t.OPEN_PAREN, power, kind, province, t.CLOSE_PAREN, verb, *tail, t.CLOSE_PAREN]


# ---------------------------------------------------------------------------
# NME / HLO
# ---------------------------------------------------------------------------


class TestNmeHlo:
    async def test_nme_seats_a_power_and_replies_yes_then_map(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)

        nme = [t.NME, *text_clause("DumbBot"), *text_clause("1.0")]
        frames = await _dispatch(session, writer, *nme)

        assert session.power == STANDARD_POWERS[0]  # AUSTRIA: first unclaimed
        assert session.client_name == "DumbBot"
        assert frames == [[t.YES, t.OPEN_PAREN, *nme, t.CLOSE_PAREN], [t.MAP, *text_clause("STANDARD")]]

    async def test_yes_map_completes_the_handshake_with_hlo_sco_now(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)
        await _dispatch(session, writer, t.NME, *text_clause("DumbBot"), *text_clause("1.0"))
        yes_map = [t.YES, t.OPEN_PAREN, t.MAP, *text_clause("STANDARD"), t.CLOSE_PAREN]

        frames = await _dispatch(session, writer, *yes_map)

        game = service.load(gid)
        assert frames == [
            build_hlo_tokens("AUSTRIA", session.passcode),
            build_sco_tokens(service.view(gid)["ownership"], server.map),
            build_now_tokens(game.state, server.map),
        ]
        assert await _dispatch(session, writer, *yes_map) == []  # a repeat needs no answer

    async def test_map_and_mdf_are_served_before_nme(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)

        assert await _dispatch(session, writer, t.MAP) == [[t.MAP, *text_clause("STANDARD")]]
        assert await _dispatch(session, writer, t.MDF) == [build_mdf_tokens(server.map)]
        assert session.power is None

    async def test_rej_map_releases_the_power_and_ends_the_session(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)
        await _dispatch(session, writer, t.NME, *text_clause("Bot"), *text_clause("1.0"))

        frames = await _dispatch(session, writer, t.REJ, t.OPEN_PAREN, t.MAP, *text_clause("STANDARD"), t.CLOSE_PAREN)

        assert frames == [[t.OFF]]
        assert session.power is None
        assert session.closing is True
        assert server.sessions_for(gid) == {}

    async def test_yes_or_rej_of_anything_but_map_is_huh(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        for verb in (t.YES, t.REJ):
            frames = await _dispatch(session, writer, verb, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN)
            assert frames == [[t.HUH, t.OPEN_PAREN, verb, t.ERR, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN, t.CLOSE_PAREN]]
        assert session.power == "AUSTRIA"

    async def test_obs_is_rejected(self, service: GameService) -> None:
        gid = _new_game(service)
        session = DaideSession(None, writer := FakeWriter(), DaideServer(service, game_id=gid))
        assert await _dispatch(session, writer, t.OBS) == [[t.REJ, t.OPEN_PAREN, t.OBS, t.CLOSE_PAREN]]

    async def test_client_hlo_resends_hlo_after_iam(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w1 = FakeWriter()
        s1 = DaideSession(None, w1, server)
        await _dispatch(s1, w1, t.NME, *text_clause("Bot"), *text_clause("1.0"))
        server.unregister(gid, s1.power, s1)
        w2 = FakeWriter()
        s2 = DaideSession(None, w2, server)
        iam = [t.IAM, t.OPEN_PAREN, t.AUS, t.CLOSE_PAREN, t.OPEN_PAREN, Token.from_int(s1.passcode), t.CLOSE_PAREN]
        assert await _dispatch(s2, w2, *iam) == [[t.YES, t.OPEN_PAREN, *iam, t.CLOSE_PAREN]]

        assert await _dispatch(s2, w2, t.HLO) == [build_hlo_tokens("AUSTRIA", s1.passcode)]

    async def test_nme_rejected_once_every_power_is_claimed(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        for power in STANDARD_POWERS:
            server.register(gid, power, object())  # dummy occupant; never sent to
        writer = FakeWriter()
        session = DaideSession(None, writer, server)

        frames = await _dispatch(session, writer, t.NME, *text_clause("Bot"), *text_clause("1.0"))

        assert session.power is None
        assert frames[0][0] == t.REJ

    async def test_iam_reclaims_power_after_disconnect(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w1 = FakeWriter()
        s1 = DaideSession(None, w1, server)
        await _dispatch(s1, w1, t.NME, *text_clause("Bot"), *text_clause("1.0"))
        power, passcode = s1.power, s1.passcode
        assert power is not None and passcode is not None

        server.unregister(gid, power, s1)  # simulate a dropped connection

        w2 = FakeWriter()
        s2 = DaideSession(None, w2, server)
        frames = await _dispatch(
            s2,
            w2,
            t.IAM,
            t.OPEN_PAREN,
            t.POWER_TOKEN_BY_ENGINE_NAME[power],
            t.CLOSE_PAREN,
            t.OPEN_PAREN,
            Token.from_int(passcode),
            t.CLOSE_PAREN,
        )

        assert s2.power == power
        assert frames[0][0] == t.YES

    async def test_iam_wrong_passcode_is_rejected(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w1 = FakeWriter()
        s1 = DaideSession(None, w1, server)
        await _dispatch(s1, w1, t.NME, *text_clause("Bot"), *text_clause("1.0"))
        power = s1.power
        server.unregister(gid, power, s1)
        # The passcode is random in 1..8191; a fixed guess would match once in 8191 runs.
        wrong = s1.passcode % 8191 + 1

        w2 = FakeWriter()
        s2 = DaideSession(None, w2, server)
        frames = await _dispatch(
            s2,
            w2,
            t.IAM,
            t.OPEN_PAREN,
            t.POWER_TOKEN_BY_ENGINE_NAME[power],
            t.CLOSE_PAREN,
            t.OPEN_PAREN,
            Token.from_int(wrong),
            t.CLOSE_PAREN,
        )
        assert s2.power is None
        assert frames[0][0] == t.REJ


# ---------------------------------------------------------------------------
# MAP / MDF
# ---------------------------------------------------------------------------


class TestMapMdf:
    async def test_map_reports_standard(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.MAP)
        assert frames[0][0] == t.MAP

    async def test_mdf_reports_full_topology(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.MDF)
        mdf = frames[0]
        assert mdf[0] == t.MDF
        assert t.AUS in mdf
        assert t.BUD in mdf
        assert t.PAR in mdf  # every province appears, SC or not
        assert t.UNO in mdf  # unowned centers group


# ---------------------------------------------------------------------------
# SCO / NOW
# ---------------------------------------------------------------------------


class TestScoNow:
    async def test_sco_reports_home_ownership_for_a_fresh_game(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.SCO)
        sco = frames[0]
        assert sco[0] == t.SCO
        assert t.AUS in sco
        assert t.UNO in sco

    async def test_now_reports_units_and_turn(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.NOW)
        now = frames[0]
        assert now[0] == t.NOW
        assert t.SPR in now
        assert t.AUS in now
        assert t.BUD in now


# ---------------------------------------------------------------------------
# SUB / THX / NOT(SUB)
# ---------------------------------------------------------------------------


class TestSub:
    async def test_valid_order_gets_mbv(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        hold = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *hold)
        assert len(frames) == 1
        assert frames[0][0] == t.THX
        assert t.MBV in frames[0]
        assert service.pending_orders_parsed(gid)["AUSTRIA"]

    async def test_illegal_order_gets_a_mapped_note(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        # No unit at all stands in Burgundy at kickoff -> validate() rejects
        # with "no unit at BUR".
        bad = _unit_order_clause(t.AUS, t.AMY, t.BUR, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *bad)
        assert frames[0][0] == t.THX
        assert t.NSU in frames[0]
        assert t.MBV not in frames[0]

    async def test_order_for_another_powers_unit_gets_nyu(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        # PAR holds a FRANCE unit at kickoff -> ownership check rejects.
        bad = _unit_order_clause(t.AUS, t.AMY, t.PAR, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *bad)
        assert frames[0][0] == t.THX
        assert t.NYU in frames[0]
        assert t.MBV not in frames[0]

    async def test_mixed_batch_gets_one_thx_per_order(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        good = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD)
        bad = _unit_order_clause(t.AUS, t.AMY, t.BUR, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *good, *bad)
        assert len(frames) == 2
        assert t.MBV in frames[0]
        assert t.MBV not in frames[1]

    async def test_fleet_move_from_the_sea_into_a_named_coast_is_accepted(self, service: GameService) -> None:
        """SUB went through ``format_order`` without the board's kinds: the fleet's
        ``F BLA - BUL/EC`` became ``A BLA - BUL/EC``, re-parsed as a coastless army
        move, and was refused as a fleet move that must name a coast."""
        session, writer, _server, gid = _identified_session(service, power="RUSSIA")
        state = GameState(
            1901, Season.SPRING, PhaseType.MOVEMENT,
            units=frozenset({Unit(UnitKind.FLEET, "RUSSIA", Location("BLA"))}), ownership={},
        )
        service.restore_snapshot(gid, state_to_dict(state), phase_code=state.phase_name)
        move = _unit_order_clause(
            t.RUS, t.FLT, t.BLA, t.MTO, t.OPEN_PAREN, t.BUL, t.ECS, t.CLOSE_PAREN
        )
        frames = await _dispatch(session, writer, t.SUB, *move)
        assert t.MBV in frames[0]
        assert service.pending_orders_view(gid)["RUSSIA"] == ["F BLA - BUL/EC"]

    async def test_not_sub_clears_pending_orders(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        hold = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD)
        await _dispatch(session, writer, t.SUB, *hold)
        assert service.pending_orders_parsed(gid).get("AUSTRIA")

        frames = await _dispatch(session, writer, t.NOT, t.OPEN_PAREN, t.SUB, t.CLOSE_PAREN)
        assert frames[0][0] == t.YES
        assert service.pending_orders_parsed(gid).get("AUSTRIA", []) == []


# ---------------------------------------------------------------------------
# DRW / NOT(DRW)
# ---------------------------------------------------------------------------


class TestDraw:
    async def test_drw_records_a_yes_vote_and_acks(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.DRW)
        assert frames[0][0] == t.YES
        votes = service.get_draw_votes(gid)
        assert votes is not None
        assert "AUSTRIA" in votes["votes"]

    async def test_not_drw_removes_the_vote(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        await _dispatch(session, writer, t.DRW)
        await _dispatch(session, writer, t.NOT, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN)
        votes = service.get_draw_votes(gid)
        assert votes is not None
        assert "AUSTRIA" not in votes["votes"]

    async def test_quorum_broadcasts_drw_to_every_session_on_the_game(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        # Shrink quorum to just AUSTRIA + ENGLAND by conceding everyone else.
        for power in ("FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"):
            service.concede(gid, power)

        w_aus = FakeWriter()
        s_aus = DaideSession(None, w_aus, server)
        s_aus.power = "AUSTRIA"
        server.register(gid, "AUSTRIA", s_aus)

        w_eng = FakeWriter()
        s_eng = DaideSession(None, w_eng, server)
        s_eng.power = "ENGLAND"
        server.register(gid, "ENGLAND", s_eng)

        await _dispatch(s_aus, w_aus, t.DRW)
        before_eng = len(w_eng.sent)
        eng_frames = await _dispatch(s_eng, w_eng, t.DRW)

        # ENGLAND's own YES ack, plus the broadcast DRW completion landing on
        # both sessions once quorum is reached by this second vote.
        assert eng_frames[0][0] == t.YES
        aus_frames = [_decode_frame(f) for f in w_aus.sent]
        eng_broadcast_frames = [_decode_frame(f) for f in w_eng.sent[before_eng:]]
        assert any(f == [t.DRW] for f in aus_frames)
        assert any(f == [t.DRW] for f in eng_broadcast_frames)


class TestGameOver:
    """Once the game has ended, well-formed write commands get REJ rather than
    an unhandled ``GameOverError`` tearing the session down."""

    async def _drawn_game(self, service: GameService) -> tuple[DaideSession, FakeWriter, str]:
        session, writer, _server, gid = _identified_session(service)
        for power in ("ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"):
            service.concede(gid, power)
        await _dispatch(session, writer, t.DRW)  # sole survivor: quorum of one
        view = service.view(gid)
        assert view is not None and view["status"] == "COMPLETED"
        return session, writer, gid

    async def test_sub_after_game_over_is_rejected(self, service: GameService) -> None:
        session, writer, gid = await self._drawn_game(service)
        clause = _unit_order_clause(t.AUS, t.AMY, t.VIE, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *clause)
        assert frames == [[t.REJ, t.OPEN_PAREN, t.SUB, *clause, t.CLOSE_PAREN]]
        assert service.pending_orders_view(gid) == {}

    async def test_drw_and_not_drw_after_game_over_are_rejected(self, service: GameService) -> None:
        session, writer, _gid = await self._drawn_game(service)
        assert (await _dispatch(session, writer, t.DRW)) == [[t.REJ, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN]]
        not_drw = [t.NOT, t.OPEN_PAREN, t.DRW, t.CLOSE_PAREN]
        assert (await _dispatch(session, writer, *not_drw)) == [
            [t.REJ, t.OPEN_PAREN, *not_drw, t.CLOSE_PAREN]
        ]

    async def test_reads_still_work_after_game_over(self, service: GameService) -> None:
        session, writer, _gid = await self._drawn_game(service)
        frames = await _dispatch(session, writer, t.NOW)
        assert frames[0][0] == t.NOW


# ---------------------------------------------------------------------------
# MIS / TME
# ---------------------------------------------------------------------------


class TestMisTme:
    async def test_mis_lists_units_with_no_order_yet(self, service: GameService) -> None:
        session, writer, server, gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.MIS)
        mis = frames[0]
        assert mis[0] == t.MIS
        assert t.BUD in mis  # AUS home units, none ordered yet

    async def test_mis_omits_units_already_ordered(self, service: GameService) -> None:
        session, writer, server, gid = _identified_session(service)
        hold = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD)
        await _dispatch(session, writer, t.SUB, *hold)
        tokens_ = build_mis_tokens(service, server.map, gid, "AUSTRIA")
        assert t.BUD not in tokens_

    async def test_tme_reports_negative_one_when_no_deadline_configured(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.TME)
        tme = frames[0]
        assert tme[0] == t.TME
        assert any(tok.is_integer and int(tok) == -1 for tok in tme)


# ---------------------------------------------------------------------------
# ADM / SND-FRM
# ---------------------------------------------------------------------------


class TestAdmSnd:
    async def test_adm_broadcasts_to_other_sessions_not_the_sender(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w1, w2 = FakeWriter(), FakeWriter()
        s1 = DaideSession(None, w1, server)
        s1.power = "AUSTRIA"
        server.register(gid, "AUSTRIA", s1)
        s2 = DaideSession(None, w2, server)
        s2.power = "ENGLAND"
        server.register(gid, "ENGLAND", s2)

        msg = [t.ADM, *text_clause("bob"), *text_clause("hello everyone")]
        await s1._handle_diplomacy(b"".join(bytes(tok) for tok in msg))

        assert w1.sent == []
        assert len(w2.sent) == 1
        frame = _decode_frame(w2.sent[0])
        assert frame[0] == t.ADM

    async def test_snd_relays_as_frm_to_the_recipient(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        w1, w2 = FakeWriter(), FakeWriter()
        s1 = DaideSession(None, w1, server)
        s1.power = "AUSTRIA"
        server.register(gid, "AUSTRIA", s1)
        s2 = DaideSession(None, w2, server)
        s2.power = "ENGLAND"
        server.register(gid, "ENGLAND", s2)

        payload = [t.SND, t.OPEN_PAREN, t.ENG, t.CLOSE_PAREN, t.OPEN_PAREN, t.PRP, t.PCE, t.CLOSE_PAREN]
        frames = await _dispatch(s1, w1, *payload)

        assert frames[0][0] == t.YES
        assert len(w2.sent) == 1
        frm = _decode_frame(w2.sent[0])
        assert frm[0] == t.FRM
        assert t.PRP in frm

    async def test_snd_to_a_power_with_no_session_is_silently_dropped(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service, power="AUSTRIA")
        payload = [t.SND, t.OPEN_PAREN, t.ENG, t.CLOSE_PAREN, t.OPEN_PAREN, t.PRP, t.PCE, t.CLOSE_PAREN]
        frames = await _dispatch(session, writer, *payload)
        assert frames[0][0] == t.YES  # no error -- just nothing delivered


# ---------------------------------------------------------------------------
# Protocol-level error cases
# ---------------------------------------------------------------------------


class TestErrors:
    async def test_unbalanced_parens_yields_prn(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        payload = bytes(t.SUB) + bytes(t.OPEN_PAREN)
        await session._handle_diplomacy(payload)
        frame = _decode_frame(writer.sent[-1])
        assert frame[0] == t.PRN

    async def test_unknown_command_yields_huh(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        await session._handle_diplomacy(bytes(t.SVE))
        frame = _decode_frame(writer.sent[-1])
        assert frame[0] == t.HUH

    async def test_command_before_identification_is_rejected(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)
        await session._handle_diplomacy(bytes(t.NOW))
        frame = _decode_frame(writer.sent[-1])
        assert frame[0] == t.REJ

    async def test_hst_is_rejected(self, service: GameService) -> None:
        """Documented scope-cut -- see `DaideSession._cmd_hst`'s docstring."""
        session, writer, _server, _gid = _identified_session(service)
        turn = [t.HST, t.OPEN_PAREN, t.SPR, Token.from_int(1901), t.CLOSE_PAREN]
        frames = await _dispatch(session, writer, *turn)
        assert frames[0][0] == t.REJ

    async def test_gof_and_not_gof_are_acknowledged(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.GOF)
        assert frames[0][0] == t.YES
        frames = await _dispatch(session, writer, t.NOT, t.OPEN_PAREN, t.GOF, t.CLOSE_PAREN)
        assert frames[0][0] == t.YES

    async def test_not_tme_is_rejected(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.NOT, t.OPEN_PAREN, t.TME, t.CLOSE_PAREN)
        assert frames[0][0] == t.REJ

    async def test_snd_with_an_unknown_recipient_token_yields_huh(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        payload = [t.SND, t.OPEN_PAREN, t.HLD, t.CLOSE_PAREN, t.OPEN_PAREN, t.PRP, t.CLOSE_PAREN]
        frames = await _dispatch(session, writer, *payload)
        assert frames[0][0] == t.HUH

    async def test_adm_with_wrong_group_count_yields_huh(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.ADM, *text_clause("only-one-group"))
        assert frames[0][0] == t.HUH


# ---------------------------------------------------------------------------
# THX order-note mapping table (pure function, no DB needed for these -- but
# kept in this module alongside the tests that exercise it end-to-end).
# ---------------------------------------------------------------------------


class TestReasonToNoteToken:
    def test_none_reason_is_might_be_valid(self) -> None:
        assert _reason_to_note_token(None) == t.MBV

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("BUD is not a home supply center of FRANCE", t.HSC),
            ("BUD is not currently owned by FRANCE", t.YSC),
            ("BUD is occupied", t.ESC),
            ("fleet build at split-coast STP must name a valid coast", t.CST),
            ("STP has no coasts to choose from", t.CST),
            ("an army build may not specify a coast", t.CST),
            ("fleet retreat into split-coast STP must name a coast", t.CST),
            ("cannot build a fleet on landlocked SWI", t.NAS),
            ("cannot build an army at sea: NTH", t.NAS),
            ("AUSTRIA has no build to make: 2 supply centres, 2 units", t.NMB),
            ("TURKEY has no build to waive (3 supply centres, 4 units); it must disband 1 unit", t.NMB),
            ("ENGLAND has 1 build; 2 builds/waives submitted", t.NMB),
            ("GERMANY has no unit to disband (4 supply centres, 2 units); it may build 2 units", t.NMR),
            ("GERMANY has 1 disband; 2 disbands submitted", t.NMR),
            ("BUR is not a legal retreat for A PAR", t.NVR),
            ("no dislodged unit at BUR", t.NRN),
            ("BUR is not adjacent to A PAR", t.FAR),
            ("F NTH cannot reach BUR to support", t.FAR),
            ("A MAR cannot reach LYO: an army cannot enter a sea", t.FAR),
            ("LYO is not a legal retreat for A MAR: an army cannot enter a sea", t.NVR),
            ("a unit cannot support itself", t.FAR),
            ("A TRI cannot move to its own province", t.FAR),
            ("a movement order is not accepted during the retreat phase (S1901R)", t.NRS),
            ("a convoying fleet must be in a sea space", t.NAS),
            ("only a fleet may convoy", t.NSF),
            ("only an army may move via convoy", t.NSA),
            ("BUR is not a coastal province", t.FAR),
            ("unit at BUD belongs to FRANCE, not AUSTRIA", t.NYU),
            ("no unit to disband at BUD", t.NSU),
            ("no unit at BUR", t.NSU),
            ("unit at STP is on coast 'NC', not 'SC'", t.CST),
            ("unknown province: 'ZZZ'", t.NSP),
            ("missing unit location", t.NSU),
            ("something entirely unmapped happened", t.NSP),
        ],
    )
    def test_reason_maps_to_expected_token(self, reason: str, expected) -> None:
        assert _reason_to_note_token(reason) == expected


def _retreat_phase(service: GameService, gid: str) -> None:
    st = GameState(
        1901, Season.SPRING, PhaseType.RETREAT,
        units=frozenset({Unit(UnitKind.ARMY, "AUSTRIA", Location("BUD"))}), ownership={},
    )
    service.restore_snapshot(gid, state_to_dict(st), phase_code=st.phase_name)


def _adjustment_phase(service: GameService, gid: str, centres: tuple[str, ...]) -> None:
    """W1901A with AUSTRIA's F TRI, A SER and A GAL, and ``centres`` AUSTRIA's."""
    units = {
        Unit(UnitKind.FLEET, "AUSTRIA", Location("TRI")),
        Unit(UnitKind.ARMY, "AUSTRIA", Location("SER")),
        Unit(UnitKind.ARMY, "AUSTRIA", Location("GAL")),
    }
    st = GameState(
        1901, Season.WINTER, PhaseType.ADJUSTMENT,
        units=frozenset(units), ownership={c: "AUSTRIA" for c in centres},
    )
    service.restore_snapshot(gid, state_to_dict(st), phase_code=st.phase_name)


class TestSubMergeAndNotes:
    async def test_sub_replaces_only_the_same_units_order(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        await _dispatch(session, writer, t.SUB, *_unit_order_clause(t.AUS, t.FLT, t.TRI, t.HLD))
        frames = await _dispatch(session, writer, t.SUB, *_unit_order_clause(t.AUS, t.AMY, t.VIE, t.HLD))
        assert t.MBV in frames[0]
        assert sorted(service.pending_orders_view(gid)["AUSTRIA"]) == ["A VIE H", "F TRI H"]
        await _dispatch(session, writer, t.SUB, *_unit_order_clause(t.AUS, t.FLT, t.TRI, t.MTO, t.VEN))
        assert sorted(service.pending_orders_view(gid)["AUSTRIA"]) == ["A VIE H", "F TRI - VEN"]

    async def test_bare_sub_is_huh(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.SUB)
        assert frames == [[t.HUH, t.OPEN_PAREN, t.SUB, t.ERR, t.CLOSE_PAREN]]

    async def test_order_of_the_wrong_phase_is_nrs(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        _retreat_phase(service, gid)
        frames = await _dispatch(session, writer, t.SUB, *_unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD))
        assert frames[0][-2] == t.NRS

    async def test_retreat_for_a_unit_owing_none_is_nrn(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        _retreat_phase(service, gid)
        rto = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.RTO, t.SER)
        dsb = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.DSB)
        assert (await _dispatch(session, writer, t.SUB, *rto))[0][-2] == t.NRN
        assert (await _dispatch(session, writer, t.SUB, *dsb))[0][-2] == t.NRN

    async def test_retreat_from_a_province_with_no_unit_is_nsu(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        _retreat_phase(service, gid)  # AUSTRIA's only unit is A BUD, not dislodged
        rto = _unit_order_clause(t.AUS, t.AMY, t.VIE, t.RTO, t.BOH)
        dsb = _unit_order_clause(t.AUS, t.AMY, t.VIE, t.DSB)
        assert (await _dispatch(session, writer, t.SUB, *rto))[0][-2] == t.NSU
        assert (await _dispatch(session, writer, t.SUB, *dsb))[0][-2] == t.NSU

    async def test_a_build_past_the_count_in_a_later_sub_is_nmb_and_the_first_stands(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=("VIE", "BUD", "TRI", "SER"))  # 3 units: 1 build owed
        vie = _unit_order_clause(t.AUS, t.AMY, t.VIE, t.BLD)
        bud = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.BLD)
        assert (await _dispatch(session, writer, t.SUB, *vie))[0][-2] == t.MBV
        assert (await _dispatch(session, writer, t.SUB, *bud))[0][-2] == t.NMB
        assert service.pending_orders_view(gid)["AUSTRIA"] == ["BUILD A VIE"]

    async def test_a_removal_past_the_count_in_a_later_sub_is_nmr_and_the_first_stands(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=("VIE", "BUD"))  # 3 units: 1 disband owed
        ser = _unit_order_clause(t.AUS, t.AMY, t.SER, t.REM)
        gal = _unit_order_clause(t.AUS, t.AMY, t.GAL, t.REM)
        assert (await _dispatch(session, writer, t.SUB, *ser))[0][-2] == t.MBV
        assert (await _dispatch(session, writer, t.SUB, *gal))[0][-2] == t.NMR
        assert service.pending_orders_view(gid)["AUSTRIA"] == ["D A SER"]

    async def test_move_to_its_own_province_is_far(self, service: GameService) -> None:
        session, writer, _server, _gid = _identified_session(service)
        frames = await _dispatch(session, writer, t.SUB, *_unit_order_clause(t.AUS, t.AMY, t.TRI, t.MTO, t.TRI))
        assert frames[0][-2] == t.FAR


class TestParsePhaseCode:
    def test_roundtrips_a_movement_phase(self) -> None:
        from engine.types import PhaseType, Season

        assert parse_phase_code("S1901M") == (Season.SPRING, PhaseType.MOVEMENT, 1901)

    def test_rejects_a_malformed_code(self) -> None:
        with pytest.raises(ValueError):
            parse_phase_code("nonsense")


# ---------------------------------------------------------------------------
# Retreat and adjustment replies, checked token for token against the DAIDE
# message syntax: NOW/MIS with ``(unit MRT (province list))`` entries,
# ``MIS (n)`` (positive: disbands still owed; negative: builds still owed; no
# parameters when nothing is owed), and the ``RET`` note on ``ORD``.
# ---------------------------------------------------------------------------


def _open(*inner: Token) -> list[Token]:
    return [t.OPEN_PAREN, *inner, t.CLOSE_PAREN]


def _dislodging_turn(service: GameService, gid: str) -> str:
    """S1901M with Russia dislodging Austria's A BUD (held) and Turkey's F CON
    (whose own move to BLA bounces); processes it and returns the resolved phase.

    Retreats left: A BUD to SER/TRI/VIE (GAL is the attacker's origin, RUM is
    occupied); F CON to AEG, both coasts of BUL and SMY (ANK is the attacker's
    origin, BLA is occupied)."""
    units = {
        Unit(UnitKind.ARMY, "AUSTRIA", Location("BUD")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("GAL")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("RUM")),
        Unit(UnitKind.ARMY, "RUSSIA", Location("ANK")),
        Unit(UnitKind.FLEET, "RUSSIA", Location("BLA")),
        Unit(UnitKind.FLEET, "TURKEY", Location("CON")),
    }
    st = GameState(1901, Season.SPRING, PhaseType.MOVEMENT, units=frozenset(units), ownership={})
    service.restore_snapshot(gid, state_to_dict(st), phase_code=st.phase_name)
    service.submit_orders(gid, "AUSTRIA", ["A BUD H"])
    service.submit_orders(
        gid, "RUSSIA", ["A GAL - BUD", "A RUM S A GAL - BUD", "A ANK - CON", "F BLA S A ANK - CON"]
    )
    service.submit_orders(gid, "TURKEY", ["F CON - BLA"])
    service.process_turn(gid)
    return st.phase_name


_BUD_MRT = [t.AUS, t.AMY, t.BUD, t.MRT, *_open(t.SER, t.TRI, t.VIE)]
_CON_MRT = [t.TUR, t.FLT, t.CON, t.MRT, *_open(t.AEG, *_open(t.BUL, t.ECS), *_open(t.BUL, t.SCS), t.SMY)]


class TestRetreatAndAdjustmentReplies:
    async def test_now_in_a_retreat_phase_lists_dislodged_units_with_their_retreats(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _dislodging_turn(service, gid)
        frames = await _dispatch(session, writer, t.NOW)
        assert frames == [
            [
                t.NOW, *_open(t.SUM, Token.from_int(1901)),
                *_open(t.RUS, t.FLT, t.BLA), *_open(t.RUS, t.AMY, t.BUD),
                *_open(t.RUS, t.AMY, t.CON), *_open(t.RUS, t.AMY, t.RUM),
                *_open(*_BUD_MRT), *_open(*_CON_MRT),
            ]
        ]

    def test_now_lists_a_dislodged_unit_with_no_retreat_as_an_empty_mrt(self) -> None:
        state = GameState(
            1901, Season.SPRING, PhaseType.RETREAT,
            units=frozenset({Unit(UnitKind.ARMY, "GERMANY", Location("MUN"))}), ownership={},
            dislodged=(DislodgedUnit(Unit(UnitKind.FLEET, "ENGLAND", Location("NTH")), "HEL", ()),),
        )
        assert build_now_tokens(state, load_standard_map()) == [
            t.NOW, *_open(t.SUM, Token.from_int(1901)),
            *_open(t.GER, t.AMY, t.MUN), *_open(t.ENG, t.FLT, t.NTH, t.MRT, t.OPEN_PAREN, t.CLOSE_PAREN),
        ]

    async def test_mis_in_a_retreat_phase_lists_the_unordered_dislodged_units(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service, power="TURKEY")
        _dislodging_turn(service, gid)
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS, *_open(*_CON_MRT)]]
        rto = _unit_order_clause(t.TUR, t.FLT, t.CON, t.RTO, t.SMY)
        assert (await _dispatch(session, writer, t.SUB, *rto))[0][-2] == t.MBV
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS]]

    async def test_ord_marks_a_dislodged_unit_with_ret(self, service: GameService) -> None:
        _session, writer, server, gid = _identified_session(service)
        resolved = _dislodging_turn(service, gid)
        await server.notify_game_processed(gid, resolved_phase=resolved)
        ords = [f for f in (_decode_frame(raw) for raw in writer.sent) if f[0] == t.ORD]
        turn = _open(t.SPR, Token.from_int(1901))
        assert [t.ORD, *turn, *_open(*_open(t.AUS, t.AMY, t.BUD), t.HLD), *_open(t.RET)] in ords
        assert [
            t.ORD, *turn, *_open(*_open(t.TUR, t.FLT, t.CON), t.MTO, t.BLA), *_open(t.BNC, t.RET)
        ] in ords
        assert [t.ORD, *turn, *_open(*_open(t.RUS, t.AMY, t.GAL), t.MTO, t.BUD), *_open(t.SUC)] in ords

    @pytest.mark.parametrize(
        ("centres", "owed"),
        [(("VIE", "BUD", "TRI", "SER"), -1), (("VIE", "BUD", "TRI", "SER", "GRE"), -2), (("VIE", "BUD"), 1)],
    )
    async def test_mis_in_an_adjustment_phase_is_disbands_positive_builds_negative(
        self, service: GameService, centres: tuple[str, ...], owed: int
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=centres)  # three units
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS, *_open(Token.from_int(owed))]]

    async def test_mis_in_an_adjustment_phase_counts_only_the_builds_still_owed(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=("VIE", "BUD", "TRI", "SER", "GRE"))  # two builds
        build = _unit_order_clause(t.AUS, t.AMY, t.VIE, t.BLD)
        assert (await _dispatch(session, writer, t.SUB, *build))[0][-2] == t.MBV
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS, *_open(Token.from_int(-1))]]
        waive = _open(t.AUS, t.WVE)
        assert (await _dispatch(session, writer, t.SUB, *waive))[0][-2] == t.MBV
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS]]

    async def test_mis_in_an_adjustment_phase_counts_only_the_disbands_still_owed(
        self, service: GameService
    ) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=("VIE",))  # two disbands
        remove = _unit_order_clause(t.AUS, t.AMY, t.GAL, t.REM)
        assert (await _dispatch(session, writer, t.SUB, *remove))[0][-2] == t.MBV
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS, *_open(Token.from_int(1))]]

    async def test_mis_in_a_balanced_adjustment_phase_is_bare(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service)
        _adjustment_phase(service, gid, centres=("VIE", "BUD", "TRI"))
        assert await _dispatch(session, writer, t.MIS) == [[t.MIS]]

    async def test_sub_for_another_powers_unit_is_nyu_and_stores_nothing(self, service: GameService) -> None:
        session, writer, _server, gid = _identified_session(service, power="FRANCE")
        hold = _unit_order_clause(t.AUS, t.AMY, t.BUD, t.HLD)
        frames = await _dispatch(session, writer, t.SUB, *hold)
        assert frames == [[t.THX, *hold, *_open(t.NYU)]]
        assert service.pending_orders_view(gid).get("FRANCE", []) == []
        assert service.pending_orders_view(gid).get("AUSTRIA", []) == []
