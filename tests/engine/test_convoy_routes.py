"""Possible convoy routes: a convoy order no route can use is illegal (VOID).

A possible route is a chain of fleets in sea provinces -- any power, any order --
from a fleet touching the army's province to one touching its destination. A
Convoy order whose fleet is on no such route can never be valid, so it is VOID,
stays out of the resolver and shows no convoy intent (DATC 4.E.1, 6.G.7).
An army move is legal when such a route exists, ordered or not (6.D.8), and a
fleet's support of a convoyed move is VOID when every route needs that fleet
(6.D.31).
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
    assert r._possible_route("LON", "SPA", without="NTH")  # ENG - MAO
    assert not r._possible_route("LON", "SPA", without="ENG")  # NTH alone reaches no MAO
    assert not r._possible_route("LON", "SPA", without="MAO")


def test_a_move_with_a_possible_route_is_legal_though_no_fleet_convoys_it() -> None:
    """A YOR - NWY with F NTH holding: the board allows the convoy, so the move
    is real and fails as NO_CONVOY. With no fleet at sea it is illegal (VOID)."""
    possible = Harness()
    possible.units("ENGLAND", "A YOR", "F NTH")
    possible.orders("ENGLAND", "A YOR - NWY", "F NTH H")
    possible.adjudicate()
    possible.assert_result("A YOR", ResultCode.NO_CONVOY)

    impossible = Harness()
    impossible.units("ENGLAND", "A YOR")
    impossible.orders("ENGLAND", "A YOR - NWY")
    impossible.adjudicate()
    impossible.assert_result("A YOR", ResultCode.VOID)


def test_a_fleet_supporting_a_convoyed_move_is_void_only_when_every_route_needs_it() -> None:
    """F NTH S A EDI - NWY: with F NWG also at sea the move has a route without
    NTH, so the support stands (OK); with NTH the only possible carrier, it is
    VOID (6.D.31's rule)."""
    other_route = Harness()
    other_route.units("ENGLAND", "A EDI", "F NTH", "F NWG")
    other_route.orders("ENGLAND", "A EDI - NWY", "F NTH S A EDI - NWY", "F NWG H")
    other_route.adjudicate()
    other_route.assert_result("F NTH", ResultCode.OK)
    other_route.assert_result("A EDI", ResultCode.NO_CONVOY)

    only_route = Harness()
    only_route.units("ENGLAND", "A EDI", "F NTH")
    only_route.orders("ENGLAND", "A EDI - NWY", "F NTH S A EDI - NWY")
    only_route.adjudicate()
    only_route.assert_result("F NTH", ResultCode.VOID)
    only_route.assert_result("A EDI", ResultCode.NO_CONVOY)


def test_a_fleet_a_route_can_reach_only_by_doubling_back_is_void() -> None:
    """SKA touches neither Holland nor Belgium, and links only to NTH: the walk
    NTH - SKA - NTH visits NTH twice, which is no route. SKA's convoy is VOID;
    NTH's own convoy carries the army round the swap, so both units move."""
    h = Harness()
    h.units("ENGLAND", "A HOL", "F NTH", "F SKA")
    h.units("FRANCE", "F BEL")
    h.orders("ENGLAND", "A HOL - BEL", "F NTH C A HOL - BEL", "F SKA C A HOL - BEL")
    h.orders("FRANCE", "F BEL - HOL")
    h.adjudicate()
    h.assert_result("F SKA", ResultCode.VOID)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("A HOL", ResultCode.OK)
    h.assert_result("F BEL", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"
    assert h.unit_powers_at("HOL") == "FRANCE"
    assert h.unit_powers_at("SKA") == "ENGLAND"


def test_possible_route_through_a_fleet_needs_a_simple_path() -> None:
    """``through`` holds only on a route that visits no fleet twice. Every fleet
    of the chain IRI - ENG - NTH is on one, the middle one included; a spur off
    the chain is not, though both ends reach it; a fleet on a loop of the chain
    is."""
    h = Harness()
    h.units("ENGLAND", "F IRI", "F ENG", "F NTH", "F NWG")
    h.units("FRANCE", "F MAO")
    r = _resolver(h)
    # LVP - IRI - ENG - NTH - HOL: IRI first, ENG in the middle, NTH last.
    assert r._possible_route("LVP", "HOL", through="IRI")
    assert r._possible_route("LVP", "HOL", through="ENG")
    assert r._possible_route("LVP", "HOL", through="NTH")
    # NWG links only to NTH and touches neither end: NTH - NWG - NTH is no route.
    assert not r._possible_route("LVP", "HOL", through="NWG")
    # MAO links to IRI and ENG, so IRI - MAO - ENG - NTH is a route...
    assert r._possible_route("LVP", "HOL", through="MAO")
    # ... but not without ENG: MAO's only way on is back through IRI.
    assert r._possible_route("LVP", "HOL", without="NWG")
    assert not r._possible_route("LVP", "HOL", through="MAO", without="ENG")
    # NWG touches EDI, so there it ends a route: LVP - IRI - ENG - NTH - NWG - EDI.
    assert r._possible_route("LVP", "EDI", through="NWG")
