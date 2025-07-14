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
        target: Optional[str] = tokens[4] if len(tokens) > 4 else None
        unit: str = f"{unit_type} {unit_loc}"
        return Order(power, unit, action, target)

    @staticmethod
    def validate(order: 'Order', game_state: Dict[str, Any]) -> bool:
        # Validate order against the game state
        # Check power exists
        if order.power not in game_state.get("powers", []):
            return False
        # Check unit format
        if not order.unit:
            return False
        # Check action is valid
        valid_actions = {'-', 'H', 'S', 'C'}
        if order.action not in valid_actions:
            return False
        # If move, check target is a valid province
        if order.action == '-' and not order.target:
            return False
        # TODO: Add adjacency and ownership checks using map and power
        return True
