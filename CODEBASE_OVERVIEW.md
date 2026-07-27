# Diplomacy — Comprehensive Codebase Overview

> **Version:** 2.0.0 (new implementation, post engine-rewrite — see
> `new_implementation/docs/specs/fix_plan.md` M0–M7)
> **Language:** Python 3.14
> **Total lines of Python:** ~20,000 in `new_implementation/src/` (post-rewrite; the old
> engine's ~2,300-line persistence layer and ~3,200-line rendering half of `map.py` moved
> to `src/persistence/` and `src/rendering/`, and ~1,180 pre-rewrite bug-enshrining tests
> were deleted along with the old engine)

---

## Table of Contents

1. [High-Level Summary](#1-high-level-summary)
2. [Repository Structure](#2-repository-structure)
3. [New Implementation — Deep Dive](#3-new-implementation--deep-dive)
   - [Game Engine (`src/engine/`)](#31-game-engine-srcengine)
   - [Server & API (`src/server/`)](#32-server--api-srcserver)
   - [Telegram Bot (`src/server/telegram_bot/`)](#33-telegram-bot-srcservertelegram_bot)
   - [Maps & Rendering (`src/rendering/`)](#34-maps--rendering)
   - [Persistence Layer (`src/persistence/`)](#35-persistence-layer)
   - [Tests](#36-tests)
   - [Infrastructure & Deployment](#37-infrastructure--deployment)
   - [Specs & Documentation](#38-specs--documentation)
4. [Old Implementation — Overview](#4-old-implementation--overview)
5. [How Everything Fits Together](#5-how-everything-fits-together)
6. [Key Data Flow](#6-key-data-flow)
7. [Technology Stack](#7-technology-stack)
8. [How to Run](#8-how-to-run)

---

## 1. High-Level Summary

This repository contains a **full implementation of the board game Diplomacy** — the classic 7-player strategy game set in pre-WWI Europe. The project provides:

- A **rules engine** that adjudicates all order types (move, hold, support, convoy, retreat, build, destroy)
- A **REST API server** (FastAPI) for managing games over HTTP
- A **Telegram bot** as the primary user interface, allowing players to create/join games, submit orders interactively, view map images, and send messages
- A **DAIDE protocol server** for connecting AI/bot clients over TCP
- **SVG map rendering** with unit positions, order arrows, and province coloring
- **PostgreSQL persistence** with SQLAlchemy ORM and Alembic migrations
- A **strategic AI** for automated demo games
- Comprehensive **test suite** (~80 test files)
- **Infrastructure-as-code** (Terraform for AWS EC2) and deployment scripts

There are two top-level directories:
- **`new_implementation/`** — The active, modern codebase (v2.0.0). This is what's used in production.
- **`old_implementation/`** — A legacy codebase (DATC-compliant engine with websocket server, React web UI, DAIDE adapter). Preserved for reference.

---

## 2. Repository Structure

```
diplomacy/
├── new_implementation/          # ← Active codebase (v2.0.0)
│   ├── src/
│   │   ├── engine/              # PURE rules core — no I/O, DB, or rendering (stdlib only)
│   │   ├── persistence/         # SQLAlchemy models + DAL (moved out of engine/ in M6)
│   │   ├── rendering/           # SVG→PNG map rendering (moved out of engine/map.py in M6)
│   │   ├── server/              # FastAPI server + Telegram bot + DAIDE + CLI Server
│   │   └── client.py            # Minimal CLI client
│   ├── tests/                   # ~80 top-level files + tests/datc/ (154 DATC cases) +
│   │                             #   tests/engine/ (engine-package unit tests)
│   ├── maps/                    # SVG maps + .map definition files
│   ├── examples/                # Demo scripts
│   ├── infra/                   # Deployment scripts & Terraform
│   ├── alembic/                 # Database migrations (14 versions)
│   ├── docs/                    # User-facing docs + specs/ subdirectory
│   ├── icons/                   # Unit icon PNGs
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── alembic.ini
│   └── VERSION                  # "2.0.0"
│
└── old_implementation/          # ← Legacy codebase (reference)
    ├── diplomacy/
    │   ├── engine/              # Original DATC game engine
    │   ├── server/              # Websocket server
    │   ├── client/              # Async websocket client
    │   ├── web/                 # React web interface
    │   ├── daide/               # DAIDE protocol adapter
    │   ├── maps/                # Map files + SVGs
    │   ├── utils/               # Shared utilities
    │   └── ...
    ├── docs/                    # Sphinx documentation
    ├── rules.pdf                # Official Diplomacy rulebook
    └── setup.py                 # pip-installable package
```

---

## 3. New Implementation — Deep Dive

### 3.1 Game Engine (`src/engine/`)

This is a **from-scratch rewrite** (`docs/specs/fix_plan.md` M0–M7, completed 2026-07-27)
of the original engine, done because the original had order-dependent (non-simultaneous)
adjudication, gave convoyed armies unearned attack strength, had no convoy-paradox
handling, wrong support-cut exemptions, dead-on-arrival coast support, and unvalidated
builds — see `fix_plan.md` §"Why a rewrite" for the itemized defects. The engine package
is **pure**: `stdlib` only, no I/O, no DB, no rendering, no framework dependencies — a
Hypothesis property enforces this isn't just aspirational. Full algorithm writeup:
`docs/specs/adjudication.md`.

| File | Purpose |
|---|---|
| `types.py` | Frozen, hashable dataclasses: `Location` (province + optional coast), `Unit`, `DislodgedUnit`, one class per order kind (`Hold`, `Move`, `SupportHold`, `SupportMove`, `Convoy`, `Retreat`, `Disband`, `Build`, `Waive`), `OrderResult`, `Resolution`, `GameState`. Enums: `UnitKind`, `ProvinceType`, `Season`, `PhaseType`, `OrderType`, `ResultCode`, `GameStatus`. |
| `map_loader.py` | Parses `maps/standard.map` into `MapData` — provinces, types (land/coast/water), coast-first-class adjacency, supply centers, home centers, 1901 starting units. Query API: `adjacent`, `is_adjacent`, `army_moves`, `fleet_moves`, `fleet_locations`. The `.map` file is the **sole** topology source — no hardcoded adjacency/coast tables anywhere in the engine. |
| `orders/parser.py` | One grammar for every order type: coast syntax (`F SPA/SC`), `VIA` convoy, aliases, optional power prefix. `parse_order` / `format_order` round-trip (Hypothesis-checked). |
| `orders/validation.py` | The single validation path, `validate(order, state, map)` — used by `GameService.submit_orders` and by build legality in `adjudicator/adjustments.py`. |
| `adjudicator/movement.py` | The heart of the engine: a **Kruijswijk fixed-point resolver**. Per-order UNRESOLVED/GUESSING/RESOLVED state, recursive resolve with dependency-cycle detection, attack/defend/prevent/hold strengths with the correct support-cut exemptions, convoy paths over surviving fleets (BFS, multi-route support), and cycle-breaking: circular movement succeeds, convoy-entangled cycles apply the **Szykman rule**. Detailed walkthrough: `adjudication.md`. |
| `adjudicator/retreats.py` | `compute_retreat_options` — the single authoritative retreat-legality function (post-resolution occupancy, excludes attacker origin + standoffs); `adjudicate_retreats` — the retreat phase, where simultaneous collisions into one province all disband. |
| `adjudicator/adjustments.py` | Builds/disbands/waives/civil-disorder for the winter adjustment phase; civil-disorder auto-removal follows the rulebook distance rule (farthest from home first, fleet before army, alphabetical tiebreak). |
| `game.py` | `Game` — a frozen snapshot (`map`, `state`, `history`) driving the phase state machine `S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M …`; retreat/adjustment phases inserted only when needed; SC ownership updates after Fall settles; victory at 18 centers. |
| `serialization.py` | Canonical `GameState`/`Order`/`Resolution` ⇄ JSON — the **one** place this conversion happens; used by persistence, the HTTP API, and DAIDE. Round-trip is exact (Hypothesis-checked). |
| `simple_ai.py` | A deliberately dumb heuristic order generator for automated/demo games (not a real AI — out of scope to make it stronger). |
| `province_mapping.py` | The one pre-rewrite module kept as-is: abbreviation → full-name lookup used only for human-facing display (`src/rendering/map.py`, the bot's `orders.py`). Not used by adjudication, which reads province codes straight off `Location`/`MapData`. |

#### Key Engine Concepts

- **Turn Phases:** `S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M …` — retreat and
  adjustment phases are inserted only when a dislodgement or a unit/center-count mismatch
  actually requires them.
- **Adjudication:** All movement-phase orders resolve simultaneously via mutual recursion
  (Kruijswijk's algorithm), not a linear pass — this is what makes interdependent cases
  (beleaguered garrison, head-to-head, circular movement, convoy paradoxes) resolve
  correctly and order-independently. See `docs/specs/adjudication.md`.
- **Multi-coast provinces:** Bulgaria (EC/SC), Spain (NC/SC), and St. Petersburg (NC/SC)
  are first-class `Location(province, coast)` pairs read straight from `standard.map` —
  no separate hardcoded coast tables.
- **Victory condition:** A power controlling ≥18 supply centers wins, checked once per
  year right after Fall ownership updates.
- **Conformance:** 144/154 DATC cases green (`tests/datc/`), 10 documented `xfail`
  hard-tail cases (second-order convoy paradoxes and a few rule-variant edge cases) —
  see `adjudication.md` §11 for exactly which and why.

---

### 3.2 Server & API (`src/server/`)

The server exposes the game engine over HTTP via **FastAPI** and also provides a CLI interface.

| File / Module | Purpose |
|---|---|
| `game_service.py` | **The single entry point from server code into the engine.** `GameService` wraps `engine.game.Game` + `engine.serialization` + `orders/parser.py`/`orders/validation.py` over `GameRepo` persistence: `create_game`, `submit_orders`, `process_turn`, `view` (the GameState-native API response — see `docs/specs/data_spec.md` §4), `last_resolution`, `order_history`. Routes, the CLI `Server`, and DAIDE all go through this — none of them touch engine internals directly. |
| `_api_module.py` / `api.py` | FastAPI application factory. Registers all route modules, initializes DB schema on startup, starts the deadline scheduler background task, mounts static files for the dashboard. |
| `server.py` | `Server` class — CLI-oriented server that manages in-memory games dict. Processes text commands like `CREATE_GAME`, `ADD_PLAYER`, `SET_ORDERS`, `PROCESS_TURN`, `GET_GAME_STATE`, all routed through `GameService`. |
| `models.py` | Pydantic response models used for typed API responses. |
| `errors.py` | `ServerError` / `ServerResponse` utility classes with standard error codes: `GAME_NOT_FOUND`, `POWER_NOT_FOUND`, `INVALID_ORDER`, etc. |
| `db_config.py` | Reads `SQLALCHEMY_DATABASE_URL` from environment (defaults to local PostgreSQL). |
| `response_cache.py` | In-memory response cache with TTL, LRU eviction, and invalidation. Used on expensive endpoints (map generation, game state). |
| `daide_protocol.py` | `DAIDEServer` — TCP socket server implementing the DAIDE bot communication protocol. Listens on port 8432, parses DAIDE messages (`HLO`, `ORD`, `GOF`, etc.), maps them to `GameService` calls. |

#### API Route Modules (`src/server/api/routes/`)

| Route Module | Prefix / Endpoints | Description |
|---|---|---|
| `games.py` | `/games/...` | Create game, list games, get game state, join/quit/replace player, set deadline, process turn, get snapshots/history, waiting list. |
| `orders.py` | `/games/{id}/orders/...` | Submit orders, get current orders, clear orders, get order history, get possible moves. |
| `users.py` | `/users/...` | Register user (Telegram ID), get/update user session, list users. |
| `messages.py` | `/games/{id}/message/...` | Send private message, send broadcast, get messages for a game. |
| `maps.py` | `/games/{id}/generate_map` | Generate PNG map image for current game state with unit positions and order arrows. |
| `channels.py` | `/games/{id}/channel/...` | Link/unlink Telegram channels to games, manage channel settings, post content to channels. |
| `admin.py` | `/admin/...` | Delete all games, manage caches, view system status. Protected by admin token. |
| `dashboard.py` | `/dashboard/...` | Admin dashboard endpoints: service status (systemd), DB table inspection, logs. |
| `health.py` | `/health`, `/health/environment` | Health check, detailed environment info (Python version, file system, DB connectivity). |

`shared.py` holds singleton instances (`db_service`, `game_service`, `server`), loggers, and notification helpers used across all routes.

#### Deadline Scheduler

A background async task (`deadline_scheduler` in `shared.py`) runs on a loop checking for games whose deadline has passed. When a deadline expires, it automatically processes the turn and notifies players via Telegram.

---

### 3.3 Telegram Bot (`src/server/telegram_bot/`)

The Telegram bot is the **primary user interface** for players. It uses the `python-telegram-bot` library (v22.x) and communicates with the FastAPI server via HTTP.

| File | Purpose |
|---|---|
| `config.py` | Bot configuration: token, API URL from environment variables. |
| `api_client.py` | HTTP client (`api_get`, `api_post`) to call the FastAPI backend. Includes `wait_for_api_health` for startup. |
| `games.py` | Game commands: `/start`, `/register`, `/games`, `/join`, `/quit`, `/replace`, `/wait`, `/status`, `/players`. |
| `orders.py` | Order commands: `/order`, `/orders`, `/myorders`, `/clearorders`, `/clear`, `/orderhistory`, `/processturn`. Interactive unit selection and move picking via inline keyboards. |
| `messages.py` | Messaging: `/message`, `/broadcast`, `/messages`. |
| `maps.py` | Map commands: `/map`, `/replay`. Map generation and caching. |
| `admin.py` | Admin commands: `/startdemo`, `/rundemo`, `/debug`. |
| `ui.py` | UI helpers: `/menu`, `/help`, `/rules`, `/examples`. Main menu with inline keyboard buttons. |
| `notifications.py` | Notification system: receives webhook notifications from the API and pushes them to players via Telegram. Runs a small FastAPI app on port 8081. |
| `channels.py` | Channel integration: posting maps, results, and broadcasts to linked Telegram channels. |
| `channel_commands.py` | Channel commands: `/link_channel`, `/unlink_channel`, `/channel_info`, `/channel_settings`. |
| `utils.py` | Shared bot utilities. |

The main entry point (`telegram_bot.py`) wires up all command handlers and callback query handlers, then starts both the Telegram bot polling loop and the notification webhook server in parallel.

---

### 3.4 Maps & Rendering

Topology (`src/engine/map_loader.py`) and rendering (`src/rendering/`) are separate
packages since M6 — the pre-rewrite `engine/map.py` tangled ~400 lines of topology with
~3,200 lines of SVG/PNG rendering; the split is mechanical (same render API, moved
wholesale to `src/rendering/`).

The `maps/` directory contains:

| File | Description |
|---|---|
| `standard.map` | The canonical, **sole** topology source. Defines all 75 provinces, their abbreviations/aliases, 7 great powers with home supply centers and starting units, unowned supply centers, and full adjacency lists (including coast-specific adjacency: `BUL/EC`, `BUL/SC`, `SPA/NC`, `SPA/SC`, `STP/NC`, `STP/SC`). `map_loader.py` is the only reader; `src/engine/` has no other adjacency/coast tables. |
| `standard.svg` | The SVG vector map of Europe used for rendering. Province regions are identified by ID attributes matching abbreviations. |
| `v2.svg` + `v2/` | An alternative "v2" map design with AI-generated assets. |
| `mini_variant.json` | A smaller map variant for testing. |
| `svg.dtd` | SVG DTD for validation. |

`src/rendering/`:

| File | Purpose |
|---|---|
| `map.py` | The renderer: loads the SVG, colors province regions by controlling power, places unit icons (army/fleet PNGs from `icons/`) from a `GameState`-derived view, and — when given order/resolution data — draws colored arrows (`render_board_png_orders` / `render_board_png_resolution`). Renders to PNG via CairoSVG + Pillow, cached in-memory and on disk at `/tmp/diplomacy_map_cache`. |
| `order_overlay.py` | Adapts engine `Order`/`Resolution` objects into the renderer's arrow-primitive dict format — the M7 follow-up that reconnected the M6-stubbed order/resolution map endpoints. |
| `visualization_config.py` / `.json` | Colors, sizes, layout config for rendering. |

---

### 3.5 Persistence Layer (`src/persistence/`)

**PostgreSQL**, accessed via **SQLAlchemy** ORM. Game *state* itself is not a normalized
relational breakdown — see `docs/specs/data_spec.md` for the full rationale and field
list; this section is the summary.

| File | Purpose |
|---|---|
| `database.py` | SQLAlchemy ORM models (`GameModel`, `UserModel`, `PlayerModel`, plus messaging/channel/tournament/spectator models). Moved here from `engine/database.py` in M6 (mechanical package move). |
| `database_service.py` | `DatabaseService` — the DAL for everything **not** engine-coupled: users, players, messages, channels, tournaments, spectators. Game state itself is delegated to `game_repo.py` / `GameService` (§3.2). |
| `game_repo.py` | `GameRepo` — the new-engine game-state repository: `state_json` (the serialized `GameState`), `pending_orders`, `last_resolution`, `order_history`. The **only** persistence path for game state; superseded the old `units`/`orders`/`supply_centers` relational tables (still present in the schema for historical reasons, no longer read or written — see `data_spec.md` §3). |

#### `games` table — the columns that matter for the new engine

| Column | Purpose |
|---|---|
| `state_json` | The serialized `GameState` — authoritative source of truth for the board. |
| `pending_orders` | `{power: [order_str]}`, submitted but not yet adjudicated. |
| `last_resolution` | Most recent `Resolution`, kept for resolution-map rendering. |
| `order_history` | `{turn: {power: [order_str]}}`, appended every `process_turn`; powers `/orders/history`. |

Plus denormalized convenience columns (`map_name`, `current_turn`, `phase_code`,
`status`, `deadline`, `channel_id`, ...) kept in sync for code that doesn't want to parse
`state_json`. Other tables (`users`, `players`, `messages`, `turn_history`,
`map_snapshots`, tournament/channel-analytics tables) are unaffected by the engine
rewrite.

#### Alembic Migrations (26 versions)

Located in `alembic/versions/`. The engine-rewrite additions, in order:
- `a1b2c3d4e5f7` — adds `state_json`/`pending_orders` to `games`; **wipes stored game
  rows** (users/auth kept — game data is explicitly disposable, this was authorized by
  the maintainer as part of the rewrite).
- `b2c3d4e5f6a8` — adds `games.last_resolution` (nullable) for resolution-map rendering.
- `c3d4e5f6a7b9` — adds `games.order_history` (nullable) for the per-turn order-history
  endpoint.

---

### 3.6 Tests

**820 passed, 15 skipped, 10 xfailed** (with a DB — see below) across `tests/` (~58
top-level files), `tests/datc/` (154 DATC conformance cases), and `tests/engine/`
(engine-package unit tests). CI enforces coverage: `--cov-fail-under=57` overall,
`--include='src/engine/*' --fail-under=92` for the engine specifically.

| Category | Location | What's Tested |
|---|---|---|
| **DATC conformance** | `tests/datc/test_datc_6a_basic.py` … `test_datc_6j_civil_disorder.py`, `test_adjudicator_mechanics.py`, `test_properties.py`, `harness.py` | One test per official DATC case (6.A–6.J, ~154 cases), tagged with the `datc` marker; `test_properties.py` is Hypothesis-based (determinism under order-shuffling, unit conservation, ≤1 unit/province, retreat-set correctness). See `docs/specs/adjudication.md`. |
| **Engine unit tests** | `tests/engine/test_types.py`, `test_map_loader.py`, `test_parser.py`, `test_validation.py`, `test_serialization.py`, `test_game.py` (incl. `TestSelfPlaySmoke`, a 7-AI-power multi-year run) | Value types, `.map` topology loading, order grammar round-trips, validation, JSON serialization round-trips, the phase machine. |
| **Game service** | `test_game_service.py`, `test_order_overlay.py` | `GameService` (create/submit/process/view) over `GameRepo`; order/resolution map-overlay adapter. |
| **API Routes** | `test_api_routes_games.py`, `test_api_routes_orders.py`, `test_api_routes_users.py`, `test_api_routes_messages.py`, `test_api_routes_maps.py`, `test_api_routes_admin.py`, `test_api_routes_dashboard.py`, `test_api_spec_shapes.py`, `test_api_games_list.py`, `test_api_parsing_simple.py`, `test_api_scheduler.py` | REST endpoints, request/response shapes against the GameState-native view. |
| **Auth** | `test_auth.py`, `test_authorization.py`, `test_user_registration.py` | JWT + Telegram-id dual auth, per-power authorization checks. |
| **Map rendering** | `test_visualization.py`, `test_order_visualization.py`, `test_map_with_units.py`, `test_map_opacity_font.py`, `test_standard_v2_map.py`, `test_standard_v2_map_comprehensive.py`, `test_map_consistency.py`, `test_province_mapping.py` | Map rendering, order arrows, unit placement, province mapping. |
| **Telegram Bot** | `test_telegram_bot.py`, `test_telegram_bot_enhanced.py`, `test_telegram_bot_edge_cases.py`, `test_telegram_messages.py`, `test_telegram_waiting_list.py`, `test_bot_functions.py`, `test_bot_map_generation.py`, `test_interactive_orders.py`, `test_interactive_orders_simple.py`, `test_channel_*` | Bot commands, interactive order flow, channel integration. |
| **DAIDE Protocol** | `test_daide_protocol.py` | TCP protocol handling, message parsing over `GameService`. |
| **Server / CLI** | `test_server.py`, `test_server_advanced.py`, `test_client.py`, `test_execution_context.py` | CLI `Server` text-command surface, command processing. |
| **Other** | `test_errors.py`, `test_response_cache.py`, `test_tournaments_api.py`, `test_deployment_infrastructure.py`, `test_demo_game_management.py`, `test_demo_integration.py` | Error handling, response caching, tournament endpoints (legacy, out-of-scope for new work), deployment config, demo-game flows. |

**Test fixtures** (`conftest.py`): DB-backed fixtures auto-initialize schema before test
collection. **DB-dependent tests silently skip without `SQLALCHEMY_DATABASE_URL`** set —
a no-DB local run looks falsely green; bring up Postgres and `alembic upgrade head`
first. CI always provides a fresh `postgres:14` container.

Run with: `PYTHONPATH=src python -m pytest tests/ -v` (from `new_implementation/`, venv
active, DB up).

---

### 3.7 Infrastructure & Deployment

#### Scripts (`infra/scripts/`)

| Script | Purpose |
|---|---|
| `start_api_server.py` | Starts the FastAPI server with uvicorn |
| `run_bot_with_logs.sh` | Starts the Telegram bot with logging |
| `setup_test_db.sh` | Creates PostgreSQL test database |
| `reset_database.py` | Drops and recreates all tables |
| `migrate_database.py` | Runs Alembic migrations |
| `add_database_indexes.py` | Adds performance indexes |
| `install_browser_deps.sh` | Installs Chrome/Selenium deps for map rendering |
| `run_tests.sh` / `run_tests_fast.sh` | Test runner scripts |
| `diagnose_bot.sh` | Diagnostic script for troubleshooting the bot |
| `compare_environments.py` | Compares local vs remote environment |
| `fix_sudoers.sh` | Fixes sudo permissions for systemctl |

#### Terraform (`infra/terraform/`)

Provisions a single **AWS EC2** instance (t3.micro) with:
- Security group (SSH + HTTP 8000 + HTTPS 443)
- User data script that installs Python, PostgreSQL, pip dependencies, and sets up systemd services
- State stored in S3 (`diplomacy-bot-test-polarsquad` bucket, `eu-west-1`)

#### Docker

The project supports Docker Compose deployment:
- App container (FastAPI + Telegram bot)
- PostgreSQL container
- Automatic Alembic migrations on startup
- Data persisted in `pgdata` Docker volume

---

### 3.8 Specs & Documentation

The `docs/specs/` directory contains detailed design documents:

| Spec | Description |
|---|---|
| `architecture.md` | System architecture: package boundaries (`engine`/`persistence`/`rendering`/`server`), state persistence, the API view shape. Post-rewrite. |
| `adjudication.md` | **The Kruijswijk fixed-point adjudication algorithm** — strength model, support-cut exemptions, convoy paths, cycle-breaking (circular movement vs. the Szykman rule), retreats, civil disorder, and the documented DATC `xfail` gaps. Written for M7; the reference for anyone touching `src/engine/adjudicator/`. |
| `diplomacy_rules.md` | Complete Diplomacy rules reference (prose; authoritative on rules, silent on algorithm — see `adjudication.md` for the algorithm) |
| `data_spec.md` | Data model specification: engine value types (`types.py`), serialization, persistence (`state_json`/`pending_orders`/`last_resolution`/`order_history`), and the HTTP API view shape. Post-rewrite. |
| `provinces_spec.md` | All 75 provinces with types, adjacencies, and multi-coast details |
| `game_phases_design.md` | Phase state machine design |
| `telegram_bot_spec.md` | Telegram bot command specification |
| `telegram_channel_integration.md` | Channel integration design |
| `visualization_spec.md` | Map rendering specification |
| `dashboard.md` | Admin dashboard design (aspirational, not implemented) |
| `testing_and_validation.md` | Testing strategy |
| `fix_plan.md` | Active development plan and current status |
| `automated_demo_game_spec.md` | Demo game automation spec |
| `browser_client_plan.md` | Browser client + auth design |
| `frontend_ui_framework.md` | Tailwind + shadcn/ui rollout plan |

User-facing docs in `docs/`:
- `TELEGRAM_BOT_COMMANDS.md` — Complete command reference
- `FAQ.md` — Common questions and troubleshooting
- `BROWSER_SETUP_INSTRUCTIONS.md` — Browser automation setup
- `DEVELOPER_GUIDE.md` — Developer onboarding
- `README_postgres.md` — PostgreSQL setup guide

---

## 4. Old Implementation — Overview

The `old_implementation/` directory contains the original open-source Diplomacy engine. It is **not actively used** but preserved for reference.

**Key differences from the new implementation:**

| Aspect | Old | New |
|---|---|---|
| Server protocol | WebSockets (asyncio) | REST API (FastAPI) |
| Client interface | React web UI + Python async client | Telegram bot |
| Game engine | DATC-compliant (via a battle-tested AGPL package), monolithic `Game` class | Independently-rewritten Kruijswijk fixed-point resolver, 144/154 DATC cases green, immutable typed value types (`docs/specs/adjudication.md`) |
| Database | File-based / in-memory | PostgreSQL with SQLAlchemy |
| Bot protocol | DAIDE (full implementation) | DAIDE (simplified) + REST |
| Maps | Multiple variants (15+ map files) | Standard + mini variant |
| Package | pip-installable (`setup.py`) | Requirements-based |
| Python | 3.5–3.7 | 3.14 |

The old implementation includes:
- `diplomacy/engine/` — Original game engine (`game.py`, `map.py`, `power.py`, `message.py`, `renderer.py`)
- `diplomacy/server/` — WebSocket server with user management and game scheduling
- `diplomacy/client/` — Async WebSocket client with connection management
- `diplomacy/web/` — React frontend (55+ JS/JSX files) with map visualization
- `diplomacy/daide/` — Full DAIDE protocol implementation (tokens, clauses, messages)
- `diplomacy/utils/` — 30 utility modules (sorting, parsing, exporting, game checks)
- `diplomacy/maps/` — 15+ map variants including standard, pure, colonial, modern, ancient Mediterranean
- `docs/` — Sphinx documentation (26 .rst files)
- `rules.pdf` — Official Diplomacy rulebook PDF

---

## 5. How Everything Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Users                        │
│              (chat with the bot in Telegram)             │
└───────────────────────┬─────────────────────────────────┘
                        │ Telegram Bot API
                        ▼
┌─────────────────────────────────────────────────────────┐
│              Telegram Bot (telegram_bot.py)              │
│  • Command handlers (/join, /order, /map, /status...)   │
│  • Interactive inline keyboards for order entry          │
│  • Notification webhook server (:8081)                   │
│  • Channel integration (auto-post maps/results)          │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP (api_client.py)
                        ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Server (_api_module.py)             │
│  • REST endpoints (games, orders, users, maps, msgs)     │
│  • Deadline scheduler (auto-processes expired turns)     │
│  • Response cache (TTL-based, in-memory)                 │
│  • Dashboard (admin UI)                                  │
│  • Health checks                                         │
├───────────────────────┬─────────────────────────────────┤
│  DAIDE TCP Server     │  CLI Server (server.py)          │
│  (port 8432)          │  (text commands)                 │
└───────────┬───────────┴──────────┬──────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────┐
│         GameService (server/game_service.py)              │
│  • THE only path from server code into the engine         │
│  • create_game / submit_orders / process_turn / view      │
│  • wraps engine.Game + serialization + parser/validation  │
└───────────────────────┬─────────────────────────────────┘
                        │
            ┌───────────┴────────────┐
            ▼                        ▼
┌───────────────────────┐  ┌──────────────────────────────┐
│  GameRepo               │  │  DatabaseService              │
│  (persistence/            │  │  (persistence/                 │
│   game_repo.py)            │  │   database_service.py)          │
│  state_json/pending_orders/ │  │  users/players/messages/         │
│  last_resolution/            │  │  channels/tournaments             │
│  order_history                │  │  (not engine-coupled)              │
└───────────┬───────────┘  └──────────────┬───────────────┘
            └────────────┬─────────────────┘
                        │ SQLAlchemy ORM
                        ▼
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                         │
│  • games (state_json/pending_orders/last_resolution/     │
│    order_history + denormalized metadata), users,        │
│    players, messages, turn_history, map_snapshots        │
│  • + legacy units/orders/supply_centers tables            │
│    (unused since the engine rewrite — see data_spec.md)   │
│  • Alembic migrations (26 versions)                       │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│         Game Engine (engine/) — stdlib only               │
│  • game.py — phase machine over immutable GameStates      │
│  • adjudicator/movement.py — Kruijswijk fixed-point       │
│    resolver (adjudication.md)                             │
│  • adjudicator/retreats.py / adjustments.py                │
│  • map_loader.py — .map topology (sole adjacency source)   │
│  • orders/parser.py / validation.py — grammar + legality   │
│  • serialization.py — GameState/Order/Resolution <-> JSON  │
│  • simple_ai.py — dumb heuristic order generator           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│         Rendering (rendering/)                            │
│  • map.py — SVG -> PNG, order/resolution arrow overlays   │
│  • order_overlay.py — Order/Resolution -> arrow primitives│
└─────────────────────────────────────────────────────────┘
```

---

## 6. Key Data Flow

### Creating and Playing a Game

1. **User sends `/start`** in Telegram → bot registers them via `POST /users/register_persistent`
2. **User sends `/games`** → bot calls `GET /games` → shows available games with inline buttons
3. **Admin creates game** → `POST /games` with `map_name` → `GameService.create_game` builds `Game.new_standard()` and persists its `state_json`
4. **User sends `/join`** → bot calls `POST /games/{id}/join` with `telegram_id` and chosen power → player row created in DB (unaffected by the engine rewrite)
5. **User sends `/order`** → bot shows interactive unit selection keyboard → user picks unit → bot shows possible moves → user picks target → bot calls `POST /games/{id}/orders` with order string → `GameService.submit_orders` parses + validates it and stores it in `pending_orders`
6. **Orders resolve** (manual `/processturn` or automatic deadline expiry) → `POST /games/{id}/process_turn` → `GameService.process_turn`:
   - Loads `state_json`, parses every power's `pending_orders`
   - Calls `Game.adjudicate(orders)` — the Kruijswijk fixed-point resolver runs for a movement phase, or the retreat/adjustment adjudicator otherwise (see `docs/specs/adjudication.md`)
   - Advances the phase (`S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M …`), updating SC ownership after Fall settles
   - Persists the next `state_json` + `last_resolution`, appends to `order_history`, clears `pending_orders`
   - Notifies all players via Telegram
7. **User views map** → `/map` command → bot calls the map-generation endpoint → `src/rendering/map.py` renders the SVG from the `GameService.view` shape (optionally with order/resolution arrows via `order_overlay.py`) → returns PNG → bot sends image to chat

### Order Format Examples

```
A PAR - BUR           # Army Paris moves to Burgundy
F BRE H                # Fleet Brest holds
A MAR S A PAR - BUR   # Army Marseilles supports Army Paris → Burgundy
F NTH C A LON - BEL    # Fleet North Sea convoys Army London → Belgium
A MUN R TYR             # Army Munich retreats to Tyrolia
BUILD A PAR              # Build Army in Paris
BUILD F STP/SC            # Build Fleet in St. Petersburg (south coast)
D A PAR                    # Disband Army in Paris (retreat failure / adjustment / civil disorder)
```

---

## 7. Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.14 |
| **Web Framework** | FastAPI + Uvicorn |
| **Database** | PostgreSQL + SQLAlchemy 2.0 + Alembic |
| **Telegram** | python-telegram-bot 22.x |
| **Data Validation** | Pydantic 2.x + Python dataclasses |
| **Image Rendering** | Pillow + CairoSVG + SVG manipulation |
| **HTTP Client** | httpx + requests |
| **Testing** | pytest + pytest-asyncio + pytest-mock + coverage + Hypothesis (property-based tests for the engine: determinism, round-trips, invariants) |
| **Infrastructure** | Terraform (AWS), Docker Compose, systemd |
| **Linting** | Ruff (strict mode, pinned version — CI pins to avoid new-release rule-set breakage) |

---

## 8. How to Run

### Quick Start (Development)

```bash
cd new_implementation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL (must be running) and run migrations
export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db
alembic upgrade head

# Start the API server (PYTHONPATH=src is required — packages live under src/)
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
# → API at http://localhost:8000, Swagger UI at /docs

# Start the Telegram bot (in another terminal)
TELEGRAM_BOT_TOKEN=your-bot-token PYTHONPATH=src python -m server.telegram_bot
```

### Run Tests

```bash
cd new_implementation
# DB-dependent tests silently skip without SQLALCHEMY_DATABASE_URL set — a no-DB run
# looks falsely green. Bring up Postgres and `alembic upgrade head` first.
PYTHONPATH=src python -m pytest tests/ -v
PYTHONPATH=src python -m pytest tests/ --cov=src --cov-report=html  # with coverage
PYTHONPATH=src python -m pytest tests/ -m datc  # DATC conformance cases only
```

### Docker Compose

```bash
cd new_implementation
export TELEGRAM_BOT_TOKEN=your-token
docker-compose up --build
# → API at http://localhost:8000
# → PostgreSQL at localhost:5432
```

### Run Demo Game

```bash
cd new_implementation
python examples/demo_perfect_game.py --map standard
```
