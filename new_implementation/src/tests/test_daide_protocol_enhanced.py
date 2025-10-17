"""
Comprehensive unit tests for DAIDE Protocol module.

Tests cover DAIDEServer class with all message types, edge cases, 
concurrent connections, error handling, and protocol compliance.
"""

import pytest
import socket
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from server.daide_protocol import DAIDEServer
from server.server import Server


class TestDAIDEServer:
    """Test DAIDEServer class."""
    
    @pytest.fixture
    def mock_server(self):
        """Create mock server for testing."""
        server = Mock(spec=Server)
        server.process_command = Mock(return_value={"status": "ok", "game_id": "test_game_001"})
        return server
    
    @pytest.fixture
    def daide_server(self, mock_server):
        """Create DAIDEServer instance for testing."""
        return DAIDEServer(mock_server, host="127.0.0.1", port=0)
    
    def test_server_initialization(self, daide_server, mock_server):
        """Test DAIDEServer initialization."""
        assert daide_server.server == mock_server
        assert daide_server.host == "127.0.0.1"
        assert daide_server.port == 0
        assert daide_server.sock is None
        assert daide_server.running is False
    
    def test_server_start(self, daide_server):
        """Test DAIDEServer start method."""
        daide_server.start()
        
        assert daide_server.sock is not None
        assert daide_server.running is True
        
        # Cleanup
        daide_server.stop()
    
    def test_server_stop(self, daide_server):
        """Test DAIDEServer stop method."""
        daide_server.start()
        daide_server.stop()
        
        assert daide_server.running is False
        assert daide_server.sock is None


class TestDAIDEMessageHandling:
    """Test DAIDE message handling."""
    
    @pytest.fixture
    def mock_server(self):
        """Create mock server with realistic responses."""
        server = Mock(spec=Server)
        
        def mock_process_command(command):
            if command.startswith("CREATE_GAME"):
                return {"status": "ok", "game_id": "test_game_001"}
            elif command.startswith("ADD_PLAYER"):
                return {"status": "ok"}
            elif command.startswith("SET_ORDERS"):
                return {"status": "ok"}
            elif command.startswith("GET_GAME_STATE"):
                return {
                    "status": "ok",
                    "state": {
                        "powers": {"FRANCE": []},
                        "orders": {"FRANCE": ["A PAR - BUR"]}
                    }
                }
            else:
                return {"status": "ok"}
        
        server.process_command = Mock(side_effect=mock_process_command)
        return server
    
    def test_hlo_message_handling(self, mock_server):
        """Test HLO (Hello) message handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket
        mock_client_sock = Mock()
        mock_client_sock.recv = Mock(return_value=b"HLO (FRANCE)")
        mock_client_sock.sendall = Mock()
        
        # Test HLO handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify server commands were called
        assert mock_server.process_command.call_count >= 2
        create_game_calls = [call for call in mock_server.process_command.call_args_list 
                           if call[0][0].startswith("CREATE_GAME")]
        add_player_calls = [call for call in mock_server.process_command.call_args_list 
                          if call[0][0].startswith("ADD_PLAYER")]
        
        assert len(create_game_calls) > 0
        assert len(add_player_calls) > 0
        
        # Verify response was sent
        mock_client_sock.sendall.assert_called()
        response_call = mock_client_sock.sendall.call_args[0][0]
        response = response_call.decode("utf-8")
        assert response.startswith("HLO OK")
        assert "FRANCE" in response
    
    def test_ord_message_handling(self, mock_server):
        """Test ORD (Order) message handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket with HLO followed by ORD
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"ORD (A PAR - BUR)"
            else:
                return b""  # End of data
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        # Test order handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify SET_ORDERS was called
        set_orders_calls = [call for call in mock_server.process_command.call_args_list 
                          if call[0][0].startswith("SET_ORDERS")]
        assert len(set_orders_calls) > 0
        
        # Verify ORD response was sent
        response_calls = mock_client_sock.sendall.call_args_list
        ord_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("ORD OK"):
                ord_response = response
                break
        
        assert ord_response is not None
    
    def test_sub_message_handling(self, mock_server):
        """Test SUB (Submit) message handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"SUB"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        # Test SUB handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify SUB response was sent
        response_calls = mock_client_sock.sendall.call_args_list
        sub_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("SUB OK"):
                sub_response = response
                break
        
        assert sub_response is not None
    
    def test_tme_message_handling(self, mock_server):
        """Test TME (Time) message handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"TME"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        # Test TME handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify TME response was sent
        response_calls = mock_client_sock.sendall.call_args_list
        tme_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("TME"):
                tme_response = response
                break
        
        assert tme_response is not None
    
    def test_off_message_handling(self, mock_server):
        """Test OFF (Offer) message handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"OFF (ALLIANCE FRANCE GERMANY)"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        # Test OFF handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify OFF response was sent
        response_calls = mock_client_sock.sendall.call_args_list
        off_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("OFF OK"):
                off_response = response
                break
        
        assert off_response is not None
    
    def test_mis_message_handling(self, mock_server):
        """Test MIS (Message) handling."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"MIS (Hello from France)"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        # Test MIS handling
        daide_server._handle_client(mock_client_sock)
        
        # Verify MIS response was sent
        response_calls = mock_client_sock.sendall.call_args_list
        mis_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("MIS OK"):
                mis_response = response
                break
        
        assert mis_response is not None


class TestDAIDEErrorHandling:
    """Test DAIDE error handling."""
    
    @pytest.fixture
    def mock_server(self):
        """Create mock server for error testing."""
        server = Mock(spec=Server)
        server.process_command = Mock(return_value={"status": "error", "message": "Test error"})
        return server
    
    def test_malformed_hlo_message(self, mock_server):
        """Test handling of malformed HLO messages."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        malformed_messages = [
            b"HLO",  # Missing power
            b"HLO ()",  # Empty power
            b"HLO (INVALID_POWER)",  # Invalid power name
            b"HLO FRANCE",  # Missing parentheses
            b"HELLO (FRANCE)",  # Wrong command
        ]
        
        for message in malformed_messages:
            mock_client_sock = Mock()
            mock_client_sock.recv = Mock(return_value=message)
            mock_client_sock.sendall = Mock()
            
            # Should handle gracefully without crashing
            daide_server._handle_client(mock_client_sock)
            
            # Verify error response was sent
            mock_client_sock.sendall.assert_called()
            response = mock_client_sock.sendall.call_args[0][0].decode("utf-8")
            assert "ERROR" in response or "HLO ERROR" in response
    
    def test_malformed_ord_message(self, mock_server):
        """Test handling of malformed ORD messages."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        malformed_messages = [
            b"ORD",  # Missing order
            b"ORD ()",  # Empty order
            b"ORD (INVALID ORDER)",  # Invalid order format
            b"ORDER (A PAR - BUR)",  # Wrong command
        ]
        
        for message in malformed_messages:
            mock_client_sock = Mock()
            call_count = 0
            
            def mock_recv(size):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return b"HLO (FRANCE)"
                else:
                    return message
            
            mock_client_sock.recv = Mock(side_effect=mock_recv)
            mock_client_sock.sendall = Mock()
            
            # Should handle gracefully
            daide_server._handle_client(mock_client_sock)
            
            # Verify error response was sent
            response_calls = mock_client_sock.sendall.call_args_list
            error_response = None
            for call in response_calls:
                response = call[0][0].decode("utf-8")
                if "ERROR" in response or "ORD ERROR" in response:
                    error_response = response
                    break
            
            assert error_response is not None
    
    def test_connection_timeout(self, mock_server):
        """Test handling of connection timeouts."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket that times out
        mock_client_sock = Mock()
        mock_client_sock.recv = Mock(side_effect=socket.timeout("Connection timeout"))
        mock_client_sock.sendall = Mock()
        
        # Should handle timeout gracefully
        daide_server._handle_client(mock_client_sock)
        
        # Should not crash or send error responses for timeouts
        mock_client_sock.sendall.assert_not_called()
    
    def test_connection_reset(self, mock_server):
        """Test handling of connection resets."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Mock client socket that resets connection
        mock_client_sock = Mock()
        mock_client_sock.recv = Mock(side_effect=ConnectionResetError("Connection reset"))
        mock_client_sock.sendall = Mock()
        
        # Should handle connection reset gracefully
        daide_server._handle_client(mock_client_sock)
        
        # Should not crash
        assert True  # Test passes if no exception is raised


class TestDAIDEConcurrentConnections:
    """Test DAIDE server with concurrent connections."""
    
    @pytest.fixture
    def mock_server(self):
        """Create mock server for concurrent testing."""
        server = Mock(spec=Server)
        
        def mock_process_command(command):
            if command.startswith("CREATE_GAME"):
                return {"status": "ok", "game_id": f"game_{threading.current_thread().ident}"}
            elif command.startswith("ADD_PLAYER"):
                return {"status": "ok"}
            else:
                return {"status": "ok"}
        
        server.process_command = Mock(side_effect=mock_process_command)
        return server
    
    def test_multiple_concurrent_connections(self, mock_server):
        """Test handling multiple concurrent connections."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        daide_server.start()
        
        try:
            # Create multiple client connections
            num_clients = 5
            threads = []
            results = []
            
            def client_thread(client_id):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(("127.0.0.1", daide_server.port))
                    
                    # Send HLO message
                    sock.sendall(f"HLO (FRANCE{client_id})".encode("utf-8"))
                    response = sock.recv(4096).decode("utf-8")
                    
                    sock.close()
                    results.append((client_id, response))
                except Exception as e:
                    results.append((client_id, f"Error: {e}"))
            
            # Start all client threads
            for i in range(num_clients):
                thread = threading.Thread(target=client_thread, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5)
            
            # Verify all clients received responses
            assert len(results) == num_clients
            for client_id, response in results:
                assert response.startswith("HLO OK"), f"Client {client_id} got invalid response: {response}"
        
        finally:
            daide_server.stop()
    
    def test_concurrent_order_submissions(self, mock_server):
        """Test concurrent order submissions."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        daide_server.start()
        
        try:
            # Create multiple clients submitting orders concurrently
            num_clients = 3
            threads = []
            results = []
            
            def order_client_thread(client_id):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect(("127.0.0.1", daide_server.port))
                    
                    # Send HLO
                    sock.sendall(f"HLO (FRANCE{client_id})".encode("utf-8"))
                    sock.recv(4096)  # Consume HLO response
                    
                    # Send ORD
                    sock.sendall(f"ORD (A PAR{client_id} - BUR)".encode("utf-8"))
                    response = sock.recv(4096).decode("utf-8")
                    
                    sock.close()
                    results.append((client_id, response))
                except Exception as e:
                    results.append((client_id, f"Error: {e}"))
            
            # Start all client threads
            for i in range(num_clients):
                thread = threading.Thread(target=order_client_thread, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=5)
            
            # Verify all orders were processed
            assert len(results) == num_clients
            for client_id, response in results:
                assert response.startswith("ORD OK"), f"Client {client_id} got invalid response: {response}"
        
        finally:
            daide_server.stop()


class TestDAIDEProtocolCompliance:
    """Test DAIDE protocol compliance."""
    
    @pytest.fixture
    def mock_server(self):
        """Create mock server for protocol testing."""
        server = Mock(spec=Server)
        
        def mock_process_command(command):
            if command.startswith("CREATE_GAME"):
                return {"status": "ok", "game_id": "protocol_test_game"}
            elif command.startswith("ADD_PLAYER"):
                return {"status": "ok"}
            elif command.startswith("SET_ORDERS"):
                return {"status": "ok"}
            elif command.startswith("GET_GAME_STATE"):
                return {
                    "status": "ok",
                    "state": {
                        "powers": {"FRANCE": []},
                        "orders": {"FRANCE": []},
                        "turn": 1,
                        "year": 1901,
                        "season": "Spring",
                        "phase": "Movement"
                    }
                }
            else:
                return {"status": "ok"}
        
        server.process_command = Mock(side_effect=mock_process_command)
        return server
    
    def test_hlo_response_format(self, mock_server):
        """Test HLO response format compliance."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        mock_client_sock = Mock()
        mock_client_sock.recv = Mock(return_value=b"HLO (FRANCE)")
        mock_client_sock.sendall = Mock()
        
        daide_server._handle_client(mock_client_sock)
        
        # Verify HLO response format
        response = mock_client_sock.sendall.call_args[0][0].decode("utf-8")
        assert response.startswith("HLO OK")
        
        # Parse response components
        parts = response.strip().split()
        assert len(parts) >= 3
        assert parts[0] == "HLO"
        assert parts[1] == "OK"
        assert parts[2] == "protocol_test_game"  # game_id
        assert parts[3] == "FRANCE"  # power_name
    
    def test_ord_response_format(self, mock_server):
        """Test ORD response format compliance."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"ORD (A PAR - BUR)"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        daide_server._handle_client(mock_client_sock)
        
        # Verify ORD response format
        response_calls = mock_client_sock.sendall.call_args_list
        ord_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("ORD OK"):
                ord_response = response
                break
        
        assert ord_response is not None
        assert ord_response.startswith("ORD OK")
    
    def test_tme_response_format(self, mock_server):
        """Test TME response format compliance."""
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        mock_client_sock = Mock()
        call_count = 0
        
        def mock_recv(size):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"HLO (FRANCE)"
            elif call_count == 2:
                return b"TME"
            else:
                return b""
        
        mock_client_sock.recv = Mock(side_effect=mock_recv)
        mock_client_sock.sendall = Mock()
        
        daide_server._handle_client(mock_client_sock)
        
        # Verify TME response format
        response_calls = mock_client_sock.sendall.call_args_list
        tme_response = None
        for call in response_calls:
            response = call[0][0].decode("utf-8")
            if response.startswith("TME"):
                tme_response = response
                break
        
        assert tme_response is not None
        assert tme_response.startswith("TME")
        
        # Parse TME response components
        parts = tme_response.strip().split()
        assert len(parts) >= 4
        assert parts[0] == "TME"
        assert parts[1] == "1"  # turn
        assert parts[2] == "1901"  # year
        assert parts[3] == "Spring"  # season


class TestDAIDEServerLifecycle:
    """Test DAIDE server lifecycle management."""
    
    def test_server_start_stop_cycle(self):
        """Test starting and stopping server multiple times."""
        mock_server = Mock(spec=Server)
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Test multiple start/stop cycles
        for _ in range(3):
            daide_server.start()
            assert daide_server.running is True
            assert daide_server.sock is not None
            
            daide_server.stop()
            assert daide_server.running is False
            assert daide_server.sock is None
    
    def test_server_port_binding(self):
        """Test server port binding."""
        mock_server = Mock(spec=Server)
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        daide_server.start()
        
        try:
            # Verify server is listening
            assert daide_server.sock is not None
            assert daide_server.running is True
            
            # Test that we can connect to the server
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.connect(("127.0.0.1", daide_server.port))
            test_sock.close()
            
        finally:
            daide_server.stop()
    
    def test_server_error_recovery(self):
        """Test server error recovery."""
        mock_server = Mock(spec=Server)
        daide_server = DAIDEServer(mock_server, host="127.0.0.1", port=0)
        
        # Start server
        daide_server.start()
        
        try:
            # Simulate server error by closing the socket
            if daide_server.sock:
                daide_server.sock.close()
            
            # Stop should handle gracefully
            daide_server.stop()
            
            # Should be able to start again
            daide_server.start()
            assert daide_server.running is True
            
        finally:
            daide_server.stop()


# Integration tests
@pytest.mark.integration
class TestDAIDEIntegration:
    """Integration tests for DAIDE protocol."""
    
    def test_full_daide_workflow(self):
        """Test complete DAIDE workflow."""
        server = Server()
        daide_server = DAIDEServer(server, host="127.0.0.1", port=0)
        daide_server.start()
        
        try:
            # Connect client
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", daide_server.port))
            
            # HLO - Hello
            sock.sendall(b"HLO (FRANCE)")
            hlo_response = sock.recv(4096).decode("utf-8")
            assert hlo_response.startswith("HLO OK")
            
            # Extract game_id
            game_id = hlo_response.strip().split()[2]
            
            # ORD - Submit orders
            sock.sendall(b"ORD (A PAR - BUR)")
            ord_response = sock.recv(4096).decode("utf-8")
            assert ord_response.startswith("ORD OK")
            
            # SUB - Submit all orders
            sock.sendall(b"SUB")
            sub_response = sock.recv(4096).decode("utf-8")
            assert sub_response.startswith("SUB OK")
            
            # TME - Get time info
            sock.sendall(b"TME")
            tme_response = sock.recv(4096).decode("utf-8")
            assert tme_response.startswith("TME")
            
            # Verify server state
            state = server.process_command(f"GET_GAME_STATE {game_id}")
            assert state["status"] == "ok"
            assert "FRANCE" in state["state"]["powers"]
            
            sock.close()
            
        finally:
            daide_server.stop()
    
    def test_multiple_powers_workflow(self):
        """Test DAIDE workflow with multiple powers."""
        server = Server()
        daide_server = DAIDEServer(server, host="127.0.0.1", port=0)
        daide_server.start()
        
        try:
            # Connect multiple clients for different powers
            powers = ["FRANCE", "GERMANY", "ENGLAND"]
            sockets = []
            
            for power in powers:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(("127.0.0.1", daide_server.port))
                sockets.append((power, sock))
                
                # HLO
                sock.sendall(f"HLO ({power})".encode("utf-8"))
                response = sock.recv(4096).decode("utf-8")
                assert response.startswith("HLO OK")
            
            # Submit orders for each power
            for power, sock in sockets:
                sock.sendall(f"ORD (A {power[:3]} - BUR)".encode("utf-8"))
                response = sock.recv(4096).decode("utf-8")
                assert response.startswith("ORD OK")
            
            # Close all connections
            for power, sock in sockets:
                sock.close()
            
        finally:
            daide_server.stop()
