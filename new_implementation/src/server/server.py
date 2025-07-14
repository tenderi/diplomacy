from typing import Dict, Any
from engine.game import Game
import logging
from .errors import ServerError, ErrorCode
import os

class Server:
    """Main class for accepting and processing game commands."""
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

    def start(self) -> None:
        self.logger.info("Diplomacy server started.")
        # Placeholder for server loop (CLI/API)
        pass

    def shutdown(self) -> None:
        self.logger.info("Diplomacy server shutting down.")

    def process_command(self, command: str) -> Dict[str, Any]:
        self.logger.info(f"Received command: {command}")
        tokens = command.strip().split()
        if not tokens:
            self.logger.error("Empty command received")
            return ServerError.create_error_response(ErrorCode.MISSING_ARGUMENTS, "Empty command", {"command": command})
        cmd = tokens[0].upper()
        if cmd == "NEW_GAME" or cmd == "CREATE_GAME":
            game_id = str(self.next_game_id)
            self.games[game_id] = Game()
            self.next_game_id += 1
            self.logger.info(f"Created new game with id {game_id}")
            return {"status": "ok", "game_id": game_id}
        elif cmd == "ADD_PLAYER":
            if len(tokens) < 3:
                self.logger.error("ADD_PLAYER missing arguments")
                return ServerError.missing_arguments("ADD_PLAYER", "ADD_PLAYER <game_id> <power_name>")
            game_id, power_name = tokens[1], tokens[2]
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for ADD_PLAYER")
                return ServerError.create_error_response(ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id})
            if power_name in game.powers:
                self.logger.error(f"Power {power_name} already exists in game {game_id}")
                return ServerError.create_error_response(ErrorCode.POWER_ALREADY_EXISTS, f"Power {power_name} already exists in game {game_id}", {"game_id": game_id, "power_name": power_name})
            game.add_player(power_name)
            self.logger.info(f"Added player {power_name} to game {game_id}")
            self.logger.debug(f"Game state after add: {game.get_state()}")
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
            if power_name not in game.powers:
                self.logger.error(f"Power {power_name} not found in game {game_id}")
                return ServerError.create_error_response(ErrorCode.POWER_NOT_FOUND, f"Power {power_name} not found in game {game_id}", {"game_id": game_id, "power_name": power_name})
            game.set_orders(power_name, [order_str])
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
            self.logger.info(f"Processed turn for game {game_id}")
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
            if power_name not in game.powers:
                self.logger.error(f"Power {power_name} not found in game {game_id}")
                return ServerError.create_error_response(ErrorCode.POWER_NOT_FOUND, f"Power {power_name} not found in game {game_id}", {"game_id": game_id, "power_name": power_name})
            # Remove the power from the game
            del game.powers[power_name]
            if power_name in game.orders:
                del game.orders[power_name]
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
            # Advance the phase by processing the current turn
            game.process_turn()
            self.logger.info(f"Advanced phase for game {game_id}")
            return {"status": "ok"}
        else:
            self.logger.error(f"Unknown command: {cmd}")
            return ServerError.unknown_command(cmd)

    def get_game_state(self, game_id: str) -> Any:
        game = self.games.get(game_id)
        if not game:
            return None
        return game.get_state()
