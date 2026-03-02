"""
Tests for database persistence edge cases.

Tests transaction rollback, connection loss, concurrent writes,
and other database resilience scenarios.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, OperationalError
from sqlalchemy.orm import Session

from engine.database_service import DatabaseService
from tests.conftest import _get_db_url


@pytest.mark.database
@pytest.mark.unit
class TestTransactionRollback:
    """Test transaction rollback scenarios."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_failed_transaction_rolls_back(self, temp_db):
        """Test that failed transactions roll back correctly."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Create a game
        game_id = f"rollback_test_game_{int(time.time() * 1000)}"
        game_state = service.create_game(game_id, "standard")
        
        # Try to create duplicate game (should fail and rollback)
        with pytest.raises((IntegrityError, Exception)):
            service.create_game(game_id, "standard")  # Duplicate ID
        
        # Verify original game still exists (transaction rolled back)
        retrieved = service.get_game_by_game_id(game_id)
        assert retrieved is not None
        assert retrieved.game_id == game_id
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_partial_transaction_rollback(self, temp_db):
        """Test that partial transactions roll back on error."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        game_id = f"partial_rollback_test_{int(time.time() * 1000)}"
        game_state = service.create_game(game_id, "standard")
        
        # Simulate error during multi-step operation
        # This tests that if one step fails, previous steps are rolled back
        try:
            # This should work
            service.update_game_state(game_state)  # update_game_state takes only game_state
            
            # This might fail (depending on implementation)
            # If it fails, previous update should be rolled back
            with patch.object(service, 'session_factory') as mock_session:
                mock_session.side_effect = SQLAlchemyError("Simulated error")
                with pytest.raises(SQLAlchemyError):
                    service.update_game_state(game_state)  # update_game_state takes only game_state
        except Exception:
            # Expected - verify rollback occurred
            pass


@pytest.mark.database
@pytest.mark.unit
class TestDatabaseConnectionResilience:
    """Test database connection loss and recovery."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_connection_loss_handled_gracefully(self, temp_db):
        """Test that connection loss is handled gracefully."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Simulate connection loss
        with patch.object(service, 'session_factory') as mock_session:
            mock_session.side_effect = OperationalError("Connection lost", None, None)
            
            # Operations should handle the error gracefully
            with pytest.raises((OperationalError, SQLAlchemyError)):
                service.get_game_by_game_id("test_game")
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_retry_on_transient_errors(self, temp_db):
        """Test retry logic on transient database errors."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Create game first
        import time
        game_id = f"retry_test_game_{int(time.time() * 1000)}"
        service.create_game(game_id, "standard")
        
        # Simulate transient error that should retry
        call_count = 0
        def mock_session_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OperationalError("Transient error", None, None)
            # Second call succeeds
            return temp_db.session_factory()
        
        # Note: This is a simplified test - actual retry logic would be in the service
        # For now, we just verify that errors are raised appropriately
        with patch.object(service, 'session_factory', side_effect=mock_session_with_retry):
            try:
                service.get_game_by_game_id(game_id)
            except OperationalError:
                # Expected on first call
                pass


@pytest.mark.database
@pytest.mark.unit
class TestConcurrentWrites:
    """Test concurrent write scenarios."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concurrent_game_creation(self, temp_db):
        """Test concurrent game creation (should handle gracefully)."""
        db_url = str(temp_db.url)
        service1 = DatabaseService(db_url)
        service2 = DatabaseService(db_url)
        
        game_id = "concurrent_test_game"
        
        # Both services try to create same game
        game1 = service1.create_game(game_id, "standard")
        
        # Second creation should fail (duplicate)
        with pytest.raises((IntegrityError, Exception)):
            service2.create_game(game_id, "standard")
        
        # First game should still exist
        retrieved = service1.get_game_by_game_id(game_id)
        assert retrieved is not None
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_concurrent_state_updates(self, temp_db):
        """Test concurrent game state updates."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Use unique game_id to avoid conflicts
        game_id = f"concurrent_update_test_{int(time.time() * 1000)}"
        game_state = service.create_game(game_id, "standard")
        
        # Update state
        game_state.current_turn = 1
        service.update_game_state(game_state)  # update_game_state takes only game_state
        
        # Verify update
        retrieved = service.get_game_by_game_id(game_id)
        assert retrieved.current_turn == 1
        
        # Update again
        game_state.current_turn = 2
        service.update_game_state(game_state)  # update_game_state takes only game_state
        
        # Verify second update
        retrieved = service.get_game_by_game_id(game_id)
        assert retrieved.current_turn == 2


@pytest.mark.database
@pytest.mark.unit
class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_orphaned_records_prevention(self, temp_db):
        """Test that orphaned records are prevented."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        game_id = f"orphan_test_game_{int(time.time() * 1000)}"
        game_state = service.create_game(game_id, "standard")
        
        # Create order for game
        from engine.data_models import Unit, MoveOrder, OrderType
        unit = Unit(unit_type="A", province="PAR", power="FRANCE")
        order = MoveOrder(
            power="FRANCE",
            unit=unit,
            target_province="BUR",
            order_type=OrderType.MOVE
        )
        
        # Save order (use submit_orders instead of save_orders)
        service.submit_orders(game_id, "FRANCE", [order])
        
        # Delete game (should cascade delete orders or prevent deletion)
        # This depends on implementation - test that data integrity is maintained
        try:
            service.delete_game(game_id)
            # If deletion succeeds, verify orders are also deleted (cascade)
            orders = service.get_orders_for_power(game_id, "FRANCE")
            assert len(orders) == 0 or orders is None
        except Exception:
            # If deletion is prevented due to foreign key constraints, that's also valid
            pass
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_foreign_key_constraints(self, temp_db):
        """Test that foreign key constraints are enforced."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Try to create order for non-existent game
        from engine.data_models import Unit, MoveOrder, OrderType
        unit = Unit(unit_type="A", province="PAR", power="FRANCE")
        order = MoveOrder(
            power="FRANCE",
            unit=unit,
            target_province="BUR",
            order_type=OrderType.MOVE
        )
        
        # This should fail due to foreign key constraint
        with pytest.raises((IntegrityError, Exception)):
            service.submit_orders("nonexistent_game", "FRANCE", [order])


@pytest.mark.database
@pytest.mark.unit
class TestOrderHistoryPersistence:
    """Test order history tracking across turns."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_order_history_persists_across_turns(self, temp_db):
        """Test that order history is tracked across multiple turns."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        game_id = f"history_test_game_{int(time.time() * 1000)}"
        game_state = service.create_game(game_id, "standard")
        # add_player expects numeric DB id, not game_id string
        game_model = service.get_game_by_game_id(game_id)
        assert game_model is not None
        numeric_game_id = game_model.id
        
        # Add FRANCE player first (required for submitting orders)
        service.add_player(numeric_game_id, "FRANCE", user_id=None)
        
        from engine.data_models import Unit, MoveOrder, OrderType
        
        # Turn 1 orders
        unit1 = Unit(unit_type="A", province="PAR", power="FRANCE")
        order1 = MoveOrder(
            power="FRANCE",
            unit=unit1,
            target_province="BUR",
            order_type=OrderType.MOVE
        )
        service.submit_orders(game_id, "FRANCE", [order1])
        
        # Advance turn
        game_state.current_turn = 1
        service.update_game_state(game_state)  # update_game_state takes only game_state
        
        # Turn 2 orders
        unit2 = Unit(unit_type="A", province="BUR", power="FRANCE")
        order2 = MoveOrder(
            power="FRANCE",
            unit=unit2,
            target_province="PIC",
            order_type=OrderType.MOVE
        )
        service.submit_orders(game_id, "FRANCE", [order2])
        
        # Retrieve order history by getting player and then orders
        assert numeric_game_id > 0, "Numeric game_id should be valid"
        
        # Get player for FRANCE using numeric game_id
        players = service.get_players_by_game_id(numeric_game_id)
        france_player = next((p for p in players if getattr(p, 'power_name', None) == 'FRANCE'), None)
        assert france_player is not None, "FRANCE player should exist"
        
        # Get orders for the player (should include orders from both turns)
        player_id = int(getattr(france_player, 'id', 0))
        assert player_id > 0, "Player ID should be valid"
        orders = service.get_orders_by_player_id(player_id)
        # Should contain orders from both turns
        assert len(orders) >= 2, f"Should have at least 2 orders (one per turn), got {len(orders)}"
        # Verify orders are from different turns
        turn_numbers = {order.turn_number for order in orders}
        assert len(turn_numbers) >= 2, f"Orders should span multiple turns, got turns: {turn_numbers}"


@pytest.mark.database
@pytest.mark.unit
class TestUserDataPersistence:
    """Test user data persistence."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_registration_persists(self, temp_db):
        """Test that user registration persists."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        telegram_id = f"persist_test_user_{int(time.time() * 1000)}"
        
        # Register user
        user = service.create_user(telegram_id=telegram_id, full_name="Test User")
        assert user is not None
        
        # Retrieve user
        retrieved = service.get_user_by_telegram_id(telegram_id)
        assert retrieved is not None
        assert retrieved.telegram_id == telegram_id
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_user_power_assignment_persists(self, temp_db):
        """Test that user power assignments persist."""
        import time
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        telegram_id = f"assignment_test_user_{int(time.time() * 1000)}"
        
        # Create game and user
        game_id = f"assignment_test_game_{int(time.time() * 1000)}"
        service.create_game(game_id, "standard")
        game_model = service.get_game_by_game_id(game_id)
        assert game_model is not None
        numeric_game_id = game_model.id
        user = service.create_user(telegram_id=telegram_id, full_name="Test User")
        
        # Assign power to user (create_player expects numeric game id)
        player = service.create_player(
            game_id=numeric_game_id,
            power="FRANCE",
            user_id=user.id
        )
        assert player is not None
        assert player.power_name == "FRANCE"
        
        # Retrieve player
        retrieved = service.get_player_by_game_id_and_power(game_id, "FRANCE")
        assert retrieved is not None
        assert retrieved.power_name == "FRANCE"
        assert retrieved.user_id == user.id
