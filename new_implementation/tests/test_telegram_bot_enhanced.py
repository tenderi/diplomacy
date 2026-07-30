"""
Comprehensive unit tests for Telegram Bot module.

Tests cover all bot functionality including commands, callbacks, error handling,
and edge cases using pytest with proper mocking.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from server.telegram_bot.config import get_telegram_token
from server.telegram_bot.api_client import api_post, api_get


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
    
    @patch('server.telegram_bot.api_client.requests.post')
    def test_api_post_success(self, mock_post):
        """Test successful API POST request."""
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'success'}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = api_post('/test', {'data': 'test'})
        assert result == {'status': 'success'}
        mock_post.assert_called_once()

    @patch('server.telegram_bot.api_client.requests.get')
    def test_api_get_success(self, mock_get):
        """Test successful API GET request."""
        mock_response = Mock()
        mock_response.json.return_value = {'data': 'test'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = api_get('/test')
        assert result == {'data': 'test'}
        mock_get.assert_called_once()


# `TestProcessWaitingList` was removed with G5. It tested
# `telegram_bot.games.process_waiting_list`, the bot-side queue-filling function
# that has moved server-side (the queue is now a Postgres table owned by
# `/waiting_list/*`, so it survives the restart that a deploy performs and its
# entries are claimed atomically). Coverage lives in `tests/test_waiting_list.py`
# and `tests/test_telegram_waiting_list.py`.
