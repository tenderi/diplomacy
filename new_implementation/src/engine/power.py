"""
Player (Power) management for Diplomacy.
- Represents a player/power, their controlled supply centers, and units.
"""
from typing import List, Set, Optional

class Power:
    """Represents a player (power) in the game."""
    def __init__(self, name: str, home_centers: Optional[List[str]] = None):
        self.name = name
        self.home_centers: Set[str] = set(home_centers or [])
        self.controlled_centers: Set[str] = set(self.home_centers)
        self.units: Set[str] = set()  # Province names where units are present
        self.is_alive: bool = True

    def add_unit(self, province: str):
        self.units.add(province)

    def remove_unit(self, province: str):
        self.units.discard(province)

    def lose_center(self, province: str):
        self.controlled_centers.discard(province)
        if not self.controlled_centers:
            self.is_alive = False

    def gain_center(self, province: str):
        self.controlled_centers.add(province)
        self.is_alive = True
