import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from client import Client
from server.server import Server

def test_client_server_interaction():
    server = Server()
    client = Client(server)
    result = client.send_command("CREATE_GAME standard")
    assert result["status"] == "ok"
    game_id = result["game_id"]
    client.send_command(f"ADD_PLAYER {game_id} FRANCE")
    client.send_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
    client.send_command(f"PROCESS_TURN {game_id}")  # Now advances phase, not just turn
    state = client.send_command(f"GET_GAME_STATE {game_id}")
    assert state["status"] == "ok"
    assert state["state"]["turn"] == 1
    assert "FRANCE" in state["state"]["orders"] or state["state"]["orders"] == {}

def test_client_error_handling():
    server = Server()
    client = Client(server)
    result = client.send_command("FOO_BAR")
    assert result["status"] == "error"
    assert "Unknown command" in result["message"]
    result = client.send_command("ADD_PLAYER")
    assert result["status"] == "error"
