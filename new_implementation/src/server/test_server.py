from .server import Server

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
