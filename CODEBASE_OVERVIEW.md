# Diplomacy — Codebase Overview

Per-module reference for the repository. For working conventions and commands see
[`CLAUDE.md`](CLAUDE.md); for design rationale see
[`new_implementation/docs/specs/`](new_implementation/docs/specs/).

A full implementation of the board game **Diplomacy**: a rules engine, a FastAPI REST
server, a Telegram bot (the primary player interface), a React browser client, a DAIDE
protocol server for AI bots, SVG map rendering, PostgreSQL persistence, and Terraform-based
AWS deployment. Python 3.14.

- **`new_implementation/`** — the active codebase, what runs in production.
- **`old_implementation/`** — legacy AGPL codebase (DATC engine, websocket server, React UI,
  full DAIDE adapter, 15+ map variants, `rules.pdf`). Reference only; never copied from.

---

## 1. Repository structure

```
diplomacy/
├── new_implementation/
│   ├── src/
│   │   ├── engine/          # PURE rules core — stdlib only, no I/O
│   │   ├── persistence/     # SQLAlchemy models + DAL
│   │   ├── rendering/       # SVG→PNG map rendering
│   │   ├── server/          # FastAPI + Telegram bot + DAIDE + CLI Server
│   │   └── client.py        # Minimal CLI client
│   ├── tests/               # ~62 top-level files + tests/datc/ + tests/engine/
│   ├── frontend/            # React 18 + Vite + TypeScript SPA
│   ├── maps/                # standard.map (topology) + standard.svg + mini_variant.json
│   ├── examples/            # demo_perfect_game.py + order visualization example
│   ├── infra/               # Terraform (AWS) + operational scripts
│   ├── alembic/             # Database migrations
│   ├── docs/                # User docs + specs/
│   └── icons/               # Unit icon PNGs
└── old_implementation/      # Legacy codebase (reference only)
```

---

## 2. Game engine (`src/engine/`)

A from-scratch rewrite of the original engine, which had order-dependent (non-simultaneous)
adjudication, gave convoyed armies unearned attack strength, no convoy-paradox handling,
wrong support-cut exemptions, dead-on-arrival coast support, and unvalidated builds. The
package is **pure**: stdlib only, no I/O, no DB, no rendering, no framework dependencies —
a Hypothesis property enforces this. Algorithm writeup:
[`docs/specs/adjudication.md`](new_implementation/docs/specs/adjudication.md).

| File | Purpose |
|---|---|
| `types.py` | Frozen, hashable dataclasses: `Location` (province + optional coast), `Unit`, `DislodgedUnit`, one class per order kind (`Hold`, `Move`, `SupportHold`, `SupportMove`, `Convoy`, `Retreat`, `Disband`, `Build`, `Waive`), `OrderResult`, `Resolution`, `GameState`. Enums: `UnitKind`, `ProvinceType`, `Season`, `PhaseType`, `OrderType`, `ResultCode`, `GameStatus`. |
| `map_loader.py` | Parses `maps/standard.map` into `MapData` — provinces, types, coast-first-class adjacency, supply centers, home centers, 1901 starting units, province aliases, and `display_names` (code → full name, from the `=` lines' left-hand side). Query API: `adjacent`, `is_adjacent`, `army_moves`, `fleet_moves`, `fleet_locations`. **The sole topology, alias and display-name source** — no hardcoded tables anywhere in the engine. Note `display_names` is for client *display* only; `aliases` is what the order parser consults, and full names deliberately do not parse. |
| `orders/parser.py` | One grammar for every order type: coast syntax (`F SPA/SC`), `VIA` convoy, aliases, optional power prefix. `parse_order` / `format_order` round-trip (Hypothesis-checked). |
| `orders/validation.py` | The single legality path, `validate(order, state, map)` — used by `GameService.submit_orders` and by build legality in `adjudicator/adjustments.py`. |
| `adjudicator/movement.py` | The heart of the engine: a **Kruijswijk fixed-point resolver**. Per-order UNRESOLVED/GUESSING/RESOLVED state, recursive resolve with dependency-cycle detection, attack/defend/prevent/hold strengths with the correct support-cut exemptions, BFS convoy paths over surviving fleets (multi-route), and cycle-breaking: circular movement succeeds, convoy-entangled cycles apply the **Szykman rule**. |
| `adjudicator/retreats.py` | `compute_retreat_options` — the single authoritative retreat-legality function (post-resolution occupancy, excludes attacker origin and standoffs); `adjudicate_retreats` — the retreat phase, where simultaneous collisions into one province all disband. |
| `adjudicator/adjustments.py` | Builds/disbands/waives/civil disorder for the winter adjustment phase; civil-disorder auto-removal follows the rulebook distance rule (farthest from home first, fleet before army, alphabetical tiebreak). |
| `game.py` | `Game` — a frozen snapshot (`map`, `state`, `history`) driving the phase state machine `S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M …`; retreat/adjustment phases inserted only when needed; SC ownership updates after Fall settles; victory at 18 centers. |
| `serialization.py` | Canonical `GameState`/`Order`/`Resolution` ⇄ JSON — the **one** place this conversion happens; used by persistence, the HTTP API, and DAIDE. Round-trip is exact (Hypothesis-checked). |
| `simple_ai.py` | A deliberately dumb heuristic order generator for automated/demo games. |

**Key concepts**

- **Simultaneity.** All movement-phase orders resolve by mutual recursion, not a linear
  pass — this is what makes beleaguered garrison, head-to-head, circular movement, and
  convoy paradoxes resolve correctly and order-independently.
- **Multi-coast provinces.** Bulgaria (EC/SC), Spain (NC/SC), and St. Petersburg (NC/SC)
  are first-class `Location(province, coast)` pairs read straight from `standard.map`.
- **Victory.** ≥18 supply centers, checked once per year right after Fall ownership updates.
- **Conformance.** 144/154 DATC cases green (`tests/datc/`), 10 documented `xfail`
  hard-tail cases — see `adjudication.md` §11 for exactly which and why.

---

## 3. Persistence (`src/persistence/`)

PostgreSQL via SQLAlchemy. Game *state* is **not** a normalized relational breakdown — see
[`docs/specs/data_spec.md`](new_implementation/docs/specs/data_spec.md) for the rationale
and full field list.

| File | Purpose |
|---|---|
| `database.py` | ORM models (`GameModel`, `UserModel`, `PlayerModel`, plus messaging/channel/tournament/spectator models) and `utcnow_naive()`. |
| `database_service.py` | `DatabaseService` — the DAL for everything **not** engine-coupled: users, players, messages, channels, tournaments, spectators. |
| `game_repo.py` | `GameRepo` — the game-state repository: `state_json`, `pending_orders`, `last_resolution`, `order_history`. The only persistence path for game state; `save_state` takes an `expected_phase_code` and raises `StaleGameError` (→ HTTP 409) on a concurrent write. |

### `games` table — the columns that matter

| Column | Purpose |
|---|---|
| `state_json` | The serialized `GameState` — authoritative source of truth for the board. |
| `pending_orders` | `{power: [order_str]}`, submitted but not yet adjudicated. |
| `last_resolution` | Most recent `Resolution`, kept for resolution-map rendering. |
| `order_history` | `{turn: {power: [order_str]}}`, appended every `process_turn`; powers `/orders/history`. |

Plus denormalized convenience columns (`map_name`, `current_turn`, `phase_code`, `status`,
`deadline`, `channel_id`, ...) kept in sync for code that doesn't want to parse
`state_json`. The legacy `units` / `orders` / `supply_centers` tables remain in the schema
but are **never read or written** — don't add code that touches them.

`waiting_list` (added by migration `g5a1c2d3e4f5`) holds the automatic-matching queue —
`telegram_id` UNIQUE, ordered by `joined_at` — so it survives the bot restart every deploy
performs. It is read and written only through `DatabaseService`'s waiting-list methods, whose
`claim_waiting_list_entries` removes exactly N rows in one transaction before any game is
created.

---

## 4. Rendering (`src/rendering/`) and maps

Topology (`engine/map_loader.py`) and rendering are separate packages; the renderer holds
no topology of its own.

| File | Purpose |
|---|---|
| `map.py` | A thin `Map` facade — staticmethod bindings over the modules below, kept so importers didn't have to change. |
| `board.py`, `svg_paths.py` | SVG loading, province coloring by controlling power, path/coordinate parsing. |
| `overlays.py`, `arrows.py` | Order and resolution overlays: movement/support/convoy/retreat arrows, hold and dislodged markers, status indicators. All four arrow variants share one geometry builder (`_arrow_geometry`) and one barbed-head stroker, and both ends are trimmed clear of the unit icons. |
| `antialias.py` | `PIL.ImageDraw` does no anti-aliasing, so overlays are drawn onto a 3× transparent layer through a coordinate/width-scaling `ScaledDraw` proxy and LANCZOS-downscaled onto the board. The legend and phase banner deliberately bypass it. |
| `icons.py`, `legend.py`, `cache.py` | Unit icons from `icons/`, the context-aware legend, and the in-memory + on-disk (`/tmp/diplomacy_map_cache`) caches. |
| `order_overlay.py` | Adapts engine `Order`/`Resolution` objects into the renderer's arrow-primitive dicts. Merges multi-fleet convoy chains into one entry; `DISLODGED` gets its own status. |
| `view_adapter.py` | Pure helpers turning a `GameService.view` dict into render inputs (`units_for_render`, `phase_info`, `svg_path_for_map_name`). |
| `visualization_config.py` / `.json` | Colors, sizes, line widths, dash patterns, legend layout. |

`maps/` holds `standard.map` (the canonical topology source: 75 provinces, aliases, 7
powers with home centers and starting units, unowned centers, coast-specific adjacency),
`standard.svg` (the rendered base map, province regions identified by ID), `svg.dtd`, and
`mini_variant.json` (a small test variant).

---

## 5. Server (`src/server/`)

| File / Module | Purpose |
|---|---|
| `game_service.py` | **The single entry point from server code into the engine.** `GameService` wraps `engine.game.Game` + `serialization` + `orders/` over `GameRepo`: `create_game`, `submit_orders`, `process_turn`, `view`, `last_resolution`, `order_history`. Routes, the CLI `Server`, and DAIDE all go through this. |
| `_api_module.py` | FastAPI application factory. Registers routes, initializes DB schema on startup, starts the deadline scheduler and the DAIDE listener in `lifespan`, mounts the dashboard and the built frontend at `/app`. |
| `legal_orders.py` | Pure, phase-aware enumeration of every legal order for a power (movement / retreat / build / disband), with no FastAPI or DB imports. Backs `GET /games/{id}/legal_orders/{power}`. |
| `server.py` | `Server` — a text-command surface (`CREATE_GAME`, `ADD_PLAYER`, `SET_ORDERS`, `PROCESS_TURN`, `GET_GAME_STATE`), routed through `GameService`. Used by tests; the HTTP API does not depend on it. |
| `errors.py` | `ServerError` / `ServerResponse` with standard codes: `GAME_NOT_FOUND`, `POWER_NOT_FOUND`, `INVALID_ORDER`, … |
| `db_config.py` | Reads `SQLALCHEMY_DATABASE_URL` from the environment (defaults to local PostgreSQL). |
| `response_cache.py` | In-memory response cache with TTL, LRU eviction, and invalidation, used on expensive endpoints. |
| `daide/` | The DAIDE protocol package — see §6. |
| `dashboard/` | Static HTML/CSS/JS for the admin dashboard served at `/dashboard`. |

### API route modules (`src/server/api/routes/`)

| Module | Endpoints |
|---|---|
| `games.py` | Create/list/get games, join/quit/replace/start, deadline get+set, process turn, snapshots + restore, history, draw vote and concede, spectators. |
| `orders.py` | Submit orders, get current orders, clear orders, order history, order-submission status, legal orders (whole power or per unit). |
| `users.py` | Register (persistent + session), list a user's games. |
| `auth.py` | JWT register/login/token/refresh/me, forgot + reset password, Telegram link code and link/unlink. |
| `messages.py` | Private messages, broadcasts, message history. |
| `maps.py` | Board / orders / resolution PNG generation, per-turn map history, map preview, and `GET /maps/{map}/provinces` — province metadata (full name, type, supply-centre flag, coasts), the one server-side source of display names for both clients. |
| `waiting_list.py` | Automatic game matching: join/leave the queue, queue status. Owns the `waiting_list` table and creates the game itself when the queue fills, claiming exactly seven entries in one transaction first so a failure cannot orphan a game. This used to be an in-memory global in the Telegram bot. |
| `channels.py` | Link/unlink Telegram channels, settings, posting maps, results, broadcasts, timelines, proposals, analytics. |
| `admin.py` | Delete all games, cache management, counts. Requires the admin token. |
| `dashboard.py` | Service status and restart (systemd), log retrieval (`journalctl`), read-only DB table inspection and stats. Requires the admin token. |
| `health.py` | `/health` and `/health/environment`. |
| `tournaments.py` | Legacy tournament endpoints — out of scope, kept for backward compatibility. |

`shared.py` holds the `db_service` / `game_service` singletons, `game_view(game_id)`,
loggers, notification helpers, and the **deadline scheduler**: a background async task that
processes turns whose deadline has passed and notifies players.

### Auth

Two modes coexist: **JWT Bearer** (browser) and **`telegram_id` in the request body**
(Telegram bot). The dependency `get_current_user_or_telegram` accepts either; per-power
authorization is enforced in route handlers.

---

## 6. DAIDE (`src/server/daide/`)

A real implementation of the DAIDE wire protocol, for interoperability with the external
bot ecosystem (DumbBot, Albert, …). Started as an `asyncio.start_server` listener on port
8432 alongside the API process.

| File | Purpose |
|---|---|
| `tokens.py` | The DAIDE byte-level vocabulary as a bidirectional registry; province coverage is asserted against `engine.map_loader`, never a second hardcoded list. |
| `wire.py` | DCSP framing: IM/RM/DM/FM/EM message types over asyncio streams. |
| `clauses.py` | Encode/decode bridge between DAIDE token clauses and `engine.types`; decode reuses `engine.orders.parser`, not a second grammar. |
| `session.py` | `DaideSession` — per-connection protocol state machine: the IM/RM handshake, then NME/IAM/HLO/MAP/MDF/SCO/NOW/SUB/THX/MIS/TME/HST/DRW/ADM/SND dispatch, all through `GameService`. |
| `server.py` | `DaideServer` — the listening socket, lazy game creation on first successful NME, the power/passcode registry, and the `notify_game_processed` broadcast (NOW/ORD/OUT/SLO). |

**Known, permanent limitation:** press content (`PRP`/`ALY`/`XDO` inside `SND`/`FRM`) is
syntax-checked and relayed opaquely, not parsed. Negotiation content is the bots' concern.

---

## 7. Telegram bot (`src/server/telegram_bot/`)

The primary player interface, built on `python-telegram-bot` 22.x. A **thin HTTP client**
— it never touches the engine or DB and never renders maps locally.

| File | Purpose |
|---|---|
| `app.py` / `__main__.py` | Entry point: wires command and callback handlers, then runs the polling loop and the notification server in parallel. |
| `config.py`, `api_client.py` | Token/API-URL config; `api_get`, `api_post`, `api_get_bytes`, `wait_for_api_health`. |
| `game_context.py` | `resolve_game_and_power(user_id, game_id=None)` + `fetch_user_games` — the one place a command figures out which game and power it is acting on. |
| `games.py` | `/start`, `/register`, `/games`, `/join`, `/quit`, `/replace`, `/wait`, `/unwait`, `/status`, `/players`. `/wait` and `/unwait` are thin calls to `/waiting_list/*` — the queue is server state. |
| `orders.py` | `/order`, `/orders`, `/myorders`, `/clearorders`, `/clear`, `/orderhistory`, `/processturn`, `/selectunit` — interactive unit and move selection via inline keyboards driven by `legal_orders`. |
| `messages.py`, `maps.py` | `/message`, `/broadcast`, `/messages`; `/map`, `/viewmap`, `/replay`. |
| `ui.py`, `admin.py` | `/help`, `/rules`, `/examples`, `/refresh` (rebuild the keyboard menu); `/debug`. |
| `help_text.py` | **Every order string shown to a player**, in one module, imported by `ui.py`, `admin.py` and `app.py`. Centralised because the same block was copy-pasted into three modules and all copies drifted into teaching syntax the engine rejects; `tests/test_bot_help_text.py` parses each documented order through the real grammar. |
| `channels.py`, `channel_commands.py` | Posting maps, results, and broadcasts to linked channels; `/link_channel`, `/unlink_channel`, `/channel_info`, `/channel_settings`. |
| `notifications.py` | A small FastAPI app on port 8081 that the main API webhooks into, pushing notifications to players. |

Command reference:
[`docs/TELEGRAM_BOT_COMMANDS.md`](new_implementation/docs/TELEGRAM_BOT_COMMANDS.md).

---

## 8. Frontend (`frontend/`)

React 18 + Vite + TypeScript SPA, Tailwind CSS + shadcn/ui, React Router, React Hook Form +
Zod. Consumes the GameState-native view directly — there is no legacy `powers`-shaped view
to translate. Routes: `/`, `/login`, `/register`, `/link-telegram`, `/games`, `/games/:id`.
Vite proxies API calls to `http://localhost:8000` in dev; `npm run build` outputs to
`dist/`, which FastAPI serves at `/app`. Tests use Vitest + React Testing Library — see
[`frontend/docs/TESTING.md`](new_implementation/frontend/docs/TESTING.md).

The board map is rendered server-side at 1835×1360 but the app column is `max-w-4xl` (896px),
so `components/MapViewer.tsx` wraps the inline image in a button that opens a full-viewport
zoom/pan viewer (wheel/pinch/buttons, 10%–600%, double-click toggles fit ↔ 1:1, `Esc` closes).
Note for tests: jsdom implements neither `PointerEvent` nor `setPointerCapture`, so pointer
tests need the polyfill in `MapViewer.test.tsx` or they silently assert nothing.

---

## 9. Tests

Run with `PYTHONPATH=src python -m pytest tests/ -v` from `new_implementation/` with the
venv active and Postgres up. CI enforces coverage: `--fail-under=60` overall, and
`--include='src/engine/*' --fail-under=92` for the engine.

| Category | Location |
|---|---|
| **DATC conformance** | `tests/datc/test_datc_6a_*.py` … `6j_*.py` (~154 cases, `datc` marker), `test_adjudicator_mechanics.py`, `harness.py`, and `test_properties.py` (Hypothesis: determinism under order-shuffling, unit conservation, ≤1 unit/province, retreat-set correctness). |
| **Engine units** | `tests/engine/` — value types, `.map` topology loading, order grammar round-trips, validation, JSON round-trips, the phase machine, plus a 7-AI-power self-play smoke run. |
| **Game service** | `test_game_service.py` (including resolution maps across every phase), `test_order_overlay.py`, `test_view_adapter.py`, `test_legal_orders.py`. |
| **API routes** | `test_api_routes_*.py`, `test_api_spec_shapes.py`, `test_api_games_list.py`, `test_api_scheduler.py`, `test_api_routes_draw_vote.py`. |
| **Auth** | `test_auth.py`, `test_authorization.py`, `test_user_registration.py`. |
| **Rendering** | `test_visualization.py`, `test_order_visualization.py`, `test_map_with_units.py`, `test_map_opacity_font.py` (`map` marker). |
| **Telegram bot** | `test_telegram_*.py`, `test_game_context.py`, `test_selectunit_phases.py`, `test_interactive_orders*.py`, `test_bot_map_generation.py`, `test_channel_*.py`. |
| **DAIDE** | `test_daide_tokens.py`, `test_daide_wire.py`, `test_daide_clauses.py`, `test_daide_session.py`, `test_daide_server.py` (including an end-to-end raw-socket test over one continuous TCP connection). |
| **Server / persistence / other** | `test_server*.py`, `test_client.py`, `test_execution_context.py`, `test_persistence_database_service.py`, `test_errors.py`, `test_response_cache.py`, `test_deployment_infrastructure.py`, `test_demo_*.py`. |

**DB-dependent tests skip silently without `SQLALCHEMY_DATABASE_URL`** — a no-DB local run
looks falsely green. CI always provides a fresh `postgres:14` container.

---

## 10. Infrastructure

`infra/terraform/` provisions one `t3.micro` EC2 in eu-north-1 (nginx + uvicorn +
Telegram bot + postgresql-16), with secrets in SSM Parameter Store and state in S3. Deploys
run from GitHub Actions over OIDC + `ssm send-command`. Full walkthrough:
[`infra/terraform/README.md`](new_implementation/infra/terraform/README.md).

`infra/scripts/` holds `deploy.sh`, `refresh-env.sh`, `start_api_server.py`,
`run_bot_with_logs.sh`, `setup_test_db.sh`, `reset_database.py`, `migrate_database.py`,
`add_database_indexes.py`, `diagnose_bot.sh` + `BOT_TROUBLESHOOTING.md`, `fix_sudoers.sh`,
`compare_environments.py`, and the test runners.

---

## 11. Key data flow

**Playing a game**

1. `/start` in Telegram → `POST /users/persistent_register`.
2. `POST /games/create` with `map_name` → `GameService.create_game` builds
   `Game.new_standard()` and persists its `state_json`.
3. `/join` → `POST /games/{id}/join` → a row in `players` (never engine-coupled).
4. `/selectunit` → bot fetches `GET /games/{id}/legal_orders/{power}` → inline keyboards →
   `POST /games/set_orders` → `GameService.submit_orders` parses and validates, stores into
   `pending_orders`.
5. `/processturn` or deadline expiry → `POST /games/{id}/process_turn` →
   `GameService.process_turn` loads `state_json`, parses every power's pending orders, calls
   `Game.adjudicate(orders)`, advances the phase, persists the next `state_json` +
   `last_resolution`, appends `order_history`, clears `pending_orders`, and notifies players.
6. `/map` → map endpoint → `src/rendering/` renders the SVG from the `GameService.view`
   shape (optionally with order/resolution arrows) → PNG back to the chat.

**Order format**

```
A PAR - BUR            # Army Paris moves to Burgundy
F BRE H                # Fleet Brest holds
A MAR S A PAR - BUR    # Army Marseilles supports Army Paris → Burgundy
F NTH C A LON - BEL    # Fleet North Sea convoys Army London → Belgium
A LON - BEL VIA        # Move explicitly via convoy
A MUN R TYR            # Army Munich retreats to Tyrolia
BUILD A PAR            # Build Army in Paris
BUILD F STP/SC         # Build Fleet in St. Petersburg (south coast)
D A PAR                # Disband Army in Paris
WAIVE                  # Waive a build
```

---

## 12. Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.14 |
| Web framework | FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy 2.0 + Alembic |
| Telegram | python-telegram-bot 22.x |
| Validation | Pydantic 2.x + Python dataclasses |
| Rendering | Pillow + CairoSVG |
| HTTP client | httpx + requests |
| Testing | pytest, pytest-asyncio, pytest-mock, coverage, Hypothesis (engine properties) |
| Frontend | React 18, Vite, TypeScript, Tailwind, shadcn/ui, Vitest, React Testing Library |
| Infrastructure | Terraform (AWS), systemd, nginx |
| Linting | Ruff (strict, pinned version — CI pins to avoid new-release rule-set breakage) |

---

## 13. Old implementation

`old_implementation/` is the original open-source engine, preserved for reference and
**not actively used**. It contains `diplomacy/engine/` (DATC-compliant `Game`, `map`,
`power`, `renderer`), `diplomacy/server/` (websocket server), `diplomacy/client/`,
`diplomacy/web/` (React UI), `diplomacy/daide/` (full DAIDE implementation),
`diplomacy/maps/` (15+ variants), Sphinx docs, and `rules.pdf` — the official rulebook, and
the authority for any rules question.

| Aspect | Old | New |
|---|---|---|
| Server protocol | WebSockets (asyncio) | REST (FastAPI) + DAIDE TCP |
| Client | React web UI + Python async client | Telegram bot + React SPA |
| Engine | DATC-compliant, monolithic mutable `Game` | Kruijswijk fixed-point resolver, frozen value types |
| Database | File-based / in-memory | PostgreSQL + SQLAlchemy |
| Maps | 15+ variants | `standard` only |
| Python | 3.5–3.7 | 3.14 |
| License | AGPL-3.0 | none (do not copy from `old_implementation`) |
