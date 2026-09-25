# Diplomacy — Codebase Overview

Per-module reference for the repository. For working conventions and commands see
[`CLAUDE.md`](CLAUDE.md); for design rationale see
[`docs/specs/`](docs/specs/).

A full implementation of the board game **Diplomacy**: a rules engine, a FastAPI REST
server, a Telegram bot (the primary player interface), a React browser client, a DAIDE
protocol server for AI bots, SVG map rendering, PostgreSQL persistence, and a single-host
Docker deployment (Postgres, API, bot and web on one VPS, deployed on every green merge).
Python 3.14.

The code is a rewrite; the map data (`maps/standard.map`, `maps/standard.svg`) is adapted
from Philip Paquette's `diplomacy` package, so the project is licensed, like that one, under
the **GNU AGPL, version 3 or later** (`LICENSE`; see the README).

---

## 1. Repository structure

```
diplomacy/
├── src/
│   ├── engine/          # PURE rules core — stdlib only, no I/O
│   ├── persistence/     # SQLAlchemy models + DAL
│   ├── rendering/       # SVG→PNG map rendering
│   └── server/          # FastAPI + Telegram bot + DAIDE + CLI Server
├── tests/               # top-level test files + tests/datc/ + tests/engine/
├── frontend/            # React 18 + Vite + TypeScript SPA
├── maps/                # standard.map (topology) + standard.svg
├── docker/              # api / bot / web / docs Dockerfiles, nginx configs, Caddyfile
├── .github/workflows/   # test.yml (the required checks), deploy.yml (deploy on merge)
├── alembic/             # Database migrations
├── docs/                # User docs + specs/ + reference/rules.pdf
├── icons/               # Unit icon PNGs
├── docker-compose.yml   # the production stack; install.sh, ensure_env.sh, upgrade.sh,
│                        #   backup.sh, harden_host.sh operate it (docs/DEPLOYMENT.md)
├── mkdocs.yml           # the docs site (docs/ as a website)
├── README.md, LICENSE (AGPL-3.0-or-later), CLAUDE.md, CODEBASE_OVERVIEW.md
```

---

## 2. Game engine (`src/engine/`)

The package is **pure**: stdlib only, no I/O, no DB, no rendering, no framework dependencies —
`tests/engine/test_purity.py` checks every import. Algorithm writeup:
[`docs/specs/adjudication.md`](docs/specs/adjudication.md).

| File | Purpose |
|---|---|
| `types.py` | Frozen, hashable dataclasses: `Location` (province + optional coast), `Unit`, `DislodgedUnit`, one class per order kind (`Hold`, `Move`, `SupportHold`, `SupportMove`, `Convoy`, `Retreat`, `Disband`, `Build`, `Waive`), `OrderResult`, `Resolution`, `GameState`. Enums: `UnitKind`, `ProvinceType`, `Season`, `PhaseType`, `OrderType`, `ResultCode`, `GameStatus`. |
| `map_loader.py` | Parses `maps/standard.map` into `MapData` — provinces, types, coast-first-class adjacency, supply centers, home centers, 1901 starting units, province aliases, and `display_names` (code → full name, from the `=` lines' left-hand side). Query API: `is_adjacent`, `army_moves`, `fleet_moves`, `fleet_locations`, `coasts_of`, `province_type`. **The sole topology, alias and display-name source** — no hardcoded tables anywhere in the engine. Note `display_names` is for client *display* only; `aliases` is what the order parser consults, and full names deliberately do not parse. |
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
[`docs/specs/data_spec.md`](docs/specs/data_spec.md) for the rationale
and full field list.

| File | Purpose |
|---|---|
| `database.py` | ORM models (`GameModel`, `UserModel`, `PlayerModel`, plus messaging/channel/tournament/spectator models) and `utcnow_naive()`. |
| `database_service.py` | `DatabaseService` — the DAL for everything **not** engine-coupled: users, players, messages, channels, tournaments, spectators. |
| `game_repo.py` | `GameRepo` — the game-state repository: `state_json`, `pending_orders`, `last_resolution`, `order_history`. The only persistence path for game state; `save_state` and `update_state_json` take an `expected_phase_code`, checked on a row locked `FOR UPDATE`, and raise `StaleGameError` (→ HTTP 409) on a concurrent write. |

### `games` table — the columns that matter

| Column | Purpose |
|---|---|
| `state_json` | The serialized `GameState` — authoritative source of truth for the board. |
| `pending_orders` | `{power: [order_str]}`, submitted but not yet adjudicated. |
| `last_resolution` | Most recent `Resolution`, kept for resolution-map rendering. |
| `order_history` | `{turn: {power: [order_str]}}`, appended every `process_turn`; powers `/orders/history`. |

Plus denormalized convenience columns (`map_name`, `current_turn`, `phase_code`, `status`,
`deadline`, `channel_id`, ...) kept in sync for code that doesn't want to parse
`state_json`. There are no relational unit, order or centre tables: the board is
`state_json`, and each processed turn's board is a `map_snapshots` row.

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
`standard.svg` (the rendered base map, province regions identified by ID) and `svg.dtd`.

---

## 5. Server (`src/server/`)

| File / Module | Purpose |
|---|---|
| `game_service.py` | **The single entry point from server code into the engine.** `GameService` wraps `engine.game.Game` + `serialization` + `orders/` over `GameRepo`: `create_game`, `submit_orders`, `process_turn`, `view`, `last_resolution`, `order_history`. Routes, the CLI `Server`, and DAIDE all go through this. |
| `_api_module.py` | FastAPI application factory. Registers routes, initializes the DB schema on startup, starts the deadline scheduler and the DAIDE listener in `lifespan`, and defines `/health`, `/healthz`, `/version` and a short `/` page. |
| `legal_orders.py` | Pure, phase-aware enumeration of every legal order for a power (movement / retreat / build / disband), with no FastAPI or DB imports. Backs `GET /games/{id}/legal_orders/{power}`. |
| `server.py` | `Server` — a text-command surface (`CREATE_GAME`, `ADD_PLAYER`, `SET_ORDERS`, `PROCESS_TURN`, `GET_GAME_STATE`), routed through `GameService`. Used by tests; the HTTP API does not depend on it. |
| `errors.py` | The CLI `Server`'s error responses (`UNKNOWN_COMMAND`, `MISSING_ARGUMENTS`, `GAME_NOT_FOUND`, `INVALID_ORDER`, `INTERNAL_ERROR`). The HTTP API uses FastAPI's `{"detail": …}`. |
| `db_config.py` | Reads `SQLALCHEMY_DATABASE_URL` from the environment (defaults to local PostgreSQL). |
| `response_cache.py` | In-memory response cache (TTL, LRU) behind `@cached_response` on `GET /games/{id}/state`, `/players` and `/users/{id}/games`; every write that changes one calls `invalidate_cache`. |
| `daide/` | The DAIDE protocol package — see §6. |

### API route modules (`src/server/api/routes/`)

| Module | Endpoints |
|---|---|
| `games.py` | Create/list/get games, join/quit/replace, private-game passwords, dummies, auto-process and wait flags, deadlines (set and majority vote), process turn, snapshots + restore, history and resolutions, draw vote and concede, legal orders, spectators (out of scope, kept). |
| `orders.py` | Submit orders (replace, or merge one per unit), get current orders, clear orders, order history. |
| `users.py` | Register a Telegram user, list a user's games. |
| `auth.py` | JWT register/login/token/refresh/me, forgot + reset password, Telegram link code and link/unlink. |
| `messages.py` | Private messages, broadcasts, message history. |
| `maps.py` | Board / orders / resolution PNGs, per-turn boards and each turn's orders map (what the Telegram group gets after every turn), map preview, and `GET /maps/{map}/provinces` — province metadata (full name, type, supply-centre flag, coasts), the one server-side source of display names for both clients. |
| `waiting_list.py` | Automatic game matching: join/leave the queue, queue status. Owns the `waiting_list` table and creates the game itself when the queue fills, claiming exactly seven entries in one transaction first so a failure cannot orphan a game. |
| `channels.py` | Link/unlink a game's Telegram group, its settings, and posts queued for it: the current map, results, broadcasts, timelines, the player dashboard, threads. |
| `admin.py` | Delete a game or all games, mark a seat inactive, cache and connection-pool management, counts. Requires the admin token. |
| `archive.py` | Saved-game export and import (admin only: an export holds every private message). |
| `bot_outbox.py` | The bot's pull endpoint for queued notifications, and its ack. |
| `tournaments.py` | Legacy tournament endpoints — out of scope, kept for backward compatibility. |

`shared.py` holds the `db_service` / `game_service` singletons, loggers, `notify_user` /
`notify_players` / `post_to_game_group` (which write `bot_outbox` rows — server code never
talks to Telegram), `finish_processed_turn` (everything after a turn, for every trigger),
and the **deadline scheduler**: a background async task that processes
turns whose deadline has passed, notifies players, and hourly purges delivered outbox rows
and expired idempotency keys. `idempotency.py` is the middleware that replays a stored response for a repeated
`Idempotency-Key`; `client_timestamp.py` normalises the composed-at time the bot sends.

### Auth

Two modes coexist: **JWT Bearer** (browser) and **`telegram_id` plus the bot secret**
(Telegram bot). `resolve_user_or_telegram` turns either into a user; `require_bot_or_user`
and `require_bot_secret` are the dependencies; per-power authorization is enforced in route
handlers.

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
| `app.py` / `__main__.py` | Entry point: wires command and callback handlers, starts the two background loops from `post_init`, runs polling. Starts even when the API is unreachable. |
| `config.py`, `api_client.py` | Token/API-URL config; `api_get`, `api_post`, `api_get_bytes` (raise `ApiUnreachableError` with a player-ready message), and **`api_post_reliable`** + `drain_outbox_once` — the durable-queue write path for orders and messages. |
| `outbox.py` | The SQLite durable queue (`DIPLOMACY_BOT_DATA_DIR/outbox.sqlite3`): pending/inflight/delivered/rejected entries with backoff, plus the per-user games cache and each player's **current game**. |
| `game_context.py` | `resolve_game_and_power(user_id, game_id=None)` + `fetch_user_games` — the one place a command figures out which game and power it is acting on. A named game becomes the player's current game (`set_current_game`), and a bare command in a multi-game player's hands acts on it. Falls back to the cached games list when the API is unreachable so orders can still be queued. |
| `hub.py` | The **game menu**: `/games`, `/game [id]`, `/findgame`, `/cancel`, and the `g\|{game_id}\|{action}[\|arg]` callback router behind every game-menu button *and* the buttons on server notifications (`api.shared.game_buttons`; a trailing `\|n` answers in a new message). Also `handle_awaited_text`: a message to a power, or a private game's password, typed as the next plain message. |
| `games.py` | `/start` (registers silently; three-key keyboard), `/register`, `/join`, `/quit`, `/replace`, `/wait`, `/leavequeue`, `/status`, `/players`, the ready/deadline commands — and the helpers the hub shares with them (`status_text`, `set_wait_flag`, `propose_deadline`/`vote_deadline`/`withdraw_deadline`, `join_game`, `ensure_registered`). The queue is server state. |
| `orders.py` | `/orders` (= `/order`), `/orderall`, `/selectunit`, `/myorders`, `/clearorders`, `/clear`, `/orderhistory`, `/processturn` (creator only, enforced by the API) — interactive unit and move selection via inline keyboards driven by `legal_orders`. |
| `messages.py`, `maps.py` | `/message`, `/broadcast`, `/messages` (game id optional; `send_diplomatic_message`, `recent_messages_text`); `/map`, `/viewmap`, `/replay`. |
| `ui.py`, `admin.py` | `/help`, `/rules`, `/examples`, `/refresh` (rebuild the keyboard menu), plain-text routing (private chats only); the solo demo (`start_demo_game`: six civil-disorder seats in a `map_name="demo"` game, where the server plays them with `engine.simple_ai`), `/debug`. |
| `help_text.py` | **Every order string shown to a player**, in one module, imported by `ui.py`, `admin.py` and `app.py`; `tests/test_bot_help_text.py` parses each documented order through the real grammar, so the help can never teach syntax the engine rejects. |
| `channels.py`, `channel_commands.py` | The text of group posts (timeline, player dashboard, battle results; the API queues them, the bot sends them); `/newgame`, `/linkgroup`, `/unlinkgroup`, and `/link_channel`, `/unlink_channel`, `/channel_info`, `/channel_settings` (players of the game only). |
| `notifications.py` | The two background loops: pull `GET /bot/outbox` and send each row — a DM, a group post, or a group map fetched by its path (ack after Telegram accepts; late ones prefixed with their original time; an image the API refuses is failed, not retried) — and replay the local queue in order, DMing each result. Also `/queue`. No listener of any kind. |

Command reference:
[`docs/TELEGRAM_BOT_COMMANDS.md`](docs/TELEGRAM_BOT_COMMANDS.md).

---

## 8. Frontend (`frontend/`)

React 18 + Vite + TypeScript SPA, Tailwind CSS + shadcn/ui, React Router, React Hook Form +
Zod. Consumes the GameState-native view directly. Routes: `/`, `/login`, `/register`,
`/forgot-password`, `/reset-password`, `/link-telegram`, `/games`, `/games/:id`. Vite
proxies `/api` to `http://localhost:8000` in dev; in production the `diplomacy_web` image
builds `dist/` and nginx serves it. Tests use Vitest + React Testing Library — see
[`frontend/docs/TESTING.md`](frontend/docs/TESTING.md).

The board map is rendered server-side at 1835×1360 but the app column is `max-w-4xl` (896px),
so `components/MapViewer.tsx` wraps the inline image in a button that opens a full-viewport
zoom/pan viewer (wheel/pinch/buttons, 10%–600%, double-click toggles fit ↔ 1:1, `Esc` closes).
Note for tests: jsdom implements neither `PointerEvent` nor `setPointerCapture`, so pointer
tests need the polyfill in `MapViewer.test.tsx` or they silently assert nothing.

---

## 9. Tests

Run with `PYTHONPATH=src python -m pytest tests/ -v` from the repository root with the
venv active and Postgres up. CI enforces coverage: `--fail-under=80` overall,
`--include='src/engine/*' --fail-under=95` for the engine, and the frontend thresholds in
`frontend/vite.config.ts`. `tests/test_suite_hygiene.py` rejects a test that cannot fail.

| Category | Location |
|---|---|
| **DATC conformance** | `tests/datc/test_datc_6a_*.py` … `6k_*.py` (~154 cases, `datc` marker), `test_adjudicator_mechanics.py`, `harness.py`, and `test_properties.py` (Hypothesis over random *supported* positions: determinism under order-shuffling, unit conservation, ≤1 unit/province, every offered retreat legal). |
| **Engine units** | `tests/engine/` — value types, `.map` topology loading, order grammar and its errors, validation, adjustment edge rules, JSON round-trips, the phase machine, `simple_ai` (its orders must validate), plus a 7-AI-power self-play run. |
| **Game service** | `test_game_service.py` (including resolution maps across every phase), `test_concurrent_processing.py` (`StaleGameError`, the cross-process guard), `test_order_overlay.py`, `test_view_adapter.py`, `test_legal_orders.py`. |
| **API routes** | `test_api_routes_*.py`, `test_api_scheduler.py`, `test_api_health.py`, `test_cache_coherence.py` (no cached read shows the world before your own write), `test_game_archive.py`, `test_channel_posts.py`, `test_background_jobs.py`. |
| **Auth** | `test_auth.py`, `test_authorization.py`, `test_auth_sweep.py`, `test_user_registration.py`. |
| **Rendering** | `test_board_render.py` (pixels and the render cache key), `test_visualization.py`, `test_order_visualization.py`, `test_arrow_geometry.py`, `test_pending_order_styling.py` (`map` marker). |
| **Telegram bot** | `test_bot_commands.py` (each command's HTTP contract), `test_bot_routing.py` (every button/keyboard route, every advertised command registered), `test_telegram_*.py`, `test_bot_*.py`, `test_api_client*.py`, `test_game_context.py`, `test_selectunit_phases.py`, `test_interactive_orders.py`. |
| **DAIDE** | `test_daide_tokens.py`, `test_daide_wire.py`, `test_daide_clauses.py`, `test_daide_session.py`, `test_daide_server.py` (including an end-to-end raw-socket test over one continuous TCP connection). |
| **Server / persistence / other** | `test_server.py`, `test_execution_context.py` (the bot image's imports and `python -m` start), `test_persistence_database_service.py`, `test_response_cache.py`, `test_deployment_infrastructure.py`, `test_suite_hygiene.py` (every test must contain something that can fail). |

**DB-dependent tests skip silently without `SQLALCHEMY_DATABASE_URL`** — a no-DB local run
looks falsely green. CI always provides a fresh `postgres:14` container.

---

## 10. Infrastructure

Production is one Docker Compose stack on the UpCloud VPS, `docker-compose.yml`: `postgres`,
`diplomacy_api`, `diplomacy_bot`, `diplomacy_web` (nginx: the SPA plus `/api/` → the API),
`caddy` (HTTPS) and `diplomacy_docs` (this documentation as a website). Only Caddy is
public; nginx and the API are on loopback, Postgres unpublished. Dockerfiles
and the nginx template are under `docker/`; host scripts are `install.sh` (first-time setup),
`ensure_env.sh` (generates secrets on the host), `upgrade.sh` (build, restart, verify) and
`backup.sh` (nightly `pg_dump`, copied off-host to Proton Drive with rclone). Full walkthrough:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

`.github/workflows/deploy.yml` deploys after a green Test Suite on `main`, writing
`TELEGRAM_BOT_TOKEN` (the only host secret GitHub holds) into `.env` and running
`upgrade.sh` (gated on `DEPLOY_CONTROL_ENABLED`).

---

## 11. Key data flow

**Playing a game**

1. `/start` in Telegram → `POST /users/persistent_register`.
2. `POST /games/create` with `map_name` → `GameService.create_game` builds
   `Game.new_standard()` and persists its `state_json`.
3. `/join` → `POST /games/{id}/join` → a row in `players` (never engine-coupled).
4. *Enter orders* (`/orderall`) → bot fetches `GET /games/{id}/legal_orders/{power}` →
   inline keyboards per unit → `POST /games/set_orders` → `GameService.submit_orders`
   parses and validates, stores into `pending_orders`.
5. The last order in (auto-process), the creator's "process now", or the deadline →
   `GameService.process_turn` loads `state_json`, parses every power's pending orders, calls
   `Game.adjudicate(orders)`, advances the phase, persists the next `state_json` +
   `last_resolution`, appends the order and resolution histories, clears `pending_orders`;
   then `finish_processed_turn` snapshots the board and notifies the players (and the
   group, with the orders and result maps).
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
| Infrastructure | Docker Compose on one VPS, nginx, Caddy (HTTPS), MkDocs (docs site); GitHub Actions deploy-on-merge |
| Linting | Ruff (strict, pinned version — CI pins to avoid new-release rule-set breakage) |
