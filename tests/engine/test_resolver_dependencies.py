"""The resolver's dependency bookkeeping (Kruijswijk, "The Math of Adjudication").

A result computed on a guess must never be frozen as RESOLVED: the guess may
flip when the cycle's head tries its second value. Two rules keep that true,
and each is pinned here on its own:

1. every read of a GUESSING order is recorded as a dependency, even when that
   order is already on the dependency list;
2. a convoying fleet's survival is read through ``_resolve`` on its Convoy
   order, so the fleet is a dependency of the army it carries and can sit in a
   cycle like any other order.

The Szykman backup rule then works on those cycles: it disrupts the convoys of
the cycle's fleets, which the route search no longer reads.

These drive ``_Resolver`` directly: a guess is planted on one order, and the
test checks what resolving another order that reads it records.
"""

from __future__ import annotations

import pytest

from engine.adjudicator.movement import _Resolver, _S
from tests.datc.harness import Harness

pytestmark = pytest.mark.unit


def _resolver(h: Harness) -> _Resolver:
    return _Resolver(h.map, h.state(), list(h._orders))


def _supported_move() -> _Resolver:
    h = Harness()
    h.units("FRANCE", "A PAR", "A GAS")
    h.units("GERMANY", "A BUR")
    h.orders("FRANCE", "A PAR - BUR", "A GAS S A PAR - BUR")
    return _resolver(h)


def test_reading_a_guess_already_on_the_dependency_list_is_still_a_dependency() -> None:
    """GAS's support is being guessed (given) and is already listed as a
    dependency. PAR - BUR succeeds only on that guess (2 against BUR's 1), so
    it must stay GUESSING and list itself, not be frozen as RESOLVED."""
    r = _supported_move()
    r.items["GAS"].state = _S.GUESSING
    r.items["GAS"].value = True
    r._deps.append("GAS")

    assert r._resolve("PAR") is True
    assert r.items["PAR"].state is _S.GUESSING
    # The read after the planted entry lists GAS again; PAR lists itself last.
    assert r._deps[0] == "GAS"
    assert "GAS" in r._deps[1:]
    assert r._deps[-1] == "PAR"


def test_reading_a_fresh_guess_is_a_dependency() -> None:
    """The same board with GAS guessed but not yet listed: the read lists it."""
    r = _supported_move()
    r.items["GAS"].state = _S.GUESSING
    r.items["GAS"].value = True

    assert r._resolve("PAR") is True
    assert r.items["PAR"].state is _S.GUESSING
    assert set(r._deps) == {"GAS", "PAR"}
    assert r._deps[-1] == "PAR"


def test_a_move_with_no_guess_to_read_is_resolved() -> None:
    """Without a planted guess nothing is pending: the move is RESOLVED and
    the dependency list stays empty."""
    r = _supported_move()

    assert r._resolve("PAR") is True
    assert r.items["PAR"].state is _S.RESOLVED
    assert r.items["GAS"].state is _S.RESOLVED
    assert r._deps == []


def _convoy() -> _Resolver:
    h = Harness()
    h.units("ENGLAND", "A LON", "F NTH")
    h.orders("ENGLAND", "A LON - NWY", "F NTH C A LON - NWY")
    return _resolver(h)


def test_a_convoyed_move_depends_on_the_convoy_order_of_its_fleet() -> None:
    """NTH's survival is being guessed. The army's move reads that guess
    through NTH's Convoy order, so it lists NTH and is not RESOLVED."""
    r = _convoy()
    r.items["NTH"].state = _S.GUESSING
    r.items["NTH"].value = True

    assert r._resolve("LON") is True
    assert r.items["LON"].state is _S.GUESSING
    assert set(r._deps) == {"NTH", "LON"}
    assert r._deps[-1] == "LON"


def test_a_guessed_dislodged_convoy_carries_no_army() -> None:
    """With NTH guessed dislodged, the route is broken and the army fails --
    the guess, not a direct dislodgement check, decides it."""
    r = _convoy()
    r.items["NTH"].state = _S.GUESSING
    r.items["NTH"].value = False

    assert r._resolve("LON") is False
    assert r.items["LON"].state is _S.GUESSING


def test_resolving_a_convoyed_move_resolves_the_convoy_order() -> None:
    """With no guess pending, resolving the army resolves its fleet's Convoy
    order on the way (the fleet survives), and both are RESOLVED."""
    r = _convoy()

    assert r._resolve("LON") is True
    assert r.items["LON"].state is _S.RESOLVED
    assert r.items["NTH"].state is _S.RESOLVED
    assert r.items["NTH"].value is True
    assert r._deps == []


def test_a_disrupted_convoy_carries_no_army_and_is_not_read() -> None:
    """A fleet the Szykman rule disrupted is skipped by the route search: the
    army fails without its fleet's survival being read, so it joins no cycle."""
    r = _convoy()
    r._disrupted.add("NTH")

    assert r._resolve("LON") is False
    assert r.items["LON"].state is _S.RESOLVED
    assert r.items["NTH"].state is _S.UNRESOLVED
    assert r._deps == []


@pytest.mark.parametrize("start", ["LON", "WAL", "BRE", "ENG"])
def test_szykman_disrupts_the_paradox_fleet_from_any_starting_order(start: str) -> None:
    """DATC 6.F.14, resolved starting from each of its orders. Starting at the
    support, the cycle found is {ENG convoy, WAL move, LON support}: it does
    not hold the army's move (the support reads the route directly), but it
    holds the convoying fleet, and disrupting that fleet fails the army."""
    h = Harness()
    h.units("ENGLAND", "F LON", "F WAL")
    h.units("FRANCE", "A BRE", "F ENG")
    h.orders("ENGLAND", "F LON S F WAL - ENG", "F WAL - ENG")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    r = _resolver(h)

    r._resolve(start)
    for prov in ("LON", "WAL", "BRE", "ENG"):
        r._resolve(prov)

    assert r._disrupted == {"ENG"}
    assert r._deps == []
    assert {p: (i.state, i.value) for p, i in r.items.items()} == {
        "LON": (_S.RESOLVED, True),  # the support is not cut
        "WAL": (_S.RESOLVED, True),  # so WAL dislodges ENG
        "BRE": (_S.RESOLVED, False),
        "ENG": (_S.RESOLVED, False),  # the fleet does not survive
    }
