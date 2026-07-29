"""Unit tests for rendering.order_overlay — the engine ``Order``/``Resolution`` →
renderer order-dict adapter (pure dict conversion), plus a few PNG-rendering
sanity checks (``TestConvoyAndDislodgedRendering``) proving the merged convoy
chain and the new "dislodged" status actually draw differently, not just that
the dict shapes look right."""
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
from rendering.map import Map
from rendering.order_overlay import (
    order_to_viz,
    orders_by_power_to_viz,
    resolution_dict_to_viz,
)

pytestmark = pytest.mark.unit

_SVG_PATH = "maps/standard.svg"
_PHASE_INFO = {"turn": 1, "year": 1901, "season": "SPRING", "phase": "MOVEMENT", "phase_code": "S1901M"}


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


def test_dislodged_hold_gets_its_own_status_not_success():
    res = Resolution(
        results=(
            OrderResult(
                order=Hold(power="GERMANY", unit=_loc("MUN")),
                result=ResultCode.DISLODGED,
                dislodged=True,
            ),
        )
    )
    viz = resolution_dict_to_viz(resolution_to_dict(res))
    assert viz["GERMANY"][0]["status"] == "dislodged"


class TestConvoyChainMerging:
    """Multiple fleets convoying the same army on the same route collapse into
    one viz entry listing every fleet, instead of one entry per fleet."""

    def test_two_fleet_chain_merges_into_one_entry(self):
        orders = {
            "ENGLAND": [
                Move(power="ENGLAND", unit=_loc("LON"), dest=_loc("HOL")),
                Convoy(power="ENGLAND", unit=_loc("ENG"), origin=_loc("LON"), dest=_loc("HOL")),
                Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
            ]
        }
        viz = orders_by_power_to_viz(orders)
        convoy_entries = [d for d in viz["ENGLAND"] if d["type"] == "convoy"]
        assert len(convoy_entries) == 1
        assert convoy_entries[0]["convoy_chain"] == ["ENG", "NTH"]

    def test_single_fleet_convoy_still_a_one_element_chain(self):
        orders = {
            "ENGLAND": [
                Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
            ]
        }
        viz = orders_by_power_to_viz(orders)
        assert viz["ENGLAND"][0]["convoy_chain"] == ["NTH"]

    def test_merge_across_powers_files_under_first_fleets_power(self):
        """Two different powers can convoy the same army (allied convoy); the
        merged entry still needs exactly one home to live under."""
        orders = {
            "ENGLAND": [Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL"))],
            "FRANCE": [Convoy(power="FRANCE", unit=_loc("ENG"), origin=_loc("LON"), dest=_loc("HOL"))],
        }
        viz = orders_by_power_to_viz(orders)
        all_convoys = [d for power in viz.values() for d in power if d["type"] == "convoy"]
        assert len(all_convoys) == 1
        assert set(all_convoys[0]["convoy_chain"]) == {"NTH", "ENG"}

    def test_resolution_merge_uses_worst_status_when_a_fleet_is_dislodged(self):
        res = Resolution(
            results=(
                OrderResult(
                    order=Move(power="ENGLAND", unit=_loc("LON"), dest=_loc("HOL")),
                    result=ResultCode.OK,
                ),
                OrderResult(
                    order=Convoy(power="ENGLAND", unit=_loc("ENG"), origin=_loc("LON"), dest=_loc("HOL")),
                    result=ResultCode.DISLODGED,
                    dislodged=True,
                ),
                OrderResult(
                    order=Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
                    result=ResultCode.NO_CONVOY,
                ),
            )
        )
        viz = resolution_dict_to_viz(resolution_to_dict(res))
        convoy_entries = [d for d in viz["ENGLAND"] if d["type"] == "convoy"]
        assert len(convoy_entries) == 1
        assert convoy_entries[0]["status"] == "dislodged"
        assert set(convoy_entries[0]["convoy_chain"]) == {"ENG", "NTH"}

    def test_unrelated_convoys_stay_separate_entries(self):
        orders = {
            "ENGLAND": [
                Convoy(power="ENGLAND", unit=_loc("NTH"), origin=_loc("LON"), dest=_loc("HOL")),
                Convoy(power="ENGLAND", unit=_loc("TYS"), origin=_loc("NAP"), dest=_loc("TUN")),
            ]
        }
        viz = orders_by_power_to_viz(orders)
        convoy_entries = [d for d in viz["ENGLAND"] if d["type"] == "convoy"]
        assert len(convoy_entries) == 2
        chains = {tuple(d["convoy_chain"]) for d in convoy_entries}
        assert chains == {("NTH",), ("TYS",)}


class TestConvoyAndDislodgedRendering:
    """PNG-level proof that a merged convoy chain draws every fleet's marker and
    that a dislodged order renders visibly differently from a successful one --
    dict-shape assertions alone (above) can't catch a renderer-side regression
    like an unhandled status silently falling through to "no marker drawn"."""

    def test_dislodged_hold_differs_from_successful_hold(self):
        units = {"GERMANY": ["A MUN"]}
        success_viz = {"GERMANY": [{"type": "hold", "unit": "A MUN", "status": "success"}]}
        dislodged_viz = {"GERMANY": [{"type": "hold", "unit": "A MUN", "status": "dislodged"}]}

        success_png = Map.render_board_png_resolution(
            _SVG_PATH, units, success_viz, {"conflicts": []}, phase_info=_PHASE_INFO
        )
        dislodged_png = Map.render_board_png_resolution(
            _SVG_PATH, units, dislodged_viz, {"conflicts": []}, phase_info=_PHASE_INFO
        )
        assert success_png[:8] == b"\x89PNG\r\n\x1a\n"
        assert dislodged_png != success_png

    def test_merged_convoy_chain_draws_both_fleet_markers(self):
        """A 2-fleet merged chain must render differently from a 1-fleet chain --
        otherwise the merge would be a no-op for the actual pixels shown."""
        units = {"ENGLAND": ["A LON", "F ENG", "F NTH"]}
        one_fleet_viz = {
            "ENGLAND": [{
                "type": "convoy", "unit": "F NTH", "convoyed_army_province": "LON",
                "target": "HOL", "convoy_chain": ["NTH"], "status": "success",
            }]
        }
        two_fleet_viz = {
            "ENGLAND": [{
                "type": "convoy", "unit": "F ENG", "convoyed_army_province": "LON",
                "target": "HOL", "convoy_chain": ["ENG", "NTH"], "status": "success",
            }]
        }
        one_fleet_png = Map.render_board_png_resolution(
            _SVG_PATH, units, one_fleet_viz, {"conflicts": []}, phase_info=_PHASE_INFO
        )
        two_fleet_png = Map.render_board_png_resolution(
            _SVG_PATH, units, two_fleet_viz, {"conflicts": []}, phase_info=_PHASE_INFO
        )
        assert one_fleet_png[:8] == b"\x89PNG\r\n\x1a\n"
        assert two_fleet_png != one_fleet_png

    def test_dislodged_convoy_fleet_renders_without_error(self):
        units = {"ENGLAND": ["A LON", "F ENG", "F NTH"]}
        viz = {
            "ENGLAND": [{
                "type": "convoy", "unit": "F ENG", "convoyed_army_province": "LON",
                "target": "HOL", "convoy_chain": ["ENG", "NTH"], "status": "dislodged",
            }]
        }
        png = Map.render_board_png_resolution(
            _SVG_PATH, units, viz, {"conflicts": []}, phase_info=_PHASE_INFO
        )
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 5000
