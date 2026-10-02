"""``Map``: the renderer's public entry points, as one namespace.

The implementation lives in focused modules:

- ``rendering.board`` -- the SVG raster, province tints, unit placement and tokens,
  and the plain board render.
- ``rendering.overlays`` -- what each order and outcome looks like, and the orders
  and resolution renders.
- ``rendering.arrows`` -- geometry and drawing primitives.
- ``rendering.tokens`` -- unit tokens.
- ``rendering.legend`` -- the footer strip (title and key) under the map.
- ``rendering.order_overlay`` -- engine orders/resolutions to the overlay's dicts.
- ``rendering.cache`` -- the rendered-PNG cache.
"""
from __future__ import annotations

import cairosvg  # type: ignore  # noqa: F401 -- re-exported so `patch.object(map_module, "cairosvg")` still works

from .board import preload_common_maps, render_board_png
from .cache import MapCache, clear_map_cache, get_cache_stats
from .overlays import render_board_png_orders, render_board_png_resolution

__all__ = ["Map", "MapCache"]


class Map:
    """Namespace for the SVG -> PNG pipeline; never instantiated."""

    render_board_png = staticmethod(render_board_png)
    render_board_png_orders = staticmethod(render_board_png_orders)
    render_board_png_resolution = staticmethod(render_board_png_resolution)
    preload_common_maps = staticmethod(preload_common_maps)
    get_cache_stats = staticmethod(get_cache_stats)
    clear_map_cache = staticmethod(clear_map_cache)
