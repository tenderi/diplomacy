"""Every DATC case gives the same result whatever order its orders arrive in.

Each ``test_datc_6*`` case is run once more with ``Harness.adjudicate`` wrapped:
the wrapper adjudicates the movement orders in the given order, reversed, and in
several seeded shuffles (every permutation when there are at most five orders),
asserts that all of them give the same resolution and board, and then hands the
given-order result to the case's own assertions. So a case passes here only if
its DATC result holds under every submission order tried.

A resolver whose cycle detection depends on which order it meets first (BC5:
6.F.14 gave a different result under half of its 24 permutations) fails here
even when the order written in the case happens to give the right answer.
"""

from __future__ import annotations

import importlib
import inspect
import itertools
import json
import random
from collections.abc import Callable
from pathlib import Path

import pytest

from engine.adjudicator.movement import adjudicate_movement
from engine.serialization import resolution_to_dict, state_to_dict
from engine.types import GameState, Order, Resolution
from tests.datc.harness import Harness

pytestmark = [pytest.mark.datc]

_SHUFFLES = 8
_ALL_PERMUTATIONS_UP_TO = 5


def _cases() -> list[tuple[str, Callable[[], None]]]:
    out = []
    for path in sorted(Path(__file__).parent.glob("test_datc_6*.py")):
        module = importlib.import_module(f"tests.datc.{path.stem}")
        for name, fn in inspect.getmembers(module, inspect.isfunction):
            # Only the cases that adjudicate a movement phase (not builds).
            if (
                name.startswith("test_")
                and fn.__module__ == module.__name__
                and ".adjudicate()" in inspect.getsource(fn)
            ):
                out.append((f"{path.stem}::{name}", fn))
    return out


def _orderings(orders: list[Order]) -> list[list[Order]]:
    if len(orders) <= _ALL_PERMUTATIONS_UP_TO:
        return [list(p) for p in itertools.permutations(orders)]
    out = [list(orders), orders[::-1]]
    for seed in range(_SHUFFLES):
        shuffled = list(orders)
        random.Random(seed).shuffle(shuffled)
        out.append(shuffled)
    return out


def _signature(resolution: Resolution, new_state: GameState) -> str:
    """The resolution and the new board, independent of the orders' order."""
    results = sorted(json.dumps(r, sort_keys=True) for r in resolution_to_dict(resolution)["results"])
    board = state_to_dict(new_state)
    board["units"] = sorted(json.dumps(u, sort_keys=True) for u in board["units"])
    return json.dumps([results, board], sort_keys=True)


def _adjudicate_every_order(self: Harness) -> Resolution:
    state = self.state()
    given = list(self._orders)
    signatures = {}
    for ordering in _orderings(given):
        resolution, new_state = adjudicate_movement(self.map, state, ordering)
        signatures.setdefault(_signature(resolution, new_state), ordering)
    assert len(signatures) == 1, (
        f"{len(signatures)} different results; for example under the orderings "
        + " / ".join(" ; ".join(str(o.unit) for o in o_list) for o_list in signatures.values())
    )
    self.resolution, self.new_state = adjudicate_movement(self.map, state, given)
    return self.resolution


@pytest.mark.parametrize("name,case", _cases(), ids=[n for n, _ in _cases()])
def test_datc_case_is_order_independent(
    name: str, case: Callable[[], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def wrapped(self: Harness) -> Resolution:
        calls.append(len(self._orders))
        return _adjudicate_every_order(self)

    monkeypatch.setattr(Harness, "adjudicate", wrapped)
    case()
    assert calls, f"{name} adjudicated no movement phase"
