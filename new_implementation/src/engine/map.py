"""
Map representation for Diplomacy.
- Represents provinces, supply centers, adjacency, and coasts.
- Loads map data (for now, hardcoded for classic map; later, can load from file).
"""

from typing import Dict, List, Set, Optional

class Province:
    """Represents a province on the Diplomacy map."""
    def __init__(self, name: str, is_supply_center: bool = False, coasts: Optional[List[str]] = None) -> None:
        self.name: str = name
        self.is_supply_center: bool = is_supply_center
        self.coasts: List[str] = coasts or []
        self.adjacent: Set[str] = set()

    def add_adjacent(self, province: str) -> None:
        self.adjacent.add(province)

class Map:
    """Represents the Diplomacy map, including provinces and their adjacencies."""
    def __init__(self, map_name: str = 'standard') -> None:
        self.provinces: Dict[str, Province] = {}
        self.supply_centers: Set[str] = set()
        self.map_name: str = map_name
        self._init_map(map_name)

    def _init_map(self, map_name: str) -> None:
        if map_name == 'standard':
            self._init_classic_map()
        else:
            # TODO: Load map from file for variants
            self._init_classic_map()

    def _init_classic_map(self) -> None:
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

    def get_locations(self) -> List[str]:
        return list(self.provinces.keys())

    def get_adjacency(self, location: str) -> List[str]:
        prov = self.get_province(location)
        if prov:
            return list(prov.adjacent)
        return []

    def validate_location(self, location: str) -> bool:
        return location in self.provinces
