"""
Unit tests for API shared utilities.

Tests shared helper functions and utilities used across route modules.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta

from server.api.shared import (
    _state_to_spec_dict,
    _get_power_for_unit,
    notify_players,
    process_due_deadlines,
    reminder_sent
)
from engine.data_models import GameState, PowerState, Unit, GameStatus, MapData, Province
from engine.game import Game


@pytest.fixture
def sample_game_state():
    """Create a sample game state for testing."""
    from engine.data_models import Province
    
    provinces = {
        "PAR": Province(name="PAR", province_type="coastal", adjacent_provinces=["BUR", "BRE"], is_supply_center=True, is_home_supply_center=True),
        "BUR": Province(name="BUR", province_type="land", adjacent_provinces=["PAR"], is_supply_center=False, is_home_supply_center=False),
    }
    
    map_data = MapData(
        map_name="standard",
        provinces=provinces,
        supply_centers=["PAR"],  # Required parameter
        home_supply_centers={"FRANCE": ["PAR"]},
        starting_positions={}
    )
    
    france_units = [Unit(unit_type="A", province="PAR", power="FRANCE", coast=None)]
    france_power = PowerState(
        power_name="FRANCE",
        user_id=1,
        is_active=True,
        is_eliminated=False,
        home_supply_centers=["PAR"],
        controlled_supply_centers=["PAR"],
        units=france_units,
        orders_submitted=False,
        last_order_time=None,
        retreat_options=[],
        build_options=[],
        destroy_options=[]
    )
    
    game_state = GameState(
        game_id="test_game",
        map_name="standard",
        current_turn=1,
        current_year=1901,
        current_season="Spring",
        current_phase="Movement",
        phase_code="S1901M",
        status=GameStatus.ACTIVE,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        powers={"FRANCE": france_power},
        map_data=map_data,  # Required parameter
        orders={},
        pending_retreats={},
        pending_builds={},
        pending_destroys={},
        order_history=[]
    )
    
    return game_state


@pytest.mark.unit
class TestStateToSpecDict:
    """Test _state_to_spec_dict function."""
    
    def test_state_to_spec_dict_basic(self, sample_game_state):
        """Test basic state conversion."""
        result = _state_to_spec_dict(sample_game_state)
        
        assert isinstance(result, dict)
        assert result["game_id"] == "test_game"
        assert result["map_name"] == "standard"
        assert result["current_turn"] == 1
        assert "powers" in result
        assert "units" in result
        assert "supply_centers" in result
    
    def test_state_to_spec_dict_powers(self, sample_game_state):
        """Test power serialization."""
        result = _state_to_spec_dict(sample_game_state)
        
        assert "FRANCE" in result["powers"]
        france = result["powers"]["FRANCE"]
        assert france["power_name"] == "FRANCE"
        assert france["is_active"] is True
        assert "units" in france
    
    def test_state_to_spec_dict_supply_centers(self, sample_game_state):
        """Test supply center serialization."""
        result = _state_to_spec_dict(sample_game_state)
        
        assert "supply_centers" in result
        assert result["supply_centers"]["PAR"] == "FRANCE"
    
    def test_state_to_spec_dict_empty_orders(self, sample_game_state):
        """Test state with empty orders."""
        result = _state_to_spec_dict(sample_game_state)
        
        assert "orders" in result
        assert isinstance(result["orders"], dict)


@pytest.mark.unit
class TestGetPowerForUnit:
    """Test _get_power_for_unit function."""
    
    def test_get_power_for_unit_success(self, sample_game_state):
        """Test getting power for existing unit."""
        # Create a mock game object
        mock_game = Mock()
        mock_game.game_state = sample_game_state
        
        power = _get_power_for_unit("PAR", mock_game)
        assert power == "FRANCE"
    
    def test_get_power_for_unit_not_found(self, sample_game_state):
        """Test getting power for non-existent unit."""
        mock_game = Mock()
        mock_game.game_state = sample_game_state
        
        power = _get_power_for_unit("NOWHERE", mock_game)
        assert power is None
    
    def test_get_power_for_unit_empty_game(self):
        """Test getting power for unit in empty game."""
        empty_map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        empty_game_state = GameState(
            game_id="empty",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            powers={},
            map_data=empty_map_data,
            orders={},
            pending_retreats={},
            pending_builds={},
            pending_destroys={},
            order_history=[]
        )
        
        mock_game = Mock()
        mock_game.game_state = empty_game_state
        
        power = _get_power_for_unit("PAR", mock_game)
        assert power is None


@pytest.mark.unit
class TestNotifyPlayers:
    """Test notify_players function."""
    
    @patch('server.api.shared.requests.post')
    @patch('server.api.shared.db_service.get_players_by_game_id')
    def test_notify_players_success(self, mock_get_players, mock_post):
        """Test successful player notification."""
        # Mock player with telegram_id
        mock_player = Mock()
        mock_player.telegram_id = "12345"
        mock_get_players.return_value = [mock_player]
        
        notify_players(1, "Test message")
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["telegram_id"] == 12345
        assert call_args[1]["json"]["message"] == "Test message"
    
    @patch('server.api.shared.db_service.get_players_by_game_id')
    def test_notify_players_no_telegram_id(self, mock_get_players):
        """Test notification when player has no telegram_id."""
        mock_player = Mock()
        mock_player.telegram_id = None
        mock_get_players.return_value = [mock_player]
        
        # Should not raise exception
        notify_players(1, "Test message")
    
    @patch('server.api.shared.requests.post')
    @patch('server.api.shared.db_service.get_players_by_game_id')
    def test_notify_players_test_id(self, mock_get_players, mock_post):
        """Test notification with test telegram_id (non-numeric)."""
        mock_player = Mock()
        mock_player.telegram_id = "u1"  # Test ID
        mock_get_players.return_value = [mock_player]
        
        notify_players(1, "Test message")
        
        # Should not call post for non-numeric IDs
        mock_post.assert_not_called()


@pytest.mark.unit
class TestProcessDueDeadlines:
    """Test process_due_deadlines function."""
    
    @patch('server.api.shared.db_service.get_games_with_deadlines_and_active_status')
    @patch('server.api.shared.server.process_command')
    @patch('server.api.shared.db_service.update_game_deadline')
    @patch('server.api.shared.db_service.commit')
    @patch('server.api.shared.notify_players')
    def test_process_due_deadline_success(self, mock_notify, mock_commit, mock_update, mock_process, mock_get_games):
        """Test processing a due deadline."""
        # Mock game with due deadline
        mock_game = Mock()
        mock_game.id = 1
        mock_game.game_id = "game1"
        mock_game.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_game.state = {"turn": 1}
        mock_get_games.return_value = [mock_game]
        
        # Mock players
        mock_player = Mock()
        mock_player.id = 1
        mock_player.is_active = True
        from server.api.shared import db_service
        with patch.object(db_service, 'get_players_by_game_id', return_value=[mock_player]):
            with patch.object(db_service, 'check_if_player_has_orders_for_turn', return_value=True):
                with patch.object(db_service, 'update_game_state'):
                    mock_process.return_value = {"status": "ok"}
                    
                    process_due_deadlines(datetime.now(timezone.utc))
                    
                    mock_process.assert_called()
                    mock_update.assert_called()
                    mock_commit.assert_called()
    
    @patch('server.api.shared.db_service.get_games_with_deadlines_and_active_status')
    def test_process_due_deadline_no_games(self, mock_get_games):
        """Test processing when no games have deadlines."""
        mock_get_games.return_value = []
        
        # Should not raise exception
        process_due_deadlines(datetime.now(timezone.utc))
    
    @patch('server.api.shared.db_service.get_games_with_deadlines_and_active_status')
    def test_process_due_deadline_future_deadline(self, mock_get_games):
        """Test processing when deadline is in future."""
        mock_game = Mock()
        mock_game.id = 1
        mock_game.deadline = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_get_games.return_value = [mock_game]
        
        # Should not process
        process_due_deadlines(datetime.now(timezone.utc))


@pytest.mark.unit
class TestSharedConstants:
    """Test shared constants and configuration."""
    
    def test_admin_token_configured(self):
        """Test that ADMIN_TOKEN is configured."""
        from server.api.shared import ADMIN_TOKEN
        assert ADMIN_TOKEN is not None
        assert isinstance(ADMIN_TOKEN, str)
    
    def test_notify_url_configured(self):
        """Test that NOTIFY_URL is configured."""
        from server.api.shared import NOTIFY_URL
        assert NOTIFY_URL is not None
        assert isinstance(NOTIFY_URL, str)

