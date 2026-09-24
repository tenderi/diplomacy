"""
Tests for battle results formatting and posting to Telegram channels.

This module tests the format_battle_results and post_battle_results_to_channel
functions to ensure they correctly format and post battle results.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from server.telegram_bot.channels import format_battle_results, post_battle_results_to_channel


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
        "current_year": 1902,
        "current_season": "Spring",
        "current_phase": "Movement",
        "phase_code": "S1902M",
        "supply_centers": {
            "AUSTRIA": ["VIE", "BUD", "TRI"],
            "ENGLAND": ["LON", "EDI", "LVP"],
            "FRANCE": ["PAR", "MAR", "BRE"],
            "GERMANY": ["BER", "MUN", "KIE"],
            "ITALY": ["ROM", "VEN"],
            "RUSSIA": ["MOS", "WAR", "SEV", "STP"],
            "TURKEY": ["CON", "ANK", "SMY"]
        },
        "units": {
            "AUSTRIA": [
                {"unit_type": "A", "province": "VIE", "is_dislodged": False},
                {"unit_type": "A", "province": "BUD", "is_dislodged": False}
            ],
            "ENGLAND": [
                {"unit_type": "F", "province": "LON", "is_dislodged": False}
            ]
        }
    }


@pytest.fixture
def sample_order_history():
    """Create sample order history for testing."""
    return {
        "AUSTRIA": [
            {
                "order_type": "move",
                "status": "success",
                "unit": {"unit_type": "A", "province": "VIE"},
                "target_province": "TRI"
            }
        ],
        "ENGLAND": [
            {
                "order_type": "move",
                "status": "bounced",
                "unit": {"unit_type": "F", "province": "NTH"},
                "target_province": "NOR"
            }
        ]
    }


@pytest.fixture
def sample_previous_supply_centers():
    """Create sample previous supply centers for comparison."""
    return {
        "AUSTRIA": ["VIE", "BUD"],
        "ENGLAND": ["LON", "EDI", "LVP"],
        "FRANCE": ["PAR", "MAR", "BRE"],
        "GERMANY": ["BER", "MUN", "KIE"],
        "ITALY": ["ROM", "VEN", "TRI"],  # Had TRI, lost it
        "RUSSIA": ["MOS", "WAR", "SEV", "STP"],
        "TURKEY": ["CON", "ANK", "SMY"]
    }


@pytest.mark.unit
@pytest.mark.channels
class TestFormatBattleResults:
    """Tests for format_battle_results function."""
    
    def test_format_battle_results_basic(self, sample_game_state):
        """Test basic battle results formatting."""
        result = format_battle_results(sample_game_state)
        
        assert "ADJUDICATION RESULTS" in result
        assert "SPRING 1902" in result
        assert "Power Rankings" in result
    
    def test_format_battle_results_with_order_history(self, sample_game_state, sample_order_history):
        """Test battle results formatting with order history."""
        result = format_battle_results(sample_game_state, sample_order_history)
        
        assert "ADJUDICATION RESULTS" in result
        assert "Successful Attacks" in result or "Bounced Movements" in result
    
    def test_format_battle_results_with_supply_changes(self, sample_game_state, sample_previous_supply_centers):
        """Test battle results formatting with supply center changes."""
        result = format_battle_results(
            sample_game_state,
            previous_supply_centers=sample_previous_supply_centers
        )
        
        assert "Supply Center Changes" in result
        assert "AUSTRIA" in result or "ITALY" in result
    
    def test_format_battle_results_power_rankings(self, sample_game_state):
        """Test that power rankings are included."""
        result = format_battle_results(sample_game_state)
        
        assert "Power Rankings" in result
        # Check that at least some powers are listed
        assert "RUSSIA" in result or "ENGLAND" in result
    
    def test_format_battle_results_empty_state(self):
        """Test formatting with empty game state."""
        empty_state = {
            "current_year": 1901,
            "current_season": "Spring",
            "current_phase": "Movement",
            "supply_centers": {},
            "units": {}
        }
        
        result = format_battle_results(empty_state)
        assert "ADJUDICATION RESULTS" in result
    
    def test_format_battle_results_error_handling(self):
        """Test error handling in format_battle_results."""
        invalid_state = None
        
        result = format_battle_results(invalid_state)
        assert "Error" in result or "ADJUDICATION RESULTS" in result


@pytest.mark.unit
@pytest.mark.channels
class TestPostBattleResultsToChannel:
    """Tests for post_battle_results_to_channel function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_battle_results_success(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test successful posting of battle results."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_battle_results_to_channel(
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
    def test_post_battle_results_no_bot(self, sample_game_state):
        """Test posting when bot is not initialized."""
        result = post_battle_results_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_battle_results_telegram_error(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.send_message.side_effect = TelegramError("API error")
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_battle_results_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_battle_results_with_order_history(self, mock_bot, sample_game_state, 
                                                     sample_order_history, mock_telegram_bot):
        """Test posting with order history."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_battle_results_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state,
            order_history=sample_order_history
        )
        
        assert result == 12345
        mock_telegram_bot.send_message.assert_called_once()
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_battle_results_with_supply_changes(self, mock_bot, sample_game_state,
                                                      sample_previous_supply_centers, mock_telegram_bot):
        """Test posting with supply center changes."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_battle_results_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state,
            previous_supply_centers=sample_previous_supply_centers
        )
        
        assert result == 12345
        # Verify the message contains supply center information
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "Supply Center" in message_text or "Power Rankings" in message_text

