"""Tests for the DAIDE token vocabulary (Track D, D1).

Covers: round-tripping every registered token through str/bytes, the signed
14-bit integer encoding at its documented boundaries, the ASCII-escape
fallback, and a literal byte-value spot check (computed here, not imported
from `old_implementation`) against the external DAIDE specification for all
7 powers and a representative mix of province types.
"""

from __future__ import annotations

import pytest

from server.daide import tokens
from server.daide.tokens import (
    ALL_TOKENS,
    ASCII_MARKER,
    COMMAND_TOKENS,
    PROVINCE_TOKENS,
    Token,
    daide_province_token,
    verify_standard_map_coverage,
)


# ---------------------------------------------------------------------------
# Round-tripping every registered token
# ---------------------------------------------------------------------------


def test_registry_is_nonempty_and_every_entry_is_two_bytes():
    assert len(ALL_TOKENS) > 100
    for token in ALL_TOKENS:
        assert len(bytes(token)) == 2


@pytest.mark.parametrize("token", ALL_TOKENS, ids=lambda t: t.text)
def test_str_to_bytes_to_str_roundtrips(token: Token):
    rebuilt_from_str = Token.from_str(token.text)
    assert bytes(rebuilt_from_str) == bytes(token)
    rebuilt_from_bytes = Token.from_bytes(bytes(token))
    assert str(rebuilt_from_bytes) == token.text
    assert bytes(rebuilt_from_bytes) == bytes(token)


def test_no_duplicate_text_or_bytes_in_registry():
    texts = [t.text for t in ALL_TOKENS]
    raws = [bytes(t) for t in ALL_TOKENS]
    assert len(texts) == len(set(texts))
    assert len(raws) == len(set(raws))


def test_unknown_string_raises():
    with pytest.raises(ValueError):
        Token.from_str("NOT_A_REAL_TOKEN")


def test_unknown_bytes_raise():
    # 0x4F is not used by any registered category and is not the ASCII marker
    # or an integer-token leading byte (>= 0x40 rules out the integer case).
    with pytest.raises(ValueError):
        Token.from_bytes(bytes((0x4F, 0xFF)))


def test_from_bytes_requires_exactly_two_bytes():
    with pytest.raises(ValueError):
        Token.from_bytes(b"\x00")
    with pytest.raises(ValueError):
        Token.from_bytes(b"\x00\x00\x00")


# ---------------------------------------------------------------------------
# Signed 14-bit integer encoding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_bytes",
    [
        (0, b"\x00\x00"),
        (8191, b"\x1f\xff"),
        (-1, b"\x3f\xff"),
        (-8192, b"\x20\x00"),
    ],
)
def test_integer_token_boundaries_match_expected_bytes(value: int, expected_bytes: bytes):
    token = Token.from_int(value)
    assert bytes(token) == expected_bytes
    assert int(token) == value
    assert token.is_integer
    assert not token.is_ascii_escape

    decoded = Token.from_bytes(expected_bytes)
    assert int(decoded) == value


@pytest.mark.parametrize("value", [-8192, -1, 0, 1, 8191])
def test_integer_roundtrips_str_to_bytes_to_int(value: int):
    token = Token.from_int(value)
    rebuilt = Token.from_bytes(bytes(token))
    assert int(rebuilt) == value
    assert str(rebuilt) == str(value)


@pytest.mark.parametrize("value", [8192, -8193, 20000, -20000])
def test_integer_out_of_range_raises(value: int):
    with pytest.raises(ValueError):
        Token.from_int(value)


def test_integer_token_has_no_string_registered():
    # An integer's decimal text must not collide with a registered mnemonic.
    with pytest.raises(ValueError):
        Token.from_str("42")


# ---------------------------------------------------------------------------
# ASCII escape fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("char", ["Z", "9", " ", "!", "\x00", chr(255)])
def test_ascii_escape_roundtrips(char: str):
    token = Token.from_str(char)
    assert token.is_ascii_escape
    assert not token.is_integer
    raw = bytes(token)
    assert raw[0] == ASCII_MARKER
    assert raw[1] == ord(char)

    decoded = Token.from_bytes(raw)
    assert decoded.text == char


def test_ascii_escape_rejects_multi_char_and_out_of_range():
    with pytest.raises(ValueError):
        Token.from_str("ZZ_not_a_token")
    with pytest.raises(ValueError):
        Token.from_str(chr(256))


def test_ascii_escape_does_not_shadow_a_real_token():
    # "A" is a single ASCII char, but it is not a registered mnemonic, so it
    # must fall back to the escape rather than erroring.
    token = Token.from_str("A")
    assert token.is_ascii_escape
    # A genuinely registered 3-letter mnemonic is unaffected by the fallback.
    assert not Token.from_str("HLD").is_ascii_escape


# ---------------------------------------------------------------------------
# Literal byte-value spot check -- all 7 powers, plus a representative mix
# of province categories (inland, coastal, sea, bicoastal). These values are
# computed by hand against the DAIDE specification (cross-checked by eye
# against old_implementation/diplomacy/daide/tokens.py, per Track D's Ground
# Rules) -- not imported from it.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("AUS", b"\x41\x00"),
        ("ENG", b"\x41\x01"),
        ("FRA", b"\x41\x02"),
        ("GER", b"\x41\x03"),
        ("ITA", b"\x41\x04"),
        ("RUS", b"\x41\x05"),
        ("TUR", b"\x41\x06"),
    ],
)
def test_all_seven_power_tokens_match_spec(text: str, expected: bytes):
    assert bytes(Token.from_str(text)) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("PAR", b"\x51\x0a"),  # inland, supply center
        ("BUR", b"\x50\x01"),  # inland, non-supply-center
        ("LON", b"\x55\x3a"),  # coastal, supply center
        ("YOR", b"\x54\x2f"),  # coastal, non-supply-center
        ("MAO", b"\x52\x1a"),  # sea
        ("ADR", b"\x52\x0e"),  # sea
        ("BUL", b"\x57\x48"),  # bicoastal supply center
        ("SPA", b"\x57\x49"),  # bicoastal supply center
        ("STP", b"\x57\x4a"),  # bicoastal supply center
        ("MUN", b"\x51\x09"),  # inland, supply center
    ],
)
def test_ten_province_tokens_match_spec(text: str, expected: bytes):
    assert bytes(Token.from_str(text)) == expected


def test_the_three_daide_sea_names_that_differ_from_engine_codes():
    # Engine calls these ENG/BOT/LYO; DAIDE calls them ECH/GOB/GOL because
    # ENG is already the England power token. Byte values per spec.
    assert bytes(Token.from_str("ECH")) == b"\x52\x14"
    assert bytes(Token.from_str("GOB")) == b"\x52\x15"
    assert bytes(Token.from_str("GOL")) == b"\x52\x16"


def test_a_sample_of_command_tokens_match_spec():
    assert bytes(Token.from_str("HLO")) == b"\x48\x04"
    assert bytes(Token.from_str("MAP")) == b"\x48\x09"
    assert bytes(Token.from_str("SCO")) == b"\x48\x15"
    assert bytes(Token.from_str("NOW")) == b"\x48\x0e"
    assert bytes(Token.from_str("SUB")) == b"\x48\x18"
    assert bytes(Token.from_str("ORD")) == b"\x48\x11"
    assert bytes(Token.from_str("THX")) == b"\x48\x1a"


def test_command_tokens_cover_the_required_command_set():
    required = {
        "HLO", "MAP", "MDF", "SCO", "NOW", "SUB", "ORD", "THX", "TME", "HST",
        "DRW", "SLO", "YES", "REJ", "NOT", "HUH", "PRN", "OFF", "ADM", "MIS",
        "NME", "IAM", "OBS", "GOF", "SVE", "LOD", "CCD", "OUT", "SMR", "SND",
        "FRM",
    }
    present = {t.text for t in COMMAND_TOKENS}
    assert required <= present


# ---------------------------------------------------------------------------
# Province coverage is derived from engine.map_loader, not hand-duplicated
# ---------------------------------------------------------------------------


def test_verify_standard_map_coverage_passes():
    verify_standard_map_coverage()


def test_province_token_count_matches_standard_map():
    from engine.map_loader import load_standard_map

    live = load_standard_map().provinces
    assert len(PROVINCE_TOKENS) == len(live)


def test_daide_province_token_translates_the_three_renamed_seas():
    assert daide_province_token("ENG").text == "ECH"
    assert daide_province_token("BOT").text == "GOB"
    assert daide_province_token("LYO").text == "GOL"


def test_daide_province_token_is_identity_for_everything_else():
    assert daide_province_token("PAR").text == "PAR"
    assert daide_province_token("stp").text == "STP"


def test_split_coast_provinces_have_the_expected_coast_tokens():
    from engine.map_loader import load_standard_map

    live = load_standard_map()
    split = {p for p in live.provinces if live.is_split_coast(p)}
    assert split == {"BUL", "SPA", "STP"}

    for province in split:
        for suffix in live.coasts_of(province):
            assert suffix in tokens.COAST_TOKEN_BY_ENGINE_SUFFIX


def test_registering_a_duplicate_token_text_raises():
    with pytest.raises(ValueError):
        tokens._register("HLD", 0x7E, 0x7E)


def test_registering_a_duplicate_token_bytes_raises():
    with pytest.raises(ValueError):
        tokens._register("__NEW_NAME__", 0x48, 0x04)  # HLO's bytes
