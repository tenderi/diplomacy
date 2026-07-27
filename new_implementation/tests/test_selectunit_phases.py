"""Phase-aware ``/selectunit`` and callback_data-scheme tests.

Covers the three ``phase_type`` branches ``/selectunit`` must handle
(MOVEMENT, RETREAT, ADJUSTMENT) and the ``ord|{game_id}|{idx}`` callback
scheme that replaced embedding full order text in ``callback_data`` (which
overflowed Telegram's 64-byte cap on coasted/convoy orders).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.orders import (
    resolve_pending_order,
    selectunit,
    show_convoy_destinations,
)

pytestmark = pytest.mark.unit


def _make_update_and_context(user_id: int = 12345):
    update = Mock()
    context = Mock()
    context.user_data = {}
    context.args = None

    message = Mock()
    message.reply_text = AsyncMock()
    user = Mock()
    user.id = user_id

    update.effective_user = user
    update.message = message
    update.callback_query = None
    return update, context, message


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_movement_phase(mock_ctx_get, mock_orders_get):
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "S1901M", "phase_type": "MOVEMENT", "power": "GERMANY",
        "units": [{"kind": "A", "location": "BER", "province": "BER", "coast": None}],
        "orders_by_unit": {"A BER": ["A BER H", "A BER - SIL"]},
        "orders": ["A BER H", "A BER - SIL"],
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "Select a unit for orders" in text
    kwargs = message.reply_text.call_args.kwargs
    # One button for the unit + one Cancel button.
    assert len(kwargs["reply_markup"].inline_keyboard) == 2
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "selunit|1|A BER"


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_retreat_phase(mock_ctx_get, mock_orders_get):
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "F1901R", "phase_type": "RETREAT", "power": "GERMANY",
        "units": [{"kind": "A", "location": "BER", "province": "BER", "coast": None}],
        "orders_by_unit": {"A BER": ["A BER R SIL", "A BER R PRU", "D A BER"]},
        "orders": ["A BER R SIL", "A BER R PRU", "D A BER"],
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "retreat/disband" in text
    kwargs = message.reply_text.call_args.kwargs
    assert kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "selunit|1|A BER"


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_retreat_phase_no_dislodged_units(mock_ctx_get, mock_orders_get):
    """A power with nothing dislodged sees a clear message, not an empty keyboard."""
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "F1901R", "phase_type": "RETREAT", "power": "GERMANY",
        "units": [], "orders_by_unit": {}, "orders": [],
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "No units require retreat" in text


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_adjustment_phase(mock_ctx_get, mock_orders_get):
    """ADJUSTMENT phase renders the delta/action/slots header verbatim from
    ``legal_orders``'s ``adjustment`` dict, and presents the flat order list --
    unlike MOVEMENT/RETREAT there is no per-unit selection step first."""
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "W1901A", "phase_type": "ADJUSTMENT", "power": "GERMANY",
        "units": [{"kind": "A", "location": "BER", "province": "BER", "coast": None}],
        "orders_by_unit": {"F BRE": ["BUILD F BRE"]},
        "orders": ["BUILD F BRE", "WAIVE"],
        "adjustment": {"delta": 1, "action": "build", "slots": 1},
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "Adjustment for GERMANY" in text
    assert "Delta: 1" in text
    assert "Action: build" in text
    assert "Slots: 1" in text


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_adjustment_phase_build(mock_ctx_get, mock_orders_get):
    """delta > 0: build/WAIVE candidates are shown directly, no per-unit step."""
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "W1901A", "phase_type": "ADJUSTMENT", "power": "GERMANY",
        "units": [{"kind": "A", "location": "BER", "province": "BER", "coast": None}],
        "orders_by_unit": {"F BRE": ["BUILD F BRE"], "A PAR": ["BUILD A PAR"]},
        "orders": ["BUILD A PAR", "BUILD F BRE", "WAIVE"],
        "adjustment": {"delta": 2, "action": "build", "slots": 2},
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "Adjustment" in text
    assert context.user_data["pending_orders"]["1"] == ["BUILD A PAR", "BUILD F BRE", "WAIVE"]
    kwargs = message.reply_text.call_args.kwargs
    # 3 orders + Cancel
    assert len(kwargs["reply_markup"].inline_keyboard) == 4


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_adjustment_phase_no_action_needed(mock_ctx_get, mock_orders_get):
    """delta == 0: no build/disband slots -- selectunit must show none, not crash."""
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "W1901A", "phase_type": "ADJUSTMENT", "power": "GERMANY",
        "units": [{"kind": "A", "location": "BER", "province": "BER", "coast": None}],
        "orders_by_unit": {}, "orders": [],
        "adjustment": {"delta": 0, "action": "none", "slots": 0},
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    text = message.reply_text.call_args[0][0]
    assert "No adjustment actions needed" in text
    assert "pending_orders" not in context.user_data


@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_selectunit_adjustment_phase_disband(mock_ctx_get, mock_orders_get):
    """delta < 0: disband candidates are exactly the player's units."""
    update, context, message = _make_update_and_context()
    mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
    mock_orders_get.return_value = {
        "phase": "W1901A", "phase_type": "ADJUSTMENT", "power": "GERMANY",
        "units": [
            {"kind": "A", "location": "BER", "province": "BER", "coast": None},
            {"kind": "A", "location": "MUN", "province": "MUN", "coast": None},
        ],
        "orders_by_unit": {"A BER": ["D A BER"], "A MUN": ["D A MUN"]},
        "orders": ["D A BER", "D A MUN"],
        "adjustment": {"delta": -1, "action": "disband", "slots": 1},
    }

    asyncio.run(selectunit(update, context))

    message.reply_text.assert_called_once()
    assert context.user_data["pending_orders"]["1"] == ["D A BER", "D A MUN"]


# ---------------------------------------------------------------------------
# callback_data byte-size + cache-resolution tests
# ---------------------------------------------------------------------------


def test_resolve_pending_order_hit():
    context = Mock()
    context.user_data = {"pending_orders": {"1": ["A BER H", "A BER - SIL"]}}
    assert resolve_pending_order(context, "1", 1) == "A BER - SIL"


def test_resolve_pending_order_missing_cache_returns_none():
    """No selection was ever cached for this game (or user_data got reset) -- must
    not raise, so the callback handler can show a clear expiry message."""
    context = Mock()
    context.user_data = {}
    assert resolve_pending_order(context, "1", 0) is None


def test_resolve_pending_order_stale_index_returns_none():
    context = Mock()
    context.user_data = {"pending_orders": {"1": ["A BER H"]}}
    assert resolve_pending_order(context, "1", 5) is None
    assert resolve_pending_order(context, "1", -1) is None


def test_resolve_pending_order_does_not_leak_across_games():
    """Two games in flight at once must not share (or clobber) each other's cache."""
    context = Mock()
    context.user_data = {
        "pending_orders": {
            "1": ["A BER H"],
            "2": ["A PAR H", "A PAR - BUR"],
        }
    }
    assert resolve_pending_order(context, "1", 0) == "A BER H"
    assert resolve_pending_order(context, "2", 1) == "A PAR - BUR"
    assert resolve_pending_order(context, "1", 1) is None


@pytest.mark.asyncio
@patch("server.telegram_bot.orders.api_get")
@patch("server.telegram_bot.game_context.api_get")
async def test_callback_data_under_64_bytes_for_coasted_convoy_order(mock_ctx_get, mock_orders_get):
    """The scenario the pre-rewrite scheme broke: a long, coast-qualified convoy
    order must not appear in callback_data at all -- only a short index does.
    """
    long_order = "F STP/SC C A WAR - LVN"  # a coasted-fleet convoy order, ~22 chars
    assert len(long_order) < 64  # sanity: even embedded whole it *could* have fit here...
    # ...but the old scheme also concatenated game_id/fleet/army/power/dest on
    # top of the order shape, which is what actually overflowed. The fix is
    # structural (never embed order text), so verify that directly instead of
    # relying on a single string being long enough to prove the point.
    mock_ctx_get.return_value = {"games": [{"game_id": 123456, "power": "RUSSIA"}]}
    mock_orders_get.return_value = {
        "phase": "S1901M", "phase_type": "MOVEMENT", "power": "RUSSIA",
        "units": [{"kind": "F", "location": "STP/SC", "province": "STP", "coast": "SC"}],
        "orders_by_unit": {"F STP/SC": [long_order, "F STP/SC C A WAR - PRU"]},
        "orders": [long_order, "F STP/SC C A WAR - PRU"],
    }

    query = Mock()
    query.from_user = Mock()
    query.from_user.id = 12345
    query.edit_message_text = AsyncMock()
    context = Mock()
    context.user_data = {}

    await show_convoy_destinations(query, context, "123456", "F STP/SC", "WAR")

    query.edit_message_text.assert_called_once()
    kwargs = query.edit_message_text.call_args.kwargs
    for row in kwargs["reply_markup"].inline_keyboard:
        for btn in row:
            assert len(btn.callback_data.encode("utf-8")) <= 64
            if btn.callback_data.startswith("ord|"):
                assert long_order not in btn.callback_data

    # And the full order text is retrievable back out of the cache by index.
    cached = context.user_data["pending_orders"]["123456"]
    assert long_order in cached
