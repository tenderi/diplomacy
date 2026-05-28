# Fix Plan - Actionable Items

## Overview

This document contains actionable implementation tasks and fixes for the Diplomacy game engine.

**Last Updated**: 2026-05-28

**Test Suite**: ✅ 1029 passing, 20 skipped, 0 failures (v2.7.7)

---

## Active Priorities

_No active priorities. See **Future Enhancements** below for optional next work._

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

**Test Suite**: 1029 passing, 20 skipped, 0 failures (as of v2.7.7).

**Feature Status**:
- ✅ Core game engine
- ✅ REST API
- ✅ Telegram Bot
- ✅ Telegram Channel Integration (Phase 1 + Phase 2)
- ✅ Database persistence
- ✅ Map visualization (last fixes shipped in v2.7.0 / v2.7.3)
- ✅ Standard-v2 Map Integration
- ✅ Documentation (consolidated in v2.7.5)
- ✅ Python 3.14 standardization (v2.7.7)

**Code Quality**: strict typing, Ruff compliance, comprehensive test coverage.

---

## Recently completed (see git log for full details)

- **v2.7.7** — Standardize on Python 3.14: `pyproject.toml`, `.python-version`, CI bump 3.13 → 3.14, docs and `install_prerequisites.sh` updated.
- **v2.7.6** — Add Python 3.14 standardization plan to `fix_plan.md`.
- **v2.7.5** — Unify documentation: 46 → 32 markdown files, single `docs/specs/` tree, drop stale snapshots and stub READMEs.
- **v2.7.3** — Map test coverage: fix inverted `units` dict in `test_real_scenario_map.py`, add 5 real-scenario render tests, add concurrent game-id collision fix.
- **v2.7.0** — Map visualization fixes: SVG `DISLODGED_UNIT` coords, icon and font caches, dead-code removal in `src/engine/map.py`.
