"""
DAIDE protocol handler for Diplomacy server.
Listens for TCP connections, parses DAIDE messages, and maps them to server commands.
Strict handling: HLO creates a DAL-backed game and ORD validates via engine and persists via DAL.
"""
import socket
import threading
from typing import Any, Optional


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
                # DAIDE message parsing: handle HLO (POWER) with strict error reporting
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
                                # Create a new-engine game and claim the power.
                                try:
                                    create_result = self.server.process_command("CREATE_GAME standard")
                                    game_id = str(create_result.get("game_id"))
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
                                else:
                                    result = self.server.process_command(
                                        f"SET_ORDERS {game_id} {power_name} {order_str}"
                                    )
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
                    # Time info request - returns current time offset (0 = no offset)
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
