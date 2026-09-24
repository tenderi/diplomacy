"""The text-command CLI surface (``server.server.Server.process_command``),
driven end to end: create, add player, set orders, process, read state."""
from server.server import Server

def test_client_server_interaction():
    client = Server()
    result = client.process_command("CREATE_GAME standard")
    assert result["status"] == "ok"
    game_id = result["game_id"]
    client.process_command(f"ADD_PLAYER {game_id} FRANCE")
    client.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    client.process_command(f"PROCESS_TURN {game_id}")  # Advances phase: Spring Movement -> Autumn Movement (same turn)
    state = client.process_command(f"GET_GAME_STATE {game_id}")
    assert state["status"] == "ok"
    # After the first PROCESS_TURN the phase advances (S1901M -> F1901M).
    assert state["state"]["phase"] == "F1901M"
    assert state["state"]["phase_type"] == "MOVEMENT"
    # Orders were consumed by adjudication.
    assert state["state"]["orders"] == {}

def test_client_error_handling():
    client = Server()
    result = client.process_command("FOO_BAR")
    assert result["status"] == "error"
    assert "Unknown command" in result["message"]
    result = client.process_command("ADD_PLAYER")
    assert result["status"] == "error"
