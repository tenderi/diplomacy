"""
Order parsing and validation for Diplomacy.
- Defines order types and basic parsing/validation stubs.
"""
from typing import List, Optional

class Order:
    """Represents a Diplomacy order (move, hold, support, convoy, etc.)."""
    def __init__(self, power: str, unit: str, action: str, target: Optional[str] = None):
        self.power = power
        self.unit = unit  # e.g., 'A PAR' or 'F BRE'
        self.action = action  # e.g., 'H', '-', 'S', 'C'
        self.target = target  # e.g., 'BUR' for move, or 'A MAR' for support

    def __repr__(self):
        return f"Order({self.power}, {self.unit}, {self.action}, {self.target})"

class OrderParser:
    """Stub for order parsing and validation."""
    @staticmethod
    def parse(order_str: str) -> Order:
        # Very basic parser; expand for full DAIDE/standard syntax
        tokens = order_str.strip().split()
        if len(tokens) < 3:
            raise ValueError("Invalid order format")
        power = tokens[0]
        unit = tokens[1]
        action = tokens[2]
        target = tokens[3] if len(tokens) > 3 else None
        return Order(power, unit, action, target)

    @staticmethod
    def validate(order: Order) -> bool:
        # Stub: always returns True for now
        return True
