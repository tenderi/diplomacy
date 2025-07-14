"""
Advanced server tests for multiple concurrent games, isolation, and new commands.
"""
import os
import tempfile
from typing import List
from .server import Server


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
    server.process_command(f"PROCESS_TURN {game1_id}")
    
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
    assert "Usage: REMOVE_PLAYER" in result["message"]
    
    result = server.process_command("REMOVE_PLAYER 1")
    assert result["status"] == "error"
    assert "Usage: REMOVE_PLAYER" in result["message"]
    
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
    result = server.process_command(f"ADVANCE_PHASE {game_id}")
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
    assert "Usage: ADVANCE_PHASE" in result["message"]
    
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
    server.process_command(f"PROCESS_TURN {game1_id}")
    server.process_command(f"PROCESS_TURN {game1_id}")  # Process twice
    
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
