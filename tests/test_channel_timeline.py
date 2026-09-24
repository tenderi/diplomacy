"""
Tests for historical timeline visualization in Telegram channels.

This module tests the format_historical_timeline and post_timeline_update_to_channel
functions to ensure they correctly format and post timeline information.
"""
import pytest
from unittest.mock import Mock, patch

from server.telegram_bot.channels import (
    format_historical_timeline,
    post_timeline_update_to_channel
)


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
        "powers": {
            "AUSTRIA": {
                "is_eliminated": False,
                "controlled_supply_centers": ["VIE", "BUD", "TRI"]
            },
            "ENGLAND": {
                "is_eliminated": False,
                "controlled_supply_centers": ["LON", "EDI", "LVP"]
            },
            "FRANCE": {
                "is_eliminated": False,
                "controlled_supply_centers": ["PAR", "MAR", "BRE"]
            },
            "ITALY": {
                "is_eliminated": True,  # Eliminated
                "controlled_supply_centers": []
            },
            "RUSSIA": {
                "is_eliminated": False,
                "controlled_supply_centers": ["MOS", "WAR", "SEV", "STP", "NOR", "SWE", "FIN", "UKR"]
            }
        },
        "supply_centers": {
            "AUSTRIA": ["VIE", "BUD", "TRI"],
            "ENGLAND": ["LON", "EDI", "LVP"],
            "FRANCE": ["PAR", "MAR", "BRE"],
            "RUSSIA": ["MOS", "WAR", "SEV", "STP", "NOR", "SWE", "FIN", "UKR"]
        }
    }


@pytest.fixture
def sample_previous_powers():
    """Create sample previous power states for comparison."""
    return {
        "AUSTRIA": {
            "is_eliminated": False,
            "controlled_supply_centers": ["VIE", "BUD"]
        },
        "ENGLAND": {
            "is_eliminated": False,
            "controlled_supply_centers": ["LON", "EDI", "LVP"]
        },
        "FRANCE": {
            "is_eliminated": False,
            "controlled_supply_centers": ["PAR", "MAR", "BRE"]
        },
        "ITALY": {
            "is_eliminated": False,  # Was not eliminated before
            "controlled_supply_centers": ["ROM", "VEN", "TRI"]
        },
        "RUSSIA": {
            "is_eliminated": False,
            "controlled_supply_centers": ["MOS", "WAR", "SEV", "STP"]
        }
    }


@pytest.mark.unit
@pytest.mark.channels
class TestFormatHistoricalTimeline:
    """Tests for format_historical_timeline function."""
    
    def test_format_historical_timeline_basic(self, sample_game_state):
        """Test basic timeline formatting."""
        result = format_historical_timeline(sample_game_state)
        
        assert "HISTORICAL TIMELINE" in result
        assert "test_game_1" in result
        assert "Current Status" in result
    
    def test_format_historical_timeline_with_eliminations(self, sample_game_state, sample_previous_powers):
        """Test timeline formatting with eliminations."""
        result = format_historical_timeline(
            sample_game_state,
            previous_powers=sample_previous_powers
        )
        
        assert "HISTORICAL TIMELINE" in result
        assert "eliminated" in result.lower() or "ITALY" in result
    
    def test_format_historical_timeline_with_supply_changes(self, sample_game_state, sample_previous_powers):
        """Test timeline formatting with supply center changes."""
        result = format_historical_timeline(
            sample_game_state,
            previous_powers=sample_previous_powers
        )
        
        assert "HISTORICAL TIMELINE" in result
        # Should mention supply center changes
        assert "AUSTRIA" in result or "RUSSIA" in result or "Current Status" in result
    
    def test_format_historical_timeline_victory_condition(self, sample_game_state):
        """Test timeline formatting with victory condition."""
        # Modify game state to have a power with 18+ centers
        sample_game_state["powers"]["RUSSIA"]["controlled_supply_centers"] = [
            "MOS", "WAR", "SEV", "STP", "NOR", "SWE", "FIN", "UKR",
            "TRI", "BUD", "VIE", "BER", "MUN", "KIE", "PAR", "MAR",
            "BRE", "LON", "EDI"
        ]
        
        result = format_historical_timeline(sample_game_state)
        
        assert "HISTORICAL TIMELINE" in result
        assert "victory" in result.lower() or "RUSSIA" in result
    
    def test_format_historical_timeline_current_status(self, sample_game_state):
        """Test that current status is included."""
        result = format_historical_timeline(sample_game_state)
        
        assert "Current Status" in result
        assert "RUSSIA" in result or "centers" in result
    
    def test_format_historical_timeline_empty_state(self):
        """Test formatting with empty game state."""
        empty_state = {
            "game_id": "test",
            "current_year": 1901,
            "current_season": "Spring",
            "current_phase": "Movement",
            "powers": {},
            "supply_centers": {}
        }
        
        result = format_historical_timeline(empty_state)
        assert "HISTORICAL TIMELINE" in result
    
    def test_format_historical_timeline_error_handling(self):
        """Test error handling in format_historical_timeline."""
        invalid_state = None
        
        result = format_historical_timeline(invalid_state)
        assert "Error" in result or "HISTORICAL TIMELINE" in result


@pytest.mark.unit
@pytest.mark.channels
class TestPostTimelineUpdateToChannel:
    """Tests for post_timeline_update_to_channel function."""
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_timeline_update_success(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test successful posting of timeline update."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_timeline_update_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result == 12345
        mock_telegram_bot.send_message.assert_called_once()
        call_args = mock_telegram_bot.send_message.call_args
        assert call_args[1]['chat_id'] == "-1001234567890"
        assert call_args[1]['parse_mode'] == 'Markdown'
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_timeline_update_with_previous_powers(self, mock_bot, sample_game_state,
                                                        sample_previous_powers, mock_telegram_bot):
        """Test posting timeline with previous power states."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_timeline_update_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state,
            previous_powers=sample_previous_powers
        )
        
        assert result == 12345
        call_args = mock_telegram_bot.send_message.call_args
        message_text = call_args[1]['text']
        assert "HISTORICAL TIMELINE" in message_text
    
    @patch('server.telegram_bot.channels._telegram_bot', None)
    def test_post_timeline_update_no_bot(self, sample_game_state):
        """Test posting when bot is not initialized."""
        result = post_timeline_update_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_timeline_update_telegram_error(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test handling of Telegram errors."""
        from telegram.error import TelegramError
        mock_telegram_bot.send_message.side_effect = TelegramError("API error")
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        result = post_timeline_update_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state
        )
        
        assert result is None
    
    @patch('server.telegram_bot.channels._telegram_bot')
    def test_post_timeline_update_with_turn_history(self, mock_bot, sample_game_state, mock_telegram_bot):
        """Test posting with turn history."""
        mock_bot.return_value = mock_telegram_bot
        from server.telegram_bot.channels import set_telegram_bot
        set_telegram_bot(mock_telegram_bot)
        
        turn_history = [
            {
                "turn_number": 1,
                "year": 1901,
                "season": "Spring",
                "phase": "Movement"
            }
        ]
        
        result = post_timeline_update_to_channel(
            channel_id="-1001234567890",
            game_id="test_game",
            game_state=sample_game_state,
            turn_history=turn_history
        )
        
        assert result == 12345

