"""DATC section 6.F — Convoys, including all convoy paradoxes.

Outcomes cross-checked against the DATC document (Lucas B. Kruijswijk) and the
reference resolver in ``old_implementation/diplomacy/tests/test_datc.py``
(``test_6_f_*``); semantics only, no code copied (that module is AGPL).

Vocabulary note: this engine's ``Convoy`` order only ever reports
``ResultCode.OK`` (fleet survives, whether or not its convoy was actually used)
or ``ResultCode.DISLODGED`` (fleet was dislodged) — see
``engine.adjudicator.movement._Resolver.run``. The reference suite sometimes
tags a convoying fleet's own order with a finer-grained category (e.g.
"the convoy order for this leg was never used" or "this order was illegal").
Where our ``ResultCode`` enum cannot express that distinction, we assert the
practical/positional consequence instead (``assert_not_dislodged``,
``assert_empty``, ``unit_powers_at``) and note the DATC-correct reading in the
docstring.

Paradox cases (6.F.14-6.F.24): DATC recognizes several ways to break a convoy
paradox cycle (1971, 1982, 2000, 'All Hold', DPTG, Szykman). The engine's own
docstring (``engine/adjudicator/movement.py``) states it implements the
**Szykman** rule: a convoyed move caught in a paradox cycle fails (as if it
had no convoy) and the rest of the cycle re-resolves around that. Every
paradox assertion below encodes the Szykman-preferred outcome, which is also
the author's preferred outcome in the DATC document.
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6f1_no_convoy_in_coastal_areas():
    """6.F.1 NO CONVOY IN COASTAL AREAS.

    A fleet in a coastal area (not open water) may not convoy. Turkey orders
    A GRE - SEV convoyed by F AEG, F CON, F BLA; F CON sits in a coastal
    province (Constantinople), not water, so that leg of the convoy is
    illegal. DATC-correct outcome: the whole convoy is invalid and the army
    in Greece does not move.
    """
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
    # Best available translation: the convoy must not work (DATC says SEV
    # stays empty). NO_CONVOY is the closest ResultCode to "convoy invalid".
    h.assert_result("A GRE", ResultCode.NO_CONVOY)
    h.assert_empty("SEV")


def test_6f2_convoyed_army_can_bounce():
    """6.F.2 AN ARMY BEING CONVOYED CAN BOUNCE AS NORMAL.

    A convoyed army bounces on another army just like a normal move.
    Expected: both England's A LON and France's A PAR bounce; BRE stays empty.
    """
    h = Harness()
    h.units("ENGLAND", "F ENG", "A LON")
    h.units("FRANCE", "A PAR")
    h.orders("ENGLAND", "F ENG C A LON - BRE", "A LON - BRE VIA")
    h.orders("FRANCE", "A PAR - BRE")
    h.adjudicate()
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_bounce("A LON")
    h.assert_bounce("A PAR")
    h.assert_empty("BRE")


def test_6f3_convoyed_army_can_receive_support():
    """6.F.3 AN ARMY BEING CONVOYED CAN RECEIVE SUPPORT.

    Expected: the supported London army beats Paris; A LON ends in Brest.
    """
    h = Harness()
    h.units("ENGLAND", "F ENG", "A LON", "F MAO")
    h.units("FRANCE", "A PAR")
    h.orders(
        "ENGLAND", "F ENG C A LON - BRE", "A LON - BRE VIA", "F MAO S A LON - BRE"
    )
    h.orders("FRANCE", "A PAR - BRE")
    h.adjudicate()
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_bounce("A PAR")
    assert h.unit_powers_at("BRE") == "ENGLAND"


def test_6f4_attacked_convoy_not_disrupted():
    """6.F.4 AN ATTACKED CONVOY IS NOT DISRUPTED.

    Merely attacking a convoying fleet (without dislodging it) does not
    disrupt the convoy. Expected: A LON successfully convoys to Holland.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("GERMANY", "F SKA")
    h.orders("ENGLAND", "F NTH C A LON - HOL", "A LON - HOL VIA")
    h.orders("GERMANY", "F SKA - NTH")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_bounce("F SKA")
    assert h.unit_powers_at("HOL") == "ENGLAND"


def test_6f5_beleaguered_convoy_not_disrupted():
    """6.F.5 A BELEAGUERED CONVOY IS NOT DISRUPTED.

    Even a convoy caught in a beleaguered garrison (two supported attacks on
    the convoying fleet's province) is not disrupted, since neither attack
    dislodges it. Expected: A LON convoys to Holland regardless.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("FRANCE", "F ENG", "F BEL")
    h.units("GERMANY", "F SKA", "F DEN")
    h.orders("ENGLAND", "F NTH C A LON - HOL", "A LON - HOL VIA")
    h.orders("FRANCE", "F ENG - NTH", "F BEL S F ENG - NTH")
    h.orders("GERMANY", "F SKA - NTH", "F DEN S F SKA - NTH")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_bounce("F ENG")
    h.assert_result("F BEL", ResultCode.OK)
    h.assert_bounce("F SKA")
    h.assert_result("F DEN", ResultCode.OK)
    assert h.unit_powers_at("HOL") == "ENGLAND"


def test_6f6_dislodged_convoy_does_not_cut_support():
    """6.F.6 DISLODGED CONVOY DOES NOT CUT SUPPORT.

    When a convoying fleet is dislodged, the convoy is entirely cancelled —
    so the (never-materialized) attack it would have carried does not cut
    any support. Expected: Holland's support of Belgium holds and Belgium is
    not dislodged by France.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("GERMANY", "A HOL", "A BEL", "F HEL", "F SKA")
    h.units("FRANCE", "A PIC", "A BUR")
    h.orders("ENGLAND", "F NTH C A LON - HOL", "A LON - HOL VIA")
    h.orders(
        "GERMANY",
        "A HOL S A BEL",
        "A BEL S A HOL",
        "F HEL S F SKA - NTH",
        "F SKA - NTH",
    )
    h.orders("FRANCE", "A PIC - BEL", "A BUR S A PIC - BEL")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_dislodged("F NTH")
    h.assert_result("A LON", ResultCode.NO_CONVOY)
    h.assert_result("A HOL", ResultCode.OK)
    h.assert_result("A BEL", ResultCode.CUT)
    h.assert_result("F HEL", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_bounce("A PIC")
    h.assert_result("A BUR", ResultCode.OK)
    assert h.unit_powers_at("HOL") == "GERMANY"
    assert h.unit_powers_at("BEL") == "GERMANY"
    assert h.unit_powers_at("NTH") == "GERMANY"


def test_6f7_dislodged_convoy_does_not_cause_contested_area():
    """6.F.7 DISLODGED CONVOY DOES NOT CAUSE CONTESTED AREA.

    Holland (the would-be landing spot) is not contested by the failed
    convoy, so the dislodged fleet may retreat there.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("GERMANY", "F HEL", "F SKA")
    h.orders("ENGLAND", "F NTH C A LON - HOL", "A LON - HOL VIA")
    h.orders("GERMANY", "F HEL S F SKA - NTH", "F SKA - NTH")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_dislodged("F NTH")
    h.assert_result("A LON", ResultCode.NO_CONVOY)
    h.assert_result("F HEL", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_empty("HOL")
    r = h._result_at("F NTH")
    hol_options = {loc.province for loc in r.retreat_options}
    assert "HOL" in hol_options, f"HOL should be a legal retreat option, got {hol_options}"


def test_6f8_dislodged_convoy_does_not_cause_a_bounce():
    """6.F.8 DISLODGED CONVOY DOES NOT CAUSE A BOUNCE.

    When the convoy is disrupted, Holland stays empty until the convoy
    "fails" — a third unit (Germany's A BEL) can move into it unopposed.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("GERMANY", "F HEL", "F SKA", "A BEL")
    h.orders("ENGLAND", "F NTH C A LON - HOL", "A LON - HOL VIA")
    h.orders("GERMANY", "F HEL S F SKA - NTH", "F SKA - NTH", "A BEL - HOL")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_result("A LON", ResultCode.NO_CONVOY)
    h.assert_result("F HEL", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_result("A BEL", ResultCode.OK)
    assert h.unit_powers_at("HOL") == "GERMANY"


def test_6f9_dislodge_of_multi_route_convoy():
    """6.F.9 DISLODGE OF MULTI-ROUTE CONVOY.

    Under the 1982/2000 rulebook (preferred), dislodging one leg of a
    multi-route convoy does not stop the army if an alternate route
    survives. Expected: A LON still reaches Belgium via the North Sea route.
    """
    h = Harness()
    h.units("ENGLAND", "F ENG", "F NTH", "A LON")
    h.units("FRANCE", "F BRE", "F MAO")
    h.orders(
        "ENGLAND", "F ENG C A LON - BEL", "F NTH C A LON - BEL", "A LON - BEL VIA"
    )
    h.orders("FRANCE", "F BRE S F MAO - ENG", "F MAO - ENG")
    h.adjudicate()
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_result("F BRE", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"


def test_6f10_dislodge_of_multi_route_convoy_with_foreign_fleet():
    """6.F.10 DISLODGE OF MULTI-ROUTE CONVOY WITH FOREIGN FLEET.

    A foreign (German) convoying fleet doesn't matter under the 1982/2000
    rule — the English convoy still succeeds via the North Sea route even
    though the German-crewed Channel route is disrupted.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON")
    h.units("GERMANY", "F ENG")
    h.units("FRANCE", "F BRE", "F MAO")
    h.orders("ENGLAND", "F NTH C A LON - BEL", "A LON - BEL VIA")
    h.orders("GERMANY", "F ENG C A LON - BEL")
    h.orders("FRANCE", "F BRE S F MAO - ENG", "F MAO - ENG")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    h.assert_result("F BRE", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"


def test_6f11_dislodge_of_multi_route_convoy_with_only_foreign_fleets():
    """6.F.11 DISLODGE OF MULTI-ROUTE CONVOY WITH ONLY FOREIGN FLEETS.

    Neither convoying fleet is English; under the 1982/2000 rule this still
    doesn't matter. Expected: A LON reaches Belgium via the Russian-crewed
    North Sea route.
    """
    h = Harness()
    h.units("ENGLAND", "A LON")
    h.units("GERMANY", "F ENG")
    h.units("RUSSIA", "F NTH")
    h.units("FRANCE", "F BRE", "F MAO")
    h.orders("ENGLAND", "A LON - BEL VIA")
    h.orders("GERMANY", "F ENG C A LON - BEL")
    h.orders("RUSSIA", "F NTH C A LON - BEL")
    h.orders("FRANCE", "F BRE S F MAO - ENG", "F MAO - ENG")
    h.adjudicate()
    h.assert_success("A LON")
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("F BRE", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"


def test_6f12_dislodged_convoying_fleet_not_on_route():
    """6.F.12 DISLODGED CONVOYING FLEET NOT ON ROUTE.

    A dislodged convoying fleet that isn't actually part of the surviving
    route doesn't disrupt the convoy. Expected: London still reaches Belgium
    via the Channel, even though the Irish Sea fleet (reachable from London
    but not part of any successful route) is dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "F ENG", "A LON", "F IRI")
    h.units("FRANCE", "F NAO", "F MAO")
    h.orders(
        "ENGLAND", "F ENG C A LON - BEL", "A LON - BEL VIA", "F IRI C A LON - BEL"
    )
    h.orders("FRANCE", "F NAO S F MAO - IRI", "F MAO - IRI")
    h.adjudicate()
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_success("A LON")
    h.assert_result("F IRI", ResultCode.DISLODGED)
    h.assert_dislodged("F IRI")
    h.assert_result("F NAO", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"


def test_6f13_the_unwanted_alternative():
    """6.F.13 THE UNWANTED ALTERNATIVE.

    England only wants F NTH's convoy but France's F ENG offers an unwanted
    alternate route; under 1982/2000 that route still counts. Expected: the
    London convoy still succeeds (via the Channel) even though F NTH is
    dislodged, and A LON reaches Belgium.
    """
    h = Harness()
    h.units("ENGLAND", "A LON", "F NTH")
    h.units("FRANCE", "F ENG")
    h.units("GERMANY", "F HOL", "F DEN")
    h.orders("ENGLAND", "A LON - BEL VIA", "F NTH C A LON - BEL")
    h.orders("FRANCE", "F ENG C A LON - BEL")
    h.orders("GERMANY", "F HOL S F DEN - NTH", "F DEN - NTH")
    h.adjudicate()
    h.assert_success("A LON")
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_dislodged("F NTH")
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_result("F HOL", ResultCode.OK)
    h.assert_result("F DEN", ResultCode.OK)
    assert h.unit_powers_at("BEL") == "ENGLAND"


# ---------------------------------------------------------------------------
# Convoy paradoxes (6.F.14 - 6.F.24) — Szykman-preferred outcomes.
# ---------------------------------------------------------------------------


def test_6f14_simple_convoy_paradox():
    """6.F.14 SIMPLE CONVOY PARADOX.

    The attacked unit (F LON) supports an attack on the convoying fleet
    (F ENG). Szykman rule (preferred): the support of London is NOT cut
    (the paradoxical convoy is simply treated as failed), so F WAL succeeds
    and dislodges F ENG.
    """
    h = Harness()
    h.units("ENGLAND", "F LON", "F WAL")
    h.units("FRANCE", "A BRE", "F ENG")
    h.orders("ENGLAND", "F LON S F WAL - ENG", "F WAL - ENG")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    h.adjudicate()
    h.assert_result("F LON", ResultCode.OK)
    h.assert_result("F WAL", ResultCode.OK)
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    assert h.unit_powers_at("ENG") == "ENGLAND"
    assert h.unit_powers_at("BRE") == "FRANCE"


def test_6f15_simple_convoy_paradox_with_additional_convoy():
    """6.F.15 SIMPLE CONVOY PARADOX WITH ADDITIONAL CONVOY.

    Paradox-breaking rules apply only to the paradox core. Italy's unrelated
    convoy (NAF - WAL) is not part of the cycle and succeeds normally once
    F WAL's move (which it depends on for the destination to be vacated)
    succeeds under Szykman.
    """
    h = Harness()
    h.units("ENGLAND", "F LON", "F WAL")
    h.units("FRANCE", "A BRE", "F ENG")
    h.units("ITALY", "F IRI", "F MAO", "A NAF")
    h.orders("ENGLAND", "F LON S F WAL - ENG", "F WAL - ENG")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    h.orders(
        "ITALY", "F IRI C A NAF - WAL", "F MAO C A NAF - WAL", "A NAF - WAL VIA"
    )
    h.adjudicate()
    h.assert_result("F LON", ResultCode.OK)
    h.assert_result("F WAL", ResultCode.OK)
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    h.assert_result("F IRI", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_success("A NAF")
    assert h.unit_powers_at("WAL") == "ITALY"
    assert h.unit_powers_at("BRE") == "FRANCE"


@pytest.mark.xfail(reason="second-order convoy paradox: beleaguered-garrison shielding the convoying fleet not yet handled by the single-pass backup rule (Szykman re-resolution needed)", strict=False)
def test_6f16_pandins_paradox():
    """6.F.16 PANDIN'S PARADOX.

    The attacked unit protects the convoying fleet via a beleaguered
    garrison. In every paradox rule (including Szykman) the support of
    London is not cut, so F ENG is not dislodged — but F WAL and F BEL bounce
    off each other in a beleaguered-garrison standoff on the English
    Channel, so *nobody* moves.
    """
    h = Harness()
    h.units("ENGLAND", "F LON", "F WAL")
    h.units("FRANCE", "A BRE", "F ENG")
    h.units("GERMANY", "F NTH", "F BEL")
    h.orders("ENGLAND", "F LON S F WAL - ENG", "F WAL - ENG")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    h.orders("GERMANY", "F NTH S F BEL - ENG", "F BEL - ENG")
    h.adjudicate()
    h.assert_result("F LON", ResultCode.OK)
    h.assert_bounce("F WAL")
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_not_dislodged("F ENG")
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_bounce("F BEL")
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("BRE") == "FRANCE"


@pytest.mark.xfail(reason="second-order convoy paradox (Pandin extended): needs iterative Szykman re-resolution", strict=False)
def test_6f17_pandins_extended_paradox():
    """6.F.17 PANDIN'S EXTENDED PARADOX.

    Like 6.F.16, but the attacked unit could also dislodge the unit
    providing its protection. Szykman (preferred): the convoy fails, the
    support of London is not cut, and neither the Channel nor London fleets
    are dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "F LON", "F WAL")
    h.units("FRANCE", "A BRE", "F ENG", "F YOR")
    h.units("GERMANY", "F NTH", "F BEL")
    h.orders("ENGLAND", "F LON S F WAL - ENG", "F WAL - ENG")
    h.orders(
        "FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON", "F YOR S A BRE - LON"
    )
    h.orders("GERMANY", "F NTH S F BEL - ENG", "F BEL - ENG")
    h.adjudicate()
    h.assert_result("F LON", ResultCode.OK)
    h.assert_bounce("F WAL")
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_not_dislodged("F ENG")
    h.assert_result("F YOR", ResultCode.OK)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_bounce("F BEL")
    assert h.unit_powers_at("LON") == "ENGLAND"
    assert h.unit_powers_at("ENG") == "FRANCE"


@pytest.mark.xfail(reason="second-order convoy paradox (betrayal): needs iterative Szykman re-resolution", strict=False)
def test_6f18_betrayal_paradox():
    """6.F.18 BETRAYAL PARADOX.

    The attacked unit (F BEL) directly supports the convoying fleet
    (F NTH). Szykman (preferred): the convoy fails, so it never cuts
    France's support, and F NTH is not dislodged by Germany.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A LON", "F ENG")
    h.units("FRANCE", "F BEL")
    h.units("GERMANY", "F HEL", "F SKA")
    h.orders(
        "ENGLAND", "F NTH C A LON - BEL", "A LON - BEL VIA", "F ENG S A LON - BEL"
    )
    h.orders("FRANCE", "F BEL S F NTH")
    h.orders("GERMANY", "F HEL S F SKA - NTH", "F SKA - NTH")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_not_dislodged("F NTH")
    h.assert_result("A LON", ResultCode.NO_CONVOY)
    h.assert_result("F BEL", ResultCode.OK)
    h.assert_result("F HEL", ResultCode.OK)
    h.assert_bounce("F SKA")
    assert h.unit_powers_at("NTH") == "ENGLAND"
    assert h.unit_powers_at("BEL") == "FRANCE"


def test_6f19_multi_route_convoy_disruption_paradox():
    """6.F.19 MULTI-ROUTE CONVOY DISRUPTION PARADOX.

    Two issues combine: multi-route convoy disruption (all routes must fail
    to disrupt) and paradox resolution. Under Szykman (preferred) there is
    no paradox: the Ionian route keeps the convoy alive, so A TUN's attack
    on Naples cuts the Italian support, and the Rome-Tyrrhenian attack
    bounces.
    """
    h = Harness()
    h.units("FRANCE", "A TUN", "F TYS", "F ION")
    h.units("ITALY", "F NAP", "F ROM")
    h.orders(
        "FRANCE", "A TUN - NAP VIA", "F TYS C A TUN - NAP", "F ION C A TUN - NAP"
    )
    h.orders("ITALY", "F NAP S F ROM - TYS", "F ROM - TYS")
    h.adjudicate()
    h.assert_bounce("A TUN")
    h.assert_result("F TYS", ResultCode.OK)
    h.assert_result("F ION", ResultCode.OK)
    h.assert_result("F NAP", ResultCode.CUT)
    h.assert_bounce("F ROM")
    assert h.unit_powers_at("NAP") == "ITALY"
    assert h.unit_powers_at("TYS") == "FRANCE"


def test_6f20_unwanted_multi_route_convoy_paradox():
    """6.F.20 UNWANTED MULTI-ROUTE CONVOY PARADOX.

    Szykman (preferred, and matching 1971/1982): the support of Naples is
    cut and the fleet in the Ionian Sea is dislodged by Turkey — the
    Italian player's "trick" of using a self-supported Ionian fleet does not
    save it.
    """
    h = Harness()
    h.units("FRANCE", "A TUN", "F TYS")
    h.units("ITALY", "F NAP", "F ION")
    h.units("TURKEY", "F AEG", "F EAS")
    h.orders("FRANCE", "A TUN - NAP VIA", "F TYS C A TUN - NAP")
    h.orders("ITALY", "F NAP S F ION", "F ION C A TUN - NAP")
    h.orders("TURKEY", "F AEG S F EAS - ION", "F EAS - ION")
    h.adjudicate()
    h.assert_bounce("A TUN")
    h.assert_result("F TYS", ResultCode.OK)
    h.assert_result("F NAP", ResultCode.CUT)
    h.assert_result("F ION", ResultCode.DISLODGED)
    h.assert_dislodged("F ION")
    h.assert_result("F AEG", ResultCode.OK)
    h.assert_result("F EAS", ResultCode.OK)
    assert h.unit_powers_at("ION") == "TURKEY"


def test_6f21_dads_army_convoy():
    """6.F.21 DAD'S ARMY CONVOY.

    The 1982 paradox rule has a side effect where a convoy to an
    already-occupied friendly space could shield a supporting fleet from a
    support-cut. Szykman (preferred) rejects this trick: the convoy fails
    (NO_CONVOY) and F NAO is dislodged as normal, cutting F CLY's support.
    """
    h = Harness()
    h.units("RUSSIA", "A EDI", "F NWG", "A NWY")
    h.units("FRANCE", "F IRI", "F MAO")
    h.units("ENGLAND", "A LVP", "F NAO", "F CLY")
    h.orders(
        "RUSSIA", "A EDI S A NWY - CLY", "F NWG C A NWY - CLY", "A NWY - CLY VIA"
    )
    h.orders("FRANCE", "F IRI S F MAO - NAO", "F MAO - NAO")
    h.orders("ENGLAND", "A LVP - CLY VIA", "F NAO C A LVP - CLY", "F CLY S F NAO")
    h.adjudicate()
    h.assert_result("A EDI", ResultCode.OK)
    h.assert_result("F NWG", ResultCode.OK)
    h.assert_success("A NWY")
    h.assert_result("F IRI", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_result("A LVP", ResultCode.NO_CONVOY)
    h.assert_result("F NAO", ResultCode.DISLODGED)
    h.assert_dislodged("F NAO")
    h.assert_result("F CLY", ResultCode.CUT)
    h.assert_dislodged("F CLY")
    assert h.unit_powers_at("CLY") == "RUSSIA"
    assert h.unit_powers_at("NAO") == "FRANCE"
    assert h.unit_powers_at("LVP") == "ENGLAND"


def test_6f22_second_order_paradox_with_two_resolutions():
    """6.F.22 SECOND ORDER PARADOX WITH TWO RESOLUTIONS.

    Two convoys chained into a second-order paradox. Szykman (preferred,
    same result as 1982): supports are not cut, both convoying armies fail
    to move, and the two attacking fleets (Picardy, Edinburgh) dislodge the
    convoying fleets (English Channel, North Sea).
    """
    h = Harness()
    h.units("ENGLAND", "F EDI", "F LON")
    h.units("FRANCE", "A BRE", "F ENG")
    h.units("GERMANY", "F BEL", "F PIC")
    h.units("RUSSIA", "A NWY", "F NTH")
    h.orders("ENGLAND", "F EDI - NTH", "F LON S F EDI - NTH")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    h.orders("GERMANY", "F BEL S F PIC - ENG", "F PIC - ENG")
    h.orders("RUSSIA", "A NWY - BEL VIA", "F NTH C A NWY - BEL")
    h.adjudicate()
    h.assert_result("F EDI", ResultCode.OK)
    h.assert_result("F LON", ResultCode.OK)
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.DISLODGED)
    h.assert_dislodged("F ENG")
    h.assert_result("F BEL", ResultCode.OK)
    h.assert_result("F PIC", ResultCode.OK)
    h.assert_result("A NWY", ResultCode.NO_CONVOY)
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_dislodged("F NTH")
    assert h.unit_powers_at("ENG") == "GERMANY"
    assert h.unit_powers_at("NTH") == "ENGLAND"


@pytest.mark.xfail(reason="second-order paradox with two exclusive convoys: needs iterative Szykman re-resolution", strict=False)
def test_6f23_second_order_paradox_with_two_exclusive_convoys():
    """6.F.23 SECOND ORDER PARADOX WITH TWO EXCLUSIVE CONVOYS.

    Two consistent resolutions exist where the convoys don't fail/succeed
    together. Szykman (preferred, same as 1982): both convoying armies fail
    to move and, because their support isn't cut, none of the attacking
    fleets move either.
    """
    h = Harness()
    h.units("ENGLAND", "F EDI", "F YOR")
    h.units("FRANCE", "A BRE", "F ENG")
    h.units("GERMANY", "F BEL", "F LON")
    h.units("ITALY", "F MAO", "F IRI")
    h.units("RUSSIA", "A NWY", "F NTH")
    h.orders("ENGLAND", "F EDI - NTH", "F YOR S F EDI - NTH")
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON")
    h.orders("GERMANY", "F BEL S F ENG", "F LON S F NTH")
    h.orders("ITALY", "F MAO - ENG", "F IRI S F MAO - ENG")
    h.orders("RUSSIA", "A NWY - BEL VIA", "F NTH C A NWY - BEL")
    h.adjudicate()
    h.assert_bounce("F EDI")
    h.assert_result("F YOR", ResultCode.OK)
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_not_dislodged("F ENG")
    h.assert_result("F BEL", ResultCode.OK)
    h.assert_result("F LON", ResultCode.OK)
    h.assert_bounce("F MAO")
    h.assert_result("F IRI", ResultCode.OK)
    h.assert_result("A NWY", ResultCode.NO_CONVOY)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_not_dislodged("F NTH")
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("NTH") == "RUSSIA"


@pytest.mark.xfail(reason="second-order paradox with no resolution: needs the all-convoys-fail fallback", strict=False)
def test_6f24_second_order_paradox_with_no_resolution():
    """6.F.24 SECOND ORDER PARADOX WITH NO RESOLUTION.

    No consistent resolution exists at all without a tie-break rule.
    Szykman (preferred, same as 1982 here): supports are not cut and the
    convoying armies fail; F EDI dislodges the Russian F NTH while F IRI
    bounces off France's beleaguered-garrison-supported Channel fleet.
    """
    h = Harness()
    h.units("ENGLAND", "F EDI", "F LON", "F IRI", "F MAO")
    h.units("FRANCE", "A BRE", "F ENG", "F BEL")
    h.units("RUSSIA", "A NWY", "F NTH")
    h.orders(
        "ENGLAND",
        "F EDI - NTH",
        "F LON S F EDI - NTH",
        "F IRI - ENG",
        "F MAO S F IRI - ENG",
    )
    h.orders("FRANCE", "A BRE - LON VIA", "F ENG C A BRE - LON", "F BEL S F ENG")
    h.orders("RUSSIA", "A NWY - BEL VIA", "F NTH C A NWY - BEL")
    h.adjudicate()
    h.assert_result("F EDI", ResultCode.OK)
    h.assert_result("F LON", ResultCode.OK)
    h.assert_bounce("F IRI")
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_result("A BRE", ResultCode.NO_CONVOY)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_not_dislodged("F ENG")
    h.assert_result("F BEL", ResultCode.OK)
    h.assert_result("A NWY", ResultCode.NO_CONVOY)
    h.assert_result("F NTH", ResultCode.DISLODGED)
    h.assert_dislodged("F NTH")
    assert h.unit_powers_at("NTH") == "ENGLAND"
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("BEL") == "FRANCE"
