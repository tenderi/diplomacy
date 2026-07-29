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

from engine.types import STANDARD_POWERS
from persistence.game_repo import GameRepo
from server.daide import tokens as t
from server.daide.server import DaideServer
from server.daide.session import (
    DaideSession,
    _reason_to_note_token,
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
    async def test_nme_assigns_next_power_and_replies_hlo(self, service: GameService) -> None:
        gid = _new_game(service)
        server = DaideServer(service, game_id=gid)
        writer = FakeWriter()
        session = DaideSession(None, writer, server)

        frames = await _dispatch(session, writer, t.NME, *text_clause("DumbBot"), *text_clause("1.0"))

        assert session.power == STANDARD_POWERS[0]  # AUSTRIA: first unclaimed
        assert session.client_name == "DumbBot"
        assert len(frames) == 1
        hlo = frames[0]
        assert hlo[0] == t.HLO
        assert t.AUS in hlo
        assert t.LVL in hlo

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
            Token.from_int(1),
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
        await session._handle_diplomacy(bytes(t.MAP))
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
            ("BUR is not a legal retreat for A PAR", t.NVR),
            ("no dislodged unit at BUR", t.NSU),
            ("BUR is not adjacent to A PAR", t.FAR),
            ("F NTH cannot reach BUR to support", t.FAR),
            ("a unit cannot support itself", t.FAR),
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


class TestParsePhaseCode:
    def test_roundtrips_a_movement_phase(self) -> None:
        from engine.types import PhaseType, Season

        assert parse_phase_code("S1901M") == (Season.SPRING, PhaseType.MOVEMENT, 1901)

    def test_rejects_a_malformed_code(self) -> None:
        with pytest.raises(ValueError):
            parse_phase_code("nonsense")
