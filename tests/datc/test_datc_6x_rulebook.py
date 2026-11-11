"""Rulebook cases the DATC does not cover (named ``6x`` so that
``test_order_independence.py``, which collects ``test_datc_6*``, shuffles them too).

**Rulebook IX.7** (``docs/specs/diplomacy_rules.md`` Examples 5 and 6): a unit
dislodged by the unit coming from the space it was ordered to has no effect on
that space, so a third unit ordered there may move in. The DATC reaches this rule
only through a land head-to-head (6.E.1 and its neighbours); these cases reach it
with a convoy on one side or the other (issue #404, found by differential fuzzing
against the pre-rewrite engine, which agrees with every outcome asserted here).
"""

from __future__ import annotations

import itertools

import pytest

from engine.adjudicator.movement import adjudicate_movement
from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def _convoyed_army_dislodged_from_its_destination() -> Harness:
    h = Harness()
    h.units("FRANCE", "A SPA", "F LYO")
    h.units("GERMANY", "F MAR", "F WES", "A BUR")
    h.orders("FRANCE", "A SPA - MAR VIA", "F LYO C A SPA - MAR")
    h.orders("GERMANY", "F MAR - SPA/SC", "F WES S F MAR - SPA/SC", "A BUR - MAR")
    return h


def test_convoyed_army_dislodged_from_its_destination_stands_nobody_off() -> None:
    h = _convoyed_army_dislodged_from_its_destination()
    h.adjudicate()
    h.assert_success("F MAR")
    h.assert_dislodged("A SPA")
    h.assert_result("A SPA", ResultCode.BOUNCE)
    h.assert_success("A BUR")
    assert h.unit_powers_at("MAR") == "GERMANY"
    assert h.new_state.contested == frozenset()


def test_same_position_without_the_convoy_already_lets_the_third_unit_in() -> None:
    h = Harness()
    h.units("FRANCE", "A SPA")
    h.units("GERMANY", "A MAR", "A GAS", "A BUR")
    h.orders("FRANCE", "A SPA - MAR")
    h.orders("GERMANY", "A MAR - SPA", "A GAS S A MAR - SPA", "A BUR - MAR")
    h.adjudicate()
    h.assert_success("A BUR")
    assert h.new_state.contested == frozenset()


def test_army_dislodged_by_a_convoyed_army_from_its_destination_stands_nobody_off() -> None:
    """The mirror case: the attacker is the convoyed one, the dislodged unit walked."""
    h = Harness()
    h.units("FRANCE", "A SPA", "F LYO", "A PIE")
    h.units("GERMANY", "A MAR")
    h.units("ENGLAND", "A GAS")
    h.orders("FRANCE", "A SPA - MAR VIA", "F LYO C A SPA - MAR", "A PIE S A SPA - MAR")
    h.orders("GERMANY", "A MAR - SPA")
    h.orders("ENGLAND", "A GAS - SPA")
    h.adjudicate()
    h.assert_success("A SPA")
    h.assert_dislodged("A MAR")
    h.assert_success("A GAS")
    assert h.unit_powers_at("SPA") == "ENGLAND"
    assert h.new_state.contested == frozenset()


def test_convoyed_case_gives_one_result_under_every_submission_order() -> None:
    """``test_order_independence.py`` tries ten of the 5040 orderings of these
    seven orders; the convoy makes the dependency circular, so try all of them."""
    h = _convoyed_army_dislodged_from_its_destination()
    state = h.state()
    outcomes = set()
    for ordering in itertools.permutations(h._orders):
        resolution, new_state = adjudicate_movement(h.map, state, list(ordering))
        results = frozenset((str(r.order), r.result, r.dislodged) for r in resolution.results)
        outcomes.add((results, new_state.units, new_state.contested))
    assert len(outcomes) == 1
    (_, units, contested), = outcomes
    assert {(u.province, u.power) for u in units} == {
        ("LYO", "FRANCE"), ("SPA", "GERMANY"), ("WES", "GERMANY"), ("MAR", "GERMANY")
    }
    assert contested == frozenset()
