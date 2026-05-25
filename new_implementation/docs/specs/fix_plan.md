# Fix Plan - Actionable Items

## Overview

This document contains actionable implementation tasks and fixes for the Diplomacy game engine.

**Last Updated**: 2026-05-25

**Test Suite**: ✅ 1029 passing, 20 skipped, 0 failures (v2.7.3)

---

## Active Priorities

### Standardize on Python 3.14 (Active — planned 2026-05-26)

The project's Python version is declared nowhere except CI. Local dev runs on 3.14.5, CI runs on 3.13, docs claim "3.8+". Standardize on **Python 3.14**.

#### Current discrepancy

| Surface | Current | Target |
|---|---|---|
| Local venv | 3.14.5 (already correct) | 3.14 |
| CI matrix | 3.13 | 3.14 |
| CI security job | 3.13 | 3.14 |
| `CODEBASE_OVERVIEW.md` | "Python 3.8+" (3 places) | "Python 3.14" |
| `docs/LOCAL_DEVELOPMENT.md` | "3.8+", "3.10+ recommended", `python@3.12` | 3.14 |
| `docs/FAQ.md` | "Python 3.8+" | "Python 3.14" |
| `install_prerequisites.sh` | "Python 3.8+" fallback msg; generic `python` package | Explicit `python3.14` / `python@3.14` |
| `pyproject.toml` | (does not exist) | `requires-python = ">=3.14,<3.15"` |
| `.python-version` | (does not exist) | `3.14` |

#### Tasks

1. **Create `new_implementation/pyproject.toml`** declaring project metadata + Python version pin. Minimal content:
   ```toml
   [project]
   name = "diplomacy"
   version = "2.7.5"
   requires-python = ">=3.14,<3.15"

   [tool.ruff]
   target-version = "py314"
   line-length = 100
   ```
   Do **not** migrate `pytest.ini` content into `pyproject.toml` in this task — keep `pytest.ini` as-is (out of scope to consolidate tool configs).

2. **Create `new_implementation/.python-version`** with single line: `3.14` (for pyenv / asdf users).

3. **Update CI** at `new_implementation/.github/workflows/test.yml`:
   - Line 14: `python-version: [3.13]` → `python-version: ['3.14']` (quote to prevent YAML float-parsing)
   - Line 110: `python-version: '3.13'` → `python-version: '3.14'`
   - Do **not** bump GitHub Actions versions in this task (separate cleanup; current uses `setup-python@v4`, `cache@v3`, `upload-artifact@v3`, `github-script@v6`, `codecov-action@v3`)

4. **Update docs to say 3.14**:
   - `CODEBASE_OVERVIEW.md` lines 4, 338, 450: `Python 3.8+` → `Python 3.14`
   - `new_implementation/docs/LOCAL_DEVELOPMENT.md`:
     - Line 9: `Python 3.8+ (3.10+ recommended)` → `Python 3.14`
     - Line 72: `brew install python@3.12` → `brew install python@3.14`
     - Line 85: `python3 --version   # 3.8 or higher` → `python3 --version   # 3.14.x`
   - `new_implementation/docs/FAQ.md` line 26: `Python 3.8+` → `Python 3.14`
   - `CLAUDE.md` setup snippet (Commands → Setup section): add a one-line note "Requires Python 3.14".

5. **Update `install_prerequisites.sh`**:
   - Arch (`install_arch`): `python python-pip` is fine — Arch core repo ships current Python (3.14.x at time of writing). Add a post-install version check: `python3 --version | grep -q 3.14 || echo "WARNING: expected python 3.14"`.
   - Debian/Ubuntu (`install_debian`): replace `python3 python3-pip python3-venv` with `python3.14 python3.14-venv python3-pip`. **Note**: Debian/Ubuntu may require the deadsnakes PPA for python3.14 on older releases — add `sudo add-apt-repository ppa:deadsnakes/ppa -y && sudo apt-get update -qq` before the install on Ubuntu. Test this branch manually before merging.
   - macOS (`install_macos`): `brew install python` → `brew install python@3.14`; `brew upgrade python` → `brew upgrade python@3.14`.
   - Line 72 fallback message: `Python 3.8+` → `Python 3.14`.
   - Verify step (line 79): `python3 --version` → also accept `python3.14 --version` and warn if not 3.14.

6. **Update `new_implementation/README.md`** "Quick start" snippet: `python3 -m venv venv` → `python3.14 -m venv venv` (or add a note "Python 3.14 required; see `pyproject.toml`").

7. **Out of scope for this task** (call out in commit message):
   - Bumping GitHub Actions versions (`setup-python@v4` → `v5`, etc.)
   - Consolidating `pytest.ini` into `pyproject.toml`
   - Adding `[build-system]` table (no build/wheel target right now)
   - Migrating alembic / full ruff config into `pyproject.toml`
   - Adding a Dockerfile — not currently tracked in the repo

#### Files to modify

New files:
- `new_implementation/pyproject.toml`
- `new_implementation/.python-version`

Edits:
- `new_implementation/.github/workflows/test.yml`
- `CODEBASE_OVERVIEW.md`
- `CLAUDE.md`
- `new_implementation/README.md`
- `new_implementation/docs/LOCAL_DEVELOPMENT.md`
- `new_implementation/docs/FAQ.md`
- `new_implementation/install_prerequisites.sh`

#### Compatibility check (already verified — no code action needed)

- All `requirements.txt` deps are working on 3.14.5 locally (1029 tests pass as of v2.7.5).
- No `src/` or `tests/` imports of stdlib modules removed in 3.13 or 3.14 (grepped `imghdr`, `crypt`, `distutils`, `telnetlib`, `cgi`, `nntplib`).
- `psycopg2-binary>=2.9.10` ships 3.14 wheels.
- `cairosvg`, `Pillow>=11`, `numpy>=2`, `selenium>=4.34`, `python-telegram-bot>=22` all support 3.14.

#### Verification

```bash
cd new_implementation
source venv/bin/activate
python --version            # expect 3.14.x
ruff check src/             # expect: All checks passed!
PYTHONPATH=src pytest tests/ -q
# expect: 1029 passed, 20 skipped, 0 failures
```

For the CI bump, push to a feature branch first and confirm the `Test Suite` workflow turns green on 3.14 before merging.

For `install_prerequisites.sh` (Debian/Ubuntu branch), do a dry-run on a fresh Ubuntu 24.04 VM/LXC to confirm the deadsnakes PPA flow works; capture the resulting `python3.14 --version` output in the commit message.

#### Commit / tag

Single commit on `main`, tag `v2.7.7` (v2.7.6 is the plan-addition commit):
```
v2.7.7: standardize on Python 3.14

- Add pyproject.toml declaring requires-python = ">=3.14,<3.15"
- Add .python-version (3.14)
- CI: 3.13 → 3.14 in both test and security jobs
- Docs: replace "Python 3.8+" with "Python 3.14" throughout
- install_prerequisites.sh: pin python3.14 (deadsnakes PPA for Debian/Ubuntu)
```

Then `git tag v2.7.7 && git push origin main --tags`.

---

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

**Test Suite**: 1029 passing, 20 skipped, 0 failures (as of v2.7.3 — see header for the latest).

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
