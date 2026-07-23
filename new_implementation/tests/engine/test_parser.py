"""M2 tests for the order grammar: parsing, formatting, and round-tripping."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from engine.map_loader import load_standard_map
from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Location,
    Move,
    Retreat,
    STANDARD_POWERS,
    SupportHold,
    SupportMove,
    UnitKind,
    Waive,
)

pytestmark = pytest.mark.map


@pytest.fixture(scope="module")
def m():
    return load_standard_map()


# ---------------------------------------------------------------------------
# Grammar matrix: one order type at a time, with/without coast, alias spellings
# ---------------------------------------------------------------------------


class TestHold:
    def test_short(self, m):
        assert parse_order("A PAR H", power="FRANCE", map=m) == Hold("FRANCE", Location("PAR"))

    def test_long_forms(self, m):
        expected = Hold("FRANCE", Location("PAR"))
        assert parse_order("A PAR HOLD", power="FRANCE", map=m) == expected
        assert parse_order("A PAR HOLDS", power="FRANCE", map=m) == expected

    def test_fleet_with_coast(self, m):
        assert parse_order("F STP/SC H", power="RUSSIA", map=m) == Hold(
            "RUSSIA", Location("STP", "SC")
        )

    def test_alias_spelling(self, m):
        assert parse_order("A bulg H", power="RUSSIA", map=m) == Hold("RUSSIA", Location("BUL"))

    def test_malformed_missing_verb(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR", power="FRANCE", map=m)

    def test_malformed_trailing_junk(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR H EXTRA", power="FRANCE", map=m)


class TestMove:
    def test_dash_with_spaces(self, m):
        assert parse_order("A PAR - BUR", power="FRANCE", map=m) == Move(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_dash_without_spaces(self, m):
        assert parse_order("A PAR-BUR", power="FRANCE", map=m) == Move(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_fleet_from_coast(self, m):
        assert parse_order("F STP/NC - BAR", power="RUSSIA", map=m) == Move(
            "RUSSIA", Location("STP", "NC"), Location("BAR")
        )

    def test_via_convoy(self, m):
        assert parse_order("A LON - BEL VIA", power="ENGLAND", map=m) == Move(
            "ENGLAND", Location("LON"), Location("BEL"), via_convoy=True
        )
        assert parse_order("A LON - BEL VIA CONVOY", power="ENGLAND", map=m) == Move(
            "ENGLAND", Location("LON"), Location("BEL"), via_convoy=True
        )

    def test_alias_spelling(self, m):
        assert parse_order("A par - burg", power="FRANCE", map=m) == Move(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_malformed_unknown_province(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR - ZZZ", power="FRANCE", map=m)

    def test_malformed_missing_dest(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR -", power="FRANCE", map=m)

    def test_fleet_split_coast_dest_missing_coast_is_parser_ambiguous(self, m):
        # STP is split-coast; a fleet destination there must name a coast.
        with pytest.raises(OrderParseError):
            parse_order("F BAR - STP", power="RUSSIA", map=m)

    def test_army_may_not_carry_coast(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A SPA/SC - GAS", power="FRANCE", map=m)


class TestSupportHold:
    def test_short(self, m):
        assert parse_order("F BRE S A PAR", power="FRANCE", map=m) == SupportHold(
            "FRANCE", Location("BRE"), Location("PAR")
        )

    def test_long(self, m):
        assert parse_order("A MUN SUPPORTS A BER", power="GERMANY", map=m) == SupportHold(
            "GERMANY", Location("MUN"), Location("BER")
        )

    def test_target_with_coast(self, m):
        assert parse_order("F MAO S F SPA/SC", power="FRANCE", map=m) == SupportHold(
            "FRANCE", Location("MAO"), Location("SPA", "SC")
        )

    def test_alias_spelling(self, m):
        assert parse_order("F bre s a par", power="FRANCE", map=m) == SupportHold(
            "FRANCE", Location("BRE"), Location("PAR")
        )

    def test_malformed_missing_supported_unit(self, m):
        with pytest.raises(OrderParseError):
            parse_order("F BRE S", power="FRANCE", map=m)


class TestSupportMove:
    def test_short(self, m):
        assert parse_order("F BRE S A PIC - BEL", power="FRANCE", map=m) == SupportMove(
            "FRANCE", Location("BRE"), Location("PIC"), Location("BEL")
        )

    def test_long(self, m):
        assert parse_order("A MUN S A BER - SIL", power="GERMANY", map=m) == SupportMove(
            "GERMANY", Location("MUN"), Location("BER"), Location("SIL")
        )

    def test_dest_with_coast(self, m):
        assert parse_order("F MAO S F POR - SPA/SC", power="FRANCE", map=m) == SupportMove(
            "FRANCE", Location("MAO"), Location("POR"), Location("SPA", "SC")
        )

    def test_alias_spelling(self, m):
        assert parse_order("F bre s a par - burgandy", power="FRANCE", map=m) == SupportMove(
            "FRANCE", Location("BRE"), Location("PAR"), Location("BUR")
        )

    def test_malformed_dangling_dash(self, m):
        with pytest.raises(OrderParseError):
            parse_order("F BRE S A PIC -", power="FRANCE", map=m)


class TestConvoy:
    def test_short(self, m):
        assert parse_order("F NTH C A LON - BEL", power="ENGLAND", map=m) == Convoy(
            "ENGLAND", Location("NTH"), Location("LON"), Location("BEL")
        )

    def test_long(self, m):
        assert parse_order("F NTH CONVOYS A LON - BEL", power="ENGLAND", map=m) == Convoy(
            "ENGLAND", Location("NTH"), Location("LON"), Location("BEL")
        )

    def test_alias_spelling(self, m):
        assert parse_order("F nth c a lon - burgandy", power="ENGLAND", map=m) == Convoy(
            "ENGLAND", Location("NTH"), Location("LON"), Location("BUR")
        )

    def test_malformed_convoying_fleet(self, m):
        # a convoy order must carry an army, not a fleet.
        with pytest.raises(OrderParseError):
            parse_order("F NTH C F LON - BEL", power="ENGLAND", map=m)

    def test_malformed_missing_dash(self, m):
        with pytest.raises(OrderParseError):
            parse_order("F NTH C A LON BEL", power="ENGLAND", map=m)


class TestRetreat:
    def test_short(self, m):
        assert parse_order("A PAR R BUR", power="FRANCE", map=m) == Retreat(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_long(self, m):
        assert parse_order("A PAR RETREAT BUR", power="FRANCE", map=m) == Retreat(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_fleet_with_coast(self, m):
        assert parse_order("F STP/NC R BAR", power="RUSSIA", map=m) == Retreat(
            "RUSSIA", Location("STP", "NC"), Location("BAR")
        )

    def test_alias_spelling(self, m):
        assert parse_order("A par r burg", power="FRANCE", map=m) == Retreat(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_malformed_missing_dest(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR R", power="FRANCE", map=m)


class TestDisband:
    def test_prefix_form(self, m):
        assert parse_order("D A PAR", power="FRANCE", map=m) == Disband("FRANCE", Location("PAR"))

    def test_suffix_forms(self, m):
        expected = Disband("FRANCE", Location("PAR"))
        assert parse_order("A PAR D", power="FRANCE", map=m) == expected
        assert parse_order("A PAR DISBAND", power="FRANCE", map=m) == expected

    def test_fleet_with_coast(self, m):
        assert parse_order("D F STP/SC", power="RUSSIA", map=m) == Disband(
            "RUSSIA", Location("STP", "SC")
        )

    def test_alias_spelling(self, m):
        assert parse_order("D A bulg", power="RUSSIA", map=m) == Disband(
            "RUSSIA", Location("BUL")
        )

    def test_malformed(self, m):
        with pytest.raises(OrderParseError):
            parse_order("D PAR", power="FRANCE", map=m)


class TestBuild:
    def test_build_prefix_army(self, m):
        assert parse_order("BUILD A PAR", power="FRANCE", map=m) == Build(
            "FRANCE", Location("PAR"), UnitKind.ARMY
        )

    def test_build_prefix_fleet_with_coast(self, m):
        assert parse_order("BUILD F STP/SC", power="RUSSIA", map=m) == Build(
            "RUSSIA", Location("STP", "SC"), UnitKind.FLEET
        )

    def test_build_suffix_forms(self, m):
        assert parse_order("A PAR B", power="FRANCE", map=m) == Build(
            "FRANCE", Location("PAR"), UnitKind.ARMY
        )
        assert parse_order("F STP/SC BUILD", power="RUSSIA", map=m) == Build(
            "RUSSIA", Location("STP", "SC"), UnitKind.FLEET
        )

    def test_alias_spelling(self, m):
        assert parse_order("BUILD A bulg", power="RUSSIA", map=m) == Build(
            "RUSSIA", Location("BUL"), UnitKind.ARMY
        )

    def test_malformed_missing_location(self, m):
        with pytest.raises(OrderParseError):
            parse_order("BUILD A", power="FRANCE", map=m)

    def test_malformed_bad_kind(self, m):
        with pytest.raises(OrderParseError):
            parse_order("BUILD X PAR", power="FRANCE", map=m)


class TestWaive:
    def test_bare(self, m):
        assert parse_order("WAIVE", power="FRANCE", map=m) == Waive("FRANCE")

    def test_with_power_prefix(self, m):
        assert parse_order("FRANCE WAIVE", power="FRANCE", map=m) == Waive("FRANCE")


class TestPowerPrefix:
    def test_colon_form(self, m):
        assert parse_order("FRANCE: A PAR - BUR", power="FRANCE", map=m) == Move(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_bare_form(self, m):
        assert parse_order("FRANCE A PAR - BUR", power="FRANCE", map=m) == Move(
            "FRANCE", Location("PAR"), Location("BUR")
        )

    def test_mismatched_power_raises(self, m):
        with pytest.raises(OrderParseError):
            parse_order("GERMANY: A PAR - BUR", power="FRANCE", map=m)


class TestGeneralMalformed:
    def test_empty_string(self, m):
        with pytest.raises(OrderParseError):
            parse_order("", power="FRANCE", map=m)

    def test_blank_string(self, m):
        with pytest.raises(OrderParseError):
            parse_order("   ", power="FRANCE", map=m)

    def test_unknown_verb(self, m):
        with pytest.raises(OrderParseError):
            parse_order("A PAR X BUR", power="FRANCE", map=m)

    def test_no_unit_kind(self, m):
        with pytest.raises(OrderParseError):
            parse_order("HOLD A PAR", power="FRANCE", map=m)


# ---------------------------------------------------------------------------
# Hypothesis round-trip property: parse_order(format_order(o)) == o
# ---------------------------------------------------------------------------

_MAP = load_standard_map()
_ALL_PROVINCES = sorted(_MAP.provinces)
_BARE_LOCS = [Location(p, None) for p in _ALL_PROVINCES]
_BARE_NONSPLIT_LOCS = [Location(p, None) for p in _ALL_PROVINCES if not _MAP.is_split_coast(p)]
_COASTAL_LOCS = [
    Location(p, c) for p in _ALL_PROVINCES if _MAP.is_split_coast(p) for c in _MAP.coasts_of(p)
]

_powers = st.sampled_from(STANDARD_POWERS)
_any_loc = st.one_of(st.sampled_from(_BARE_LOCS), st.sampled_from(_COASTAL_LOCS))

# A (unit_loc, dest) pair safe for Move/Retreat: format_order infers the acting
# unit's kind purely from whether `unit_loc` carries a coast (see parser.py's
# docstring), and that inferred kind then governs how `dest` gets re-parsed.
# So either both locations are coastless ("army" case), or `unit_loc` carries a
# coast and `dest` is either coastal or a coastless *non-split* province.
_army_pair = st.tuples(st.sampled_from(_BARE_LOCS), st.sampled_from(_BARE_LOCS))
_fleet_pair = st.tuples(
    st.sampled_from(_COASTAL_LOCS),
    st.sampled_from(_COASTAL_LOCS + _BARE_NONSPLIT_LOCS),
)
_move_pairs = st.one_of(_army_pair, _fleet_pair)

_build_options = []
for _p in _ALL_PROVINCES:
    _build_options.append((UnitKind.ARMY, Location(_p, None)))
    if _MAP.is_split_coast(_p):
        for _c in _MAP.coasts_of(_p):
            _build_options.append((UnitKind.FLEET, Location(_p, _c)))
    else:
        _build_options.append((UnitKind.FLEET, Location(_p, None)))


@given(power=_powers, loc=_any_loc)
def test_hold_roundtrip_property(power, loc):
    order = Hold(power, loc)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, loc=_any_loc)
def test_disband_roundtrip_property(power, loc):
    order = Disband(power, loc)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, pair=_move_pairs, via=st.booleans())
def test_move_roundtrip_property(power, pair, via):
    unit_loc, dest = pair
    order = Move(power, unit_loc, dest, via_convoy=via)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, pair=_move_pairs)
def test_retreat_roundtrip_property(power, pair):
    unit_loc, dest = pair
    order = Retreat(power, unit_loc, dest)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, unit_loc=_any_loc, target_loc=_any_loc)
def test_support_hold_roundtrip_property(power, unit_loc, target_loc):
    order = SupportHold(power, unit_loc, target_loc)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, unit_loc=_any_loc, pair=_move_pairs)
def test_support_move_roundtrip_property(power, unit_loc, pair):
    origin, dest = pair
    order = SupportMove(power, unit_loc, origin, dest)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(
    power=_powers,
    unit_loc=_any_loc,
    origin=st.sampled_from(_BARE_LOCS),
    dest=st.sampled_from(_BARE_LOCS),
)
def test_convoy_roundtrip_property(power, unit_loc, origin, dest):
    order = Convoy(power, unit_loc, origin, dest)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers, pair=st.sampled_from(_build_options))
def test_build_roundtrip_property(power, pair):
    kind, loc = pair
    order = Build(power, loc, kind)
    assert parse_order(format_order(order), power=power, map=_MAP) == order


@given(power=_powers)
def test_waive_roundtrip_property(power):
    order = Waive(power)
    assert parse_order(format_order(order), power=power, map=_MAP) == order
