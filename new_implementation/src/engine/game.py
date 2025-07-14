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

        # 2. Collect current unit positions and map orders to actual units
        unit_positions: Dict[str, str] = {}  # full unit identifier -> location
        unit_to_power: Dict[str, str] = {}   # full unit identifier -> power
        
        # Build a mapping from order unit identifiers to actual units
        for power, p in self.powers.items():
            for location in p.units:
                # For each location, find matching orders to determine unit type
                for orders in parsed_orders.values():
                    for order in orders:
                        unit_parts = order.unit.split()
                        if len(unit_parts) == 2 and unit_parts[1] == location:
                            # This order references a unit at this location
                            unit_positions[order.unit] = location
                            unit_to_power[order.unit] = power

        # 3. Parse orders into structured data
        moves: Dict[str, str] = {}  # unit -> destination
        supports: Dict[str, List[str]] = {}  # supported move -> list of supporting units
        convoys: Dict[str, str] = {}  # convoyed unit -> convoy path
        convoy_orders: Dict[str, str] = {}  # fleet -> move being convoyed

        for power, orders in parsed_orders.items():
            for order in orders:
                if order.action == '-' and order.target is not None:
                    # Move order
                    target = order.target.replace(' VIA CONVOY', '')
                    moves[order.unit] = target
                    
                    # Check if this is a convoyed move
                    if 'VIA CONVOY' in order.target:
                        convoys[order.unit] = target
                        
                elif order.action == 'S' and order.target:
                    # Support order
                    if order.target not in supports:
                        supports[order.target] = []
                    supports[order.target].append(order.unit)
                    
                elif order.action == 'C' and order.target:
                    # Convoy order
                    convoy_orders[order.unit] = order.target

        # 4. Calculate support strengths (after support cuts)
        move_strength: Dict[str, int] = {}
        for move_unit, destination in moves.items():
            strength = 1  # Base strength
            move_string = f"{move_unit} - {destination}"
            
            # Add supports
            if move_string in supports:
                for supporting_unit in supports[move_string]:
                    # Check if support is cut
                    support_cut = False
                    supporting_location = unit_positions.get(supporting_unit)
                    if supporting_location:
                        for other_unit, other_dest in moves.items():
                            if other_dest == supporting_location and other_unit != move_unit:
                                support_cut = True
                                break
                    
                    if not support_cut:
                        strength += 1
            
            move_strength[move_unit] = strength

        # 5. Resolve moves (including convoys)
        successful_moves: Dict[str, str] = {}
        failed_moves: set[str] = set()
        
        for move_unit, destination in moves.items():
            # Check if convoy is required and available
            if move_unit in convoys:
                convoy_available = False
                for convoyed_move in convoy_orders.values():
                    expected_convoy = f"{move_unit} - {destination}"
                    if expected_convoy == convoyed_move:
                        convoy_available = True
                        break
                
                if not convoy_available:
                    failed_moves.add(move_unit)
                    continue
            
            # Check for competing moves to the same destination
            competitors = [u for u, d in moves.items() if d == destination and u != move_unit]
            unit_strength = move_strength.get(move_unit, 1)
            
            # Check if this move beats all competitors
            beats_all = True
            for competitor in competitors:
                competitor_strength = move_strength.get(competitor, 1)
                if competitor_strength >= unit_strength:
                    beats_all = False
                    break
            
            # Check if there's a defending unit
            defending_unit = None
            for unit, location in unit_positions.items():
                if location == destination and unit != move_unit:
                    defending_unit = unit
                    break
            
            if defending_unit and defending_unit not in moves:
                # Stationary defender gets 1 strength plus supports
                defend_string = f"{defending_unit} H"
                defend_strength = 1
                if defend_string in supports:
                    for supporting_unit in supports[defend_string]:
                        # Check if support is cut
                        support_cut = False
                        supporting_location = unit_positions.get(supporting_unit)
                        if supporting_location:
                            for other_unit, other_dest in moves.items():
                                if other_dest == supporting_location and other_unit != defending_unit:
                                    support_cut = True
                                    break
                        
                        if not support_cut:
                            defend_strength += 1
                
                # Diplomacy rule: attacker must have GREATER strength than defender to succeed
                if unit_strength <= defend_strength:
                    beats_all = False
            
            if beats_all:
                successful_moves[move_unit] = destination
            else:
                failed_moves.add(move_unit)

        # 6. Update unit positions
        # Clear all unit positions first
        for power in self.powers.values():
            power.units = set()
        
        # Place units in their final positions
        for unit, current_location in unit_positions.items():
            power = unit_to_power[unit]
            
            if unit in successful_moves:
                # Unit moved successfully
                new_location = successful_moves[unit]
                self.powers[power].units.add(new_location)
            elif unit not in failed_moves:
                # Unit stayed in place (hold or no order)
                # Check if it was dislodged
                dislodged = False
                for attack_dest in successful_moves.values():
                    if attack_dest == current_location:
                        dislodged = True
                        break
                
                if not dislodged:
                    self.powers[power].units.add(current_location)
            else:
                # Unit failed to move, stays in original location
                # Check if it was dislodged
                dislodged = False
                for attack_dest in successful_moves.values():
                    if attack_dest == current_location:
                        dislodged = True
                        break
                
                if not dislodged:
                    self.powers[power].units.add(current_location)

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
        # Compose a richer state dictionary for server_spec compliance
        units = {power: list(p.units) for power, p in self.powers.items()}
        return {
            "game_id": getattr(self, "game_id", None),
            "phase": f"Turn {self.turn}",
            "players": list(self.powers.keys()),
            "units": units,
            "orders": self.orders,
            "status": "done" if self.done else "active",
            "turn": self.turn,  # add legacy key for test compatibility
            "turn_number": self.turn,
            "map": self.map_name,
            "powers": list(self.powers.keys()),  # add legacy key for test compatibility
            "done": self.done
        }

    def is_game_done(self) -> bool:
        return self.done
