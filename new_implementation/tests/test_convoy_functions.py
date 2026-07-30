"""
Tests for convoy-related functions in the Telegram bot.

This module tests ``show_convoy_options`` and ``show_convoy_destinations``.
Rewritten for v2.7.22: both functions are now driven entirely by
``GET /games/{id}/legal_orders/{power}`` (``server.telegram_bot.orders.api_get``)
rather than ``rendering.map.Map`` adjacency data, which the bot no longer
imports. ``resolve_game_and_power`` (used internally to find the caller's
power) fetches ``/users/{id}/games`` via a *separate* import
(``server.telegram_bot.game_context.api_get``), so tests patch both names.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import CallbackQuery, User

from server.telegram_bot.orders import show_convoy_options, show_convoy_destinations


@pytest.fixture
def mock_query():
    """Create a mock callback query for testing."""
    query = Mock(spec=CallbackQuery)
    query.edit_message_text = AsyncMock()
    query.from_user = Mock(spec=User)
    query.from_user.id = 12345
    return query


@pytest.fixture
def mock_context():
    context = Mock()
    context.user_data = {}
    return context


@pytest.fixture
def user_games():
    return {"games": [{"game_id": "test_game_1", "power": "ENGLAND"}]}


@pytest.fixture
def fleet_legal_orders():
    """A fleet at NTH with a Hold/Move plus two convoyable armies (LON, EDI),
    each with two possible destinations -- i.e. a bucket that mixes
    non-convoy and convoy order strings, exactly the shape
    ``server.legal_orders.legal_orders_for_power`` produces."""
    return {
        "phase": "S1901M",
        "phase_type": "MOVEMENT",
        "power": "ENGLAND",
        "units": [{"kind": "F", "location": "NTH", "province": "NTH", "coast": None}],
        "orders_by_unit": {
            "F NTH": [
                "F NTH H",
                "F NTH - HOL",
                "F NTH C A LON - BEL",
                "F NTH C A LON - HOL",
                "F NTH C A EDI - BEL",
            ]
        },
        "orders": [
            "F NTH H", "F NTH - HOL",
            "F NTH C A LON - BEL", "F NTH C A LON - HOL", "F NTH C A EDI - BEL",
        ],
    }


@pytest.mark.unit
@pytest.mark.telegram
class TestShowConvoyOptions:
    """Tests for show_convoy_options function."""

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_options_with_adjacent_armies(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games, fleet_legal_orders
    ):
        """Convoy options are grouped by origin army, one button per origin."""
        mock_ctx_get.return_value = user_games
        mock_orders_get.return_value = fleet_legal_orders

        await show_convoy_options(mock_query, mock_context, "test_game_1", "F NTH")

        # `assert_any_call`, not `assert_called_once_with`: the interactive flow now
        # also fetches province display names once per process (G2).
        mock_orders_get.assert_any_call("/games/test_game_1/legal_orders/ENGLAND")
        mock_query.edit_message_text.assert_called_once()
        kwargs = mock_query.edit_message_text.call_args.kwargs
        button_texts = [btn.text for row in kwargs["reply_markup"].inline_keyboard for btn in row]
        assert any("LON" in t for t in button_texts)
        assert any("EDI" in t for t in button_texts)

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_options_no_convoy_orders(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games
    ):
        """A unit whose bucket has no 'C' entries reports no convoy options."""
        mock_ctx_get.return_value = user_games
        mock_orders_get.return_value = {
            "phase_type": "MOVEMENT", "power": "ENGLAND",
            "units": [], "orders_by_unit": {"F NWG": ["F NWG H"]}, "orders": ["F NWG H"],
        }

        await show_convoy_options(mock_query, mock_context, "test_game_1", "F NWG")

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args[0][0]
        assert "No convoy options" in call_args

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_options_unknown_unit(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games, fleet_legal_orders
    ):
        """A unit key absent from orders_by_unit degrades to a clear message."""
        mock_ctx_get.return_value = user_games
        mock_orders_get.return_value = fleet_legal_orders

        await show_convoy_options(mock_query, mock_context, "test_game_1", "F BAL")

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args[0][0]
        assert "No convoy options" in call_args

    @pytest.mark.asyncio
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_options_user_not_in_game(self, mock_ctx_get, mock_query, mock_context):
        """If the caller can't be resolved to a power, fail gracefully with a message."""
        mock_ctx_get.return_value = {"games": []}

        await show_convoy_options(mock_query, mock_context, "test_game_1", "F NTH")

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args[0][0]
        assert "not in game test_game_1" in call_args


@pytest.mark.unit
@pytest.mark.telegram
class TestShowConvoyDestinations:
    """Tests for show_convoy_destinations function."""

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_destinations_with_valid_destinations(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games, fleet_legal_orders
    ):
        """Destinations are filtered to the chosen origin and cached under a
        short ord|game_id|idx callback (never the full order text)."""
        mock_ctx_get.return_value = user_games
        mock_orders_get.return_value = fleet_legal_orders

        await show_convoy_destinations(mock_query, mock_context, "test_game_1", "F NTH", "LON")

        mock_query.edit_message_text.assert_called_once()
        cached = mock_context.user_data["pending_orders"]["test_game_1"]
        assert cached == ["F NTH C A LON - BEL", "F NTH C A LON - HOL"]

        kwargs = mock_query.edit_message_text.call_args.kwargs
        for row in kwargs["reply_markup"].inline_keyboard:
            for btn in row:
                if btn.callback_data.startswith("ord|"):
                    assert len(btn.callback_data.encode("utf-8")) <= 64

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_destinations_no_matching_origin(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games, fleet_legal_orders
    ):
        mock_ctx_get.return_value = user_games
        mock_orders_get.return_value = fleet_legal_orders

        await show_convoy_destinations(mock_query, mock_context, "test_game_1", "F NTH", "SEV")

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args[0][0]
        assert "No convoy destinations" in call_args

    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.game_context.api_get')
    async def test_show_convoy_destinations_exception_handling(
        self, mock_ctx_get, mock_orders_get, mock_query, mock_context, user_games
    ):
        mock_ctx_get.return_value = user_games
        mock_orders_get.side_effect = Exception("Test error")

        await show_convoy_destinations(mock_query, mock_context, "test_game_1", "F NTH", "LON")

        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args[0][0]
        assert "error" in call_args.lower()


@pytest.mark.integration
@pytest.mark.telegram
class TestConvoyFunctionsIntegration:
    """Integration tests for convoy functions with a real API server."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires running API server")
    async def test_convoy_options_with_real_game(self):
        """Test convoy options with a real game state (requires API server)."""
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires running API server")
    async def test_convoy_destinations_with_real_game(self):
        """Test convoy destinations with a real game state (requires API server)."""
        pass
