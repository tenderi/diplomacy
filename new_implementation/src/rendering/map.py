"""
SVG -> PNG rendering pipeline for the Diplomacy board -- facade module.

This module has zero topology knowledge of its own: province adjacency,
coasts, and supply centers all come from ``engine.map_loader`` (the sole
topology source in the codebase).

The implementation was split (V3 of the Track B post-rewrite cleanup) into
focused modules that hold plain module-level functions, matching
``rendering.order_overlay``'s style:

- ``rendering.cache`` -- ``MapCache`` + the module-level ``_map_cache``.
- ``rendering.board`` -- SVG load/parse, coordinate extraction,
  ``render_board_png``, the phase-info banner, and the small color/power-name
  utilities shared by the other modules.
- ``rendering.svg_paths`` -- province transparency coloring, ocean hatching,
  and the raw SVG polygon/path-fill helpers underneath them. Split out of
  ``board.py`` (not in the plan's original proposed layout) purely to keep
  both files under the ~800-line target -- see that module's docstring.
- ``rendering.overlays`` -- the per-order-type drawing functions
  (``_draw_movement_order``, ``_draw_support_order``, ...) plus
  ``_draw_comprehensive_order_visualization`` and the two render entry points
  that use them, ``render_board_png_orders``/``render_board_png_resolution``.
- ``rendering.arrows`` -- the generic arrow/line/circle primitives
  (``_draw_arrow``, curved/dashed/dotted variants, checkmark/X, star) that
  ``overlays.py`` calls. Split out of ``overlays.py`` for the same reason
  ``svg_paths.py`` was split out of ``board.py`` -- also not in the plan's
  original proposed layout, recorded here and in ``done_fixes.md``.
- ``rendering.legend`` -- the on-image legend + its mini-icon helpers.
- ``rendering.icons`` -- army/fleet icon loading and drawing.

``Map`` here stays as a thin facade re-exporting every one of those functions as
a ``@staticmethod``, so ``Map.render_board_png(...)``, ``Map._draw_arrow(...)``,
etc. keep working unchanged. This is a deliberate choice, not the default:
callers across ``src/server/api/routes/`` and a couple dozen test call sites
reach directly into ``Map._private_method(...)`` (verified by grep before the
split), so deleting the facade and repointing every one of those at seven
different modules would turn a mechanical code-organization move into a test
suite rewrite -- out of scope for this pass. ``Map`` carries no per-instance
topology state and is never instantiated; every method is still a
``@staticmethod`` operating on plain data fed in by the caller.
"""
from __future__ import annotations

import cairosvg  # type: ignore  # noqa: F401 -- re-exported so `patch.object(map_module, "cairosvg")` still works

from .arrows import (
    _draw_arrow,
    _draw_bounce_arrow,
    _draw_circle,
    _draw_circle_at_size,
    _draw_cross,  # noqa: F401
    _draw_curved_arrow,
    _draw_dashed_circle,
    _draw_dashed_line,
    _draw_dotted_arrow,  # noqa: F401
    _draw_dotted_line,
    _draw_failure_x,
    _draw_glowing_circle,  # noqa: F401
    _draw_star,
    _draw_success_checkmark,
    _draw_support_cut_indicator,
    _lighten_color,  # noqa: F401
)
from .board import (
    KNOWN_POWER_NAMES,  # noqa: F401
    _convert_color_to_rgb,
    _draw_phase_info,
    _engine_map,  # noqa: F401
    _get_cached_font,
    _get_cached_svg_data,
    _get_power_colors_dict,  # noqa: F401
    _hex_to_rgb,
    _is_water_province,  # noqa: F401
    _resolve_svg_path,
    get_dislodged_unit_coordinates,
    get_svg_province_coordinates,
    preload_common_maps,
    render_board_png,
)
from .cache import MapCache, _map_cache, clear_map_cache, get_cache_stats  # noqa: F401
from .icons import _draw_army_icon, _draw_fleet_icon, _load_and_process_icon
from .legend import _draw_legend, _draw_mini_arrow, _draw_mini_checkmark, _draw_mini_x
from .overlays import (
    _draw_build_order,
    _draw_comprehensive_order_visualization,
    _draw_conflict_marker,
    _draw_convoy_order,
    _draw_destroy_order,
    _draw_hold_order,
    _draw_movement_order,
    _draw_retreat_order,
    _draw_standoff_indicator,
    _draw_support_order,
    render_board_png_orders,
    render_board_png_resolution,
)
from .svg_paths import (
    _color_provinces_by_power_with_transparency,
    _draw_ocean_pattern,
    _extract_polygon_points_from_path,
    _fill_svg_path,
    _fill_svg_path_direct,
    _fill_svg_path_with_transform,
)

__all__ = ["Map", "MapCache"]


class Map:
    """Namespace for the SVG -> PNG rendering pipeline.

    ``Map`` carries no per-instance topology state -- ``engine.map_loader`` is
    the sole topology source (province adjacency, supply centers, coasts).
    Every method here is a ``@staticmethod`` operating on plain data (unit
    lists, phase info, SVG paths) fed in by the caller; there is nothing left
    to construct, so the class is used purely as a namespace and is never
    instantiated. The actual implementations live in the focused modules
    listed in this file's docstring -- this class just binds them as
    staticmethods so existing callers (``Map.render_board_png(...)``, etc.)
    keep working unchanged.
    """

    # -- SVG / coordinates (rendering.board) --
    _resolve_svg_path = staticmethod(_resolve_svg_path)
    _get_cached_svg_data = staticmethod(_get_cached_svg_data)
    get_svg_province_coordinates = staticmethod(get_svg_province_coordinates)
    get_dislodged_unit_coordinates = staticmethod(get_dislodged_unit_coordinates)
    _get_cached_font = staticmethod(_get_cached_font)
    _hex_to_rgb = staticmethod(_hex_to_rgb)
    _convert_color_to_rgb = staticmethod(_convert_color_to_rgb)
    render_board_png = staticmethod(render_board_png)
    _draw_phase_info = staticmethod(_draw_phase_info)
    preload_common_maps = staticmethod(preload_common_maps)

    # -- Province coloring / SVG path filling (rendering.svg_paths) --
    _color_provinces_by_power_with_transparency = staticmethod(_color_provinces_by_power_with_transparency)
    _extract_polygon_points_from_path = staticmethod(_extract_polygon_points_from_path)
    _fill_svg_path_with_transform = staticmethod(_fill_svg_path_with_transform)
    _draw_ocean_pattern = staticmethod(_draw_ocean_pattern)
    _fill_svg_path_direct = staticmethod(_fill_svg_path_direct)
    _fill_svg_path = staticmethod(_fill_svg_path)

    # -- Cache (rendering.cache) --
    get_cache_stats = staticmethod(get_cache_stats)
    clear_map_cache = staticmethod(clear_map_cache)

    # -- Per-order-type drawing + orders/resolution renders (rendering.overlays) --
    _draw_comprehensive_order_visualization = staticmethod(_draw_comprehensive_order_visualization)
    _draw_movement_order = staticmethod(_draw_movement_order)
    _draw_hold_order = staticmethod(_draw_hold_order)
    _draw_support_order = staticmethod(_draw_support_order)
    _draw_convoy_order = staticmethod(_draw_convoy_order)
    _draw_build_order = staticmethod(_draw_build_order)
    _draw_destroy_order = staticmethod(_draw_destroy_order)
    _draw_retreat_order = staticmethod(_draw_retreat_order)
    _draw_conflict_marker = staticmethod(_draw_conflict_marker)
    _draw_standoff_indicator = staticmethod(_draw_standoff_indicator)
    render_board_png_orders = staticmethod(render_board_png_orders)
    render_board_png_resolution = staticmethod(render_board_png_resolution)

    # -- Generic arrow/line/circle primitives (rendering.arrows) --
    _draw_bounce_arrow = staticmethod(_draw_bounce_arrow)
    _draw_success_checkmark = staticmethod(_draw_success_checkmark)
    _draw_failure_x = staticmethod(_draw_failure_x)
    _draw_support_cut_indicator = staticmethod(_draw_support_cut_indicator)
    _draw_star = staticmethod(_draw_star)
    _draw_arrow = staticmethod(_draw_arrow)
    _draw_circle = staticmethod(_draw_circle)
    _draw_circle_at_size = staticmethod(_draw_circle_at_size)
    _draw_curved_arrow = staticmethod(_draw_curved_arrow)
    _draw_dashed_line = staticmethod(_draw_dashed_line)
    _draw_dotted_line = staticmethod(_draw_dotted_line)
    _draw_dashed_circle = staticmethod(_draw_dashed_circle)

    # -- Legend (rendering.legend) --
    _draw_legend = staticmethod(_draw_legend)
    _draw_mini_arrow = staticmethod(_draw_mini_arrow)
    _draw_mini_checkmark = staticmethod(_draw_mini_checkmark)
    _draw_mini_x = staticmethod(_draw_mini_x)

    # -- Icons (rendering.icons) --
    _load_and_process_icon = staticmethod(_load_and_process_icon)
    _draw_army_icon = staticmethod(_draw_army_icon)
    _draw_fleet_icon = staticmethod(_draw_fleet_icon)
