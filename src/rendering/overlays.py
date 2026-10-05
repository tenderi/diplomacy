"""The order overlay: what each order, and each outcome, looks like on the map.

**Every marker belongs to the unit that gave the order and is drawn at that unit.**
The overlay is drawn on the board the orders were *given* on, so the unit that gave
an order is still where the order started. (The old overlay put each status marker
on the target province's centre, which is where some *other* unit stands: a bounce's
✗ landed on the defender that held, and a won attack's ✓ on the unit it dislodged.)

Symbols (``docs/specs/visualization_spec.md`` is the full key):

- **Move**: solid arrow in the mover's colour. Two units ordered into each other's
  province are drawn side by side, not on top of each other.
- **Convoyed move**: the same arrow, curving through the convoying fleets.
- **Bounced**: the arrow stops at the border (half way) on a red bar.
- **Failed** (void, no convoy path): dashed, faded arrow with a red ✗ at its tip.
- **Hold**: an octagon round the unit.
- **Support**: a dashed line in the supporter's colour, never with an arrowhead.
  To hold: it ends in a ring round the supported unit. To move: it ends in a dot
  on the supported move's arrow.
- **Support cut**: a red ✗ across the line. **No effect** (void): the line grey.
- **Convoy**: a dashed ring round the fleet.
- **Retreat**: dashed arrow from the dislodged unit.
- **Dislodged**: a red ring round the unit, whatever its order did.
- **Standoff**: an orange burst in the province nobody got into.
- **Build**: the new unit, translucent, with a green ``+``. **Disband**: a red ✗.

Layering: order *lines* are drawn under the unit tokens (so a line running past a
unit goes behind it), status *markers* over them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from PIL import Image

from .antialias import DrawTarget, antialiased_overlay
from .arrows import (
    Point,
    burst,
    catmull_rom,
    draw_arrow,
    draw_bar,
    draw_cross,
    draw_polygon_outline,
    draw_ring,
    octagon,
    offset,
    path_length,
    point_at,
    stroke_path,
    trim,
)
from .board import (
    _cached,
    draw_units,
    get_dislodged_unit_coordinates,
    get_svg_province_coordinates,
    place_units,
    png_bytes,
    render_base,
)
from .cache import _map_cache
from .legend import add_footer
from .tokens import paste_token, rgb, token_radius
from .visualization_config import get_config

_cfg = get_config()

DrawOp = Callable[[DrawTarget], None]
ImageOp = Callable[[Image.Image], None]


@dataclass
class Scene:
    """Where things are on the board the overlay is drawn over."""

    centres: dict[str, Point]
    anchors: dict[str, Point]
    standing: set[str]
    dislodged_at: dict[str, Point]

    def unit_at(self, province: str, *, dislodged: bool = False) -> Point | None:
        if dislodged and province in self.dislodged_at:
            return self.dislodged_at[province]
        return self.centres.get(province)

    def has_token(self, province: str) -> bool:
        return province in self.standing


@dataclass
class Plan:
    """What to draw, by layer, and which legend keys that uses."""

    under: list[DrawOp] = field(default_factory=list)
    tokens: list[ImageOp] = field(default_factory=list)
    over: list[DrawOp] = field(default_factory=list)
    legend: set[str] = field(default_factory=set)


def build_scene(units: dict, svg_path: str) -> Scene:
    placed = place_units(units, svg_path)
    return Scene(
        centres=dict(get_svg_province_coordinates(svg_path)),
        anchors=dict(get_dislodged_unit_coordinates(svg_path)),
        standing={u.province for u in placed if not u.dislodged},
        dislodged_at={u.province: u.center for u in placed if u.dislodged},
    )


# --------------------------------------------------------------------------
# Style helpers
# --------------------------------------------------------------------------


def _casing() -> tuple[int, int, int]:
    return rgb(_cfg.get_color("casing"))


def _failure() -> tuple[int, int, int]:
    return rgb(_cfg.get_color("failure"))


def _faded(colour: tuple[int, ...]) -> tuple[int, int, int, int]:
    return (colour[0], colour[1], colour[2], _cfg.get_marker_specs()["faded_alpha"])


def _dash(style: str) -> tuple[float, float]:
    s = _cfg.get_line_style(style)
    return (s["dash"], s["gap"])


def _clearance() -> float:
    return token_radius() + _cfg.get_arrow_specs()["token_gap"]


def _arrow(draw: DrawTarget, points: list[Point], colour: Any, width: float, dash: tuple[float, float] | None = None) -> None:
    a = _cfg.get_arrow_specs()
    draw_arrow(draw, points, colour, width, casing=_casing(), casing_width=a["casing"],
               head_length=a["head_length"], head_half_width=a["head_half_width"],
               head_notch=a["head_notch"], dash=dash)


def _cross(draw: DrawTarget, at: Point, size: float | None = None) -> None:
    m = _cfg.get_marker_specs()
    draw_cross(draw, at, size or m["cross_size"], _failure(), m["cross_width"], casing=(255, 255, 255), casing_width=1.5)


def _dislodged_ring(draw: DrawTarget, at: Point) -> None:
    m = _cfg.get_marker_specs()
    draw_ring(draw, at, token_radius() + m["dislodged_gap"], _failure(), m["dislodged_width"],
              casing=(255, 255, 255), casing_width=1.5)


def _plus_badge(draw: DrawTarget, at: Point) -> None:
    br = _cfg.get_marker_specs()["build_badge_radius"]
    x, y = at
    draw.ellipse([x - br, y - br, x + br, y + br], fill=rgb(_cfg.get_color("build")), outline=(255, 255, 255), width=2)
    draw.line([(x - br * 0.55, y), (x + br * 0.55, y)], fill=(255, 255, 255), width=2.5)
    draw.line([(x, y - br * 0.55), (x, y + br * 0.55)], fill=(255, 255, 255), width=2.5)


# --------------------------------------------------------------------------
# Geometry of a move
# --------------------------------------------------------------------------


def _ordered_chain(origin: Point, fleets: list[tuple[str, Point]]) -> list[Point]:
    """The convoying fleets in route order: nearest-next from the army. The chain is
    always a path of adjacent seas, so walking it by distance recovers its order."""
    remaining = sorted(fleets)
    route: list[Point] = []
    here = origin
    while remaining:
        nxt = min(remaining, key=lambda f: (math.dist(here, f[1]), f[0]))
        remaining.remove(nxt)
        route.append(nxt[1])
        here = nxt[1]
    return route


def move_centreline(order: dict, scene: Scene, opposed: bool, *, dislodged_start: bool = False) -> list[Point] | None:
    """The untrimmed line a move is drawn along: unit to destination, through any
    convoying fleets, nudged sideways when it is opposed by the reverse move."""
    start = scene.unit_at(order["province"], dislodged=dislodged_start)
    end = scene.centres.get(order["target"])
    if start is None or end is None:
        return None
    chain = [(p, scene.centres[p]) for p in order.get("convoy_chain") or [] if p in scene.centres]
    if chain:
        steps = _cfg.get_arrow_specs()["convoy_steps_per_leg"]
        return catmull_rom([start, *_ordered_chain(start, chain), end], steps)
    line = [start, end]
    return offset(line, _cfg.get_arrow_specs()["opposed_offset"]) if opposed else line


def _end_clearance(scene: Scene, target: str) -> float:
    """Stop short of a token standing in the target; reach the centre of an empty one."""
    return _clearance() if scene.has_token(target) else 4.0


def _stop_distance(line: list[Point]) -> float:
    """How far along ``line`` a bounced move gets: the border, which is about half
    way along its last leg."""
    last_leg = math.dist(line[-2], line[-1]) if len(line) >= 2 else 0.0
    return path_length(line) - last_leg / 2


# --------------------------------------------------------------------------
# Planning each order
# --------------------------------------------------------------------------


def _plan_move(plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene, opposed: bool) -> None:
    line = move_centreline(order, scene, opposed)
    if line is None:
        return
    result = order.get("result", "pending")
    width = _cfg.get_arrow_specs()["move_width"]
    plan.legend.add("convoy" if order.get("convoy_chain") else "move")
    if result == "bounce":
        stop = _stop_distance(line)
        shaft = trim(line, _clearance(), path_length(line) - stop)
        if not shaft:
            return
        _, direction = point_at(line, stop)
        a = _cfg.get_arrow_specs()
        plan.under.append(lambda d: stroke_path(d, shaft, colour, width, casing=_casing(), casing_width=a["casing"]))
        plan.over.append(lambda d: draw_bar(d, shaft[-1], direction, _failure(), half_length=a["bounce_bar_half_length"],
                                            width=a["bounce_bar_width"], casing=_casing(), casing_width=a["casing"]))
        plan.legend.add("bounce")
        return
    path = trim(line, _clearance(), _end_clearance(scene, order["target"]))
    if not path:
        return
    if result in ("void", "no_convoy"):
        plan.under.append(lambda d: _arrow(d, path, _faded(colour), width - 1, dash=_dash("dashed")))
        plan.over.append(lambda d: _cross(d, path[-1]))
        plan.legend.add("failed")
    else:
        plan.under.append(lambda d: _arrow(d, path, colour, width))


def _plan_hold(plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene) -> None:
    at = scene.unit_at(order["province"])
    if at is None:
        return
    m = _cfg.get_marker_specs()
    shape = octagon(at, token_radius() + m["hold_gap"])
    plan.over.append(lambda d: draw_polygon_outline(d, shape, colour, m["hold_width"], casing=_casing(), casing_width=1))
    plan.legend.add("hold")


def _support_style(order: dict, colour: tuple[int, int, int]) -> tuple[Any, bool]:
    """(line colour, cased) for a support's outcome."""
    result = order.get("result", "pending")
    if result == "void":
        return rgb(_cfg.get_color("void")), False
    if result == "cut":
        return _faded(colour), True
    return colour, True


def _plan_support(
    plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene,
    move_lines: dict[tuple[str, str], list[Point]], ring_count: dict[str, int],
) -> None:
    start = scene.unit_at(order["province"])
    supported = order.get("supported_unit_province", "")
    supported_at = scene.unit_at(supported)
    if start is None or supported_at is None:
        return
    a = _cfg.get_arrow_specs()
    m = _cfg.get_marker_specs()
    line_colour, cased = _support_style(order, colour)
    width = a["support_width"]
    casing = dict(casing=_casing(), casing_width=1.0) if cased else {}
    result = order.get("result", "pending")

    if order.get("supported_action") == "move" and order.get("supported_target") in scene.centres:
        target = order["supported_target"]
        drawn = move_lines.get((supported, target))
        end = point_at(drawn, path_length(drawn) * 0.45)[0] if drawn else (
            (supported_at[0] + scene.centres[target][0]) / 2, (supported_at[1] + scene.centres[target][1]) / 2)
        dot_r = a["support_dot_radius"]
        path = trim([start, end], _clearance(), dot_r)
        if not path:
            return
        plan.under.append(lambda d: stroke_path(d, path, line_colour, width, dash=_dash("dashed"), **casing))
        def dot(d: DrawTarget) -> None:
            x, y = end
            d.ellipse([x - dot_r - 1, y - dot_r - 1, x + dot_r + 1, y + dot_r + 1], fill=_casing())
            d.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=line_colour)
        plan.under.append(dot)
        plan.legend.add("support_move")
    else:
        k = ring_count.get(supported, 0)
        ring_count[supported] = k + 1
        ring_r = token_radius() + m["support_ring_gap"] + 5 * k
        path = trim([start, supported_at], _clearance(), ring_r + m["support_ring_width"] / 2)
        if not path:
            return
        plan.under.append(lambda d: stroke_path(d, path, line_colour, width, dash=_dash("dashed"), **casing))
        plan.over.append(lambda d: draw_ring(d, supported_at, ring_r, line_colour, m["support_ring_width"], **casing))
        plan.legend.add("support_hold")

    if result == "cut":
        mark = point_at(path, min(path_length(path) * 0.35, 40))[0]
        plan.over.append(lambda d: _cross(d, mark, 7))
        plan.legend.add("cut")
    elif result == "void":
        plan.legend.add("void")


def _plan_convoy(
    plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene, drawn_chains: set[tuple[str, str]],
    army_moves: set[tuple[str, str]],
) -> None:
    at = scene.unit_at(order["province"])
    if at is None:
        return
    r = token_radius() + 5
    plan.over.append(lambda d: _dashed_ring(d, at, r, colour))
    plan.legend.add("convoy")
    key = (order["convoyed_army_province"], order["target"])
    if key in army_moves or key in drawn_chains:
        return
    # The army never ordered this move: show the route the fleets offered, thinly.
    drawn_chains.add(key)
    line = move_centreline({"province": key[0], "target": key[1], "convoy_chain": order["convoy_chain"]}, scene, False)
    if line is None:
        return
    path = trim(line, _clearance(), _end_clearance(scene, key[1]))
    if path:
        plan.under.append(lambda d: _arrow(d, path, _faded(colour), 3, dash=_dash("dotted")))


def _dashed_ring(d: DrawTarget, at: Point, r: float, colour: tuple[int, int, int]) -> None:
    n = 16
    for k in range(0, n, 2):
        a0, a1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        pts = [(at[0] + r * math.cos(a0 + (a1 - a0) * t / 4), at[1] + r * math.sin(a0 + (a1 - a0) * t / 4)) for t in range(5)]
        stroke_path(d, pts, colour, 3, casing=_casing(), casing_width=1)


def _plan_retreat(plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene) -> None:
    line = move_centreline(order, scene, False, dislodged_start=True)
    if line is None:
        return
    a = _cfg.get_arrow_specs()
    plan.legend.add("retreat")
    if order.get("result") == "disband":
        stop = _stop_distance(line)
        shaft = trim(line, _clearance(), path_length(line) - stop)
        if not shaft:
            return
        _, direction = point_at(line, stop)
        plan.under.append(lambda d: stroke_path(d, shaft, colour, a["retreat_width"], casing=_casing(),
                                                casing_width=a["casing"], dash=_dash("dashed")))
        plan.over.append(lambda d: draw_bar(d, shaft[-1], direction, _failure(), half_length=a["bounce_bar_half_length"],
                                            width=a["bounce_bar_width"], casing=_casing(), casing_width=a["casing"]))
        plan.legend.add("bounce")
        return
    path = trim(line, _clearance(), _end_clearance(scene, order["target"]))
    if path:
        plan.under.append(lambda d: _arrow(d, path, colour, a["retreat_width"], dash=_dash("dashed")))


def _plan_build(plan: Plan, order: dict, colour: tuple[int, int, int], scene: Scene) -> None:
    at = scene.centres.get(order["target"])
    if at is None:
        return
    kind = order.get("unit_kind", "A")
    alpha = _cfg.get_unit_specs()["build_alpha"]
    plan.tokens.append(lambda img: paste_token(img, at, kind, colour, alpha=alpha))
    r = token_radius()
    plan.over.append(lambda d: _plus_badge(d, (at[0] + r * 0.75, at[1] - r * 0.75)))
    plan.legend.add("build")


def _plan_destroy(plan: Plan, order: dict, scene: Scene) -> None:
    at = scene.unit_at(order["province"], dislodged=True)
    if at is None:
        return
    plan.over.append(lambda d: _cross(d, at, token_radius() * 0.75))
    plan.legend.add("disband")


def plan_orders(orders: dict[str, list[dict]], scene: Scene, standoffs: list[str] | None = None) -> Plan:
    """Turn the order dicts into layered drawing operations."""
    plan = Plan()
    entries = [(power, o) for power, power_orders in orders.items() for o in power_orders]
    army_moves = {(o["province"], o.get("target")) for _, o in entries if o.get("type") == "move" and o.get("via_convoy")}
    plain_moves = {(o["province"], o.get("target")) for _, o in entries
                   if o.get("type") == "move" and not o.get("convoy_chain")}
    move_lines: dict[tuple[str, str], list[Point]] = {}
    for _, o in entries:
        if o.get("type") == "move":
            opposed = (o.get("target"), o["province"]) in plain_moves and not o.get("convoy_chain")
            line = move_centreline(o, scene, opposed)
            if line is not None:
                move_lines[(o["province"], o["target"])] = line
    ring_count: dict[str, int] = {}
    drawn_chains: set[tuple[str, str]] = set()

    for power, o in sorted(entries, key=lambda e: (e[1].get("type") != "move", e[0])):
        colour = rgb(_cfg.get_power_color(power))
        kind = o.get("type")
        if kind == "move":
            opposed = (o.get("target"), o["province"]) in plain_moves and not o.get("convoy_chain")
            _plan_move(plan, o, colour, scene, opposed)
        elif kind == "hold":
            _plan_hold(plan, o, colour, scene)
        elif kind == "support":
            _plan_support(plan, o, colour, scene, move_lines, ring_count)
        elif kind == "convoy":
            _plan_convoy(plan, o, colour, scene, drawn_chains, army_moves)
        elif kind == "retreat":
            _plan_retreat(plan, o, colour, scene)
        elif kind == "build":
            _plan_build(plan, o, colour, scene)
        elif kind == "destroy":
            _plan_destroy(plan, o, scene)
        if o.get("dislodged") or o.get("result") == "dislodged":
            at = scene.unit_at(o.get("province", ""))
            if at is not None:
                plan.over.append(lambda d, at=at: _dislodged_ring(d, at))
                plan.legend.add("dislodged")

    for province in standoffs or []:
        at = scene.centres.get(province)
        if at is None:
            continue
        if scene.has_token(province):
            at = scene.anchors.get(province, at)
        r = _cfg.get_marker_specs()["standoff_radius"]
        shape = burst(at, r, r * 0.5)
        plan.over.append(lambda d, shape=shape: d.polygon(shape, fill=rgb(_cfg.get_color("standoff")), outline=_casing()))
        plan.legend.add("standoff")
    return plan


def _render(
    svg_path: str,
    units: dict,
    orders: dict,
    standoffs: list[str],
    phase_info: dict | None,
    supply_center_control: dict | None,
    color_only_supply_centers: bool,
    title: str,
) -> Image.Image:
    bg = render_base(svg_path, units, supply_center_control, color_only_supply_centers)
    scene = build_scene(units, svg_path)
    plan = plan_orders(orders, scene, standoffs)
    with antialiased_overlay(bg) as under:
        for op in plan.under:
            op(under)
    placed = place_units(units, svg_path)
    draw_units(bg, placed)
    for token_op in plan.tokens:
        token_op(bg)
    with antialiased_overlay(bg) as over:
        for op in plan.over:
            op(over)
    if any(u.dislodged for u in placed):
        plan.legend.add("dislodged_unit")
    return add_footer(bg, phase_info, plan.legend, sorted({u.power for u in placed}), title_prefix=title)


def render_board_png_orders(
    svg_path: str,
    units: dict,
    orders: dict,
    phase_info: dict | None = None,
    output_path: str | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> bytes:
    """The board plus every submitted order, before adjudication: every order is
    drawn as given, whatever result its dict carries."""
    if svg_path is None:
        raise ValueError("svg_path must not be None")
    pending = {
        power: [{**o, "result": "pending", "status": "pending", "dislodged": False} for o in power_orders]
        for power, power_orders in orders.items()
    }
    cache_key = _map_cache._generate_cache_key(
        svg_path, units, phase_info, orders=pending,
        supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers,
    )
    cached = _cached(cache_key, output_path)
    if cached is not None:
        return cached
    image = _render(svg_path, units, pending, [], phase_info, supply_center_control,
                    color_only_supply_centers, "Orders")
    img_bytes = png_bytes(image, output_path)
    _map_cache.put(cache_key, img_bytes)
    return img_bytes


def render_board_png_resolution(
    svg_path: str,
    units: dict,
    orders: dict,
    resolution_data: dict,
    phase_info: dict | None = None,
    output_path: str | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> bytes:
    """The orders of a processed turn with their outcomes, drawn on the board they
    were given on (``units`` is that board).

    ``resolution_data``: ``{"conflicts": [{"province": "BUR", "result": "standoff"}]}``
    -- the provinces to mark with a standoff burst (``order_overlay.standoff_provinces``).
    """
    if svg_path is None:
        raise ValueError("svg_path must not be None")
    standoffs = sorted({c["province"] for c in resolution_data.get("conflicts", []) if c.get("result") == "standoff"})
    cache_key = _map_cache._generate_cache_key(
        svg_path, units, phase_info, orders=orders,
        supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers,
        extra={"standoffs": standoffs},
    )
    cached = _cached(cache_key, output_path)
    if cached is not None:
        return cached
    image = _render(svg_path, units, orders, standoffs, phase_info, supply_center_control,
                    color_only_supply_centers, "Orders and results")
    img_bytes = png_bytes(image, output_path)
    _map_cache.put(cache_key, img_bytes)
    return img_bytes


__all__ = [
    "Plan",
    "Scene",
    "build_scene",
    "move_centreline",
    "plan_orders",
    "render_board_png_orders",
    "render_board_png_resolution",
]
