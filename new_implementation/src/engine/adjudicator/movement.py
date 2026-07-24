"""Movement-phase adjudicator — a Kruijswijk fixed-point resolver.

This is the heart of the engine. It computes, for a set of movement-phase orders,
which moves succeed, which supports are cut, which convoys work, and which units
are dislodged — *order-independently* and correctly for the hard interdependent
cases (beleaguered garrison, head-to-head, circular movement, convoy paradoxes).

## The algorithm (Kruijswijk, "The Math of Adjudication")

Three predicates are resolved recursively:

- ``move_succeeds(m)``   — does move ``m`` advance its unit?
- ``support_given(s)``   — is support ``s`` effective (valid and not cut)?
- ``convoy_survives(c)`` — does convoying fleet ``c`` avoid dislodgement?

Each is memoized with a three-valued state (UNRESOLVED / GUESSING / RESOLVED).
When resolving a predicate re-enters an order already in GUESSING state, a
dependency cycle exists. The resolver then tries both truth values for the head
of the cycle; if the outcome is guess-independent it is taken directly, otherwise
the **backup rule** breaks the cycle:

- a cycle of only moves (no convoy involved) is *circular movement* → every move
  in it succeeds;
- a cycle that touches a convoy is a *convoy paradox* → **Szykman rule**: the
  convoyed move(s) in the cycle fail (treated as having no convoy).

## Strength model

- **hold strength** of a province: 0 if empty or successfully vacated; else
  ``1 + valid uncut supports-to-hold`` (a unit that ordered a move but failed
  holds at strength 1, with no hold supports).
- **attack strength** of a move: 0 if its convoy path fails or it would dislodge
  a friendly unit that stays; else ``1 + supports`` (supports from the defender's
  own power don't count toward dislodging that defender).
- **defend strength** (head-to-head) / **prevent strength** (standoff):
  ``1 + supports`` with the usual exclusions.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from engine.map_loader import MapData
from engine.types import (
    Convoy,
    GameState,
    Hold,
    Location,
    Move,
    Order,
    OrderResult,
    ProvinceType,
    Resolution,
    ResultCode,
    SupportHold,
    SupportMove,
    Unit,
    UnitKind,
)


class _S(Enum):
    UNRESOLVED = auto()
    GUESSING = auto()
    RESOLVED = auto()


@dataclass
class _Item:
    """One resolvable order (move / support / convoy) with its resolver state."""

    order: Order
    unit: Unit
    state: _S = _S.UNRESOLVED
    value: bool = False  # current guess / resolved truth


def adjudicate_movement(
    map: MapData, state: GameState, orders: list[Order]
) -> tuple[Resolution, GameState]:
    """Adjudicate one movement phase.

    Returns the per-order ``Resolution`` and the resulting ``GameState`` (units
    advanced, dislodged units recorded in ``dislodged``, standoff provinces in
    ``contested``).
    """
    return _Resolver(map, state, orders).run()


class _Resolver:
    def __init__(self, map: MapData, state: GameState, orders: list[Order]):
        self.map = map
        self.state = state

        # Map each unit's province to its order; fill implicit holds.
        self.order_by_prov: dict[str, Order] = {}
        self.unit_by_prov: dict[str, Unit] = {u.province: u for u in state.units}

        for o in orders:
            loc = _order_unit_loc(o)
            if loc is None:
                continue
            if loc.province in self.unit_by_prov:
                self.order_by_prov[loc.province] = o

        for prov, unit in self.unit_by_prov.items():
            if prov not in self.order_by_prov:
                self.order_by_prov[prov] = Hold(unit.power, unit.location)

        # Illegal orders (unreachable destination, invalid support/convoy) are
        # void: the unit holds, and the result is reported as VOID.
        self.void: set[str] = set()

        # Build resolvable items keyed by province. A Move/Support/Convoy that is
        # not legal is treated as a hold (kept out of `items`) and marked void.
        self.items: dict[str, _Item] = {}
        for prov, o in self.order_by_prov.items():
            unit = self.unit_by_prov[prov]
            if isinstance(o, Move):
                if self._legal_move(o, unit):
                    self.items[prov] = _Item(o, unit)
                else:
                    self.void.add(prov)
            elif isinstance(o, (SupportHold, SupportMove, Convoy)):
                self.items[prov] = _Item(o, unit)

        self._deps: list[str] = []

    # ------------------------------------------------------------------
    # Kruijswijk resolve wrapper
    # ------------------------------------------------------------------

    def _resolve(self, prov: str) -> bool:
        item = self.items[prov]
        if item.state is _S.RESOLVED:
            return item.value
        if item.state is _S.GUESSING:
            if prov not in self._deps:
                self._deps.append(prov)
            return item.value

        old_len = len(self._deps)
        item.value = False
        item.state = _S.GUESSING
        first = self._adjudicate(prov)

        if len(self._deps) == old_len:
            # No cycle touched this order: result is definitive.
            if item.state is not _S.RESOLVED:
                item.value = first
                item.state = _S.RESOLVED
            return item.value

        if self._deps[old_len] != prov:
            # In a cycle but not its head: propagate the guess upward.
            self._deps.append(prov)
            item.value = first
            return first

        # This order is the head of a dependency cycle. Reset the tail to
        # UNRESOLVED so that flipping the head's guess propagates all the way
        # around the loop on the second pass.
        cycle: list[str] = []
        while len(self._deps) > old_len:
            p = self._deps.pop()
            cycle.append(p)
            if p != prov:
                self.items[p].state = _S.UNRESOLVED

        item.state = _S.GUESSING
        item.value = True
        second = self._adjudicate(prov)
        del self._deps[old_len:]  # drop deps discovered on the second pass

        if first == second:
            # Guess-independent: reset the tail and take the (stable) value.
            for p in cycle:
                if p != prov:
                    self.items[p].state = _S.UNRESOLVED
            item.value = first
            item.state = _S.RESOLVED
            return item.value

        # Genuine paradox / circular cycle: apply the backup rule.
        self._backup_rule(cycle)
        return item.value

    def _backup_rule(self, cycle: list[str]) -> None:
        """Break a dependency cycle.

        A cycle is a *convoy paradox* only when a convoy's outcome is entangled
        with a support cut — i.e. the cycle contains both a convoyed move (or a
        Convoy order) AND a support. Then Szykman applies: the convoyed move(s)
        fail. A cycle of moves alone — including armies swapping/rotating via
        convoy with no contested support — is ordinary circular movement: every
        move succeeds.
        """
        has_convoy = any(
            isinstance(self.items[p].order, Convoy)
            or (isinstance(self.items[p].order, Move) and self._uses_convoy(self.items[p].order))
            for p in cycle
        )
        has_support = any(
            isinstance(self.items[p].order, (SupportHold, SupportMove)) for p in cycle
        )
        is_paradox = has_convoy and has_support

        for prov in cycle:
            item = self.items[prov]
            o = item.order
            if is_paradox:
                # Szykman: convoyed moves in the cycle fail; other orders in the
                # cycle resolve as though those convoys never happened.
                if isinstance(o, Move) and self._uses_convoy(o):
                    item.value = False
                item.state = _S.RESOLVED
            else:
                # Circular movement: every move in the cycle succeeds.
                item.value = isinstance(o, Move)
                item.state = _S.RESOLVED

        # Re-resolve any non-move members (supports/convoys) now that the moves
        # in the cycle are fixed, so their values reflect the resolved cycle.
        for prov in cycle:
            item = self.items[prov]
            if not isinstance(item.order, Move):
                item.state = _S.UNRESOLVED
        for prov in cycle:
            item = self.items[prov]
            if item.state is _S.UNRESOLVED:
                self._deps.clear()
                item.value = self._adjudicate(prov)
                item.state = _S.RESOLVED

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _adjudicate(self, prov: str) -> bool:
        o = self.items[prov].order
        if isinstance(o, Move):
            return self._move_succeeds(o)
        if isinstance(o, (SupportHold, SupportMove)):
            return self._support_given(o)
        if isinstance(o, Convoy):
            return self._convoy_survives(o)
        return False

    # ------------------------------------------------------------------
    # Move resolution
    # ------------------------------------------------------------------

    def _move_succeeds(self, m: Move) -> bool:
        if self._uses_convoy(m) and not self._convoy_path_works(m):
            return False

        dst = m.dest.province
        src = m.unit.province
        attack = self._attack_strength(m)
        if attack <= 0:
            return False

        # Standoff: any other move into dst with prevent strength >= our attack
        # bounces us.
        for other_prov, item in self.items.items():
            if other_prov == src:
                continue
            o = item.order
            if isinstance(o, Move) and o.dest.province == dst:
                if self._prevent_strength(o) >= attack:
                    return False

        occ = self.unit_by_prov.get(dst)
        if occ is None:
            return True

        hh = self._head_to_head_opponent(m)
        if hh is not None:
            # Head-to-head: beat the opposing move's defend strength.
            if self._defend_strength(hh) >= attack:
                return False
            return True

        # Occupant not in a head-to-head with us: it either vacates or stays.
        if self._vacates(dst):
            return True
        # Occupant stays: must exceed its hold strength and not be our own unit.
        if occ.power == m.power:
            return False
        if self._hold_strength(dst) >= attack:
            return False
        return True

    def _vacates(self, prov: str) -> bool:
        """True if the unit in ``prov`` successfully moves elsewhere (not h2h)."""
        item = self.items.get(prov)
        if item is None or not isinstance(item.order, Move):
            return False
        mv = item.order
        # A unit in a head-to-head battle does not "vacate" for a third party.
        if self._head_to_head_opponent(mv) is not None:
            return self._resolve(prov)
        return self._resolve(prov)

    # ------------------------------------------------------------------
    # Strengths
    # ------------------------------------------------------------------

    def _supports_for_move(self, m: Move) -> list[SupportMove]:
        out: list[SupportMove] = []
        for item in self.items.values():
            o = item.order
            if (
                isinstance(o, SupportMove)
                and o.origin.province == m.unit.province
                and o.dest.province == m.dest.province
                and self._coast_compatible(o.dest.coast, m.dest.coast)
            ):
                out.append(o)
        return out

    @staticmethod
    def _coast_compatible(support_coast: Optional[str], move_coast: Optional[str]) -> bool:
        """A support whose named dest coast contradicts the move's is void."""
        if support_coast is None or move_coast is None:
            return True
        return support_coast == move_coast

    def _support_has_target(self, s: Order) -> bool:
        """True if the support refers to a real order/unit (else it is void)."""
        if isinstance(s, SupportMove):
            for item in self.items.values():
                m = item.order
                if (
                    isinstance(m, Move)
                    and m.unit.province == s.origin.province
                    and m.dest.province == s.dest.province
                    and self._coast_compatible(s.dest.coast, m.dest.coast)
                ):
                    return True
            return False
        if isinstance(s, SupportHold):
            occ = self.unit_by_prov.get(s.target.province)
            return occ is not None
        return True

    def _supports_for_hold(self, prov: str) -> list[SupportHold]:
        out: list[SupportHold] = []
        for item in self.items.values():
            o = item.order
            if isinstance(o, SupportHold) and o.target.province == prov:
                out.append(o)
        return out

    def _attack_strength(self, m: Move) -> int:
        if self._uses_convoy(m) and not self._convoy_path_works(m):
            return 0
        dst = m.dest.province
        occ = self.unit_by_prov.get(dst)
        # Does an occupant remain in dst that this move must dislodge?
        remains = occ is not None and not self._vacates(dst)
        if remains and occ is not None and occ.power == m.power:
            return 0
        strength = 1
        for s in self._supports_for_move(m):
            if remains and occ is not None and s.power == occ.power:
                continue  # can't support dislodging a unit of its own power
            if self._resolve(s.unit.province):
                strength += 1
        return strength

    def _hold_strength(self, prov: str) -> int:
        occ = self.unit_by_prov.get(prov)
        if occ is None:
            return 0
        item = self.items.get(prov)
        if item is not None and isinstance(item.order, Move):
            # Ordered to move: strength 0 if it left, else 1 (no hold supports).
            return 0 if self._resolve(prov) else 1
        strength = 1
        for s in self._supports_for_hold(prov):
            if self._resolve(s.unit.province):
                strength += 1
        return strength

    def _defend_strength(self, m: Move) -> int:
        strength = 1
        for s in self._supports_for_move(m):
            if self._resolve(s.unit.province):
                strength += 1
        return strength

    def _prevent_strength(self, m: Move) -> int:
        if self._uses_convoy(m) and not self._convoy_path_works(m):
            return 0
        # A move that loses its head-to-head cannot prevent others.
        hh = self._head_to_head_opponent(m)
        if hh is not None and self._resolve(hh.unit.province):
            # opponent moved into our source — we are dislodged and prevent nothing
            if self._resolve(m.unit.province) is False:
                return 0
        strength = 1
        for s in self._supports_for_move(m):
            if self._resolve(s.unit.province):
                strength += 1
        return strength

    # ------------------------------------------------------------------
    # Support resolution
    # ------------------------------------------------------------------

    def _support_given(self, s: Order) -> bool:
        assert isinstance(s, (SupportHold, SupportMove))
        supp_prov = s.unit.province
        if not self._support_valid(s):
            return False

        exempt = s.dest.province if isinstance(s, SupportMove) else None
        supported_unit_prov = (
            s.origin.province if isinstance(s, SupportMove) else s.target.province
        )

        for prov, item in self.items.items():
            o = item.order
            if not isinstance(o, Move):
                continue
            if o.dest.province != supp_prov:
                continue
            if prov == supported_unit_prov:
                continue  # the supported unit doesn't cut its own support
            if self._uses_convoy(o) and not self._convoy_path_works(o):
                continue  # a disrupted convoy attack doesn't cut
            if prov == exempt:
                # Attack from the province supported against cuts only by dislodging.
                if self._resolve(prov):
                    return False
                continue
            return False  # cut
        return True

    def _support_valid(self, s: Order) -> bool:
        assert isinstance(s, (SupportHold, SupportMove))
        supporter = self.unit_by_prov.get(s.unit.province)
        if supporter is None:
            return False
        target_prov = (
            s.dest.province if isinstance(s, SupportMove) else s.target.province
        )
        # The supporter must be able to move into the supported province.
        if supporter.kind is UnitKind.ARMY:
            return target_prov in self.map.army_moves(s.unit.province)
        # Fleet: some fleet node of the supporter must be adjacent to target_prov.
        for floc in self.map.fleet_locations(s.unit.province):
            if floc != s.unit and floc.province != s.unit.province:
                continue
            for dest in self.map.fleet_moves(s.unit):
                if dest.province == target_prov:
                    return True
        for dest in self.map.fleet_moves(s.unit):
            if dest.province == target_prov:
                return True
        return False

    # ------------------------------------------------------------------
    # Convoys
    # ------------------------------------------------------------------

    def _convoy_survives(self, c: Convoy) -> bool:
        return not self._is_dislodged(c.unit.province)

    def _convoy_path_intact(self, c: Convoy) -> bool:
        """Does a working convoy path still exist for the army this fleet serves?

        True even if the army merely bounced, as long as the fleet chain is whole;
        False when the chain is broken by a dislodged sibling fleet.
        """
        for item in self.items.values():
            m = item.order
            if (
                isinstance(m, Move)
                and m.unit.province == c.origin.province
                and m.dest.province == c.dest.province
            ):
                return self._convoy_path_works(m)
        return False

    def _legal_move(self, m: Move, unit: Unit) -> bool:
        """Is ``m`` a legal move for ``unit`` (reachable destination)?"""
        dst = m.dest.province
        if dst == m.unit.province:
            return False
        if unit.kind is UnitKind.FLEET:
            if self.map.province_type(dst) is ProvinceType.LAND:
                return False
            reachable = {
                d.coast for d in self.map.fleet_moves(unit.location) if d.province == dst
            }
            if not reachable:
                return False
            if m.dest.coast is not None:
                return m.dest.coast in reachable
            # No coast named: legal only if unambiguous.
            return reachable == {None} or len(reachable) == 1
        # Army:
        if self.map.province_type(dst) is ProvinceType.WATER:
            return False
        if self._uses_convoy(m):
            # Convoyed army move: endpoints must both be coastal land.
            return (
                self.map.province_type(dst) is ProvinceType.COAST
                and self.map.province_type(m.unit.province) is ProvinceType.COAST
            )
        return dst in self.map.army_moves(m.unit.province)

    def _uses_convoy(self, m: Move) -> bool:
        u = self.unit_by_prov.get(m.unit.province)
        if u is None or u.kind is UnitKind.FLEET:
            return False
        if m.via_convoy:
            return True
        return m.dest.province not in self.map.army_moves(m.unit.province)

    def _convoy_path_works(self, m: Move) -> bool:
        """BFS from src to dst over surviving convoying fleets for this move."""
        src, dst = m.unit.province, m.dest.province
        fleets: dict[str, Location] = {}
        for item in self.items.values():
            o = item.order
            if (
                isinstance(o, Convoy)
                and o.origin.province == src
                and o.dest.province == dst
                and self.map.province_type(o.unit.province) is ProvinceType.WATER
            ):
                if not self._is_dislodged(o.unit.province):
                    fleets[o.unit.province] = o.unit
        if not fleets:
            return False

        # Convoying fleets adjacent to the source coast start the BFS.
        seen: set[str] = set()
        queue: deque[str] = deque()
        for fp, floc in fleets.items():
            if self._fleet_touches(floc, src):
                queue.append(fp)
                seen.add(fp)
        while queue:
            here = queue.popleft()
            hloc = fleets[here]
            if self._fleet_touches(hloc, dst):
                return True
            for nxt_p, nxt_loc in fleets.items():
                if nxt_p in seen:
                    continue
                if self.map.is_adjacent(hloc, nxt_loc, UnitKind.FLEET):
                    seen.add(nxt_p)
                    queue.append(nxt_p)
        return False

    def _fleet_touches(self, floc: Location, province: str) -> bool:
        """True if a fleet at ``floc`` is adjacent to ``province`` (any coast)."""
        return any(d.province == province for d in self.map.fleet_moves(floc))

    # ------------------------------------------------------------------
    # Dislodgement
    # ------------------------------------------------------------------

    def _is_dislodged(self, prov: str) -> bool:
        """True if some move into ``prov`` succeeds and the unit did not vacate."""
        occ = self.unit_by_prov.get(prov)
        if occ is None:
            return False
        if self._vacates(prov):
            return False
        for other_prov, item in self.items.items():
            o = item.order
            if not isinstance(o, Move) or o.dest.province != prov:
                continue
            if self._resolve(other_prov):
                return True
        return False

    def _head_to_head_opponent(self, m: Move) -> Optional[Move]:
        """The opposing move if ``m`` is in a direct (non-convoyed) head-to-head."""
        if self._uses_convoy(m):
            return None
        dst_item = self.items.get(m.dest.province)
        if dst_item is None or not isinstance(dst_item.order, Move):
            return None
        opp = dst_item.order
        if opp.dest.province != m.unit.province:
            return None
        if self._uses_convoy(opp):
            return None
        return opp

    # ------------------------------------------------------------------
    # Assemble results
    # ------------------------------------------------------------------

    def run(self) -> tuple[Resolution, GameState]:
        # Resolve every resolvable order.
        for prov in list(self.items):
            self._deps.clear()
            self._resolve(prov)

        results: list[OrderResult] = []
        surviving: dict[str, Unit] = {}
        dislodged_units: list[Unit] = []
        contested: set[str] = set()

        # Which provinces are being successfully moved into.
        incoming: dict[str, list[str]] = {}
        for prov, item in self.items.items():
            o = item.order
            if isinstance(o, Move):
                target = o.dest.province
                if item.value:
                    incoming.setdefault(target, []).append(prov)

        # Standoff provinces: two or more moves aimed at an empty province all failed.
        move_targets: dict[str, list[str]] = {}
        for prov, item in self.items.items():
            if isinstance(item.order, Move):
                move_targets.setdefault(item.order.dest.province, []).append(prov)
        for target, srcs in move_targets.items():
            if len(srcs) >= 2 and not any(self.items[s].value for s in srcs):
                if self.unit_by_prov.get(target) is None:
                    contested.add(target)

        # Place surviving units.
        for prov, unit in self.unit_by_prov.items():
            item = self.items.get(prov)
            if item is not None and isinstance(item.order, Move) and item.value:
                new_loc = _move_dest_location(item.order, unit, self.map)
                surviving[item.order.dest.province] = Unit(unit.kind, unit.power, new_loc)
            else:
                if self._is_dislodged(prov):
                    dislodged_units.append(unit)
                else:
                    surviving[prov] = unit

        # Build per-order results.
        for prov, item in self.items.items():
            o = item.order
            unit = item.unit
            dislodged = self._is_dislodged(prov) and not (
                isinstance(o, Move) and item.value
            )
            if isinstance(o, Move):
                if item.value:
                    code = ResultCode.OK
                elif self._uses_convoy(o) and not self._convoy_path_works(o):
                    code = ResultCode.NO_CONVOY
                else:
                    code = ResultCode.BOUNCE
            elif isinstance(o, (SupportHold, SupportMove)):
                if not self._support_valid(o) or not self._support_has_target(o):
                    code = ResultCode.VOID  # illegal support, or supports no real order
                elif item.value:
                    code = ResultCode.OK
                else:
                    code = ResultCode.CUT
            elif isinstance(o, Convoy):
                if not item.value:
                    code = ResultCode.DISLODGED
                elif self._convoy_path_intact(o):
                    code = ResultCode.OK
                else:
                    # Fleet survived but its convoy chain is broken elsewhere
                    # (a sibling fleet was dislodged): report NO_CONVOY. A merely
                    # bounced army over an intact path stays OK.
                    code = ResultCode.NO_CONVOY
            else:
                code = ResultCode.OK
            retreats = (
                self._retreat_options(unit, prov) if dislodged else ()
            )
            results.append(
                OrderResult(order=o, result=code, dislodged=dislodged, retreat_options=retreats)
            )

        # Hold orders and void (illegal) orders: the unit holds; success unless
        # dislodged. A void order is reported VOID even when it survives.
        for prov, unit in self.unit_by_prov.items():
            if prov in self.items:
                continue
            o = self.order_by_prov[prov]
            dislodged = self._is_dislodged(prov)
            retreats = self._retreat_options(unit, prov) if dislodged else ()
            if dislodged:
                code = ResultCode.DISLODGED
            elif prov in self.void:
                code = ResultCode.VOID
            else:
                code = ResultCode.OK
            results.append(
                OrderResult(order=o, result=code, dislodged=dislodged, retreat_options=retreats)
            )

        new_state = GameState(
            year=self.state.year,
            season=self.state.season,
            phase_type=self.state.phase_type,
            units=frozenset(surviving.values()),
            ownership=dict(self.state.ownership),
            dislodged=frozenset(dislodged_units),
            contested=frozenset(contested),
        )
        return Resolution(tuple(results)), new_state

    def _retreat_options(self, unit: Unit, from_prov: str) -> tuple[Location, ...]:
        """Legal retreat destinations: adjacent, empty, uncontested, not attacker origin."""
        opts: list[Location] = []
        # The attacker's origin (can't retreat back into it).
        attacker_origins = {
            p
            for p, item in self.items.items()
            if isinstance(item.order, Move)
            and item.order.dest.province == from_prov
            and item.value
        }
        if unit.kind is UnitKind.ARMY:
            dests = [Location(p) for p in self.map.army_moves(from_prov)]
        else:
            dests = list(self.map.fleet_moves(unit.location))
        for d in dests:
            if d.province in attacker_origins:
                continue
            if self.unit_by_prov.get(d.province) is not None:
                continue
            opts.append(d)
        return tuple(opts)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _order_unit_loc(o: Order) -> Optional[Location]:
    return getattr(o, "unit", None)


def _move_dest_location(m: Move, unit: Unit, map: MapData) -> Location:
    """Resolve the destination Location a moving unit ends up at (coast-correct)."""
    if unit.kind is UnitKind.ARMY:
        return Location(m.dest.province, None)
    # Fleet: keep an explicit coast, or infer the sole reachable coast when the
    # order left it unspecified (legal only when unambiguous — see _legal_move).
    if m.dest.coast is not None:
        return m.dest
    reachable = {
        d.coast for d in map.fleet_moves(unit.location) if d.province == m.dest.province
    }
    reachable.discard(None)
    if len(reachable) == 1:
        return Location(m.dest.province, next(iter(reachable)))
    return Location(m.dest.province, None)
