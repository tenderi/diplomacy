"""Every order string the Telegram bot shows a player must actually parse.

Track G1: the bot's `/rules`, `/examples`, `/help` and demo-game text documented
full-province-name orders (`A Berlin - Kiel`) throughout, and *every one of them*
raised `OrderParseError: unknown province: 'BERLIN'`. Two of the blocks also
claimed `ARMY`/`FLEET` were accepted long forms (they are rejected) and marked
`A Berlin HOLD` with a ❌ (that form is valid — only the unit kind must be short).

The docs had been wrong since before the engine rewrite because nothing read
them. This test reads the *actual* help text a player receives and parses each
order through the real engine, so the next wrong example fails CI.

The two prior bugs of this shape (PR1's `spec_from_file_location` tests, PR3's
routeless `GameView` test) both had a test that exercised something *adjacent*
to the thing that broke. Hence: assert on the strings themselves.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from engine.map_loader import load_standard_map
from engine.orders.parser import OrderParseError, parse_order
from server.telegram_bot import help_text

# Backtick-quoted spans are how every example is marked up for Telegram Markdown.
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")

# A code span is order-like if its first token is a unit kind or an order verb.
# This deliberately includes the *wrong* spellings (`ARMY`, `FLEET`) so that
# reintroducing "or full names: ARMY, FLEET" is caught rather than skipped over.
_ORDER_FIRST_TOKENS = {
    "A", "F", "ARMY", "FLEET",
    "BUILD", "B", "D", "DISBAND", "WAIVE", "R", "RETREAT",
}

# Spans that start with an order token but are format documentation, not orders.
# Kept as an explicit allowlist so a genuinely broken example cannot hide here.
_NOT_ORDERS = {
    "A", "F", "H", "S", "C", "R", "D", "B",
    "BUILD", "WAIVE", "HOLD", "SUPPORT", "CONVOY", "RETREAT", "DISBAND",
    "A (army)", "F (fleet)",
}

# `DEMO_UNITS` lists the units a demo player *controls* (`A BER`), not orders —
# a bare unit is correctly rejected ("missing order verb after unit at BER").
# It gets its own check below rather than an exemption, so a bad province code
# there still fails.
_POSITION_CONSTANTS = {"DEMO_UNITS"}

# Examples are sometimes shown behind the command that submits them, e.g.
# "`/orders 12 A BER - KIE`". The order is the part after the command and id.
_COMMAND_PREFIX_RE = re.compile(r"^/[a-z]+\s+(?:\d+\s+)?", re.IGNORECASE)


def _help_text_constants() -> dict[str, str]:
    """Every public string constant in `help_text`, i.e. everything a user sees."""
    return {
        name: value
        for name, value in vars(help_text).items()
        if not name.startswith("_") and isinstance(value, str)
    }


def _order_like_spans(text: str) -> list[str]:
    """Backtick-quoted spans in `text` that claim to be orders."""
    spans = []
    for raw in _CODE_SPAN_RE.findall(text):
        # `A PAR - BUR; F BRE - ENG` documents the multi-order separator.
        for candidate in raw.split(";"):
            candidate = _COMMAND_PREFIX_RE.sub("", candidate.strip()).strip()
            if not candidate or candidate in _NOT_ORDERS:
                continue
            first = candidate.split()[0].upper()
            if first in _ORDER_FIRST_TOKENS:
                spans.append(candidate)
    return spans


def _collect_orders() -> list[tuple[str, str]]:
    """`(constant_name, order_string)` for every order shown to a player."""
    found = [
        (name, order)
        for name, text in sorted(_help_text_constants().items())
        if name not in _POSITION_CONSTANTS
        for order in _order_like_spans(text)
    ]
    assert found, "extracted no orders from help_text — the extractor is broken"
    return found


HELP_TEXT_ORDERS = _collect_orders()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("constant", "order"),
    HELP_TEXT_ORDERS,
    ids=[f"{name}:{order}" for name, order in HELP_TEXT_ORDERS],
)
def test_every_documented_order_parses(constant: str, order: str) -> None:
    """An order the bot teaches must parse, or a new player hits a wall."""
    map_data = load_standard_map()
    try:
        parse_order(order, power="GERMANY", map=map_data)
    except OrderParseError as exc:
        pytest.fail(
            f"help_text.{constant} documents {order!r}, which the engine rejects: "
            f"{exc}. Use canonical 3-letter province codes and `A`/`F` for the "
            f"unit kind (see help_text.py's module docstring)."
        )


@pytest.mark.unit
def test_help_text_teaches_no_full_province_names() -> None:
    """Guard the specific regression: `A Berlin - Kiel` instead of `A BER - KIE`.

    Track G1's decision was **codes only** — 26 of the map's province names are
    multi-word (`English Channel`, `Gulf of Bothnia`) and the order grammar
    tokenizes on whitespace, so supporting single-word names alone would make
    `A Burgundy - Ruhr` work while `F English Channel - NTH` failed. A parse check
    alone would not catch a *new* full name that happens to be a valid alias
    (`A baltic - BER` parses), so assert the shape of the text too.
    """
    offenders = [
        (name, order)
        for name, order in HELP_TEXT_ORDERS
        # A mixed-case province token (`Berlin`) rather than a code (`BER`).
        if re.search(r"\b[A-Z][a-z]{2,}\b", order)
    ]
    assert not offenders, (
        "help text uses full province names, which do not parse: "
        + ", ".join(f"help_text.{n}: {o!r}" for n, o in offenders)
    )


@pytest.mark.unit
def test_help_text_does_not_mention_army_fleet_long_forms() -> None:
    """`ARMY`/`FLEET` are rejected by the grammar; three help blocks claimed otherwise.

    Verbs *do* have long forms (`HOLD`, `SUPPORT`, `CONVOY`, `RETREAT`,
    `DISBAND`), so the fix is not "delete all long forms" — it is to stop
    listing the unit kinds among them.

    The check bans the words outright rather than trying to tell an endorsement
    ("or full names: `ARMY`, `FLEET`") from a disclaimer ("`ARMY` is not
    accepted"), because that distinction is not mechanically decidable and the
    help text does not need to name a spelling it won't accept.
    """
    for name, text in sorted(_help_text_constants().items()):
        for bad in ("ARMY", "FLEET"):
            assert bad not in text, (
                f"help_text.{name} mentions {bad!r}, but parse_order rejects it "
                f"with \"expected unit kind 'A' or 'F'\""
            )


@pytest.mark.unit
def test_position_constants_name_real_provinces() -> None:
    """`DEMO_UNITS` isn't parseable as orders, but its province codes must be real."""
    map_data = load_standard_map()
    for name in sorted(_POSITION_CONSTANTS):
        text = _help_text_constants()[name]
        spans = _CODE_SPAN_RE.findall(text)
        assert spans, f"help_text.{name} has no code spans — is it still a unit list?"
        for span in spans:
            kind, _, province = span.partition(" ")
            assert kind in ("A", "F"), (
                f"help_text.{name} shows unit kind {kind!r}; parse_order accepts "
                f"only 'A' or 'F'"
            )
            assert province in map_data.provinces, (
                f"help_text.{name} names province {province!r}, which is not on the board"
            )


# The "### Order syntax" fenced block in the command reference, whose lines are
# "<order><2+ spaces><English gloss>".
_COMMANDS_DOC = Path(__file__).resolve().parent.parent / "docs" / "TELEGRAM_BOT_COMMANDS.md"


def _documented_reference_orders() -> list[str]:
    text = _COMMANDS_DOC.read_text(encoding="utf-8")
    _, _, after = text.partition("### Order syntax")
    block, _, _ = after.partition("```")[2].partition("```")
    orders = []
    for line in block.splitlines():
        order = re.split(r"\s{2,}", line.strip())[0].strip()
        if order:
            orders.append(order)
    return orders


@pytest.mark.unit
def test_command_reference_order_syntax_parses() -> None:
    """`docs/TELEGRAM_BOT_COMMANDS.md` teaches order syntax too — hold it to the same bar.

    G1 called this file suspect because E3 had already caught it misdescribing
    `/join` and `/order`. Its syntax block is correct today; this pins it there.
    """
    map_data = load_standard_map()
    orders = _documented_reference_orders()
    assert len(orders) >= 8, f"only found {orders} — the doc's syntax block moved"
    for order in orders:
        try:
            parse_order(order, power="GERMANY", map=map_data)
        except OrderParseError as exc:
            pytest.fail(
                f"{_COMMANDS_DOC.name}'s order-syntax block documents {order!r}, "
                f"which the engine rejects: {exc}"
            )


@pytest.mark.unit
def test_extractor_would_catch_a_bad_example() -> None:
    """Meta-test: the extractor must actually flag the syntax G1 found.

    Without this, a silently-broken extractor would make every assertion above
    vacuously green — which is exactly how the original bug survived.
    """
    regressed = "*Example:*\n• `A Berlin - Kiel` (Army move)\n• `/selectunit`\n"
    assert _order_like_spans(regressed) == ["A Berlin - Kiel"]

    map_data = load_standard_map()
    with pytest.raises(OrderParseError):
        parse_order("A Berlin - Kiel", power="GERMANY", map=map_data)
