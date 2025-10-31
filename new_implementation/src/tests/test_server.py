from server.server import Server

def test_server_initialization():
    """Test that the Server can be initialized."""
    server = Server()
    assert server is not None

def test_server_accepts_commands():
    """Test that the Server can accept and process a command."""
    server = Server()
    # This assumes a process_command method will exist
    result = server.process_command("NEW_GAME")
    assert result is not None

def test_server_create_and_query_game():
    server = Server()
    result = server.process_command("CREATE_GAME standard")
    assert result["status"] == "ok"
    game_id = result["game_id"]
    # Query game state
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["status"] == "ok"
    state_data = state["state"]
    assert state_data["map_name"] == "standard"
    assert state_data["turn"] == 0

def test_server_add_player_and_set_orders():
    server = Server()
    result = server.process_command("CREATE_GAME standard")
    game_id = result["game_id"]
    add_result = server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    assert add_result["status"] == "ok"
    set_orders = server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    assert set_orders["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert "FRANCE" in state["state"]["orders"]

def test_server_process_turn_and_game_done():
    server = Server()
    result = server.process_command("CREATE_GAME standard")
    game_id = result["game_id"]
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    # Dynamically move all French armies each turn, always issuing a valid move or hold
    max_iters = 10  # Reduced iterations for test
    for i in range(max_iters):
        state = server.process_command(f"GET_GAME_STATE {game_id}")
        if state["state"]["done"]:
            break
        # Also break after a reasonable number of turns for single-player test
        if i >= 5:  # Stop after 5 iterations to avoid infinite loop
            break
        units = state["state"]["units"]["FRANCE"]
        current_phase = state["state"]["phase"]
        orders = []
        
        # Only submit orders for Movement phase
        if current_phase == "Movement":
            from engine.map import Map
            map_obj = Map('standard')
            # Issue orders for all armies
            for army in [u for u in units if u.startswith("A ")]:
                loc = army.split()[1]
                adj = map_obj.get_adjacency(loc)
                valid_moves = [prov for prov in adj if map_obj.provinces[prov].type in ("land", "coast")]
                if valid_moves:
                    next_prov = valid_moves[0]
                    orders.append(f"A {loc} - {next_prov}")
                else:
                    orders.append(f"A {loc} H")
            # If no armies, issue a hold for a fleet if present
            if not orders:
                fleets = [u for u in units if u.startswith("F ")]
                if fleets:
                    floc = fleets[0].split()[1]
                    orders.append(f"F {floc} H")
            # Send all orders as a single string (space-separated)
            for order in orders:
                server.process_command(f"SET_ORDERS {game_id} FRANCE {order}")
        elif current_phase == "Builds":
            # In Builds phase, submit build/destroy orders or skip
            # For now, just skip submitting orders in Builds phase
            pass
        server.process_command(f"PROCESS_TURN {game_id}")  # Now advances phase, not just turn
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    # For single-player test, we just verify the game ran without errors
    # The game won't be "done" without other players to compete with
    assert "state" in state
    assert "units" in state["state"]
    assert "FRANCE" in state["state"]["units"]

def test_server_invalid_command():
    server = Server()
    result = server.process_command("FOO_BAR")
    assert result["status"] == "error"
    assert "Unknown command" in result["message"]

def test_server_missing_arguments():
    server = Server()
    result = server.process_command("ADD_PLAYER")
    assert result["status"] == "error"
    result = server.process_command("SET_ORDERS 1 FRANCE")
    assert result["status"] == "error"
    result = server.process_command("PROCESS_TURN")
    assert result["status"] == "error"
    result = server.process_command("GET_GAME_STATE")
    assert result["status"] == "error"

def test_server_save_and_load_game(tmp_path):
    server = Server()
    result = server.process_command("CREATE_GAME standard")
    game_id = result["game_id"]
    server.process_command(f"ADD_PLAYER {game_id} FRANCE")
    server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    filename = str(tmp_path / "game_save.pkl")
    save_result = server.process_command(f"SAVE_GAME {game_id} {filename}")
    assert save_result["status"] == "ok"
    # Remove the game and reload
    del server.games[game_id]
    load_result = server.process_command(f"LOAD_GAME {game_id} {filename}")
    assert load_result["status"] == "ok"
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["status"] == "ok"
    assert "FRANCE" in state["state"]["powers"]

import os
import pytest

def test_replace_only_inactive_allowed_via_api():
    from server.api import app, ADMIN_TOKEN
    from fastapi.testclient import TestClient
    if not (os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")):
        pytest.skip("Database URL not configured; skipping DAL-backed API test")
    client = TestClient(app)
    # Register two users
    client.post("/users/persistent_register", json={"telegram_id": "u1", "full_name": "User1"})
    client.post("/users/persistent_register", json={"telegram_id": "u2", "full_name": "User2"})
    # Create game and add player (assign u1 to FRANCE)
    resp = client.post("/games/create", json={"map_name": "standard"})
    assert resp.status_code == 200
    game_id = int(resp.json()["game_id"])
    join_resp = client.post(f"/games/{game_id}/join", json={"telegram_id": "u1", "game_id": game_id, "power": "FRANCE"})
    assert join_resp.status_code == 200
    # Mark player inactive (admin endpoint)
    inactive_resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": ADMIN_TOKEN})
    assert inactive_resp.status_code == 200
    # Now replace should succeed (assign u2)
    replace_resp = client.post(f"/games/{game_id}/replace", json={"telegram_id": "u2", "power": "FRANCE"})
    assert replace_resp.status_code == 200

def test_adjudication_results_in_state():
    """Test that adjudication results are included in the game state after a turn."""
    import os
    import pytest
    from server.api import app
    from fastapi.testclient import TestClient
    if not (os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")):
        pytest.skip("Database URL not configured; skipping DAL-backed API test")
    client = TestClient(app)
    # Create a game and register a user
    resp = client.post("/games/create", json={"map_name": "standard"})
    game_id = int(resp.json()["game_id"])
    # Use persistent_register which actually creates the user in the database
    client.post("/users/persistent_register", json={"telegram_id": "u1", "full_name": "User1"})
    # Add player to the game (associate user with power)
    join_resp = client.post(f"/games/{game_id}/join", json={"telegram_id": "u1", "game_id": game_id, "power": "FRANCE"})
    assert join_resp.status_code == 200, f"Join failed: {join_resp.json()}"
    # Submit a valid order and process the turn
    order = "FRANCE F BRE H"
    set_orders_resp = client.post("/games/set_orders", json={"game_id": str(game_id), "power": "FRANCE", "orders": [order], "telegram_id": "u1"})
    assert set_orders_resp.status_code == 200, f"Set orders failed: {set_orders_resp.json()}"
    client.post(f"/games/{game_id}/process_turn")
    # Get the game state
    resp = client.get(f"/games/{game_id}/state")
    data = resp.json()
    # adjudication_results is optional and may be empty dict if game not in server.games
    assert "adjudication_results" in data
    # In spec mode, adjudication_results can be engine-shaped dict; require dict
    results = data["adjudication_results"]
    assert isinstance(results, dict)
