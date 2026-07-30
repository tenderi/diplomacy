"""Support orders must not flood the first-level order menu (G4).

`show_possible_moves` used to render **one button per row for every direct
order**, and supports counted as direct. Convoys had already been split into a
sub-menu precisely because "an open-water fleet's bucket can contain a full cross
product of origin/destination convoy pairs, which would otherwise dominate the
menu" (orders.py's own docstring) — but supports are the same cross product and
were left inline, and there are usually more of them. A central army neighbouring
several units produced 20-30 buttons in a single message.

Supports now go behind "🤝 Support options", grouped by the province being
supported (`show_support_options`), then narrowed to hold-vs-move
(`show_support_choices`), reusing the `cvopt|`/`cvorig|` shape with its own
`supopt|`/`suporig|` namespace.

The load-bearing assertions here are about **bounds**: the first-level menu size
must depend on the board, not on how crowded the position is.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.orders import (
    show_possible_moves,
    show_support_choices,
    show_support_options,
)

pytestmark = pytest.mark.unit

TELEGRAM_CALLBACK_DATA_LIMIT = 64


def _crowded_bucket() -> list[str]:
    """A BER's bucket in a busy mid-game position: 2 moves, 24 supports, 1 hold.

    Six neighbouring units, each supportable holding plus three destinations.
    This is the shape that produced the unbounded menu.

    **Deliberately emitted in an unhelpful order** — destinations descending, the
    support-hold *after* the moves — so that `show_support_choices`' own sort is
    load-bearing. With a pre-sorted fixture, the cache/label alignment assertions
    in `test_support_choices_caches_exactly_the_orders_it_offers` pass whether or
    not the sort happens, i.e. they assert nothing. `legal_orders` makes no
    ordering promise, so this is also the more honest input.
    """
    bucket = ["A BER H", "A BER - SIL", "A BER - PRU"]
    for target in ("MUN", "KIE", "PRU", "SIL", "WAR", "BOH"):
        for dest in ("TYR", "GAL", "DEN"):
            bucket.append(f"A BER S A {target} - {dest}")
        bucket.append(f"A BER S A {target}")
    return bucket


def _legal_orders(bucket: list[str], unit_key: str, power: str = "GERMANY") -> dict:
    kind, _, location = unit_key.partition(" ")
    province, _, coast = location.partition("/")
    return {
        "phase": "S1901M",
        "phase_type": "MOVEMENT",
        "power": power,
        "units": [{
            "kind": kind,
            "location": location,
            "province": province,
            "coast": coast or None,
        }],
        "orders_by_unit": {unit_key: bucket},
        "orders": list(bucket),
    }


class _Harness:
    """A mock callback query plus the two `api_get` references that must be patched.

    `game_context.api_get` serves `resolve_game_and_power`; `orders.api_get`
    serves `/games/{id}/legal_orders/{power}`. Patching only one leaves the other
    making a real, failing network call.
    """

    def __init__(self) -> None:
        self.context = Mock()
        self.context.user_data = {}
        self.query = Mock()
        self.query.edit_message_text = AsyncMock()
        self.query.answer = AsyncMock()
        user = Mock()
        user.id = 12345
        self.query.from_user = user

    def keyboard(self) -> list[list]:
        markup = self.query.edit_message_text.call_args.kwargs["reply_markup"]
        return markup.inline_keyboard

    def labels(self) -> list[str]:
        return [btn.text for row in self.keyboard() for btn in row]

    def callbacks(self) -> list[str]:
        return [btn.callback_data for row in self.keyboard() for btn in row]

    def text(self) -> str:
        return self.query.edit_message_text.call_args.args[0]


def _run(coro_fn, harness: _Harness, bucket: list[str], unit_key: str, *args) -> None:
    """Drive one menu function. `unit_key` is both the bucket key and the argument."""
    games = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    legal = _legal_orders(bucket, unit_key)
    with patch("server.telegram_bot.game_context.api_get", return_value=games), \
         patch("server.telegram_bot.orders.api_get", return_value=legal):
        asyncio.run(coro_fn(harness.query, harness.context, "1", unit_key, *args))


def test_first_level_menu_is_bounded_with_many_supports() -> None:
    """The G4 regression: 27 legal orders must not become 27 buttons."""
    bucket = _crowded_bucket()
    assert len([o for o in bucket if o.split()[2] == "S"]) == 24, "fixture drifted"

    h = _Harness()
    _run(show_possible_moves, h, bucket, "A BER")

    labels = h.labels()
    # hold + 2 moves + support submenu + cancel. No convoys in this bucket.
    assert len(labels) == 5, labels
    assert not any(" S " in label for label in labels), (
        f"a support order leaked into the first-level menu: {labels}"
    )
    assert any(label.startswith("🤝 Support options") for label in labels), labels
    assert any("A BER H" in label for label in labels)
    assert any("A BER - SIL" in label for label in labels)


def test_first_level_menu_size_does_not_grow_with_the_position() -> None:
    """Bounded means bounded: doubling the supports must not add a single button.

    This is the assertion that would have failed before G4 and that a naive
    "just cap the list at 20" fix would also fail.
    """
    small = ["A BER H", "A BER - SIL", "A BER S A MUN"]
    huge = _crowded_bucket()

    h_small, h_huge = _Harness(), _Harness()
    _run(show_possible_moves, h_small, small, "A BER")
    _run(show_possible_moves, h_huge, huge, "A BER")

    # small: hold + 1 move + support submenu + cancel = 4
    assert len(h_small.labels()) == 4, h_small.labels()
    # huge has 8x the supports but only one extra *move*
    assert len(h_huge.labels()) == len(h_small.labels()) + 1, (
        f"menu grew with the position: {h_small.labels()} vs {h_huge.labels()}"
    )


def test_no_support_submenu_button_when_there_are_no_supports() -> None:
    h = _Harness()
    _run(show_possible_moves, h, ["A BER H", "A BER - SIL"], "A BER")
    labels = h.labels()
    assert not any("Support options" in label for label in labels), labels
    assert len(labels) == 3, labels


def test_support_options_groups_by_supported_province() -> None:
    """First sub-level: one button per neighbour, not per (neighbour, destination)."""
    h = _Harness()
    _run(show_support_options, h, _crowded_bucket(), "A BER")

    labels = h.labels()
    targets = [label for label in labels if label.startswith("🎯 ")]
    assert sorted(targets) == [
        "🎯 BOH", "🎯 KIE", "🎯 MUN", "🎯 PRU", "🎯 SIL", "🎯 WAR",
    ], labels
    # 6 targets + cancel; the 24 orders collapse to 6 buttons.
    assert len(labels) == 7, labels


def test_support_submenu_callbacks_carry_provinces_not_order_text() -> None:
    """Callback payloads must stay inside Telegram's 64-byte `callback_data` cap.

    The index-into-cache scheme exists for exactly this reason; carrying order
    text here is what it is there to prevent.
    """
    h = _Harness()
    _run(show_support_options, h, _crowded_bucket(), "A BER")

    for cb in h.callbacks():
        assert len(cb.encode("utf-8")) <= TELEGRAM_CALLBACK_DATA_LIMIT, cb
    for cb in h.callbacks():
        if cb.startswith("suporig|"):
            _, game_id, unit_key, target = cb.split("|", 3)
            assert game_id == "1"
            assert unit_key == "A BER"
            assert " S " not in target, f"order text leaked into callback_data: {cb}"


def test_support_choices_distinguishes_hold_from_move() -> None:
    """Second sub-level: `S A MUN` and `S A MUN - DEN` must not read alike.

    Flattening them into identical-looking labels would rebuild the original
    problem one level down — the player could not tell which button did what.
    """
    h = _Harness()
    _run(show_support_choices, h, _crowded_bucket(), "A BER", "MUN")

    labels = [label for label in h.labels() if label != "❌ Cancel"]
    assert labels[0] == "🛡️ supports holding", labels
    assert sorted(labels[1:]) == [
        "➡️ supports move to DEN", "➡️ supports move to GAL", "➡️ supports move to TYR",
    ], labels
    assert len(set(labels)) == len(labels), f"duplicate labels: {labels}"


def test_support_choices_caches_exactly_the_orders_it_offers() -> None:
    """The `ord|` indices must resolve to the orders shown, in the same order.

    `show_support_choices` re-sorts (hold first, then destinations) *before*
    caching. If it cached the unsorted list, every button would submit the wrong
    order — silently, since all of them are legal.
    """
    h = _Harness()
    _run(show_support_choices, h, _crowded_bucket(), "A BER", "MUN")

    cached = h.context.user_data["pending_orders"]["1"]
    assert cached == [
        "A BER S A MUN",
        "A BER S A MUN - DEN",
        "A BER S A MUN - GAL",
        "A BER S A MUN - TYR",
    ], cached

    indices = [
        int(cb.split("|")[2]) for cb in h.callbacks() if cb.startswith("ord|")
    ]
    assert indices == list(range(len(cached))), indices
    # And the label at each index describes the order cached at that index.
    for idx, cb_label in zip(indices, [label for label in h.labels() if label != "❌ Cancel"]):
        order = cached[idx]
        if "supports holding" in cb_label:
            assert len(order.split()) == 5, order
        else:
            assert order.split()[6] in cb_label, (cb_label, order)


def test_support_choices_rejects_an_unknown_target() -> None:
    h = _Harness()
    _run(show_support_choices, h, _crowded_bucket(), "A BER", "PAR")
    assert "No support options found" in h.text()


def test_support_options_with_no_supports_reports_cleanly() -> None:
    h = _Harness()
    _run(show_support_options, h, ["A BER H", "A BER - SIL"], "A BER")
    assert "No support options found" in h.text()


def test_split_coast_supported_fleet_keeps_its_coast() -> None:
    """A supported fleet on a named coast must round-trip verbatim.

    `_support_target` returns `"BUL/SC"`, and the order string posted back has to
    match what `legal_orders` produced — the coast is part of the order, not
    decoration.
    """
    bucket = ["F AEG H", "F AEG S F BUL/SC", "F AEG S F BUL/SC - CON"]
    h = _Harness()
    _run(show_support_options, h, bucket, "F AEG")
    assert "🎯 BUL/SC" in h.labels(), h.labels()

    h2 = _Harness()
    _run(show_support_choices, h2, bucket, "F AEG", "BUL/SC")
    cached = h2.context.user_data["pending_orders"]["1"]
    assert cached == ["F AEG S F BUL/SC", "F AEG S F BUL/SC - CON"], cached
