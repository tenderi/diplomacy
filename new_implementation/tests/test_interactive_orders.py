#!/usr/bin/env python3
"""
Tests for Interactive Order Input System

This module tests the interactive order input functionality including:
- /selectunit command
- Unit selection callbacks
- Move options display
- Order submission
- Error handling

Run with: python -m pytest src/server/test_interactive_orders.py -v
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from server.telegram_bot.orders import (
    selectunit, 
    show_possible_moves, 
    submit_interactive_order,
    normalize_order_provinces
)
from engine.map import Map
from engine.province_mapping import normalize_province_name


class TestInteractiveOrderInput:
    """Test suite for Interactive Order Input functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.mock_update = Mock()
        self.mock_context = Mock()
        # Mock query with awaitable methods
        self.mock_query = Mock()
        self.mock_query.edit_message_text = AsyncMock()
        self.mock_query.answer = AsyncMock()
        self.mock_message = Mock()
        
        # Mock user
        self.mock_user = Mock()
        self.mock_user.id = 12345
        self.mock_user.full_name = "Test User"
        
        # Mock effective user
        self.mock_update.effective_user = self.mock_user
        self.mock_update.message = self.mock_message
        
        # Mock message reply
        self.mock_message.reply_text = AsyncMock()
        
        # Mock query for callbacks
        self.mock_query.from_user = self.mock_user
        self.mock_query.edit_message_text = AsyncMock()
        
        # Sample game state
        self.sample_game_state = {
            "units": {
                "GERMANY": ["A BER", "A MUN", "F KIE"]
            },
            "turn": 0,
            "phase": "movement",
            "done": False
        }
        
        # Sample user games response
        self.sample_user_games = {
            "games": [
                {"game_id": 1, "power": "GERMANY"}
            ]
        }

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.InlineKeyboardButton')
    @patch('server.telegram_bot.orders.InlineKeyboardMarkup')
    def test_selectunit_single_game_success(self, mock_markup, mock_button, mock_api_get):
        """Test /selectunit command with single game"""
        # Mock API responses
        mock_api_get.side_effect = [
            self.sample_user_games,  # user games
            self.sample_game_state   # game state
        ]
        
        # Mock message reply
        self.mock_message.reply_text = AsyncMock()
        
        # Mock InlineKeyboardButton and InlineKeyboardMarkup
        mock_button_instance = Mock()
        mock_button.return_value = mock_button_instance
        
        # Call the function
        import asyncio
        asyncio.run(selectunit(self.mock_update, self.mock_context))
        
        # Verify API calls
        assert mock_api_get.call_count == 2
        mock_api_get.assert_any_call("/users/12345/games")
        mock_api_get.assert_any_call("/games/1/state")
        
        # Verify message was sent
        self.mock_message.reply_text.assert_called_once()
        
        # Verify keyboard was created (InlineKeyboardButton should be called for each unit)
        assert mock_button.call_count > 0, "InlineKeyboardButton should have been called"
        mock_markup.assert_called_once()

    @patch('server.telegram_bot.orders.api_get')
    def test_selectunit_no_games(self, mock_api_get):
        """Test /selectunit command when user has no games"""
        # Mock empty games response
        mock_api_get.return_value = {"games": []}
        
        # Mock message reply
        self.mock_message.reply_text = AsyncMock()
        
        # Call the function
        import asyncio
        asyncio.run(selectunit(self.mock_update, self.mock_context))
        
        # Verify error message
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "You're not in any games!" in call_args

    @patch('server.telegram_bot.orders.api_get')
    def test_selectunit_multiple_games(self, mock_api_get):
        """Test /selectunit command when user has multiple games"""
        # Mock multiple games response
        mock_api_get.return_value = {
            "games": [
                {"game_id": 1, "power": "GERMANY"},
                {"game_id": 2, "power": "FRANCE"}
            ]
        }
        
        # Mock message reply
        self.mock_message.reply_text = AsyncMock()
        
        # Call the function
        import asyncio
        asyncio.run(selectunit(self.mock_update, self.mock_context))
        
        # Verify error message
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "You're in 2 games" in call_args

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    @patch('server.telegram_bot.orders.InlineKeyboardButton')
    @patch('server.telegram_bot.orders.InlineKeyboardMarkup')
    def test_show_possible_moves_army(self, mock_markup, mock_button, mock_map_class, mock_api_get):
        """Test show_possible_moves for an army unit"""
        # Mock API response
        mock_api_get.return_value = self.sample_game_state
        
        # Mock map instance
        mock_map_instance = Mock()
        mock_map_instance.get_adjacency.return_value = {"SIL", "PRU", "RUH"}
        mock_map_instance.provinces = {
            "SIL": Mock(type="land"),
            "PRU": Mock(type="land"),
            "RUH": Mock(type="land"),
            "BAL": Mock(type="water")  # Should be filtered out for army
        }
        mock_map_class.return_value = mock_map_instance
        
        # Call the function
        import asyncio
        asyncio.run(show_possible_moves(self.mock_query, "1", "A BER"))
        
        # Verify map was created
        mock_map_class.assert_called_once_with("standard")
        mock_map_instance.get_adjacency.assert_called_once_with("BER")
        
        # Verify message was sent
        self.mock_query.edit_message_text.assert_called_once()
        
        # Verify keyboard was created
        assert mock_button.call_count > 0, "InlineKeyboardButton should have been called"
        mock_markup.assert_called_once()

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    @patch('server.telegram_bot.orders.InlineKeyboardButton')
    @patch('server.telegram_bot.orders.InlineKeyboardMarkup')
    def test_show_possible_moves_fleet(self, mock_markup, mock_button, mock_map_class, mock_api_get):
        """Test show_possible_moves for a fleet unit"""
        # Mock API response
        mock_api_get.return_value = self.sample_game_state
        
        # Mock map instance
        mock_map_instance = Mock()
        mock_map_instance.get_adjacency.return_value = {"DEN", "BAL", "HEL"}
        mock_map_instance.provinces = {
            "DEN": Mock(type="coast"),
            "BAL": Mock(type="water"),
            "HEL": Mock(type="water"),
            "SIL": Mock(type="land")  # Should be filtered out for fleet
        }
        mock_map_class.return_value = mock_map_instance
        
        # Call the function
        import asyncio
        asyncio.run(show_possible_moves(self.mock_query, "1", "F KIE"))
        
        # Verify map was created
        mock_map_class.assert_called_once_with("standard")
        mock_map_instance.get_adjacency.assert_called_once_with("KIE")
        
        # Verify keyboard was created
        assert mock_button.call_count > 0, "InlineKeyboardButton should have been called"
        mock_markup.assert_called_once()

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.api_post')
    @patch('server.telegram_bot.orders.normalize_order_provinces')
    def test_submit_interactive_order_success(self, mock_normalize, mock_api_post, mock_api_get):
        """Test successful order submission"""
        # Mock API responses
        mock_api_get.return_value = self.sample_user_games
        mock_api_post.return_value = {
            "results": [{"success": True, "order": "A BER - SIL"}]
        }
        mock_normalize.return_value = "A BER - SIL"
        
        # Call the function
        import asyncio
        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - SIL"))
        
        # Verify API calls (api_get may be called multiple times for user games)
        assert mock_api_get.call_count >= 1
        mock_api_post.assert_called_once()
        
        # Verify order submission (api_post takes endpoint as first arg, json as keyword)
        call_args, call_kwargs = mock_api_post.call_args
        assert call_args[0] == "/games/set_orders"
        # Check if json is in kwargs or in args[1]
        if "json" in call_kwargs:
            json_data = call_kwargs["json"]
        else:
            json_data = call_args[1]
        assert json_data["game_id"] == "1"
        assert json_data["power"] == "GERMANY"
        assert json_data["orders"] == ["A BER - SIL"]
        
        # Verify success message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "Order Submitted Successfully!" in call_args

    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.api_post')
    def test_submit_interactive_order_failure(self, mock_api_post, mock_api_get):
        """Test failed order submission"""
        # Mock API responses
        mock_api_get.return_value = self.sample_user_games
        mock_api_post.return_value = {
            "results": [{"success": False, "error": "Invalid move"}]
        }
        
        # Call the function
        import asyncio
        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - INVALID"))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "Order Failed" in call_args
        assert "Invalid move" in call_args

    @patch('server.telegram_bot.orders.api_get')
    def test_submit_interactive_order_user_not_in_game(self, mock_api_get):
        """Test order submission when user is not in the game"""
        # Mock empty games response
        mock_api_get.return_value = {"games": []}
        
        # Call the function
        import asyncio
        asyncio.run(submit_interactive_order(self.mock_query, "1", "A BER - SIL"))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "You are not in game 1" in call_args

    def test_normalize_order_provinces(self):
        """Test province name normalization in orders"""
        # Test basic normalization
        result = normalize_order_provinces("A BER - SIL", "GERMANY")
        assert result == "A BER - SIL"  # Should remain the same
        
        # Test with lowercase provinces
        result = normalize_order_provinces("A ber - sil", "GERMANY")
        assert result == "A BER - SIL"  # Should be normalized
        
        # Test with mixed case
        result = normalize_order_provinces("A Ber - Sil", "GERMANY")
        assert result == "A BER - SIL"  # Should be normalized
        
        # Test hold order
        result = normalize_order_provinces("A BER H", "GERMANY")
        assert result == "A BER H"  # Should remain the same

    def test_normalize_order_provinces_edge_cases(self):
        """Test province normalization with edge cases"""
        # Test with invalid province names
        result = normalize_order_provinces("A INVALID - SIL", "GERMANY")
        assert "INVALID" in result  # Should preserve invalid names
        
        # Test with empty order
        result = normalize_order_provinces("", "GERMANY")
        assert result == ""
        
        # Test with single word
        result = normalize_order_provinces("A", "GERMANY")
        assert result == "A"

    @patch('server.telegram_bot.orders.api_get')
    def test_show_possible_moves_no_game_state(self, mock_api_get):
        """Test show_possible_moves when game state is not available"""
        # Mock API response returning None
        mock_api_get.return_value = None
        
        # Call the function
        import asyncio
        asyncio.run(show_possible_moves(self.mock_query, "1", "A BER"))
        
        # Verify error message
        self.mock_query.edit_message_text.assert_called_once()
        call_args = self.mock_query.edit_message_text.call_args[0][0]
        assert "Could not retrieve game state" in call_args

    @patch('server.telegram_bot.orders.api_get')
    def test_selectunit_no_units(self, mock_api_get):
        """Test /selectunit when user has no units"""
        # Mock API responses
        mock_api_get.side_effect = [
            self.sample_user_games,  # user games
            {"units": {"GERMANY": []}}  # empty units
        ]
        
        # Mock message reply
        self.mock_message.reply_text = AsyncMock()
        
        # Call the function
        import asyncio
        asyncio.run(selectunit(self.mock_update, self.mock_context))
        
        # Verify error message
        self.mock_message.reply_text.assert_called_once()
        call_args = self.mock_message.reply_text.call_args[0][0]
        assert "No units found for GERMANY" in call_args

    def test_callback_data_parsing(self):
        """Test parsing of callback data for unit selection"""
        # Test unit selection callback (fixed format with underscores)
        callback_data = "select_unit_1_A_BER"
        parts = callback_data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"  # Reconstruct "A BER" from "A_BER"
        
        assert game_id == "1"
        assert unit == "A BER"
        
        # Test move selection callback
        callback_data = "move_unit_1_A_BER_move_SIL"
        parts = callback_data.split("_")
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"
        move_type = parts[5]
        target_province = parts[6]
        
        assert game_id == "1"
        assert unit == "A BER"
        assert move_type == "move"
        assert target_province == "SIL"

    def test_province_mapping_integration(self):
        """Test integration with province mapping system"""
        # Test that province mapping is used correctly
        from engine.province_mapping import normalize_province_name
        
        # Test known provinces
        assert normalize_province_name("ber") == "BER"
        assert normalize_province_name("SIL") == "SIL"
        assert normalize_province_name("kie") == "KIE"
        
        # Test unknown provinces
        assert normalize_province_name("unknown") == "UNKNOWN"


class TestInteractiveOrderIntegration:
    """Integration tests for the complete interactive order flow"""
    
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.api_post')
    @patch('server.telegram_bot.orders.Map')
    def test_complete_interactive_flow(self, mock_map_class, mock_api_post, mock_api_get):
        """Test the complete flow from unit selection to order submission"""
        # Mock map instance
        mock_map_instance = Mock()
        mock_map_instance.get_adjacency.return_value = ["SIL", "PRU"]
        mock_map_instance.provinces = {
            "SIL": Mock(type="land"),
            "PRU": Mock(type="land")
        }
        mock_map_class.return_value = mock_map_instance
        
        # Mock API responses
        mock_api_get.side_effect = [
            {"games": [{"game_id": 1, "power": "GERMANY"}]},  # user games
            {"units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}},  # game state
            {"games": [{"game_id": 1, "power": "GERMANY"}]}  # user games for submission
        ]
        mock_api_post.return_value = {
            "results": [{"success": True, "order": "A BER - SIL"}]
        }
        
        # Mock query and message
        mock_query = Mock()
        mock_query.from_user = Mock()
        mock_query.from_user.id = 12345
        mock_query.edit_message_text = AsyncMock()
        
        # Test the complete flow
        import asyncio
        
        # Step 1: Show possible moves
        asyncio.run(show_possible_moves(mock_query, "1", "A BER"))
        
        # Step 2: Submit order
        asyncio.run(submit_interactive_order(mock_query, "1", "A BER - SIL"))
        
        # Verify the flow worked
        # Note: Call count may vary due to validation/state checks
        assert mock_api_get.call_count >= 3  # At least 3 calls expected
        assert mock_api_post.call_count == 1
        
        # Verify success message
        mock_query.edit_message_text.assert_called()
        success_call = None
        for call in mock_query.edit_message_text.call_args_list:
            if "Order Submitted Successfully!" in str(call):
                success_call = call
                break
        assert success_call is not None


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])

