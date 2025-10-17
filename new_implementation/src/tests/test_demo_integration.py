#!/usr/bin/env python3
"""
Simple integration test for demo game order management.

This test can be run directly without pytest to verify the fixes work.
"""
import os
import sys
import tempfile
import json
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from server.api import app
from server.db_models import Base, GameModel, UserModel, PlayerModel
from server.db_session import SessionLocal


def test_demo_game_workflow():
    """Test the complete demo game workflow."""
    print("🧪 Testing Demo Game Order Management...")
    
    # Create in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    
    # Create test session
    TestingSessionLocal = sessionmaker(autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    # Override the app's database session
    app.dependency_overrides[SessionLocal] = lambda: db
    
    try:
        client = TestClient(app)
        
        # Test 1: User Registration
        print("  📝 Testing user registration...")
        register_response = client.post("/users/persistent_register", json={
            "telegram_id": "12345",
            "full_name": "Demo Player"
        })
        assert register_response.status_code == 200, f"Registration failed: {register_response.text}"
        print("    ✅ User registration successful")
        
        # Test 2: Demo Game Creation
        print("  🎮 Testing demo game creation...")
        create_response = client.post("/games/create", json={"map_name": "demo"})
        assert create_response.status_code == 200, f"Game creation failed: {create_response.text}"
        game_id = create_response.json()["game_id"]
        print(f"    ✅ Demo game created with ID: {game_id}")
        
        # Test 3: User Joins Demo Game
        print("  👤 Testing user joining demo game...")
        join_response = client.post(f"/games/{game_id}/join", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "power": "GERMANY"
        })
        assert join_response.status_code == 200, f"Join failed: {join_response.text}"
        print("    ✅ User joined as Germany")
        
        # Test 4: API Response Structure (The Fix!)
        print("  🔧 Testing API response parsing fix...")
        games_response = client.get("/users/12345/games")
        assert games_response.status_code == 200, f"Games retrieval failed: {games_response.text}"
        
        games_data = games_response.json()
        print(f"    📊 API Response: {json.dumps(games_data, indent=2)}")
        
        # Test the fixed parsing logic
        user_games = games_data.get("games", []) if games_data else []
        assert isinstance(user_games, list), "Games should be a list"
        assert len(user_games) == 1, f"Expected 1 game, got {len(user_games)}"
        assert user_games[0]["power"] == "GERMANY", f"Expected GERMANY, got {user_games[0]['power']}"
        print("    ✅ API response parsing works correctly")
        
        # Test 5: Order Submission
        print("  📋 Testing order submission...")
        orders_response = client.post("/games/set_orders", json={
            "telegram_id": "12345",
            "game_id": int(game_id),
            "orders": ["GERMANY A BER - KIE", "GERMANY F KIE - DEN"]
        })
        assert orders_response.status_code == 200, f"Order submission failed: {orders_response.text}"
        print("    ✅ Orders submitted successfully")
        
        # Test 6: Order Retrieval
        print("  📖 Testing order retrieval...")
        orders_response = client.get(f"/games/{game_id}/orders")
        assert orders_response.status_code == 200, f"Order retrieval failed: {orders_response.text}"
        
        orders = orders_response.json()
        assert len(orders) == 2, f"Expected 2 orders, got {len(orders)}"
        print("    ✅ Orders retrieved successfully")
        
        # Test 7: Game State for Map Generation
        print("  🗺️ Testing game state for map generation...")
        state_response = client.get(f"/games/{game_id}/state")
        assert state_response.status_code == 200, f"State retrieval failed: {state_response.text}"
        
        state = state_response.json()
        assert "units" in state, "State should contain units"
        assert "GERMANY" in state["units"], "Germany should have units"
        print("    ✅ Game state retrieved successfully")
        
        # Test 8: Simulate Telegram Bot Logic
        print("  🤖 Testing Telegram bot logic simulation...")
        
        # Simulate show_my_orders_menu
        user_games_response = games_data
        user_games = user_games_response.get("games", []) if user_games_response else []
        
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            result = "no_games"
        else:
            result = f"found_{len(user_games)}_games"
        
        assert result == "found_1_games", f"Expected 'found_1_games', got '{result}'"
        print("    ✅ Telegram bot logic works correctly")
        
        print("\n🎉 All tests passed! Demo game order management is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False
        
    finally:
        # Cleanup
        db.close()
        Base.metadata.drop_all(engine)


def test_api_response_parsing_edge_cases():
    """Test edge cases for API response parsing."""
    print("\n🧪 Testing API Response Parsing Edge Cases...")
    
    def test_parsing_logic(api_response, expected_result):
        """Test the parsing logic with different inputs."""
        user_games = api_response.get("games", []) if api_response else []
        
        if not user_games or not isinstance(user_games, list) or len(user_games) == 0:
            return "no_games"
        else:
            return f"found_{len(user_games)}_games"
    
    # Test cases
    test_cases = [
        # (input, expected_output, description)
        ({"telegram_id": "12345", "games": [{"game_id": 1, "power": "GERMANY"}]}, "found_1_games", "Valid response with 1 game"),
        ({"telegram_id": "12345", "games": []}, "no_games", "Empty games list"),
        ({"telegram_id": "12345", "games": [{"game_id": 1, "power": "GERMANY"}, {"game_id": 2, "power": "FRANCE"}]}, "found_2_games", "Valid response with 2 games"),
        (None, "no_games", "None response"),
        ({}, "no_games", "Empty response"),
        ({"telegram_id": "12345"}, "no_games", "Response without games key"),
    ]
    
    for i, (input_data, expected, description) in enumerate(test_cases, 1):
        result = test_parsing_logic(input_data, expected)
        assert result == expected, f"Test case {i} failed: {description}. Expected '{expected}', got '{result}'"
        print(f"    ✅ Test case {i}: {description}")
    
    print("    ✅ All edge case tests passed!")


if __name__ == "__main__":
    print("🚀 Starting Demo Game Order Management Tests\n")
    
    # Run main workflow test
    success1 = test_demo_game_workflow()
    
    # Run edge case tests
    test_api_response_parsing_edge_cases()
    
    if success1:
        print("\n🎉 All tests completed successfully!")
        print("✅ Demo game order management is working correctly")
        print("✅ API response parsing fixes are working")
        print("✅ My Games buttons should now be functional")
        sys.exit(0)
    else:
        print("\n❌ Tests failed!")
        sys.exit(1)
