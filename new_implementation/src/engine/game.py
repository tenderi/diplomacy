from typing import Dict, List, Any
from engine.map import Map
from engine.power import Power
from engine.order import OrderParser, Order

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
        """Process all orders for the current turn using Diplomacy rules (move/hold/support + supply center control)."""
        # 1. Parse and validate all orders
        parsed_orders: Dict[str, List[Order]] = {}
        for power, order_strs in self.orders.items():
            parsed_orders[power] = []
            for order_str in order_strs:
                try:
                    order = OrderParser.parse(order_str)
                    if not OrderParser.validate(order, self.get_state()):
                        continue  # Skip invalid orders
                    parsed_orders[power].append(order)
                except Exception:
                    continue  # Skip invalid orders

        # 2. Adjudicate orders (support cut, standoff, move/hold/support)
        unit_positions: Dict[str, str] = {}
        for power, p in self.powers.items():
            for unit in p.units:
                unit_positions[unit] = unit.split()[-1]

        moves: Dict[str, str] = {}
        supports: Dict[str, int] = {}
        support_cut: Dict[str, bool] = {}
        # First pass: collect moves and supports
        for power, orders in parsed_orders.items():
            for order in orders:
                if order.action == '-' and order.target is not None:
                    moves[order.unit] = order.target
                elif order.action == 'S' and order.target:
                    supports[order.target] = supports.get(order.target, 0) + 1

        # Support cut: if a supporting unit is attacked from a province other than the one it is supporting against, cut the support
        for power, orders in parsed_orders.items():
            for order in orders:
                if order.action == 'S' and order.target:
                    supporter_unit = order.unit
                    supporter_prov = supporter_unit.split()[-1]
                    for atk_power, atk_orders in parsed_orders.items():
                        for atk_order in atk_orders:
                            if atk_order.action == '-' and atk_order.target == supporter_prov:
                                # Only cut if not the unit being supported
                                if not (atk_order.unit == order.target):
                                    support_cut[order.target] = True
        # Remove cut supports
        for cut_target in support_cut:
            if cut_target in supports:
                del supports[cut_target]

        # Moves and standoffs
        new_positions: Dict[str, str] = {}
        contested: Dict[str, List[str]] = {}
        for unit, from_prov in unit_positions.items():
            if unit in moves:
                dest = moves[unit]
                contested.setdefault(dest, []).append(unit)
        # Standoff: if more than one unit moves to the same province, all fail
        for dest, units in contested.items():
            if len(units) > 1:
                for unit in units:
                    new_positions[unit] = unit_positions[unit]
            else:
                unit = units[0]
                strength = 1 + supports.get(unit, 0)
                competitors = [u for u, d in moves.items() if d == dest and u != unit]
                max_strength = strength
                for comp in competitors:
                    comp_strength = 1 + supports.get(comp, 0)
                    if comp_strength > max_strength:
                        max_strength = comp_strength
                if all(1 + supports.get(comp, 0) < strength for comp in competitors):
                    new_positions[unit] = dest
                else:
                    new_positions[unit] = unit_positions[unit]
        # Units not moving or not in standoff
        for unit, from_prov in unit_positions.items():
            if unit not in new_positions:
                new_positions[unit] = from_prov

        # Update units in powers
        for power, p in self.powers.items():
            p.units = set()
        for unit, prov in new_positions.items():
            for power, p in self.powers.items():
                if unit in unit_positions:
                    p.units.add(prov)

        # 3. Update supply center control
        supply_centers = self.map.get_supply_centers()
        province_to_power: Dict[str, str] = {}
        for power, p in self.powers.items():
            for prov in p.units:
                if prov in supply_centers:
                    province_to_power[prov] = power
        for power, p in self.powers.items():
            p.controlled_centers = set()
        for prov, power in province_to_power.items():
            self.powers[power].gain_center(prov)
        for power, p in self.powers.items():
            if not p.controlled_centers:
                p.is_alive = False

        # 4. Clear orders and increment turn
        self.orders = {}
        self.turn += 1
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
