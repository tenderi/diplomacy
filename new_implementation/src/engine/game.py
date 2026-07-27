"""Phase machine over immutable ``GameState`` snapshots.

This is the pure orchestration layer that drives the season/phase state machine and
threads the three adjudicators together:

    S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M → …

A retreat phase is inserted only when the preceding movement dislodged a unit; a
winter adjustment phase only when some power's unit count differs from its supply-
center count. Supply-center ownership is recomputed after the **Fall** turn settles
(movement + any retreats), and a power holding ≥ ``VICTORY_CENTERS`` centers at that
point wins.

Everything is a pure function of ``(map, state, orders)``; ``Game`` is a frozen
snapshot plus its history, and :meth:`Game.adjudicate` returns the phase resolution
and the next ``Game``. No I/O, no mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from engine.adjudicator.adjustments import adjudicate_adjustments
from engine.adjudicator.movement import adjudicate_movement
from engine.adjudicator.retreats import adjudicate_retreats
from engine.map_loader import MapData, load_standard_map
from engine.types import (
    VICTORY_CENTERS,
    GameState,
    GameStatus,
    Order,
    PhaseType,
    Resolution,
    Season,
)

__all__ = ["Game"]


@dataclass(frozen=True)
class Game:
    """An immutable game: its map, the current ``state``, and past snapshots."""

    map: MapData
    state: GameState
    history: tuple[GameState, ...] = field(default_factory=tuple)

    # -- construction -----------------------------------------------------

    @classmethod
    def new_standard(cls) -> "Game":
        """A fresh standard game at its opening movement phase."""
        map = load_standard_map()
        state = GameState(
            year=map.start_year,
            season=map.start_season,
            phase_type=PhaseType.MOVEMENT,
            units=map.starting_units,
            ownership=dict(map.initial_ownership),
        )
        return cls(map=map, state=state)

    # -- driving ----------------------------------------------------------

    def adjudicate(self, orders: list[Order]) -> tuple[Resolution, "Game"]:
        """Adjudicate the current phase and advance to the next.

        Returns the phase ``Resolution`` and a new ``Game`` whose ``state`` is the
        next phase to play (or a completed game). The current state is appended to
        the returned game's ``history``.
        """
        if self.state.status is GameStatus.COMPLETED:
            return Resolution(()), self

        pt = self.state.phase_type
        if pt is PhaseType.MOVEMENT:
            resolution, post = adjudicate_movement(self.map, self.state, orders)
        elif pt is PhaseType.RETREAT:
            resolution, post = adjudicate_retreats(self.map, self.state, orders)
        else:
            resolution, post = adjudicate_adjustments(self.map, self.state, orders)

        next_state = self._transition(post)
        return resolution, Game(
            map=self.map, state=next_state, history=self.history + (self.state,)
        )

    # -- phase transitions ------------------------------------------------

    def _transition(self, post: GameState) -> GameState:
        """Compute the next phase's opening state from a settled adjudication."""
        pt = self.state.phase_type

        if pt is PhaseType.MOVEMENT:
            if post.dislodged:
                # Insert a retreat phase; keep dislodged units and standoffs.
                return replace(post, phase_type=PhaseType.RETREAT)
            return self._after_moves_settled(post)

        if pt is PhaseType.RETREAT:
            return self._after_moves_settled(post)

        # ADJUSTMENT → next year's spring movement.
        return GameState(
            year=post.year + 1,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=post.units,
            ownership=dict(post.ownership),
            status=post.status,
        )

    def _after_moves_settled(self, post: GameState) -> GameState:
        """After movement (+ any retreats) settle: go to the next movement, or —
        after Fall — update SC ownership, check victory, and enter adjustment."""
        year, season = post.year, post.season

        if season is Season.SPRING:
            return GameState(
                year=year,
                season=Season.FALL,
                phase_type=PhaseType.MOVEMENT,
                units=post.units,
                ownership=dict(post.ownership),
                status=post.status,
            )

        # Fall settled: recompute supply-center ownership, then check victory.
        ownership = self._updated_ownership(post)
        status = post.status
        if _has_winner(ownership):
            status = GameStatus.COMPLETED
            return GameState(
                year=year,
                season=Season.WINTER,
                phase_type=PhaseType.ADJUSTMENT,
                units=post.units,
                ownership=ownership,
                status=status,
            )

        if self._adjustments_needed(post.units, ownership):
            return GameState(
                year=year,
                season=Season.WINTER,
                phase_type=PhaseType.ADJUSTMENT,
                units=post.units,
                ownership=ownership,
                status=status,
            )

        # No adjustments owed: skip straight to next spring.
        return GameState(
            year=year + 1,
            season=Season.SPRING,
            phase_type=PhaseType.MOVEMENT,
            units=post.units,
            ownership=ownership,
            status=status,
        )

    # -- supply centers / powers -----------------------------------------

    def _updated_ownership(self, post: GameState) -> dict[str, str]:
        """A supply center is captured by whoever occupies it after Fall; empty
        centers keep their previous owner."""
        ownership = dict(post.ownership)
        for prov in self.map.supply_centers:
            unit = post.unit_at(prov)
            if unit is not None:
                ownership[prov] = unit.power
        return ownership

    def _adjustments_needed(self, units, ownership: dict[str, str]) -> bool:
        counts_units: dict[str, int] = {}
        for u in units:
            counts_units[u.power] = counts_units.get(u.power, 0) + 1
        counts_centers: dict[str, int] = {}
        for owner in ownership.values():
            counts_centers[owner] = counts_centers.get(owner, 0) + 1
        powers = set(self.map.home_centers) | set(counts_units) | set(counts_centers)
        return any(
            counts_centers.get(p, 0) != counts_units.get(p, 0) for p in powers
        )

    # -- queries ----------------------------------------------------------

    def eliminated_powers(self) -> frozenset[str]:
        """Powers with no units and no supply centers."""
        out = set()
        for power in self.map.home_centers:
            has_units = any(u.power == power for u in self.state.units)
            has_centers = any(o == power for o in self.state.ownership.values())
            if not has_units and not has_centers:
                out.add(power)
        return frozenset(out)

    def winner(self) -> str | None:
        """The winning power (≥ ``VICTORY_CENTERS`` centers), if any."""
        counts: dict[str, int] = {}
        for owner in self.state.ownership.values():
            counts[owner] = counts.get(owner, 0) + 1
        for power, n in counts.items():
            if n >= VICTORY_CENTERS:
                return power
        return None


def _has_winner(ownership: dict[str, str]) -> bool:
    counts: dict[str, int] = {}
    for owner in ownership.values():
        counts[owner] = counts.get(owner, 0) + 1
    return any(n >= VICTORY_CENTERS for n in counts.values())
