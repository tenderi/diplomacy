"""SVG -> PNG board rendering: parsing, coordinates, province coloring, and the
plain (no-orders) board render.

This module has zero topology knowledge of its own: province adjacency, coasts,
and supply centers all come from ``engine.map_loader`` (the sole topology source
in the codebase). It also carries the small color/power-name utilities shared by
``rendering.overlays`` and ``rendering.legend`` (``_convert_color_to_rgb``,
``_get_power_colors_dict``, ``KNOWN_POWER_NAMES``) so those modules can depend on
this one without a cycle back.
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import Any

import cairosvg  # type: ignore
from PIL import Image, ImageDraw, ImageFont

from engine.map_loader import MapData, load_standard_map
from engine.types import ProvinceType

from .cache import _map_cache
from .icons import _draw_army_icon, _draw_fleet_icon
from .visualization_config import get_config

logger = logging.getLogger("diplomacy.rendering.map")

_engine_map_data: MapData | None = None


def _engine_map() -> MapData:
    """The engine's topology for the bundled standard map (module-cached).

    A rendering -> engine import is fine; only the reverse direction (engine
    importing rendering) is banned. Used to replace what used to be a
    duplicate, hardcoded topology parser in this module.
    """
    global _engine_map_data
    if _engine_map_data is None:
        _engine_map_data = load_standard_map()
    return _engine_map_data


def _is_water_province(province_code: str) -> bool:
    """Ocean hatching predicate, backed by the engine's province types."""
    try:
        return _engine_map().province_type(province_code) is ProvinceType.WATER
    except KeyError:
        return False


KNOWN_POWER_NAMES = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})

# Global SVG parsing cache
_svg_cache: dict[str, tuple[ET.ElementTree, dict[str, tuple[float, float]], dict[str, tuple[float, float]]]] = {}
_font_cache: dict[int, ImageFont.ImageFont] = {}

# Get global config instance
_viz_config = get_config()


def _get_power_colors_dict() -> dict[str, str]:
    """Get power colors dictionary from config."""
    power_colors = {}
    for power in KNOWN_POWER_NAMES:
        power_colors[power] = _viz_config.get_power_color(power)
    return power_colors


def _convert_color_to_rgb(color: str) -> Any:
    """Convert hex color to RGB tuple or return named color as-is"""
    if color.startswith('#'):
        # Convert hex to RGB tuple
        hex_color = color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
    return color  # Return named colors as-is


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color string to RGB tuple."""
    # Handle named colors
    color_map = {
        "darkviolet": (148, 0, 211),
        "royalblue": (65, 105, 225),
        "forestgreen": (34, 139, 34),
        "black": (0, 0, 0)
    }

    if hex_color in color_map:
        return color_map[hex_color]

    # Handle hex colors
    hex_color = hex_color.removeprefix('#')

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except (ValueError, IndexError):
        # Fallback to black if parsing fails
        return (0, 0, 0)


def _resolve_svg_path(map_name: str = 'standard') -> str:
    """
    Resolve SVG file path based on map name.

    Args:
        map_name: Name of the map variant ('standard')

    Returns:
        Path to the SVG file
    """
    base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
    base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"

    if map_name == 'standard':
        svg_path = base_path
    else:
        # For other variants, try {map_name}.svg
        svg_path = os.path.join(base_dir, f"{map_name}.svg")
        if not os.path.exists(svg_path):
            svg_path = base_path  # Fallback to standard

    return svg_path


def _get_cached_svg_data(
    svg_path: str,
) -> tuple[ET.ElementTree, dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """Get cached SVG data or parse and cache it."""
    global _svg_cache

    if svg_path not in _svg_cache:
        # Resolve SVG path with fallbacks for tests/env
        if not os.path.exists(svg_path):
            fallback = os.environ.get("DIPLOMACY_MAP_PATH")
            if fallback and os.path.exists(fallback):
                svg_path = fallback
            else:
                candidates = [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "maps", "standard.svg")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "tests", "maps", "standard.svg")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "maps", "standard.svg")),
                ]
                for c in candidates:
                    if os.path.exists(c):
                        svg_path = c
                        break
        # Parse SVG and extract coordinates
        # nosec B314 -- svg_path resolves to the bundled repo asset maps/standard.svg,
        # never untrusted input; no defusedxml dependency needed for a trusted local file.
        tree = ET.parse(svg_path)  # nosec B314
        root = tree.getroot()

        # Use jdipNS coordinates -- these are the authoritative coordinate system
        coords = {}
        dislodged_coords: dict[str, tuple[float, float]] = {}
        ns = {'jdipNS': 'svg.dtd'}

        for prov in root.findall('.//jdipNS:PROVINCE', ns):
            name = prov.attrib.get('name')
            unit = prov.find('jdipNS:UNIT', ns)
            if name and unit is not None:
                coords[name.upper()] = (float(unit.attrib.get('x', '0')), float(unit.attrib.get('y', '0')))
            dislodged = prov.find('jdipNS:DISLODGED_UNIT', ns)
            if name and dislodged is not None:
                dislodged_coords[name.upper()] = (float(dislodged.attrib.get('x', '0')), float(dislodged.attrib.get('y', '0')))

        # Cache the parsed data
        _svg_cache[svg_path] = (tree, coords, dislodged_coords)

    return _svg_cache[svg_path]


def get_svg_province_coordinates(svg_path: str) -> dict[str, tuple[float, float]]:
    """
    Parse the SVG file and extract province coordinates for unit placement.
    Returns a dict: {province_name: (x, y)}
    Uses jdipNS coordinates which are the correct coordinate system.
    Optimized with caching to avoid repeated parsing.
    """
    _, coords, _ = _get_cached_svg_data(svg_path)
    return coords


def get_dislodged_unit_coordinates(svg_path: str) -> dict[str, tuple[float, float]]:
    """Return dislodged-unit pixel positions from SVG jdipNS:DISLODGED_UNIT elements."""
    _, _, dislodged_coords = _get_cached_svg_data(svg_path)
    return dislodged_coords


def _get_cached_font(size: int) -> ImageFont.ImageFont:
    """Get cached font or load and cache it."""
    global _font_cache
    if size not in _font_cache:
        try:
            _font_cache[size] = ImageFont.truetype("DejaVuSans-Bold.ttf", size)
        except OSError:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def render_board_png(
    svg_path: str,
    units: dict,
    output_path: str | None = None,
    phase_info: dict | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> bytes:
    """Render board PNG with comprehensive caching for performance optimization."""
    # Local imports: both rendering.legend and rendering.svg_paths import this
    # module's helpers, so the reverse edges (these two calls) have to be resolved
    # at call time to avoid a circular import at module load.
    from .legend import _draw_legend
    from .svg_paths import _color_provinces_by_power_with_transparency

    if svg_path is None:
        raise ValueError("svg_path must not be None")
    # Fallback if provided path does not exist (common in tests)
    try:
        if not os.path.exists(svg_path):
            # Try environment override
            fallback = os.environ.get("DIPLOMACY_MAP_PATH")
            if fallback and os.path.exists(fallback):
                svg_path = fallback
            else:
                # Try common repo locations
                candidates = [
                    os.path.join(os.path.dirname(__file__), "..", "tests", "maps", "standard.svg"),
                    os.path.join(os.path.dirname(__file__), "..", "..", "src", "tests", "maps", "standard.svg"),
                    os.path.join(os.path.dirname(__file__), "..", "..", "maps", "standard.svg"),
                ]
                for c in candidates:
                    c = os.path.abspath(c)
                    if os.path.exists(c):
                        svg_path = c
                        break
    except OSError:
        pass

    # Generate cache key for this map configuration
    cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info)

    # Try to get from cache first
    cached_img = _map_cache.get(cache_key)
    if cached_img is not None:
        # Cache hit - return cached image
        if isinstance(output_path, str) and output_path:
            with open(output_path, 'wb') as f:
                f.write(cached_img)
        return cached_img

    # Cache miss - generate new map
    # Optimize for empty maps (no units) - skip expensive operations
    if not units:
        # For empty maps, just convert SVG to PNG and add phase info
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=1835, output_height=1360)  # type: ignore
        if png_bytes is None:
            raise ValueError("cairosvg.svg2png returned None")
        bg = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore

        # Add phase information if provided
        if phase_info:
            draw = ImageDraw.Draw(bg)
            _draw_phase_info(draw, phase_info, bg.size)

        # Save or return PNG
        if isinstance(output_path, str) and output_path:
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            except OSError:
                pass
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        img_bytes = output.getvalue()

        # Cache the generated image
        _map_cache.put(cache_key, img_bytes)

        return img_bytes

    # Full map generation for maps with units
    # 1. Convert SVG to PNG (background) with EXACT SVG size - NO SCALING
    # The SVG has viewBox="0 0 1835 1360" - use exact size to avoid coordinate scaling issues
    # This gives us 1835x1360 pixels - no scaling, coordinates match exactly
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=1835, output_height=1360)  # type: ignore
    if png_bytes is None:
        raise ValueError("cairosvg.svg2png returned None")
    bg = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore
    draw = ImageDraw.Draw(bg)
    # 2. Get province coordinates (cached)
    coords = get_svg_province_coordinates(svg_path)
    dislodged_coords = get_dislodged_unit_coordinates(svg_path)
    # 3. Get power colors from config
    power_colors = _get_power_colors_dict()
    # Get supply centers set if filtering is enabled
    supply_centers_set = None
    if color_only_supply_centers:
        try:
            supply_centers_set = set(_engine_map().supply_centers)
        except (OSError, ValueError, KeyError):
            supply_centers_set = set()

    # First pass: Color provinces based on power control using proper transparency
    _color_provinces_by_power_with_transparency(bg, units, power_colors, svg_path, supply_center_control, phase_info.get('phase') if phase_info else None, color_only_supply_centers, supply_centers_set)

    # Second pass: Draw units on top
    for power, unit_list in units.items():
        color = power_colors.get(power.upper(), "black")
        for unit in unit_list:
            parts = unit.split()
            if len(parts) != 2:
                continue
            unit_type, prov = parts
            prov = prov.upper()

            # Handle dislodged units
            is_dislodged = prov.startswith("DISLODGED_")
            if is_dislodged:
                original_prov = prov.replace("DISLODGED_", "")
                if original_prov in dislodged_coords:
                    x, y = dislodged_coords[original_prov]
                elif original_prov in coords:
                    # Fallback for maps without DISLODGED_UNIT (e.g. v2 map)
                    x, y = coords[original_prov]
                else:
                    continue
            else:
                if prov not in coords:
                    continue
                x, y = coords[prov]

            # NO SCALING - use SVG coordinates directly
            # All coordinates are now in the same coordinate system (no scaling needed)

            # Get unit specs from config
            unit_specs = _viz_config.get_unit_specs()
            unit_diameter = unit_specs["diameter"]
            r = unit_diameter // 2  # Radius from diameter

            # Convert color to RGB tuple
            rgb_color = _convert_color_to_rgb(color)
            if isinstance(rgb_color, str):
                from PIL import ImageColor
                try:
                    rgb_color = ImageColor.getrgb(rgb_color)
                except ValueError:
                    rgb_color = (128, 128, 128)  # Fallback to gray

            outline_color = (0, 0, 0)  # Black outline
            failure_color = _convert_color_to_rgb(_viz_config.get_color("failure"))
            if isinstance(failure_color, str):
                from PIL import ImageColor
                try:
                    failure_color = ImageColor.getrgb(failure_color)
                except ValueError:
                    failure_color = (255, 0, 0)  # Fallback to red

            if is_dislodged:
                # Draw icon with red outline for dislodged units
                if unit_type == "A":
                    _draw_army_icon(draw, (x, y), rgb_color, failure_color, unit_diameter, bg)
                else:  # F
                    _draw_fleet_icon(draw, (x, y), rgb_color, failure_color, unit_diameter, bg)

                # Add "D" marker in top-right corner
                dislodged_indicator_size = unit_specs["dislodged_indicator_size"]
                dislodged_indicator_offset = unit_specs["dislodged_indicator_offset"]
                indicator_x = x + r - dislodged_indicator_offset[0]
                indicator_y = y - r + dislodged_indicator_offset[1]
                # Draw small circle/square for "D" marker
                indicator_r = dislodged_indicator_size // 2
                draw.ellipse((indicator_x - indicator_r, indicator_y - indicator_r,
                            indicator_x + indicator_r, indicator_y + indicator_r),
                           fill=failure_color,
                           outline=failure_color)
                # Draw "D" text
                dislodged_font = _get_cached_font(dislodged_indicator_size)
                draw.text((indicator_x - indicator_r//2, indicator_y - indicator_r//2), "D",
                        fill="white", font=dislodged_font)
            else:
                # Standard unit: black outline
                if unit_type == "A":
                    _draw_army_icon(draw, (x, y), rgb_color, outline_color, unit_diameter, bg)
                else:  # F
                    _draw_fleet_icon(draw, (x, y), rgb_color, outline_color, unit_diameter, bg)

    # 5. Add phase information to bottom right corner
    if phase_info:
        _draw_phase_info(draw, phase_info, bg.size)

    # 6. Add legend showing power colors
    active_powers = list(units.keys())
    _draw_legend(bg, "initial", active_powers)

    # 7. Save or return PNG
    if isinstance(output_path, str) and output_path:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        except OSError:
            pass
        bg.save(output_path, format="PNG")
    output = BytesIO()
    bg.save(output, format="PNG")
    img_bytes = output.getvalue()

    # Cache the generated image
    _map_cache.put(cache_key, img_bytes)

    return img_bytes


def _draw_phase_info(draw: ImageDraw.ImageDraw, phase_info: dict, image_size: tuple[int, int]) -> None:
    """Draw phase information overlay according to visualization spec.

    Format: "Year Season Phase" (e.g., "1901 Spring Movement")
    Includes phase code (e.g., "S1901M") if available
    Position: top-right corner (per spec)
    Font size: from config (within 14-18 range)
    """
    font_specs = _viz_config.get_font_specs()
    font_size = font_specs["phase_overlay_size"]
    try:
        phase_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
    except OSError:
        phase_font = ImageFont.load_default()

    # Extract phase information
    year = phase_info.get("year", "1901")
    season = phase_info.get("season", "Spring")
    phase = phase_info.get("phase", "Movement")
    phase_code = phase_info.get("phase_code", "")
    turn = phase_info.get("turn", None)

    # Create phase text: "Year Season Phase" format
    phase_text = f"{year} {season} {phase}"

    # Add phase code if available
    if phase_code:
        phase_text = f"{phase_code} - {phase_text}"

    # Add turn number if available and useful
    if turn and turn > 1:
        phase_text = f"{phase_text} (Turn {turn})"

    # Calculate position (top-right corner with padding)
    width, height = image_size
    padding = 15

    # Get text dimensions
    bbox = draw.textbbox((0, 0), phase_text, font=phase_font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Position in top-right corner
    x = width - text_width - padding
    y = padding

    # Draw background rectangle for better readability
    bg_padding = 6
    draw.rectangle([
        x - bg_padding,
        y - bg_padding,
        x + text_width + bg_padding,
        y + text_height + bg_padding
    ], fill=(0, 0, 0, 200))  # Semi-transparent black background (more opaque for readability)

    # Draw phase text in white for contrast
    draw.text((x, y), phase_text, fill="white", font=phase_font)


def preload_common_maps() -> None:
    """Preload common map configurations for better performance."""
    svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")

    # Preload empty map (most common)
    empty_units: dict = {}
    empty_phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }

    try:
        render_board_png(svg_path, empty_units, phase_info=empty_phase_info)
        logger.info("Preloaded empty map")
    except (OSError, ValueError, TypeError) as e:
        logger.warning(f"Could not preload empty map: {e}")

    # Preload starting positions map
    starting_units = {
        "AUSTRIA": ["A VIE", "A BUD", "F TRI"],
        "ENGLAND": ["F LON", "F EDI", "A LVP"],
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN", "F KIE"],
        "ITALY": ["A ROM", "A VEN", "F NAP"],
        "RUSSIA": ["A MOS", "A WAR", "F STP", "A SEV"],
        "TURKEY": ["A CON", "A SMY", "F ANK"]
    }

    try:
        render_board_png(svg_path, starting_units, phase_info=empty_phase_info)
        logger.info("Preloaded starting positions map")
    except (OSError, ValueError, TypeError) as e:
        logger.warning(f"Could not preload starting positions map: {e}")
