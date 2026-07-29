"""Tests for the DAIDE clause encode/decode bridge (Track D, D2).

Covers the atomic translation functions directly (province/coast, power, unit,
turn) and, for every one of the 9 DAIDE order-clause types, a full round trip:
hand-written DAIDE tokens -> `decode_order` -> `Order`, checked against what
`engine.orders.parser.parse_order` builds from the equivalent order string,
then `encode_order` back to confirm the same tokens come out.
"""

from __future__ import annotations

import pytest

from engine.map_loader import MapData, load_standard_map
from engine.orders.parser import parse_order
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Location,
    Move,
    PhaseType,
    Retreat,
    Season,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
    Waive,
)
from server.daide import clauses as c
from server.daide import tokens as t


@pytest.fixture(scope="module")
def m() -> MapData:
    return load_standard_map()


def toks(*texts: str) -> tuple[t.Token, ...]:
    """Shorthand for building an expected clause from token-text strings."""
    return tuple(t.Token.from_str(x) for x in texts)


# ---------------------------------------------------------------------------
# Province + coast <-> Location
# ---------------------------------------------------------------------------


class TestLocation:
    def test_bare_province_no_coast(self, m: MapData):
        loc = Location("PAR")
        clause = c.location_to_clause(loc)
        assert clause == (t.PAR,)
        decoded, consumed = c.location_from_clause(clause, map=m, fleet=False)
        assert decoded == loc
        assert consumed == 1

    def test_renamed_sea_province(self, m: MapData):
        # engine ENG (English Channel) -> DAIDE ECH.
        loc = Location("ENG")
        clause = c.location_to_clause(loc)
        assert clause == (t.ECH,)
        decoded, consumed = c.location_from_clause(clause, map=m, fleet=True)
        assert decoded == loc

    @pytest.mark.parametrize(
        "province,coast,coast_token",
        [
            ("STP", "SC", t.SCS),
            ("STP", "NC", t.NCS),
            ("SPA", "NC", t.NCS),
            ("SPA", "SC", t.SCS),
            ("BUL", "EC", t.ECS),
            ("BUL", "SC", t.SCS),
        ],
    )
    def test_split_coast_provinces_roundtrip(
        self, m: MapData, province: str, coast: str, coast_token: t.Token
    ):
        loc = Location(province, coast)
        clause = c.location_to_clause(loc)
        assert clause == (t.OPEN_PAREN, t.Token.from_str(province), coast_token, t.CLOSE_PAREN)
        decoded, consumed = c.location_from_clause(clause, map=m, fleet=True)
        assert decoded == loc
        assert consumed == len(clause)

    def test_coast_on_non_split_province_is_a_decode_error(self, m: MapData):
        # BRE is coastal but not split -- attaching a coast token is malformed.
        bogus = (t.OPEN_PAREN, t.BRE, t.SCS, t.CLOSE_PAREN)
        with pytest.raises(c.ClauseDecodeError):
            c.location_from_clause(bogus, map=m, fleet=True)

    def test_missing_coast_for_fleet_at_split_province_is_a_decode_error(self, m: MapData):
        with pytest.raises(c.ClauseDecodeError):
            c.location_from_clause((t.STP,), map=m, fleet=True)

    def test_bare_split_province_for_an_army_is_fine(self, m: MapData):
        decoded, consumed = c.location_from_clause((t.STP,), map=m, fleet=False)
        assert decoded == Location("STP")
        assert consumed == 1

    def test_coast_on_an_army_location_is_a_decode_error(self, m: MapData):
        clause = (t.OPEN_PAREN, t.STP, t.SCS, t.CLOSE_PAREN)
        with pytest.raises(c.ClauseDecodeError):
            c.location_from_clause(clause, map=m, fleet=False)

    def test_wrong_coast_for_province_is_a_decode_error(self, m: MapData):
        # STP has NC/SC, not EC.
        clause = (t.OPEN_PAREN, t.STP, t.ECS, t.CLOSE_PAREN)
        with pytest.raises(c.ClauseDecodeError):
            c.location_from_clause(clause, map=m, fleet=True)


# ---------------------------------------------------------------------------
# Power <-> token
# ---------------------------------------------------------------------------


class TestPower:
    @pytest.mark.parametrize("name,token", list(t.POWER_TOKEN_BY_ENGINE_NAME.items()))
    def test_all_seven_powers_roundtrip(self, name: str, token: t.Token):
        assert t.engine_power_name(token) == name

    def test_unknown_power_token_raises(self):
        with pytest.raises(ValueError):
            t.engine_power_name(t.PAR)

    def test_uno_is_rejected_as_a_real_power(self):
        with pytest.raises(ValueError):
            t.engine_power_name(t.UNO)


# ---------------------------------------------------------------------------
# Unit <-> engine.types.Unit
# ---------------------------------------------------------------------------


class TestUnit:
    def test_army_unit_roundtrips(self, m: MapData):
        unit = Unit(kind=UnitKind.ARMY, power="FRANCE", location=Location("PAR"))
        clause = c.unit_to_clause(unit)
        assert clause == (t.OPEN_PAREN, t.FRA, t.AMY, t.PAR, t.CLOSE_PAREN)
        decoded, consumed = c.unit_from_clause(clause, map=m)
        assert decoded == unit
        assert consumed == len(clause)

    def test_fleet_at_split_coast_roundtrips(self, m: MapData):
        unit = Unit(kind=UnitKind.FLEET, power="RUSSIA", location=Location("STP", "SC"))
        clause = c.unit_to_clause(unit)
        assert clause == (
            t.OPEN_PAREN,
            t.RUS,
            t.FLT,
            t.OPEN_PAREN,
            t.STP,
            t.SCS,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
        )
        decoded, consumed = c.unit_from_clause(clause, map=m)
        assert decoded == unit
        assert consumed == len(clause)

    def test_unknown_power_placeholder_decodes_to_uno_string(self, m: MapData):
        clause = (t.OPEN_PAREN, t.UNO, t.AMY, t.PAR, t.CLOSE_PAREN)
        decoded, _ = c.unit_from_clause(clause, map=m)
        assert decoded.power == "UNO"
        assert decoded.location == Location("PAR")

    def test_bad_unit_type_token_raises(self, m: MapData):
        clause = (t.OPEN_PAREN, t.FRA, t.HLD, t.PAR, t.CLOSE_PAREN)
        with pytest.raises(c.ClauseDecodeError):
            c.unit_from_clause(clause, map=m)


# ---------------------------------------------------------------------------
# Turn/season <-> (Season, PhaseType)
# ---------------------------------------------------------------------------


class TestTurn:
    @pytest.mark.parametrize(
        "token,season,phase_type",
        [
            (t.SPR, Season.SPRING, PhaseType.MOVEMENT),
            (t.SUM, Season.SPRING, PhaseType.RETREAT),
            (t.FAL, Season.FALL, PhaseType.MOVEMENT),
            (t.AUT, Season.FALL, PhaseType.RETREAT),
            (t.WIN, Season.WINTER, PhaseType.ADJUSTMENT),
        ],
    )
    def test_all_five_phases_roundtrip(self, token: t.Token, season: Season, phase_type: PhaseType):
        assert c.turn_token_to_engine(token) == (season, phase_type)
        assert c.engine_to_turn_token(season, phase_type) == token

    def test_turn_clause_carries_the_year(self):
        clause = c.turn_clause(Season.FALL, PhaseType.MOVEMENT, 1901)
        assert clause == (t.OPEN_PAREN, t.FAL, t.Token.from_int(1901), t.CLOSE_PAREN)
        season, phase_type, year = c.turn_from_clause(clause)
        assert (season, phase_type, year) == (Season.FALL, PhaseType.MOVEMENT, 1901)

    def test_unreal_phase_combination_has_no_turn_token(self):
        with pytest.raises(ValueError):
            c.engine_to_turn_token(Season.SPRING, PhaseType.ADJUSTMENT)

    def test_malformed_turn_clause_raises(self):
        with pytest.raises(c.ClauseDecodeError):
            c.turn_from_clause((t.SPR, t.Token.from_int(1901)))


# ---------------------------------------------------------------------------
# Order clauses <-> engine.types.Order, all 9 DAIDE order-clause types
# ---------------------------------------------------------------------------


class TestHold:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("A PAR H", power="FRANCE", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.HLD,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Hold)
        assert c.encode_order(decoded, phase_type=PhaseType.MOVEMENT, map=m) == clause


class TestMoveTo:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("A PAR - BUR", power="FRANCE", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.MTO,
            t.BUR,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Move)
        assert decoded.via_convoy is False
        assert c.encode_order(decoded, phase_type=PhaseType.MOVEMENT, map=m) == clause

    def test_fleet_move_out_of_split_coast_and_into_a_renamed_sea(self, m: MapData):
        # F STP/SC - BOT (engine BOT -> DAIDE GOB).
        expected = parse_order("F STP/SC - BOT", power="RUSSIA", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.RUS,
            t.FLT,
            t.OPEN_PAREN,
            t.STP,
            t.SCS,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
            t.MTO,
            t.GOB,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert (
            c.encode_order(
                decoded, phase_type=PhaseType.MOVEMENT, map=m, kind_by_province={"STP": "F"}
            )
            == clause
        )


class TestSupport:
    def test_support_hold_roundtrip(self, m: MapData):
        expected = parse_order("F BRE S A PAR", power="FRANCE", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.FLT,
            t.BRE,
            t.CLOSE_PAREN,
            t.SUP,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, SupportHold)
        kbp = {"BRE": "F", "PAR": "A"}
        pbp = {"PAR": "FRANCE"}
        assert (
            c.encode_order(
                decoded,
                phase_type=PhaseType.MOVEMENT,
                map=m,
                kind_by_province=kbp,
                power_by_province=pbp,
            )
            == clause
        )

    def test_support_move_roundtrip(self, m: MapData):
        expected = parse_order("F BRE S A PAR - BUR", power="FRANCE", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.FLT,
            t.BRE,
            t.CLOSE_PAREN,
            t.SUP,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.MTO,
            t.BUR,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, SupportMove)
        kbp = {"BRE": "F", "PAR": "A"}
        pbp = {"PAR": "FRANCE"}
        assert (
            c.encode_order(
                decoded,
                phase_type=PhaseType.MOVEMENT,
                map=m,
                kind_by_province=kbp,
                power_by_province=pbp,
            )
            == clause
        )

    def test_support_move_falls_back_to_uno_without_power_lookup(self, m: MapData):
        order = SupportMove(
            "FRANCE", unit=Location("BRE"), origin=Location("PAR"), dest=Location("BUR")
        )
        clause = c.encode_order(
            order, phase_type=PhaseType.MOVEMENT, map=m, kind_by_province={"BRE": "F", "PAR": "A"}
        )
        assert t.UNO in clause


class TestConvoy:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("F NTH C A LON - BEL", power="ENGLAND", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ENG,
            t.FLT,
            t.NTH,
            t.CLOSE_PAREN,
            t.CVY,
            t.OPEN_PAREN,
            t.ENG,
            t.AMY,
            t.LON,
            t.CLOSE_PAREN,
            t.CTO,
            t.BEL,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Convoy)
        kbp = {"NTH": "F", "LON": "A"}
        pbp = {"LON": "ENGLAND"}
        assert (
            c.encode_order(
                decoded,
                phase_type=PhaseType.MOVEMENT,
                map=m,
                kind_by_province=kbp,
                power_by_province=pbp,
            )
            == clause
        )

    def test_convoying_a_fleet_is_a_decode_error(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ENG,
            t.FLT,
            t.NTH,
            t.CLOSE_PAREN,
            t.CVY,
            t.OPEN_PAREN,
            t.ENG,
            t.FLT,
            t.LON,
            t.CLOSE_PAREN,
            t.CTO,
            t.BEL,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)


class TestConvoyedMoveViaAndVia:
    def test_cto_via_roundtrip_with_explicit_fleet_list(self, m: MapData):
        expected = parse_order("A LON - BEL VIA", power="ENGLAND", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ENG,
            t.AMY,
            t.LON,
            t.CLOSE_PAREN,
            t.CTO,
            t.BEL,
            t.VIA,
            t.OPEN_PAREN,
            t.NTH,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Move)
        assert decoded.via_convoy is True
        encoded = c.encode_order(
            decoded, phase_type=PhaseType.MOVEMENT, map=m, via_fleets=[Location("NTH")]
        )
        assert encoded == clause

    def test_cto_via_with_no_fleets_supplied_encodes_an_empty_group(self, m: MapData):
        order = Move("ENGLAND", unit=Location("LON"), dest=Location("BEL"), via_convoy=True)
        clause = c.encode_order(order, phase_type=PhaseType.MOVEMENT, map=m)
        assert clause[-4:] == (t.VIA, t.OPEN_PAREN, t.CLOSE_PAREN, t.CLOSE_PAREN)
        decoded = c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
        assert decoded == order

    def test_malformed_via_list_is_a_decode_error(self, m: MapData):
        # VIA not followed by a parenthesized group at all.
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ENG,
            t.AMY,
            t.LON,
            t.CLOSE_PAREN,
            t.CTO,
            t.BEL,
            t.VIA,
            t.NTH,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)

    def test_via_list_containing_a_non_province_token_is_a_decode_error(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ENG,
            t.AMY,
            t.LON,
            t.CLOSE_PAREN,
            t.CTO,
            t.BEL,
            t.VIA,
            t.OPEN_PAREN,
            t.HLD,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
        )
        with pytest.raises(ValueError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)


class TestBuild:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("BUILD F STP/SC", power="RUSSIA", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.RUS,
            t.FLT,
            t.OPEN_PAREN,
            t.STP,
            t.SCS,
            t.CLOSE_PAREN,
            t.CLOSE_PAREN,
            t.BLD,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.ADJUSTMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Build)
        assert c.encode_order(decoded, phase_type=PhaseType.ADJUSTMENT, map=m) == clause


class TestRemove:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("D A PAR", power="FRANCE", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.REM,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.ADJUSTMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Disband)
        assert c.encode_order(decoded, phase_type=PhaseType.ADJUSTMENT, map=m) == clause

    def test_rem_in_a_retreat_phase_is_a_decode_error(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.REM,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.RETREAT, map=m)


class TestWaive:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("WAIVE", power="GERMANY", map=m)
        clause = (t.OPEN_PAREN, t.GER, t.WVE, t.CLOSE_PAREN)
        decoded = c.decode_order(clause, phase_type=PhaseType.ADJUSTMENT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Waive)
        assert c.encode_order(decoded, phase_type=PhaseType.ADJUSTMENT, map=m) == clause


class TestRetreatTo:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("A VEN R TRI", power="ITALY", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ITA,
            t.AMY,
            t.VEN,
            t.CLOSE_PAREN,
            t.RTO,
            t.TRI,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.RETREAT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Retreat)
        assert c.encode_order(decoded, phase_type=PhaseType.RETREAT, map=m) == clause


class TestDisband:
    def test_roundtrip(self, m: MapData):
        expected = parse_order("D A VEN", power="ITALY", map=m)
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ITA,
            t.AMY,
            t.VEN,
            t.CLOSE_PAREN,
            t.DSB,
            t.CLOSE_PAREN,
        )
        decoded = c.decode_order(clause, phase_type=PhaseType.RETREAT, map=m)
        assert decoded == expected
        assert isinstance(decoded, Disband)
        assert c.encode_order(decoded, phase_type=PhaseType.RETREAT, map=m) == clause

    def test_dsb_in_an_adjustment_phase_is_a_decode_error(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.ITA,
            t.AMY,
            t.VEN,
            t.CLOSE_PAREN,
            t.DSB,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.ADJUSTMENT, map=m)

    def test_the_same_disband_order_encodes_differently_by_phase(self, m: MapData):
        order = Disband("ITALY", unit=Location("VEN"))
        retreat_clause = c.encode_order(order, phase_type=PhaseType.RETREAT, map=m)
        adjustment_clause = c.encode_order(order, phase_type=PhaseType.ADJUSTMENT, map=m)
        assert t.DSB in retreat_clause
        assert t.REM in adjustment_clause
        assert t.REM not in retreat_clause
        assert t.DSB not in adjustment_clause


# ---------------------------------------------------------------------------
# Malformed order-clause shapes
# ---------------------------------------------------------------------------


class TestMalformedOrderClauses:
    def test_missing_outer_parens_raises(self, m: MapData):
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order((t.FRA, t.AMY, t.PAR, t.HLD), phase_type=PhaseType.MOVEMENT, map=m)

    def test_empty_clause_raises(self, m: MapData):
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order((t.OPEN_PAREN, t.CLOSE_PAREN), phase_type=PhaseType.MOVEMENT, map=m)

    def test_unrecognized_verb_raises(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.BEL,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)

    def test_uno_as_the_orders_own_power_is_rejected(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.UNO,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.HLD,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)

    def test_trailing_tokens_after_a_complete_order_raise(self, m: MapData):
        clause = (
            t.OPEN_PAREN,
            t.OPEN_PAREN,
            t.FRA,
            t.AMY,
            t.PAR,
            t.CLOSE_PAREN,
            t.HLD,
            t.BUR,
            t.CLOSE_PAREN,
        )
        with pytest.raises(c.ClauseDecodeError):
            c.decode_order(clause, phase_type=PhaseType.MOVEMENT, map=m)
