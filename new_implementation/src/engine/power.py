"""
Player (Power) management for Diplomacy using new data models.
- Represents a player/power using the new PowerState data model.
"""
from typing import List, Set, Optional
from datetime import datetime
from .data_models import PowerState, Unit


class Power:
    """Represents a player (power) in the game using new data models."""
    
    def __init__(self, name: str, home_centers: Optional[List[str]] = None) -> None:
        self.name: str = name
        self.home_centers: Set[str] = set(home_centers or [])
        self.controlled_centers: Set[str] = set(self.home_centers)
        self.units: List[Unit] = []  # List of Unit objects
        self.is_alive: bool = True

    def add_unit(self, province: str, unit_type: str = "A") -> None:
        """Add a unit to this power"""
        unit = Unit(unit_type=unit_type, province=province, power=self.name)
        self.units.append(unit)

    def remove_unit(self, province: str) -> None:
        """Remove a unit from this power"""
        self.units = [u for u in self.units if u.province != province]

    def get_unit_at_province(self, province: str) -> Optional[Unit]:
        """Get unit at specific province"""
        for unit in self.units:
            if unit.province == province:
                return unit
        return None

    def lose_center(self, province: str) -> None:
        self.controlled_centers.discard(province)
        if not self.controlled_centers:
            self.is_alive = False

    def gain_center(self, province: str) -> None:
        self.controlled_centers.add(province)
        self.is_alive = True

    def get_unit_count(self) -> int:
        """Get number of units"""
        return len(self.units)

    def get_supply_center_count(self) -> int:
        """Get number of supply centers"""
        return len(self.controlled_centers)

    def needs_builds(self) -> bool:
        """Check if power needs to build units"""
        return self.get_supply_center_count() > self.get_unit_count()

    def needs_destroys(self) -> bool:
        """Check if power needs to destroy units"""
        return self.get_unit_count() > self.get_supply_center_count()

    def to_power_state(self) -> PowerState:
        """Convert to PowerState data model"""
        return PowerState(
            power_name=self.name,
            home_supply_centers=list(self.home_centers),
            controlled_supply_centers=list(self.controlled_centers),
            units=self.units.copy(),
            is_eliminated=not self.is_alive
        )
