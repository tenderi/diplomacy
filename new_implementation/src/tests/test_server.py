from src.server.server import Server

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
    assert state_data["map"] == "standard"
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
    max_iters = 50
    for _ in range(max_iters):
        state = server.process_command(f"GET_GAME_STATE {game_id}")
        if state["state"]["done"]:
            break
        units = state["state"]["units"]["FRANCE"]
        orders = []
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
        server.process_command(f"PROCESS_TURN {game_id}")  # Now advances phase, not just turn
    state = server.process_command(f"GET_GAME_STATE {game_id}")
    assert state["state"]["done"]

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

def test_replace_only_inactive_allowed():
    from server.api import app, ADMIN_TOKEN
    from server.db_session import SessionLocal
    from server.db_models import PlayerModel, UserModel
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    client = TestClient(app)
    db = SessionLocal()
    # Clean up orders, players, and users tables
    db.execute(text('DELETE FROM orders'))
    db.execute(text('DELETE FROM players'))
    db.execute(text('DELETE FROM users'))
    db.commit()
    # Register two users
    user1 = UserModel(telegram_id="u1", full_name="User1")
    user2 = UserModel(telegram_id="u2", full_name="User2")
    db.add(user1)
    db.add(user2)
    db.commit()
    db.refresh(user1)
    db.refresh(user2)
    # Create game and add player (vacated, active)
    resp = client.post("/games/create", json={"map_name": "standard"})
    game_id = int(resp.json()["game_id"])
    player = PlayerModel(game_id=game_id, power="FRANCE", user_id=None, is_active=True)
    db.add(player)
    db.commit()
    # Try to replace active player (should fail)
    resp = client.post(f"/games/{game_id}/replace", json={"telegram_id": "u2", "power": "FRANCE"})
    assert resp.status_code == 400
    assert "inactive" in resp.json()["detail"].lower() or "vacated" in resp.json()["detail"].lower() or "assigned" in resp.json()["detail"].lower()
    # Mark player inactive (admin endpoint)
    resp = client.post(f"/games/{game_id}/players/FRANCE/mark_inactive", json={"admin_token": ADMIN_TOKEN})
    assert resp.status_code == 200
    # Now replace should succeed
    resp = client.post(f"/games/{game_id}/replace", json={"telegram_id": "u2", "power": "FRANCE"})
    assert resp.status_code == 200
    # Check player is now active and assigned to user2
    db.refresh(player)
    assert player.user_id == user2.id
    assert getattr(player, 'is_active', True) is True
    db.close()

def test_adjudication_results_in_state():
    """Test that adjudication results are included in the game state after a turn."""
    from server.api import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    # Create a game and register a user
    resp = client.post("/games/create", json={"map_name": "standard"})
    game_id = int(resp.json()["game_id"])
    client.post("/users/register", json={"telegram_id": "u1", "full_name": "User1"})
    # Add player to the game (associate user with power)
    client.post(f"/games/{game_id}/join", json={"telegram_id": "u1", "game_id": game_id, "power": "FRANCE"})
    # Submit a valid order and process the turn
    order = "FRANCE F BRE H"
    client.post("/games/set_orders", json={"game_id": str(game_id), "power": "FRANCE", "orders": [order], "telegram_id": "u1"})
    client.post(f"/games/{game_id}/process_turn")
    # Get the game state
    resp = client.get(f"/games/{game_id}/state")
    data = resp.json()
    assert "adjudication_results" in data
    results = data["adjudication_results"]
    assert "FRANCE" in results
    france_results = results["FRANCE"]
    assert "orders" in france_results
    assert "results" in france_results
