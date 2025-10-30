from typing import Dict, Any
from engine.game import Game
import logging
from .errors import ServerError, ErrorCode
import os

class Server:
    """
    Main class for accepting and processing game commands.
    
    This class provides the core server functionality for managing Diplomacy games,
    including game creation, player management, order processing, and turn advancement.
    It supports both CLI and programmatic interfaces for game control.
    
    Attributes:
        games: Dictionary mapping game IDs to Game instances
        next_game_id: Counter for generating unique game IDs
        logger: Logger instance for server operations
        
    Environment Variables:
        DIPLOMACY_LOG_LEVEL: Set logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO
        DIPLOMACY_LOG_FILE: If set, log output goes to this file instead of stdout
    """
    def __init__(self) -> None:
        self.games: Dict[str, Game] = {}
        self.next_game_id: int = 1
        self.logger = logging.getLogger("diplomacy.server")
        log_level = os.environ.get("DIPLOMACY_LOG_LEVEL", "INFO").upper()
        log_file = os.environ.get("DIPLOMACY_LOG_FILE")
        handler = logging.StreamHandler() if not log_file else logging.FileHandler(log_file)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.hasHandlers():
            self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        self.logger.info("Diplomacy server starting up.")

    def _is_same_unit_order(self, existing_order: str, new_unit: str) -> bool:
        """Check if an existing order is for the same unit as the new order."""
        try:
            # Extract unit from existing order string
            tokens = existing_order.strip().split()
            if len(tokens) >= 3:
                # Format: "POWER UNIT_TYPE PROVINCE ACTION TARGET?"
                # or "UNIT_TYPE PROVINCE ACTION TARGET?"
                if tokens[1] in ['A', 'F']:
                    existing_unit = f"{tokens[1]} {tokens[2]}"
                elif len(tokens) >= 2 and tokens[0] in ['A', 'F']:
                    existing_unit = f"{tokens[0]} {tokens[1]}"
                else:
                    return False
                return existing_unit == new_unit
            return False
        except Exception:
            # If parsing fails, assume different units to be safe
            return False

    def start(self) -> None:
        """
        Start the server CLI interface.
        
        This method starts an interactive command-line interface that accepts
        Diplomacy commands and processes them. The server will run until
        explicitly stopped with 'QUIT' or 'EXIT' commands, or interrupted
        with Ctrl+C.
        
        Note:
            This method blocks until the server is shut down. For programmatic
            use, prefer the process_command() method directly.
        """
        self.logger.info("Diplomacy server started.")
        print("Diplomacy Server CLI. Type commands or 'QUIT' to exit.")
        while True:
            try:
                command = input('> ').strip()
                if command.upper() in ("QUIT", "EXIT"):
                    print("Shutting down server.")
                    self.shutdown()
                    break
                response = self.process_command(command)
                print(response)
            except (EOFError, KeyboardInterrupt):
                print("\nShutting down server.")
                self.shutdown()
                break
            except Exception as e:
                print(f"Error: {e}")
                self.logger.exception(f"Exception in server loop: {e}")

    def shutdown(self) -> None:
        """
        Shutdown the server gracefully.
        
        This method performs cleanup operations and logs the shutdown event.
        It should be called when the server is no longer needed.
        """
        self.logger.info("Diplomacy server shutting down.")

    def process_command(self, command: str) -> Dict[str, Any]:
        """
        Process a Diplomacy server command.
        
        Args:
            command: Command string to process (e.g., "CREATE_GAME standard")
            
        Returns:
            Dictionary containing the command result with keys:
                - status: "ok" for success, "error" for failure
                - Additional keys depend on the command type
                
        Supported Commands:
            - CREATE_GAME <map_name>: Create a new game
            - ADD_PLAYER <game_id> <power>: Add a player to a game
            - SET_ORDERS <game_id> <power> <order>: Set orders for a power
            - PROCESS_TURN <game_id>: Process the current turn
            - GET_GAME_STATE <game_id>: Get current game state
            - LIST_GAMES: List all active games
            - QUIT/EXIT: Shutdown the server
        """
        self.logger.info(f"Received command: {command}")
        tokens = command.strip().split()
        if not tokens:
            self.logger.error("Empty command received")
            return ServerError.create_error_response(ErrorCode.MISSING_ARGUMENTS, "Empty command", {"command": command})
        cmd = tokens[0].upper()
        try:
            if cmd == "NEW_GAME" or cmd == "CREATE_GAME":
                map_name = tokens[1] if len(tokens) > 1 else "standard"
                game_id = str(self.next_game_id)
                game = Game(map_name=map_name)
                game.game_id = game_id  # Set the game_id attribute
                self.games[game_id] = game
                self.next_game_id += 1
                self.logger.info(f"Created new game with id {game_id} and map {map_name}")
                return {"status": "ok", "game_id": game_id, "map_name": map_name}
            elif cmd == "ADD_PLAYER":
                if len(tokens) < 3:
                    self.logger.error("ADD_PLAYER missing arguments")
                    return ServerError.missing_arguments("ADD_PLAYER", "ADD_PLAYER <game_id> <power_name>")
                game_id, power_name = tokens[1], tokens[2]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for ADD_PLAYER")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                if power_name in game.game_state.powers:
                    self.logger.error(f"Power {power_name} already exists in game {game_id}")
                    return ServerError.create_error_response(ErrorCode.POWER_ALREADY_EXISTS, f"Power {power_name} already exists in game {game_id}", {"game_id": game_id, "power_name": power_name})
                game.add_player(power_name)
                self.logger.info(f"Added player {power_name} to game {game_id}")
                self.logger.debug(f"Game state after add: {game.get_game_state()}")
                return {"status": "ok"}
            elif cmd == "SET_ORDERS":
                if len(tokens) < 4:
                    self.logger.error("SET_ORDERS missing arguments")
                    return ServerError.missing_arguments("SET_ORDERS", "SET_ORDERS <game_id> <power_name> <order_str>")
                game_id, power_name = tokens[1], tokens[2]
                order_str = " ".join(tokens[3:])
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for SET_ORDERS")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                if power_name not in game.game_state.powers:
                    self.logger.error(f"Power {power_name} not found in game {game_id}")
                    return ServerError.create_error_response(ErrorCode.POWER_NOT_FOUND, f"Power {power_name} not found in game {game_id}", {"game_id": game_id, "power_name": power_name})
                
                # Set the new orders (split multiple orders)
                order_str = " ".join(tokens[3:])
                
                # Parse the order string into individual orders using the new parser
                from engine.order_parser_utils import split_orders
                orders = split_orders(order_str)
                
                self.logger.info(f"Raw order string: {order_str}")
                self.logger.info(f"Parsed {len(orders)} orders: {orders}")
                
                game.set_orders(power_name, orders)
                
                self.logger.debug(f"Stored orders for {power_name}: {game.game_state.orders[power_name]}")
                
                self.logger.info(f"Set orders for {power_name} in game {game_id}: {order_str}")
                return {"status": "ok"}
            elif cmd == "PROCESS_TURN":
                if len(tokens) < 2:
                    self.logger.error("PROCESS_TURN missing arguments")
                    return ServerError.missing_arguments("PROCESS_TURN", "PROCESS_TURN <game_id>")
                game_id = tokens[1]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for PROCESS_TURN")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                game.process_turn()
                
                # Clear all orders after processing to prevent accumulation
                for power_name in game.game_state.powers.keys():
                    game.clear_orders(power_name)
                
                self.logger.info(f"Processed phase for game {game_id}")
                return {"status": "ok"}
            elif cmd == "GET_GAME_STATE":
                if len(tokens) < 2:
                    self.logger.error("GET_GAME_STATE missing arguments")
                    return ServerError.missing_arguments("GET_GAME_STATE", "GET_GAME_STATE <game_id>")
                game_id = tokens[1]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for GET_GAME_STATE")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                self.logger.info(f"Queried game state for game {game_id}")
                return {"status": "ok", "state": game.get_state()}
            elif cmd == "SAVE_GAME":
                if len(tokens) < 3:
                    self.logger.error("SAVE_GAME missing arguments")
                    return ServerError.missing_arguments("SAVE_GAME", "SAVE_GAME <game_id> <filename>")
                game_id, filename = tokens[1], tokens[2]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for SAVE_GAME")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                import pickle
                try:
                    with open(filename, 'wb') as f:
                        pickle.dump(game, f)
                    self.logger.info(f"Saved game {game_id} to {filename}")
                    return {"status": "ok"}
                except Exception as e:
                    self.logger.error(f"Failed to save game {game_id}: {e}")
                    return ServerError.create_error_response(ErrorCode.FILE_ERROR, f"Failed to save game {game_id}: {e}", {"game_id": game_id, "filename": filename})
            elif cmd == "LOAD_GAME":
                if len(tokens) < 3:
                    self.logger.error("LOAD_GAME missing arguments")
                    return ServerError.missing_arguments("LOAD_GAME", "LOAD_GAME <game_id> <filename>")
                game_id, filename = tokens[1], tokens[2]
                import pickle
                try:
                    with open(filename, 'rb') as f:
                        game = pickle.load(f)
                    self.games[game_id] = game
                    self.logger.info(f"Loaded game {game_id} from {filename}")
                    return {"status": "ok"}
                except Exception as e:
                    self.logger.error(f"Failed to load game {game_id}: {e}")
                    return ServerError.create_error_response(ErrorCode.FILE_ERROR, f"Failed to load game {game_id}: {e}", {"game_id": game_id, "filename": filename})
            elif cmd == "REMOVE_PLAYER":
                if len(tokens) < 3:
                    self.logger.error("REMOVE_PLAYER missing arguments")
                    return ServerError.missing_arguments("REMOVE_PLAYER", "REMOVE_PLAYER <game_id> <power_name>")
                game_id, power_name = tokens[1], tokens[2]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for REMOVE_PLAYER")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                if power_name not in game.game_state.powers:
                    self.logger.error(f"Power {power_name} not found in game {game_id}")
                    return ServerError.create_error_response(ErrorCode.POWER_NOT_FOUND, f"Power {power_name} not found in game {game_id}", {"game_id": game_id, "power_name": power_name})
                # Remove the power from the game
                del game.game_state.powers[power_name]
                if power_name in game.game_state.orders:
                    del game.game_state.orders[power_name]
                self.logger.info(f"Removed player {power_name} from game {game_id}")
                return {"status": "ok"}
            elif cmd == "ADVANCE_PHASE":
                if len(tokens) < 2:
                    self.logger.error("ADVANCE_PHASE missing arguments")
                    return ServerError.missing_arguments("ADVANCE_PHASE", "ADVANCE_PHASE <game_id>")
                game_id = tokens[1]
                game = self.games.get(game_id)
                if not game:
                    self.logger.error(f"Game {game_id} not found for ADVANCE_PHASE")
                    return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
                # Advance the phase by processing the current phase
                game.process_turn()
                self.logger.info(f"Advanced phase for game {game_id}")
                return {"status": "ok"}
            else:
                self.logger.error(f"Unknown command: {cmd}")
                return ServerError.unknown_command(cmd)
        except Exception as e:
            self.logger.exception(f"Exception while processing command '{command}': {e}")
            return ServerError.create_error_response(ErrorCode.INTERNAL_ERROR, f"Exception: {e}", {"command": command})

    def get_game_state(self, game_id: str) -> Any:
        """
        Get the current state of a specific game.
        
        Args:
            game_id: Unique identifier of the game
            
        Returns:
            GameState object if the game exists, None otherwise
            
        Note:
            This method returns the complete GameState object containing
            all game information including units, orders, and power states.
        """
        game = self.games.get(game_id)
        if not game:
            # Return structured error per spec instead of None
            return ServerError.create_error_response(
                ErrorCode.GAME_NOT_FOUND,
                f"Game {game_id} not found",
                {"game_id": game_id},
            )
        return game.get_game_state()
