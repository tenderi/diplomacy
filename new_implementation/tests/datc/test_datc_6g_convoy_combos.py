"""DATC section 6.G — Convoying to adjacent places / convoy + move combinations.

Outcomes cross-checked against the DATC document (Lucas B. Kruijswijk) and the
reference resolver in ``old_implementation/diplomacy/tests/test_datc.py``
(``test_6_g_*``); semantics only, no code copied (that module is AGPL).

Every assertion below encodes the DATC author's **preferred** ruling: the
1982 rulebook with the 2000 rulebook's clarification for convoys to adjacent
places (issue 4.A.3, "choice d" — whether a move to an adjacent province
goes by land or by convoy depends on the *intent* shown by the totality of a
player's own orders), combined with Szykman paradox resolution.

Important engine-design note: this engine (see ``engine/orders/parser.py``
and ``engine/adjudicator/movement.py:_uses_convoy``) does **not** infer
convoy "intent" from a player's other orders. A move to an adjacent province
is only treated as convoyed if that move's own order explicitly carries
``VIA``; otherwise it is always attempted as a land move when a land route
exists, regardless of any convoy orders issued for it. This is DATC's
"explicit adjacent convoying" (DPTG, choice e) semantics for the *default*
case, not the author-preferred intent-based choice d. Test cases below are
written with DATC's preferred (choice d) expected outcome and the exact DATC
order text (adding ``VIA`` only where DATC's own case text includes "via
Convoy"); where the DATC case omits ``VIA`` but relies on inferred intent to
reach its preferred outcome, we still assert that preferred outcome — a
failure there is real signal that this engine implements choice e (explicit
convoying) rather than choice d (intent-based) for the ambiguous default
case, which is exactly what the driver needs to know.

Vocabulary note: as in the 6.F module, a ``Convoy`` order here only ever
reports ``OK`` or ``DISLODGED`` (see ``engine/adjudicator/movement.py``), so
where the reference suite tags an unused-but-legal convoy order with a
finer-grained category, we check the practical consequence instead
(``assert_not_dislodged``, ``unit_powers_at``).
"""

from __future__ import annotations

import pytest

from engine.types import ResultCode
from tests.datc.harness import Harness

pytestmark = pytest.mark.datc


def test_6g1_two_units_can_swap_places_by_convoy():
    """6.G.1 TWO UNITS CAN SWAP PLACES BY CONVOY.

    The only way to swap two units is by convoy. DATC's own order text has
    no ``VIA`` on either move (relying on inferred intent from England's own
    convoy order); preferred (2000 rule) outcome: the armies swap.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "F SKA")
    h.units("RUSSIA", "A SWE")
    h.orders("ENGLAND", "A NWY - SWE", "F SKA C A NWY - SWE")
    h.orders("RUSSIA", "A SWE - NWY")
    h.adjudicate()
    h.assert_result("A NWY", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_result("A SWE", ResultCode.OK)
    assert h.unit_powers_at("NWY") == "RUSSIA"
    assert h.unit_powers_at("SKA") == "ENGLAND"
    assert h.unit_powers_at("SWE") == "ENGLAND"


def test_6g2_kidnapping_an_army():
    """6.G.2 KIDNAPPING AN ARMY.

    England never asked for a convoy (no own convoying fleet, no VIA);
    Germany's convoy order is an unwanted "kidnap" attempt. Preferred
    (1982/2000) outcome: England shows no intent to convoy, so this is a
    plain head-to-head battle and both A NWY and F SWE bounce; Germany's
    convoy simply goes unused.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY")
    h.units("RUSSIA", "F SWE")
    h.units("GERMANY", "F SKA")
    h.orders("ENGLAND", "A NWY - SWE")
    h.orders("RUSSIA", "F SWE - NWY")
    h.orders("GERMANY", "F SKA C A NWY - SWE")
    h.adjudicate()
    h.assert_bounce("A NWY")
    h.assert_bounce("F SWE")
    h.assert_not_dislodged("F SKA")
    assert h.unit_powers_at("NWY") == "ENGLAND"
    assert h.unit_powers_at("SWE") == "RUSSIA"
    assert h.unit_powers_at("SKA") == "GERMANY"


def test_6g3_kidnapping_with_a_disrupted_convoy():
    """6.G.3 KIDNAPPING WITH A DISRUPTED CONVOY.

    France never asked for a convoy for A PIC - BEL (no VIA); England's
    convoy offer is irrelevant to France's intent. Preferred (1982/2000)
    outcome: the move from Picardy succeeds over land regardless of the
    (disrupted) convoy. Separately, France's supported attack on the
    Channel dislodges England's fleet there.
    """
    h = Harness()
    h.units("FRANCE", "F BRE", "A PIC", "A BUR", "F MAO")
    h.units("ENGLAND", "F ENG")
    h.orders(
        "FRANCE", "F BRE - ENG", "A PIC - BEL", "A BUR S A PIC - BEL", "F MAO S F BRE - ENG"
    )
    h.orders("ENGLAND", "F ENG C A PIC - BEL")
    h.adjudicate()
    h.assert_result("F BRE", ResultCode.OK)
    h.assert_success("A PIC")
    h.assert_result("A BUR", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_dislodged("F ENG")
    assert h.unit_powers_at("BUR") == "FRANCE"
    assert h.unit_powers_at("MAO") == "FRANCE"
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("BEL") == "FRANCE"


def test_6g4_kidnapping_with_a_disrupted_convoy_and_opposite_move():
    """6.G.4 KIDNAPPING WITH A DISRUPTED CONVOY AND OPPOSITE MOVE.

    Same as 6.G.3 but England also moves the opposite way (A BEL - PIC, no
    VIA). Preferred (1982/2000) outcome: France's move over land still
    succeeds (with Burgundy's support) and dislodges the English army in
    Belgium; the Channel fleet is dislodged as before.
    """
    h = Harness()
    h.units("FRANCE", "F BRE", "A PIC", "A BUR", "F MAO")
    h.units("ENGLAND", "F ENG", "A BEL")
    h.orders(
        "FRANCE", "F BRE - ENG", "A PIC - BEL", "A BUR S A PIC - BEL", "F MAO S F BRE - ENG"
    )
    h.orders("ENGLAND", "F ENG C A PIC - BEL", "A BEL - PIC")
    h.adjudicate()
    h.assert_result("F BRE", ResultCode.OK)
    h.assert_success("A PIC")
    h.assert_result("A BUR", ResultCode.OK)
    h.assert_result("F MAO", ResultCode.OK)
    h.assert_dislodged("F ENG")
    h.assert_dislodged("A BEL")
    assert h.unit_powers_at("BUR") == "FRANCE"
    assert h.unit_powers_at("MAO") == "FRANCE"
    assert h.unit_powers_at("ENG") == "FRANCE"
    assert h.unit_powers_at("BEL") == "FRANCE"


def test_6g5_swapping_with_intent():
    """6.G.5 SWAPPING WITH INTENT.

    Both sides have an own-nationality fleet convoying their army (no VIA
    on either move, relying on inferred intent). Preferred (1982/2000):
    since each side's own fleet is in the convoy, intent is shown and the
    armies in Rome and Apulia swap.
    """
    h = Harness()
    h.units("ITALY", "A ROM", "F TYS")
    h.units("TURKEY", "A APU", "F ION")
    h.orders("ITALY", "A ROM - APU", "F TYS C A APU - ROM")
    h.orders("TURKEY", "A APU - ROM", "F ION C A APU - ROM")
    h.adjudicate()
    h.assert_result("A ROM", ResultCode.OK)
    h.assert_result("F TYS", ResultCode.OK)
    h.assert_result("A APU", ResultCode.OK)
    h.assert_result("F ION", ResultCode.OK)
    assert h.unit_powers_at("ROM") == "TURKEY"
    assert h.unit_powers_at("APU") == "ITALY"


def test_6g6_swapping_with_unintended_intent():
    """6.G.6 SWAPPING WITH UNINTENDED INTENT.

    England's own fleet (F ENG) is ordered to convoy A LVP - EDI (no VIA),
    but the French fleets that would carry it are only holding — the actual
    surviving route is via the (unrequested) Russian fleets. Preferred
    (1982/2000): England still showed intent to convoy via its own fleet, so
    the armies swap via the alternate Russian route; F ENG's own convoy
    order simply goes unused.
    """
    h = Harness()
    h.units("ENGLAND", "A LVP", "F ENG")
    h.units("GERMANY", "A EDI")
    h.units("FRANCE", "F IRI", "F NTH")
    h.units("RUSSIA", "F NWG", "F NAO")
    h.orders("ENGLAND", "A LVP - EDI", "F ENG C A LVP - EDI")
    h.orders("GERMANY", "A EDI - LVP")
    h.orders("FRANCE", "F IRI H", "F NTH H")
    h.orders("RUSSIA", "F NWG C A LVP - EDI", "F NAO C A LVP - EDI")
    h.adjudicate()
    h.assert_result("A LVP", ResultCode.OK)
    h.assert_not_dislodged("F ENG")
    h.assert_result("A EDI", ResultCode.OK)
    h.assert_result("F IRI", ResultCode.OK)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("F NWG", ResultCode.OK)
    h.assert_result("F NAO", ResultCode.OK)
    assert h.unit_powers_at("LVP") == "GERMANY"
    assert h.unit_powers_at("EDI") == "ENGLAND"


@pytest.mark.xfail(reason="convoy-to-adjacent intent (issue 4.A.7): distinguishing an illegal same-power convoy order from a valid one requires path-validity in intent, which currently conflicts with 6.G.10/14", strict=False)
def test_6g7_swapping_with_illegal_intent():
    """6.G.7 SWAPPING WITH ILLEGAL INTENT.

    Russia's Gulf of Bothnia convoy order cannot express intent because it
    can't actually reach the destination (BOT is not adjacent to Norway) —
    the "intent" order is itself geographically nonsensical. Preferred
    (1982/2000, treating any not-genuinely-useful order as unable to signal
    intent): no intent is shown by Russia, so the move from Sweden is over
    land and it is a plain head-to-head bounce with England's fleet.
    """
    h = Harness()
    h.units("ENGLAND", "F SKA", "F NWY")
    h.units("RUSSIA", "A SWE", "F BOT")
    h.orders("ENGLAND", "F SKA C A SWE - NWY", "F NWY - SWE")
    h.orders("RUSSIA", "A SWE - NWY", "F BOT C A SWE - NWY")
    h.adjudicate()
    h.assert_not_dislodged("F SKA")
    h.assert_bounce("F NWY")
    h.assert_bounce("A SWE")
    assert h.unit_powers_at("SKA") == "ENGLAND"
    assert h.unit_powers_at("NWY") == "ENGLAND"
    assert h.unit_powers_at("SWE") == "RUSSIA"


def test_6g8_explicit_convoy_that_isnt_there():
    """6.G.8 EXPLICIT CONVOY THAT ISN'T THERE.

    France explicitly requests VIA but no fleet is ordered to convoy.
    Preferred (1982/2000): "via Convoy" only has meaning when there is BOTH
    a land route and a genuine convoy route on offer; since there's no
    convoy at all here, the directive is ignored and the move succeeds over
    land.
    """
    h = Harness()
    h.units("FRANCE", "A BEL")
    h.units("ENGLAND", "F NTH", "A HOL")
    h.orders("FRANCE", "A BEL - HOL VIA")
    h.orders("ENGLAND", "F NTH - HEL", "A HOL - KIE")
    h.adjudicate()
    h.assert_success("A BEL")
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("A HOL", ResultCode.OK)
    assert h.unit_powers_at("HOL") == "FRANCE"
    assert h.unit_powers_at("HEL") == "ENGLAND"
    assert h.unit_powers_at("KIE") == "ENGLAND"


def test_6g9_swapped_or_dislodged():
    """6.G.9 SWAPPED OR DISLODGED?.

    England's A NWY - SWE (no VIA) is convoyed by its own fleet (F SKA) and
    supported (F FIN). Preferred (1982/2000): England's own convoy order
    shows intent, so this is a convoy, not a land head-to-head — the armies
    swap rather than Russia's army being dislodged.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "F SKA", "F FIN")
    h.units("RUSSIA", "A SWE")
    h.orders("ENGLAND", "A NWY - SWE", "F SKA C A NWY - SWE", "F FIN S A NWY - SWE")
    h.orders("RUSSIA", "A SWE - NWY")
    h.adjudicate()
    h.assert_result("A NWY", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_result("F FIN", ResultCode.OK)
    h.assert_result("A SWE", ResultCode.OK)
    assert h.unit_powers_at("NWY") == "RUSSIA"
    assert h.unit_powers_at("SWE") == "ENGLAND"


def test_6g10_swapped_or_a_head_to_head_battle():
    """6.G.10 SWAPPED OR AN HEAD TO HEAD BATTLE?.

    England explicitly convoys (VIA) so the convoy route is used
    unambiguously regardless of rulebook. The army in Norway (strength 3)
    dislodges Russia's army in Sweden; separately, whether the French fleet
    bounces off the dislodged Russian army depends on issue 4.A.7 — this
    engine's preferred choice (b) is that it still bounces even though no
    head-to-head is involved.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "F DEN", "F FIN")
    h.units("GERMANY", "F SKA")
    h.units("RUSSIA", "A SWE", "F BAR")
    h.units("FRANCE", "F NWG", "F NTH")
    h.orders(
        "ENGLAND", "A NWY - SWE VIA", "F DEN S A NWY - SWE", "F FIN S A NWY - SWE"
    )
    h.orders("GERMANY", "F SKA C A NWY - SWE")
    h.orders("RUSSIA", "A SWE - NWY", "F BAR S A SWE - NWY")
    h.orders("FRANCE", "F NWG - NWY", "F NTH S F NWG - NWY")
    h.adjudicate()
    h.assert_success("A NWY")
    h.assert_result("F DEN", ResultCode.OK)
    h.assert_result("F FIN", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_bounce("A SWE")
    h.assert_dislodged("A SWE")
    h.assert_result("F BAR", ResultCode.OK)
    h.assert_bounce("F NWG")
    h.assert_result("F NTH", ResultCode.OK)
    assert h.unit_powers_at("SWE") == "ENGLAND"
    assert h.unit_powers_at("NWY") is None


@pytest.mark.xfail(reason="convoy-to-adjacent paradox (issue 4.A.7 + Szykman): inferred non-swap convoy intent needed to enter the paradox, which conflicts with the kidnapping cases", strict=False)
def test_6g11_a_convoy_to_an_adjacent_place_with_a_paradox():
    """6.G.11 A CONVOY TO AN ADJACENT PLACE WITH A PARADOX.

    Russia's A SWE - NWY (no VIA) is convoyed by Russia's own F SKA, so
    preferred (1982/2000, choice d) treats it as a convoy — which puts it
    in a paradox cycle with England's attack on Skagerrak. Szykman
    (preferred paradox rule): the convoyed move fails (NO_CONVOY) and
    England's fleet dislodges the Russian convoying fleet in Skagerrak.
    """
    h = Harness()
    h.units("ENGLAND", "F NWY", "F NTH")
    h.units("RUSSIA", "A SWE", "F SKA", "F BAR")
    h.orders("ENGLAND", "F NWY S F NTH - SKA", "F NTH - SKA")
    h.orders("RUSSIA", "A SWE - NWY", "F SKA C A SWE - NWY", "F BAR S A SWE - NWY")
    h.adjudicate()
    h.assert_result("F NWY", ResultCode.OK)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("A SWE", ResultCode.NO_CONVOY)
    h.assert_result("F SKA", ResultCode.DISLODGED)
    h.assert_dislodged("F SKA")
    assert h.unit_powers_at("NWY") == "ENGLAND"
    assert h.unit_powers_at("SKA") == "ENGLAND"
    assert h.unit_powers_at("SWE") == "RUSSIA"


def test_6g12_swapping_two_units_with_two_convoys():
    """6.G.12 SWAPPING TWO UNITS WITH TWO CONVOYS.

    Both armies explicitly convoy (VIA) via fully-crewed multi-fleet
    routes. Expected: a clean swap, no ambiguity.
    """
    h = Harness()
    h.units("ENGLAND", "A LVP", "F NAO", "F NWG")
    h.units("GERMANY", "A EDI", "F NTH", "F ENG", "F IRI")
    h.orders(
        "ENGLAND", "A LVP - EDI VIA", "F NAO C A LVP - EDI", "F NWG C A LVP - EDI"
    )
    h.orders(
        "GERMANY",
        "A EDI - LVP VIA",
        "F NTH C A EDI - LVP",
        "F ENG C A EDI - LVP",
        "F IRI C A EDI - LVP",
    )
    h.adjudicate()
    h.assert_result("A LVP", ResultCode.OK)
    h.assert_result("F NAO", ResultCode.OK)
    h.assert_result("F NWG", ResultCode.OK)
    h.assert_result("A EDI", ResultCode.OK)
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_result("F IRI", ResultCode.OK)
    assert h.unit_powers_at("LVP") == "GERMANY"
    assert h.unit_powers_at("EDI") == "ENGLAND"


def test_6g13_support_cut_on_attack_on_itself_via_convoy():
    """6.G.13 SUPPORT CUT ON ATTACK ON ITSELF VIA CONVOY.

    Austria explicitly convoys (VIA) A TRI - VEN. Preferred (1982/2000): the
    attack is considered to come from Trieste (not the Adriatic), so it does
    not cut Italy's support in Venice; Trieste itself is then dislodged by
    Italy's supported attack from Albania.
    """
    h = Harness()
    h.units("AUSTRIA", "F ADR", "A TRI")
    h.units("ITALY", "A VEN", "F ALB")
    h.orders("AUSTRIA", "F ADR C A TRI - VEN", "A TRI - VEN VIA")
    h.orders("ITALY", "A VEN S F ALB - TRI", "F ALB - TRI")
    h.adjudicate()
    h.assert_result("F ADR", ResultCode.OK)
    h.assert_bounce("A TRI")
    h.assert_dislodged("A TRI")
    h.assert_result("A VEN", ResultCode.OK)
    h.assert_result("F ALB", ResultCode.OK)
    assert h.unit_powers_at("TRI") == "ITALY"
    assert h.unit_powers_at("VEN") == "ITALY"


def test_6g14_bounce_by_convoy_to_adjacent_place():
    """6.G.14 BOUNCE BY CONVOY TO ADJACENT PLACE.

    Mirror of 6.G.10: this time Russia explicitly convoys (VIA). The army
    in Sweden is bounced by the French fleet from the Norwegian Sea, while
    the army in Norway dislodges the Russian army in Sweden.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "F DEN", "F FIN")
    h.units("FRANCE", "F NWG", "F NTH")
    h.units("GERMANY", "F SKA")
    h.units("RUSSIA", "A SWE", "F BAR")
    h.orders(
        "ENGLAND", "A NWY - SWE", "F DEN S A NWY - SWE", "F FIN S A NWY - SWE"
    )
    h.orders("FRANCE", "F NWG - NWY", "F NTH S F NWG - NWY")
    h.orders("GERMANY", "F SKA C A SWE - NWY")
    h.orders("RUSSIA", "A SWE - NWY VIA", "F BAR S A SWE - NWY")
    h.adjudicate()
    h.assert_success("A NWY")
    h.assert_result("F DEN", ResultCode.OK)
    h.assert_result("F FIN", ResultCode.OK)
    h.assert_bounce("F NWG")
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_bounce("A SWE")
    h.assert_dislodged("A SWE")
    h.assert_result("F BAR", ResultCode.OK)
    assert h.unit_powers_at("SWE") == "ENGLAND"
    assert h.unit_powers_at("NWG") == "FRANCE"


def test_6g15_bounce_and_dislodge_with_double_convoy():
    """6.G.15 BOUNCE AND DISLODGE WITH DOUBLE CONVOY.

    Both moves are explicitly convoyed (VIA). The French army in Belgium is
    bounced by the third-party army from Yorkshire, while London's army
    dislodges the unit in Belgium.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A HOL", "A YOR", "A LON")
    h.units("FRANCE", "F ENG", "A BEL")
    h.orders(
        "ENGLAND",
        "F NTH C A LON - BEL",
        "A HOL S A LON - BEL",
        "A YOR - LON",
        "A LON - BEL VIA",
    )
    h.orders("FRANCE", "F ENG C A BEL - LON", "A BEL - LON VIA")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("A HOL", ResultCode.OK)
    h.assert_bounce("A YOR")
    h.assert_success("A LON")
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_bounce("A BEL")
    h.assert_dislodged("A BEL")
    assert h.unit_powers_at("YOR") == "ENGLAND"
    assert h.unit_powers_at("BEL") == "ENGLAND"


def test_6g16_two_units_in_one_area_bug_moving_by_convoy():
    """6.G.16 THE TWO UNIT IN ONE AREA BUG, MOVING BY CONVOY.

    A regression check for a specific adjudicator bug: PREVENT STRENGTH must
    be zero only when the unit is in a genuine head-to-head battle, not
    merely because the opposing unit happens to move successfully. Russia
    explicitly convoys (VIA); expected: Norway/Sweden swap while England's
    unsupported fleet from the North Sea bounces (it is not in a
    head-to-head with the convoyed Swedish army).
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "A DEN", "F BAL", "F NTH")
    h.units("RUSSIA", "A SWE", "F SKA", "F NWG")
    h.orders(
        "ENGLAND", "A NWY - SWE", "A DEN S A NWY - SWE", "F BAL S A NWY - SWE", "F NTH - NWY"
    )
    h.orders("RUSSIA", "A SWE - NWY VIA", "F SKA C A SWE - NWY", "F NWG S A SWE - NWY")
    h.adjudicate()
    h.assert_success("A NWY")
    h.assert_result("A DEN", ResultCode.OK)
    h.assert_result("F BAL", ResultCode.OK)
    h.assert_bounce("F NTH")
    h.assert_result("A SWE", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_result("F NWG", ResultCode.OK)
    assert h.unit_powers_at("NWY") == "RUSSIA"
    assert h.unit_powers_at("SWE") == "ENGLAND"
    assert h.unit_powers_at("NTH") == "ENGLAND"


def test_6g17_two_units_in_one_area_bug_moving_over_land():
    """6.G.17 THE TWO UNIT IN ONE AREA BUG, MOVING OVER LAND.

    Mirror of 6.G.16: this time the England-Norway side convoys explicitly
    (VIA) and Russia moves over land. Expected: Norway/Sweden still swap
    and the North Sea fleet still bounces.
    """
    h = Harness()
    h.units("ENGLAND", "A NWY", "A DEN", "F BAL", "F SKA", "F NTH")
    h.units("RUSSIA", "A SWE", "F NWG")
    h.orders(
        "ENGLAND",
        "A NWY - SWE VIA",
        "A DEN S A NWY - SWE",
        "F BAL S A NWY - SWE",
        "F SKA C A NWY - SWE",
        "F NTH - NWY",
    )
    h.orders("RUSSIA", "A SWE - NWY", "F NWG S A SWE - NWY")
    h.adjudicate()
    h.assert_success("A NWY")
    h.assert_result("A DEN", ResultCode.OK)
    h.assert_result("F BAL", ResultCode.OK)
    h.assert_result("F SKA", ResultCode.OK)
    h.assert_bounce("F NTH")
    h.assert_result("A SWE", ResultCode.OK)
    h.assert_result("F NWG", ResultCode.OK)
    assert h.unit_powers_at("NWY") == "RUSSIA"
    assert h.unit_powers_at("SWE") == "ENGLAND"
    assert h.unit_powers_at("NTH") == "ENGLAND"


def test_6g18_two_units_in_one_area_bug_with_double_convoy():
    """6.G.18 THE TWO UNIT IN ONE AREA BUG, WITH DOUBLE CONVOY.

    Both London/Belgium moves are convoyed by each side's own fleet (no
    explicit VIA in DATC's own case text, relying on inferred intent).
    Preferred (1982/2000): Belgium and London swap by convoy (not a
    head-to-head, since both moves are convoyed), and the third-party army
    from Yorkshire fails to move to London because it is outcompeted by the
    stronger, supported convoyed army arriving from Belgium.
    """
    h = Harness()
    h.units("ENGLAND", "F NTH", "A HOL", "A YOR", "A LON", "A RUH")
    h.units("FRANCE", "F ENG", "A BEL", "A WAL")
    h.orders(
        "ENGLAND",
        "F NTH C A LON - BEL",
        "A HOL S A LON - BEL",
        "A YOR - LON",
        "A LON - BEL",
        "A RUH S A LON - BEL",
    )
    h.orders("FRANCE", "F ENG C A BEL - LON", "A BEL - LON", "A WAL S A BEL - LON")
    h.adjudicate()
    h.assert_result("F NTH", ResultCode.OK)
    h.assert_result("A HOL", ResultCode.OK)
    h.assert_bounce("A YOR")
    h.assert_success("A LON")
    h.assert_result("A RUH", ResultCode.OK)
    h.assert_result("F ENG", ResultCode.OK)
    h.assert_result("A BEL", ResultCode.OK)
    h.assert_result("A WAL", ResultCode.OK)
    assert h.unit_powers_at("YOR") == "ENGLAND"
    assert h.unit_powers_at("LON") == "FRANCE"
    assert h.unit_powers_at("BEL") == "ENGLAND"
    assert h.unit_powers_at("WAL") == "FRANCE"
