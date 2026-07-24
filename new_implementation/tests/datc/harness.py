"""Test harness for DATC and adjudicator tests.

Ergonomic helpers to place units, give orders, run one movement adjudication, and
assert per-order outcomes against the new engine API
(``engine.adjudicator.movement.adjudicate_movement``).

Usage::

    h = Harness()
    h.units("FRANCE", "A PAR", "F BRE")
    h.units("GERMANY", "A MUN")
    h.orders("FRANCE", "A PAR - BUR", "F BRE S A PAR - BUR")
    h.orders("GERMANY", "A MUN - BUR")
    h.adjudicate()
    h.assert_success("A PAR")     # France's army reached Burgundy
    h.assert_bounce("A MUN")      # Germany bounced
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.adjudicator.adjustments import adjudicate_adjustments
from engine.adjudicator.movement import adjudicate_movement
from engine.adjudicator.retreats import adjudicate_retreats
from engine.map_loader import MapData, load_standard_map
from engine.orders.parser import parse_order
from engine.types import (
    GameState,
    Location,
    Order,
    PhaseType,
    Resolution,
    ResultCode,
    Season,
    Unit,
    UnitKind,
)

_MAP: MapData | None = None


def standard_map() -> MapData:
    global _MAP
    if _MAP is None:
        _MAP = load_standard_map()
    return _MAP


def _split_coast(token: str) -> tuple[str, str | None]:
    if "/" in token:
        p, c = token.split("/", 1)
        return p.upper(), c.upper()
    return token.upper(), None


def parse_unit(power: str, spec: str) -> Unit:
    """Parse a ``"A PAR"`` / ``"F STP/SC"`` spec into a ``Unit`` for ``power``."""
    kind_tok, loc_tok = spec.split()
    prov, coast = _split_coast(loc_tok)
    kind = UnitKind.ARMY if kind_tok.upper() == "A" else UnitKind.FLEET
    return Unit(kind, power.upper(), Location(prov, coast))


@dataclass
class Harness:
    """Build a movement-phase position, adjudicate it, and assert outcomes."""

    map: MapData = field(default_factory=standard_map)
    year: int = 1901
    season: Season = Season.SPRING
    phase_type: PhaseType = PhaseType.MOVEMENT
    _units: dict[Location, Unit] = field(default_factory=dict)
    _orders: list[Order] = field(default_factory=list)
    _ownership: dict[str, str] = field(default_factory=dict)
    _retreat_orders: list[Order] = field(default_factory=list)
    resolution: Resolution | None = None
    new_state: GameState | None = None
    retreat_resolution: Resolution | None = None
    retreat_state: GameState | None = None

    def units(self, power: str, *specs: str) -> "Harness":
        for spec in specs:
            u = parse_unit(power, spec)
            self._units[u.location] = u
        return self

    def owns(self, power: str, *provinces: str) -> "Harness":
        """Record supply-center ownership (for adjustment-phase tests)."""
        for p in provinces:
            self._ownership[p.upper()] = power.upper()
        return self

    def orders(self, power: str, *order_strings: str) -> "Harness":
        for s in order_strings:
            self._orders.append(parse_order(s, power=power.upper(), map=self.map))
        return self

    def state(self) -> GameState:
        return GameState(
            year=self.year,
            season=self.season,
            phase_type=self.phase_type,
            units=frozenset(self._units.values()),
            ownership=dict(self._ownership),
        )

    def adjudicate(self) -> Resolution:
        self.resolution, self.new_state = adjudicate_movement(
            self.map, self.state(), list(self._orders)
        )
        return self.resolution

    # -- retreat phase ----------------------------------------------------

    def retreats(self, power: str, *order_strings: str) -> "Harness":
        """Queue retreat/disband orders for the retreat phase."""
        for s in order_strings:
            self._retreat_orders.append(parse_order(s, power=power.upper(), map=self.map))
        return self

    def adjudicate_retreats(self) -> Resolution:
        """Adjudicate the retreat phase against the post-movement state."""
        assert self.new_state is not None, "call adjudicate() (movement) first"
        self.retreat_resolution, self.retreat_state = adjudicate_retreats(
            self.map, self.new_state, list(self._retreat_orders)
        )
        return self.retreat_resolution

    def adjudicate_adjustments(self) -> Resolution:
        """Adjudicate an adjustment phase from the harness's own state.

        Use with ``phase_type=PhaseType.ADJUSTMENT``, ``units(...)``, ``owns(...)``
        and ``orders(...)`` (build/disband/waive). Results land in
        ``retreat_resolution``/``retreat_state`` for a uniform assertion surface.
        """
        self.retreat_resolution, self.retreat_state = adjudicate_adjustments(
            self.map, self.state(), list(self._orders)
        )
        return self.retreat_resolution

    # -- lookups ----------------------------------------------------------

    def _loc(self, spec: str) -> Location:
        """Accept either a unit spec ``"A PAR"`` or a bare province ``"PAR"``."""
        parts = spec.split()
        tok = parts[1] if len(parts) == 2 else parts[0]
        prov, coast = _split_coast(tok)
        return Location(prov, coast)

    def _result_at(self, spec: str):
        assert self.resolution is not None, "call adjudicate() first"
        loc = self._loc(spec)
        for r in self.resolution.results:
            unit_loc = getattr(r.order, "unit", None) or getattr(r.order, "location", None)
            if unit_loc == loc or (unit_loc and unit_loc.province == loc.province):
                return r
        raise AssertionError(f"no order result for {spec!r} (loc {loc})")

    # -- assertions -------------------------------------------------------

    def assert_success(self, spec: str) -> None:
        r = self._result_at(spec)
        assert r.result is ResultCode.OK, f"{spec}: expected OK, got {r.result.name}"

    def assert_bounce(self, spec: str) -> None:
        r = self._result_at(spec)
        assert r.result is ResultCode.BOUNCE, f"{spec}: expected BOUNCE, got {r.result.name}"

    def assert_result(self, spec: str, code: ResultCode) -> None:
        r = self._result_at(spec)
        assert r.result is code, f"{spec}: expected {code.name}, got {r.result.name}"

    def assert_dislodged(self, spec: str) -> None:
        r = self._result_at(spec)
        assert r.dislodged, f"{spec}: expected dislodged, was not"

    def assert_not_dislodged(self, spec: str) -> None:
        r = self._result_at(spec)
        assert not r.dislodged, f"{spec}: expected NOT dislodged, but it was"

    def assert_at(self, province: str) -> None:
        """Assert some unit ended the phase standing in ``province``."""
        assert self.new_state is not None
        assert self.new_state.unit_at(province.upper()) is not None, (
            f"expected a unit at {province} after adjudication"
        )

    def assert_empty(self, province: str) -> None:
        assert self.new_state is not None
        assert self.new_state.unit_at(province.upper()) is None, (
            f"expected {province} empty after adjudication"
        )

    def unit_powers_at(self, province: str) -> str | None:
        assert self.new_state is not None
        u = self.new_state.unit_at(province.upper())
        return u.power if u else None

    # -- retreat / adjustment assertions ----------------------------------

    def _retreat_result_at(self, spec: str):
        assert self.retreat_resolution is not None, (
            "call adjudicate_retreats()/adjudicate_adjustments() first"
        )
        loc = self._loc(spec)
        for r in self.retreat_resolution.results:
            unit_loc = getattr(r.order, "unit", None) or getattr(r.order, "location", None)
            if unit_loc == loc or (unit_loc and unit_loc.province == loc.province):
                return r
        raise AssertionError(f"no retreat/adjustment result for {spec!r} (loc {loc})")

    def assert_retreat_ok(self, spec: str) -> None:
        r = self._retreat_result_at(spec)
        assert r.result is ResultCode.OK, f"{spec}: expected retreat OK, got {r.result.name}"

    def assert_disbanded(self, spec: str) -> None:
        r = self._retreat_result_at(spec)
        assert r.result is ResultCode.DISBAND, (
            f"{spec}: expected DISBAND, got {r.result.name}"
        )

    def assert_built(self, spec: str) -> None:
        r = self._retreat_result_at(spec)
        assert r.result is ResultCode.BUILD, f"{spec}: expected BUILD, got {r.result.name}"

    def assert_result_post(self, spec: str, code: ResultCode) -> None:
        r = self._retreat_result_at(spec)
        assert r.result is code, f"{spec}: expected {code.name}, got {r.result.name}"

    def dislodged_provinces(self) -> set[str]:
        """Provinces holding a dislodged unit after movement adjudication."""
        assert self.new_state is not None
        return {du.province for du in self.new_state.dislodged}

    def retreat_options_at(self, province: str) -> set[str]:
        """The legal retreat destination provinces for the unit dislodged at ``province``."""
        assert self.new_state is not None
        du = self.new_state.dislodged_at(province.upper())
        assert du is not None, f"no dislodged unit at {province}"
        return {loc.province for loc in du.retreats}

    def final_at(self, province: str) -> str | None:
        """Power occupying ``province`` after the retreat/adjustment phase."""
        assert self.retreat_state is not None
        u = self.retreat_state.unit_at(province.upper())
        return u.power if u else None

    def unit_count(self, power: str) -> int:
        """Number of units ``power`` has after the retreat/adjustment phase."""
        assert self.retreat_state is not None
        return len(self.retreat_state.units_of(power.upper()))
