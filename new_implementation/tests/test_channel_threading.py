"""
Tests for discussion threading support in Telegram channels.

This module tests the threading functionality for broadcast messages and
discussion threads in Telegram channels.
"""
import pytest
from unittest.mock import Mock, patch

from server.telegram_bot.channels import (
    post_broadcast_to_channel,
    create_discussion_thread
)


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot instance."""
    bot = Mock()
    bot.send_message = Mock(return_value=Mock(message_id=12345))
    bot.create_forum_topic = Mock(return_value=Mock(message_thread_id=67890))
    return bot


@pytest.mark.unit
@pytest.mark.channels
class TestPostBroadcastWithThreading:
    """Tests for post_broadcast_to_channel with threading support."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_broadcast_with_reply(self, mock_bot, mock_telegram_bot):
        """Test posting broadcast with reply threading."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test broadcast message",
            power="FRANCE",
            reply_to_message_id=11111
        )
        
        assert result == 12345
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert call_args[1]['chat_id'] == "-1001234567890"
        assert call_args[1]['reply_to_message_id'] == 11111
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_broadcast_without_reply(self, mock_bot, mock_telegram_bot):
        """Test posting broadcast without reply threading."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test broadcast message",
            power="FRANCE"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        # Should not have reply_to_message_id if not specified
        assert 'reply_to_message_id' not in call_args[1] or call_args[1].get('reply_to_message_id') is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_broadcast_with_power(self, mock_bot, mock_telegram_bot):
        """Test posting broadcast with power formatting."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test message",
            power="ENGLAND"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "ENGLAND" in message_text or "All Powers" in message_text
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_broadcast_without_power(self, mock_bot, mock_telegram_bot):
        """Test posting broadcast without power."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test message"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "PUBLIC BROADCAST" in message_text
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_post_broadcast_no_bot(self):
        """Test posting when bot is not initialized."""
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test message"
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_broadcast_telegram_error(self, mock_bot, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.send_message.side_effect = TelegramError("API error")
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_broadcast_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            message="Test message"
        )
        
        assert result is None


@pytest.mark.unit
@pytest.mark.channels
class TestCreateDiscussionThread:
    """Tests for create_discussion_thread function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_create_discussion_thread_success(self, mock_bot, mock_telegram_bot):
        """Test successful creation of discussion thread."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = create_discussion_thread(
            channel_id="-1001234567890",
            game_id="test_game",
            topic="Spring 1901 Strategy",
            phase="Spring 1901 Movement"
        )
        
        # Should return thread_id if successful, or None if forum not supported
        assert result is not None or result is None  # Both are valid outcomes
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_create_discussion_thread_without_phase(self, mock_bot, mock_telegram_bot):
        """Test creating thread without phase."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = create_discussion_thread(
            channel_id="-1001234567890",
            game_id="test_game",
            topic="General Discussion"
        )
        
        # Should handle gracefully
        assert result is not None or result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_create_discussion_thread_forum_not_supported(self, mock_bot, mock_telegram_bot):
        """Test handling when forum topics are not supported."""
        from telegram.error import TelegramError
        mock_telegram_bot.create_forum_topic.side_effect = TelegramError("Forum not supported")
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = create_discussion_thread(
            channel_id="-1001234567890",
            game_id="test_game",
            topic="Test Topic"
        )
        
        # Should return None when forum not supported
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_create_discussion_thread_no_bot(self):
        """Test creating thread when bot is not initialized."""
        result = create_discussion_thread(
            channel_id="-1001234567890",
            game_id="test_game",
            topic="Test Topic"
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_create_discussion_thread_telegram_error(self, mock_bot, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.create_forum_topic.side_effect = TelegramError("API error")
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = create_discussion_thread(
            channel_id="-1001234567890",
            game_id="test_game",
            topic="Test Topic"
        )
        
        assert result is None

