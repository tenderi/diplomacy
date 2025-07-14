from typing import List, Dict

class Game:
    """Main class for managing the game state, phases, and turn processing."""
    def __init__(self, map_name: str = 'standard'):
        self.map_name = map_name
        self.players: List[str] = []
        self.orders: Dict[str, List[str]] = {}
        self.turn = 0
        self.done = False

    def add_player(self, power_name: str):
        if power_name not in self.players:
            self.players.append(power_name)

    def set_orders(self, power_name: str, orders: List[str]):
        self.orders[power_name] = orders

    def process_turn(self):
        self.turn += 1
        # For now, just clear orders and continue
        self.orders = {}
        # Mark done after 10 turns for stub
        if self.turn >= 10:
            self.done = True

    def get_state(self) -> Dict[str, object]:
        return {
            "map": self.map_name,
            "players": self.players,
            "orders": self.orders,
            "turn": self.turn,
            "done": self.done
        }

    def is_game_done(self) -> bool:
        return self.done
