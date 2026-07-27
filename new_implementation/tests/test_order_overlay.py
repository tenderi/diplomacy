"""Unit tests for rendering.order_overlay — the engine ``Order``/``Resolution`` →
renderer order-dict adapter. Pure dict conversion, no PNG rendering."""
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
    SupportHold,
    SupportMove,
    UnitKind,
    Waive,
)
from rendering.order_overlay import (
    order_to_viz,
    orders_by_power_to_viz,
    resolution_dict_to_viz,
)

pytestmark = pytest.mark.unit


def _loc(prov, coast=None):
    return Location(prov, coast)


def test_move_viz_uses_provinces_and_kind_lookup():
    o = Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR"))
    assert order_to_viz(o, "success", {"PAR": "A"}) == {
        "type": "move",
        "unit": "A PAR",
        "target": "BUR",
        "status": "success",
    }


def test_move_viz_defaults_kind_to_army_when_unknown():
    o = Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR"))
    assert order_to_viz(o)["unit"] == "A PAR"


def test_hold_viz():
    o = Hold(power="ENGLAND", unit=_loc("LON"))
    assert order_to_viz(o, kind_by_province={"LON": "F"}) == {
        "type": "hold",
        "unit": "F LON",
        "status": "success",
    }


def test_support_hold_viz():
    o = SupportHold(power="FRANCE", unit=_loc("BRE"), target=_loc("PAR"))
    d = order_to_viz(o)
    assert d["type"] == "support"
    assert d["supported_action"] == "hold"
    assert d["supported_unit_province"] == "PAR"


def test_support_move_viz_carries_origin_and_target():
    o = SupportMove(power="FRANCE", unit=_loc("BUR"), origin=_loc("PIC"), dest=_loc("BEL"))
    d = order_to_viz(o)
    assert d["type"] == "support"
    assert d["supported_action"] == "move"
    assert d["supported_unit_province"] == "PIC"
    assert d["supported_target"] == "BEL"


def test_convoy_viz():
    o = Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("BEL"))
    d = order_to_viz(o)
    assert d["type"] == "convoy"
    assert d["convoyed_army_province"] == "LON"
    assert d["target"] == "BEL"
    assert d["convoy_chain"] == ["NTH"]


def test_build_viz_has_no_unit_province():
    o = Build(power="FRANCE", location=_loc("PAR"), kind=UnitKind.ARMY)
    assert order_to_viz(o) == {
        "type": "build",
        "unit": "",
        "target": "PAR",
        "status": "success",
    }


def test_disband_becomes_destroy():
    o = Disband(power="FRANCE", unit=_loc("MAR"))
    assert order_to_viz(o)["type"] == "destroy"


def test_waive_draws_nothing():
    assert order_to_viz(Waive(power="FRANCE")) is None


def test_coast_is_stripped_to_province():
    o = Move(power="RUSSIA", unit=_loc("STP", "SC"), dest=_loc("BOT"))
    assert order_to_viz(o)["unit"] == "A STP"


def test_orders_by_power_groups_and_drops_waives():
    orders = {
        "FRANCE": [
            Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR")),
            Waive(power="FRANCE"),
        ],
        "ITALY": [],
    }
    out = orders_by_power_to_viz(orders, {"PAR": "A"})
    assert list(out.keys()) == ["FRANCE"]  # empty/waive-only powers dropped
    assert len(out["FRANCE"]) == 1


def test_resolution_dict_to_viz_colours_status_by_result():
    res = Resolution(
        results=(
            OrderResult(
                order=Move(power="FRANCE", unit=_loc("PAR"), dest=_loc("BUR")),
                result=ResultCode.OK,
            ),
            OrderResult(
                order=Move(power="GERMANY", unit=_loc("MUN"), dest=_loc("BUR")),
                result=ResultCode.BOUNCE,
            ),
            OrderResult(
                order=SupportHold(power="ENGLAND", unit=_loc("LON"), target=_loc("WAL")),
                result=ResultCode.CUT,
            ),
        )
    )
    viz = resolution_dict_to_viz(resolution_to_dict(res))
    assert viz["FRANCE"][0]["status"] == "success"
    assert viz["GERMANY"][0]["status"] == "bounced"
    assert viz["ENGLAND"][0]["status"] == "failed"
