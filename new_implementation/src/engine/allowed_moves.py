"""
Precomputed allowed moves for Diplomacy: direct moves and convoy reachability.

Generated from map data (Map) at startup or first load. Used for fast validation
and legal-order generation without traversing the map each time.

- Direct moves: (province, unit_type [, coast]) -> [target_provinces]
- Convoy reachability: coastal -> coastal pairs reachable by some sea path

Convoy movement flow (see also game.py _process_movement_phase):
  1) Unit A orders move from area 1 to area 2.
  2) This module (allowed_moves): the dictionary says whether the move is possible
     (is_convoy_reachable(area1, area2)). If not, validation rejects the order.
  3) Game engine: checks whether there is an actual route of convoy orders
     (fleet chain) that can perform the move; only then does the move get
     convoy strength and succeed in resolution.
  4) Resolution: if any convoying fleet in that route is dislodged, the whole
     convoyed move is cancelled and unit A stays in area 1.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from collections import deque

# Coast-specific adjacencies for multi-coast provinces (mirrors data_models.Province).
# Only fleets use these; keys are province name, values are coast -> list of adjacent provinces.
MULTI_COAST_ADJACENCIES: Dict[str, Dict[str, List[str]]] = {
    "SPA": {
        "NC": ["POR", "GAS", "MAO"],
        "SC": ["MAR", "WES"],
    },
    "BUL": {
        "EC": ["RUM", "BLA"],
        "SC": ["GRE", "AEG"],
    },
    "STP": {
        "NC": ["BAR", "NWG"],
        "SC": ["FIN", "BOT", "LVN"],
    },
}

MULTI_COAST_PROVINCES = frozenset(MULTI_COAST_ADJACENCIES.keys())


def _get_adjacencies_for_province(
    province_name: str,
    provinces: Dict[str, Any],
    coast: Optional[str] = None,
    unit_type: str = "A",
) -> List[str]:
    """
    Return list of adjacent province names relevant for movement.
    For multi-coast provinces with a fleet, uses coast-specific adjacencies.
    """
    if province_name not in provinces:
        return []
    prov = provinces[province_name]
    if unit_type == "F" and province_name in MULTI_COAST_PROVINCES and coast:
        adj = MULTI_COAST_ADJACENCIES.get(province_name, {}).get(coast)
        if adj is not None:
            return list(adj)
    # Default: use map adjacency
    return list(getattr(prov, "adjacent", []) or [])


def _can_unit_enter(unit_type: str, target_type: str) -> bool:
    """Army -> land/coastal; Fleet -> sea/coastal."""
    if unit_type == "A":
        return target_type in ("land", "coastal")
    if unit_type == "F":
        return target_type in ("sea", "coastal")
    return False


def build_direct_moves(map_obj: Any) -> Dict[Tuple[str, ...], List[str]]:
    """
    Build (province, unit_type [, coast]) -> [target_provinces] from a Map.

    Keys are tuples: (province, unit_type) for armies and non-multi-coast fleets;
    (province, unit_type, coast) for fleets in multi-coast provinces (STP, BUL, SPA).
    """
    direct: Dict[Tuple[str, ...], List[str]] = {}
    provinces = getattr(map_obj, "provinces", {})

    for prov_name, prov in provinces.items():
        prov_type = getattr(prov, "type", "land")
        adj_full = list(getattr(prov, "adjacent", []) or [])

        # Army in this province -> can move to adjacent land/coastal
        if prov_type in ("land", "coastal"):
            targets_a = [
                adj for adj in adj_full
                if adj in provinces and _can_unit_enter("A", getattr(provinces[adj], "type", "land"))
            ]
            direct[(prov_name, "A")] = targets_a

        # Fleet in this province
        if prov_type in ("sea", "coastal"):
            if prov_name in MULTI_COAST_PROVINCES:
                for coast, adj_list in MULTI_COAST_ADJACENCIES.get(prov_name, {}).items():
                    targets_f = [
                        adj for adj in adj_list
                        if adj in provinces and _can_unit_enter("F", getattr(provinces[adj], "type", "land"))
                    ]
                    direct[(prov_name, "F", coast)] = targets_f
            else:
                targets_f = [
                    adj for adj in adj_full
                    if adj in provinces and _can_unit_enter("F", getattr(provinces[adj], "type", "land"))
                ]
                direct[(prov_name, "F")] = targets_f

    return direct


def build_convoy_reachable(map_obj: Any) -> Set[Tuple[str, str]]:
    """
    Build set of (from_coastal, to_coastal) pairs reachable by some path of sea/coastal provinces.

    Graph: nodes = sea + coastal provinces; edges = map adjacencies.
    BFS from each coastal province, collect all other coastal provinces reachable.
    """
    provinces = getattr(map_obj, "provinces", {})
    coastal = {p for p, prov in provinces.items() if getattr(prov, "type", "") == "coastal"}
    sea = {p for p, prov in provinces.items() if getattr(prov, "type", "") == "sea"}
    # Nodes that can be used in convoy path: sea and coastal
    convoy_nodes = sea | coastal

    reachable: Set[Tuple[str, str]] = set()
    for start in coastal:
        # BFS from start through convoy_nodes
        seen = {start}
        q = deque([start])
        while q:
            cur = q.popleft()
            prov = provinces.get(cur)
            if not prov:
                continue
            for adj in getattr(prov, "adjacent", []) or []:
                if adj not in convoy_nodes or adj in seen:
                    continue
                seen.add(adj)
                q.append(adj)
                if adj in coastal and adj != start:
                    reachable.add((start, adj))
    return reachable


def build_convoy_reachable_by_source(map_obj: Any) -> Dict[str, List[str]]:
    """
    Same as build_convoy_reachable but as a dict: coastal_province -> [reachable coastal provinces].
    """
    reachable_set = build_convoy_reachable(map_obj)
    by_source: Dict[str, List[str]] = {}
    for from_c, to_c in reachable_set:
        by_source.setdefault(from_c, []).append(to_c)
    for k in by_source:
        by_source[k] = sorted(by_source[k])
    return by_source


class AllowedMoves:
    """
    Precomputed allowed moves for one map. Build once per map (e.g. at game init).
    """

    __slots__ = ("map_name", "direct_moves", "convoy_reachable", "convoy_reachable_by_source")

    def __init__(self, map_name: str, direct_moves: Dict[Tuple[str, ...], List[str]], convoy_reachable: Set[Tuple[str, str]]):
        self.map_name = map_name
        self.direct_moves = direct_moves
        self.convoy_reachable = convoy_reachable
        self.convoy_reachable_by_source = {}
        for from_c, to_c in convoy_reachable:
            self.convoy_reachable_by_source.setdefault(from_c, []).append(to_c)
        for k in self.convoy_reachable_by_source:
            self.convoy_reachable_by_source[k] = sorted(self.convoy_reachable_by_source[k])

    def get_direct_targets(self, province: str, unit_type: str, coast: Optional[str] = None) -> List[str]:
        """Return list of provinces this unit can move to by direct (non-convoy) move."""
        if unit_type == "F" and province in MULTI_COAST_PROVINCES and coast:
            key = (province, unit_type, coast)
        else:
            key = (province, unit_type)
        return self.direct_moves.get(key, [])

    def is_direct_move_allowed(self, from_province: str, to_province: str, unit_type: str, coast: Optional[str] = None) -> bool:
        return to_province in self.get_direct_targets(from_province, unit_type, coast)

    def is_convoy_reachable(self, from_coastal: str, to_coastal: str) -> bool:
        return (from_coastal, to_coastal) in self.convoy_reachable

    def get_convoy_targets(self, from_coastal: str) -> List[str]:
        return self.convoy_reachable_by_source.get(from_coastal, [])

    def to_dict(self) -> Dict[str, Any]:
        """Export for JSON: direct_moves keys as strings, convoy_reachable as list of pairs."""
        direct_ser = {}
        for k, v in self.direct_moves.items():
            direct_ser["|".join(k)] = v
        return {
            "map_name": self.map_name,
            "direct_moves": direct_ser,
            "convoy_reachable": [list(pair) for pair in sorted(self.convoy_reachable)],
        }


def build_allowed_moves(map_obj: Any, map_name: Optional[str] = None) -> AllowedMoves:
    """Build AllowedMoves from a Map instance."""
    name = map_name or getattr(map_obj, "map_name", "standard")
    direct = build_direct_moves(map_obj)
    convoy = build_convoy_reachable(map_obj)
    return AllowedMoves(name, direct, convoy)
