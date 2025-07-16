"""
Advanced server tests for multiple concurrent games, isolation, and new commands.
"""
import os
import tempfile
from typing import List
from .server import Server
from fastapi.testclient import TestClient
from server.api import app


def test_multiple_concurrent_games() -> None:
    """Test that the server can handle multiple concurrent games independently."""
    server = Server()
    
    # Create multiple games
    game1 = server.process_command("CREATE_GAME standard")
    game2 = server.process_command("CREATE_GAME standard")
    game3 = server.process_command("CREATE_GAME standard")
    
    assert game1["status"] == "ok"
    assert game2["status"] == "ok"
    assert game3["status"] == "ok"
    
    game1_id = game1["game_id"]
    game2_id = game2["game_id"]
    game3_id = game3["game_id"]
    
    # Verify games have different IDs
    assert game1_id != game2_id != game3_id
    
    # Add players to different games
    server.process_command(f"ADD_PLAYER {game1_id} FRANCE")
    server.process_command(f"ADD_PLAYER {game1_id} GERMANY")
    
    server.process_command(f"ADD_PLAYER {game2_id} ENGLAND")
    server.process_command(f"ADD_PLAYER {game2_id} RUSSIA")
    
    server.process_command(f"ADD_PLAYER {game3_id} ITALY")
    server.process_command(f"ADD_PLAYER {game3_id} AUSTRIA")
    
    # Verify game isolation - each game should have its own players
    state1 = server.process_command(f"GET_GAME_STATE {game1_id}")
    state2 = server.process_command(f"GET_GAME_STATE {game2_id}")
    state3 = server.process_command(f"GET_GAME_STATE {game3_id}")
    
    assert "FRANCE" in state1["state"]["powers"]
    assert "GERMANY" in state1["state"]["powers"]
    assert "ENGLAND" not in state1["state"]["powers"]
    
    assert "ENGLAND" in state2["state"]["powers"]
    assert "RUSSIA" in state2["state"]["powers"]
    assert "FRANCE" not in state2["state"]["powers"]
    
    assert "ITALY" in state3["state"]["powers"]
    assert "AUSTRIA" in state3["state"]["powers"]
    assert "GERMANY" not in state3["state"]["powers"]


def test_game_isolation_with_orders() -> None:
    """Test that orders and turns in different games don't interfere."""
    server = Server()
    
    # Create two games
    game1 = server.process_command("CREATE_GAME standard")
    game2 = server.process_command("CREATE_GAME standard")
    
    game1_id = game1["game_id"]
    game2_id = game2["game_id"]
    
    # Add players
    server.process_command(f"ADD_PLAYER {game1_id} FRANCE")
    server.process_command(f"ADD_PLAYER {game2_id} FRANCE")
    
    # Set different orders in each game
    server.process_command(f"SET_ORDERS {game1_id} FRANCE A PAR - BUR")
    server.process_command(f"SET_ORDERS {game2_id} FRANCE A PAR - PIC")
    
    # Check that orders are isolated
    state1 = server.process_command(f"GET_GAME_STATE {game1_id}")
    state2 = server.process_command(f"GET_GAME_STATE {game2_id}")
    
    assert "A PAR - BUR" in state1["state"]["orders"]["FRANCE"]
    assert "A PAR - PIC" in state2["state"]["orders"]["FRANCE"]
    
    # Process turns independently
    server.process_command(f"PROCESS_TURN {game1_id}")  # Now advances phase, not just turn
    
    # Check that only game1 advanced
    state1_after = server.process_command(f"GET_GAME_STATE {game1_id}")
    state2_after = server.process_command(f"GET_GAME_STATE {game2_id}")
    
    assert state1_after["state"]["turn"] == 1
    assert state2_after["state"]["turn"] == 0


def test_remove_player_command() -> None:
    """Test REMOVE_PLAYER command functionality."""
    server = Server()
    
    # Create game and add players
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    server.process_command(f"ADD_PLAYER {game_id} GERMANY")
    server.process_command(f"ADD_PLAYER {game_id} ENGLAND")
    
    # Set orders for players
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    server.process_command(f"SET_ORDERS {game_id} GERMANY A BER - MUN")
    
    # Remove a player
    result = server.process_command(f"REMOVE_PLAYER {game_id} FRANCE")
    assert result["status"] == "ok"
    
    # Verify player is removed
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert "FRANCE" not in state["state"]["powers"]
    assert "GERMANY" in state["state"]["powers"]
    assert "ENGLAND" in state["state"]["powers"]
    
    # Verify orders are also removed
    assert "FRANCE" not in state["state"]["orders"]
    assert "GERMANY" in state["state"]["orders"]


def test_remove_player_error_cases() -> None:
    """Test error cases for REMOVE_PLAYER command."""
    server = Server()
    
    # Test missing arguments
    result = server.process_command("REMOVE_PLAYER")
    assert result["status"] == "error"
    assert "REMOVE_PLAYER missing arguments" in result["message"]
    
    result = server.process_command("REMOVE_PLAYER 1")
    assert result["status"] == "error"
    assert "REMOVE_PLAYER missing arguments" in result["message"]
    
    # Test non-existent game
    result = server.process_command("REMOVE_PLAYER 999 FRANCE")
    assert result["status"] == "error"
    assert "Game 999 not found" in result["message"]
    
    # Test non-existent player
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    
    result = server.process_command(f"REMOVE_PLAYER {game_id} NONEXISTENT")
    assert result["status"] == "error"
    assert "Power NONEXISTENT not found" in result["message"]


def test_advance_phase_command() -> None:
    """Test ADVANCE_PHASE command functionality."""
    server = Server()
    
    # Create game and add player
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    
    # Check initial state
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["state"]["turn"] == 0
    
    # Advance phase
    result = server.process_command(f"ADVANCE_PHASE {game_id}")  # Now advances phase using process_phase()
    assert result["status"] == "ok"
    
    # Check turn advanced
    state_after = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state_after["state"]["turn"] == 1


def test_advance_phase_error_cases() -> None:
    """Test error cases for ADVANCE_PHASE command."""
    server = Server()
    
    # Test missing arguments
    result = server.process_command("ADVANCE_PHASE")
    assert result["status"] == "error"
    assert "ADVANCE_PHASE missing arguments" in result["message"]
    
    # Test non-existent game
    result = server.process_command("ADVANCE_PHASE 999")
    assert result["status"] == "error"
    assert "Game 999 not found" in result["message"]


def test_game_state_isolation() -> None:
    """Test that game state changes don't affect other games."""
    server = Server()
    
    # Create multiple games
    game1 = server.process_command("CREATE_GAME standard")
    game2 = server.process_command("CREATE_GAME standard")
    game3 = server.process_command("CREATE_GAME standard")
    
    game1_id = game1["game_id"]
    game2_id = game2["game_id"]
    game3_id = game3["game_id"]
    
    # Add players and set orders
    for game_id in [game1_id, game2_id, game3_id]:
        server.process_command(f"ADD_PLAYER {game_id} FRANCE")
        server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    
    # Process turns for only some games
    server.process_command(f"PROCESS_TURN {game1_id}")  # Now advances phase, not just turn
    server.process_command(f"PROCESS_TURN {game1_id}")  # Process twice (phase advancement)
    
    # Check isolation
    state1 = server.process_command(f"GET_GAME_STATE {game1_id}")
    state2 = server.process_command(f"GET_GAME_STATE {game2_id}")
    state3 = server.process_command(f"GET_GAME_STATE {game3_id}")
    
    assert state1["state"]["turn"] == 2
    assert state2["state"]["turn"] == 0
    assert state3["state"]["turn"] == 0


def test_concurrent_game_limit() -> None:
    """Test that server can handle a reasonable number of concurrent games."""
    server = Server()
    
    # Create many games
    game_ids: List[str] = []
    for _ in range(50):  # Create 50 games
        game = server.process_command("CREATE_GAME standard")
        assert game["status"] == "ok"
        game_ids.append(game["game_id"])
    
    # Verify all games are unique and accessible
    assert len(set(game_ids)) == 50  # All unique IDs
    
    # Test that all games can be accessed
    for game_id in game_ids:
        state = server.process_command(f"GET_GAME_STATE {game_id}")
        assert state["status"] == "ok"
        assert state["state"]["turn"] == 0


def test_save_load_with_multiple_games() -> None:
    """Test saving and loading games with multiple concurrent games."""
    server = Server()
    
    # Create multiple games with different states
    game1 = server.process_command("CREATE_GAME standard")
    game2 = server.process_command("CREATE_GAME standard")
    
    game1_id = game1["game_id"]
    game2_id = game2["game_id"]
    
    # Setup different states
    server.process_command(f"ADD_PLAYER {game1_id} FRANCE")
    server.process_command(f"ADD_PLAYER {game2_id} GERMANY")
    
    server.process_command(f"SET_ORDERS {game1_id} FRANCE A PAR - BUR")
    server.process_command(f"SET_ORDERS {game2_id} GERMANY A BER - MUN")
    
    server.process_command(f"PROCESS_TURN {game1_id}")
    # game2 not processed, should remain at turn 0
    
    # Save both games
    with tempfile.TemporaryDirectory() as temp_dir:
        save_path1 = os.path.join(temp_dir, "game1.pkl")
        save_path2 = os.path.join(temp_dir, "game2.pkl")
        
        server.process_command(f"SAVE_GAME {game1_id} {save_path1}")
        server.process_command(f"SAVE_GAME {game2_id} {save_path2}")
        
        # Create new server and load games
        new_server = Server()
        new_server.process_command(f"LOAD_GAME {game1_id} {save_path1}")
        new_server.process_command(f"LOAD_GAME {game2_id} {save_path2}")
        
        # Verify states are preserved
        state1 = new_server.process_command(f"GET_GAME_STATE {game1_id}")
        state2 = new_server.process_command(f"GET_GAME_STATE {game2_id}")
        
        assert state1["state"]["turn"] == 1
        assert state2["state"]["turn"] == 0
        assert "FRANCE" in state1["state"]["powers"]
        assert "GERMANY" in state2["state"]["powers"]


def test_remove_last_player() -> None:
    """Test removing the last player from a game."""
    server = Server()
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    
    # Remove the only player
    result = server.process_command(f"REMOVE_PLAYER {game_id} FRANCE")
    assert result["status"] == "ok"
    
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert "FRANCE" not in state["state"]["powers"]
    # Accept both empty list and empty dict for legacy compatibility
    assert state["state"]["powers"] == [] or state["state"]["powers"] == {}
    assert state["state"]["orders"] == {}


def test_remove_player_with_pending_state() -> None:
    """Test removing a player with pending retreats/builds (should clean up all state)."""
    server = Server()
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    
    # Simulate pending retreat/build (mock by setting orders, as full retreat/build logic may be in engine)
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    result = server.process_command(f"REMOVE_PLAYER {game_id} FRANCE")
    assert result["status"] == "ok"
    
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert "FRANCE" not in state["state"]["powers"]
    assert "FRANCE" not in state["state"]["orders"]


def test_remove_player_twice() -> None:
    """Test removing a player twice returns an error the second time."""
    server = Server()
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    server.process_command(f"REMOVE_PLAYER {game_id} FRANCE")
    
    result = server.process_command(f"REMOVE_PLAYER {game_id} FRANCE")
    assert result["status"] == "error"
    assert "Power FRANCE not found" in result["message"]


def test_advance_phase_with_no_players() -> None:
    """Test advancing phase on a game with no players."""
    server = Server()
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    
    result = server.process_command(f"ADVANCE_PHASE {game_id}")
    # Should still succeed, but state should be empty
    assert result["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["state"]["turn"] == 1
    # Accept both empty list and empty dict for legacy compatibility
    assert state["state"]["powers"] == [] or state["state"]["powers"] == {}


def test_advance_phase_with_no_orders() -> None:
    """Test advancing phase when no orders are set (should not error)."""
    server = Server()
    game = server.process_command("CREATE_GAME standard")
    game_id = game["game_id"]
    
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    # Do not set any orders
    result = server.process_command(f"ADVANCE_PHASE {game_id}")
    assert result["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["state"]["turn"] == 1


def test_order_history_and_clearing():
    """Test order history API, order clearing, and turn-by-turn grouping."""
    client = TestClient(app)

    # Register users
    france_telegram_id = "1001"
    germany_telegram_id = "1002"
    client.post("/users/persistent_register", json={"telegram_id": france_telegram_id, "full_name": "France Player"})
    client.post("/users/persistent_register", json={"telegram_id": germany_telegram_id, "full_name": "Germany Player"})

    # Create game
    resp = client.post("/games/create", json={"map_name": "standard"})
    assert resp.status_code == 200
    game_id = str(resp.json()["game_id"])

    # Join players
    resp = client.post(f"/games/{game_id}/join", json={"telegram_id": france_telegram_id, "game_id": int(game_id), "power": "FRANCE"})
    assert resp.status_code == 200
    resp = client.post(f"/games/{game_id}/join", json={"telegram_id": germany_telegram_id, "game_id": int(game_id), "power": "GERMANY"})
    assert resp.status_code == 200

    # Submit orders for turn 0
    client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": france_telegram_id})
    client.post("/games/set_orders", json={"game_id": game_id, "power": "GERMANY", "orders": ["A MUN - RUH"], "telegram_id": germany_telegram_id})

    # Check order history for turn 0
    resp = client.get(f"/games/{game_id}/orders/history")
    assert resp.status_code == 200
    history = resp.json()["order_history"]
    assert "0" in history
    assert "FRANCE" in history["0"]
    assert "GERMANY" in history["0"]
    assert "A PAR - BUR" in history["0"]["FRANCE"]
    assert "A MUN - RUH" in history["0"]["GERMANY"]

    # Process turn (advance to turn 1)
    resp = client.post(f"/games/{game_id}/process_turn")
    assert resp.status_code == 200

    # Submit new orders for turn 1
    client.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A BUR - MUN"], "telegram_id": france_telegram_id})
    client.post("/games/set_orders", json={"game_id": game_id, "power": "GERMANY", "orders": ["A RUH - BUR"], "telegram_id": germany_telegram_id})

    # Check order history for turn 1
    resp = client.get(f"/games/{game_id}/orders/history")
    assert resp.status_code == 200
    history = resp.json()["order_history"]
    assert "1" in history
    assert "A BUR - MUN" in history["1"]["FRANCE"]
    assert "A RUH - BUR" in history["1"]["GERMANY"]

    # Clear FRANCE's orders for turn 1
    resp = client.post(f"/games/{game_id}/orders/FRANCE/clear", content=f'"{france_telegram_id}"', headers={"Content-Type": "application/json"})
    assert resp.status_code == 200
    # Check that FRANCE's orders for turn 1 are now empty
    resp = client.get(f"/games/{game_id}/orders/history")
    history = resp.json()["order_history"]
    assert "1" in history
    assert "FRANCE" not in history["1"] or not history["1"]["FRANCE"]
    # GERMANY's orders for turn 1 should remain
    assert "A RUH - BUR" in history["1"]["GERMANY"]


def test_persistent_user_registration_and_multi_game():
    client = TestClient(app)
    # Register user
    resp = client.post("/users/persistent_register", json={"telegram_id": "12345", "full_name": "Test User"})
    assert resp.status_code == 200
    # Create two games
    resp1 = client.post("/games/create", json={"map_name": "standard"})
    resp2 = client.post("/games/create", json={"map_name": "standard"})
    game_id1 = resp1.json()["game_id"]
    game_id2 = resp2.json()["game_id"]
    # Join both games as different powers
    resp = client.post(f"/games/{game_id1}/join", json={"telegram_id": "12345", "game_id": int(game_id1), "power": "FRANCE"})
    assert resp.status_code == 200
    resp = client.post(f"/games/{game_id2}/join", json={"telegram_id": "12345", "game_id": int(game_id2), "power": "GERMANY"})
    assert resp.status_code == 200
    # List user games
    resp = client.get("/users/12345/games")
    assert resp.status_code == 200
    games = resp.json()["games"]
    assert any(str(g["game_id"]) == str(game_id1) and g["power"] == "FRANCE" for g in games)
    assert any(str(g["game_id"]) == str(game_id2) and g["power"] == "GERMANY" for g in games)
    # Quit one game
    resp = client.post(f"/games/{game_id1}/quit", json={"telegram_id": "12345", "game_id": int(game_id1)})
    assert resp.status_code == 200
    # List user games again
    resp = client.get("/users/12345/games")
    games = resp.json()["games"]
    assert not any(str(g["game_id"]) == str(game_id1) for g in games)
    assert any(str(g["game_id"]) == str(game_id2) for g in games)
