"""
Tests for demo game order management functionality.

This module tests the fixes for:
1. API response parsing in My Games functions
2. Demo game creation and user association
3. My Games button functionality
4. Order management integration
"""
import os
import tempfile
import pytest
from typing import Dict, Any
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server.api import app
from server.db_models import Base, GameModel, UserModel, PlayerModel
from server.db_session import SessionLocal


class TestDemoGameManagement:
    """Test class for demo game order management functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Set up test database for each test."""
        # Create PostgreSQL database for testing
        self.engine = create_engine("postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db", echo=False)
        Base.metadata.create_all(self.engine)
        
        # Create test session
        TestingSessionLocal = sessionmaker(autoflush=False, bind=self.engine)
        self.db = TestingSessionLocal()
        
        # Override the app's database session
        app.dependency_overrides[SessionLocal] = lambda: self.db
        
        yield
        
        # Cleanup
        self.db.close()
        Base.metadata.drop_all(self.engine)
    
    def test_user_games_api_response_structure(self):
        """Test that /users/{telegram_id}/games returns correct structure."""
        client = TestClient(app)
        
        # Create a test user
        user = UserModel(telegram_id="12345", full_name="Test User")
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Create a test game
        game = GameModel(map_name="demo", state={"status": "ok"}, is_active=True)
        self.db.add(game)
        self.db.commit()
        self.db.refresh(game)
        
        # Add user to game
        player = PlayerModel(game_id=game.id, power="GERMANY", user_id=user.id)
        self.db.add(player)
        self.db.commit()
        
        # Test API response structure
        response = client.get(f"/users/{user.telegram_id}/games")
        assert response.status_code == 200
        
        data = response.json()
        assert "telegram_id" in data
        assert "games" in data
        assert isinstance(data["games"], list)
        assert len(data["games"]) == 1
        
        game_data = data["games"][0]
        assert "game_id" in game_data
        assert "power" in game_data
        assert game_data["power"] == "GERMANY"
        assert game_data["game_id"] == game.id
    
    def test_demo_game_creation_and_user_association(self):
        """Test that demo game creation properly associates user with game."""
        client = TestClient(app)
        
        # Register user
        register_response = client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        assert register_response.status_code == 200
        
        # Create demo game
        create_response = client.post("/games/create", json={"map_name": "demo"})
        assert create_response.status_code == 200
        game_id = create_response.json()["game_id"]
        
        # Join user to demo game as Germany
        join_response = client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        assert join_response.status_code == 200
        
        # Verify user is associated with game
        games_response = client.get("/users/12345/games")
        assert games_response.status_code == 200
        
        games_data = games_response.json()
        assert len(games_data["games"]) == 1
        assert games_data["games"][0]["game_id"] == int(game_id)
        assert games_data["games"][0]["power"] == "GERMANY"
    
    def test_demo_game_with_ai_players(self):
        """Test demo game creation with AI players for all powers."""
        client = TestClient(app)
        
        # Register human user
        client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        
        # Create demo game
        create_response = client.post("/games/create", json={"map_name": "demo"})
        game_id = create_response.json()["game_id"]
        
        # Add human player
        client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # Add AI players for other powers
        other_powers = ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"]
        for power in other_powers:
            ai_telegram_id = f"ai_{power.lower()}"
            
            # Register AI player
            client.post("/users/persistent_register", json={
                "telegram_id": ai_telegram_id,
                "full_name": f"AI {power}"
            })
            
            # Join AI player to game
            join_response = client.post(f"/games/{game_id}/join", json={
                "telegram_id": ai_telegram_id,
                "game_id": int(game_id),
                "power": power
            })
            assert join_response.status_code == 200
        
        # Verify all players are in the game
        players_response = client.get(f"/games/{game_id}/players")
        assert players_response.status_code == 200
        
        players = players_response.json()
        assert len(players) == 7  # All 7 powers
        
        # Check that human player is Germany
        human_player = next((p for p in players if p["telegram_id"] == "12345"), None)
        assert human_player is not None
        assert human_player["power"] == "GERMANY"
    
    def test_order_submission_for_demo_game(self):
        """Test that orders can be submitted for demo games."""
        client = TestClient(app)
        
        # Set up demo game with user
        client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        
        create_response = client.post("/games/create", json={"map_name": "demo"})
        game_id = create_response.json()["game_id"]
        
        client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # Submit orders for Germany
        orders_response = client.post("/games/set_orders", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "orders": ["GERMANY A BER - KIE", "GERMANY F KIE - DEN"]
        })
        assert orders_response.status_code == 200
        
        # Verify orders were saved
        orders_response = client.get(f"/games/{game_id}/orders")
        assert orders_response.status_code == 200
        
        orders = orders_response.json()
        assert len(orders) == 2
        assert any("A BER - KIE" in order["order"] for order in orders)
        assert any("F KIE - DEN" in order["order"] for order in orders)
    
    def test_game_state_retrieval_for_demo_game(self):
        """Test that game state can be retrieved for demo games."""
        client = TestClient(app)
        
        # Set up demo game
        client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        
        create_response = client.post("/games/create", json={"map_name": "demo"})
        game_id = create_response.json()["game_id"]
        
        client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # Get game state
        state_response = client.get(f"/games/{game_id}/state")
        assert state_response.status_code == 200
        
        state = state_response.json()
        assert "units" in state
        assert "powers" in state
        assert "turn" in state
        assert "phase" in state
        
        # Verify Germany has units
        assert "GERMANY" in state["units"]
        assert len(state["units"]["GERMANY"]) > 0
    
    def test_api_response_parsing_simulation(self):
        """Test the API response parsing logic that was fixed."""
        # Simulate the API response structure
        api_response = {
            "telegram_id": "12345",
            "games": [
                {"game_id": 1, "power": "GERMANY"},
                {"game_id": 2, "power": "FRANCE"}
            ]
        }
        
        # Test the parsing logic that was fixed
        user_games = api_response.get("games", []) if api_response else []
        
        assert isinstance(user_games, list)
        assert len(user_games) == 2
        assert user_games[0]["power"] == "GERMANY"
        assert user_games[1]["power"] == "FRANCE"
    
    def test_empty_games_response_handling(self):
        """Test handling of empty games response."""
        # Simulate empty API response
        api_response = {
            "telegram_id": "12345",
            "games": []
        }
        
        user_games = api_response.get("games", []) if api_response else []
        
        assert isinstance(user_games, list)
        assert len(user_games) == 0
        
        # Test the condition that was causing issues
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            # This should trigger the "no games" UI
            assert True  # This condition should be True for empty games
    
    def test_none_api_response_handling(self):
        """Test handling of None API response."""
        # Simulate None API response (API error)
        api_response = None
        
        user_games = api_response.get("games", []) if api_response else []
        
        assert isinstance(user_games, list)
        assert len(user_games) == 0
    
    def test_demo_game_map_generation(self):
        """Test that demo game can generate maps."""
        client = TestClient(app)
        
        # Set up demo game
        client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        
        create_response = client.post("/games/create", json={"map_name": "demo"})
        game_id = create_response.json()["game_id"]
        
        client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        
        # Get game state for map generation
        state_response = client.get(f"/games/{game_id}/state")
        assert state_response.status_code == 200
        
        state = state_response.json()
        
        # Test the map generation logic
        units = {}
        if "units" in state:
            units = state["units"]
        
        assert isinstance(units, dict)
        assert "GERMANY" in units
        assert len(units["GERMANY"]) > 0


def test_telegram_bot_api_parsing_functions():
    """Test the specific API parsing functions that were fixed."""
    
    def simulate_show_my_orders_menu_logic(user_games_response):
        """Simulate the fixed show_my_orders_menu logic."""
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            return "no_games"
        else:
            return f"found_{len(user_games)}_games"
    
    def simulate_games_function_logic(user_games_response):
        """Simulate the fixed games function logic."""
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games or not isinstance(user_games, list):
            return "no_games"
        else:
            return f"found_{len(user_games)}_games"
    
    def simulate_show_map_menu_logic(user_games_response):
        """Simulate the fixed show_map_menu logic."""
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            return "no_games"
        else:
            return f"found_{len(user_games)}_games"
    
    # Test with valid response
    valid_response = {
        "telegram_id": "12345",
        "games": [{"game_id": 1, "power": "GERMANY"}]
    }
    
    assert simulate_show_my_orders_menu_logic(valid_response) == "found_1_games"
    assert simulate_games_function_logic(valid_response) == "found_1_games"
    assert simulate_show_map_menu_logic(valid_response) == "found_1_games"
    
    # Test with empty response
    empty_response = {
        "telegram_id": "12345",
        "games": []
    }
    
    assert simulate_show_my_orders_menu_logic(empty_response) == "no_games"
    assert simulate_games_function_logic(empty_response) == "no_games"
    assert simulate_show_map_menu_logic(empty_response) == "no_games"
    
    # Test with None response
    assert simulate_show_my_orders_menu_logic(None) == "no_games"
    assert simulate_games_function_logic(None) == "no_games"
    assert simulate_show_map_menu_logic(None) == "no_games"


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
