"""
Tests for player status dashboard formatting and posting to Telegram channels.

This module tests the format_player_dashboard and post_player_dashboard_to_channel
functions to ensure they correctly format and post player status information.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from server.telegram_bot.channels import format_player_dashboard, post_player_dashboard_to_channel


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot instance."""
    bot = Mock()
    bot.send_message = Mock(return_value=Mock(message_id=12345))
    return bot


@pytest.fixture
def sample_game_state():
    """Create a sample game state for testing."""
    return {
        "game_id": "test_game_1",
        "current_year": 1902,
        "current_season": "Spring",
        "current_phase": "Movement",
        "phase_code": "S1902M",
        "orders": {
            "AUSTRIA": [],
            "ENGLAND": [],
            "FRANCE": []
        },
        "powers": {
            "AUSTRIA": {
                "orders_submitted": True,
                "last_order_time": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                "is_active": True,
                "is_eliminated": False
            },
            "ENGLAND": {
                "orders_submitted": True,
                "last_order_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                "is_active": True,
                "is_eliminated": False
            },
            "FRANCE": {
                "orders_submitted": False,
                "last_order_time": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
                "is_active": True,
                "is_eliminated": False
            },
            "GERMANY": {
                "orders_submitted": False,
                "last_order_time": None,
                "is_active": True,
                "is_eliminated": False
            },
            "ITALY": {
                "orders_submitted": False,
                "last_order_time": None,
                "is_active": True,
                "is_eliminated": True
            }
        }
    }


@pytest.fixture
def sample_players_data():
    """Create sample players data for testing."""
    return [
        {
            "power": "AUSTRIA",
            "user_id": 1,
            "is_active": True,
            "telegram_id": "12345",
            "full_name": "Test User 1"
        },
        {
            "power": "ENGLAND",
            "user_id": 2,
            "is_active": True,
            "telegram_id": "67890",
            "full_name": "Test User 2"
        },
        {
            "power": "FRANCE",
            "user_id": 3,
            "is_active": True,
            "telegram_id": None,
            "full_name": None
        }
    ]


@pytest.mark.unit
@pytest.mark.channels
class TestFormatPlayerDashboard:
    """Tests for format_player_dashboard function."""
    
    def test_format_player_dashboard_basic(self, sample_game_state):
        """Test basic player dashboard formatting."""
        result = format_player_dashboard(sample_game_state)
        
        assert "PLAYER STATUS DASHBOARD" in result
        assert "test_game_1" in result
        assert "Spring 1902" in result
    
    def test_format_player_dashboard_with_players_data(self, sample_game_state, sample_players_data):
        """Test dashboard formatting with player information."""
        result = format_player_dashboard(sample_game_state, sample_players_data)
        
        assert "PLAYER STATUS DASHBOARD" in result
        assert "Test User 1" in result or "AUSTRIA" in result
    
    def test_format_player_dashboard_submitted_players(self, sample_game_state):
        """Test that submitted players are listed."""
        result = format_player_dashboard(sample_game_state)
        
        assert "Orders Submitted" in result
        assert "AUSTRIA" in result or "ENGLAND" in result
    
    def test_format_player_dashboard_pending_players(self, sample_game_state):
        """Test that pending players are listed."""
        result = format_player_dashboard(sample_game_state)
        
        assert "Pending" in result or "No Orders" in result
        assert "FRANCE" in result or "GERMANY" in result
    
    def test_format_player_dashboard_eliminated_players(self, sample_game_state):
        """Test that eliminated players are shown."""
        result = format_player_dashboard(sample_game_state)
        
        assert "ITALY" in result or "Eliminated" in result
    
    def test_format_player_dashboard_empty_state(self):
        """Test formatting with empty game state."""
        empty_state = {
            "game_id": "test",
            "current_year": 1901,
            "current_season": "Spring",
            "current_phase": "Movement",
            "orders": {},
            "powers": {}
        }
        
        result = format_player_dashboard(empty_state)
        assert "PLAYER STATUS DASHBOARD" in result
    
    def test_format_player_dashboard_time_formatting(self, sample_game_state):
        """Test that time ago is formatted correctly."""
        result = format_player_dashboard(sample_game_state)
        
        # Should contain time indicators
        assert "ago" in result or "Submitted" in result or "Last active" in result
    
    def test_format_player_dashboard_error_handling(self):
        """Test error handling in format_player_dashboard."""
        invalid_state = None
        
        result = format_player_dashboard(invalid_state)
        assert "Error" in result or "PLAYER STATUS DASHBOARD" in result


@pytest.mark.unit
@pytest.mark.channels
class TestPostPlayerDashboardToChannel:
    """Tests for post_player_dashboard_to_channel function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_player_dashboard_success(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test successful posting of player dashboard."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_player_dashboard_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result == 12345
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert call_args[1]['chat_id'] == "-1001234567890"
        assert call_args[1]['parse_mode'] == 'Markdown'
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_post_player_dashboard_no_bot(self, sample_game_state):
        """Test posting when bot is not initialized."""
        result = post_player_dashboard_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_player_dashboard_telegram_error(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.send_message.side_effect = TelegramError("API error")
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_player_dashboard_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_player_dashboard_with_players_data(self, mock_bot, sample_game_state,
                                                      sample_players_data, mock_telegram_bot):
        """Test posting with player data."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_player_dashboard_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state,
            players_data=sample_players_data
        )
        
        assert result == 12345
        # Verify the message contains player information
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "PLAYER STATUS" in message_text

