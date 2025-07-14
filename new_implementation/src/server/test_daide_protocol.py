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

def test_daide_server_ord_sets_orders() -> None:
    """Test that DAIDE server handles ORD (order submission) after HLO."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9002)
    daide_server.start()
    time.sleep(0.1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9002))
    try:
        # HLO to create game and player
        sock.sendall(b"HLO (FRANCE)")
        data = sock.recv(4096)
        response = data.decode("utf-8")
        assert response.startswith("HLO OK ")
        _, _, game_id, power_name = response.strip().split()
        # ORD to submit an order
        sock.sendall(b"ORD (A PAR - BUR)")
        data2 = sock.recv(4096)
        response2 = data2.decode("utf-8")
        assert response2.startswith("ORD OK ")
        # Check server state
        state = server.process_command(f"GET_GAME_STATE {game_id}")
        assert state["status"] == "ok"
        assert "A PAR - BUR" in state["state"]["orders"][power_name]
    finally:
        sock.close()
        daide_server.stop()

def test_daide_server_negotiation_messages() -> None:
    """Test that DAIDE server handles PRP, REJ, ACC negotiation messages."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9003)
    daide_server.start()
    time.sleep(0.1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9003))
    try:
        # PRP
        sock.sendall(b"PRP (DRAW)")
        data = sock.recv(4096)
        assert data.decode("utf-8").startswith("PRP ACK")
        # REJ
        sock.sendall(b"REJ (DRAW)")
        data = sock.recv(4096)
        assert data.decode("utf-8").startswith("REJ ACK")
        # ACC
        sock.sendall(b"ACC (DRAW)")
        data = sock.recv(4096)
        assert data.decode("utf-8").startswith("ACC ACK")
    finally:
        sock.close()
        daide_server.stop()

def test_daide_server_invalid_ord_context() -> None:
    """Test that DAIDE server returns error for ORD without HLO context."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9004)
    daide_server.start()
    time.sleep(0.1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9004))
    try:
        # ORD without HLO
        sock.sendall(b"ORD (A PAR - BUR)")
        data = sock.recv(4096)
        response = data.decode("utf-8")
        assert response.startswith("ERR ORD No game or power context")
    finally:
        sock.close()
        daide_server.stop()

def test_daide_server_invalid_message() -> None:
    """Test that DAIDE server returns echo for unknown/invalid DAIDE messages."""
    server = Server()
    daide_server = DAIDEServer(server, host="127.0.0.1", port=9005)
    daide_server.start()
    time.sleep(0.1)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 9005))
    try:
        # Send a random/invalid message
        sock.sendall(b"FOOBAR")
        data = sock.recv(4096)
        response = data.decode("utf-8")
        assert response.startswith("ECHO: FOOBAR")
    finally:
        sock.close()
        daide_server.stop()
