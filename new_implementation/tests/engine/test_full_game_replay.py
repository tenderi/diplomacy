"""A whole game, replayed phase by phase against a recorded fixture.

The DATC suite checks positions the size of a chess puzzle. What it cannot check
is a resolver regression that only shows up after the board has drifted somewhere
no hand-written case goes — a subtly wrong retreat option in 1906, a build the
civil-disorder rule picks differently once a power is down to two centres. The
legacy tree caught that class of bug by replaying three recorded real games
through the server and diffing every phase; nothing here did, until Track K.

This is that test, without the AGPL fixtures: a **deterministic self-play game**
(seeded RNG + `simple_ai`) is recorded once into `fixtures/full_game_replay.json`
and re-derived on every run. Every phase's units, supply-centre ownership and
per-order result codes must match exactly.

**When this fails**, the diff tells you the first phase that diverged and what
changed in it. That is the whole point: a legitimate engine change (a fixed
paradox case, a corrected retreat rule) will *also* fail here, and the right
response is to read the reported phase, satisfy yourself the new behaviour is
correct, and regenerate:

    PYTHONPATH=src python -m tests.engine.test_full_game_replay

Regenerating without reading the diff throws away the only thing this test does.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest

from engine.game import Game
from engine.simple_ai import generate_orders
from engine.types import GameStatus

FIXTURE = Path(__file__).parent / "fixtures" / "full_game_replay.json"

# Any seed works; this one is recorded in the fixture so a regeneration with a
# different seed is visible in review rather than silently producing a new game.
SEED = 20260909
# Ten game-years is enough to reach adjustment phases, eliminations and retreats
# many times over while keeping the fixture readable.
MAX_PHASES = 40

POWERS = ("AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY")


def _phase_record(game: Game, resolution: Any) -> dict[str, Any]:
    """One phase's observable outcome, in a stable, diffable shape."""
    return {
        "phase": game.state.phase_name,
        "units": sorted(f"{u.power} {u.kind.value} {u.location}" for u in game.state.units),
        "ownership": dict(sorted(game.state.ownership.items())),
        "results": sorted(
            f"{r.order.power} {type(r.order).__name__} -> {r.result.name}"
            for r in resolution.results
        ),
    }


def play_recorded_game(seed: int = SEED, max_phases: int = MAX_PHASES) -> dict[str, Any]:
    """Play a deterministic self-play game and record every phase.

    Determinism rests on three things, all deliberate: one RNG seeded once,
    powers visited in a fixed order, and an adjudicator that is a pure function
    of (map, state, orders). Change any of them and the fixture must be
    regenerated.
    """
    rng = random.Random(seed)
    game = Game.new_standard()
    phases: list[dict[str, Any]] = []

    for _ in range(max_phases):
        if game.state.status is GameStatus.COMPLETED:
            break
        orders = []
        for power in POWERS:
            orders.extend(generate_orders(game.map, game.state, power, rng))
        before = game
        resolution, game = before.adjudicate(orders)
        phases.append(_phase_record(before, resolution))

    return {
        "seed": seed,
        "max_phases": max_phases,
        "final_phase": game.state.phase_name,
        "final_status": game.state.status.value,
        "phases": phases,
    }


def _load_fixture() -> dict[str, Any]:
    if not FIXTURE.exists():  # pragma: no cover - only before the first generation
        pytest.fail(
            f"{FIXTURE} is missing. Generate it with: "
            "PYTHONPATH=src python -m tests.engine.test_full_game_replay"
        )
    return json.loads(FIXTURE.read_text())


@pytest.mark.integration
def test_a_whole_game_replays_exactly_as_recorded() -> None:
    expected = _load_fixture()
    actual = play_recorded_game(expected["seed"], expected["max_phases"])

    assert len(actual["phases"]) == len(expected["phases"]), (
        f"the game now runs {len(actual['phases'])} phases, recorded {len(expected['phases'])}"
    )

    for got, want in zip(actual["phases"], expected["phases"]):
        assert got["phase"] == want["phase"], (
            f"phase sequence diverged: got {got['phase']}, expected {want['phase']}"
        )
        # Compared field by field so a failure names the phase *and* what in it
        # changed, rather than dumping two whole games side by side.
        for field in ("units", "ownership", "results"):
            assert got[field] == want[field], (
                f"{want['phase']}: {field} diverged from the recorded game.\n"
                f"  only now:      {sorted(set(map(str, got[field])) - set(map(str, want[field])))}\n"
                f"  only recorded: {sorted(set(map(str, want[field])) - set(map(str, got[field])))}"
            )

    assert actual["final_phase"] == expected["final_phase"]
    assert actual["final_status"] == expected["final_status"]


@pytest.mark.unit
def test_the_recorded_game_is_actually_worth_replaying() -> None:
    """Guard the fixture itself: a game that stalls in Spring 1901 proves nothing.

    If a future change makes `simple_ai` passive, or the phase machine stops
    inserting retreat/adjustment phases, the replay test above would still pass
    while checking almost nothing. This asserts the recorded game has the
    variety that makes it a useful regression: several years, all three phase
    types, and centres actually changing hands.
    """
    fixture = _load_fixture()
    phases = fixture["phases"]
    assert len(phases) >= 20, "the recorded game is too short to be a useful regression"

    kinds = {p["phase"][-1] for p in phases}
    assert {"M", "A"} <= kinds, f"the recorded game never reached an adjustment phase: {kinds}"
    assert "R" in kinds, f"the recorded game never had a retreat phase: {kinds}"

    years = {p["phase"][1:5] for p in phases}
    assert len(years) >= 5, f"the recorded game spans too few years: {sorted(years)}"

    first, last = phases[0]["ownership"], phases[-1]["ownership"]
    assert first != last, "no supply centre ever changed hands"


if __name__ == "__main__":  # pragma: no cover - fixture regeneration
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(play_recorded_game(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {FIXTURE} ({FIXTURE.stat().st_size} bytes)")
