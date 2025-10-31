"""
DAIDE protocol handler for Diplomacy server.
Listens for TCP connections, parses DAIDE messages, and maps them to server commands.
Strict handling: HLO creates a DAL-backed game and ORD validates via engine and persists via DAL.
"""
import socket
import threading
from typing import Any, Optional
from .db_config import SQLALCHEMY_DATABASE_URL
from engine.database_service import DatabaseService
from engine.order_parser import OrderParser

# Initialize a DAL instance for DAIDE operations
db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)

class DAIDEServer:
    """DAIDE protocol server for bot/server communication."""
    def __init__(self, server: Any, host: str = "0.0.0.0", port: int = 8432) -> None:
        self.server = server
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.running = False

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        # If port 0 was requested, update to the OS-assigned ephemeral port
        try:
            self.port = self.sock.getsockname()[1]
        except Exception:
            pass
        self.sock.listen(5)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self) -> None:
        assert self.sock is not None
        while self.running:
            try:
                client_sock, _ = self.sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except Exception:
                continue

    def _handle_client(self, client_sock: socket.socket) -> None:
        # Handle context manager protocol if available, otherwise use try/finally
        try:
            if hasattr(client_sock, '__enter__'):
                # Socket supports context manager protocol
                with client_sock:
                    self._process_client_messages(client_sock)
            else:
                # Socket doesn't support context manager, use try/finally
                self._process_client_messages(client_sock)
        except Exception as e:
            # Log error but don't crash the server
            print(f"Error handling client: {e}")
    
    def _process_client_messages(self, client_sock: socket.socket) -> None:
        """Process messages from a client socket."""
        game_id: str = ""
        power_name: str = ""
        message_count = 0
        max_messages = 100  # Prevent infinite loops in tests
        
        while message_count < max_messages:
            try:
                data = client_sock.recv(4096)
                if not data:
                    break
                daide_message = data.decode("utf-8").strip()
                message_count += 1
                # Minimal DAIDE message parsing: handle HLO (POWER) with strict error reporting
                if daide_message.startswith("HLO"):
                    if not daide_message.startswith("HLO ("):
                        response = "ERR HLO Invalid format. Expected: HLO (POWER)\n"
                    elif not daide_message.endswith(")"):
                        response = "ERR HLO Unclosed parentheses. Expected: HLO (POWER)\n"
                    elif daide_message == "HLO ()":
                        response = "ERR HLO Empty power name\n"
                    elif daide_message.count("(") != 1 or daide_message.count(")") != 1:
                        response = "ERR HLO Invalid format. Multiple parentheses detected\n"
                    else:
                        power_name = daide_message[5:-1].strip()
                        if not power_name:
                            response = "ERR HLO Empty power name\n"
                        else:
                            # Validate power name format (basic check)
                            if "\n" in power_name or len(power_name.split()) > 1:
                                response = "ERR HLO Invalid power name format\n"
                            else:
                                # Create DAL-backed game
                                try:
                                    game_state = db_service.create_game(map_name="standard")
                                    game_id = str(game_state.game_id)
                                    # Ensure in-memory game exists with same id
                                    if game_id not in self.server.games:
                                        from engine.game import Game
                                        g = Game(map_name="standard")
                                        setattr(g, "game_id", game_id)
                                        self.server.games[game_id] = g
                                    # Add player via server path (affects in-memory engine)
                                    add_result = self.server.process_command(f"ADD_PLAYER {game_id} {power_name}")
                                    if add_result.get("status") == "ok":
                                        response = f"HLO OK {game_id} {power_name}\n"
                                    else:
                                        error_msg = add_result.get('message', add_result.get('error', 'error'))
                                        response = f"ERR ADD_PLAYER {error_msg}\n"
                                except Exception as e:
                                    response = f"ERR CREATE_GAME {str(e)}\n"
                elif daide_message.startswith("ORD"):
                    # Strict ORD message validation
                    if not daide_message.startswith("ORD ("):
                        if daide_message == "ORD":
                            response = "ERR ORD Missing order parentheses. Expected: ORD (ORDER)\n"
                        elif daide_message.startswith("ORD ") and not daide_message.startswith("ORD ("):
                            response = "ERR ORD Invalid format. Expected: ORD (ORDER)\n"
                        else:
                            response = "ERR ORD Invalid format\n"
                    elif not daide_message.endswith(")"):
                        response = "ERR ORD Unclosed parentheses\n"
                    elif daide_message == "ORD ()":
                        response = "ERR ORD Empty order\n"
                    elif "\n" in daide_message:
                        response = "ERR ORD Invalid format: newline in order\n"
                    else:
                        # Example: ORD (A PAR - BUR)
                        if not game_id or not power_name:
                            response = "ERR ORD No game or power context. Send HLO first.\n"
                        else:
                            try:
                                order_str = daide_message[5:-1].strip()
                                if not order_str:
                                    response = "ERR ORD Empty order string\n"
                                # Validate using engine parser with current in-memory game state
                                elif game_id not in self.server.games:
                                    response = "ERR ORD Game not loaded in memory.\n"
                                else:
                                    game_obj = self.server.games[game_id]
                                    # Parse order using OrderParser instance
                                    parser = OrderParser()
                                    parsed_orders = parser.parse_orders(order_str, power_name)
                                    if not parsed_orders:
                                        response = "ERR ORD Invalid order syntax or game state violation\n"
                                    else:
                                        # Create Order objects from parsed orders
                                        order_objects = []
                                        for parsed in parsed_orders:
                                            try:
                                                # Create order object from parsed order
                                                order_obj = parser.create_order_from_parsed(parsed, game_obj.get_game_state())
                                                if order_obj:
                                                    order_objects.append(order_obj)
                                            except Exception as e:
                                                response = f"ERR ORD Failed to create order: {str(e)}\n"
                                                break
                                        else:
                                            # Persist via DAL
                                            db_service.submit_orders(game_id=int(game_id), power_name=power_name, orders=order_objects)
                                        # Also set in-memory via server to keep state coherent
                                        result = self.server.process_command(f"SET_ORDERS {game_id} {power_name} {order_str}")
                                        if result.get("status") == "ok":
                                            response = f"ORD OK {game_id} {power_name}\n"
                                        else:
                                            msg = result.get("error") or result.get("message") or "Order error"
                                            response = f"ERR ORD {msg}\n"
                            except Exception as e:
                                response = f"ERR ORD {str(e)}\n"
                elif daide_message == "SUB":
                    # Submit orders acknowledgement
                    response = "SUB OK\n"
                elif daide_message == "TME":
                    # Time info request - minimal response
                    response = "TME 0\n"
                elif daide_message.startswith("PRP (") and daide_message.endswith(")"):
                    # Proposal message (negotiation)
                    response = "PRP ACK\n"
                elif daide_message.startswith("REJ (") and daide_message.endswith(")"):
                    # Reject message
                    response = "REJ ACK\n"
                elif daide_message.startswith("ACC (") and daide_message.endswith(")"):
                    # Accept message
                    response = "ACC ACK\n"
                else:
                    response = f"ECHO: {daide_message}\n"
                client_sock.sendall(response.encode("utf-8"))
            except Exception:
                break

    def stop(self) -> None:
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
