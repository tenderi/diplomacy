"""Possible convoy routes: a convoy order no route can use is illegal (VOID).

A possible route is a chain of fleets in sea provinces -- any power, any order --
from a fleet touching the army's province to one touching its destination. A
Convoy order whose fleet is on no such route can never be valid, so it is VOID,
stays out of the resolver and shows no convoy intent (DATC 4.E.1, 6.G.7).
"""

from __future__ import annotations

import pytest

from engine.adjudicator.movement import _Resolver
from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.unit


def test_a_coastal_fleet_convoy_is_void_and_so_is_every_fleet_it_would_link() -> None:
    """6.F.1's board: CON is a coast, so AEG and BLA are on no chain of seas
    from Greece to Sevastopol either. All three convoys are VOID, and the
    fleets stay put."""
    h = Harness()
    h.units("TURKEY", "A GRE", "F AEG", "F CON", "F BLA")
    h.orders(
        "TURKEY",
        "A GRE - SEV VIA",
        "F AEG C A GRE - SEV",
        "F CON C A GRE - SEV",
        "F BLA C A GRE - SEV",
    )
    h.adjudicate()
    h.assert_result("F CON", ResultCode.VOID)
    h.assert_result("F AEG", ResultCode.VOID)
    h.assert_result("F BLA", ResultCode.VOID)
    h.assert_not_dislodged("F CON")
    assert h.unit_powers_at("CON") == "TURKEY"
    h.assert_empty("SEV")


def test_a_fleet_on_a_coast_is_void_even_next_to_both_ends() -> None:
    """F DEN touches both KIE and SWE, but a fleet on a coast never convoys."""
    h = Harness()
    h.units("GERMANY", "A KIE", "F DEN")
    h.orders("GERMANY", "A KIE - SWE VIA", "F DEN C A KIE - SWE")
    h.adjudicate()
    h.assert_result("F DEN", ResultCode.VOID)
    assert h.unit_powers_at("KIE") == "GERMANY"


def test_a_route_may_run_through_a_foreign_fleet_that_does_not_convoy() -> None:
    """F MAO alone cannot reach Tunis, so its convoy is VOID; with an Italian
    fleet holding in the Western Med the route is possible, so the order is
    legal -- it only fails, because WES does not carry the army."""
    alone = Harness()
    alone.units("FRANCE", "A BRE", "F MAO")
    alone.orders("FRANCE", "A BRE - TUN VIA", "F MAO C A BRE - TUN")
    alone.adjudicate()
    alone.assert_result("F MAO", ResultCode.VOID)

    linked = Harness()
    linked.units("FRANCE", "A BRE", "F MAO")
    linked.units("ITALY", "F WES")
    linked.orders("FRANCE", "A BRE - TUN VIA", "F MAO C A BRE - TUN")
    linked.orders("ITALY", "F WES H")
    linked.adjudicate()
    linked.assert_result("F MAO", ResultCode.NO_CONVOY)
    linked.assert_result("A BRE", ResultCode.NO_CONVOY)


def _resolver(h: Harness) -> _Resolver:
    return _Resolver(h.map, h.state(), list(h._orders))


def test_possible_route_between_two_ends_and_through_a_fleet() -> None:
    """The helper answers both "is there a route from src to dst" and "is
    there one through this fleet", from the board alone (no orders)."""
    h = Harness()
    h.units("ENGLAND", "F ENG", "F NTH")
    h.units("FRANCE", "F MAO")
    h.units("RUSSIA", "F BOT")
    r = _resolver(h)
    assert r._possible_route("LON", "SPA")  # ENG - MAO
    assert r._possible_route("LON", "SPA", through="MAO")
    assert r._possible_route("LON", "SPA", through="NTH")  # LON - NTH - ENG - MAO - SPA
    assert r._possible_route("LON", "NWY", through="NTH")
    assert not r._possible_route("LON", "SPA", through="BOT")  # BOT links to no other fleet
    assert not r._possible_route("SWE", "NWY")  # BOT reaches nothing near Norway
    assert not r._possible_route("SWE", "NWY", through="BOT")
    assert not r._possible_route("MOS", "SPA")  # an inland end: no fleet touches it
