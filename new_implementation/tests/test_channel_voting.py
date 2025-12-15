"""
Tests for reaction-based voting on proposals in Telegram channels.

This module tests the post_proposal_with_voting and get_proposal_results
functions to ensure they correctly handle proposal posting and vote tracking.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from server.telegram_bot.channels import (
    post_proposal_with_voting,
    get_proposal_results
)


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot instance."""
    bot = Mock()
    bot.send_message = Mock(return_value=Mock(message_id=12345))
    return bot


@pytest.mark.unit
@pytest.mark.channels
class TestPostProposalWithVoting:
    """Tests for post_proposal_with_voting function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_proposal_success(self, mock_bot, mock_telegram_bot):
        """Test successful posting of proposal with voting."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="I propose a Western Triple Alliance.",
            power="FRANCE"
        )
        
        assert result == 12345
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert call_args[1]['chat_id'] == "-1001234567890"
        assert call_args[1]['parse_mode'] == 'Markdown'
        assert 'reply_markup' in call_args[1]
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_proposal_with_title(self, mock_bot, mock_telegram_bot):
        """Test posting proposal with custom title."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="Alliance proposal text",
            power="ENGLAND",
            proposal_title="Western Alliance"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "Western Alliance" in message_text or "PROPOSAL" in message_text
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_proposal_voting_buttons(self, mock_bot, mock_telegram_bot):
        """Test that voting buttons are included."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="Test proposal",
            power="GERMANY"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        reply_markup = call_args[1]['reply_markup']
        assert reply_markup is not None
        # Check that it's an InlineKeyboardMarkup
        assert hasattr(reply_markup, 'inline_keyboard') or isinstance(reply_markup, InlineKeyboardMarkup)
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_proposal_power_formatting(self, mock_bot, mock_telegram_bot):
        """Test that power is correctly formatted in proposal."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="Test proposal",
            power="ITALY"
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "ITALY" in message_text or "🇮🇹" in message_text
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_post_proposal_no_bot(self):
        """Test posting when bot is not initialized."""
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="Test proposal",
            power="RUSSIA"
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_proposal_telegram_error(self, mock_bot, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.send_message.side_effect = TelegramError("API error")
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_proposal_with_voting(
            channel_id="-1001234567890",
            game_id="test_game",
            proposal_text="Test proposal",
            power="TURKEY"
        )
        
        assert result is None


@pytest.mark.unit
@pytest.mark.channels
class TestGetProposalResults:
    """Tests for get_proposal_results function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_get_proposal_results_success(self, mock_bot, mock_telegram_bot):
        """Test getting proposal results."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = get_proposal_results(
            channel_id="-1001234567890",
            message_id=12345
        )
        
        assert isinstance(result, dict)
        assert "message_id" in result
        assert result["message_id"] == 12345
        assert "votes" in result
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_get_proposal_results_no_bot(self):
        """Test getting results when bot is not initialized."""
        result = get_proposal_results(
            channel_id="-1001234567890",
            message_id=12345
        )
        
        assert isinstance(result, dict)
        assert "error" in result
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_get_proposal_results_structure(self, mock_bot, mock_telegram_bot):
        """Test that results have correct structure."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = get_proposal_results(
            channel_id="-1001234567890",
            message_id=12345
        )
        
        assert "votes" in result
        assert "support" in result["votes"]
        assert "oppose" in result["votes"]
        assert "undecided" in result["votes"]
        assert "total_votes" in result

