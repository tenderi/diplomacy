"""``rendering.order_overlay``: engine ``Order``/``Resolution`` → the overlay's
order dicts. What those dicts then *look like* is ``tests/test_order_symbols.py``."""
import pytest

from engine.serialization import resolution_to_dict
from engine.types import (
    Build,
    Convoy,
    Disband,
    Hold,
    Location,
    Move,
    OrderResult,
    Resolution,
    ResultCode,
    Retreat,
    SupportHold,
    SupportMove,
    UnitKind,
    Waive,
)
from rendering.order_overlay import (
    order_to_viz,
    orders_by_power_to_viz,
    resolution_dict_to_viz,
    standoff_provinces,
)

pytestmark = pytest.mark.unit


def _loc(prov: str, coast: str | None = None) -> Location:
    return Location(prov, coast)


def _resolve(*results: OrderResult) -> dict:
    return resolution_dict_to_viz(resolution_to_dict(Resolution(results=results)))


def test_move_viz_carries_its_own_province_and_outcome() -> None:
    o = Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR"))
    assert order_to_viz(o, "ok", {"PAR": "A"}) == {
        "type": "move", "power": "FRANCE", "unit": "A PAR", "province": "PAR", "target": "BUR",
        "result": "ok", "status": "success", "dislodged": False, "via_convoy": False, "convoy_chain": [],
    }


def test_unknown_kind_defaults_to_army() -> None:
    assert order_to_viz(Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR")))["unit"] == "A PAR"


def test_an_unadjudicated_order_is_pending() -> None:
    viz = order_to_viz(Hold(power="ENGLAND", unit=_loc("LON")), kind_by_province={"LON": "F"})
    assert (viz["type"], viz["unit"], viz["result"], viz["status"]) == ("hold", "F LON", "pending", "pending")


def test_supports_name_what_they_support() -> None:
    hold = order_to_viz(SupportHold(power="ENGLAND", unit=_loc("LON"), target=_loc("WAL")))
    move = order_to_viz(SupportMove(power="FRANCE", unit=_loc("MAR"), origin=_loc("PAR"), dest=_loc("BUR")))
    assert (hold["supported_action"], hold["supported_unit_province"]) == ("hold", "WAL")
    assert (move["supported_action"], move["supported_unit_province"], move["supported_target"]) == ("move", "PAR", "BUR")


def test_build_carries_the_kind_to_draw() -> None:
    viz = order_to_viz(Build(power="FRANCE", location=_loc("BRE"), kind=UnitKind.FLEET))
    assert (viz["type"], viz["province"], viz["unit_kind"]) == ("build", "BRE", "F")


def test_disband_and_retreat() -> None:
    assert order_to_viz(Disband(power="FRANCE", unit=_loc("PAR")))["type"] == "destroy"
    retreat = order_to_viz(Retreat(power="FRANCE", unit=_loc("BUR"), dest=_loc("PIC")))
    assert (retreat["type"], retreat["province"], retreat["target"]) == ("retreat", "BUR", "PIC")


def test_waive_draws_nothing() -> None:
    assert order_to_viz(Waive(power="FRANCE")) is None


def test_coast_is_stripped_to_province() -> None:
    viz = order_to_viz(Move(power="RUSSIA", unit=_loc("STP", "SC"), dest=_loc("BOT")))
    assert (viz["province"], viz["unit"]) == ("STP", "A STP")


def test_waive_only_powers_are_dropped() -> None:
    out = orders_by_power_to_viz({"FRANCE": [Hold(power="FRANCE", unit=_loc("PAR")), Waive(power="FRANCE")], "ITALY": []})
    assert list(out) == ["FRANCE"] and len(out["FRANCE"]) == 1


def test_resolution_carries_each_result_code() -> None:
    viz = _resolve(
        OrderResult(order=Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR")), result=ResultCode.OK),
        OrderResult(order=Move(power="GERMANY", unit=_loc("MUN"), dest=_loc("BUR")), result=ResultCode.BOUNCE),
        OrderResult(order=SupportHold(power="ENGLAND", unit=_loc("LON"), target=_loc("WAL")), result=ResultCode.CUT),
        OrderResult(order=SupportHold(power="ITALY", unit=_loc("ROM"), target=_loc("VEN")), result=ResultCode.VOID),
    )
    assert [(p, v[0]["result"], v[0]["status"]) for p, v in sorted(viz.items())] == [
        ("ENGLAND", "cut", "failed"), ("FRANCE", "ok", "success"), ("GERMANY", "bounce", "bounced"), ("ITALY", "void", "failed"),
    ]


def test_a_dislodged_mover_keeps_its_bounce_and_is_marked_dislodged() -> None:
    """The engine reports a unit knocked out while moving as BOUNCE + dislodged. The
    old adapter read only the code, so the map showed a plain bounce."""
    viz = _resolve(OrderResult(order=Move(power="GERMANY", unit=_loc("BUR"), dest=_loc("PAR")),
                               result=ResultCode.BOUNCE, dislodged=True))
    assert (viz["GERMANY"][0]["result"], viz["GERMANY"][0]["dislodged"]) == ("bounce", True)


def test_a_dislodged_hold() -> None:
    viz = _resolve(OrderResult(order=Hold(power="GERMANY", unit=_loc("MUN")), result=ResultCode.DISLODGED, dislodged=True))
    assert (viz["GERMANY"][0]["result"], viz["GERMANY"][0]["status"], viz["GERMANY"][0]["dislodged"]) == ("dislodged", "dislodged", True)


class TestConvoys:
    def test_the_convoyed_move_carries_every_fleet_on_its_route(self) -> None:
        viz = orders_by_power_to_viz({"ENGLAND": [
            Move(power="ENGLAND", unit=_loc("LON"), dest=_loc("HOL"), via_convoy=True),
            Convoy(power="ENGLAND", unit=_loc("ENG"), origin=_loc("LON"), dest=_loc("HOL")),
        ], "FRANCE": [
            Convoy(power="FRANCE", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
        ]})
        move = next(v for v in viz["ENGLAND"] if v["type"] == "move")
        assert move["convoy_chain"] == ["ENG", "NTH"]

    def test_each_fleet_keeps_its_own_entry_and_outcome(self) -> None:
        viz = _resolve(
            OrderResult(order=Convoy(power="ENGLAND", unit=_loc("ENG"), origin=_loc("LON"), dest=_loc("HOL")),
                        result=ResultCode.DISLODGED, dislodged=True),
            OrderResult(order=Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
                        result=ResultCode.OK),
        )
        assert [(v["province"], v["dislodged"], v["convoy_chain"]) for v in viz["ENGLAND"]] == [
            ("ENG", True, ["ENG", "NTH"]), ("NTH", False, ["ENG", "NTH"]),
        ]

    def test_an_overland_move_is_never_routed_through_fleets(self) -> None:
        viz = orders_by_power_to_viz({"FRANCE": [
            Move(power="FRANCE", unit=_loc("PIC"), dest=_loc("BEL")),
            Convoy(power="FRANCE", unit=_loc("ENG"), origin=_loc("PIC"), dest=_loc("BEL")),
        ]})
        assert viz["FRANCE"][0]["convoy_chain"] == []

    def test_unrelated_convoys_have_their_own_chains(self) -> None:
        viz = orders_by_power_to_viz({"ENGLAND": [
            Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
            Convoy(power="ENGLAND", unit=_loc("TYS"), origin=_loc("NAP"), dest=_loc("TUN")),
        ]})
        assert [v["convoy_chain"] for v in viz["ENGLAND"]] == [["NTH"], ["TYS"]]


def _move_result(origin: str, dest: str, result: str) -> dict:
    return {"order": {"type": "MOVE", "power": "FRANCE", "unit": origin, "dest": dest, "via_convoy": False}, "result": result}


@pytest.mark.parametrize(("results", "standoffs"), [
    ([_move_result("PAR", "BUR", "BOUNCE"), _move_result("MUN", "BUR", "BOUNCE")], ["BUR"]),
    ([_move_result("PAR", "BUR", "OK"), _move_result("MUN", "BUR", "BOUNCE")], []),  # 2 beat 1: no standoff
    ([_move_result("PAR", "BUR", "BOUNCE")], []),  # one move bouncing off a holding unit
    ([_move_result("BRE", "ENG", "BOUNCE"), _move_result("LON", "ENG", "BOUNCE"),
      _move_result("PAR", "BUR", "BOUNCE"), _move_result("MUN", "BUR", "BOUNCE")], ["BUR", "ENG"]),
])
def test_standoff_provinces(results: list, standoffs: list) -> None:
    assert standoff_provinces({"results": results}) == standoffs
