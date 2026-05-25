# Fix Plan - Actionable Items

## Overview

This document contains actionable implementation tasks and fixes for the Diplomacy game engine.

**Last Updated**: 2026-05-25

**Test Suite**: ✅ 1029 passing, 20 skipped, 0 failures (v2.7.3)

---

## Active Priorities

### Map Test Coverage (Completed — 2026-05-25, v2.7.3)

Audit of all 11 map-related test files revealed two issues:

**Bug**: `test_real_scenario_map.py` builds the `units` dict in the wrong format —
`{"A PAR": "FRANCE"}` instead of `{"FRANCE": ["A PAR"]}`. All units are silently skipped
by `render_board_png` (iterates chars of "FRANCE" as unit strings), so the test renders
an empty map and still passes because it only checks `len(img_bytes) > 0`.

**Coverage gap**: `test_map_rendering_quality.py` never calls any render function despite
class names suggesting visual testing. Most "map" tests only check data structures.

#### Tasks

1. **Fix `test_real_scenario_map.py`**
   - Replace inverted `units` dict construction (line 42):
     `units[f"{u.unit_type} {u.province}"] = power_name` →
     `units.setdefault(power_name, []).append(f"{u.unit_type} {u.province}")`
   - Add `assert len(img_bytes) > 500_000` (map with 2 units + SC coloring is ~600–900 KB;
     a blank map is ~300 KB — this catches future regressions where units silently disappear)

2. **New file `tests/test_map_real_scenarios.py`** — 5 tests:
   - `test_dislodged_unit_rendering` — regression test for v2.7.0 fix; verifies
     `Map.get_dislodged_unit_coordinates` differs from `get_svg_province_coordinates` for PAR,
     renders a map with `"A DISLODGED_PAR"`, checks PNG 1835×1360
   - `test_full_7_power_initial_state` — all 7 powers + 22 starting units + SC control dict;
     checks PNG dimensions and mode
   - `test_supply_center_capture_rendering` — France captures MUN (no German unit); verifies
     render with updated `supply_center_control` dict
   - `test_real_adjudication_multiple_orders` — France A PAR→BUR + Germany A MUN→BUR (both
     bounce); runs `game.process_turn()`, renders result, asserts correct unit positions
   - `test_order_visualization_with_game_orders` — calls `render_board_png_with_orders` with
     a move + support order for France; asserts PNG 1835×1360

3. **Add rendering to `test_map_rendering_quality.py`**
   - `TestMapRenderingEdgeCases.test_map_with_no_units` → add `render_board_png({})` call
   - `TestMapRenderingEdgeCases.test_map_with_all_units` → build correct units dict, add render call
   - `TestMapVisualizationQuality.test_unit_placement_on_map` → add render call with France units
   - Leave `TestMapRenderingPerformance`, `TestMapFileHandling`, `TestMapGeneration` as-is

#### Files to modify
- `tests/test_real_scenario_map.py`
- `tests/test_map_real_scenarios.py` (new)
- `tests/test_map_rendering_quality.py`

#### Leave alone
- `test_order_visualization.py` — correct format, actually renders, fine
- `test_api_routes_maps.py` — skipped tests require DB setup; keep skipped
- `test_map_and_power.py`, `test_province_mapping.py` — correct scope

#### Verification
```bash
PYTHONPATH=src pytest tests/test_real_scenario_map.py tests/test_map_real_scenarios.py -v
PYTHONPATH=src pytest tests/ -q  # must be 0 failures
```

---

### Map Visualization Fixes (Completed — 2026-05-25, v2.7.0)

Six defects identified in `src/engine/map.py` via code audit. Implementation applies all fixes
in the order listed below.

#### Fix 1 — Use SVG DISLODGED_UNIT coordinates (correctness bug) 🔴
The SVG (`maps/standard.svg`) defines `<jdipNS:DISLODGED_UNIT x="..." y="..."/>` for every
province. The code ignores these and applies a flat `+20, +20` offset twice (lines 1282–1292 +
1326–1328), placing dislodged units at wrong pixel positions.

Changes required:
- `_svg_cache` type annotation → 3-tuple (add `Dict[str, Tuple[float, float]]` for dislodged coords)
- `_get_cached_svg_data` return type → 3-tuple
- Expand jdipNS parsing branch to also read `jdipNS:DISLODGED_UNIT` elements
- Update two callers that unpack the cache tuple (`get_svg_province_coordinates`, `_color_provinces_by_power_with_transparency`)
- Add `get_dislodged_unit_coordinates` static method
- In `render_board_png`: fetch dislodged coords, use them for placement, remove double-offset block
- In `_draw_comprehensive_order_visualization`: add `dislodged_coords=None` param, use SVG coords for retreat arrows
- Update callers in `render_board_png_with_orders` and `render_board_png_resolution`
- Fallback to `dislodged_offset` heuristic for v2 map (no DISLODGED_UNIT elements)

#### Fix 2 — Icon processing cache (performance) 🟡
`_load_and_process_icon` is called per unit per render with no memoization. Contains two
pixel-by-pixel loops; fires ~34× per render.

Changes required:
- Add `_icon_cache: Dict[Tuple[str, Tuple[int, ...], Tuple[int, ...], int], Image.Image] = {}` module global
- At start of `_load_and_process_icon` (after the `os.path.exists` guard): check cache
- Before `return scaled`: store in cache

#### Fix 3 — Font cache for all sizes (performance) 🟡
`_get_cached_font` caches only size 30; all other sizes load fresh each call.

Changes required:
- Change `_font_cache: Optional[ImageFont.ImageFont] = None` → `_font_cache: Dict[int, ImageFont.ImageFont] = {}`
- Rewrite `_get_cached_font` body to use dict lookup

#### Fix 4 — Remove dead redundant supply-center filter (code quality) 🟢
Lines 680–683 in `_color_provinces_by_power_with_transparency` re-check `color_only_supply_centers`
and skip non-SC provinces, but `province_power_map` was already filtered at line 664. Dead code.

Changes required:
- Delete the 4-line block at lines 680–683

#### Fix 5 — Remove dead `_color_provinces_by_power` method (code quality) 🟢
Method at line 736 is defined but never called. Only `_color_provinces_by_power_with_transparency`
is used. The dead method also contains an unnecessary local `import xml.etree.ElementTree as ET`.

Changes required:
- Delete entire method (~103 lines from the `@staticmethod` decorator through closing `except`)

#### Fix 6 — Move polygon extraction inside water-province branch (code quality) 🟢
`polygon_points = Map._extract_polygon_points_from_path(...)` is computed for all provinces
(line 694–695) but only consumed in the `if normalized_id in Map.WATER_PROVINCES:` branch.
Land provinces invoke `_fill_svg_path_with_transform` which re-extracts internally — double work.

Changes required:
- Move the extraction call inside the water-province `if` block

#### Verification
```bash
cd new_implementation
source venv/bin/activate
ruff check src/engine/map.py
pytest tests/ -v -x
pytest tests/ -v -m map
python -c "
from engine.map import Map
import os
svg = os.path.abspath('maps/standard.svg')
dc = Map.get_dislodged_unit_coordinates(svg)
print('Dislodged coords for BUR:', dc.get('BUR'))
print('Total provinces with dislodged coords:', len(dc))
"
```
Expected: ~87 provinces in `dc`, each with SVG-specified offset coordinates (not flat +20/+20).

#### SVG file assessment
`maps/standard.svg` does **not** need modification. The absence of `<path>` elements for
MAO/NAO/NWG/TYS is by design — they are open-ocean provinces, never controlled, never colored.

---

## Out of Scope (do not pursue unless explicitly requested)

- **Tournament feature** (bracket management, tournament bot commands, etc.)
- **Discord implementation** (Discord bot, Discord bridge, cross-platform Discord work)
- **AI-powered analysis** (strategic insights, victory predictions, move recommendations)
- **Observer / spectator mode** (spectator bot commands, observer features beyond existing API)

Existing tournament/spectator/Discord code or APIs may remain for backward compatibility;
no further development unless requested.

---

## Future Enhancements (Optional)

### Phase 3 Telegram Channel Integration
**Goal**: Analytics and insights only — message counts, player activity, engagement metrics.

Tasks:
1. Add `channel_analytics` DB table (`src/engine/database.py`, Alembic migration)
2. Instrument channel posting functions to log analytics events
3. Add API endpoints: `GET /games/{game_id}/channel/analytics` and sub-routes
4. Optional analytics dashboard

*Tournament, spectator, Discord, and AI-powered analysis remain out of scope.*

### Visualization Enhancements (long-term)
- Interactive map features (clickable provinces, tooltips, zoom/pan)
- Enhanced visualization options (3D rendering, map styles, themes)
- Analysis tools (strategic overlays, heatmaps, probability visualizations)

---

## Current Status

**Test Suite**: 550+ passing, 35 skipped (database tests), 0 failures (as of v2.6.9)

**Feature Status**:
- ✅ Core game engine
- ✅ REST API
- ✅ Telegram Bot
- ✅ Telegram Channel Integration (Phase 1 + Phase 2)
- ✅ Database persistence
- ✅ Map visualization (fixes in progress — see above)
- ✅ Standard-v2 Map Integration
- ✅ Documentation

**Code Quality**: strict typing, Ruff compliance, comprehensive test coverage.
