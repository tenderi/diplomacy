"""Tests for ``server.order_notes`` -- the order helper notes (#460).

Pure module tests: a hand-built ``GameState`` on the standard map, a power and
its own orders in, notes out. One test per note the issue lists; each asserts
the exact sentence, so it fails without its note.
"""

from __future__ import annotations

import pytest

from engine.map_loader import load_standard_map
from engine.types import DislodgedUnit, GameState, Location, PhaseType, Season, Unit, UnitKind
from server.order_notes import convoy_routes, order_notes

pytestmark = pytest.mark.unit

_MAP = load_standard_map()


def _unit(spec: str) -> Unit:
    power, kind, where = spec.split()
    province, _, coast = where.partition("/")
    return Unit(UnitKind(kind), power, Location(province, coast or None))


def _state(*units: str, phase: PhaseType = PhaseType.MOVEMENT, **kw: object) -> GameState:
    season = {PhaseType.ADJUSTMENT: Season.WINTER}.get(phase, Season.SPRING)
    return GameState(
        year=1901,
        season=season,
        phase_type=phase,
        units=frozenset(_unit(u) for u in units),
        ownership=dict(_MAP.initial_ownership),
        **kw,  # type: ignore[arg-type]
    )


def _notes(state: GameState, power: str, *orders: str) -> dict[str, list[str]]:
    """``{order: [note text, ...]}`` for every order, plus ``"*"`` for the set notes."""
    out = order_notes(_MAP, state, power, list(orders))
    by_order = {e["order"]: [n["text"] for n in e["notes"]] for e in out["orders"]}
    by_order["*"] = [n["text"] for n in out["notes"]]
    return by_order


def _codes(state: GameState, power: str, *orders: str) -> dict[str, list[str]]:
    out = order_notes(_MAP, state, power, list(orders))
    return {e["order"]: [n["code"] for n in e["notes"]] for e in out["orders"]}


# -- 1. why an order is impossible -------------------------------------------------


def test_a_convoyed_move_names_the_one_fleet_that_could_carry_it() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F NTH")
    assert _notes(state, "ENGLAND", "A LON - NWY", "F NTH H")["A LON - NWY"] == [
        "A LON - NWY needs a convoy: it can succeed only if F NTH convoys it"
    ]


def test_a_convoyed_move_names_every_fleet_of_a_chain_and_their_power() -> None:
    state = _state("ENGLAND A LON", "FRANCE F ENG", "FRANCE F MAO")
    assert _notes(state, "ENGLAND", "A LON - POR")["A LON - POR"] == [
        "A LON - POR needs a convoy: it can succeed only if France's F ENG and "
        "France's F MAO both convoy it"
    ]


def test_a_convoyed_move_lists_the_alternative_routes() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F NTH", "ENGLAND F ENG")
    assert _notes(state, "ENGLAND", "A LON - BEL", "F NTH H", "F ENG H")["A LON - BEL"] == [
        "A LON - BEL needs a convoy: it can succeed only if F ENG convoys it, or if F NTH convoys it"
    ]


def test_a_convoyed_move_with_no_fleet_chain_is_impossible_this_turn() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F EDI")
    out = order_notes(_MAP, state, "ENGLAND", ["A LON - NWY"])
    assert out["orders"][0]["ok"] is True  # legal: it just cannot succeed
    assert out["orders"][0]["notes"] == [
        {
            "kind": "impossible",
            "code": "no_convoy_route",
            "text": "A LON - NWY cannot succeed this turn: no chain of fleets at sea reaches "
            "from LON to NWY, so no convoy can carry it",
        }
    ]


def test_an_army_in_an_inland_province_cannot_be_convoyed() -> None:
    state = _state("FRANCE A PAR")
    assert _notes(state, "FRANCE", "A PAR - LON")["A PAR - LON"] == [
        "A PAR cannot reach LON this turn: LON is not next to PAR, and an army in an inland province cannot be convoyed"
    ]


def test_an_army_cannot_be_convoyed_into_an_inland_province() -> None:
    state = _state("FRANCE A BRE")
    assert _notes(state, "FRANCE", "A BRE - MUN")["A BRE - MUN"] == [
        "A BRE cannot reach MUN this turn: MUN is not next to BRE, and an army can be convoyed only to a coastal province"
    ]


def test_a_fleet_cannot_move_inland() -> None:
    state = _state("FRANCE F BRE")
    assert _notes(state, "FRANCE", "F BRE - PAR")["F BRE - PAR"] == [
        "F BRE cannot move to PAR: a fleet moves only through seas and along coasts, and PAR is inland"
    ]


def test_an_army_cannot_move_to_a_sea() -> None:
    state = _state("FRANCE A PIC")
    assert _notes(state, "FRANCE", "A PIC - ENG")["A PIC - ENG"] == [
        "A PIC cannot move to ENG: an army cannot enter a sea; it crosses water only when fleets convoy it"
    ]


def test_only_an_army_moves_by_convoy() -> None:
    state = _state("FRANCE F BRE")
    assert _notes(state, "FRANCE", "F BRE - PIC VIA")["F BRE - PIC VIA"] == [
        "only an army can be convoyed; F BRE has to move on its own"
    ]


def test_a_split_coast_move_with_no_coast_names_both() -> None:
    state = _state("FRANCE F MAO")
    assert _notes(state, "FRANCE", "F MAO - SPA")["F MAO - SPA"] == [
        "SPA has two coasts and F MAO can reach both: name one, SPA/NC or SPA/SC"
    ]


def test_a_split_coast_move_to_the_wrong_coast_names_the_right_one() -> None:
    state = _state("FRANCE F GAS")
    assert _notes(state, "FRANCE", "F GAS - SPA/SC")["F GAS - SPA/SC"] == [
        "F GAS can reach only SPA/NC of SPA: order F GAS - SPA/NC"
    ]


def test_a_support_out_of_reach_says_why_and_who_could_give_it() -> None:
    state = _state("FRANCE A PAR", "FRANCE A MAR", "FRANCE A GAS", "FRANCE F BRE")
    assert _notes(state, "FRANCE", "A PAR S A MAR - SPA")["A PAR S A MAR - SPA"] == [
        "A PAR cannot support into SPA: a unit can support only into a province it could move "
        "to itself, and A PAR cannot move to SPA. Your units that could give this support: A GAS"
    ]


def test_a_support_hold_out_of_reach_has_the_same_note() -> None:
    state = _state("FRANCE F BRE", "FRANCE A PAR")
    assert _notes(state, "FRANCE", "F BRE S A PAR")["F BRE S A PAR"] == [
        "F BRE cannot support into PAR: a unit can support only into a province it could move "
        "to itself, and F BRE cannot move to PAR"
    ]


def test_a_fleet_in_a_coastal_province_cannot_convoy() -> None:
    state = _state("FRANCE F BRE", "FRANCE A PIC")
    assert _notes(state, "FRANCE", "F BRE C A PIC - LON")["F BRE C A PIC - LON"] == [
        "F BRE is in a coastal province: only a fleet at sea can convoy"
    ]


def test_a_convoy_for_an_inland_army_cannot_be_used() -> None:
    state = _state("ENGLAND F NTH", "FRANCE A BUR")
    assert _notes(state, "ENGLAND", "F NTH C A BUR - LON")["F NTH C A BUR - LON"] == [
        "BUR is not on a coast, so no fleet can convoy an army from it"
    ]


def test_a_convoy_off_every_route_has_no_effect() -> None:
    # NTH touches LON but not BRE, and no other fleet links them.
    state = _state("ENGLAND F NTH", "FRANCE A BRE")
    assert _notes(state, "ENGLAND", "F NTH C A BRE - LON")["F NTH C A BRE - LON"] == [
        "F NTH cannot help carry the army from BRE to LON: no chain of fleets between them "
        "passes through NTH"
    ]


def _retreat_state() -> GameState:
    """France's A PIC dislodged from BUR; BEL occupied; PAR left empty by a standoff."""
    du = DislodgedUnit(
        _unit("FRANCE A PIC"),
        attacker_origin="BUR",
        retreats=(Location("BRE"),),
    )
    return _state(
        "GERMANY A PIC",
        "GERMANY A BEL",
        phase=PhaseType.RETREAT,
        dislodged=(du,),
        contested=frozenset({"PAR"}),
    )


@pytest.mark.parametrize(
    ("order", "why"),
    [
        ("A PIC R BUR", "the unit that dislodged it attacked from there"),
        ("A PIC R BEL", "another unit stands there"),
        ("A PIC R PAR", "a standoff left it empty this turn, and no unit may retreat there"),
    ],
)
def test_a_refused_retreat_says_why_and_where_it_can_go(order: str, why: str) -> None:
    dest = order.split()[-1]
    assert _notes(_retreat_state(), "FRANCE", order)[order] == [
        f"A PIC cannot retreat to {dest}: {why}. A PIC can retreat to BRE, or disband"
    ]


def test_a_unit_with_no_retreat_can_only_disband() -> None:
    state = _state(
        "GERMANY A PIC",
        phase=PhaseType.RETREAT,
        dislodged=(DislodgedUnit(_unit("FRANCE A PIC"), attacker_origin="BUR", retreats=()),),
    )
    assert _notes(state, "FRANCE", "A PIC R BUR")["A PIC R BUR"] == [
        "A PIC cannot retreat to BUR: the unit that dislodged it attacked from there. "
        "A PIC has no retreat and can only disband"
    ]


def _build_state(*units: str) -> GameState:
    """France owns its three home centres; ``units`` decide how many builds it has."""
    return _state(*units, phase=PhaseType.ADJUSTMENT)


def test_a_build_outside_the_home_centres_lists_the_builds_there_are() -> None:
    state = _build_state("FRANCE A PAR")
    assert _notes(state, "FRANCE", "BUILD A BUR")["BUILD A BUR"] == [
        "you cannot build in BUR: BUR is not one of your home supply centres. "
        "You can build A BRE, A MAR, F BRE or F MAR"
    ]


def test_a_build_on_a_centre_not_owned_says_so() -> None:
    state = _build_state("FRANCE A PAR")
    state.ownership["MAR"] = "ITALY"
    state.ownership["SPA"] = "FRANCE"  # keep two builds due
    assert _notes(state, "FRANCE", "BUILD A MAR")["BUILD A MAR"] == [
        "you cannot build in MAR: you do not own MAR now. You can build A BRE or F BRE"
    ]


def test_a_build_on_an_occupied_centre_says_so() -> None:
    state = _build_state("FRANCE A PAR")
    assert _notes(state, "FRANCE", "BUILD A PAR")["BUILD A PAR"] == [
        "you cannot build in PAR: PAR is occupied. You can build A BRE, A MAR, F BRE or F MAR"
    ]


def test_a_build_of_the_wrong_unit_type_names_the_one_that_fits() -> None:
    state = _build_state("FRANCE A BUR")
    assert _notes(state, "FRANCE", "BUILD F PAR")["BUILD F PAR"] == ["in PAR you can build A PAR"]


def test_a_build_with_no_free_site_says_builds_are_waived() -> None:
    state = _build_state("FRANCE A PAR", "FRANCE A BRE", "FRANCE A MAR")
    state.ownership["BEL"] = "FRANCE"
    assert _notes(state, "FRANCE", "BUILD A BUR")["BUILD A BUR"] == [
        "you cannot build in BUR: BUR is not one of your home supply centres, and you have no "
        "free home centre of your own to build on, so your builds are waived"
    ]


def test_a_build_when_nothing_is_owed() -> None:
    state = _build_state("FRANCE A PAR", "FRANCE A BRE", "FRANCE A MAR")
    assert _notes(state, "FRANCE", "BUILD A PAR")["BUILD A PAR"] == [
        "no build is due: you have 3 supply centres and 3 units"
    ]
    state = _build_state("FRANCE A PAR", "FRANCE A BRE", "FRANCE A MAR", "FRANCE A BUR")
    assert _notes(state, "FRANCE", "BUILD A PAR")["BUILD A PAR"] == [
        "no build is due: you have 3 supply centres and 4 units, so you must disband 1 unit"
    ]


# -- 2. accepted, but it depends on something ---------------------------------------


def test_a_convoyed_move_carried_by_the_players_own_convoy_has_no_note() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F NTH")
    assert _notes(state, "ENGLAND", "A LON - NWY", "F NTH C A LON - NWY")["A LON - NWY"] == []


def test_a_convoyed_move_names_the_foreign_fleet_its_own_convoy_still_needs() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F ENG", "FRANCE F MAO")
    assert _notes(state, "ENGLAND", "A LON - POR", "F ENG C A LON - POR")["A LON - POR"] == [
        "A LON - POR needs a convoy: it can succeed only if F ENG and France's F MAO both convoy it"
    ]


def test_a_support_for_an_own_unit_ordered_to_hold() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F NTH", "ENGLAND F ENG")
    notes = _notes(state, "ENGLAND", "F ENG S A LON - BEL", "A LON H")
    assert notes["F ENG S A LON - BEL"] == ["F ENG supports A LON - BEL, but A LON is ordered to hold"]


def test_a_support_for_an_own_unit_ordered_elsewhere_or_not_at_all() -> None:
    state = _state("FRANCE A PAR", "FRANCE A MAR")
    assert _notes(state, "FRANCE", "A MAR S A PAR - BUR", "A PAR - PIC")["A MAR S A PAR - BUR"] == [
        "A MAR supports A PAR - BUR, but A PAR is ordered to move to PIC"
    ]
    assert _notes(state, "FRANCE", "A MAR S A PAR - BUR")["A MAR S A PAR - BUR"] == [
        "A MAR supports A PAR - BUR, but A PAR has no order, so it will hold"
    ]
    # A matching order: no note.
    assert _notes(state, "FRANCE", "A MAR S A PAR - BUR", "A PAR - BUR")["A MAR S A PAR - BUR"] == []


def test_a_support_to_hold_for_an_own_unit_ordered_to_move() -> None:
    state = _state("FRANCE A PAR", "FRANCE A BUR")
    assert _notes(state, "FRANCE", "A BUR S A PAR", "A PAR - PIC")["A BUR S A PAR"] == [
        "A BUR supports A PAR to hold, but A PAR is ordered to move to PIC: a unit ordered to "
        "move cannot be supported in place"
    ]


def test_a_support_for_a_foreign_unit_says_nothing_about_its_orders() -> None:
    state = _state("FRANCE A MAR", "GERMANY A MUN")
    assert _notes(state, "FRANCE", "A MAR S A MUN - BUR")["A MAR S A MUN - BUR"] == []


def test_a_convoy_for_an_own_army_ordered_otherwise() -> None:
    state = _state("ENGLAND A LON", "ENGLAND F NTH")
    assert _notes(state, "ENGLAND", "F NTH C A LON - NWY", "A LON H")["F NTH C A LON - NWY"] == [
        "F NTH convoys A LON - NWY, but A LON is ordered to hold"
    ]


def test_two_own_units_ordered_into_one_province() -> None:
    state = _state("FRANCE A PAR", "FRANCE A MAR", "FRANCE A GAS")
    notes = _notes(state, "FRANCE", "A PAR - BUR", "A MAR - BUR", "A GAS H")
    assert notes["A PAR - BUR"] == [
        "you also ordered A MAR - BUR: two of your units moving into BUR bounce off each "
        "other unless one has more support"
    ]
    assert notes["A MAR - BUR"] == [
        "you also ordered A PAR - BUR: two of your units moving into BUR bounce off each "
        "other unless one has more support"
    ]


def test_a_support_for_an_attack_on_the_players_own_unit() -> None:
    state = _state("AUSTRIA A VIE", "AUSTRIA F TRI", "ITALY A VEN")
    assert _codes(state, "AUSTRIA", "A VIE S A VEN - TRI", "F TRI H")["A VIE S A VEN - TRI"] == [
        "own_unit_support"
    ]
    assert _notes(state, "AUSTRIA", "A VIE S A VEN - TRI", "F TRI H")["A VIE S A VEN - TRI"] == [
        "your own F TRI is there: this support has no effect unless it moves away"
    ]


def test_a_unit_without_an_order_will_hold() -> None:
    state = _state("FRANCE A PAR", "FRANCE F BRE")
    assert _notes(state, "FRANCE", "A PAR - BUR")["*"] == ["F BRE has no order, so it will hold"]
    assert _notes(state, "FRANCE", "A PAR - BUR", "F BRE H")["*"] == []


def test_a_dislodged_unit_without_an_order_will_be_disbanded() -> None:
    assert _notes(_retreat_state(), "FRANCE")["*"] == ["A PIC has no order, so it will be disbanded"]
    assert _notes(_retreat_state(), "FRANCE", "A PIC R BRE")["*"] == []


def test_builds_and_disbands_not_yet_ordered() -> None:
    state = _build_state("FRANCE A PAR")
    assert _notes(state, "FRANCE", "BUILD A MAR")["*"] == [
        "you may build 1 more unit; a build you do not order is waived"
    ]
    assert _notes(state, "FRANCE", "BUILD A MAR", "WAIVE")["*"] == []
    state = _build_state("FRANCE A PAR", "FRANCE A BRE", "FRANCE A MAR", "FRANCE A BUR", "FRANCE A PIC")
    assert _notes(state, "FRANCE")["*"] == [
        "you must disband 2 more units; if you do not choose, the units farthest from your "
        "home centres are removed for you"
    ]


# -- the rules of the module ----------------------------------------------------------


def test_notes_read_only_the_requesting_powers_orders() -> None:
    """Another power's order in the list is not the requester's: it fails validation
    and changes nothing about the requester's notes. The function has no input for
    other powers' pending orders, so it cannot reveal them."""
    state = _state("ENGLAND A LON", "FRANCE F ENG")
    alone = _notes(state, "ENGLAND", "A LON - BEL")
    with_french = _notes(state, "ENGLAND", "A LON - BEL", "F ENG C A LON - BEL")
    assert with_french["A LON - BEL"] == alone["A LON - BEL"] == [
        "A LON - BEL needs a convoy: it can succeed only if France's F ENG convoys it"
    ]
    assert with_french["F ENG C A LON - BEL"] == []  # refused (not England's), and not explained


def test_a_later_order_for_a_unit_replaces_the_earlier_one() -> None:
    state = _state("FRANCE A PAR", "FRANCE A MAR")
    notes = _notes(state, "FRANCE", "A MAR S A PAR - BUR", "A PAR H", "A PAR - BUR")
    assert notes["A MAR S A PAR - BUR"] == []


def test_an_unparsable_order_has_no_notes() -> None:
    out = order_notes(_MAP, _state("FRANCE A PAR"), "france", ["  ", "nonsense"])
    assert out["orders"] == [{"order": "nonsense", "ok": False, "notes": []}]


def test_convoy_routes_agree_with_the_adjudicators_possible_route() -> None:
    from engine.adjudicator.movement import convoy_route_possible

    state = _state("ENGLAND F NTH", "ENGLAND F NWG", "FRANCE F ENG", "FRANCE F MAO", "ITALY F WES")
    coasts = ["LON", "EDI", "NWY", "BEL", "BRE", "POR", "TUN", "NAF", "SPA", "CLY", "HOL"]
    for src in coasts:
        for dst in coasts:
            if src != dst:
                found = bool(convoy_routes(_MAP, state, src, dst))
                assert found == convoy_route_possible(_MAP, state, src, dst), (src, dst)
    routes = convoy_routes(_MAP, state, "LON", "NAF")
    assert [[str(f) for f in r] for r in routes] == [["F ENG", "F MAO"]]


def test_an_army_ordered_to_its_own_province_is_told_to_hold() -> None:
    state = _state("FRANCE A PAR")
    assert _notes(state, "FRANCE", "A PAR - PAR")["A PAR - PAR"] == [
        "A PAR is already in PAR: to stay there, order it to hold"
    ]
