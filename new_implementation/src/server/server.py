from typing import Dict
from engine.game import Game
import logging

class Server:
    """Main class for accepting and processing game commands."""
    def __init__(self) -> None:
        self.games: Dict[str, Game] = {}
        self.next_game_id: int = 1
        self.logger = logging.getLogger("diplomacy.server")
        if not self.logger.hasHandlers():
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def start(self) -> None:
        # Placeholder for server loop (CLI/API)
        pass

    def process_command(self, command: str) -> Dict[str, object]:
        self.logger.info(f"Received command: {command}")
        tokens = command.strip().split()
        if not tokens:
            self.logger.error("Empty command received")
            return {"status": "error", "message": "Empty command"}
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
                return {"status": "error", "message": "Usage: ADD_PLAYER <game_id> <power_name>"}
            game_id, power_name = tokens[1], tokens[2]
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for ADD_PLAYER")
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.add_player(power_name)
            self.logger.info(f"Added player {power_name} to game {game_id}")
            return {"status": "ok"}
        elif cmd == "SET_ORDERS":
            if len(tokens) < 4:
                self.logger.error("SET_ORDERS missing arguments")
                return {"status": "error", "message": "Usage: SET_ORDERS <game_id> <power_name> <order_str>"}
            game_id, power_name = tokens[1], tokens[2]
            order_str = " ".join(tokens[3:])
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for SET_ORDERS")
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.set_orders(power_name, [order_str])
            self.logger.info(f"Set orders for {power_name} in game {game_id}: {order_str}")
            return {"status": "ok"}
        elif cmd == "PROCESS_TURN":
            if len(tokens) < 2:
                self.logger.error("PROCESS_TURN missing arguments")
                return {"status": "error", "message": "Usage: PROCESS_TURN <game_id>"}
            game_id = tokens[1]
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for PROCESS_TURN")
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.process_turn()
            self.logger.info(f"Processed turn for game {game_id}")
            return {"status": "ok"}
        elif cmd == "GET_GAME_STATE":
            if len(tokens) < 2:
                self.logger.error("GET_GAME_STATE missing arguments")
                return {"status": "error", "message": "Usage: GET_GAME_STATE <game_id>"}
            game_id = tokens[1]
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for GET_GAME_STATE")
                return {"status": "error", "message": f"Game {game_id} not found"}
            self.logger.info(f"Queried game state for game {game_id}")
            return {"status": "ok", "state": game.get_state()}
        elif cmd == "SAVE_GAME":
            if len(tokens) < 3:
                self.logger.error("SAVE_GAME missing arguments")
                return {"status": "error", "message": "Usage: SAVE_GAME <game_id> <filename>"}
            game_id, filename = tokens[1], tokens[2]
            game = self.games.get(game_id)
            if not game:
                self.logger.error(f"Game {game_id} not found for SAVE_GAME")
                return {"status": "error", "message": f"Game {game_id} not found"}
            import pickle
            try:
                with open(filename, 'wb') as f:
                    pickle.dump(game, f)
                self.logger.info(f"Saved game {game_id} to {filename}")
                return {"status": "ok"}
            except Exception as e:
                self.logger.error(f"Failed to save game {game_id}: {e}")
                return {"status": "error", "message": str(e)}
        elif cmd == "LOAD_GAME":
            if len(tokens) < 3:
                self.logger.error("LOAD_GAME missing arguments")
                return {"status": "error", "message": "Usage: LOAD_GAME <game_id> <filename>"}
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
                return {"status": "error", "message": str(e)}
        else:
            self.logger.error(f"Unknown command: {cmd}")
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def get_game_state(self, game_id: str) -> object:
        game = self.games.get(game_id)
        if not game:
            return None
        return game.get_state()
