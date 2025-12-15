"""
Tests for convoy-related functions in the Telegram bot.

This module tests the show_convoy_options and show_convoy_destinations functions
to ensure they work correctly with the game state and map data.
"""
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, CallbackQuery, User, Message, Chat
from telegram.ext import ContextTypes

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
def mock_game_state():
    """Create a mock game state with units."""
    return {
        "units": {
            "ENGLAND": ["A LON", "F NTH", "F ENG"],
            "FRANCE": ["A PAR", "F BRE"],
            "GERMANY": ["A BER", "F KIE"]
        },
        "game_id": "test_game_1",
        "current_phase": "Movement"
    }


@pytest.mark.unit
@pytest.mark.telegram
class TestShowConvoyOptions:
    """Tests for show_convoy_options function."""
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    async def test_show_convoy_options_with_adjacent_armies(self, mock_map_class, mock_api_get, mock_query, mock_game_state):
        """Test that convoy options shows armies adjacent to the fleet's sea area."""
        # Setup mocks
        mock_api_get.return_value = mock_game_state
        
        mock_map = Mock()
        mock_map.get_adjacency.return_value = ["LON", "EDI", "NTH", "DEN", "HOL", "BEL"]
        mock_map_class.return_value = mock_map
        
        # Call function
        await show_convoy_options(mock_query, "test_game_1", "F NTH")
        
        # Verify API was called
        mock_api_get.assert_called_once_with("/games/test_game_1/state")
        
        # Verify map was created
        mock_map_class.assert_called_once_with("standard")
        
        # Verify edit_message_text was called with convoy options
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Convoy Options" in call_args[0][0] or "convoy" in call_args[0][0].lower()
        assert "F NTH" in call_args[0][0] or "NTH" in call_args[0][0]
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    async def test_show_convoy_options_no_adjacent_armies(self, mock_map_class, mock_api_get, mock_query, mock_game_state):
        """Test that convoy options shows error when no armies are adjacent."""
        # Setup mocks - no armies adjacent to this sea area
        mock_api_get.return_value = mock_game_state
        
        mock_map = Mock()
        mock_map.get_adjacency.return_value = ["NWG", "BAR"]  # No coastal provinces
        mock_map_class.return_value = mock_map
        
        # Call function
        await show_convoy_options(mock_query, "test_game_1", "F NWG")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "No armies" in call_args[0][0] or "not found" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    async def test_show_convoy_options_invalid_fleet_type(self, mock_api_get, mock_query):
        """Test that convoy options rejects non-fleet units."""
        # Call function with army instead of fleet
        await show_convoy_options(mock_query, "test_game_1", "A LON")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Only fleets" in call_args[0][0] or "not a fleet" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    async def test_show_convoy_options_game_state_error(self, mock_api_get, mock_query):
        """Test that convoy options handles game state retrieval errors."""
        # Setup mock to return None (error)
        mock_api_get.return_value = None
        
        # Call function
        await show_convoy_options(mock_query, "test_game_1", "F NTH")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Could not retrieve" in call_args[0][0] or "error" in call_args[0][0].lower()


@pytest.mark.unit
@pytest.mark.telegram
class TestShowConvoyDestinations:
    """Tests for show_convoy_destinations function."""
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    async def test_show_convoy_destinations_with_valid_destinations(self, mock_map_class, mock_api_get, mock_query, mock_game_state):
        """Test that convoy destinations shows coastal provinces adjacent to fleet."""
        # Setup mocks
        mock_api_get.return_value = mock_game_state
        
        mock_map = Mock()
        # Mock adjacency returns both land and coastal provinces
        mock_map.get_adjacency.return_value = ["LON", "EDI", "NTH", "DEN", "HOL", "BEL"]
        
        # Mock province info for coastal provinces
        def mock_get_province(name):
            prov = Mock()
            if name in ["LON", "EDI", "DEN", "HOL", "BEL"]:
                prov.type = "coast"
            else:
                prov.type = "land"
            return prov
        
        mock_map.get_province = mock_get_province
        mock_map_class.return_value = mock_map
        
        # Call function
        await show_convoy_destinations(mock_query, "test_game_1", "F NTH", "ENGLAND", "A LON")
        
        # Verify API was called
        mock_api_get.assert_called_once_with("/games/test_game_1/state")
        
        # Verify map was created
        mock_map_class.assert_called_once_with("standard")
        
        # Verify edit_message_text was called with destination options
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Convoy Destination" in call_args[0][0] or "destination" in call_args[0][0].lower()
        assert "A LON" in call_args[0][0] or "LON" in call_args[0][0]
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    async def test_show_convoy_destinations_no_coastal_destinations(self, mock_map_class, mock_api_get, mock_query, mock_game_state):
        """Test that convoy destinations shows error when no coastal provinces available."""
        # Setup mocks - only landlocked provinces adjacent
        mock_api_get.return_value = mock_game_state
        
        mock_map = Mock()
        mock_map.get_adjacency.return_value = ["MUN", "BER", "WAR"]  # Landlocked provinces
        
        def mock_get_province(name):
            prov = Mock()
            prov.type = "land"  # All landlocked
            return prov
        
        mock_map.get_province = mock_get_province
        mock_map_class.return_value = mock_map
        
        # Call function
        await show_convoy_destinations(mock_query, "test_game_1", "F BLA", "RUSSIA", "A SEV")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "No valid convoy destinations" in call_args[0][0] or "not found" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    async def test_show_convoy_destinations_game_state_error(self, mock_api_get, mock_query):
        """Test that convoy destinations handles game state retrieval errors."""
        # Setup mock to return None (error)
        mock_api_get.return_value = None
        
        # Call function
        await show_convoy_destinations(mock_query, "test_game_1", "F NTH", "ENGLAND", "A LON")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Could not retrieve" in call_args[0][0] or "error" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    @patch('server.telegram_bot.orders.api_get')
    @patch('server.telegram_bot.orders.Map')
    async def test_show_convoy_destinations_exception_handling(self, mock_map_class, mock_api_get, mock_query, mock_game_state):
        """Test that convoy destinations handles exceptions gracefully."""
        # Setup mocks to raise exception
        mock_api_get.side_effect = Exception("Test error")
        
        # Call function
        await show_convoy_destinations(mock_query, "test_game_1", "F NTH", "ENGLAND", "A LON")
        
        # Verify error message
        mock_query.edit_message_text.assert_called_once()
        call_args = mock_query.edit_message_text.call_args
        assert "Error" in call_args[0][0] or "error" in call_args[0][0].lower()


@pytest.mark.integration
@pytest.mark.telegram
class TestConvoyFunctionsIntegration:
    """Integration tests for convoy functions with real game state."""
    
    @pytest.mark.skip(reason="Requires running API server")
    async def test_convoy_options_with_real_game(self):
        """Test convoy options with a real game state (requires API server)."""
        # This would test against a real game if API server is running
        pass
    
    @pytest.mark.skip(reason="Requires running API server")
    async def test_convoy_destinations_with_real_game(self):
        """Test convoy destinations with a real game state (requires API server)."""
        # This would test against a real game if API server is running
        pass

