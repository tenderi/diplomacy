# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Two top-level Python codebases. Almost all work happens in `new_implementation/`.

- **`new_implementation/`** — the active codebase; what runs in production. All edits, tests, and new features belong here. CWD for nearly every command below.
- **`old_implementation/`** — legacy DATC engine + websocket server + React UI. **Reference only.** Useful for cross-checking rules (`rules.pdf`) and DAIDE details. Do not modify or wire into new code. It is **AGPL-3.0** and this repo ships no LICENSE — read it, never copy from it.
- **`CODEBASE_OVERVIEW.md`** — per-module breakdown at the repo root. Read it for depth beyond this file.

## Workflow rule: always commit and push when work is done

After completing any task (feature, fix, refactor, docs):

1. Stage all changed and new files.
2. Commit with a message starting with the next version tag (e.g. `v2.7.44: ...`).
3. Tag it (`git tag v2.7.44`).
4. Push branch and tags: `git push origin main --tags`.

Check the latest tag with `git tag --sort=-v:refname | head -1`.

## Branch protection and CI gating

`main` is protected. Required status checks: **`test`, `frontend`, `security`** (all defined in [`.github/workflows/test.yml`](.github/workflows/test.yml)). Strict mode is on (branches must be up to date with `main`), admin enforcement is on, force-push and branch deletion are blocked, no PR reviews required (solo repo).

**A bare `git push origin main` is always rejected** — the required checks have never run on a brand-new SHA. Either go through a PR, or push the commit to a temp branch, wait for the checks to go green on that SHA, then fast-forward `main` to the identical SHA.

Prefer a feature branch whenever CI is the validation gate — Alembic migrations (CI runs against a fresh `postgres:14`), `requirements.txt` changes, workflow changes, or anything you cannot fully verify locally.

```bash
git checkout -b some-feature
git push -u origin some-feature
gh pr create -R tenderi/diplomacy          # the -R is mandatory; gh otherwise resolves the wrong remote
gh pr checks <n> -R tenderi/diplomacy
git rebase origin/main && git push -f      # strict mode refuses stale branches
gh pr merge <n> -R tenderi/diplomacy --merge
```

Never chain `gh pr merge && git push --delete`: if the merge is refused for staleness the delete still runs, and deleting the head branch **closes** the PR. Tag the resulting `main` merge commit, not the pre-rebase branch commit (verify with `git merge-base --is-ancestor <tag> main`).

If you genuinely must push past a CI failure (e.g. fixing CI itself), disable *only* admin enforcement, then restore it immediately:

```bash
gh api --method DELETE repos/tenderi/diplomacy/branches/main/protection/enforce_admins
gh api --method POST   repos/tenderi/diplomacy/branches/main/protection/enforce_admins
```

## Commands

All from `new_implementation/` with the venv active. Requires **Python 3.14** (pinned in `pyproject.toml`).

```bash
# Setup (first time)
python3.14 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./setup_database.sh                        # creates Postgres user/db and runs migrations

# API server (PYTHONPATH=src is required — packages live under src/)
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
# Swagger UI at http://localhost:8000/docs

# Telegram bot (needs the API running)
TELEGRAM_BOT_TOKEN=<token> PYTHONPATH=src python -m server.telegram_bot

# Migrations
alembic upgrade head
alembic revision -m "describe change"      # autogenerate is NOT used; hand-write upgrade/downgrade

# Tests
pytest tests/ -v
pytest tests/datc/ -v                      # DATC conformance suite (6.A–6.J)
pytest tests/ -m unit                      # markers: unit integration slow database telegram channels map
                                           #   ai datc execution_context deployment infrastructure performance
pytest tests/ --cov=src --cov-report=term-missing

# Lint (Ruff only; CI pins the version — keep local in sync)
ruff check src/ && ruff format src/

# Frontend (React + Vite + TS, in frontend/)
cd frontend && npm install && npm run dev  # :5173, proxies /auth /games /users to :8000
npm run build                              # → frontend/dist; API serves it at /app when present
npm run test:run                           # Vitest + React Testing Library

# Production (see docs/DEPLOYMENT.md)
docker compose up -d                                   # home server: postgres + API
docker compose -f docker-compose.control.yml up -d     # VPS: bot + web
```

**Local gates before every push** (mirrors CI):

```bash
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

The engine floor has under a point of headroom and is deliberately **not** ratcheted tighter — a tighter floor would make ordinary dead-code deletion fail CI.

### Test database

DB-dependent tests need `SQLALCHEMY_DATABASE_URL` (or `DIPLOMACY_DATABASE_URL`); a `.env` in `new_implementation/` is picked up automatically via `python-dotenv`. **Without it they skip silently — a no-DB run looks falsely green.** A skip means something is wrong, not that the DB is unavailable.

## Architecture

Five components, all over one Postgres database. In production the first two run on a
**VPS** and everything else on the **home server**, joined by a WireGuard tunnel (see
[Deployment](#deployment-vps--home-server)):

```
Telegram Bot ──┐  (VPS)
React SPA ─────┼──► FastAPI (:8000) ──► GameService ──► GameRepo ──► Postgres   (home)
DAIDE clients ─┘         │                   │
                         └── engine.Game (pure logic, no I/O) ──► src/rendering (PNG maps)
```

The bot never receives pushes. The API writes player notifications to the `bot_outbox`
table and the bot pulls them; the bot keeps its own durable SQLite queue of player writes
(orders, messages) and replays them with an `Idempotency-Key` and the original
`client_timestamp` when the API is unreachable. `docs/specs/architecture.md` §Notifications
and §Split deployment have the full contract.

Full writeups: [`docs/specs/architecture.md`](new_implementation/docs/specs/architecture.md) (packages, boundaries, DAIDE), [`docs/specs/adjudication.md`](new_implementation/docs/specs/adjudication.md) (the resolver), [`docs/specs/data_spec.md`](new_implementation/docs/specs/data_spec.md) (types, serialization, DB columns, API view shape).

### Game engine (`src/engine/`)

**Pure rules logic — stdlib only, no I/O, DB, rendering, or framework deps** (a Hypothesis property enforces this). All values are **frozen, hashable dataclasses** in `types.py` (`Location(province, coast)`, `Unit`, the `Order` variants, `GameState`, `DislodgedUnit`, `Resolution`/`OrderResult`, plus the enums). Adjudication is a pure function `(map, state, orders) -> (Resolution, new_state)`; history is a list of snapshots.

- `game.py` — `Game` (frozen snapshot: map, state, history) + the phase machine `S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M`. Retreat phase only on dislodgement; adjustment only when a power's unit and center counts differ; SC ownership recomputed after Fall; victory at 18.
- `map_loader.py` — parses `maps/standard.map` into `MapData`. **The sole topology source** — no hardcoded adjacency or coast tables anywhere. Multi-coast provinces (BUL, SPA, STP) have per-coast fleet adjacency; check here before assuming a single adjacency list. It is also the only alias source: to teach the parser a new province alias, edit the `.map` file's `=` line rather than adding a table.
- `adjudicator/movement.py` — Kruijswijk fixed-point resolver. `retreats.py` — retreat legality (`compute_retreat_options`) + resolution. `adjustments.py` — builds/disbands/waives + the civil-disorder distance rule.
- `orders/parser.py` + `orders/validation.py` — one grammar, one validation path (coasts, VIA convoy, aliases).
- `serialization.py` — canonical JSON for `GameState`/`Order`/`Resolution`, the one place that conversion happens. `simple_ai.py` — dumb heuristic order generator (demo/self-play).

DATC conformance lives in `tests/datc/`: 144/154 green plus **10 documented `xfail`s** — second-order convoy paradoxes 6.F.16/17/18/23/24, convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8. Do not un-xfail any of them without the iterative-Szykman resolver upgrade.

### Persistence (`src/persistence/`) and rendering (`src/rendering/`)

- `database.py` / `database_service.py` — SQLAlchemy models plus the DAL for everything **not** engine-coupled (users, players, messages, channels, tournaments). `game_repo.py` — `GameRepo`, the only persistence path for game state: `state_json` (a serialized `GameState`), `pending_orders`, `last_resolution`, `order_history`. The legacy `units`/`orders`/`supply_centers` tables still exist in the schema but are never read or written; don't add code that touches them.
- `server/game_service.py` — `GameService` is the **single entry point from server code into the engine** (`create_game`/`submit_orders`/`process_turn`/`view`/`last_resolution`/`order_history`). Non-engine code goes through `GameService` or `DatabaseService`, never ORM models or engine internals directly.
- `rendering/` — the SVG → PNG pipeline (Pillow + CairoSVG), fed a plain-dict view by `view_adapter.py`. Split into focused modules (`board`, `overlays`, `arrows`, `svg_paths`, `legend`, `icons`, `cache`); `map.py` is a thin `Map` facade of staticmethods, kept so importers didn't have to change. `order_overlay.py` adapts `Order`/`Resolution` into arrow primitives. Results are cached in memory and at `/tmp/diplomacy_map_cache`.

**Timestamps:** every `datetime` column is a naive `TIMESTAMP`. Use `persistence.database.utcnow_naive()`, which returns **naive UTC on purpose** — handing Postgres a tz-aware value makes it convert to the connection's session timezone and store it shifted (this silently corrupted every deadline on non-UTC dev machines). Do not "modernize" it to `datetime.now(timezone.utc)`. New `datetime` columns must either be `timestamptz` or normalize on write.

### Server (`src/server/`)

FastAPI app assembled in `_api_module.py`:

- Routes in `src/server/api/routes/` (`games`, `orders`, `users`, `auth`, `messages`, `maps`, `channels`, `admin`, `dashboard`, `health`, `tournaments`). `shared.py` holds the singletons `db_service` / `game_service`, `game_view(game_id)`, loggers, and the deadline-scheduler background task. Game endpoints return the GameState-native view shape (`units`/`units_by_power`/`ownership`/`phase`/`phase_type`/`players`/`dislodged`/`contested`/`orders`).
- `legal_orders.py` — pure, phase-aware enumeration of every legal order for a power, exposed as `GET /games/{id}/legal_orders/{power}`. Both the frontend and the bot's interactive order UI drive off it. Two gotchas: `format_order` renders fleets as `A` unless passed an explicit `kind_by_province` map, and `orders_by_unit` keys (`"F STP/SC"`) match builds and disbands as a *suffix*, because that grammar is verb-first (`D A PAR`, `BUILD F BRE`).
- `server.py` — a text-command CLI surface (`CREATE_GAME`, `ADD_PLAYER`, ...) used by tests; the HTTP API does not depend on it.
- `daide/` — a real DAIDE wire-protocol implementation (`tokens`, `wire`, `clauses`, `session`, `server`), started as an `asyncio` listener on port 8432 alongside the API. **Press content is relayed opaquely, not parsed** — a permanent scope decision, not a gap.
- `response_cache.py` — TTL+LRU caching for expensive endpoints (map generation, game state).

**Auth has two modes that coexist**: JWT Bearer (browser) and `telegram_id` in the request body (Telegram bot). The dependency `get_current_user_or_telegram` accepts either. Per-power authorization (only the assigned user may act for a power) is enforced in route handlers — preserve it when editing.

**Concurrency:** `GameRepo.save_state` takes an `expected_phase_code` and raises `StaleGameError` → HTTP 409. That is the cross-process guard; an `asyncio.Lock` cannot be one, since each uvicorn worker has its own.

### Telegram bot (`src/server/telegram_bot/`)

A thin client over the HTTP API (`api_client.py`) — it never talks to the engine or DB, and never renders maps locally. Its only dependencies are `python-telegram-bot` and `requests` (`requirements-bot.txt`; the Docker image installs nothing else — keep it that way). Entry point is `app.py` / `__main__.py`; **there must never be a `telegram_bot.py` module**, which shadows the package and breaks `python -m server.telegram_bot`. Command modules are split by domain (`games`, `orders`, `messages`, `maps`, `admin`, `channels`, `channel_commands`, `ui`), plus `game_context.py` (`resolve_game_and_power`, with a per-user cache so it resolves offline).

**Reliability (Track J).** `outbox.py` is a SQLite-backed durable queue under `DIPLOMACY_BOT_DATA_DIR`. Writes that must never be lost — orders and diplomatic messages — go through `api_client.api_post_reliable`, which enqueues *before* attempting and returns `delivered` / `queued` / `rejected`; the handler shows the matching reply. `notifications.py` runs two background loops from `post_init`: one pulls `GET /bot/outbox` and DMs players (acking only after Telegram accepts), one replays the local queue in order and DMs each result. There is no port 8081 and no inbound listener of any kind. When adding a new player *write*, use `api_post_reliable`; reads and retryable interactive actions (join, waiting list) keep using `api_post`/`api_get`, which raise `ApiUnreachableError` with a player-ready message.

### Frontend (`frontend/`)

React 18 + Vite + TypeScript SPA with Tailwind + shadcn/ui. Routes: `/`, `/login`, `/register`, `/link-telegram`, `/games`, `/games/:id`. Add a component with `npx shadcn@latest add <component>`. Any test touching a `/games/:id` page must wrap it in `<Routes><Route path="/games/:gameId" …>` — a bare `MemoryRouter` leaves `useParams()` unresolved and silently tests the loading spinner.

## Deployment (VPS + home server)

Production is **split across two hosts**, the same shape as the `p2p` repo, and reuses that
repo's WireGuard tunnel (VPS `10.8.0.1`, home `10.8.0.2`):

- **VPS — control layer** (`docker-compose.control.yml`): `diplomacy_bot` (the Telegram bot,
  `docker/bot.Dockerfile`, only `requirements-bot.txt`) and `diplomacy_web` (nginx serving the
  built SPA and proxying `/api/` across the tunnel, `docker/web.Dockerfile`). Holds a Telegram
  token and `DIPLOMACY_BOT_SECRET`. Nothing else.
- **Home server `kattotuuletin.local` — game layer** (`docker-compose.yml`): `postgres` and
  `diplomacy_api` (`docker/api.Dockerfile`; migrations run in the entrypoint). The API is
  published on loopback and on the tunnel address only — never a bare `8000:8000`.

Scripts, all in `new_implementation/`: `install_home.sh` (Arch; generates the secrets and
prints the bot secret to copy to the VPS), `install_vps.sh` (Debian), `upgrade.sh`,
`upgrade_control.sh`. `.env.example` / `.env.control.example` are the two env files, and the
separation is the point: no database URL or JWT secret ever goes to the VPS.

**The full operational guide — setup, ports and the UpCloud firewall, TLS, monitoring,
troubleshooting — is [`new_implementation/docs/DEPLOYMENT.md`](new_implementation/docs/DEPLOYMENT.md).**

**No message is ever lost across the tunnel.** Player writes are queued durably on the VPS
and replayed with the original timestamp; server notifications are committed to Postgres and
pulled by the bot. See the Telegram bot section above and `docs/specs/architecture.md`.

Things that are *not* automated: deploy-on-merge (the AWS workflow in
`.github/workflows/deploy.yml` stays gated off; run `./upgrade.sh` / `./upgrade_control.sh` on
the hosts), and TLS (see `docs/DEPLOYMENT.md`). The Terraform under `infra/terraform/` describes
the previous single-EC2 layout, which never ran in anger; it is kept as reference only.

## Conventions and gotchas

- **`PYTHONPATH=src` is required** to import `server.*` and `engine.*`. Forgetting it produces `ModuleNotFoundError`. Tests handle it via `pytest.ini` (`pythonpath = . src`).
- **Type hints are mandatory** on new code. Ruff is in strict mode; CI fails on lint errors.
- **Never add a blanket `except Exception`.** `src/rendering/` was deliberately narrowed to specific exception tuples so that a real programming bug raises instead of being logged and swallowed behind a subtly wrong image.
- **Specs are load-bearing.** [`docs/specs/`](new_implementation/docs/specs/) is the source of truth for rules and design — `architecture.md`, `adjudication.md`, `data_spec.md`, `diplomacy_rules.md`. Update them when behavior changes.
- **[`docs/specs/fix_plan.md`](new_implementation/docs/specs/fix_plan.md) is the living tracker** for what to work on next, and holds **open work only**. Check tasks off in the same commit as the work, keep its Status block current, and never do newly discovered work silently. When a track completes, move its section verbatim — findings and evidence included — into [`docs/specs/done_fixes.md`](new_implementation/docs/specs/done_fixes.md), the completed-work archive. Read `done_fixes.md` for the *why* behind existing code; read `fix_plan.md` to decide what to do.
- **Game rule questions**: cross-check `old_implementation/rules.pdf` (the official rulebook, authoritative) and `old_implementation/diplomacy/engine/` before changing adjudication logic.
- **Map rendering** requires CairoSVG (`libcairo2`). Tests that need it are marked `@pytest.mark.map`.
- **Out of scope** unless the maintainer explicitly asks: tournaments, Discord, observer/spectator mode, AI-powered analysis, map variants beyond `standard`, full DAIDE press-grammar parsing. Existing code in those areas (`api/routes/tournaments.py`, `discord_bot/`, the spectator routes) is kept for backward compatibility — don't extend it.
- **Schema changes**: update `src/persistence/database.py`, add an Alembic revision under `alembic/versions/`, and add the corresponding method(s) to `DatabaseService`. The schema autoupdater in `_api_module.py` is a safety net, not a substitute for migrations.
