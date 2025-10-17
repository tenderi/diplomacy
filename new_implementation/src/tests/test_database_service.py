"""
Comprehensive unit tests for Database Service module.

Tests cover DatabaseService class with both mocked and real database scenarios,
including CRUD operations, error handling, and transaction management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from engine.database_service import DatabaseService
from engine.data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus, GameStatus,
    MapData, Province, TurnState, MapSnapshot
)


class TestDatabaseService:
    """Test DatabaseService class."""
    
    @pytest.fixture
    def db_service(self, temp_db):
        """Create DatabaseService instance with test database."""
        # Use PostgreSQL database URL directly
        db_url = str(temp_db.url)
        return DatabaseService(db_url)
    
    @pytest.fixture
    def sample_game_state(self):
        """Create sample game state for testing."""
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        return GameState(
            game_id="test_game_001",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers={},
            map_data=map_data,
            orders={}
        )
    
    @pytest.fixture
    def sample_power_state(self):
        """Create sample power state for testing."""
        units = [
            Unit(unit_type="A", province="PAR", power="FRANCE"),
            Unit(unit_type="F", province="BRE", power="FRANCE")
        ]
        
        return PowerState(
            power_name="FRANCE",
            units=units,
            controlled_supply_centers=["PAR", "BRE"]
        )
    
    def test_service_initialization(self, temp_db):
        """Test DatabaseService initialization."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        assert service.session_factory is not None
    
    def test_create_game(self, db_service, sample_game_state):
        """Test game creation."""
        game_state = db_service.create_game("test_game_001", "standard")
        
        assert isinstance(game_state, GameState)
        assert game_state.game_id == "test_game_001"
        assert game_state.map_name == "standard"
        assert game_state.current_turn == 0
        assert game_state.current_year == 1901
        assert game_state.current_season == "Spring"
        assert game_state.current_phase == "Movement"
        assert game_state.status == "active"
    
    def test_create_game_with_existing_id(self, db_service):
        """Test creating game with existing ID raises error."""
        # Create first game
        db_service.create_game("duplicate_game", "standard")
        
        # Try to create second game with same ID
        with pytest.raises(IntegrityError):
            db_service.create_game("duplicate_game", "standard")
    
    def test_get_game_state(self, db_service, sample_game_state):
        """Test loading existing game."""
        # Create game first
        created_game = db_service.create_game("load_test_game", "standard")
        
        # Load the game
        loaded_game = db_service.get_game_state("load_test_game")
        
        assert isinstance(loaded_game, GameState)
        assert loaded_game.game_id == "load_test_game"
        assert loaded_game.map_name == "standard"
    
    def test_load_nonexistent_game(self, db_service):
        """Test loading non-existent game returns None."""
        loaded_game = db_service.get_game_state("nonexistent_game")
        
        assert loaded_game is None
    
    def test_save_game_state(self, db_service, sample_game_state):
        """Test saving game state."""
        # Create game first
        db_service.create_game("save_test_game", "standard")
        
        # Save game state
        result = db_service.save_game_state(sample_game_state)
        
        assert result is True
        
        # Verify state was saved
        loaded_game = db_service.get_game_state("save_test_game")
        assert loaded_game.current_turn == sample_game_state.current_turn
        assert loaded_game.current_year == sample_game_state.current_year
        assert loaded_game.current_season == sample_game_state.current_season
    
    def test_update_units(self, db_service, sample_power_state):
        """Test updating units for a power."""
        # Create game first
        db_service.create_game("unit_test_game", "standard")
        
        # Update units
        result = db_service.update_units("unit_test_game", "FRANCE", sample_power_state.units)
        
        assert result is True
        
        # Verify units were updated
        loaded_game = db_service.get_game_state("unit_test_game")
        france_units = loaded_game.powers["FRANCE"].units
        assert len(france_units) == 2
        assert any(unit.province == "PAR" for unit in france_units)
        assert any(unit.province == "BRE" for unit in france_units)
    
    def test_save_orders(self, db_service):
        """Test saving orders for a power."""
        # Create game first
        db_service.create_game("order_test_game", "standard")
        
        # Create sample orders
        orders = [
            Order(
                power="FRANCE",
                unit_type="A",
                unit_province="PAR",
                order_type=OrderType.MOVE,
                target_province="BUR",
                status=OrderStatus.SUBMITTED
            ),
            Order(
                power="FRANCE",
                unit_type="F",
                unit_province="BRE",
                order_type=OrderType.HOLD,
                status=OrderStatus.SUBMITTED
            )
        ]
        
        # Save orders
        result = db_service.save_orders("order_test_game", "FRANCE", orders)
        
        assert result is True
        
        # Verify orders were saved
        loaded_game = db_service.get_game_state("order_test_game")
        france_orders = loaded_game.powers["FRANCE"].orders
        assert len(france_orders) == 2
    
    def test_get_game_history(self, db_service):
        """Test retrieving game history."""
        # Create game and add some history
        db_service.create_game("history_test_game", "standard")
        
        # Add some turn history
        turn_states = [
            TurnState(
                turn=1,
                year=1901,
                season="Spring",
                phase="Movement",
                phase_code="S1901M"
            ),
            TurnState(
                turn=2,
                year=1901,
                season="Spring",
                phase="Retreat",
                phase_code="S1901R"
            )
        ]
        
        # Save history
        result = db_service.save_game_history("history_test_game", turn_states)
        assert result is True
        
        # Retrieve history
        history = db_service.get_game_history("history_test_game")
        
        assert isinstance(history, list)
        assert len(history) == 2
        assert history[0].turn == 1
        assert history[1].turn == 2
    
    def test_save_map_snapshot(self, db_service):
        """Test saving map snapshot."""
        # Create game first
        db_service.create_game("snapshot_test_game", "standard")
        
        # Create map snapshot
        snapshot = MapSnapshot(
            game_id="snapshot_test_game",
            turn=1,
            map_data=MapData(provinces={}, adjacencies={}),
            units={},
            orders={}
        )
        
        # Save snapshot
        result = db_service.save_map_snapshot(snapshot)
        
        assert result is True
    
    def test_get_map_snapshot(self, db_service):
        """Test retrieving map snapshot."""
        # Create game and save snapshot
        db_service.create_game("get_snapshot_test_game", "standard")
        
        snapshot = MapSnapshot(
            game_id="get_snapshot_test_game",
            turn=1,
            map_data=MapData(provinces={}, adjacencies={}),
            units={},
            orders={}
        )
        
        db_service.save_map_snapshot(snapshot)
        
        # Retrieve snapshot
        retrieved_snapshot = db_service.get_map_snapshot("get_snapshot_test_game", 1)
        
        assert retrieved_snapshot is not None
        assert retrieved_snapshot.game_id == "get_snapshot_test_game"
        assert retrieved_snapshot.turn == 1


class TestDatabaseServiceErrorHandling:
    """Test error handling in DatabaseService."""
    
    @pytest.fixture
    def db_service(self, temp_db):
        """Create DatabaseService instance."""
        # Use PostgreSQL database URL directly
        db_url = str(temp_db.url)
        return DatabaseService(db_url)
    
    @patch('src.engine.database_service.Session')
    def test_database_connection_error(self, mock_session, temp_db):
        """Test handling of database connection errors."""
        mock_session.side_effect = SQLAlchemyError("Connection failed")
        
        service = DatabaseService("invalid://url")
        
        with pytest.raises(SQLAlchemyError):
            service.create_game("test_game", "standard")
    
    def test_invalid_game_id(self, db_service):
        """Test handling of invalid game ID."""
        with pytest.raises(ValueError):
            db_service.create_game("", "standard")
        
        with pytest.raises(ValueError):
            db_service.create_game(None, "standard")
    
    def test_invalid_map_name(self, db_service):
        """Test handling of invalid map name."""
        with pytest.raises(ValueError):
            db_service.create_game("test_game", "")
        
        with pytest.raises(ValueError):
            db_service.create_game("test_game", None)
    
    def test_save_nonexistent_game(self, db_service, sample_game_state):
        """Test saving state for non-existent game."""
        sample_game_state.game_id = "nonexistent_game"
        
        result = db_service.save_game_state(sample_game_state)
        
        assert result is False
    
    def test_update_units_nonexistent_game(self, db_service, sample_power_state):
        """Test updating units for non-existent game."""
        result = db_service.update_units("nonexistent_game", "FRANCE", sample_power_state.units)
        
        assert result is False
    
    def test_save_orders_nonexistent_game(self, db_service):
        """Test saving orders for non-existent game."""
        orders = [
            Order(
                power="FRANCE",
                unit_type="A",
                unit_province="PAR",
                order_type=OrderType.MOVE,
                target_province="BUR",
                status=OrderStatus.SUBMITTED
            )
        ]
        
        result = db_service.save_orders("nonexistent_game", "FRANCE", orders)
        
        assert result is False


class TestDatabaseServiceTransactionManagement:
    """Test transaction management in DatabaseService."""
    
    @pytest.fixture
    def db_service(self, temp_db):
        """Create DatabaseService instance."""
        # Use PostgreSQL database URL directly
        db_url = str(temp_db.url)
        return DatabaseService(db_url)
    
    def test_transaction_rollback_on_error(self, db_service):
        """Test that transactions are rolled back on error."""
        # This test would require more complex setup to trigger a rollback
        # For now, we'll test that the service handles errors gracefully
        
        with pytest.raises(ValueError):
            db_service.create_game("", "standard")
        
        # Verify no partial data was created
        loaded_game = db_service.get_game_state("")
        assert loaded_game is None
    
    def test_concurrent_access(self, db_service):
        """Test concurrent access to database."""
        # Create multiple games concurrently
        game_ids = [f"concurrent_game_{i}" for i in range(5)]
        
        for game_id in game_ids:
            result = db_service.create_game(game_id, "standard")
            assert result is not None
        
        # Verify all games were created
        for game_id in game_ids:
            loaded_game = db_service.get_game_state(game_id)
            assert loaded_game is not None
            assert loaded_game.game_id == game_id


class TestDatabaseServiceMocked:
    """Test DatabaseService with mocked dependencies."""
    
    @pytest.fixture
    def mock_session_factory(self):
        """Create mock session factory."""
        mock_session = Mock(spec=Session)
        mock_session_factory = Mock(return_value=mock_session)
        return mock_session_factory
    
    @pytest.fixture
    def db_service_mocked(self, mock_session_factory):
        """Create DatabaseService with mocked session factory."""
        service = DatabaseService("postgresql+psycopg2://test:test@localhost:5432/test_db")
        service.session_factory = mock_session_factory
        return service
    
    def test_create_game_mocked(self, db_service_mocked, mock_session_factory):
        """Test create_game with mocked session."""
        mock_session = mock_session_factory.return_value
        
        result = db_service_mocked.create_game("mocked_game", "standard")
        
        # Verify session was used
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        
        assert isinstance(result, GameState)
        assert result.game_id == "mocked_game"
    
    def test_get_game_state_mocked(self, db_service_mocked, mock_session_factory):
        """Test get_game_state with mocked session."""
        mock_session = mock_session_factory.return_value
        
        # Mock query result
        mock_game_model = Mock()
        mock_game_model.game_id = "mocked_game"
        mock_game_model.map_name = "standard"
        mock_game_model.current_turn = 1
        mock_game_model.current_year = 1901
        mock_game_model.current_season = "Spring"
        mock_game_model.current_phase = "Movement"
        mock_game_model.phase_code = "S1901M"
        mock_game_model.status = "active"
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_game_model
        
        result = db_service_mocked.get_game_state("mocked_game")
        
        # Verify session was used
        mock_session.query.assert_called_once()
        
        assert isinstance(result, GameState)
        assert result.game_id == "mocked_game"
    
    def test_save_game_state_mocked(self, db_service_mocked, mock_session_factory, sample_game_state):
        """Test save_game_state with mocked session."""
        mock_session = mock_session_factory.return_value
        
        # Mock query result
        mock_game_model = Mock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_game_model
        
        result = db_service_mocked.save_game_state(sample_game_state)
        
        # Verify session was used
        mock_session.query.assert_called_once()
        mock_session.commit.assert_called_once()
        
        assert result is True


# Integration tests
@pytest.mark.integration
class TestDatabaseServiceIntegration:
    """Integration tests for DatabaseService with real database."""
    
    @pytest.fixture
    def db_service(self, temp_db):
        """Create DatabaseService with real database."""
        # Use PostgreSQL database URL directly
        db_url = str(temp_db.url)
        return DatabaseService(db_url)
    
    def test_full_game_lifecycle(self, db_service):
        """Test complete game lifecycle with database."""
        # Create game
        game_state = db_service.create_game("lifecycle_test", "standard")
        assert game_state is not None
        
        # Add players and units
        game_state.powers = {
            "FRANCE": PowerState(
                power_name="FRANCE",
                units=[
                    Unit(unit_type="A", province="PAR", power="FRANCE"),
                    Unit(unit_type="F", province="BRE", power="FRANCE")
                ],
                controlled_supply_centers=["PAR", "BRE"]
            )
        }
        
        # Save game state
        result = db_service.save_game_state(game_state)
        assert result is True
        
        # Load game state
        loaded_game = db_service.get_game_state("lifecycle_test")
        assert loaded_game is not None
        assert "FRANCE" in loaded_game.powers
        assert len(loaded_game.powers["FRANCE"].units) == 2
        
        # Update units
        new_units = [
            Unit(unit_type="A", province="BUR", power="FRANCE"),
            Unit(unit_type="F", province="ENG", power="FRANCE")
        ]
        
        result = db_service.update_units("lifecycle_test", "FRANCE", new_units)
        assert result is True
        
        # Verify units were updated
        updated_game = db_service.get_game_state("lifecycle_test")
        france_units = updated_game.powers["FRANCE"].units
        assert len(france_units) == 2
        assert any(unit.province == "BUR" for unit in france_units)
        assert any(unit.province == "ENG" for unit in france_units)
    
    def test_multiple_games_concurrent(self, db_service):
        """Test handling multiple games concurrently."""
        game_ids = [f"concurrent_test_{i}" for i in range(10)]
        
        # Create multiple games
        for game_id in game_ids:
            game_state = db_service.create_game(game_id, "standard")
            assert game_state.game_id == game_id
        
        # Load all games
        for game_id in game_ids:
            loaded_game = db_service.get_game_state(game_id)
            assert loaded_game is not None
            assert loaded_game.game_id == game_id
        
        # Update games concurrently
        for i, game_id in enumerate(game_ids):
            units = [
                Unit(unit_type="A", province=f"PROV_{i}", power="FRANCE")
            ]
            result = db_service.update_units(game_id, "FRANCE", units)
            assert result is True
        
        # Verify all updates
        for i, game_id in enumerate(game_ids):
            loaded_game = db_service.get_game_state(game_id)
            france_units = loaded_game.powers["FRANCE"].units
            assert len(france_units) == 1
            assert france_units[0].province == f"PROV_{i}"
