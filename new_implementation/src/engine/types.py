"""Core value types for the Diplomacy engine (rewrite).

This module is the foundation every other engine module imports. It is **pure**:
no I/O, no database, no rendering, no framework dependencies — only stdlib.

Design decisions (see docs/specs/fix_plan.md, "Target design"):

- **Immutability.** Every type here is a frozen, hashable dataclass or an enum.
  Adjudication is a pure function ``(map, state, orders) -> (Resolution, new_state)``
  and history is a list of ``GameState`` snapshots. Nothing mutates in place.
- **``Location = (province, coast)`` everywhere.** A fleet in Spain is *at*
  ``Location("SPA", "SC")``. Armies never carry a coast. Split-coast provinces
  (BUL, SPA, STP) always carry one for fleets. There are no hardcoded adjacency
  or coast tables anywhere in the engine — ``map_loader`` reads ``standard.map``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UnitKind(Enum):
    """The two unit types. Armies occupy land/coast; fleets occupy water/coast."""

    ARMY = "A"
    FLEET = "F"


class ProvinceType(Enum):
    """Topological class of a province, taken from the ``.map`` file keyword."""

    LAND = "LAND"
    COAST = "COAST"
    WATER = "WATER"


class Season(Enum):
    """The season of a phase. WINTER hosts only adjustment (build/disband) phases."""

    SPRING = "SPRING"
    FALL = "FALL"
    WINTER = "WINTER"


class PhaseType(Enum):
    """What kind of orders a phase accepts."""

    MOVEMENT = "MOVEMENT"
    RETREAT = "RETREAT"
    ADJUSTMENT = "ADJUSTMENT"


class OrderType(Enum):
    """Discriminator for order variants (useful for serialization/dispatch)."""

    HOLD = "HOLD"
    MOVE = "MOVE"
    SUPPORT_HOLD = "SUPPORT_HOLD"
    SUPPORT_MOVE = "SUPPORT_MOVE"
    CONVOY = "CONVOY"
    RETREAT = "RETREAT"
    DISBAND = "DISBAND"
    BUILD = "BUILD"
    WAIVE = "WAIVE"


class ResultCode(Enum):
    """Outcome of adjudicating a single order.

    - ``OK``          — order succeeded (move happened, support held, convoy ran).
    - ``BOUNCE``      — a move failed for lack of strength / standoff.
    - ``CUT``         — a support order was cut by an attack.
    - ``VOID``        — order was illegal/ill-formed and ignored (treated as hold).
    - ``NO_CONVOY``   — a convoyed move had no surviving fleet path.
    - ``DISLODGED``   — the ordered unit was dislodged (annotation, not a command).
    - ``DISBAND``     — a unit was removed (retreat failure / adjustment / civil disorder).
    - ``BUILD``       — a build succeeded.
    - ``WAIVE``       — a build was waived (explicitly or implicitly).
    """

    OK = "OK"
    BOUNCE = "BOUNCE"
    CUT = "CUT"
    VOID = "VOID"
    NO_CONVOY = "NO_CONVOY"
    DISLODGED = "DISLODGED"
    DISBAND = "DISBAND"
    BUILD = "BUILD"
    WAIVE = "WAIVE"


class GameStatus(Enum):
    """Lifecycle of a whole game."""

    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


# The seven standard powers. Kept as a tuple (not an enum) because powers are also
# free-form strings in the map file's power blocks; this is the canonical order.
STANDARD_POWERS: tuple[str, ...] = (
    "AUSTRIA",
    "ENGLAND",
    "FRANCE",
    "GERMANY",
    "ITALY",
    "RUSSIA",
    "TURKEY",
)

# Number of supply centers required to win.
VICTORY_CENTERS = 18


# ---------------------------------------------------------------------------
# Location & Unit
# ---------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Location:
    """A place a unit can be: a province, optionally a specific coast.

    ``province`` is the uppercase 3-letter code (e.g. ``"SPA"``). ``coast`` is one
    of ``"NC"``, ``"SC"``, ``"EC"``, ``"WC"`` for split-coast provinces, else
    ``None``. Armies always use ``coast=None``. Fleets in split-coast provinces
    always name a coast; fleets elsewhere use ``coast=None``.
    """

    province: str
    coast: Optional[str] = None

    def __post_init__(self) -> None:
        if self.province != self.province.upper():
            object.__setattr__(self, "province", self.province.upper())
        if self.coast is not None:
            c = self.coast.upper()
            if c not in ("NC", "SC", "EC", "WC"):
                raise ValueError(f"invalid coast {self.coast!r} for {self.province}")
            object.__setattr__(self, "coast", c)

    @property
    def base(self) -> "Location":
        """This location without its coast (the whole province as a node)."""
        return Location(self.province, None) if self.coast else self

    def __str__(self) -> str:
        return f"{self.province}/{self.coast}" if self.coast else self.province


@dataclass(frozen=True)
class Unit:
    """A unit on the board: kind, owning power, and where it stands."""

    kind: UnitKind
    power: str
    location: Location

    def __post_init__(self) -> None:
        if self.kind is UnitKind.ARMY and self.location.coast is not None:
            raise ValueError(f"army may not carry a coast: {self}")

    @property
    def province(self) -> str:
        return self.location.province

    def __str__(self) -> str:
        return f"{self.kind.value} {self.location}"


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
#
# Every order names the unit's own location (``unit``). Movement-phase orders are
# Hold / Move / SupportHold / SupportMove / Convoy. Retreat-phase orders are
# Retreat / Disband. Adjustment-phase orders are Build / Disband / Waive.
#
# Orders are frozen dataclasses sharing a common ``power`` and ``order_type``.


@dataclass(frozen=True)
class Order:
    """Base class for all orders. Never instantiated directly."""

    power: str

    @property
    def order_type(self) -> OrderType:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class Hold(Order):
    """``A PAR H`` — the unit stays put and defends."""

    unit: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.HOLD


@dataclass(frozen=True)
class Move(Order):
    """``A PAR - BUR`` — move to ``dest``. ``via_convoy`` forces the convoy route."""

    unit: Location
    dest: Location
    via_convoy: bool = False

    @property
    def order_type(self) -> OrderType:
        return OrderType.MOVE


@dataclass(frozen=True)
class SupportHold(Order):
    """``F BRE S A PAR`` — support the unit at ``target`` to hold."""

    unit: Location
    target: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.SUPPORT_HOLD


@dataclass(frozen=True)
class SupportMove(Order):
    """``F BRE S A PIC - BEL`` — support a move from ``origin`` to ``dest``."""

    unit: Location
    origin: Location
    dest: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.SUPPORT_MOVE


@dataclass(frozen=True)
class Convoy(Order):
    """``F NTH C A LON - BEL`` — a fleet convoys an army from ``origin`` to ``dest``."""

    unit: Location
    origin: Location
    dest: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.CONVOY


@dataclass(frozen=True)
class Retreat(Order):
    """``A PAR R BUR`` — a dislodged unit retreats to ``dest``."""

    unit: Location
    dest: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.RETREAT


@dataclass(frozen=True)
class Disband(Order):
    """``D A PAR`` — remove the unit (retreat-phase failure or adjustment)."""

    unit: Location

    @property
    def order_type(self) -> OrderType:
        return OrderType.DISBAND


@dataclass(frozen=True)
class Build(Order):
    """``BUILD A PAR`` — build a new ``kind`` unit at ``location`` (a home SC)."""

    location: Location
    kind: UnitKind

    def __post_init__(self) -> None:
        if self.kind is UnitKind.ARMY and self.location.coast is not None:
            raise ValueError(f"cannot build an army on a coast: {self.location}")

    @property
    def order_type(self) -> OrderType:
        return OrderType.BUILD


@dataclass(frozen=True)
class Waive(Order):
    """``WAIVE`` — decline one owed build."""

    @property
    def order_type(self) -> OrderType:
        return OrderType.WAIVE


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrderResult:
    """The adjudicated outcome of one order.

    ``order`` is the command as submitted; ``result`` is its primary code;
    ``dislodged`` flags whether the ordering unit was dislodged this phase (only
    meaningful in movement/retreat phases). ``retreat_options`` lists the legal
    destinations a dislodged unit may retreat to (empty when not dislodged, or
    when the unit is trapped and must disband).
    """

    order: Order
    result: ResultCode
    dislodged: bool = False
    retreat_options: tuple[Location, ...] = ()


@dataclass(frozen=True)
class Resolution:
    """The full result of adjudicating one phase: one ``OrderResult`` per order."""

    results: tuple[OrderResult, ...] = ()

    def for_unit(self, loc: Location) -> Optional[OrderResult]:
        """Return the result whose order acts on the unit at ``loc``, if any."""
        for r in self.results:
            unit_loc = getattr(r.order, "unit", None) or getattr(r.order, "location", None)
            if unit_loc == loc:
                return r
        return None


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GameState:
    """An immutable snapshot of the whole game between phases.

    - ``units`` — every unit on the board.
    - ``ownership`` — supply-center province → owning power (only SCs appear).
    - ``dislodged`` — units awaiting retreat orders, mapped to the province they
      were dislodged *from's* attacker origin (so a retreat can't bounce back).
      During non-retreat phases this is empty.
    - ``contested`` — provinces that stood off this movement phase (no unit may
      retreat into them). Empty outside a retreat phase.
    """

    year: int
    season: Season
    phase_type: PhaseType
    units: frozenset[Unit] = field(default_factory=frozenset)
    ownership: dict[str, str] = field(default_factory=dict)
    dislodged: frozenset[Unit] = field(default_factory=frozenset)
    contested: frozenset[str] = field(default_factory=frozenset)
    status: GameStatus = GameStatus.ACTIVE

    @property
    def phase_name(self) -> str:
        """Canonical phase code, e.g. ``S1901M``, ``F1901R``, ``W1901A``."""
        season = self.season.value[0]
        kind = {
            PhaseType.MOVEMENT: "M",
            PhaseType.RETREAT: "R",
            PhaseType.ADJUSTMENT: "A",
        }[self.phase_type]
        return f"{season}{self.year}{kind}"

    def units_of(self, power: str) -> frozenset[Unit]:
        return frozenset(u for u in self.units if u.power == power)

    def unit_at(self, province: str) -> Optional[Unit]:
        """The (non-dislodged) unit standing in ``province``, if any."""
        province = province.upper()
        for u in self.units:
            if u.province == province:
                return u
        return None

    def centers_of(self, power: str) -> frozenset[str]:
        return frozenset(p for p, owner in self.ownership.items() if owner == power)
