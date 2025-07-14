from typing import Dict
from engine.game import Game

class Server:
    """Main class for accepting and processing game commands."""
    def __init__(self):
        self.games: Dict[str, Game] = {}  # game_id -> Game instance
        self.next_game_id = 1

    def start(self):
        # Placeholder for server loop (CLI/API)
        pass

    def process_command(self, command: str):
        """Accept and process a command. Returns a result or raises on error."""
        tokens = command.strip().split()
        if not tokens:
            return {"status": "error", "message": "Empty command"}
        cmd = tokens[0].upper()
        if cmd == "NEW_GAME" or cmd == "CREATE_GAME":
            game_id = str(self.next_game_id)
            self.games[game_id] = Game()
            self.next_game_id += 1
            return {"status": "ok", "game_id": game_id}
        elif cmd == "ADD_PLAYER":
            if len(tokens) < 3:
                return {"status": "error", "message": "Usage: ADD_PLAYER <game_id> <power_name>"}
            game_id, power_name = tokens[1], tokens[2]
            game = self.games.get(game_id)
            if not game:
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.add_player(power_name)
            return {"status": "ok"}
        elif cmd == "SET_ORDERS":
            if len(tokens) < 4:
                return {"status": "error", "message": "Usage: SET_ORDERS <game_id> <power_name> <order_str>"}
            game_id, power_name = tokens[1], tokens[2]
            order_str = " ".join(tokens[3:])
            game = self.games.get(game_id)
            if not game:
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.set_orders(power_name, [order_str])
            return {"status": "ok"}
        elif cmd == "PROCESS_TURN":
            if len(tokens) < 2:
                return {"status": "error", "message": "Usage: PROCESS_TURN <game_id>"}
            game_id = tokens[1]
            game = self.games.get(game_id)
            if not game:
                return {"status": "error", "message": f"Game {game_id} not found"}
            game.process_turn()
            return {"status": "ok"}
        elif cmd == "GET_GAME_STATE":
            if len(tokens) < 2:
                return {"status": "error", "message": "Usage: GET_GAME_STATE <game_id>"}
            game_id = tokens[1]
            game = self.games.get(game_id)
            if not game:
                return {"status": "error", "message": f"Game {game_id} not found"}
            return {"status": "ok", "state": game.get_state()}
        else:
            return {"status": "error", "message": f"Unknown command: {cmd}"}

    def get_game_state(self, game_id: str):
        game = self.games.get(game_id)
        if not game:
            return None
        return game.get_state()
