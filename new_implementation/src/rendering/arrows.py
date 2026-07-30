"""Generic arrow/line/circle drawing primitives, plus the status markers
(checkmark, X, star) built on top of them.

Split out of ``rendering.overlays`` during the V3 rendering split: that module
paired these low-level geometry primitives with the higher-level per-order-type
drawing functions (``_draw_movement_order``, ``_draw_support_order``, ...) that
call them, which pushed it past the ~800-line target. This module holds the
primitives; ``overlays.py`` imports them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from .antialias import DrawTarget

from .board import _convert_color_to_rgb
from .visualization_config import get_config

_viz_config = get_config()


# --------------------------------------------------------------------------
# Shared arrow geometry (Track I2)
#
# The four arrow variants below (straight, curved/convoy, dotted/retreat, bounce)
# each used to carry their own copy of the same ~14 lines of arrowhead
# trigonometry, differing only in typos' worth of detail. They now all resolve
# their geometry through ``_arrow_geometry`` and draw through ``_stroke_head``,
# so a change to how an arrowhead looks happens once.
#
# Two substantive changes came with the consolidation:
#
# 1. **Both ends are trimmed clear of the unit icons.** The old code pulled the
#    tip back a flat ``collision_offset = 4`` px and started the shaft at the
#    source unit's exact centre, so a 12px-wide shaft was drawn straight over
#    the 32px unit icon it came from and its head landed *inside* the icon it
#    pointed at. Both units are now legible and the head is visible.
# 2. **The head is barbed rather than a plain isoceles triangle.** The old head
#    was as wide as it was long (30 degree half-angle), which reads as a blunt
#    stub at map scale. A longer head with a notched back edge reads as an arrow.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ArrowGeometry:
    """Resolved arrow geometry in board coordinates.

    ``shaft_end`` is the notch at the *back* of the head, not the tip: the shaft
    stops there so it does not protrude through the barbs, and the two shapes
    still meet with no seam.
    """

    start: tuple[float, float]
    shaft_end: tuple[float, float]
    tip: tuple[float, float]
    #: Unit vector the head points along. For a straight arrow this is ``start`` ->
    #: ``tip``; for a curved one it is the tangent at the tip (see ``_reaimed``).
    direction: tuple[float, float]
    head: list[tuple[float, float]]
    head_casing: list[tuple[float, float]]
    # Head dimensions are carried so a curved arrow can rebuild its head along the
    # curve's tangent without re-reading (and possibly disagreeing with) the config.
    head_len: float
    half_width: float
    notch: float
    casing: float


def _head_polygon(
    tip: tuple[float, float],
    direction: tuple[float, float],
    length: float,
    half_width: float,
    notch: float,
) -> list[tuple[float, float]]:
    """Build a barbed arrowhead: tip, one barb, the notch, the other barb."""
    ux, uy = direction
    # Perpendicular to the direction of travel.
    vx, vy = -uy, ux
    tx, ty = tip
    back_x, back_y = tx - length * ux, ty - length * uy
    notch_x, notch_y = tx - (length - notch) * ux, ty - (length - notch) * uy
    return [
        (tx, ty),
        (back_x + half_width * vx, back_y + half_width * vy),
        (notch_x, notch_y),
        (back_x - half_width * vx, back_y - half_width * vy),
    ]


def _arrow_geometry(
    from_coord: tuple, to_coord: tuple, *, casing: float = 0.0
) -> ArrowGeometry | None:
    """Resolve arrow geometry between two province centres, or ``None`` if degenerate.

    Returns ``None`` when the two points are closer together than the clearances
    plus the head, which is a real case on this map -- some adjacent province
    centroids are only a few dozen pixels apart. The old code had no such guard
    and would happily emit a backwards-pointing head on a negative-length shaft.
    """
    specs = _viz_config.get_arrow_specs()
    base = specs["arrowhead_size"]
    head_len = specs.get("arrowhead_length", base * 1.35)
    half_width = specs.get("arrowhead_half_width", base * 0.5)
    notch = specs.get("arrowhead_notch", base * 0.38)
    clearance = specs.get("unit_clearance", 19)

    from_x, from_y = from_coord
    to_x, to_y = to_coord
    dx, dy = to_x - from_x, to_y - from_y
    span = math.hypot(dx, dy)
    if span <= 0:
        return None
    ux, uy = dx / span, dy / span

    # Trim both ends clear of the unit icons that sit on the province centres.
    # If the pair is too close to fit clearance + a head, shrink the clearances
    # proportionally rather than dropping the arrow -- a short arrow is still
    # information, an absent one is not.
    needed = clearance * 2 + head_len
    if span < needed:
        scale = max(0.0, (span - head_len) / (clearance * 2)) if span > head_len else 0.0
        clearance *= scale
    if span - clearance * 2 <= 0:
        return None

    start = (from_x + clearance * ux, from_y + clearance * uy)
    tip = (to_x - clearance * ux, to_y - clearance * uy)
    shaft_end = (tip[0] - (head_len - notch) * ux, tip[1] - (head_len - notch) * uy)
    head = _head_polygon(tip, (ux, uy), head_len, half_width, notch)
    # The casing is the same shape grown outwards, including past the tip, so it
    # reads as an outline rather than a shadow on one side.
    casing_tip = (tip[0] + casing * ux, tip[1] + casing * uy)
    head_casing = _head_polygon(
        casing_tip, (ux, uy), head_len + casing * 2, half_width + casing, notch
    )
    return ArrowGeometry(
        start, shaft_end, tip, (ux, uy), head, head_casing,
        head_len, half_width, notch, casing,
    )


def _reaimed(geo: ArrowGeometry, direction: tuple[float, float]) -> ArrowGeometry:
    """Return ``geo`` with its head rebuilt to point along ``direction``.

    Curved arrows (convoy, bounce) need this: the head must align with the tangent
    where the curve *arrives*, not with the straight chord between the two
    provinces, or it visibly sits askew on the end of the curve.
    """
    ux, uy = direction
    tip = geo.tip
    shaft_end = (tip[0] - (geo.head_len - geo.notch) * ux, tip[1] - (geo.head_len - geo.notch) * uy)
    casing_tip = (tip[0] + geo.casing * ux, tip[1] + geo.casing * uy)
    return replace(
        geo,
        direction=direction,
        shaft_end=shaft_end,
        head=_head_polygon(tip, direction, geo.head_len, geo.half_width, geo.notch),
        head_casing=_head_polygon(
            casing_tip, direction, geo.head_len + geo.casing * 2,
            geo.half_width + geo.casing, geo.notch,
        ),
    )


def _stroke_head(draw: DrawTarget, geo: ArrowGeometry, color: Any, casing_color: Any) -> None:
    """Draw the arrowhead casing then its fill."""
    draw.polygon(geo.head_casing, fill=casing_color)
    draw.polygon(geo.head, fill=color)


def _quadratic_points(
    p0: tuple[float, float],
    ctrl: tuple[float, float],
    p1: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    """Sample a quadratic bezier as a polyline of ``steps`` segments."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t ** 2
        points.append((a * p0[0] + b * ctrl[0] + c * p1[0], a * p0[1] + b * ctrl[1] + c * p1[1]))
    return points


def _normalized(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length else (1.0, 0.0)


def _draw_polyline(
    draw: DrawTarget, points: list[tuple[float, float]], color: Any, width: int, *, skip_alternate: bool = False
) -> None:
    """Stroke a polyline, optionally dropping every other segment to fake a dash."""
    for i in range(len(points) - 1):
        if skip_alternate and i % 2 == 0:
            continue
        draw.line([points[i], points[i + 1]], fill=color, width=width)


def _draw_curve_with_head(
    draw: DrawTarget,
    from_coord: tuple,
    to_coord: tuple,
    color: Any,
    width: int,
    *,
    bow: float,
    style: str = "solid",
    steps: int = 24,
) -> None:
    """Draw a bowed arrow: a quadratic curve bulging ``bow`` px sideways, plus a head.

    Shared by the convoy arrow and the bounce arrow, which previously carried two
    near-identical copies of this and differed only in ``bow`` and dash handling.
    """
    arrow_specs = _viz_config.get_arrow_specs()
    outline_width = arrow_specs.get("outline_width", 2)
    outline_color = (0, 0, 0)
    total_width = width + outline_width * 2

    geo = _arrow_geometry(from_coord, to_coord, casing=outline_width)
    if geo is None:
        return

    # Control point: perpendicular offset from the chord's midpoint.
    ux, uy = geo.direction
    mid_x = (geo.start[0] + geo.tip[0]) / 2
    mid_y = (geo.start[1] + geo.tip[1]) / 2
    ctrl = (mid_x - bow * uy, mid_y + bow * ux)

    # Aim the head along the curve's tangent at the tip, which for a quadratic
    # bezier is the direction from the control point to the end point.
    geo = _reaimed(geo, _normalized(geo.tip[0] - ctrl[0], geo.tip[1] - ctrl[1]))

    points = _quadratic_points(geo.start, ctrl, geo.shaft_end, steps)
    dashed = style == "dashed"
    for stroke_color, stroke_width in ((outline_color, total_width), (color, width)):
        _draw_polyline(draw, points, stroke_color, stroke_width, skip_alternate=dashed)
    _stroke_head(draw, geo, color, outline_color)


def _draw_bounce_arrow(draw: DrawTarget, from_coord: tuple, to_coord: tuple, color: str, width: int = 2) -> None:
    """Draw curved return arrow for bounced moves.

    Bows harder than a convoy arrow so a bounce reads as "came back" rather than as
    another route: the two are otherwise the same shape.
    """
    _draw_curve_with_head(draw, from_coord, to_coord, color, width, bow=40, steps=30)


def _draw_dotted_arrow(draw: DrawTarget, from_coord: tuple, to_coord: tuple, color: str, width: int = 2) -> None:
    """Draw dotted arrow for retreat orders"""
    arrow_specs = _viz_config.get_arrow_specs()
    outline_width = arrow_specs.get("outline_width", 2)
    outline_color = (0, 0, 0)  # Black
    total_width = width + outline_width * 2

    geo = _arrow_geometry(from_coord, to_coord, casing=outline_width)
    if geo is None:
        return

    # Long dashes rather than the config "dotted" style: a retreat has to stay
    # distinguishable from a convoy at a glance, and this is the only arrow that
    # uses this spacing.
    for stroke_color, stroke_width in ((outline_color, total_width), (color, width)):
        _draw_dashed_line(draw, geo.start[0], geo.start[1], geo.shaft_end[0], geo.shaft_end[1],
                          stroke_color, stroke_width, dash=8, gap=8)
    _stroke_head(draw, geo, color, outline_color)


def _draw_success_checkmark(draw: DrawTarget, coord: tuple, color: str | None = None) -> None:
    """Draw success checkmark at coordinate using config values.

    Merged with the former ``_draw_checkmark`` (a same-body legacy alias) during the
    V3 rendering split.
    """
    if color is None:
        color = _viz_config.get_color("success")
    x, y = coord
    marker_specs = _viz_config.get_marker_specs()
    size = marker_specs["status_indicator_size"]
    line_width = marker_specs["status_indicator_line_width"]
    rgb_color = _convert_color_to_rgb(color)

    # Draw checkmark (check shape)
    check_points = [
        (x - size, y),
        (x - size // 3, y + size // 2),
        (x + size, y - size // 2)
    ]
    draw.line([check_points[0], check_points[1], check_points[2]], fill=rgb_color, width=line_width)


def _draw_dislodged_marker(draw: DrawTarget, coord: tuple, color: str | None = None) -> None:
    """Draw the dislodged-order marker: a heavy hollow ring, distinct from both the
    green success checkmark and the failure X so a dislodged unit's order doesn't
    read as either a successful hold or a merely-failed one at a glance.
    """
    if color is None:
        color = _viz_config.get_color("failure")
    x, y = coord
    marker_specs = _viz_config.get_marker_specs()
    size = marker_specs["status_indicator_size"]
    line_width = marker_specs["status_indicator_line_width"]
    rgb_color = _convert_color_to_rgb(color)
    draw.ellipse([x - size, y - size, x + size, y + size], outline=rgb_color, width=line_width + 1)


def _draw_failure_x(draw: DrawTarget, coord: tuple, color: str | None = None) -> None:
    """Draw failure X marker at coordinate using config values.

    Merged with the former ``_draw_status_x`` (a same-body legacy alias) during the
    V3 rendering split.
    """
    if color is None:
        color = _viz_config.get_color("failure")
    x, y = coord
    marker_specs = _viz_config.get_marker_specs()
    size = marker_specs["status_indicator_size"]
    line_width = marker_specs["status_indicator_line_width"]
    rgb_color = _convert_color_to_rgb(color)

    # Draw X
    draw.line([x - size, y - size, x + size, y + size], fill=rgb_color, width=line_width)
    draw.line([x - size, y + size, x + size, y - size], fill=rgb_color, width=line_width)


def _draw_support_cut_indicator(draw: DrawTarget, from_coord: tuple, to_coord: tuple) -> None:
    """Draw red X through support line to indicate support was cut"""
    # Draw X at midpoint of support line
    mid_x = (from_coord[0] + to_coord[0]) / 2
    mid_y = (from_coord[1] + to_coord[1]) / 2
    _draw_failure_x(draw, (mid_x, mid_y), "red")


def _draw_star(draw: DrawTarget, coord: tuple, size: int, outline_color: str, fill_color: str) -> None:
    """Draw star shape for conflict markers"""
    x, y = coord

    # Create 5-pointed star
    outer_radius = size
    inner_radius = size * 0.4

    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2  # Start at top
        radius = outer_radius if i % 2 == 0 else inner_radius
        px = x + radius * math.cos(angle)
        py = y + radius * math.sin(angle)
        points.append((px, py))

    # Draw filled star
    if len(points) > 2:
        draw.polygon(points, fill=fill_color, outline=outline_color, width=2)


def _draw_arrow(
    draw: DrawTarget,
    from_coord: tuple,
    to_coord: tuple,
    color: str,
    width: int | None = None,
    style: str = "solid",
    status: str | None = None,
) -> None:
    """
    Unified arrow drawing function using config values.

    Args:
        draw: ImageDraw or ScaledDraw target (see rendering.antialias)
        from_coord: Start coordinate (x, y)
        to_coord: End coordinate (x, y)
        color: Arrow color (hex or named color)
        width: Line width (uses config if None)
        style: Line style ("solid", "dashed", "dotted")
        status: Optional status indicator ("success", "failure", "bounce")
    """
    # Get arrow specs from config
    arrow_specs = _viz_config.get_arrow_specs()
    line_width = width if width is not None else arrow_specs["line_width_primary"]
    outline_width = arrow_specs.get("outline_width", 2)  # Default 2px black outline

    # Convert color to RGB if needed
    rgb_color = _convert_color_to_rgb(color)
    outline_color = (0, 0, 0)  # Black

    geo = _arrow_geometry(from_coord, to_coord, casing=outline_width)
    if geo is None:
        # Coincident or near-coincident provinces: there is no direction to point in,
        # so draw nothing rather than an arbitrary stub.
        return

    total_width = line_width + outline_width * 2

    # Casing first, then the coloured stroke on top, for both the shaft and the head.
    for stroke_color, stroke_width in ((outline_color, total_width), (rgb_color, line_width)):
        _stroke_shaft(draw, geo, stroke_color, stroke_width, style)
    _stroke_head(draw, geo, rgb_color, outline_color)

    # Draw status indicators if provided (at the tip, which now sits clear of the unit)
    if status == "success":
        _draw_success_checkmark(draw, geo.tip)
    elif status == "failure":
        _draw_failure_x(draw, geo.tip)
    elif status == "bounce":
        # Draw bounce indicator (curved return arrow)
        bounce_color = _viz_config.get_color("failure")  # Use failure color for bounce
        _draw_bounce_arrow(draw, geo.tip, from_coord, bounce_color, arrow_specs["line_width_secondary"])


def _stroke_shaft(
    draw: DrawTarget, geo: ArrowGeometry, color: Any, width: int, style: str
) -> None:
    """Draw the shaft from ``geo.start`` to the head's notch in the requested style."""
    x1, y1 = geo.start
    x2, y2 = geo.shaft_end
    if style == "dashed":
        line_style = _viz_config.get_line_style("dashed")
        _draw_dashed_line(draw, x1, y1, x2, y2, color, width,
                          dash=line_style.get("dash", 4), gap=line_style.get("gap", 2))
    elif style == "dotted":
        line_style = _viz_config.get_line_style("dotted")
        _draw_dotted_line(draw, x1, y1, x2, y2, color, width,
                          dot=line_style.get("dot", 2), gap=line_style.get("gap", 2))
    else:  # solid
        draw.line([x1, y1, x2, y2], fill=color, width=width)


def _draw_circle(draw: DrawTarget, coord: tuple, color: str, width: int = 2, style: str = "solid") -> None:
    """Draw circle around coordinate (legacy - use _draw_circle_at_size for config-based sizing)"""
    x, y = coord
    radius = 15

    if style == "dashed":
        _draw_dashed_circle(draw, x, y, radius, color, width)
    else:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)


def _draw_circle_at_size(draw: DrawTarget, coord: tuple, color: str, diameter: int, width: int, style: str = "solid") -> None:
    """Draw circle at specified diameter using config values."""
    x, y = coord
    radius = diameter // 2
    rgb_color = _convert_color_to_rgb(color)

    if style == "dashed":
        _draw_dashed_circle(draw, x, y, radius, rgb_color, width)
    else:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                    outline=rgb_color, width=width)


def _draw_glowing_circle(draw: DrawTarget, coord: tuple, color: str, width: int = 4) -> None:
    """Draw glowing circle for build orders"""
    x, y = coord
    radius = 20

    # Draw outer glow (lighter color)
    glow_color = _lighten_color(color)
    draw.ellipse([x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2], outline=glow_color, width=width)

    # Draw inner circle
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)


def _draw_cross(draw: DrawTarget, coord: tuple, color: str, width: int = 4) -> None:
    """Draw red cross for destroy orders"""
    x, y = coord
    size = 15

    # Draw X
    draw.line([x - size, y - size, x + size, y + size], fill=color, width=width)
    draw.line([x - size, y + size, x + size, y - size], fill=color, width=width)


def _draw_curved_arrow(draw: DrawTarget, from_coord: tuple, to_coord: tuple, color: str, width: int = 2, style: str = "solid") -> None:
    """Draw curved arrow for convoy orders.

    Bowed rather than straight so a convoy route is distinguishable from the
    movement arrow that shares its endpoints.
    """
    _draw_curve_with_head(draw, from_coord, to_coord, color, width, bow=30, style=style, steps=20)


def _draw_dashed_line(draw: DrawTarget, x1: float, y1: float, x2: float, y2: float, color: Any, width: int, dash: int = 4, gap: int = 2) -> None:
    """Draw dashed line with configurable dash and gap lengths."""
    length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    if length == 0:
        return

    # Calculate unit vector
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length

    # Draw dashes
    current_length = 0
    while current_length < length:
        start_x = x1 + current_length * dx
        start_y = y1 + current_length * dy
        end_length = min(current_length + dash, length)
        end_x = x1 + end_length * dx
        end_y = y1 + end_length * dy

        draw.line([start_x, start_y, end_x, end_y], fill=color, width=width)
        current_length += dash + gap


def _draw_dotted_line(draw: DrawTarget, x1: float, y1: float, x2: float, y2: float, color: Any, width: int, dot: int = 2, gap: int = 2) -> None:
    """Draw dotted line with configurable dot and gap lengths."""
    length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    if length == 0:
        return

    # Calculate unit vector
    dx = (x2 - x1) / length
    dy = (y2 - y1) / length

    # Draw dots
    current_length = 0
    while current_length < length:
        dot_x = x1 + current_length * dx
        dot_y = y1 + current_length * dy
        # Draw small circle for dot
        radius = width // 2
        draw.ellipse([dot_x - radius, dot_y - radius, dot_x + radius, dot_y + radius],
                    fill=color, outline=color)
        current_length += dot + gap


def _draw_dashed_circle(draw: DrawTarget, x: float, y: float, radius: float, color: Any, width: int) -> None:
    """Draw dashed circle"""
    num_segments = 24
    dash_length = 2

    for i in range(0, num_segments, 2):
        start_angle = 2 * math.pi * i / num_segments
        end_angle = 2 * math.pi * (i + dash_length) / num_segments

        start_x = x + radius * math.cos(start_angle)
        start_y = y + radius * math.sin(start_angle)
        end_x = x + radius * math.cos(end_angle)
        end_y = y + radius * math.sin(end_angle)

        draw.line([start_x, start_y, end_x, end_y], fill=color, width=width)


def _lighten_color(color: str) -> str:
    """Lighten a color for glow effects"""
    # Simple color lightening - add white component
    if color.startswith("#"):
        # Convert hex to RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # Lighten by adding white
        r = min(255, int(r + (255 - r) * 0.5))
        g = min(255, int(g + (255 - g) * 0.5))
        b = min(255, int(b + (255 - b) * 0.5))

        return f"#{r:02x}{g:02x}{b:02x}"
    else:
        # For named colors, return a lighter version
        light_colors = {
            "red": "#ff8080",
            "blue": "#8080ff",
            "green": "#80ff80",
            "yellow": "#ffff80",
            "purple": "#ff80ff",
            "orange": "#ffc080",
            "brown": "#d4a574",
        }
        return light_colors.get(color.lower(), color)
