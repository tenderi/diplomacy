"""A fleet on a split-coast province is drawn on its coast (STP/NC, STP/SC, SPA/NC,
SPA/SC, BUL/EC, BUL/SC), not at the province's one spot: the coast decides where the
fleet can go, so the map must show it."""
from __future__ import annotations

from pathlib import Path

import pytest

from engine.types import Build, Hold, Location, Move, SupportMove, UnitKind
from rendering import board
from rendering.board import get_dislodged_unit_coordinates, get_svg_province_coordinates, render_board_png
from rendering.cache import _map_cache
from rendering.order_overlay import order_to_viz
from rendering.overlays import build_scene
from rendering.view_adapter import retreat_options_for_render, units_for_render

pytestmark = pytest.mark.map

SVG = str(Path(__file__).parent.parent / "maps" / "standard.svg")
PHASE = {"turn": 5, "year": 1903, "season": "Fall", "phase": "Movement", "phase_code": "F1903M"}
COASTS = ["STP/NC", "STP/SC", "SPA/NC", "SPA/SC", "BUL/EC", "BUL/SC"]


@pytest.fixture(autouse=True)
def _cold_cache():
    _map_cache.clear()
    yield
    _map_cache.clear()


def _loc(prov: str, coast: str | None = None) -> Location:
    return Location(prov, coast)


def test_every_coast_has_its_own_position_distinct_from_its_province():
    coords = get_svg_province_coordinates(SVG)
    for coast in COASTS:
        assert coords[coast] != coords[coast.split("/")[0]]
    for province in ("STP", "SPA", "BUL"):
        assert len({coords[c] for c in COASTS if c.startswith(province)}) == 2


@pytest.mark.parametrize("coast", COASTS)
def test_place_units_puts_a_fleet_on_its_coast(coast):
    [standing] = board.place_units({"RUSSIA": [f"F {coast}"]}, SVG)
    assert standing.center == get_svg_province_coordinates(SVG)[coast]
    [dislodged] = board.place_units({"RUSSIA": [f"F DISLODGED_{coast}"]}, SVG)
    assert dislodged.center == get_dislodged_unit_coordinates(SVG)[coast]


def test_fleets_on_different_coasts_render_differently():
    north = render_board_png(SVG, {"RUSSIA": ["F STP/NC"]}, phase_info=PHASE)
    south = render_board_png(SVG, {"RUSSIA": ["F STP/SC"]}, phase_info=PHASE)
    assert north != south


def test_retreat_options_end_on_the_coast():
    units = {"FRANCE": ["F DISLODGED_MAO"]}
    one = render_board_png(SVG, units, phase_info=PHASE, retreat_options={"MAO": ["SPA/NC"]})
    other = render_board_png(SVG, units, phase_info=PHASE, retreat_options={"MAO": ["SPA/SC"]})
    assert one != other


def test_adapter_keeps_the_coast():
    view = {
        "units_by_power": {"RUSSIA": [{"kind": "F", "power": "RUSSIA", "location": "STP/NC"}]},
        "dislodged": [{"unit": {"kind": "F", "power": "FRANCE", "location": "MAO"},
                       "retreats": ["SPA/SC", "SPA/NC", "POR"]}],
    }
    assert units_for_render(view) == {"RUSSIA": ["F STP/NC"], "FRANCE": ["F DISLODGED_MAO"]}
    assert retreat_options_for_render(view) == {"MAO": ["POR", "SPA/NC", "SPA/SC"]}


def test_adapter_keeps_a_dislodged_fleets_coast():
    view = {"dislodged": [{"unit": {"kind": "F", "power": "RUSSIA", "location": "STP/NC"}}]}
    assert units_for_render(view) == {"RUSSIA": ["F DISLODGED_STP/NC"]}


def test_orders_name_a_fleets_coast_so_the_arrow_starts_and_ends_there():
    move = order_to_viz(Move("RUSSIA", _loc("STP", "NC"), _loc("STP", "SC")))
    assert (move["province"], move["target"]) == ("STP/NC", "STP/SC")
    build = order_to_viz(Build("RUSSIA", _loc("BUL", "EC"), UnitKind.FLEET))
    assert (build["province"], build["target"]) == ("BUL/EC", "BUL/EC")
    support = order_to_viz(SupportMove("ENGLAND", _loc("MAO"), _loc("POR"), _loc("SPA", "SC")))
    assert support["supported_target"] == "SPA/SC"
    assert order_to_viz(Hold("RUSSIA", _loc("STP")))["province"] == "STP"


def test_scene_finds_a_fleet_named_by_its_bare_province():
    scene = build_scene({"RUSSIA": ["F STP/NC"]}, SVG)
    assert scene.unit_at("STP/NC") == scene.centres["STP/NC"]
    assert scene.unit_at("STP") == scene.centres["STP/NC"]
    assert build_scene({}, SVG).unit_at("STP") == scene.centres["STP"]


def _move(province: str, target: str) -> dict:
    return {"type": "move", "province": province, "target": target, "convoy_chain": [], "via_convoy": False,
            "result": "pending", "status": "pending", "dislodged": False}


def test_head_to_head_is_seen_across_a_coast():
    from unittest.mock import patch

    from rendering import overlays

    scene = build_scene({"RUSSIA": ["F STP/NC"], "TURKEY": ["A BOT"]}, SVG)
    seen = []
    real = overlays.move_centreline

    def spy(order, scene, opposed, **kw):
        seen.append((order["province"], opposed))
        return real(order, scene, opposed, **kw)

    orders = {"RUSSIA": [_move("STP/NC", "BOT")], "TURKEY": [_move("BOT", "STP")]}
    with patch.object(overlays, "move_centreline", spy):
        overlays.plan_orders(orders, scene)
    assert sorted(set(seen)) == [("BOT", True), ("STP/NC", True)]


def test_support_dot_sits_on_a_move_into_a_coast():
    from unittest.mock import patch

    from rendering import overlays

    scene = build_scene({"RUSSIA": ["F BOT", "A FIN"]}, SVG)
    support = {"type": "support", "province": "FIN", "supported_action": "move", "supported_unit_province": "BOT",
               "supported_target": "STP", "result": "pending", "status": "pending", "dislodged": False}
    orders = {"RUSSIA": [_move("BOT", "STP/NC"), support]}
    calls = []
    real = overlays.point_at

    def spy(path, dist):
        calls.append(dist)
        return real(path, dist)

    with patch.object(overlays, "point_at", spy):
        overlays.plan_orders(orders, scene)
    assert len(calls) == 1


def test_scene_finds_a_dislodged_fleet_named_by_its_bare_province():
    scene = build_scene({"RUSSIA": ["F DISLODGED_STP/NC"]}, SVG)
    assert scene.unit_at("STP", dislodged=True) == get_dislodged_unit_coordinates(SVG)["STP/NC"]
