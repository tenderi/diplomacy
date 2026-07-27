#!/usr/bin/env python3
"""
Tests for the interactive order selection flow in the Telegram bot
(``/selectunit`` -> ``show_possible_moves`` -> ``submit_interactive_order``).

Rewritten for the phase-aware, ``legal_orders``-driven implementation
(v2.7.22): the bot no longer imports ``rendering.map.Map`` or adjacency
data -- everything is sourced from ``GET /games/{id}/legal_orders/{power}``,
which returns fully-formed canonical order strings per unit.

Two separate ``api_get`` references matter here:
- ``server.telegram_bot.game_context.api_get`` -- used by
  ``resolve_game_and_power`` to fetch ``/users/{id}/games``.
- ``server.telegram_bot.orders.api_get`` -- used directly by orders.py for
  ``/games/{id}/legal_orders/{power}``.
Both must be patched independently; patching only one leaves the other
making a real (failing) network call.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.orders import (
    normalize_order_provinces,
    selectunit,
    show_possible_moves,
    submit_interactive_order,
)

pytestmark = pytest.mark.unit


def _movement_legal_orders(power: str = "GERMANY") -> dict:
    return {
        "phase": "S1901M",
        "phase_type": "MOVEMENT",
        "power": power,
        "units": [
            {"kind": "A", "location": "BER", "province": "BER", "coast": None},
            {"kind": "A", "location": "MUN", "province": "MUN", "coast": None},
            {"kind": "F", "location": "KIE", "province": "KIE", "coast": None},
        ],
        "orders_by_unit": {
            "A BER": ["A BER H", "A BER - SIL", "A BER - PRU"],
            "A MUN": ["A MUN H", "A MUN - SIL"],
            "F KIE": ["F KIE H", "F KIE - DEN", "F KIE - HOL"],
        },
        "orders": [
            "A BER H", "A BER - SIL", "A BER - PRU",
            "A MUN H", "A MUN - SIL",
            "F KIE H", "F KIE - DEN", "F KIE - HOL",
        ],
    }


class TestInteractiveOrderInput:
    """Test suite for the interactive order input flow."""

    def setup_method(self):
        self.mock_update = Mock()
        self.mock_context = Mock()
        self.mock_context.user_data = {}
        self.mock_context.args = None

        self.mock_query = Mock()
        self.mock_query.edit_message_text = AsyncMock()
        self.mock_query.answer = AsyncMock()
        self.mock_message = Mock()

        self.mock_user = Mock()
        self.mock_user.id = 12345
        self.mock_user.full_name = "Test User"

        self.mock_update.effective_user = self.mock_user
        self.mock_update.message = self.mock_message
        self.mock_update.callback_query = None
        self.mock_message.reply_text = AsyncMock()

        self.mock_query.from_user = self.mock_user

        self.sample_user_games = {"games": [{"game_id": 1, "power": "GERMANY"}]}

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_selectunit_single_game_success(self, mock_ctx_get, mock_orders_get):
        """selectunit resolves the sole game and shows one button per unit."""
        mock_ctx_get.return_value = self.sample_user_games
        mock_orders_get.return_value = _movement_legal_orders()

        asyncio.run(selectunit(self.mock_update, self.mock_context))

        mock_ctx_get.assert_called_once_with("/users/12345/games")
        mock_orders_get.assert_called_once_with("/games/1/legal_orders/GERMANY")

        self.mock_message.reply_text.assert_called_once()
        args, kwargs = self.mock_message.reply_text.call_args
        assert kwargs["reply_markup"] is not None

    @patch('server.telegram_bot.game_context.api_get')
    def test_selectunit_no_games(self, mock_ctx_get):
        mock_ctx_get.return_value = {"games": []}

        asyncio.run(selectunit(self.mock_update, self.mock_context))

        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "not in any games" in call_args

    @patch('server.telegram_bot.game_context.api_get')
    def test_selectunit_multiple_games(self, mock_ctx_get):
        mock_ctx_get.return_value = {
            "games": [
                {"game_id": 1, "power": "GERMANY"},
                {"game_id": 2, "power": "FRANCE"},
            ]
        }

        asyncio.run(selectunit(self.mock_update, self.mock_context))

        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "You're in 2 games" in call_args

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_selectunit_no_units(self, mock_ctx_get, mock_orders_get):
        mock_ctx_get.return_value = self.sample_user_games
        mock_orders_get.return_value = {
            "phase": "S1901M", "phase_type": "MOVEMENT", "power": "GERMANY",
            "units": [], "orders_by_unit": {}, "orders": [],
        }

        asyncio.run(selectunit(self.mock_update, self.mock_context))

        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "No units require" in call_args

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_show_possible_moves_army(self, mock_ctx_get, mock_orders_get):
        """show_possible_moves lists an army's non-convoy orders_by_unit bucket."""
        mock_ctx_get.return_value = self.sample_user_games
        mock_orders_get.return_value = _movement_legal_orders()

        asyncio.run(show_possible_moves(self.mock_query, self.mock_context, "1", "A BER"))

        mock_orders_get.assert_called_once_with("/games/1/legal_orders/GERMANY")
        self.mock_query.edit_message_text.assert_called_once()
        cached = self.mock_context.user_data["pending_orders"]["1"]
        assert cached == ["A BER H", "A BER - SIL", "A BER - PRU"]

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_show_possible_moves_fleet_with_convoy(self, mock_ctx_get, mock_orders_get):
        """A fleet with convoy entries in its bucket gets a 'Convoy options' button
        and only its non-convoy orders are cached directly."""
        data = _movement_legal_orders()
        data["orders_by_unit"]["F KIE"] = [
            "F KIE H", "F KIE - DEN", "F KIE C A BER - SWE",
        ]
        mock_ctx_get.return_value = self.sample_user_games
        mock_orders_get.return_value = data

        asyncio.run(show_possible_moves(self.mock_query, self.mock_context, "1", "F KIE"))

        self.mock_query.edit_message_text.assert_called_once()
        cached = self.mock_context.user_data["pending_orders"]["1"]
        assert cached == ["F KIE H", "F KIE - DEN"]
        kwargs = self.mock_query.edit_message_text.call_args.kwargs
        button_texts = [
            btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row
        ]
        assert any("Convoy options" in t for t in button_texts)

    @patch('server.telegram_bot.orders.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_submit_interactive_order_success(self, mock_ctx_get, mock_api_post):
        mock_ctx_get.return_value = self.sample_user_games
        mock_api_post.return_value = {"results": [{"success": True, "order": "A BER - SIL"}]}

        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - SIL"))

        mock_api_post.assert_called_once()
        call_args, call_kwargs = mock_api_post.call_args
        assert call_args[0] == "/games/set_orders"
        json_data = call_kwargs.get("json_data", call_args[1] if len(call_args) > 1 else None)
        assert json_data["game_id"] == "1"
        assert json_data["power"] == "GERMANY"
        assert json_data["orders"] == ["A BER - SIL"]

        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "Order Submitted Successfully!" in call_args

    @patch('server.telegram_bot.orders.api_post')
    @patch('server.telegram_bot.game_context.api_get')
    def test_submit_interactive_order_failure(self, mock_ctx_get, mock_api_post):
        mock_ctx_get.return_value = self.sample_user_games
        mock_api_post.return_value = {"results": [{"success": False, "error": "Invalid move"}]}

        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - INVALID"))

        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "Order Failed" in call_args
        assert "Invalid move" in call_args

    @patch('server.telegram_bot.game_context.api_get')
    def test_submit_interactive_order_user_not_in_game(self, mock_ctx_get):
        mock_ctx_get.return_value = {"games": []}

        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - SIL"))

        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "not in game 1" in call_args

    def test_normalize_order_provinces(self):
        result = normalize_order_provinces("A BER - SIL", "GERMANY")
        assert result == "A BER - SIL"

        result = normalize_order_provinces("A ber - sil", "GERMANY")
        assert result == "A BER - SIL"

        result = normalize_order_provinces("A Ber - Sil", "GERMANY")
        assert result == "A BER - SIL"

        result = normalize_order_provinces("A BER H", "GERMANY")
        assert result == "A BER H"

    def test_normalize_order_provinces_edge_cases(self):
        result = normalize_order_provinces("A INVALID - SIL", "GERMANY")
        assert "INVALID" in result

        result = normalize_order_provinces("", "GERMANY")
        assert result == ""

        result = normalize_order_provinces("A", "GERMANY")
        assert result == "A"

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_show_possible_moves_no_legal_orders(self, mock_ctx_get, mock_orders_get):
        """An unrecognized unit key (empty bucket) yields a clear error, not a crash."""
        mock_ctx_get.return_value = self.sample_user_games
        mock_orders_get.return_value = _movement_legal_orders()

        asyncio.run(show_possible_moves(self.mock_query, self.mock_context, "1", "A NOPE"))

        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "No legal orders found" in call_args

    def test_callback_data_uses_index_scheme(self):
        """The new scheme carries only a short index, never order text."""
        callback_data = "ord|1|2"
        _, game_id, idx_str = callback_data.split("|", 2)
        assert game_id == "1"
        assert int(idx_str) == 2
        assert len(callback_data.encode("utf-8")) <= 64


class TestInteractiveOrderIntegration:
    """Integration-style test for the complete select -> show -> submit flow."""

    @patch('server.telegram_bot.orders.api_post')
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    def test_complete_interactive_flow(self, mock_ctx_get, mock_orders_get, mock_api_post):
        mock_ctx_get.return_value = {"games": [{"game_id": 1, "power": "GERMANY"}]}
        mock_orders_get.return_value = _movement_legal_orders()
        mock_api_post.return_value = {"results": [{"success": True, "order": "A BER - SIL"}]}

        mock_query = Mock()
        mock_query.from_user = Mock()
        mock_query.from_user.id = 12345
        mock_query.edit_message_text = AsyncMock()

        mock_context = Mock()
        mock_context.user_data = {}

        # Step 1: show possible moves for A BER
        asyncio.run(show_possible_moves(mock_query, mock_context, "1", "A BER"))
        assert mock_context.user_data["pending_orders"]["1"] == [
            "A BER H", "A BER - SIL", "A BER - PRU"
        ]

        # Step 2: submit the cached order chosen by index 1 ("A BER - SIL")
        order_text = mock_context.user_data["pending_orders"]["1"][1]
        asyncio.run(submit_interactive_order(mock_query, "1", order_text))

        assert mock_api_post.call_count == 1
        mock_query.edit_message_text.assert_called()
        success_call = None
        for call in mock_query.edit_message_text.call_args_list:
            if "Order Submitted Successfully!" in str(call):
                success_call = call
                break
        assert success_call is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
