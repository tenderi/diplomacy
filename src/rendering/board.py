"""SVG -> PNG board rendering: the map, province tints and unit tokens.

A picture is built in layers, bottom to top, so that order lines can run *under*
the unit tokens and status markers sit *over* them (``rendering.overlays``):

1. ``render_base`` -- the SVG rasterized, provinces tinted by owner/occupant.
2. (overlay lines, drawn by the caller)
3. ``draw_units`` -- a token per unit; dislodged units on top at their own spot.
4. (overlay markers, drawn by the caller)
5. ``legend.add_footer`` -- phase title and legend in a strip *below* the map,
   so no province is ever covered.

``render_board_png`` is the plain board: 1, 3 and 5, plus the retreat options of
any dislodged unit. Topology comes from ``engine.map_loader``; placement comes
from the SVG's ``jdipNS`` elements (``UNIT`` for a unit, ``DISLODGED_UNIT`` for a
dislodged one -- see ``maps/place_dislodged_anchors.py``).
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO

import cairosvg  # type: ignore
from PIL import Image, ImageFont

from engine.map_loader import MapData, load_standard_map
from engine.types import ProvinceType

from .antialias import antialiased_overlay
from .cache import _map_cache
from .tokens import font, paste_token, rgb, token_radius
from .visualization_config import get_config

logger = logging.getLogger("diplomacy.rendering.map")

MAP_WIDTH, MAP_HEIGHT = 1835, 1360

KNOWN_POWER_NAMES = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})

_engine_map_data: MapData | None = None
_svg_cache: dict[str, tuple[ET.ElementTree, dict[str, tuple[float, float]], dict[str, tuple[float, float]]]] = {}
_viz_config = get_config()


def _engine_map() -> MapData:
    """The engine's topology for the bundled standard map (module-cached)."""
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


def _get_power_colors_dict() -> dict[str, str]:
    return {power: _viz_config.get_power_color(power) for power in KNOWN_POWER_NAMES}


def _hex_to_rgb(colour: str) -> tuple[int, int, int]:
    """Any PIL colour as an RGB tuple; black for one PIL cannot read."""
    try:
        return rgb(colour)
    except ValueError:
        return (0, 0, 0)


def _get_cached_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    return font(size)


def _resolve_existing_svg(svg_path: str) -> str:
    """``svg_path``, or the bundled map when it does not exist (tests pass bare
    relative paths from other working directories)."""
    if os.path.exists(svg_path):
        return svg_path
    fallback = os.environ.get("DIPLOMACY_MAP_PATH")
    if fallback and os.path.exists(fallback):
        return fallback
    bundled = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "maps", "standard.svg"))
    return bundled if os.path.exists(bundled) else svg_path


def _get_cached_svg_data(
    svg_path: str,
) -> tuple[ET.ElementTree, dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    """The parsed SVG plus its unit and dislodged-unit positions, cached per path."""
    if svg_path not in _svg_cache:
        resolved = _resolve_existing_svg(svg_path)
        # nosec B314 -- the bundled repo asset maps/standard.svg, never untrusted input.
        tree = ET.parse(resolved)  # nosec B314
        coords: dict[str, tuple[float, float]] = {}
        dislodged_coords: dict[str, tuple[float, float]] = {}
        ns = {"jdipNS": "svg.dtd"}
        for prov in tree.getroot().findall(".//jdipNS:PROVINCE", ns):
            name = prov.attrib.get("name")
            unit = prov.find("jdipNS:UNIT", ns)
            if name and unit is not None:
                coords[name.upper()] = (float(unit.attrib.get("x", "0")), float(unit.attrib.get("y", "0")))
            dislodged = prov.find("jdipNS:DISLODGED_UNIT", ns)
            if name and dislodged is not None:
                dislodged_coords[name.upper()] = (float(dislodged.attrib.get("x", "0")), float(dislodged.attrib.get("y", "0")))
        _svg_cache[svg_path] = (tree, coords, dislodged_coords)
    return _svg_cache[svg_path]


def get_svg_province_coordinates(svg_path: str) -> dict[str, tuple[float, float]]:
    """``{province: (x, y)}`` -- where a unit in that province is drawn."""
    return _get_cached_svg_data(svg_path)[1]


def get_dislodged_unit_coordinates(svg_path: str) -> dict[str, tuple[float, float]]:
    """``{province: (x, y)}`` -- where a dislodged unit in that province is drawn."""
    return _get_cached_svg_data(svg_path)[2]


# --------------------------------------------------------------------------
# Unit placement
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PlacedUnit:
    power: str
    kind: str
    province: str
    center: tuple[float, float]
    dislodged: bool


def place_units(units: dict[str, list[str]], svg_path: str) -> list[PlacedUnit]:
    """Where each unit of the renderer's ``{power: ["A PAR", "F DISLODGED_SPA"]}``
    map is drawn. A unit whose province the SVG does not know is left out."""
    coords = get_svg_province_coordinates(svg_path)
    dislodged_coords = get_dislodged_unit_coordinates(svg_path)
    placed: list[PlacedUnit] = []
    for power, unit_list in units.items():
        for unit in unit_list:
            parts = unit.split()
            if len(parts) != 2:
                continue
            kind, prov = parts[0].upper(), parts[1].upper()
            dislodged = prov.startswith("DISLODGED_")
            prov = prov.removeprefix("DISLODGED_")
            spot = (dislodged_coords if dislodged else coords).get(prov) or coords.get(prov)
            if spot is not None:
                placed.append(PlacedUnit(power.upper(), kind, prov, spot, dislodged))
    return placed


def draw_units(image: Image.Image, placed: list[PlacedUnit]) -> None:
    """Paste every token; dislodged units last, so they are never under the unit
    that took their place, each with a red ring."""
    for unit in sorted(placed, key=lambda u: u.dislodged):
        paste_token(image, unit.center, unit.kind, _viz_config.get_power_color(unit.power))
    dislodged = [u for u in placed if u.dislodged]
    if not dislodged:
        return
    from .arrows import draw_ring

    width = _viz_config.get_marker_specs()["dislodged_width"] - 1
    with antialiased_overlay(image) as draw:
        for unit in dislodged:
            # White halo, so the ring still reads on Austria's red.
            draw_ring(draw, unit.center, token_radius() + 2, rgb(_viz_config.get_color("failure")), width,
                      casing=(255, 255, 255), casing_width=1.5)


def draw_retreat_options(
    image: Image.Image, placed: list[PlacedUnit], retreat_options: dict[str, list[str]], svg_path: str,
) -> set[str]:
    """Thin dotted lines from each dislodged unit to the provinces it may retreat
    to, ending in a small open circle; a red ✗ beside one with nowhere to go.
    Returns the legend keys used."""
    from .arrows import draw_cross, stroke_path, trim

    coords = get_svg_province_coordinates(svg_path)
    style = _viz_config.get_line_style("dotted")
    casing = rgb(_viz_config.get_color("casing"))
    used: set[str] = set()
    with antialiased_overlay(image) as draw:
        for unit in placed:
            if not unit.dislodged or unit.province not in retreat_options:
                continue
            colour = rgb(_viz_config.get_power_color(unit.power))
            options = [o.split("/")[0] for o in retreat_options[unit.province]]
            if not options:
                x, y = unit.center
                draw_cross(draw, (x + token_radius() + 6, y - token_radius()), 6, rgb(_viz_config.get_color("failure")),
                           3, casing=(255, 255, 255), casing_width=1.5)
                used.add("no_retreat")
                continue
            for dest in options:
                if dest not in coords:
                    continue
                path = trim([unit.center, coords[dest]], token_radius() + 2, 6)
                if not path:
                    continue
                stroke_path(draw, path, colour, 2.5, casing=casing, casing_width=1,
                            dash=(style["dash"], style["gap"]))
                x, y = coords[dest]
                draw.ellipse([x - 6, y - 6, x + 6, y + 6], outline=colour, width=3)
                used.add("retreat_option")
    return used


# --------------------------------------------------------------------------
# Renders
# --------------------------------------------------------------------------


def render_base(
    svg_path: str,
    units: dict[str, list[str]],
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> Image.Image:
    """Layer 1: the rasterized map with provinces tinted by owner and occupant."""
    from .svg_paths import _color_provinces_by_power_with_transparency

    svg_path = _resolve_existing_svg(svg_path)
    png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=MAP_WIDTH, output_height=MAP_HEIGHT)  # type: ignore
    if png_bytes is None:
        raise ValueError("cairosvg.svg2png returned None")
    raster = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore
    # The raster is transparent along every province border (~60k pixels). Flatten it
    # onto white, so the borders look the same in every viewer -- a transparent
    # PNG shows them black on a dark Telegram theme.
    bg = Image.new("RGBA", raster.size, (255, 255, 255, 255))
    bg.alpha_composite(raster)
    if units or supply_center_control:
        supply_centers_set = set(_engine_map().supply_centers) if color_only_supply_centers else None
        _color_provinces_by_power_with_transparency(
            bg, units, _get_power_colors_dict(), svg_path, supply_center_control, None,
            color_only_supply_centers, supply_centers_set,
        )
    return bg


def png_bytes(image: Image.Image, output_path: str | None = None) -> bytes:
    """Encode ``image`` (and write it to ``output_path`` when given)."""
    if isinstance(output_path, str) and output_path:
        directory = os.path.dirname(output_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        image.save(output_path, format="PNG")
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _cached(cache_key: str, output_path: str | None) -> bytes | None:
    cached = _map_cache.get(cache_key)
    if cached is not None and isinstance(output_path, str) and output_path:
        with open(output_path, "wb") as f:
            f.write(cached)
    return cached


def render_board_png(
    svg_path: str,
    units: dict,
    output_path: str | None = None,
    phase_info: dict | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
    retreat_options: dict[str, list[str]] | None = None,
) -> bytes:
    """The board: provinces, units, dislodged units with their retreat options,
    and the footer (phase and the powers on the board)."""
    from .legend import add_footer

    if svg_path is None:
        raise ValueError("svg_path must not be None")
    cache_key = _map_cache._generate_cache_key(
        svg_path, units, phase_info,
        supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers,
        extra={"retreat_options": retreat_options},
    )
    cached = _cached(cache_key, output_path)
    if cached is not None:
        return cached

    bg = render_base(svg_path, units, supply_center_control, color_only_supply_centers)
    placed = place_units(units, svg_path)
    legend_keys: set[str] = set()
    if retreat_options:
        legend_keys |= draw_retreat_options(bg, placed, retreat_options, svg_path)
    draw_units(bg, placed)
    if any(u.dislodged for u in placed):
        legend_keys.add("dislodged_unit")
    image = add_footer(bg, phase_info, legend_keys, sorted({u.power for u in placed}))
    img_bytes = png_bytes(image, output_path)
    _map_cache.put(cache_key, img_bytes)
    return img_bytes


def preload_common_maps() -> None:
    """Render the empty board and the opening position once, so the first real
    request is a cache hit."""
    svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
    phase = {"year": 1901, "season": "SPRING", "phase": "MOVEMENT", "phase_code": "S1901M"}
    opening = {
        "AUSTRIA": ["A VIE", "A BUD", "F TRI"],
        "ENGLAND": ["F LON", "F EDI", "A LVP"],
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN", "F KIE"],
        "ITALY": ["A ROM", "A VEN", "F NAP"],
        "RUSSIA": ["A MOS", "A WAR", "F STP", "A SEV"],
        "TURKEY": ["A CON", "A SMY", "F ANK"],
    }
    for units in ({}, opening):
        try:
            render_board_png(svg_path, units, phase_info=phase)
        except (OSError, ValueError, TypeError) as e:
            logger.warning(f"Could not preload map: {e}")
