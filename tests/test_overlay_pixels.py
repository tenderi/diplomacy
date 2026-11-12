"""Pixels of the overlay's small marks, drawn on a plain board (issue #411, DI2).

``tests/test_order_symbols.py`` spies on drawing calls; this file renders the planned
operations onto a flat grey canvas and reads the pixels, so a mark that is drawn in
the wrong place, at the wrong size, or upside down, fails here. The canvas is grey so
the white casings show. Nothing goes through the map cache.
"""
from __future__ import annotations

import math
from typing import Callable

import pytest
from PIL import Image, ImageColor

from rendering import legend
from rendering.antialias import DrawTarget, antialiased_overlay
from rendering.arrows import burst
from rendering.map import Map
from rendering.overlays import Plan, Scene, _dashed_ring, _plus_badge, plan_orders
from rendering.tokens import token_radius
from rendering.visualization_config import get_config

pytestmark = [pytest.mark.unit, pytest.mark.map]

_cfg = get_config()
BG = (90, 90, 90)
WHITE = (255, 255, 255)
SIZE = (320, 300)
Colour = tuple[int, int, int]


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    Map.clear_map_cache()


def colour(name: str) -> Colour:
    r, g, b = ImageColor.getrgb(_cfg.get_color(name))[:3]
    return (r, g, b)


def power(name: str) -> Colour:
    r, g, b = ImageColor.getrgb(_cfg.get_power_color(name))[:3]
    return (r, g, b)


def canvas() -> Image.Image:
    return Image.new("RGBA", SIZE, BG + (255,))


def draw(plan: Plan) -> Image.Image:
    """The plan's layers in the renderer's order: lines, tokens, markers."""
    img = canvas()
    with antialiased_overlay(img) as under:
        for op in plan.under:
            op(under)
    for token_op in plan.tokens:
        token_op(img)
    with antialiased_overlay(img) as over:
        for op in plan.over:
            op(over)
    return img


def scene(centres: dict[str, tuple[float, float]], standing: set[str] | None = None) -> Scene:
    return Scene(centres=centres, anchors={}, standing=set(centres) if standing is None else standing, dislodged_at={})


def near(px: tuple[int, ...], want: Colour, tol: int = 12) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px[:3], want))


def at(img: Image.Image, x: float, y: float) -> tuple[int, ...]:
    return img.getpixel((round(x), round(y)))  # type: ignore[return-value]


def polar(c: tuple[float, float], r: float, deg: float) -> tuple[float, float]:
    return (c[0] + r * math.cos(math.radians(deg)), c[1] + r * math.sin(math.radians(deg)))


def bbox_of(img: Image.Image, want: Colour, box: tuple[int, int, int, int] | None = None,
            tol: int = 12) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1), inclusive, of the pixels near ``want`` (inside ``box``)."""
    x0, y0, x1, y1 = box or (0, 0, img.width, img.height)
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if near(img.getpixel((x, y)), want, tol):  # type: ignore[arg-type]
                xs.append(x)
                ys.append(y)
    assert xs, f"no pixel near {want}"
    return min(xs), min(ys), max(xs), max(ys)


def ink(img: Image.Image, bg: Colour = BG, tol: int = 30) -> list[tuple[int, int]]:
    return [(x, y) for y in range(img.height) for x in range(img.width)
            if not near(img.getpixel((x, y)), bg, tol)]  # type: ignore[arg-type]


# -- the build badge ----------------------------------------------------------


def test_build_badge_is_a_green_disc_up_and_right_of_the_token() -> None:
    plan = plan_orders({"england": [{"type": "build", "target": "LON", "unit_kind": "A"}]}, scene({"LON": (100, 150)}))
    assert len(plan.tokens) == 1 and plan.legend == {"build"}
    img = draw(plan)
    r, br = token_radius(), _cfg.get_marker_specs()["build_badge_radius"]
    cx, cy = 100 + r * 0.75, 150 - r * 0.75
    x0, y0, x1, y1 = bbox_of(img, colour("build"), (int(cx - 20), int(cy - 20), int(cx + 20), int(cy + 20)))
    assert y1 - y0 >= br and x1 - x0 >= br  # not squashed to a line
    assert abs((x0 + x1) / 2 - cx) <= 1 and abs((y0 + y1) / 2 - cy) <= 1
    assert near(at(img, cx + 3.5, cy + 3.5), colour("build"), 20)
    assert near(at(img, cx - 3.5, cy - 3.5), colour("build"), 20)


def _badge(fn: Callable[[DrawTarget, tuple[float, float]], None]) -> Image.Image:
    img = canvas()
    with antialiased_overlay(img) as d:
        fn(d, (160, 150))
    return img


@pytest.mark.parametrize("fn", [_plus_badge, legend._plus_badge], ids=["overlay", "legend"])
def test_plus_badge_geometry(fn: Callable[[DrawTarget, tuple[float, float]], None]) -> None:
    br = _cfg.get_marker_specs()["build_badge_radius"]
    img = _badge(fn)
    # The green disc is centred on the point and as tall as it is wide.
    x0, y0, x1, y1 = bbox_of(img, colour("build"))
    assert abs((x0 + x1) / 2 - 160) <= 0.6 and abs((y0 + y1) / 2 - 150) <= 0.6
    assert br - 3 <= (y1 - y0) / 2 <= br and br - 3 <= (x1 - x0) / 2 <= br
    # The white plus: arms reach about 0.55 * radius (4.4 px, plus the stroke) from the centre.
    for dx, dy in ((3, 0), (-3, 0), (0, 3), (0, -3), (0, 0)):
        assert near(at(img, 160 + dx, 150 + dy), WHITE, 30), (dx, dy)
    for dx, dy in ((5, 0), (-6, 0), (0, 5), (0, -6), (3.5, 3.5), (-3.5, 3.5), (3.5, -3.5), (-3.5, -3.5)):
        assert near(at(img, 160 + dx, 150 + dy), colour("build"), 35), (dx, dy)
    assert near(at(img, 160 + br + 4, 150), BG, 20)


# -- the support dot ----------------------------------------------------------


def _support(result: str = "pending", action: str = "move", target: str = "BBB") -> dict:
    o = {"type": "support", "province": "SUP", "supported_unit_province": "AAA", "supported_action": action,
         "result": result}
    if action == "move":
        o["supported_target"] = target
    return o


def test_support_dot_sits_on_the_midpoint_when_the_move_is_not_ordered() -> None:
    sc = scene({"SUP": (150, 30), "AAA": (60, 150), "BBB": (240, 150)})
    plan = plan_orders({"england": [_support()]}, sc)
    assert plan.legend == {"support_move"}
    img = draw(plan)
    dot_r = _cfg.get_arrow_specs()["support_dot_radius"]
    mid = (150.0, 150.0)
    # The dashed line comes from above at x == 150, 3 px wide: look only off it.
    left = bbox_of(img, power("england"), (130, 130, 148, 170))
    right = bbox_of(img, power("england"), (153, 130, 170, 170))
    assert abs(left[0] - (mid[0] - dot_r)) <= 1.5 and abs(right[2] - (mid[0] + dot_r)) <= 1.5
    assert abs((left[1] + left[3]) / 2 - mid[1]) <= 1.5 and abs((right[1] + right[3]) / 2 - mid[1]) <= 1.5
    assert near(at(img, *mid), power("england"))
    # The casing one pixel out, then the board.
    assert near(at(img, mid[0] + dot_r + 0.5, mid[1]), colour("casing"), 60)
    assert near(at(img, mid[0] - dot_r - 0.5, mid[1]), colour("casing"), 60)
    assert near(at(img, mid[0], mid[1] + dot_r + 0.5), colour("casing"), 60)
    assert near(at(img, mid[0] + dot_r + 3, mid[1]), BG, 20)
    assert near(at(img, mid[0] - dot_r - 3, mid[1] + 3), BG, 20)
    assert near(at(img, mid[0], mid[1] + dot_r + 3), BG, 20)  # nothing continues below the dot


def test_support_dot_sits_on_the_drawn_move_when_it_is_ordered() -> None:
    sc = scene({"SUP": (148, 30), "AAA": (40, 200), "BBB": (280, 200)})
    orders = {"england": [_support()], "france": [{"type": "move", "province": "AAA", "target": "BBB"}]}
    img = draw(plan_orders(orders, sc))
    dot_r = _cfg.get_arrow_specs()["support_dot_radius"]
    want = 40 + 240 * 0.45  # 45% along the drawn line (x = 148), not half way (x = 160)
    # The support's dashed line comes in from above at x == 148: look only off it.
    left = bbox_of(img, power("england"), (130, 180, 145, 220))
    right = bbox_of(img, power("england"), (151, 180, 170, 220))
    assert abs(left[0] - (want - dot_r)) <= 1.5 and abs(right[2] - (want + dot_r)) <= 1.5
    assert abs((left[1] + left[3]) / 2 - 200) <= 1.5 and abs((right[1] + right[3]) / 2 - 200) <= 1.5


# -- the support ring ---------------------------------------------------------


def test_support_to_hold_ends_in_a_ring_round_the_supported_unit() -> None:
    sc = scene({"SUP": (150, 30), "AAA": (150, 200)})
    plan = plan_orders({"england": [_support(action="hold")]}, sc)
    assert plan.legend == {"support_hold"}
    img = draw(plan)
    m = _cfg.get_marker_specs()
    ring_r = token_radius() + m["support_ring_gap"]
    for deg in (0, 45, 90, 135, 180, 225, 315):  # not 270: the dashed line comes in from above
        assert near(at(img, *polar((150, 200), ring_r, deg)), power("england")), deg
        assert near(at(img, *polar((150, 200), ring_r + m["support_ring_width"] / 2 + 4, deg)), BG, 20), deg
        assert near(at(img, *polar((150, 200), ring_r - m["support_ring_width"] / 2 - 4, deg)), BG, 20), deg
    assert near(at(img, 150, 200), BG, 5)


def test_two_supports_to_hold_the_same_unit_get_rings_five_pixels_apart() -> None:
    sc = scene({"SUP": (150, 30), "SUQ": (30, 200), "AAA": (200, 200)})
    sup2 = {**_support(action="hold"), "province": "SUQ"}
    img = draw(plan_orders({"england": [_support(action="hold")], "france": [sup2]}, sc))
    r0 = token_radius() + _cfg.get_marker_specs()["support_ring_gap"]
    # sorted by power: england's ring is the inner one, france's 5 px further out
    assert near(at(img, *polar((200, 200), r0, 90)), power("england"))
    assert near(at(img, *polar((200, 200), r0 + 5, 90)), power("france"))


# -- the convoy ring ----------------------------------------------------------


def test_convoy_ring_is_a_ring_of_arcs() -> None:
    sc = scene({"SEA": (150, 150)})
    order = {"type": "convoy", "province": "SEA", "convoyed_army_province": "AAA", "target": "BBB",
             "convoy_chain": []}
    img = draw(plan_orders({"england": [order]}, sc))
    r = token_radius() + 5
    assert near(at(img, 150, 150), BG, 5)  # none at the centre
    for j in range(8):
        assert near(at(img, *polar((150, 150), r, 11.25 + 45 * j)), power("england"), 45), j
        assert near(at(img, *polar((150, 150), r, 33.75 + 45 * j)), BG, 20), j
        assert near(at(img, *polar((150, 150), r + 6, 11.25 + 45 * j)), BG, 20), j
        assert near(at(img, *polar((150, 150), r - 6, 11.25 + 45 * j)), BG, 20), j


def test_dashed_ring_arc_ends_are_where_the_sixteenths_are() -> None:
    img = canvas()
    with antialiased_overlay(img) as d:
        _dashed_ring(d, (150, 150), 40, (200, 0, 0))
    red = (200, 0, 0)
    # arc k=0 spans 0 .. 22.5 degrees; the gap 22.5 .. 45
    assert near(at(img, *polar((150, 150), 40, 5)), red, 20) and near(at(img, *polar((150, 150), 40, 17)), red, 20)
    assert near(at(img, *polar((150, 150), 40, 28)), BG, 20) and near(at(img, *polar((150, 150), 40, 40)), BG, 20)
    assert near(at(img, *polar((150, 150), 40, 48)), red, 20) and near(at(img, *polar((150, 150), 40, 66)), red, 20)
    # Every inked pixel is within the stroke's width of radius 40 ...
    pixels = ink(img)
    assert all(abs(math.dist(p, (150, 150)) - 40) <= 4 for p in pixels)
    # ... and the ring goes all the way round.
    octants = {int((math.degrees(math.atan2(y - 150, x - 150)) % 360) // 45) for x, y in pixels}
    assert octants == set(range(8))


# -- the standoff burst -------------------------------------------------------


def test_standoff_burst_has_its_inner_radius() -> None:
    sc = scene({"BUR": (150, 150)}, standing=set())
    plan = plan_orders({}, sc, standoffs=["BUR"])
    assert plan.legend == {"standoff"}
    img = draw(plan)
    outer = _cfg.get_marker_specs()["standoff_radius"]
    inner = outer * 0.5
    c = (150.0, 150.0)
    star = colour("standoff")
    for k in range(8):  # outer points at -90 + 45k, inner vertices between them
        assert near(at(img, *polar(c, outer - 4, -90 + 45 * k)), star, 40), k
        assert near(at(img, *polar(c, outer + 3, -90 + 45 * k)), BG, 20), k
        valley = -67.5 + 45 * k
        assert near(at(img, *polar(c, inner - 2.5, valley)), star, 40), k
        assert near(at(img, *polar(c, inner + 3, valley)), BG, 30), k
    assert near(at(img, *c), star)


def test_burst_alternates_outer_and_inner_vertices() -> None:
    pts = burst((10, 20), 15, 7.5)
    assert [round(math.dist(p, (10, 20)), 6) for p in pts] == [15, 7.5] * 8
    assert pts[0] == pytest.approx((10, 5))


def test_standoff_on_an_occupied_province_is_drawn_at_its_anchor() -> None:
    sc = Scene(centres={"BUR": (100, 100)}, anchors={"BUR": (220, 200)}, standing={"BUR"}, dislodged_at={})
    img = draw(plan_orders({}, sc, standoffs=["BUR"]))
    assert near(at(img, 220, 200), colour("standoff"))
    assert near(at(img, 100, 100), BG, 5)


# -- plan_orders --------------------------------------------------------------


def test_opposed_moves_are_drawn_side_by_side() -> None:
    sc = scene({"AAA": (40, 150), "BBB": (280, 150)})
    orders = {"england": [{"type": "move", "province": "AAA", "target": "BBB"}],
              "france": [{"type": "move", "province": "BBB", "target": "AAA"}]}
    img = draw(plan_orders(orders, sc))
    off = _cfg.get_arrow_specs()["opposed_offset"]
    # England goes east: to its right is south (y down). France goes west: its right is north.
    assert near(at(img, 160, 150 + off), power("england"))
    assert near(at(img, 160, 150 - off), power("france"))
    assert near(at(img, 160, 150), BG, 20)


def test_a_lone_move_is_not_offset() -> None:
    sc = scene({"AAA": (40, 150), "BBB": (280, 150)})
    img = draw(plan_orders({"england": [{"type": "move", "province": "AAA", "target": "BBB"}]}, sc))
    assert near(at(img, 160, 150), power("england"))
    assert near(at(img, 160, 150 + _cfg.get_arrow_specs()["opposed_offset"]), BG, 20)


def test_a_dislodged_unit_gets_a_red_ring_whatever_its_order() -> None:
    sc = scene({"AAA": (150, 150)})
    plan = plan_orders({"england": [{"type": "hold", "province": "AAA", "dislodged": True}]}, sc)
    assert plan.legend == {"hold", "dislodged"}
    img = draw(plan)
    r = token_radius() + _cfg.get_marker_specs()["dislodged_gap"]
    for deg in (0, 90, 180, 270):
        assert near(at(img, *polar((150, 150), r, deg)), colour("failure"), 30), deg


def test_dislodged_result_alone_marks_the_ring() -> None:
    plan = plan_orders({"england": [{"type": "move", "province": "AAA", "target": "BBB", "result": "dislodged"}]},
                       scene({"AAA": (40, 150), "BBB": (280, 150)}))
    assert plan.legend == {"move", "dislodged"}


def test_moves_are_planned_before_other_orders() -> None:
    sc = scene({"AAA": (40, 150), "BBB": (280, 150), "CCC": (150, 40)})
    orders = {"russia": [{"type": "move", "province": "AAA", "target": "BBB"}],
              "england": [{"type": "hold", "province": "CCC"}, {"type": "move", "province": "CCC", "target": "BBB"}]}
    plan = plan_orders(orders, sc)
    assert len(plan.under) == 2 and len(plan.over) == 1  # two arrows under, the hold octagon over
    assert plan.legend == {"move", "hold"}


def test_legend_keys_follow_the_orders_drawn() -> None:
    sc = scene({"AAA": (40, 150), "BBB": (280, 150), "SEA": (150, 60), "SUP": (150, 250)})
    orders = {"england": [
        {"type": "move", "province": "AAA", "target": "BBB", "convoy_chain": ["SEA"], "via_convoy": True},
        {"type": "convoy", "province": "SEA", "convoyed_army_province": "AAA", "target": "BBB", "convoy_chain": ["SEA"]},
        {**_support(result="cut"), "supported_unit_province": "AAA"},
    ]}
    assert plan_orders(orders, sc).legend == {"convoy", "support_move", "cut"}
    assert plan_orders({"england": [_support(result="void", action="hold")]}, sc).legend == {"support_hold", "void"}
    failed = {"england": [{"type": "move", "province": "AAA", "target": "BBB", "result": "no_convoy"}]}
    assert plan_orders(failed, sc).legend == {"move", "failed"}
    bounce = {"england": [{"type": "move", "province": "AAA", "target": "BBB", "result": "bounce"}]}
    assert plan_orders(bounce, sc).legend == {"move", "bounce"}


def test_destroy_draws_a_cross_and_retreat_is_dashed() -> None:
    sc = Scene(centres={"AAA": (60, 150), "BBB": (260, 150)}, anchors={}, standing=set(),
               dislodged_at={"AAA": (60, 150)})
    plan = plan_orders({"england": [{"type": "destroy", "province": "AAA"}]}, sc)
    assert plan.legend == {"disband"}
    assert near(at(draw(plan), 60, 150), colour("failure"), 60)
    plan = plan_orders({"england": [{"type": "retreat", "province": "AAA", "target": "BBB"}]}, sc)
    assert plan.legend == {"retreat"}
