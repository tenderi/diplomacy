"""
Map representation for Diplomacy.
- Represents provinces, supply centers, adjacency, and coasts.
- Loads map data (for now, hardcoded for classic map; later, can load from file).
"""

from typing import Dict, List, Set, Optional

class Province:
    """Represents a province on the Diplomacy map."""
    def __init__(self, name: str, is_supply_center: bool = False, coasts: Optional[List[str]] = None):
        self.name = name
        self.is_supply_center = is_supply_center
        self.coasts = coasts or []
        self.adjacent: Set[str] = set()

    def add_adjacent(self, province: str):
        self.adjacent.add(province)

class Map:
    """Represents the Diplomacy map, including provinces and their adjacencies."""
    def __init__(self):
        self.provinces: Dict[str, Province] = {}
        self.supply_centers: Set[str] = set()
        self._init_classic_map()

    def _init_classic_map(self):
        # Minimal classic map for demonstration; expand as needed
        for name, is_sc in [
            ("PAR", True), ("MAR", True), ("BRE", True), ("BUR", False), ("PIC", False)
        ]:
            self.provinces[name] = Province(name, is_supply_center=is_sc)
            if is_sc:
                self.supply_centers.add(name)
        # Example adjacencies
        self.provinces["PAR"].add_adjacent("BUR")
        self.provinces["PAR"].add_adjacent("PIC")
        self.provinces["PAR"].add_adjacent("BRE")
        self.provinces["MAR"].add_adjacent("BUR")
        self.provinces["MAR"].add_adjacent("PAR")
        self.provinces["MAR"].add_adjacent("BRE")
        # ...add more as needed

    def get_province(self, name: str) -> Optional[Province]:
        return self.provinces.get(name)

    def is_adjacent(self, from_prov: str, to_prov: str) -> bool:
        return to_prov in self.provinces[from_prov].adjacent

    def get_supply_centers(self) -> Set[str]:
        return self.supply_centers
