"""
Test DAIDE protocol server: verifies TCP connection, message echo, and integration point.
"""
import socket
import time
from server.daide_protocol import DAIDEServer
from server.server import Server

def test_daide_server_echo() -> None:
    """Test that DAIDE server echoes non-HLO messages."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9000)
    daide_server.start()
    time.sleep(0.1)  # Allow server to start

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9000))
    try:
        test_message = "PING"
        sock.sendall(test_message.encode("utf-8"))
        data = sock.recv(4096)
        assert data.decode("utf-8").startswith("ECHO: PING")
    finally:
        sock.close()
        daide_server.stop()

def test_daide_server_hlo_creates_game_and_player() -> None:
    """Test that DAIDE server handles HLO (POWER) by creating a game and adding the player."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9001)
    daide_server.start()
    time.sleep(0.1)  # Allow server to start

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9001))
    try:
        test_message = "HLO (FRANCE)"
        sock.sendall(test_message.encode("utf-8"))
        data = sock.recv(4096)
        response = data.decode("utf-8")
        assert response.startswith("HLO OK ")
        # Extract game_id and power_name
        _, _, game_id, power_name = response.strip().split()
        assert power_name == "FRANCE"
        # Check server state
        state = server.process_command(f"GET_GAME_STATE {game_id}")
        assert state["status"] == "ok"
        assert "FRANCE" in state["state"]["powers"]
    finally:
        sock.close()
        daide_server.stop()
