"""Load a dpjudge ``.map`` file into an immutable ``MapData`` topology.

The ``.map`` file is the **single source of truth** for the board. No adjacency,
coast, supply-center, or home-center data is hardcoded anywhere in the engine —
it all comes from here.

## dpjudge ``.map`` format (the parts we use)

```
BEGIN SPRING 1901 MOVEMENT          # start phase

AUSTRIA  (AUSTRIAN)  BUD TRI VIE     # power  (adjective)  home supply centers
A BUD                                # starting units, one per line
F TRI
...
UNOWNED  BEL BUL DEN ...             # neutral supply centers

Budapest = bud budapest             # aliases (province code = alternate spellings)
Bulgaria (east coast) = bul/ec ...

COAST  ANK  ABUTS  ARM BLA CON smy   # TYPE  province  ABUTS  neighbours...
```

### Neighbour-token case encodes passability (the crucial rule)

In an ``ABUTS`` list the **case** of each neighbour says which unit type may use
the edge:

- **lowercase** neighbour → *army-only* edge (a fleet may not traverse it).
  E.g. ``COAST ANK ABUTS ... smy`` — an army in Ankara can reach Smyrna, a fleet
  cannot (they don't share a coastline).
- **UPPERCASE** neighbour → *fleet-capable* edge (and army-capable too, unless
  the destination is water).

So army moves = all non-water neighbours (case ignored); fleet moves = uppercase
neighbours that are not land. Split-coast provinces list three entries — the two
coast nodes (``BUL/EC``, ``BUL/SC``) give fleet adjacency; the bare lowercase
node (``bul``) gives the army adjacency for the whole province.

Provinces that are referenced only as neighbours but have no ``ABUTS`` line of
their own (Switzerland) are impassable and dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from engine.types import Location, ProvinceType, Season, Unit, UnitKind

_ADJ_KEYWORDS = {"WATER", "COAST", "LAND"}
_HEADER_RE = re.compile(
    r"^BEGIN\s+(\w+)\s+(\d+)\s+(\w+)\s*$", re.IGNORECASE
)


def _split_token(token: str) -> tuple[str, Optional[str]]:
    """Split a neighbour/location token like ``BUL/SC`` into ``("BUL", "SC")``.

    A bare token like ``ank`` returns ``("ANK", None)``.
    """
    if "/" in token:
        prov, coast = token.split("/", 1)
        return prov.upper(), coast.upper()
    return token.upper(), None


@dataclass(frozen=True)
class _RawEntry:
    """One parsed ``ABUTS`` line, before adjacency graphs are built."""

    ptype: ProvinceType
    base: str
    coast: Optional[str]  # the coast this node represents, or None for the bare node
    neighbours: tuple[str, ...]  # neighbour tokens as written (case preserved)


@dataclass(frozen=True)
class MapData:
    """Immutable board topology.

    Query API:
      - ``army_moves(province)``    → provinces an army there may move to
      - ``fleet_moves(location)``   → fleet locations a fleet there may move to
      - ``adjacent(location, kind)``→ generic reachable set for a unit kind
      - ``is_adjacent(a, b, kind)`` → adjacency predicate
      - ``is_supply_center(prov)``  → bool
      - ``province_type(prov)``     → ProvinceType
      - ``coasts_of(prov)``         → the split coasts, e.g. ``("EC", "SC")`` or ()
      - ``fleet_locations(prov)``   → fleet nodes for a province
    """

    provinces: frozenset[str]
    province_types: dict[str, ProvinceType]
    supply_centers: frozenset[str]
    home_centers: dict[str, frozenset[str]]
    aliases: dict[str, str]  # alternate spelling → canonical province code
    display_names: dict[str, str]  # canonical code → human-readable name ("BER" → "Berlin")
    starting_units: frozenset[Unit]
    initial_ownership: dict[str, str]  # home SC province → owning power
    start_year: int
    start_season: Season
    _army_adj: dict[str, frozenset[str]] = field(default_factory=dict)
    _fleet_adj: dict[Location, frozenset[Location]] = field(default_factory=dict)
    _split_coasts: dict[str, tuple[str, ...]] = field(default_factory=dict)

    # -- queries -----------------------------------------------------------

    def province_type(self, province: str) -> ProvinceType:
        return self.province_types[province.upper()]

    def is_supply_center(self, province: str) -> bool:
        return province.upper() in self.supply_centers

    def coasts_of(self, province: str) -> tuple[str, ...]:
        """Return the split coasts of a province (``()`` if not split)."""
        return self._split_coasts.get(province.upper(), ())

    def is_split_coast(self, province: str) -> bool:
        return bool(self._split_coasts.get(province.upper()))

    def fleet_locations(self, province: str) -> tuple[Location, ...]:
        """The fleet node(s) for a province: one per coast, or a single bare node."""
        province = province.upper()
        coasts = self._split_coasts.get(province)
        if coasts:
            return tuple(Location(province, c) for c in coasts)
        if self.province_types[province] is ProvinceType.LAND:
            return ()
        return (Location(province, None),)

    def army_moves(self, province: str) -> frozenset[str]:
        return self._army_adj.get(province.upper(), frozenset())

    def fleet_moves(self, location: Location) -> frozenset[Location]:
        return self._fleet_adj.get(location, frozenset())

    def adjacent(self, location: Location, kind: UnitKind) -> frozenset[Location]:
        if kind is UnitKind.ARMY:
            return frozenset(Location(p, None) for p in self.army_moves(location.base.province))
        return self.fleet_moves(location)

    def is_adjacent(self, a: Location, b: Location, kind: UnitKind) -> bool:
        if kind is UnitKind.ARMY:
            return b.province in self.army_moves(a.province)
        return b in self.fleet_moves(a)


def load_map(path: str | Path) -> MapData:
    """Parse a ``.map`` file at ``path`` into a ``MapData``."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    start_year = 1901
    start_season = Season.SPRING
    home_centers: dict[str, frozenset[str]] = {}
    neutral_scs: set[str] = set()
    starting_units: set[Unit] = set()
    initial_ownership: dict[str, str] = {}
    alias_groups: list[tuple[str, list[str]]] = []  # (full name, alternate spellings)
    raw_entries: list[_RawEntry] = []

    current_power: Optional[str] = None

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        header = _HEADER_RE.match(line.strip())
        if header:
            start_season = Season[header.group(1).upper()]
            start_year = int(header.group(2))
            continue

        tokens = line.split()
        first = tokens[0].upper()

        # Adjacency line: "TYPE  CODE  ABUTS  n1 n2 ..."
        if first in _ADJ_KEYWORDS and len(tokens) >= 3 and tokens[2].upper() == "ABUTS":
            base, coast = _split_token(tokens[1])
            raw_entries.append(
                _RawEntry(
                    ptype=ProvinceType[first],
                    base=base,
                    coast=coast,
                    neighbours=tuple(tokens[3:]),
                )
            )
            current_power = None
            continue

        # Alias line: "Full Name = a b c". The canonical code is resolved later
        # (once the province set is known) to the spelling that names a real
        # province — the first token is NOT reliably canonical (e.g. Tyrolia's
        # line lists `trl` first, but the board node is `TYR`).
        #
        # The left-hand side is the province's human-readable name and is kept
        # too, for `display_names` (G2). It used to be discarded, which is why
        # every client surface could only ever show 3-letter codes.
        if "=" in line:
            lhs, _, rhs = line.partition("=")
            spellings = rhs.split()
            if spellings:
                alias_groups.append((lhs.strip(), spellings))
            current_power = None
            continue

        # Unit line inside a power block: "A BUD" / "F STP/SC"
        if first in ("A", "F") and current_power is not None and len(tokens) == 2:
            base, coast = _split_token(tokens[1])
            kind = UnitKind.ARMY if first == "A" else UnitKind.FLEET
            starting_units.add(Unit(kind, current_power, Location(base, coast)))
            continue

        # UNOWNED line: neutral supply centers.
        if first == "UNOWNED":
            neutral_scs.update(t.upper() for t in tokens[1:])
            current_power = None
            continue

        # Power block header: "AUSTRIA (AUSTRIAN) BUD TRI VIE"
        if "(" in line and ")" in line:
            power = first
            homes = {t.upper() for t in tokens if "(" not in t and ")" not in t}
            homes.discard(power)
            home_centers[power] = frozenset(homes)
            for sc in homes:
                initial_ownership[sc] = power
            current_power = power
            continue

    # ------------------------------------------------------------------
    # Build the topology from the raw entries.
    # ------------------------------------------------------------------
    defined: set[str] = {e.base for e in raw_entries}

    # Resolve each alias group to the province it actually names: the spelling
    # whose base is a real (defined) province. Groups that name only impassable
    # provinces (Switzerland) resolve to nothing and are dropped.
    aliases: dict[str, str] = {}
    display_names: dict[str, str] = {}
    for lhs, spellings in alias_groups:
        canonical: Optional[str] = None
        canonical_is_bare = False
        for spelling in spellings:
            base, coast = _split_token(spelling)
            if base in defined:
                canonical = base
                canonical_is_bare = coast is None
                break
        if canonical is None:
            continue
        for spelling in spellings:
            aliases[spelling.lower()] = canonical
        # Display name: take it only from the *bare* province line. Split-coast
        # provinces have three lines each -- "Bulgaria (east coast)",
        # "Bulgaria (south coast)", "Bulgaria" -- and all three resolve to BUL,
        # so without this the coast-qualified name could win and every client
        # would render plain BUL as "Bulgaria (east coast)".
        if canonical_is_bare and lhs and canonical not in display_names:
            display_names[canonical] = lhs

    province_types: dict[str, ProvinceType] = {}
    split_coasts: dict[str, list[str]] = {}
    army_entry: dict[str, _RawEntry] = {}  # base → its bare (coast-None) entry
    coast_entries: dict[str, list[_RawEntry]] = {}  # base → its /XX entries

    for e in raw_entries:
        province_types.setdefault(e.base, e.ptype)
        if e.coast is None:
            army_entry[e.base] = e
        else:
            split_coasts.setdefault(e.base, []).append(e.coast)
            coast_entries.setdefault(e.base, []).append(e)

    # Army adjacency: from each base's bare entry, all non-water neighbours.
    army_adj: dict[str, frozenset[str]] = {}
    for base, entry in army_entry.items():
        if province_types[base] is ProvinceType.WATER:
            continue  # armies never occupy water
        dests: set[str] = set()
        for tok in entry.neighbours:
            nb, _coast = _split_token(tok)
            if nb in defined and province_types.get(nb) is not ProvinceType.WATER:
                dests.add(nb)
        army_adj[base] = frozenset(dests)

    # Fleet adjacency: per fleet node, uppercase neighbours that are not land.
    fleet_adj: dict[Location, frozenset[Location]] = {}

    def _fleet_dests(entry: _RawEntry) -> frozenset[Location]:
        dests: set[Location] = set()
        for tok in entry.neighbours:
            if tok != tok.upper():
                continue  # lowercase → army-only edge
            nb, coast = _split_token(tok)
            if nb not in defined or province_types.get(nb) is ProvinceType.LAND:
                continue
            dests.add(Location(nb, coast))
        return frozenset(dests)

    for base in defined:
        if base in coast_entries:
            for e in coast_entries[base]:
                fleet_adj[Location(base, e.coast)] = _fleet_dests(e)
        else:
            entry = army_entry[base]
            if province_types[base] is ProvinceType.LAND:
                continue  # no fleet node on pure land
            fleet_adj[Location(base, None)] = _fleet_dests(entry)

    supply_centers = frozenset(neutral_scs | set(initial_ownership))

    return MapData(
        provinces=frozenset(defined),
        province_types=province_types,
        supply_centers=supply_centers,
        home_centers=home_centers,
        aliases=aliases,
        display_names=display_names,
        starting_units=frozenset(starting_units),
        initial_ownership=dict(initial_ownership),
        start_year=start_year,
        start_season=start_season,
        _army_adj=army_adj,
        _fleet_adj=fleet_adj,
        _split_coasts={b: tuple(sorted(cs)) for b, cs in split_coasts.items()},
    )


_DEFAULT_MAP_PATH = Path(__file__).resolve().parents[2] / "maps" / "standard.map"


def load_standard_map() -> MapData:
    """Load the bundled ``maps/standard.map``."""
    return load_map(_DEFAULT_MAP_PATH)
