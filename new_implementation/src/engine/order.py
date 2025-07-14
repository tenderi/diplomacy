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
        map_obj = game_state.get("map_obj")  # Should be a Map instance if available
        
        if order.power not in powers:
            return False, f"Power '{order.power}' does not exist."
        if order.power not in units or order.unit not in units[order.power]:
            return False, f"Unit '{order.unit}' does not belong to power '{order.power}'."
        valid_actions = {'-', 'H', 'S', 'C'}
        if order.action not in valid_actions:
            return False, f"Invalid action '{order.action}'. Must be one of {valid_actions}."
        unit_type, unit_loc = order.unit.split()
        # Move validation
        if order.action == '-':
            if not order.target:
                return False, "Move order missing target."
            if map_obj and not map_obj.validate_location(order.target):
                return False, f"Target location '{order.target}' is invalid."
            if map_obj and order.target not in map_obj.get_adjacency(unit_loc):
                return False, f"Target '{order.target}' is not adjacent to '{unit_loc}'."
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
