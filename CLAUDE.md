# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

This repo contains two top-level Python codebases. Almost all work happens in `new_implementation/`.

- `new_implementation/` — **The active codebase (v2.0.0).** This is what runs in production. All edits, tests, and new features belong here. CWD for nearly every command below is this directory.
- `old_implementation/` — A legacy DATC-compliant engine with a websocket server and React UI. **Reference only** — useful for cross-checking adjudication rules (`rules.pdf`, `diplomacy/engine/`) and DAIDE protocol details. Do not modify or wire it into new code.
- `CODEBASE_OVERVIEW.md` — Detailed per-module breakdown maintained at the repo root. Read it when you need depth beyond this file.

## Commands

All commands run from `new_implementation/` with the venv active unless noted.

```bash
# Setup (first time)
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./setup_database.sh                       # creates Postgres user/db and runs migrations

# Run the API server (note: PYTHONPATH=src is required — packages live under src/)
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
# Swagger UI at http://localhost:8000/docs

# Run the Telegram bot (needs the API running)
TELEGRAM_BOT_TOKEN=<token> PYTHONPATH=src python -m server.telegram_bot

# Database migrations
alembic upgrade head
alembic revision -m "describe change"     # autogenerate is NOT used; write the upgrade/downgrade by hand

# Tests
pytest tests/ -v                           # all tests
pytest tests/test_game.py -v               # one file
pytest tests/test_game.py::TestX::test_y   # one test
pytest tests/ -m unit                      # by marker: unit | integration | slow | database | telegram | channels | map | ai | deployment | infrastructure | performance
pytest tests/ --cov=src --cov-report=term-missing

# Lint (Ruff is the only linter; CI enforces it)
ruff check src/
ruff format src/

# Frontend (React + Vite + TypeScript, in frontend/)
cd frontend && npm install && npm run dev  # http://localhost:5173, proxies /auth /games /users to :8000
npm run build                              # outputs to frontend/dist; API serves it at /app when present
npm run test:run                           # Vitest + React Testing Library
```

### Test database

Many tests require `SQLALCHEMY_DATABASE_URL` (or `DIPLOMACY_DATABASE_URL`). Without it, DB-dependent tests **silently skip** — if you expect a test to run and it doesn't, check the env. A `.env` file in `new_implementation/` is picked up automatically via `python-dotenv`.

## Architecture

Five processes/components, all talking to one Postgres database via `DatabaseService`:

```
Telegram Bot ──┐
React SPA ─────┼──► FastAPI (port 8000) ──► DatabaseService ──► Postgres
DAIDE clients ─┘         │                        ▲
                         └── Game Engine ─────────┘ (pure logic, no I/O)
```

### Game engine (`src/engine/`)

The engine is **pure logic with no I/O or framework dependencies**. Everything passes through typed dataclasses defined in `data_models.py` (`Unit`, `Order` + subtypes, `GameState`, `PowerState`, `MapData`, plus `OrderType`/`OrderStatus`/`GameStatus` enums).

- `game.py` — `Game` class. Drives the phase state machine `S1901M → F1901M → F1901R → W1901B → S1902M …`. The adjudicator computes strengths, resolves standoffs, cuts support, handles convoy disruption, and applies dislodgement. Multi-coast provinces (BUL, SPA, STP) have separate coast adjacencies for fleets — check `map.py` before assuming a province has a single adjacency list.
- `map.py` — Loads `.map` files, exposes adjacency/topology, AND owns the SVG → PNG rendering pipeline (Pillow + CairoSVG). Map results are cached in-memory and on disk at `/tmp/diplomacy_map_cache`.
- `order_parser.py` — Parses strings like `A PAR - BUR`, `F BRE S A PAR - BUR`, `F NTH C A LON - BEL`, `BUILD A PAR`, `D F BRE` into `Order` objects. Province normalization uses `province_mapping.py`.
- `database.py` / `database_service.py` — SQLAlchemy models and the DAL. **All non-engine code should go through `DatabaseService`** rather than touching ORM models directly. Schema autoupdates on server startup; new columns can sometimes be added without an Alembic revision, but write one anyway for anything beyond a trivially nullable column.
- `strategic_ai.py` — Order generator for automated demo games. Not a real AI; configurable heuristics only.

### Server (`src/server/`)

FastAPI app assembled in `_api_module.py`:
- Route modules live in `src/server/api/routes/` (`games`, `orders`, `users`, `auth`, `messages`, `maps`, `channels`, `admin`, `dashboard`, `health`, `tournaments`). `shared.py` holds the singleton `db_service`, the `_state_to_spec_dict` serializer, loggers, and the deadline scheduler background task.
- A separate `Server` class in `server.py` provides a text-command CLI surface (`CREATE_GAME`, `ADD_PLAYER`, ...). It's used by tests and DAIDE; the HTTP API does not depend on it.
- `daide_protocol.py` runs a TCP server on port 8432 for DAIDE bots.
- `response_cache.py` provides TTL+LRU caching used by expensive endpoints (map generation, game state).

**Auth has two modes that coexist**: JWT Bearer (browser frontend) and `telegram_id` in the request body (Telegram bot). The dependency `get_current_user_or_telegram` accepts either. Authorization checks (only the assigned user can act for a power) are enforced in route handlers — preserve them when editing.

### Telegram bot (`src/server/telegram_bot/`)

The bot is a thin client over the HTTP API (`api_client.py`). It never talks to the engine or DB directly. Command modules are split by domain: `games.py`, `orders.py`, `messages.py`, `maps.py`, `admin.py`, `channels.py`, `channel_commands.py`, `ui.py`, plus `notifications.py` which runs a small FastAPI server on port 8081 that the main API webhooks into.

### Frontend (`frontend/`)

React 18 + Vite + TypeScript SPA with Tailwind + shadcn/ui. Proxies API calls to `http://localhost:8000` in dev. Routes: `/`, `/login`, `/register`, `/link-telegram`, `/games`, `/games/:id`. To add a shadcn component: `npx shadcn@latest add <component>`.

## Conventions and gotchas

- **`PYTHONPATH=src` is required** to import `server.*` and `engine.*` from `new_implementation/`. Forgetting it produces `ModuleNotFoundError`. Tests handle this via `pytest.ini` (`pythonpath = . src`).
- **Type hints are mandatory** on all new code. Ruff is in strict mode; CI fails on lint errors.
- **Out of scope** unless explicitly requested by the maintainer (see `specs/fix_plan.md`): tournaments, Discord, observer/spectator mode, AI-powered analysis. Existing code in these areas (e.g. `tournaments.py`, `discord_bot/`, `run_discord_bot.py`) is kept for backward compatibility — don't extend it.
- **Specs are load-bearing.** `specs/` holds the source of truth for rules and design (`diplomacy_rules.md`, `provinces_spec.md`, `data_spec.md`, `game_phases_design.md`, `architecture.md`). Update them when behavior changes; `documentation_plan.md` describes the doc workflow.
- **Game rule questions**: cross-check against `old_implementation/rules.pdf` (the official rulebook) and `old_implementation/diplomacy/engine/` (a battle-tested DATC implementation) before changing adjudication logic.
- **Map rendering** requires CairoSVG and optionally Chrome/Selenium for some flows — see `docs/BROWSER_SETUP_INSTRUCTIONS.md`. Tests that need rendering are marked `@pytest.mark.map`.
- **Schema changes**: update `src/engine/database.py`, add an Alembic revision under `alembic/versions/`, add the corresponding method(s) to `DatabaseService`. The schema autoupdater in `_api_module.py` is a safety net, not a substitute for migrations.
