# Diplomacy — Comprehensive Codebase Overview

> **Version:** 2.0.0 (new implementation)
> **Language:** Python 3.8+
> **Total lines of Python:** ~46,000 (new implementation)

---

## Table of Contents

1. [High-Level Summary](#1-high-level-summary)
2. [Repository Structure](#2-repository-structure)
3. [New Implementation — Deep Dive](#3-new-implementation--deep-dive)
   - [Game Engine (`src/engine/`)](#31-game-engine-srcengine)
   - [Server & API (`src/server/`)](#32-server--api-srcserver)
   - [Telegram Bot (`src/server/telegram_bot/`)](#33-telegram-bot-srcservertelegram_bot)
   - [Maps & Visualization](#34-maps--visualization)
   - [Database Layer](#35-database-layer)
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
│   │   ├── engine/              # Core game logic
│   │   ├── server/              # FastAPI server + Telegram bot
│   │   └── client.py            # Minimal CLI client
│   ├── tests/                   # ~80 test files
│   ├── maps/                    # SVG maps + .map definition files
│   ├── specs/                   # Design documents & specifications
│   ├── examples/                # Demo scripts
│   ├── infra/                   # Deployment scripts & Terraform
│   ├── alembic/                 # Database migrations (14 versions)
│   ├── docs/                    # User-facing docs
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

The engine is the heart of the system. It implements all Diplomacy game rules without any I/O or framework dependencies.

| File | Lines | Purpose |
|---|---|---|
| `data_models.py` | ~900 | Core dataclasses: `Unit`, `Order`, `GameState`, `PowerState`, `MapData`, `Province`, `TurnState`, `MapSnapshot`. Enums: `OrderType`, `OrderStatus`, `GameStatus`. Order subtypes: `MoveOrder`, `HoldOrder`, `SupportOrder`, `ConvoyOrder`, `RetreatOrder`, `BuildOrder`, `DestroyOrder`. |
| `game.py` | ~1,375 | `Game` class — main game controller. Manages turn processing, order validation, adjudication (move resolution with strength calculation, standoff detection, dislodgement, support cutting), retreat phases, and build/destroy phases. Tracks year/season/phase state machine (`S1901M` → `F1901M` → `F1901R` → `W1901B` → `S1902M` …). |
| `map.py` | ~3,600 | `Map` class — loads map topology from `.map` files, manages provinces, adjacencies (including coast-specific adjacency for fleets), and supply centers. Includes `Province` class and `MapCache` class. Also contains the full **SVG rendering pipeline**: parses SVG map files, overlays unit icons (army/fleet PNGs), draws colored order arrows (moves, supports, convoys), and colors provinces by controlling power. Uses Pillow + CairoSVG. |
| `power.py` | ~70 | `Power` class — represents one of the 7 great powers. Manages units (list of `Unit` objects), home supply centers, controlled supply centers, alive/eliminated status, and build/destroy needs. |
| `order_parser.py` | ~520 | `OrderParser` class — parses human-readable order strings (e.g., `"A PAR - BUR"`, `"F BRE S A PAR - BUR"`, `"F NTH C A LON - BEL"`) into structured `ParsedOrder` / `Order` data model objects. Supports regex patterns for all order types. Includes validation against game state. |
| `order_parser_utils.py` | — | Helper utilities for the order parser (province normalization, fuzzy matching). |
| `order_visualization.py` | ~390 | `OrderVisualizationService` — creates structured visualization data from game state orders, ensuring correct order-to-unit mapping for the map renderer. |
| `province_mapping.py` | ~365 | Province abbreviation → full name mapping (e.g., `"BUR"` → `"Burgundy"`). Covers all 75 provinces: 19 sea, ~20 inland, ~36 coastal. Includes reverse lookup and multi-coast info (Bulgaria, Spain, St. Petersburg). |
| `database.py` | ~540 | SQLAlchemy ORM models: `GameModel`, `UserModel`, `PlayerModel`, `UnitModel`, `OrderModel`, `SupplyCenterModel`, `TurnHistoryModel`, `MapSnapshotModel`, `MessageModel`. Defines all table schemas, relationships, and indexes. Helper functions: `unit_to_dict`, `dict_to_unit`, `order_to_dict`, `dict_to_order`, `create_database_schema`. |
| `database_service.py` | ~950 | `DatabaseService` class — the data access layer (DAL). Full CRUD for all entities: `create_game`, `add_player`, `set_orders`, `process_turn`, `get_game_state`, `get_user_by_telegram_id`, etc. Manages SQLAlchemy sessions and transactions. |
| `strategic_ai.py` | ~530 | `StrategicAI` class — generates orders for automated demo games. Configurable aggression, support probability, convoy usage, etc. Produces proper `Order` objects for any game phase. |
| `visualization_config.py` | — | Configuration for map visualization (colors, sizes, layout). |
| `visualization_config.json` | — | JSON visualization config. |

#### Key Engine Concepts

- **Turn Phases:** The game follows a strict state machine: `Movement → Retreat → Builds` for each season (Spring and Fall).
- **Adjudication:** Move orders are resolved simultaneously. The engine calculates attack/defense strengths, handles standoffs (bounce), cuts to support, convoy disruption, and dislodgement.
- **Multi-coast provinces:** Bulgaria (EC/SC), Spain (NC/SC), and St. Petersburg (NC/SC) have separate coast adjacencies for fleets.
- **Victory condition:** A power controlling 18+ supply centers wins. Alternatively, a game ends when all remaining players agree to a draw.

---

### 3.2 Server & API (`src/server/`)

The server exposes the game engine over HTTP via **FastAPI** and also provides a CLI interface.

| File / Module | Purpose |
|---|---|
| `_api_module.py` / `api.py` | FastAPI application factory. Registers all route modules, initializes DB schema on startup, starts the deadline scheduler background task, mounts static files for the dashboard. |
| `server.py` | `Server` class — CLI-oriented server that manages in-memory games dict. Processes text commands like `CREATE_GAME`, `ADD_PLAYER`, `SET_ORDERS`, `PROCESS_TURN`, `GET_GAME_STATE`. |
| `models.py` | Pydantic response models: `GameStateOut`, `PowerStateOut`, `UnitOut`, `MapSnapshotOut`, `TurnStateOut`. Used for typed API responses. |
| `errors.py` | `ServerError` / `ServerResponse` utility classes with standard error codes: `GAME_NOT_FOUND`, `POWER_NOT_FOUND`, `INVALID_ORDER`, etc. |
| `db_config.py` | Reads `SQLALCHEMY_DATABASE_URL` from environment (defaults to local PostgreSQL). |
| `response_cache.py` | In-memory response cache with TTL, LRU eviction, and invalidation. Used on expensive endpoints (map generation, game state). |
| `daide_protocol.py` | `DAIDEServer` — TCP socket server implementing the DAIDE bot communication protocol. Listens on port 8432, parses DAIDE messages (`HLO`, `ORD`, `GOF`, etc.), maps them to engine operations. |

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

`shared.py` holds singleton instances (`db_service`, `server`), loggers, notification helpers, and the `_state_to_spec_dict` serializer used across all routes.

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

### 3.4 Maps & Visualization

The `maps/` directory contains:

| File | Description |
|---|---|
| `standard.map` | The canonical map definition file. Defines all 75 provinces, their abbreviations/aliases, 7 great powers with home supply centers and starting units, unowned supply centers, and full adjacency lists (including coast-specific adjacency). |
| `standard.svg` | The SVG vector map of Europe used for rendering. Province regions are identified by ID attributes matching abbreviations. |
| `v2.svg` + `v2/` | An alternative "v2" map design with AI-generated assets. |
| `mini_variant.json` | A smaller map variant for testing. |
| `svg.dtd` | SVG DTD for validation. |

**Rendering pipeline:**
1. The `Map` class loads the SVG file
2. Province regions are colored by controlling power (each power has a distinct color)
3. Unit icons (army/fleet PNGs from `icons/`) are placed at province centroids
4. Order arrows are drawn: green for moves, blue for supports, orange for convoys
5. The SVG is rendered to PNG via CairoSVG + Pillow
6. Results are cached via `MapCache` (in-memory + disk at `/tmp/diplomacy_map_cache`)

---

### 3.5 Database Layer

**PostgreSQL** is the production database, accessed via **SQLAlchemy** ORM.

#### Tables (9 total)

| Table | Key Columns | Purpose |
|---|---|---|
| `games` | `game_id`, `map_name`, `current_turn`, `current_year`, `current_season`, `current_phase`, `phase_code`, `status`, `deadline`, `channel_id`, `channel_settings` | Game state and metadata |
| `users` | `telegram_id`, `full_name`, `username`, `is_active` | Telegram users |
| `players` | `game_id` (FK), `user_id` (FK), `power_name`, `is_active` | Player assignments to games |
| `units` | `game_id` (FK), `power`, `unit_type`, `province`, `coast`, `is_dislodged` | Current unit positions |
| `orders` | `game_id` (FK), `power`, `turn`, `order_type`, `unit_type`, `unit_province`, `target_province`, `status` | Submitted and resolved orders |
| `supply_centers` | `game_id` (FK), `province`, `power` | Supply center ownership |
| `turn_history` | `game_id` (FK), `turn_number`, `year`, `season`, `phase`, `orders_json`, `results_json` | Historical turn records |
| `game_snapshots` | `game_id` (FK), `turn_number`, `phase_code`, `units_json`, `supply_centers_json`, `map_image_path` | Map snapshots per phase |
| `messages` | `game_id` (FK), `sender_power`, `recipient_power`, `message_text`, `turn` | In-game messaging |

#### Alembic Migrations (14 versions)

Located in `alembic/versions/`. Key migrations include:
- Initial schema creation
- Adding `deadline` column to games
- Adding channel fields (`channel_id`, `channel_settings`) to games
- Adding `username` column to users
- Changing `telegram_id` to VARCHAR
- Adding `is_active` to users
- Adding game snapshots with phase tracking
- Renaming `power` to `power_name` in players
- Adding units and supply centers tables

---

### 3.6 Tests

**79 test files** covering all layers of the application:

| Category | Example Files | What's Tested |
|---|---|---|
| **Engine / Game Logic** | `test_game.py`, `test_game_module.py`, `test_adjudication.py`, `test_battle_resolution.py`, `test_standoff_detection.py`, `test_convoy_functions.py`, `test_consecutive_phases.py`, `test_supply_center_persistence.py` | Turn processing, order resolution, standoffs, convoys, retreats, builds, victory conditions |
| **Order Parsing** | `test_order_parser.py`, `test_order_parser_utils.py`, `test_enhanced_validation.py` | Parsing all order formats, validation rules |
| **Map** | `test_map_and_power.py`, `test_map_consistency.py`, `test_adjacency_validation.py`, `test_province_mapping.py` | Map loading, adjacency correctness, province mappings |
| **Visualization** | `test_visualization.py`, `test_order_visualization.py`, `test_order_visualization_system.py`, `test_map_with_units.py`, `test_map_opacity_font.py`, `test_standard_v2_map.py` | Map rendering, order arrows, unit placement |
| **API Routes** | `test_api_routes_games.py`, `test_api_routes_orders.py`, `test_api_routes_users.py`, `test_api_routes_messages.py`, `test_api_routes_maps.py`, `test_api_routes_admin.py`, `test_api_routes_dashboard.py`, `test_api_spec_shapes.py` | All REST endpoints, request/response shapes |
| **Database** | `test_database_service.py`, `test_data_models.py` | CRUD operations, model integrity |
| **Telegram Bot** | `test_telegram_bot.py`, `test_telegram_bot_enhanced.py`, `test_telegram_messages.py`, `test_telegram_waiting_list.py`, `test_bot_functions.py`, `test_bot_map_generation.py`, `test_interactive_orders.py`, `test_channel_*` | Bot commands, interactive order flow, channel integration |
| **DAIDE Protocol** | `test_daide_protocol.py`, `test_daide_protocol_enhanced.py` | TCP protocol handling, message parsing |
| **Server** | `test_server.py`, `test_server_advanced.py`, `test_client.py` | CLI server, command processing |
| **Integration** | `test_integration.py`, `test_integration_spec_only.py`, `test_demo_integration.py` | End-to-end game flows |
| **Demo** | `test_demo_game_battles.py`, `test_demo_game_management.py`, `test_demo_order_visualization.py`, `test_strategic_ai.py` | AI strategy, demo game scenarios |
| **Infrastructure** | `test_deployment_infrastructure.py`, `test_remote_environment.py` | Deployment config, environment validation |

**Test fixtures** (`conftest.py`): Provides `standard_game`, `mid_game_state`, `mock_telegram_context`, `mock_telegram_update`, `sample_orders`, `temp_db`, `db_session` fixtures. Auto-initializes DB schema before test collection.

Run with: `pytest tests/ -v` (from `new_implementation/`)

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

The `specs/` directory contains detailed design documents:

| Spec | Description |
|---|---|
| `architecture.md` | System architecture overview |
| `diplomacy_rules.md` / `diplomacy_rules_v2.md` | Complete Diplomacy rules reference |
| `data_spec.md` | Data model specification (what `data_models.py` implements) |
| `provinces_spec.md` | All 75 provinces with types, adjacencies, and multi-coast details |
| `game_phases_design.md` | Phase state machine design |
| `telegram_bot_spec.md` | Telegram bot command specification |
| `telegram_channel_integration.md` | Channel integration design |
| `visualization_spec.md` | Map rendering specification |
| `dashboard.md` | Admin dashboard design |
| `testing_and_validation.md` | Testing strategy |
| `planning.md` / `fix_plan.md` / `documentation_plan.md` | Development planning docs |
| `automated_demo_game_spec.md` | Demo game automation spec |

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
| Game engine | DATC-compliant, monolithic `Game` class | Modular engine with typed data models |
| Database | File-based / in-memory | PostgreSQL with SQLAlchemy |
| Bot protocol | DAIDE (full implementation) | DAIDE (simplified) + REST |
| Maps | Multiple variants (15+ map files) | Standard + mini variant |
| Package | pip-installable (`setup.py`) | Requirements-based |
| Python | 3.5–3.7 | 3.8+ |

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
│            DatabaseService (database_service.py)         │
│  • CRUD for all entities                                 │
│  • Transaction management                                │
│  • Game state serialization/deserialization               │
└───────────────────────┬─────────────────────────────────┘
                        │ SQLAlchemy ORM
                        ▼
┌─────────────────────────────────────────────────────────┐
│              PostgreSQL Database                         │
│  • 9 tables (games, users, players, units, orders,       │
│    supply_centers, turn_history, game_snapshots, msgs)   │
│  • Alembic migrations                                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Game Engine (engine/)                        │
│  • Game — turn processing, adjudication                  │
│  • Map — province topology, SVG rendering                │
│  • Power — player state management                       │
│  • OrderParser — text → Order objects                    │
│  • StrategicAI — automated order generation              │
│  • Data Models — typed dataclasses & enums               │
└─────────────────────────────────────────────────────────┘
```

---

## 6. Key Data Flow

### Creating and Playing a Game

1. **User sends `/start`** in Telegram → bot registers them via `POST /users/register_persistent`
2. **User sends `/games`** → bot calls `GET /games` → shows available games with inline buttons
3. **Admin creates game** → `POST /games` with `map_name` → engine creates `Game` object, DB persists it
4. **User sends `/join`** → bot calls `POST /games/{id}/join` with `telegram_id` and chosen power → player row created in DB
5. **User sends `/order`** → bot shows interactive unit selection keyboard → user picks unit → bot shows possible moves → user picks target → bot calls `POST /games/{id}/orders` with order string
6. **Orders resolve** (manual `/processturn` or automatic deadline expiry) → `POST /games/{id}/process_turn`:
   - Engine loads game state from DB
   - Validates all submitted orders
   - Runs adjudication (strength calculation, bouncing, dislodgement)
   - Updates unit positions, supply center ownership
   - Advances phase (Movement → Retreat → Builds → next season)
   - Saves new state to DB
   - Generates map snapshot
   - Notifies all players via Telegram
7. **User views map** → `/map` command → bot calls `POST /games/{id}/generate_map` → engine renders SVG → returns PNG → bot sends image to chat

### Order Format Examples

```
A PAR - BUR          # Army Paris moves to Burgundy
F BRE H              # Fleet Brest holds
A MAR S A PAR - BUR  # Army Marseilles supports Army Paris → Burgundy
F NTH C A LON - BEL  # Fleet North Sea convoys Army London → Belgium
A MUN R TYR          # Army Munich retreats to Tyrolia
BUILD A PAR          # Build Army in Paris
D F BRE              # Destroy Fleet in Brest
```

---

## 7. Technology Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.8+ |
| **Web Framework** | FastAPI + Uvicorn |
| **Database** | PostgreSQL + SQLAlchemy 2.0 + Alembic |
| **Telegram** | python-telegram-bot 22.x |
| **Data Validation** | Pydantic 2.x + Python dataclasses |
| **Image Rendering** | Pillow + CairoSVG + SVG manipulation |
| **HTTP Client** | httpx + requests |
| **Testing** | pytest + pytest-asyncio + pytest-mock + coverage |
| **Infrastructure** | Terraform (AWS), Docker Compose, systemd |
| **Linting** | Ruff (strict mode) |

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

# Set up PostgreSQL (must be running)
export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/diplomacy_db

# Start the API server
cd src
python -m server._api_module
# → API at http://localhost:8000

# Start the Telegram bot (in another terminal)
export TELEGRAM_BOT_TOKEN=your-bot-token
cd src
python -m server.telegram_bot
```

### Run Tests

```bash
cd new_implementation
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html  # with coverage
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
