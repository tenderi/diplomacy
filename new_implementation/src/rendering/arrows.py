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
from typing import Any

from PIL import ImageDraw

from .board import _convert_color_to_rgb
from .visualization_config import get_config

_viz_config = get_config()


def _draw_bounce_arrow(draw: ImageDraw.ImageDraw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2) -> None:
    """Draw curved return arrow for bounced moves"""
    from_x, from_y = from_coord
    to_x, to_y = to_coord

    # Get config for outline
    arrow_specs = _viz_config.get_arrow_specs()
    outline_width = arrow_specs.get("outline_width", 2)
    arrowhead_size = arrow_specs["arrowhead_size"]
    outline_color = (0, 0, 0)  # Black
    total_width = width + outline_width * 2

    # Calculate midpoint
    mid_x = (from_x + to_x) / 2
    mid_y = (from_y + to_y) / 2

    # Calculate perpendicular offset for curve
    angle = math.atan2(to_y - from_y, to_x - from_x)
    perp_angle = angle + math.pi / 2
    offset = 40  # Larger offset for bounce curve

    control_x = mid_x + offset * math.cos(perp_angle)
    control_y = mid_y + offset * math.sin(perp_angle)

    # Draw curved line showing bounce
    steps = 30
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = (1-t)**2 * from_x + 2*(1-t)*t * control_x + t**2 * to_x
        y = (1-t)**2 * from_y + 2*(1-t)*t * control_y + t**2 * to_y
        points.append((x, y))

    # Offset target by 4 pixels to prevent collisions
    collision_offset = 4
    angle_to_dest = math.atan2(to_y - points[-2][1], to_x - points[-2][0])
    actual_tip_x = to_x - collision_offset * math.cos(angle_to_dest)
    actual_tip_y = to_y - collision_offset * math.sin(angle_to_dest)

    arrow_length = arrowhead_size
    arrow_angle = math.pi / 6
    head_x1 = actual_tip_x - arrow_length * math.cos(angle_to_dest - arrow_angle)
    head_y1 = actual_tip_y - arrow_length * math.sin(angle_to_dest - arrow_angle)
    head_x2 = actual_tip_x - arrow_length * math.cos(angle_to_dest + arrow_angle)
    head_y2 = actual_tip_y - arrow_length * math.sin(angle_to_dest + arrow_angle)

    # Calculate arrowhead base center (where curve should end)
    base_center_x = (head_x1 + head_x2) / 2
    base_center_y = (head_y1 + head_y2) / 2

    # Calculate outline arrowhead (slightly larger)
    outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle_to_dest - arrow_angle)
    outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle_to_dest - arrow_angle)
    outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle_to_dest + arrow_angle)
    outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle_to_dest + arrow_angle)

    # Adjust last point to end at arrowhead base
    points[-1] = (base_center_x, base_center_y)

    # Draw outline curve
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=outline_color, width=total_width)

    # Draw outline arrowhead (slightly larger)
    draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)

    # Draw colored curve on top
    for i in range(len(points) - 1):
        draw.line([points[i], points[i+1]], fill=color, width=width)

    # Draw colored arrowhead on top
    draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)


def _draw_dotted_arrow(draw: ImageDraw.ImageDraw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2) -> None:
    """Draw dotted arrow for retreat orders"""
    from_x, from_y = from_coord
    to_x, to_y = to_coord

    # Get config for outline
    arrow_specs = _viz_config.get_arrow_specs()
    outline_width = arrow_specs.get("outline_width", 2)
    arrowhead_size = arrow_specs["arrowhead_size"]
    outline_color = (0, 0, 0)  # Black
    total_width = width + outline_width * 2

    # Calculate arrowhead first
    angle = math.atan2(to_y - from_y, to_x - from_x)

    # Offset target by 4 pixels to prevent collisions
    collision_offset = 4
    actual_tip_x = to_x - collision_offset * math.cos(angle)
    actual_tip_y = to_y - collision_offset * math.sin(angle)

    arrow_length = arrowhead_size
    arrow_angle = math.pi / 6
    head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
    head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
    head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
    head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)

    # Calculate arrowhead base center (where line should end)
    base_center_x = (head_x1 + head_x2) / 2
    base_center_y = (head_y1 + head_y2) / 2

    # Calculate outline arrowhead (slightly larger)
    outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
    outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
    outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
    outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)

    # Draw dotted line ending at arrowhead base
    length = math.sqrt((base_center_x - from_x)**2 + (base_center_y - from_y)**2)
    if length == 0:
        return

    dot_spacing = 8
    num_dots = int(length / dot_spacing)
    dx = (base_center_x - from_x) / num_dots if num_dots > 0 else 0
    dy = (base_center_y - from_y) / num_dots if num_dots > 0 else 0

    # Draw outline dots
    for i in range(0, num_dots, 2):
        x1 = from_x + i * dx
        y1 = from_y + i * dy
        x2 = from_x + (i + 1) * dx if i + 1 < num_dots else base_center_x
        y2 = from_y + (i + 1) * dy if i + 1 < num_dots else base_center_y
        draw.line([x1, y1, x2, y2], fill=outline_color, width=total_width)

    # Draw outline arrowhead (slightly larger)
    draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)

    # Draw colored dots on top
    for i in range(0, num_dots, 2):
        x1 = from_x + i * dx
        y1 = from_y + i * dy
        x2 = from_x + (i + 1) * dx if i + 1 < num_dots else base_center_x
        y2 = from_y + (i + 1) * dy if i + 1 < num_dots else base_center_y
        draw.line([x1, y1, x2, y2], fill=color, width=width)

    # Draw colored arrowhead on top
    draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)


def _draw_success_checkmark(draw: ImageDraw.ImageDraw, coord: tuple, color: str | None = None) -> None:
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


def _draw_dislodged_marker(draw: ImageDraw.ImageDraw, coord: tuple, color: str | None = None) -> None:
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


def _draw_failure_x(draw: ImageDraw.ImageDraw, coord: tuple, color: str | None = None) -> None:
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


def _draw_support_cut_indicator(draw: ImageDraw.ImageDraw, from_coord: tuple, to_coord: tuple) -> None:
    """Draw red X through support line to indicate support was cut"""
    # Draw X at midpoint of support line
    mid_x = (from_coord[0] + to_coord[0]) / 2
    mid_y = (from_coord[1] + to_coord[1]) / 2
    _draw_failure_x(draw, (mid_x, mid_y), "red")


def _draw_star(draw: ImageDraw.ImageDraw, coord: tuple, size: int, outline_color: str, fill_color: str) -> None:
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
    draw: ImageDraw.ImageDraw,
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
        draw: ImageDraw object
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
    arrowhead_size = arrow_specs["arrowhead_size"]
    outline_width = arrow_specs.get("outline_width", 2)  # Default 2px black outline

    # Convert color to RGB if needed
    rgb_color = _convert_color_to_rgb(color)

    from_x, from_y = from_coord
    to_x, to_y = to_coord

    # Offset target by 4 pixels to prevent collisions when multiple arrows point to same region
    collision_offset = 4
    angle = math.atan2(to_y - from_y, to_x - from_x)
    # Move target back by collision_offset pixels
    actual_tip_x = to_x - collision_offset * math.cos(angle)
    actual_tip_y = to_y - collision_offset * math.sin(angle)

    # Calculate arrowhead points first (needed for both outline and fill)
    arrow_length = arrowhead_size
    arrow_angle = math.pi / 6  # 30 degrees (triangular shape)

    # Arrowhead tip is at actual_tip (4px before destination)
    # Arrowhead base extends backwards from tip
    head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
    head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
    head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
    head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)

    # Calculate arrowhead base center (where line should end)
    base_center_x = (head_x1 + head_x2) / 2
    base_center_y = (head_y1 + head_y2) / 2

    # Draw black outline first (wider line + outlined arrowhead)
    outline_color = (0, 0, 0)  # Black
    total_width = line_width + outline_width * 2

    # Calculate outline arrowhead (slightly larger for outline effect)
    outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
    outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
    outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
    outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)

    if style == "solid":
        # Draw outline line ending at arrowhead base
        draw.line([from_x, from_y, base_center_x, base_center_y], fill=outline_color, width=total_width)
    elif style == "dashed":
        line_style = _viz_config.get_line_style("dashed")
        _draw_dashed_line(draw, from_x, from_y, base_center_x, base_center_y, outline_color, total_width,
                            dash=line_style.get("dash", 4), gap=line_style.get("gap", 2))
    elif style == "dotted":
        line_style = _viz_config.get_line_style("dotted")
        _draw_dotted_line(draw, from_x, from_y, base_center_x, base_center_y, outline_color, total_width,
                             dot=line_style.get("dot", 2), gap=line_style.get("gap", 2))

    # Draw outline arrowhead (slightly larger to create outline effect)
    draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)

    # Now draw the colored arrow on top
    if style == "dashed":
        line_style = _viz_config.get_line_style("dashed")
        _draw_dashed_line(draw, from_x, from_y, base_center_x, base_center_y, rgb_color, line_width,
                            dash=line_style.get("dash", 4), gap=line_style.get("gap", 2))
    elif style == "dotted":
        line_style = _viz_config.get_line_style("dotted")
        _draw_dotted_line(draw, from_x, from_y, base_center_x, base_center_y, rgb_color, line_width,
                             dot=line_style.get("dot", 2), gap=line_style.get("gap", 2))
    else:  # solid
        # Draw colored line ending at arrowhead base
        draw.line([from_x, from_y, base_center_x, base_center_y], fill=rgb_color, width=line_width)

    # Draw colored arrowhead on top
    draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=rgb_color)

    # Draw status indicators if provided (use actual tip position)
    actual_tip_coord = (actual_tip_x, actual_tip_y)
    if status == "success":
        _draw_success_checkmark(draw, actual_tip_coord)
    elif status == "failure":
        _draw_failure_x(draw, actual_tip_coord)
    elif status == "bounce":
        # Draw bounce indicator (curved return arrow)
        bounce_color = _viz_config.get_color("failure")  # Use failure color for bounce
        _draw_bounce_arrow(draw, actual_tip_coord, from_coord, bounce_color, arrow_specs["line_width_secondary"])


def _draw_circle(draw: ImageDraw.ImageDraw, coord: tuple, color: str, width: int = 2, style: str = "solid") -> None:
    """Draw circle around coordinate (legacy - use _draw_circle_at_size for config-based sizing)"""
    x, y = coord
    radius = 15

    if style == "dashed":
        _draw_dashed_circle(draw, x, y, radius, color, width)
    else:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)


def _draw_circle_at_size(draw: ImageDraw.ImageDraw, coord: tuple, color: str, diameter: int, width: int, style: str = "solid") -> None:
    """Draw circle at specified diameter using config values."""
    x, y = coord
    radius = diameter // 2
    rgb_color = _convert_color_to_rgb(color)

    if style == "dashed":
        _draw_dashed_circle(draw, x, y, radius, rgb_color, width)
    else:
        draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                    outline=rgb_color, width=width)


def _draw_glowing_circle(draw: ImageDraw.ImageDraw, coord: tuple, color: str, width: int = 4) -> None:
    """Draw glowing circle for build orders"""
    x, y = coord
    radius = 20

    # Draw outer glow (lighter color)
    glow_color = _lighten_color(color)
    draw.ellipse([x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2], outline=glow_color, width=width)

    # Draw inner circle
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)


def _draw_cross(draw: ImageDraw.ImageDraw, coord: tuple, color: str, width: int = 4) -> None:
    """Draw red cross for destroy orders"""
    x, y = coord
    size = 15

    # Draw X
    draw.line([x - size, y - size, x + size, y + size], fill=color, width=width)
    draw.line([x - size, y + size, x + size, y - size], fill=color, width=width)


def _draw_curved_arrow(draw: ImageDraw.ImageDraw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2, style: str = "solid") -> None:
    """Draw curved arrow for convoy orders"""
    from_x, from_y = from_coord
    to_x, to_y = to_coord

    # Get config for outline
    arrow_specs = _viz_config.get_arrow_specs()
    outline_width = arrow_specs.get("outline_width", 2)
    arrowhead_size = arrow_specs["arrowhead_size"]
    outline_color = (0, 0, 0)  # Black
    total_width = width + outline_width * 2

    # Calculate control point for curve
    mid_x = (from_x + to_x) / 2
    mid_y = (from_y + to_y) / 2

    # Offset control point to create curve
    angle = math.atan2(to_y - from_y, to_x - from_x)
    perp_angle = angle + math.pi / 2
    offset = 30

    control_x = mid_x + offset * math.cos(perp_angle)
    control_y = mid_y + offset * math.sin(perp_angle)

    # Offset target by 4 pixels to prevent collisions
    collision_offset = 4
    actual_tip_x = to_x - collision_offset * math.cos(angle)
    actual_tip_y = to_y - collision_offset * math.sin(angle)

    # Calculate arrowhead position
    arrow_length = arrowhead_size
    arrow_angle = math.pi / 6
    head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
    head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
    head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
    head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)

    # Calculate arrowhead base center (where curve should end)
    base_center_x = (head_x1 + head_x2) / 2
    base_center_y = (head_y1 + head_y2) / 2

    # Calculate outline arrowhead (slightly larger)
    outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
    outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
    outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
    outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)

    # Draw outline curved line using quadratic bezier, ending at arrowhead base
    steps = 20
    for i in range(steps):
        t1 = i / steps
        t2 = (i + 1) / steps

        x1 = (1-t1)**2 * from_x + 2*(1-t1)*t1 * control_x + t1**2 * base_center_x
        y1 = (1-t1)**2 * from_y + 2*(1-t1)*t1 * control_y + t1**2 * base_center_y
        x2 = (1-t2)**2 * from_x + 2*(1-t2)*t2 * control_x + t2**2 * base_center_x
        y2 = (1-t2)**2 * from_y + 2*(1-t2)*t2 * control_y + t2**2 * base_center_y

        if style == "dashed" and i % 2 == 0:
            continue
        draw.line([x1, y1, x2, y2], fill=outline_color, width=total_width)

    # Draw outline arrowhead (slightly larger)
    draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)

    # Draw colored curved line on top
    for i in range(steps):
        t1 = i / steps
        t2 = (i + 1) / steps

        x1 = (1-t1)**2 * from_x + 2*(1-t1)*t1 * control_x + t1**2 * base_center_x
        y1 = (1-t1)**2 * from_y + 2*(1-t1)*t1 * control_y + t1**2 * base_center_y
        x2 = (1-t2)**2 * from_x + 2*(1-t2)*t2 * control_x + t2**2 * base_center_x
        y2 = (1-t2)**2 * from_y + 2*(1-t2)*t2 * control_y + t2**2 * base_center_y

        if style == "dashed" and i % 2 == 0:
            continue
        draw.line([x1, y1, x2, y2], fill=color, width=width)

    # Draw colored arrowhead on top
    draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)


def _draw_dashed_line(draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, color: Any, width: int, dash: int = 4, gap: int = 2) -> None:
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


def _draw_dotted_line(draw: ImageDraw.ImageDraw, x1: float, y1: float, x2: float, y2: float, color: Any, width: int, dot: int = 2, gap: int = 2) -> None:
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


def _draw_dashed_circle(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, color: Any, width: int) -> None:
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
