"""
Order parsing and validation for Diplomacy.
- Defines order types and basic parsing/validation stubs.
"""
from typing import Optional, Dict, Any

class Order:
    """Represents a Diplomacy order (move, hold, support, convoy, etc.)."""
    def __init__(self, power: str, unit: str, action: str, target: Optional[str] = None) -> None:
        self.power: str = power
        self.unit: str = unit  # e.g., 'A PAR' or 'F BRE'
        self.action: str = action  # e.g., 'H', '-', 'S', 'C'
        self.target: Optional[str] = target  # e.g., 'BUR' for move, or 'A MAR' for support

    def __repr__(self) -> str:
        return f"Order({self.power}, {self.unit}, {self.action}, {self.target})"

class OrderParser:
    """Order parsing and validation for Diplomacy orders."""
    @staticmethod
    def parse(order_str: str) -> 'Order':
        # Parse order string: e.g. 'FRANCE A PAR - BUR' or 'FRANCE F BRE H'
        tokens = order_str.strip().split()
        if len(tokens) < 4:
            raise ValueError("Invalid order format. Expected: <POWER> <UNIT_TYPE> <UNIT_LOC> <ACTION> <TARGET?>")
        power: str = tokens[0]
        unit_type: str = tokens[1]  # 'A' or 'F'
        unit_loc: str = tokens[2]   # e.g. 'PAR'
        action: str = tokens[3]     # '-', 'H', 'S', 'C', etc.
        
        # Handle multi-word targets (e.g., convoy, support)
        if len(tokens) > 4:
            target: Optional[str] = ' '.join(tokens[4:])
        else:
            target = None
            
        unit: str = f"{unit_type} {unit_loc}"
        return Order(power, unit, action, target)

    @staticmethod
    def validate(order: 'Order', game_state: Dict[str, Any]) -> tuple[bool, str]:
        # Enhanced validation with detailed error messages
        powers = game_state.get("powers", [])
        units = game_state.get("units", {})
        
        if order.power not in powers:
            return False, f"Power '{order.power}' does not exist."
        if order.power not in units or order.unit not in units[order.power]:
            return False, f"Unit '{order.unit}' does not belong to power '{order.power}'."
        valid_actions = {'-', 'H', 'S', 'C'}
        if order.action not in valid_actions:
            return False, f"Invalid action '{order.action}'. Must be one of {valid_actions}."
        unit_type, _ = order.unit.split()
        # Move validation
        if order.action == '-':
            if not order.target:
                return False, "Move order missing target."
            
            # Check adjacency for move orders
            unit_location = order.unit.split()[-1]  # Get the province from unit
            target_location = order.target.replace(' VIA CONVOY', '')  # Remove convoy marker
            
            # Get the map object from game state
            map_obj = game_state.get("map_obj")
            if map_obj:
                # Check if the move is to an adjacent province
                adjacent_provinces = map_obj.get_adjacency(unit_location)
                if target_location not in adjacent_provinces:
                    # Check if this could be a convoy move
                    if 'VIA CONVOY' in order.target:
                        # Allow convoy moves (they will be validated during processing)
                        pass
                    else:
                        # Check if there are any convoy orders that could support this move
                        # We need to check current orders for convoy orders
                        current_orders = game_state.get("orders", {})
                        power_orders = current_orders.get(order.power, [])
                        
                        # Look for a convoy order that matches this move
                        has_convoy_support = False
                        for order_str in power_orders:
                            if ' C ' in order_str:
                                # This is a convoy order, check if it supports our move
                                convoy_target = order_str.split(' C ')[-1]
                                expected_convoy_target = f"{order.unit} - {target_location}"
                                if convoy_target == expected_convoy_target:
                                    has_convoy_support = True
                                    break
                        
                        if not has_convoy_support:
                            return False, f"Cannot move from '{unit_location}' to '{target_location}' - not adjacent and no convoy support."
                # --- NEW: Check unit type vs province type ---
                target_prov = map_obj.get_province(target_location)
                if target_prov:
                    if unit_type == 'A' and target_prov.type == 'water':
                        return False, f"Army cannot move to water province '{target_location}'."
                    if unit_type == 'F' and target_prov.type == 'land':
                        return False, f"Fleet cannot move to land province '{target_location}'."
                # Fleets can move to 'water' or 'coast', armies to 'land' or 'coast'.
        # Support validation
        if order.action == 'S':
            if not order.target:
                return False, "Support order missing target."
            # Optionally, parse and check supported order
        # Convoy validation
        if order.action == 'C':
            if unit_type != 'F':
                return False, "Only fleets can perform convoy orders."
            if not order.target:
                return False, "Convoy order missing target."
        # Hold validation
        if order.action == 'H' and order.target:
            return False, "Hold order should not have a target."
        return True, ""

    @staticmethod
    def generate_legal_orders(power: str, unit: str, game_state: dict) -> list[str]:
        """
        Generate all legal order strings for the given unit and power in the current game state.
        Args:
            power: The power (player) issuing the order (e.g., 'FRANCE').
            unit: The unit identifier (e.g., 'A PAR', 'F BRE').
            game_state: The current game state dict, must include 'units' and 'map_obj'.
        Returns:
            List of valid order strings for this unit (e.g., 'FRANCE A PAR - BUR', 'FRANCE A PAR H', ...).
        Logic:
            - Hold: Always legal for any unit.
            - Move: To any adjacent province (type-checked for army/fleet).
            - Support: Support hold or move for any adjacent unit (if adjacency allows).
            - Convoy: For fleets in water, convoy any adjacent army to any adjacent province.
        """
        orders = []
        units = game_state.get("units", {}).get(power, [])
        map_obj = game_state.get("map_obj")
        if unit not in units or map_obj is None:
            return []
        unit_type, unit_loc = unit.split()
        # Hold is always legal
        orders.append(f"{power} {unit} H")  # Hold order
        # Move orders
        for adj in map_obj.get_adjacency(unit_loc):
            target_prov = map_obj.get_province(adj)
            if not target_prov:
                continue
            if unit_type == 'A' and target_prov.type == 'water':
                continue  # Armies can't move to water
            if unit_type == 'F' and target_prov.type == 'land':
                continue  # Fleets can't move to land
            orders.append(f"{power} {unit} - {adj}")  # Move order
        # Support orders (support hold and support move for adjacent units)
        for other_power, other_units in game_state.get("units", {}).items():
            for other_unit in other_units:
                if other_unit == unit:
                    continue
                other_type, other_loc = other_unit.split()
                # Support hold (if adjacent)
                if map_obj.is_adjacent(unit_loc, other_loc):
                    orders.append(f"{power} {unit} S {other_unit} H")  # Support hold
                # Support move (if adjacent to both)
                for move_target in map_obj.get_adjacency(other_loc):
                    if map_obj.is_adjacent(unit_loc, other_loc):
                        orders.append(f"{power} {unit} S {other_unit} - {move_target}")  # Support move
        # Convoy orders (only for fleets in water)
        if unit_type == 'F' and map_obj.get_province(unit_loc).type == 'water':
            # Find all armies that could be convoyed
            for other_power, other_units in game_state.get("units", {}).items():
                for other_unit in other_units:
                    if other_unit == unit:
                        continue
                    o_type, o_loc = other_unit.split()
                    if o_type != 'A':
                        continue
                    # If this fleet is adjacent to the army, allow convoy
                    if map_obj.is_adjacent(unit_loc, o_loc):
                        # Try all possible destinations for the army
                        for dest in map_obj.get_adjacency(unit_loc):
                            orders.append(f"{power} {unit} C {other_unit} - {dest}")  # Convoy order
        return orders
