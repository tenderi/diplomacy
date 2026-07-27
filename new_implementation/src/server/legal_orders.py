"""Phase-aware legal-order enumeration for a power's units.

Pure module: no FastAPI, no DB, no ``game_service`` import. It takes a
``MapData`` + ``GameState`` (+ a power name) and returns plain data — a dict
of JSON-serializable values — so it is directly unit-testable without a
running server or database, and so any caller (the HTTP routes, the
Telegram bot, a future DAIDE surface) gets the same answer.

The old ``GET /games/{id}/legal_orders/{power}/{unit}`` route enumerated
moves from map topology alone, ignoring ``state.phase_type`` entirely. That
meant retreat phases offered movement orders for dislodged units (which fail
validation) and adjustment phases offered movement orders too — which
*pass* validation and then get silently dropped by the adjustment
adjudicator, waiving a player's build with no error anywhere. This module
enumerates the right order shapes per phase:

- **MOVEMENT** — hold / move / support-hold / support-move / convoy, per unit
  actually on the board for ``power``.
- **RETREAT** — retreat / disband, per ``DislodgedUnit`` belonging to
  ``power``. Retreat destinations are read from the already-computed
  ``DislodgedUnit.retreats`` (see ``engine.adjudicator.retreats.
  compute_retreat_options``) — retreat legality is not recomputed here.
- **ADJUSTMENT** — build/waive or disband, computed from the same
  ``centers - units`` delta the adjustment adjudicator uses
  (``engine.adjudicator.adjustments.adjudicate_adjustments``). Build
  candidates are generated and filtered by
  ``engine.orders.validation.legal_builds`` (which wraps the existing,
  unmodified ``_validate_build``) rather than re-deriving home-centre /
  ownership / occupancy / coast rules here.

Every order string is produced via ``engine.orders.parser.format_order``
with an explicit ``kind_by_province`` override for every unit involved in
that particular order. This matters: without it, ``format_order`` infers the
"A"/"F" letter from coast presence alone, so a fleet at a non-split-coast
province (Brest, London, ...) would print as "A". Passing the real kind for
every province named in the order keeps every emitted string truthful.
"""

from __future__ import annotations

from typing import Any

from engine.map_loader import MapData
from engine.orders.parser import format_order
from engine.orders.validation import legal_builds
from engine.types import (
    Convoy,
    Disband,
    DislodgedUnit,
    GameState,
    Hold,
    Location,
    Move,
    PhaseType,
    ProvinceType,
    Retreat,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
)

__all__ = ["legal_orders_for_power"]


def legal_orders_for_power(map: MapData, state: GameState, power: str) -> dict[str, Any]:
    """All legal order strings for ``power``'s units in the current phase.

    Returns::

        {
          "phase": "W1901A",
          "phase_type": "ADJUSTMENT",
          "power": "FRANCE",
          "units": [{"kind": "F", "location": "STP/SC", "province": "STP", "coast": "SC"}],
          "orders_by_unit": {"F STP/SC": ["F STP/SC H", "F STP/SC - BOT", ...]},
          "orders": [...],                       # flat, deduplicated, sorted
          "adjustment": {"delta": 2, "action": "build", "slots": 2},  # ADJUSTMENT only
        }

    Every key of ``orders_by_unit`` is exactly ``f"{kind} {location}"`` (coast
    included), and every string in that bucket starts with that key. ``WAIVE``
    is not unit-specific and so appears only in the flat ``orders`` list, not
    under any ``orders_by_unit`` key.
    """
    power = power.upper()
    out: dict[str, Any] = {
        "phase": state.phase_name,
        "phase_type": state.phase_type.value,
        "power": power,
    }

    flat: list[str]
    if state.phase_type is PhaseType.MOVEMENT:
        units = sorted(state.units_of(power), key=_unit_key)
        orders_by_unit, flat = _movement_orders(map, state, power, units)
        out["units"] = [_unit_info(u.kind, u.location) for u in units]
    elif state.phase_type is PhaseType.RETREAT:
        dus = sorted(
            (du for du in state.dislodged if du.power == power),
            key=lambda du: _loc_key(du.location),
        )
        orders_by_unit, flat = _retreat_orders(power, dus)
        out["units"] = [_unit_info(du.kind, du.location) for du in dus]
    else:
        units = sorted(state.units_of(power), key=_unit_key)
        orders_by_unit, flat, adjustment = _adjustment_orders(map, state, power)
        out["units"] = [_unit_info(u.kind, u.location) for u in units]
        out["adjustment"] = adjustment

    out["orders_by_unit"] = {k: sorted(set(v)) for k, v in orders_by_unit.items()}
    out["orders"] = sorted(set(flat))
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _loc_key(loc: Location) -> tuple[str, str]:
    return (loc.province, loc.coast or "")


def _unit_key(unit: Unit) -> tuple[str, str]:
    return _loc_key(unit.location)


def _unit_info(kind: UnitKind, location: Location) -> dict[str, Any]:
    return {
        "kind": kind.value,
        "location": str(location),
        "province": location.province,
        "coast": location.coast,
    }


def _can_reach(map: MapData, frm: Location, kind: UnitKind, dest_province: str) -> bool:
    """Whether a unit of ``kind`` at ``frm`` could reach (any coast of) ``dest_province``.

    Mirrors ``engine.orders.validation._can_reach_province`` (support range,
    which ignores the supported unit's specific coast). Duplicated locally
    rather than imported since it is a private helper of that module.
    """
    if kind is UnitKind.ARMY:
        return dest_province in map.army_moves(frm.province)
    return any(loc.province == dest_province for loc in map.fleet_moves(frm))


def _own_moves(map: MapData, unit: Unit) -> list[Location]:
    """Destinations ``unit`` could move to directly, coast-correct for fleets."""
    if unit.kind is UnitKind.ARMY:
        return sorted(
            (Location(p) for p in map.army_moves(unit.province)), key=_loc_key
        )
    return sorted(map.fleet_moves(unit.location), key=_loc_key)


# -- MOVEMENT -----------------------------------------------------------------


def _movement_orders(
    map: MapData, state: GameState, power: str, units: list[Unit]
) -> tuple[dict[str, list[str]], list[str]]:
    orders_by_unit: dict[str, list[str]] = {}
    flat: list[str] = []
    all_units = sorted(state.units, key=_unit_key)

    for u in units:
        key = f"{u.kind.value} {u.location}"
        own_kbp = {u.province: u.kind.value}
        bucket: list[str] = [format_order(Hold(power, unit=u.location), own_kbp)]

        for dest in _own_moves(map, u):
            bucket.append(format_order(Move(power, unit=u.location, dest=dest), own_kbp))

        for other in all_units:
            if other.province == u.province:
                continue
            if not _can_reach(map, u.location, u.kind, other.province):
                continue
            support_kbp = {u.province: u.kind.value, other.province: other.kind.value}
            bucket.append(
                format_order(
                    SupportHold(power, unit=u.location, target=other.location), support_kbp
                )
            )
            for dest in _own_moves(map, other):
                if not _can_reach(map, u.location, u.kind, dest.province):
                    continue
                bucket.append(
                    format_order(
                        SupportMove(
                            power, unit=u.location, origin=other.location, dest=dest
                        ),
                        support_kbp,
                    )
                )

        if u.kind is UnitKind.FLEET and map.province_type(u.province) is ProvinceType.WATER:
            coastal = sorted(
                {
                    loc.province
                    for loc in map.fleet_moves(u.location)
                    if map.province_type(loc.province) is ProvinceType.COAST
                }
            )
            for origin_prov in coastal:
                for dest_prov in coastal:
                    if origin_prov == dest_prov:
                        continue
                    bucket.append(
                        format_order(
                            Convoy(
                                power,
                                unit=u.location,
                                origin=Location(origin_prov),
                                dest=Location(dest_prov),
                            ),
                            own_kbp,
                        )
                    )

        orders_by_unit[key] = bucket
        flat.extend(bucket)

    return orders_by_unit, flat


# -- RETREAT --------------------------------------------------------------


def _retreat_orders(
    power: str, dus: list[DislodgedUnit]
) -> tuple[dict[str, list[str]], list[str]]:
    orders_by_unit: dict[str, list[str]] = {}
    flat: list[str] = []

    for du in dus:
        key = f"{du.kind.value} {du.location}"
        kbp = {du.province: du.kind.value}
        bucket: list[str] = []
        for dest in du.retreats:
            bucket.append(format_order(Retreat(power, unit=du.location, dest=dest), kbp))
        bucket.append(format_order(Disband(power, unit=du.location), kbp))
        orders_by_unit[key] = bucket
        flat.extend(bucket)

    return orders_by_unit, flat


# -- ADJUSTMENT -------------------------------------------------------------


def _adjustment_orders(
    map: MapData, state: GameState, power: str
) -> tuple[dict[str, list[str]], list[str], dict[str, Any]]:
    orders_by_unit: dict[str, list[str]] = {}
    flat: list[str] = []

    centers = len(state.centers_of(power))
    my_units = list(state.units_of(power))
    delta = centers - len(my_units)

    if delta > 0:
        for b in legal_builds(power, state, map):
            key = f"{b.kind.value} {b.location}"
            s = format_order(b, {b.location.province: b.kind.value})
            orders_by_unit.setdefault(key, []).append(s)
            flat.append(s)
        flat.append("WAIVE")
        adjustment = {"delta": delta, "action": "build", "slots": delta}
    elif delta < 0:
        for u in sorted(my_units, key=_unit_key):
            key = f"{u.kind.value} {u.location}"
            s = format_order(Disband(power, unit=u.location), {u.province: u.kind.value})
            orders_by_unit[key] = [s]
            flat.append(s)
        adjustment = {"delta": delta, "action": "disband", "slots": -delta}
    else:
        adjustment = {"delta": 0, "action": "none", "slots": 0}

    return orders_by_unit, flat, adjustment
