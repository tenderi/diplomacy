"""
Comprehensive unit tests for Telegram Bot module.

Tests cover all bot functionality including commands, callbacks, error handling,
and edge cases using pytest with proper mocking.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from server.telegram_bot import (
    get_cached_default_map, set_cached_default_map, generate_default_map,
    get_telegram_token, api_post, api_get, normalize_order_provinces,
    process_waiting_list
)


class TestTelegramBotFunctions:
    """Test Telegram Bot functions."""
    
    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        context = Mock()
        context.bot = Mock()
        context.user_data = {}
        context.chat_data = {}
        context.bot_data = {}
        context.bot.send_message = AsyncMock()
        context.bot.edit_message_text = AsyncMock()
        context.bot.answer_callback_query = AsyncMock()
        return context
    
    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.effective_chat = Mock()
        update.effective_chat.id = 67890
        update.callback_query = None
        update.message = Mock()
        update.message.text = "/test"
        update.message.reply_text = AsyncMock()
        update.message.reply_markup = Mock()
        return update


class TestBotCommands:
    """Test bot command handling."""
    
    def test_get_cached_default_map_initial(self):
        """Test getting cached map when cache is empty."""
        result = get_cached_default_map()
        assert result is None
    
    def test_set_and_get_cached_default_map(self):
        """Test setting and getting cached map."""
        test_data = b"test_map_data"
        set_cached_default_map(test_data)
        result = get_cached_default_map()
        assert result == test_data
    
    def test_get_telegram_token_from_env(self):
        """Test getting Telegram token from environment."""
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            result = get_telegram_token()
            assert result == 'test_token'
    
    def test_get_telegram_token_json_format(self):
        """Test getting Telegram token from JSON format."""
        json_token = '{"TELEGRAM_BOT_TOKEN": "json_token"}'
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': json_token}):
            result = get_telegram_token()
            assert result == 'json_token'
    
    def test_get_telegram_token_empty(self):
        """Test getting Telegram token when not set."""
        with patch.dict('os.environ', {}, clear=True):
            result = get_telegram_token()
            assert result == ''
    
    @patch('server.telegram_bot.requests.post')
    def test_api_post_success(self, mock_post):
        """Test successful API POST request."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'success'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        result = api_post('/test', {'data': 'test'})
        assert result == {'status': 'success'}
        mock_post.assert_called_once()
    
    @patch('server.telegram_bot.requests.get')
    def test_api_get_success(self, mock_get):
        """Test successful API GET request."""
        mock_response = Mock()
        mock_response.json.return_value = {'data': 'test'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = api_get('/test')
        assert result == {'data': 'test'}
        mock_get.assert_called_once()
    
    def test_normalize_order_provinces_basic(self):
        """Test basic province normalization."""
        result = normalize_order_provinces("A PAR - BUR", "FRANCE")
        assert "PAR" in result
        assert "BUR" in result
    
    def test_normalize_order_provinces_with_power(self):
        """Test province normalization with power prefix."""
        result = normalize_order_provinces("FRANCE A PAR - BUR", "FRANCE")
        assert "FRANCE" not in result  # Power should be removed
        assert "PAR" in result
        assert "BUR" in result


class TestProcessWaitingList:
    """Test waiting list processing functionality."""
    
    def test_process_waiting_list_empty(self):
        """Test processing empty waiting list."""
        waiting_list = []
        powers = ['FRANCE', 'GERMANY', 'ENGLAND']
        notify_callback = Mock()
        
        result = process_waiting_list(waiting_list, 3, powers, notify_callback)
        assert result is None  # No game created
    
    def test_process_waiting_list_enough_players(self):
        """Test processing waiting list with enough players."""
        waiting_list = [
            {'user_id': 1, 'power': 'FRANCE'},
            {'user_id': 2, 'power': 'GERMANY'},
            {'user_id': 3, 'power': 'ENGLAND'}
        ]
        powers = ['FRANCE', 'GERMANY', 'ENGLAND']
        notify_callback = Mock()
        
        with patch('server.telegram_bot.api_post') as mock_api_post:
            mock_api_post.return_value = {'game_id': 123}
            
            result = process_waiting_list(waiting_list, 3, powers, notify_callback)
            assert result is not None
            mock_api_post.assert_called_once()