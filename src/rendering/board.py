"""SVG -> PNG board rendering: the map, province tints and unit tokens.

A picture is built in layers, bottom to top, so that order lines can run *under*
the unit tokens and status markers sit *over* them (``rendering.overlays``):

1. ``render_base`` -- the SVG rasterized, provinces tinted by owner/occupant, then
   the province names and the supply-centre markers *over* the tint: both are left
   out of the main raster, so the tint never washes a name out or turns a centre's
   dot into a ghost of a unit token.
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

import copy
import logging
import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO

import cairosvg  # type: ignore
from PIL import Image, ImageDraw, ImageFont

from engine.map_loader import MapData, load_standard_map
from engine.types import ProvinceType

from .antialias import SUPERSAMPLE, antialiased_overlay
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
            # A coast entry is named "stp-nc" in the SVG; units are keyed "STP/NC".
            name = name.upper().replace("-", "/") if name else name
            if name and unit is not None:
                coords[name] = (float(unit.attrib.get("x", "0")), float(unit.attrib.get("y", "0")))
            dislodged = prov.find("jdipNS:DISLODGED_UNIT", ns)
            if name and dislodged is not None:
                dislodged_coords[name] = (float(dislodged.attrib.get("x", "0")), float(dislodged.attrib.get("y", "0")))
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
            if spot is None and "/" in prov:  # a coast the SVG does not know: the province
                spot = coords.get(prov.split("/")[0])
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
            options = retreat_options[unit.province]
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


#: SVG layers drawn over the tint rather than under it (see ``render_base``).
_LABEL_LAYER = "BriefLabelLayer"
_SC_LAYER = "SupplyCenterLayer"
#: An invisible hit-test layer, left out of every raster.
_MOUSE_LAYER = "MouseLayer"
_label_cache: dict[str, Image.Image] = {}


def _strip_layers(svg_path: str, drop: frozenset[str], keep_only: str | None = None) -> bytes:
    """The SVG as bytes without the top-level layers in ``drop`` (or, with
    ``keep_only``, with that one layer and the shared ``<defs>`` alone)."""
    root = copy.deepcopy(_get_cached_svg_data(svg_path)[0].getroot())
    for child in list(root):
        layer = child.attrib.get("id", "")
        tag = child.tag.rsplit("}", 1)[-1]
        if layer in drop or layer == _MOUSE_LAYER or (keep_only and tag != "defs" and layer != keep_only):
            root.remove(child)
    return ET.tostring(root)


def _rasterize(data: bytes) -> Image.Image:
    png = cairosvg.svg2png(bytestring=data, output_width=MAP_WIDTH, output_height=MAP_HEIGHT)  # type: ignore
    if png is None:
        raise ValueError("cairosvg.svg2png returned None")
    return Image.open(BytesIO(png)).convert("RGBA")  # type: ignore


def _label_raster(svg_path: str) -> Image.Image:
    """The province names alone on a transparent canvas (constant, so cached)."""
    if svg_path not in _label_cache:
        _label_cache[svg_path] = _rasterize(_strip_layers(svg_path, frozenset(), keep_only=_LABEL_LAYER))
    return _label_cache[svg_path]


def supply_centre_positions(svg_path: str) -> dict[str, tuple[float, float]]:
    """``{province: (x, y)}`` of the centre of every supply-centre marker."""
    root = _get_cached_svg_data(svg_path)[0].getroot()
    found: dict[str, tuple[float, float]] = {}
    for layer in root:
        if layer.attrib.get("id") != _SC_LAYER:
            continue
        for use in layer:
            ident = use.attrib.get("id", "")
            if ident.startswith("sc_"):
                found[ident[3:].upper()] = (
                    float(use.attrib["x"]) + float(use.attrib.get("width", "20")) / 2,
                    float(use.attrib["y"]) + float(use.attrib.get("height", "20")) / 2,
                )
    return found


def draw_supply_centres(image: Image.Image, svg_path: str, supply_center_control: dict | None) -> None:
    """A small crisp marker per supply centre, over the tint: the owner's colour
    with a dark outline, or plain dark while nobody owns it. Drawn on a
    supersampled layer so the edge is smooth."""
    spec = _viz_config.get_marker_specs()
    owners = {prov.upper(): str(power).upper() for prov, power in (supply_center_control or {}).items()}
    colours = _get_power_colors_dict()
    casing = _viz_config.get_color("casing")
    k = SUPERSAMPLE
    radius, outline = spec["supply_centre_radius"], spec["supply_centre_outline"]
    reach = math.ceil(radius + outline) + 2  # tile half-side, in output pixels
    for prov, (cx, cy) in supply_centre_positions(svg_path).items():
        fill = colours.get(owners.get(prov, ""), casing)
        # A tile on the integer pixel grid, the marker offset inside it by the fraction.
        left, top = int(cx) - reach, int(cy) - reach
        tile = Image.new("RGBA", (2 * reach * k, 2 * reach * k), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        mx, my = (cx - left) * k, (cy - top) * k
        for r, colour in (((radius + outline) * k, casing), (radius * k, fill)):
            draw.ellipse([mx - r, my - r, mx + r, my + r], fill=colour)
        small = tile.resize((2 * reach, 2 * reach), Image.Resampling.LANCZOS)
        image.alpha_composite(small, (left, top))


def render_base(
    svg_path: str,
    units: dict[str, list[str]],
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> Image.Image:
    """Layer 1: the rasterized map with provinces tinted by owner and occupant,
    then the province names and supply-centre markers drawn over the tint."""
    from .svg_paths import _color_provinces_by_power_with_transparency

    svg_path = _resolve_existing_svg(svg_path)
    # The raster is transparent along every province border (~60k pixels). Flatten it
    # onto white, so the borders look the same in every viewer -- a transparent
    # PNG shows them black on a dark Telegram theme.
    bg = Image.new("RGBA", (MAP_WIDTH, MAP_HEIGHT), (255, 255, 255, 255))
    bg.alpha_composite(_rasterize(_strip_layers(svg_path, frozenset({_LABEL_LAYER, _SC_LAYER}))))
    if units or supply_center_control:
        supply_centers_set = set(_engine_map().supply_centers) if color_only_supply_centers else None
        _color_provinces_by_power_with_transparency(
            bg, units, _get_power_colors_dict(), svg_path, supply_center_control, None,
            color_only_supply_centers, supply_centers_set,
        )
    bg.alpha_composite(_label_raster(svg_path))
    draw_supply_centres(bg, svg_path, supply_center_control)
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
