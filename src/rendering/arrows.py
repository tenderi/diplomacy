"""Geometry and drawing primitives for the order overlay.

Two halves, kept apart on purpose:

- **Geometry** (pure functions on point lists): trimming a path by arc length,
  offsetting it sideways, sampling a spline through a convoy chain, building an
  arrowhead or a bounce bar. ``tests/test_arrow_geometry.py`` asserts these
  directly -- a picture can only be checked by its numbers.
- **Drawing** (``stroke_*``/``draw_*``): put those shapes on a ``DrawTarget``,
  always as a dark casing first and the colour on top, so a line in a power's
  colour reads on land, sea and every other power's tint.

Nothing here knows about orders or results; ``rendering.overlays`` decides what
each order looks like and calls these.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from .antialias import DrawTarget

Point = tuple[float, float]
Colour = tuple[int, ...]


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def unit_vector(a: Point, b: Point) -> Point:
    """Direction from ``a`` to ``b``; ``(1, 0)`` when they coincide."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length else (1.0, 0.0)


def path_length(points: Sequence[Point]) -> float:
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def point_at(points: Sequence[Point], distance: float) -> tuple[Point, Point]:
    """The point ``distance`` along ``points`` and the path's direction there."""
    remaining = max(0.0, distance)
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        seg = math.dist(a, b)
        if seg and remaining <= seg:
            t = remaining / seg
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), unit_vector(a, b)
        remaining -= seg
    return points[-1], unit_vector(points[-2], points[-1]) if len(points) > 1 else (1.0, 0.0)


def trim(points: Sequence[Point], start: float, end: float) -> list[Point]:
    """``points`` with ``start`` cut off its beginning and ``end`` off its end, by
    arc length. Empty when nothing is left."""
    total = path_length(points)
    if total <= 0 or start + end >= total:
        return []
    head, _ = point_at(points, start)
    tail, _ = point_at(points, total - end)
    out = [head]
    walked = 0.0
    for i in range(len(points) - 1):
        walked += math.dist(points[i], points[i + 1])
        if start < walked < total - end:
            out.append(points[i + 1])
    out.append(tail)
    return out


def offset(points: Sequence[Point], distance: float) -> list[Point]:
    """``points`` moved ``distance`` to the right of their direction of travel
    (screen coordinates, y down). Two opposed moves offset by the same amount end
    up on opposite sides of the line between their provinces."""
    if len(points) < 2 or not distance:
        return list(points)
    ux, uy = unit_vector(points[0], points[-1])
    nx, ny = -uy, ux
    return [(x + nx * distance, y + ny * distance) for x, y in points]


def catmull_rom(points: Sequence[Point], steps_per_leg: int) -> list[Point]:
    """A smooth curve through every point of ``points`` (centripetal-free uniform
    Catmull-Rom; the end points are repeated so the curve starts and ends on them)."""
    if len(points) < 3:
        return list(points)
    pts = [points[0], *points, points[-1]]
    out: list[Point] = [points[0]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(1, steps_per_leg + 1):
            t = s / steps_per_leg
            t2, t3 = t * t, t * t * t
            out.append(tuple(  # type: ignore[arg-type]
                0.5 * (2 * p1[k] + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                       + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in (0, 1)
            ))
    return out


def head_polygon(tip: Point, direction: Point, length: float, half_width: float, notch: float) -> list[Point]:
    """A barbed arrowhead: tip, one barb, the notch, the other barb."""
    ux, uy = direction
    vx, vy = -uy, ux
    bx, by = tip[0] - length * ux, tip[1] - length * uy
    nx, ny = tip[0] - (length - notch) * ux, tip[1] - (length - notch) * uy
    return [tip, (bx + half_width * vx, by + half_width * vy), (nx, ny), (bx - half_width * vx, by - half_width * vy)]


def bar_segment(at: Point, direction: Point, half_length: float) -> tuple[Point, Point]:
    """The two ends of a bar across a path at ``at`` -- the "stopped here" mark."""
    vx, vy = -direction[1], direction[0]
    return (at[0] + vx * half_length, at[1] + vy * half_length), (at[0] - vx * half_length, at[1] - vy * half_length)


def octagon(center: Point, radius: float) -> list[Point]:
    """A flat-topped regular octagon -- the hold symbol, a shape no other marker uses."""
    cx, cy = center
    return [
        (cx + radius * math.cos(math.pi / 8 + k * math.pi / 4), cy + radius * math.sin(math.pi / 8 + k * math.pi / 4))
        for k in range(8)
    ]


def burst(center: Point, outer: float, inner: float, points: int = 8) -> list[Point]:
    """A star burst -- the standoff symbol."""
    cx, cy = center
    out = []
    for k in range(points * 2):
        r = outer if k % 2 == 0 else inner
        a = -math.pi / 2 + k * math.pi / points
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def dash_segments(points: Sequence[Point], dash: float, gap: float) -> list[list[Point]]:
    """Split a path into dashes of ``dash`` length separated by ``gap``, following
    its bends (each dash is itself a polyline)."""
    total = path_length(points)
    out: list[list[Point]] = []
    pos = 0.0
    while pos < total:
        end = min(pos + dash, total)
        piece = trim(points, pos, total - end)
        if len(piece) >= 2:
            out.append(piece)
        pos += dash + gap
    return out


# --------------------------------------------------------------------------
# Drawing
# --------------------------------------------------------------------------


def _polyline(draw: DrawTarget, points: Sequence[Point], colour: Any, width: float) -> None:
    if len(points) >= 2:
        draw.line([tuple(p) for p in points], fill=colour, width=width, joint="curve")


def stroke_path(
    draw: DrawTarget,
    points: Sequence[Point],
    colour: Any,
    width: float,
    *,
    casing: Any = None,
    casing_width: float = 0.0,
    dash: tuple[float, float] | None = None,
) -> None:
    """Stroke ``points``: the casing (``width + 2 * casing_width``) under the colour,
    either unbroken or as ``dash = (dash, gap)``."""
    pieces = dash_segments(points, *dash) if dash else [list(points)]
    if casing is not None and casing_width > 0:
        for piece in pieces:
            _polyline(draw, piece, casing, width + 2 * casing_width)
    for piece in pieces:
        _polyline(draw, piece, colour, width)


def draw_arrow(
    draw: DrawTarget,
    points: Sequence[Point],
    colour: Any,
    width: float,
    *,
    casing: Any,
    casing_width: float,
    head_length: float,
    head_half_width: float,
    head_notch: float,
    dash: tuple[float, float] | None = None,
) -> list[Point] | None:
    """An arrow along ``points`` ending in a head at the last point.

    The head shrinks on a path too short for it, and the shaft stops at the head's
    notch so it never pokes through the barbs. Returns the head polygon (``None``
    when the path is too short to draw at all)."""
    total = path_length(points)
    if total < 4:
        return None
    length = min(head_length, total * 0.6)
    scale = length / head_length
    tip = points[-1]
    _, direction = point_at(points, total)
    head = head_polygon(tip, direction, length, head_half_width * max(scale, 0.6), head_notch * scale)
    shaft = trim(points, 0, length - head_notch * scale)
    if casing is not None and casing_width > 0:
        stroke_path(draw, shaft, casing, width + 2 * casing_width, dash=dash)
        cased = head_polygon(
            (tip[0] + casing_width * direction[0], tip[1] + casing_width * direction[1]),
            direction, length + 2 * casing_width, head_half_width * max(scale, 0.6) + casing_width,
            head_notch * scale,
        )
        draw.polygon(cased, fill=casing)
    stroke_path(draw, shaft, colour, width, dash=dash)
    draw.polygon(head, fill=colour)
    return head


def draw_bar(
    draw: DrawTarget, at: Point, direction: Point, colour: Any, *, half_length: float, width: float,
    casing: Any, casing_width: float,
) -> tuple[Point, Point]:
    """A bar across a path at ``at``; returns its two ends."""
    a, b = bar_segment(at, direction, half_length)
    ca, cb = bar_segment(at, direction, half_length + casing_width)
    draw.line([ca, cb], fill=casing, width=width + 2 * casing_width)
    draw.line([a, b], fill=colour, width=width)
    return a, b


def draw_ring(
    draw: DrawTarget, center: Point, radius: float, colour: Any, width: float, *,
    casing: Any = None, casing_width: float = 0.0,
) -> None:
    """A circle outline of ``radius`` (to the middle of the stroke)."""
    cx, cy = center
    if casing is not None and casing_width > 0:
        r = radius + width / 2 + casing_width
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=casing, width=width + 2 * casing_width)
    r = radius + width / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=colour, width=width)


def draw_polygon_outline(
    draw: DrawTarget, polygon: Sequence[Point], colour: Any, width: float, *,
    casing: Any = None, casing_width: float = 0.0,
) -> None:
    closed = [*polygon, polygon[0], polygon[1]]
    if casing is not None and casing_width > 0:
        _polyline(draw, closed, casing, width + 2 * casing_width)
    _polyline(draw, closed, colour, width)


def draw_cross(
    draw: DrawTarget, center: Point, size: float, colour: Any, width: float, *,
    casing: Any = None, casing_width: float = 0.0,
) -> None:
    """An ✗ of half-size ``size``, optionally cased."""
    cx, cy = center
    strokes = [((cx - size, cy - size), (cx + size, cy + size)), ((cx - size, cy + size), (cx + size, cy - size))]
    if casing is not None and casing_width > 0:
        c = size + casing_width * 0.7
        for (a, b) in [((cx - c, cy - c), (cx + c, cy + c)), ((cx - c, cy + c), (cx + c, cy - c))]:
            draw.line([a, b], fill=casing, width=width + 2 * casing_width)
    for a, b in strokes:
        draw.line([a, b], fill=colour, width=width)


def draw_filled(draw: DrawTarget, polygon: Sequence[Point], colour: Any, *, casing: Any = None) -> None:
    draw.polygon([tuple(p) for p in polygon], fill=colour, outline=casing)
