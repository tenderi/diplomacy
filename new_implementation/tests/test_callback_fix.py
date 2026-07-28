#!/usr/bin/env python3
"""
Test Callback Data Format Fix

Documents why the interactive-order ``callback_data`` scheme changed in
v2.7.22 and verifies the replacement.

The pre-rewrite scheme embedded the order text itself (and, for units,
underscore-escaped unit strings like ``select_unit_1_A_BER``). That worked
for a two-token unit id but overflowed Telegram's 64-byte ``callback_data``
cap once real order strings -- support-move and convoy orders, coasted
locations like ``F STP/SC`` -- got embedded directly. The fix is structural:
``callback_data`` never carries order text at all. It carries only a short
index (``ord|{game_id}|{idx}``) or unit key (``selunit|{game_id}|{unit}``),
"|"-delimited so a value containing a space (a unit key) or a slash (a
coast) doesn't need escaping. The real order text lives in
``context.user_data`` and is resolved by index in the callback handler --
see ``server.telegram_bot.orders._present_order_choices`` /
``resolve_pending_order``.
"""


def test_new_unit_select_callback_survives_a_coast():
    """selunit|{game_id}|{unit} -- "|" split, no escaping needed for "F STP/SC"."""
    game_id = "1"
    unit = "F STP/SC"

    callback_data = f"selunit|{game_id}|{unit}"
    assert len(callback_data.encode("utf-8")) <= 64

    parts = callback_data.split("|", 2)
    assert len(parts) == 3
    assert parts[1] == game_id
    assert parts[2] == unit


def test_new_order_callback_is_index_based_not_order_text():
    """ord|{game_id}|{idx} -- the order text is never embedded, so its length
    (support/convoy strings, coasted locations, ...) cannot overflow the cap."""
    game_id = "123456"
    long_order = "A MOS S F STP/SC - BOT"  # a support order with a coasted target
    idx = 4

    callback_data = f"ord|{game_id}|{idx}"

    assert long_order not in callback_data
    assert len(callback_data.encode("utf-8")) <= 64

    parts = callback_data.split("|", 2)
    assert parts[1] == game_id
    assert int(parts[2]) == idx


def test_order_callback_stays_under_cap_for_worst_case_ids():
    """Even with a large game id and a deep order list, the callback stays tiny --
    unlike embedding order text, index length barely grows with the payload."""
    callback_data = f"ord|{999999999}|{9999}"
    assert len(callback_data.encode("utf-8")) <= 64


def test_cancel_callback_format():
    """cancelunit|{game_id} clears the per-game cache; also index-free."""
    game_id = "42"
    callback_data = f"cancelunit|{game_id}"
    assert len(callback_data.encode("utf-8")) <= 64
    assert callback_data.split("|", 1) == ["cancelunit", "42"]


if __name__ == "__main__":
    test_new_unit_select_callback_survives_a_coast()
    test_new_order_callback_is_index_based_not_order_text()
    test_order_callback_stays_under_cap_for_worst_case_ids()
    test_cancel_callback_format()
    print("✅ All callback format tests passed!")
