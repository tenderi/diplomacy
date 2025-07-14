from typing import Dict, List, Any
from engine.map import Map
from engine.power import Power

class Game:
    """Main class for managing the game state, phases, and turn processing."""
    def __init__(self, map_name: str = 'standard') -> None:
        self.map_name: str = map_name
        self.map: Map = Map()  # Use Map for board representation
        self.powers: Dict[str, Power] = {}
        self.orders: Dict[str, List[str]] = {}
        self.turn: int = 0
        self.done: bool = False

    def add_player(self, power_name: str) -> None:
        if power_name not in self.powers:
            # For now, assign all supply centers as home centers for demo
            self.powers[power_name] = Power(power_name, list(self.map.get_supply_centers()))

    def set_orders(self, power_name: str, orders: List[str]) -> None:
        self.orders[power_name] = orders

    def process_turn(self) -> None:
        self.turn += 1
        # For now, just clear orders and continue
        self.orders = {}
        # Mark done after 10 turns for stub
        if self.turn >= 10:
            self.done = True

    def get_state(self) -> Dict[str, Any]:
        return {
            "map": self.map_name,
            "powers": list(self.powers.keys()),
            "orders": self.orders,
            "turn": self.turn,
            "done": self.done
        }

    def is_game_done(self) -> bool:
        return self.done
