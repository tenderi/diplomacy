"""Low-level SVG path parsing and filling: province transparency coloring, ocean
hatching, and the raw polygon/path fill helpers they're built on.

Split out of ``rendering.board`` during the V3 rendering split -- ``board.py``'s
``render_board_png`` was pulling in this whole polygon-parsing layer just to
call ``_color_provinces_by_power_with_transparency`` once, which pushed it past
the ~800-line target on its own. This module is deliberately one layer below
``board.py`` (it imports helpers from there, not the reverse): callers reach it
via a local import inside ``render_board_png`` to avoid a circular import.
"""
from __future__ import annotations

import logging
import math
import re
from typing import Any

from PIL import Image, ImageChops, ImageDraw

from .board import _engine_map, _get_cached_svg_data, _hex_to_rgb, _is_water_province

logger = logging.getLogger("diplomacy.rendering.map")


def _color_provinces_by_power_with_transparency(
    bg_image: Image.Image,
    units: dict,
    power_colors: dict,
    svg_path: str,
    supply_center_control: dict | None = None,
    current_phase: str | None = None,
    color_only_supply_centers: bool = False,
    supply_centers_set: set | None = None,
) -> None:
    """Color provinces using proper transparency with separate overlay layer.

    Args:
        bg_image: Background image to color
        units: Dictionary mapping powers to their unit lists
        power_colors: Dictionary mapping power names to colors
        svg_path: Path to SVG map file
        supply_center_control: Dictionary mapping supply center provinces to controlling powers
        current_phase: Current game phase (for future use)
        color_only_supply_centers: If True, only color supply center provinces
        supply_centers_set: Set of supply center province names (required if color_only_supply_centers is True)

    Note:
        This function processes SVG paths with IDs starting with '_' (preferred) and without '_' (fallback).
        Known limitation: MAO, NAO, NWG, and TYS do not have path elements in the SVG file and cannot be colored.
        These provinces will be logged as warnings but will not cause errors.
    """
    try:
        # Use cached SVG data instead of parsing again
        tree, jdip_coords, _ = _get_cached_svg_data(svg_path)
        root = tree.getroot()

        # Create a separate transparent overlay layer
        overlay = Image.new('RGBA', bg_image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # Define namespace for SVG elements
        namespaces = {'svg': 'http://www.w3.org/2000/svg'}

        # Find all path elements with id attributes (these are provinces)
        all_paths = root.findall('.//svg:path[@id]', namespaces)
        if not all_paths:
            all_paths = root.findall('.//path[@id]')

        # Find SVG paths for provinces (these are the actual province shapes)
        # Some provinces have paths with underscore prefix (_province), some without (province)
        # We prioritize underscore paths but also include non-underscore paths as fallback
        province_paths = []
        province_paths_by_id = {}  # Map normalized ID to path element (to avoid duplicates)

        for path in all_paths:
            province_id = path.get('id')
            if province_id:
                normalized_id = province_id.lstrip('_').upper()
                # Prioritize paths with underscore prefix, but also track non-underscore paths
                if province_id.startswith('_'):
                    # Path with underscore - preferred
                    if normalized_id not in province_paths_by_id:
                        province_paths_by_id[normalized_id] = path
                        province_paths.append(path)
                else:
                    # Path without underscore - use as fallback if no underscore version exists
                    if normalized_id not in province_paths_by_id:
                        province_paths_by_id[normalized_id] = path
                        province_paths.append(path)

        # Create a map of province names to power colors
        province_power_map = {}

        # First, add supply center control colors (if provided)
        if supply_center_control:
            for province, power in supply_center_control.items():
                color = power_colors.get(power.upper(), "black")
                province_power_map[province.upper()] = color

        # Then, add unit location colors (overrides supply center colors for occupied provinces)
        for power, unit_list in units.items():
            color = power_colors.get(power.upper(), "black")
            for unit in unit_list:
                parts = unit.split()
                if len(parts) == 2:
                    prov = parts[1].upper()
                    # Only override if this is not a dislodged unit
                    if not prov.startswith("DISLODGED_"):
                        province_power_map[prov] = color

        # Get supply centers set if filtering is enabled
        if color_only_supply_centers:
            if supply_centers_set is None:
                # Get supply centers from the engine's topology if available
                try:
                    supply_centers_set = set(_engine_map().supply_centers)
                except Exception:
                    supply_centers_set = set()  # Fallback: empty set
            # Filter province_power_map to only include supply centers
            province_power_map = {prov: color for prov, color in province_power_map.items()
                                if prov in supply_centers_set}

        # Track which provinces from province_power_map were found in SVG
        colored_provinces = set()

        # Color each province based on power control using SVG paths
        for path_elem in province_paths:
            province_id = path_elem.get('id')
            if province_id:
                # Remove underscore prefix and convert to uppercase
                normalized_id = province_id.lstrip('_').upper()

                if normalized_id in province_power_map:
                    colored_provinces.add(normalized_id)

                    # Get the power color for this province
                    power_color = province_power_map[normalized_id]

                    # Convert color to RGB for proper transparency
                    rgb_color = _hex_to_rgb(power_color)

                    path_data = path_elem.get('d')
                    if path_data:
                        if _is_water_province(normalized_id):
                            polygon_points = _extract_polygon_points_from_path(path_data, 195, 170)
                            pattern_color = (*rgb_color, 120)
                            if polygon_points and len(polygon_points) >= 3:
                                _draw_ocean_pattern(overlay, polygon_points, pattern_color, spacing=10, angle=45, line_width=1)
                        else:
                            transparent_color = (*rgb_color, 90)
                            _fill_svg_path_with_transform(overlay_draw, path_data, transparent_color, power_color, 195, 170)

        # Log warning for provinces in province_power_map but not found in SVG paths
        missing_provinces = set(province_power_map.keys()) - colored_provinces
        if missing_provinces:
            # Known missing provinces: MAO, NAO, NWG, TYS (these don't have path elements in the SVG file)
            known_missing = {"MAO", "NAO", "NWG", "TYS"}
            unknown_missing = missing_provinces - known_missing

            if unknown_missing:
                logger.warning(f"Provinces in province_power_map but missing SVG paths (unexpected): {sorted(unknown_missing)}")

            if missing_provinces & known_missing:
                logger.debug(f"Provinces missing SVG paths (known limitation): {sorted(missing_provinces & known_missing)}. "
                           f"These provinces (MAO, NAO, NWG, TYS) exist in the game but have no path elements in the SVG file.")

        # Composite the overlay onto the background image using proper alpha compositing
        bg_image.paste(overlay, (0, 0), overlay)

    except Exception as e:
        logger.warning(f"Could not parse SVG for province coloring: {e}")
        # Fallback: continue without province coloring


def _extract_polygon_points_from_path(
    path_data: str, offset_x: float, offset_y: float
) -> list[tuple[float, float]] | None:
    """Extract polygon points from SVG path data with coordinate transform.

    Handles M (moveto), L (lineto), C (cubic Bezier), and Z (close) commands.
    Bezier curves are sampled at multiple points for accurate boundary representation.

    Returns:
        List of (x, y) tuples, or None if parsing fails
    """
    def cubic_bezier_point(p0, p1, p2, p3, t):
        """Calculate point on cubic Bezier curve at parameter t (0 to 1)."""
        mt = 1 - t
        return (
            mt**3 * p0[0] + 3*mt**2*t * p1[0] + 3*mt*t**2 * p2[0] + t**3 * p3[0],
            mt**3 * p0[1] + 3*mt**2*t * p1[1] + 3*mt*t**2 * p2[1] + t**3 * p3[1]
        )

    try:
        points = []
        current_x, current_y = 0, 0
        start_x, start_y = 0, 0

        # Split path data into commands
        path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)

        for cmd, params in path_commands:
            coords = re.findall(r'(-?\d+\.?\d*)', params)
            coords = [float(c) for c in coords]

            if cmd == 'M':  # Absolute moveto
                if len(coords) >= 2:
                    current_x, current_y = coords[0], coords[1]
                    start_x, start_y = current_x, current_y
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'm':  # Relative moveto
                if len(coords) >= 2:
                    current_x += coords[0]
                    current_y += coords[1]
                    start_x, start_y = current_x, current_y
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'L':  # Absolute lineto
                if len(coords) >= 2:
                    current_x, current_y = coords[0], coords[1]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'l':  # Relative lineto
                if len(coords) >= 2:
                    current_x += coords[0]
                    current_y += coords[1]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'H':  # Absolute horizontal lineto
                if len(coords) >= 1:
                    current_x = coords[0]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'h':  # Relative horizontal lineto
                if len(coords) >= 1:
                    current_x += coords[0]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'V':  # Absolute vertical lineto
                if len(coords) >= 1:
                    current_y = coords[0]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'v':  # Relative vertical lineto
                if len(coords) >= 1:
                    current_y += coords[0]
                    points.append((current_x - offset_x, current_y - offset_y))
            elif cmd == 'C':  # Absolute cubic Bezier
                # Process all sets of 6 coordinates (multiple curves can be chained)
                for i in range(0, len(coords) - 5, 6):
                    p0 = (current_x, current_y)
                    p1 = (coords[i], coords[i+1])
                    p2 = (coords[i+2], coords[i+3])
                    p3 = (coords[i+4], coords[i+5])
                    # Sample 8 points along the curve for smooth approximation
                    for t in [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]:
                        bx, by = cubic_bezier_point(p0, p1, p2, p3, t)
                        points.append((bx - offset_x, by - offset_y))
                    current_x, current_y = p3[0], p3[1]
            elif cmd == 'c':  # Relative cubic Bezier
                for i in range(0, len(coords) - 5, 6):
                    p0 = (current_x, current_y)
                    p1 = (current_x + coords[i], current_y + coords[i+1])
                    p2 = (current_x + coords[i+2], current_y + coords[i+3])
                    p3 = (current_x + coords[i+4], current_y + coords[i+5])
                    for t in [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]:
                        bx, by = cubic_bezier_point(p0, p1, p2, p3, t)
                        points.append((bx - offset_x, by - offset_y))
                    current_x, current_y = p3[0], p3[1]
            elif cmd in ['Z', 'z']:  # Close path
                if start_x != current_x or start_y != current_y:
                    points.append((start_x - offset_x, start_y - offset_y))

        if len(points) > 2:
            return points
        return None

    except Exception as e:
        logger.warning(f"Could not extract polygon points from path: {e}")
        return None


def _fill_svg_path_with_transform(
    draw: ImageDraw.ImageDraw, path_data: str, fill_color: Any, stroke_color: Any, offset_x: float, offset_y: float
) -> None:
    """Fill an SVG path with coordinate transform to compensate for SVG group transforms."""
    try:
        # Extract polygon points
        points = _extract_polygon_points_from_path(path_data, offset_x, offset_y)

        if points and len(points) > 2:
            # Draw the filled polygon with transformed coordinates
            draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)

    except Exception as e:
        logger.warning(f"Could not fill SVG path with transform: {e}")
        # Fallback: continue without path filling


def _draw_ocean_pattern(
    overlay_image: Image.Image,
    polygon_points: list[tuple[float, float]],
    pattern_color: tuple[int, ...],
    spacing: int = 10,
    angle: int = 45,
    line_width: int = 1,
) -> None:
    """Draw hatched/striped pattern for ocean provinces, clipped to polygon shape.

    Args:
        overlay_image: PIL Image object (RGBA mode) to draw on
        polygon_points: List of (x, y) tuples defining the polygon
        pattern_color: RGBA color tuple for the pattern lines
        spacing: Distance between pattern lines in pixels
        angle: Angle of pattern lines in degrees (45 = diagonal)
        line_width: Width of pattern lines in pixels
    """
    if len(polygon_points) < 3:
        return  # Need at least 3 points for a polygon

    try:
        # Calculate bounding box of the polygon
        x_coords = [p[0] for p in polygon_points]
        y_coords = [p[1] for p in polygon_points]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        # Create a mask from the polygon for clipping
        mask = Image.new('L', overlay_image.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.polygon(polygon_points, fill=255)

        # Create a temporary image for the pattern (fully transparent)
        pattern_img = Image.new('RGBA', overlay_image.size, (0, 0, 0, 0))
        pattern_draw = ImageDraw.Draw(pattern_img)

        # Convert angle to radians
        angle_rad = math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        # Calculate the diagonal length of the bounding box
        width = max_x - min_x
        height = max_y - min_y
        diagonal = math.sqrt(width * width + height * height)

        # Calculate number of lines needed
        num_lines = int(diagonal / spacing) + 2

        # Draw diagonal lines across the bounding box
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2

        for i in range(-num_lines, num_lines + 1):
            # Calculate line offset
            offset = i * spacing

            # Calculate line endpoints
            # For 45-degree diagonal, we move perpendicular to the line direction
            perp_x = -sin_a * offset
            perp_y = cos_a * offset

            # Line extends from one corner to the opposite corner
            # We extend it well beyond the bounding box
            line_length = diagonal * 1.5
            start_x = center_x + perp_x - cos_a * line_length / 2
            start_y = center_y + perp_y - sin_a * line_length / 2
            end_x = center_x + perp_x + cos_a * line_length / 2
            end_y = center_y + perp_y + sin_a * line_length / 2

            # Draw line on pattern image (lines have their own alpha from pattern_color)
            pattern_draw.line([(start_x, start_y), (end_x, end_y)], fill=pattern_color, width=line_width)

        # Apply mask to pattern image alpha channel to clip to polygon
        # This ensures only the polygon area shows the pattern, and transparent areas stay transparent
        pattern_alpha = pattern_img.split()[3]  # Get alpha channel
        # Multiply pattern alpha by mask: areas outside polygon become 0, areas inside keep pattern alpha
        masked_alpha = ImageChops.multiply(pattern_alpha, mask.convert('L'))
        pattern_img.putalpha(masked_alpha)

        # Composite pattern onto overlay - transparent areas remain transparent
        overlay_image.paste(pattern_img, (0, 0), pattern_img)

    except Exception as e:
        logger.warning(f"Could not draw ocean pattern: {e}")
        # Fallback: continue without pattern


def _fill_svg_path_direct(draw: ImageDraw.ImageDraw, path_data: str, fill_color: Any, stroke_color: Any) -> None:
    """Fill an SVG path using SVG coordinates directly - NO SCALING."""
    try:
        # Parse the path data to extract coordinates
        commands = []
        current_x, current_y = 0, 0

        # Split path data into commands
        path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)

        for cmd, params in path_commands:
            cmd = cmd.upper()
            if cmd == 'M':  # Move to
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 2:
                    current_x, current_y = float(coords[0]), float(coords[1])
                    commands.append(('M', current_x, current_y))
            elif cmd == 'L':  # Line to
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 2:
                    current_x, current_y = float(coords[0]), float(coords[1])
                    commands.append(('L', current_x, current_y))
            elif cmd == 'C':  # Cubic Bezier curve
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 6:  # C x1 y1 x2 y2 x y
                    # For simplicity, we'll use the end point of the curve
                    current_x, current_y = float(coords[4]), float(coords[5])
                    commands.append(('L', current_x, current_y))
            elif cmd == 'Z':  # Close path
                commands.append(('Z',))

        # NO SCALING - use SVG coordinates directly as they are
        # This should restore the working state from before I added scaling

        if len(commands) > 2:
            points = []
            for cmd in commands:
                if cmd[0] in ['M', 'L']:
                    # Use SVG coordinates directly - no transformation
                    x = cmd[1]
                    y = cmd[2]
                    points.append((x, y))

            if len(points) > 2:
                # Draw the filled polygon with direct SVG coordinates
                draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)

    except Exception as e:
        logger.warning(f"Could not fill SVG path with direct coordinates: {e}")
        # Fallback: continue without path filling


def _fill_svg_path(draw: ImageDraw.ImageDraw, path_data: str, fill_color: Any, stroke_color: Any) -> None:
    """Fill an SVG path on the PIL ImageDraw object."""
    try:
        # This is a simplified SVG path parser
        # For a production system, you'd want a proper SVG path library

        # Parse the path data to extract coordinates
        # SVG paths use commands like M (move), L (line), C (curve), Z (close)
        # For now, we'll implement a basic parser for simple paths

        commands = []
        current_x, current_y = 0, 0

        # Split path data into commands
        path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)

        for cmd, params in path_commands:
            cmd = cmd.upper()
            if cmd == 'M':  # Move to
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 2:
                    current_x, current_y = float(coords[0]), float(coords[1])
                    commands.append(('M', current_x, current_y))
            elif cmd == 'L':  # Line to
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 2:
                    current_x, current_y = float(coords[0]), float(coords[1])
                    commands.append(('L', current_x, current_y))
            elif cmd == 'C':  # Cubic Bezier curve
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                if len(coords) >= 6:  # C x1 y1 x2 y2 x y
                    # For simplicity, we'll use the end point of the curve
                    current_x, current_y = float(coords[4]), float(coords[5])
                    commands.append(('L', current_x, current_y))
            elif cmd == 'Z':  # Close path
                commands.append(('Z',))

        # Convert SVG coordinates to PIL coordinates
        # NO SCALING - PNG size matches SVG size exactly

        # For now, let's use a simple approach: create a polygon from the path
        if len(commands) > 2:
            points = []
            for cmd in commands:
                if cmd[0] in ['M', 'L']:
                    # NO SCALING - use SVG coordinates directly
                    x = cmd[1]
                    y = cmd[2]
                    points.append((x, y))

            if len(points) > 2:
                # Draw the filled polygon
                draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)

    except Exception as e:
        logger.warning(f"Could not fill SVG path: {e}")
        # Fallback: continue without path filling
