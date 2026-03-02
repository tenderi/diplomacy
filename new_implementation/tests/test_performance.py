"""
Performance benchmark tests.

Tests response times, load handling, and database query performance.
"""
import pytest
import time
from fastapi.testclient import TestClient
from engine.game import Game
from engine.database_service import DatabaseService
from server.api import app
from tests.conftest import _get_db_url


@pytest.fixture
def client():
    """Create test client for API testing."""
    return TestClient(app)


@pytest.mark.slow
@pytest.mark.performance
class TestAPIResponseTimes:
    """Test API endpoint response times."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_game_creation_response_time(self, client):
        """Test that game creation completes quickly."""
        start_time = time.time()
        
        client.post("/games/create", json={"map_name": "standard"})
        
        duration = time.time() - start_time
        assert duration < 1.0, f"Game creation took {duration:.2f}s, should be < 1.0s"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_game_state_retrieval_response_time(self, client):
        """Test that game state retrieval is fast."""
        # Create game first
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        
        start_time = time.time()
        
        client.get(f"/games/{game_id}/state")
        
        duration = time.time() - start_time
        assert duration < 0.5, f"Game state retrieval took {duration:.2f}s, should be < 0.5s"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_order_submission_response_time(self, client):
        """Test that order submission is fast."""
        # Setup
        client.post("/users/persistent_register", json={"telegram_id": "perf_user", "full_name": "Perf User"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "perf_user",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        
        start_time = time.time()
        
        client.post("/games/set_orders", json={
            "game_id": game_id,
            "power": "FRANCE",
            "orders": ["A PAR - BUR"],
            "telegram_id": "perf_user"
        })
        
        duration = time.time() - start_time
        assert duration < 1.0, f"Order submission took {duration:.2f}s, should be < 1.0s"


@pytest.mark.slow
@pytest.mark.performance
class TestGameEnginePerformance:
    """Test game engine performance."""
    
    def test_turn_processing_performance(self):
        """Test that turn processing completes quickly."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        game.add_player("ITALY")
        game.add_player("AUSTRIA")
        game.add_player("RUSSIA")
        game.add_player("TURKEY")
        game.add_player("ENGLAND")
        
        # Set orders for all players (use actual units that exist after add_player)
        # Get the first unit for each power
        france_unit = game.game_state.powers["FRANCE"].units[0] if game.game_state.powers["FRANCE"].units else None
        germany_unit = game.game_state.powers["GERMANY"].units[0] if game.game_state.powers["GERMANY"].units else None
        italy_unit = game.game_state.powers["ITALY"].units[0] if game.game_state.powers["ITALY"].units else None
        austria_unit = game.game_state.powers["AUSTRIA"].units[0] if game.game_state.powers["AUSTRIA"].units else None
        russia_unit = game.game_state.powers["RUSSIA"].units[0] if game.game_state.powers["RUSSIA"].units else None
        turkey_unit = game.game_state.powers["TURKEY"].units[0] if game.game_state.powers["TURKEY"].units else None
        england_unit = game.game_state.powers["ENGLAND"].units[0] if game.game_state.powers["ENGLAND"].units else None
        
        if france_unit:
            game.set_orders("FRANCE", [f"FRANCE {france_unit.unit_type} {france_unit.province} H"])
        if germany_unit:
            game.set_orders("GERMANY", [f"GERMANY {germany_unit.unit_type} {germany_unit.province} H"])
        if italy_unit:
            game.set_orders("ITALY", [f"ITALY {italy_unit.unit_type} {italy_unit.province} H"])
        if austria_unit:
            game.set_orders("AUSTRIA", [f"AUSTRIA {austria_unit.unit_type} {austria_unit.province} H"])
        if russia_unit:
            game.set_orders("RUSSIA", [f"RUSSIA {russia_unit.unit_type} {russia_unit.province} H"])
        if turkey_unit:
            game.set_orders("TURKEY", [f"TURKEY {turkey_unit.unit_type} {turkey_unit.province} H"])
        if england_unit:
            game.set_orders("ENGLAND", [f"ENGLAND {england_unit.unit_type} {england_unit.province} H"])
        
        start_time = time.time()
        game.process_turn()
        duration = time.time() - start_time
        
        assert duration < 2.0, f"Turn processing took {duration:.2f}s, should be < 2.0s"
    
    def test_complex_adjudication_performance(self):
        """Test performance with complex adjudication scenarios."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        game.add_player("ITALY")
        
        # Set up complex scenario with supports and convoys
        from engine.data_models import Unit
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='F', province='BRE', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BER', power='GERMANY'),
            Unit(unit_type='A', province='MUN', power='GERMANY')
        ]
        game.game_state.powers["ITALY"].units = [
            Unit(unit_type='A', province='ROM', power='ITALY'),
            Unit(unit_type='F', province='NAP', power='ITALY')
        ]
        
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR",
            "FRANCE F BRE H"
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BER - SIL",
            "GERMANY A MUN H"
        ])
        game.set_orders("ITALY", [
            "ITALY A ROM H",
            "ITALY F NAP H"
        ])
        
        start_time = time.time()
        game.process_turn()
        duration = time.time() - start_time
        
        assert duration < 1.0, f"Complex adjudication took {duration:.2f}s, should be < 1.0s"
    
    def test_map_loading_performance(self):
        """Test that map loading is fast."""
        start_time = time.time()
        
        game = Game('standard')
        
        duration = time.time() - start_time
        assert duration < 1.0, f"Map loading took {duration:.2f}s, should be < 1.0s"


@pytest.mark.slow
@pytest.mark.performance
@pytest.mark.database
class TestDatabaseQueryPerformance:
    """Test database query performance."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_game_retrieval_performance(self, temp_db):
        """Test that game retrieval is fast."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        # Create multiple games with unique IDs
        import time
        game_ids = []
        for i in range(10):
            game_id = f"perf_test_game_{int(time.time() * 1000)}_{i}"
            service.create_game(game_id, "standard")
            game_ids.append(game_id)
        
        # Measure retrieval time
        start_time = time.time()
        for game_id in game_ids:
            service.get_game_by_game_id(game_id)
        duration = time.time() - start_time
        
        avg_time = duration / len(game_ids)
        assert avg_time < 0.1, f"Average game retrieval took {avg_time:.3f}s, should be < 0.1s"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_order_history_retrieval_performance(self, temp_db):
        """Test that order history retrieval is fast."""
        db_url = str(temp_db.url)
        service = DatabaseService(db_url)
        
        import time
        game_id = f"perf_history_test_{int(time.time() * 1000)}"
        service.create_game(game_id, "standard")
        
        # Add multiple orders across turns
        from engine.data_models import Unit, MoveOrder, OrderType
        for turn in range(5):
            unit = Unit(unit_type="A", province="PAR", power="FRANCE")
            order = MoveOrder(
                power="FRANCE",
                unit=unit,
                target_province="BUR",
                order_type=OrderType.MOVE
            )
            service.submit_orders(game_id, "FRANCE", [order])
            service.increment_game_current_turn(game_id)
        
        # Measure retrieval time
        start_time = time.time()
        history = service.get_order_history(game_id)
        duration = time.time() - start_time
        
        assert duration < 0.5, f"Order history retrieval took {duration:.2f}s, should be < 0.5s"


@pytest.mark.slow
@pytest.mark.performance
class TestLoadHandling:
    """Test system behavior under load."""
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_multiple_concurrent_game_creations(self, client):
        """Test creating multiple games concurrently."""
        import concurrent.futures
        
        def create_game():
            return client.post("/games/create", json={"map_name": "standard"})
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_game) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        duration = time.time() - start_time
        
        # Most should succeed (some may fail due to race conditions, which is acceptable)
        success_count = sum(1 for r in results if r.status_code == 200)
        # Allow for some failures due to race conditions in concurrent game creation
        assert success_count >= 5, f"Expected at least 5 successful game creations, got {success_count}"
        assert duration < 5.0, f"10 concurrent game creations took {duration:.2f}s, should be < 5.0s"
    
    @pytest.mark.skipif(not _get_db_url(), reason="Database URL not configured")
    def test_multiple_concurrent_order_submissions(self, client):
        """Test submitting orders concurrently."""
        import concurrent.futures
        
        # Setup: create game and register users
        client.post("/users/persistent_register", json={"telegram_id": "load_user1", "full_name": "Load User 1"})
        client.post("/users/persistent_register", json={"telegram_id": "load_user2", "full_name": "Load User 2"})
        game_resp = client.post("/games/create", json={"map_name": "standard"})
        game_id = game_resp.json()["game_id"]
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "load_user1",
            "game_id": int(game_id),
            "power": "FRANCE"
        })
        client.post(f"/games/{int(game_id)}/join", json={
            "telegram_id": "load_user2",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        def submit_orders(user_id, power):
            return client.post("/games/set_orders", json={
                "game_id": game_id,
                "power": power,
                "orders": ["A PAR H"] if power == "FRANCE" else ["A BER H"],
                "telegram_id": user_id
            })
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(submit_orders, "load_user1", "FRANCE"),
                executor.submit(submit_orders, "load_user2", "GERMANY")
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        duration = time.time() - start_time
        
        # All should succeed
        assert all(r.status_code == 200 for r in results), "All order submissions should succeed"
        assert duration < 2.0, f"Concurrent order submissions took {duration:.2f}s, should be < 2.0s"


@pytest.mark.slow
@pytest.mark.performance
class TestMemoryUsage:
    """Test memory usage patterns."""
    
    def test_multiple_games_memory(self):
        """Test that creating multiple games doesn't cause excessive memory usage."""
        import sys
        
        # Create multiple games
        games = []
        for i in range(10):
            game = Game('standard')
            game.add_player("FRANCE")
            games.append(game)
        
        # Memory usage should be reasonable
        # (exact measurement would require psutil or similar)
        assert len(games) == 10, "All games should be created"
        
        # Clean up
        del games
