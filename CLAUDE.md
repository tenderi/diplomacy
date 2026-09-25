# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

- **The repository root is the whole codebase** — what runs in production, and the CWD for
  every command below.
- **`CODEBASE_OVERVIEW.md`** — per-module breakdown. Read it for depth beyond this file.
- **`docs/specs/`** — the design and rules specs (authoritative); **`docs/specs/fix_plan.md`**
  — open work.
- The project began as a rewrite of Philip Paquette's AGPL `diplomacy` package. That code
  is no longer in the tree, but `git show v2.7.68:old_implementation/<path>` reads any file
  of it — useful when cross-checking a rules question against its engine.

## Workflow: every change lands through a PR, tagged

`main` is protected. Required status checks: **`test`, `frontend`, `security`** (all in
[`.github/workflows/test.yml`](.github/workflows/test.yml)). Strict mode is on (a branch must
be up to date with `main`), admin enforcement is on, force-push and branch deletion are
blocked, no reviews required. **A bare `git push origin main` is always rejected.**

Other sessions may be working on the repository at the same time. Fetch first, and take
the next free version and track letter from `origin/main`, not from local tags.

```bash
git fetch origin && git checkout -b some-change origin/main
# ... work, run the local gates below ...
git commit -m "v3.0.N: <what changed>"   # next patch version; see below
git fetch origin && git rebase origin/main
git push -u origin some-change
gh pr create -R tenderi/diplomacy          # the -R is mandatory; gh otherwise resolves the wrong remote
gh pr checks <n> -R tenderi/diplomacy --watch
gh pr merge <n> -R tenderi/diplomacy --merge
git checkout main && git pull --ff-only origin main
git tag v3.0.N && git push origin v3.0.N   # tag the merge commit on main
```

- The commit message starts with the version (`v3.0.N: ...`) and carries the write-up:
  what was wrong, what changed, how it was verified. That *is* the project history.
- Patch tags are `v3.0.x`. A minor/major bump and a GitHub Release are the maintainer's
  call; the version lives in `pyproject.toml`, `frontend/package.json` and `_api_module.py`
  (`tests/test_api_health.py` checks they agree).
- Never chain `gh pr merge && git push --delete`: if the merge is refused for staleness the
  delete still runs, and deleting the head branch **closes** the PR. Tag the `main` merge
  commit, not the pre-rebase branch commit (`git merge-base --is-ancestor <tag> main`).
- To push past a CI failure (e.g. fixing CI itself), disable *only* admin enforcement, then
  restore it immediately:

  ```bash
  gh api --method DELETE repos/tenderi/diplomacy/branches/main/protection/enforce_admins
  gh api --method POST   repos/tenderi/diplomacy/branches/main/protection/enforce_admins
  ```

## Commands

All from the repository root with the venv active. Requires **Python 3.14** (pinned in `pyproject.toml`).

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
pytest tests/datc/ -v                      # DATC conformance suite
pytest tests/ -m unit                      # markers: unit integration slow database telegram channels map
                                           #   ai datc execution_context deployment infrastructure performance

# Lint (Ruff only; CI pins the version — keep local in sync)
ruff check src/ && ruff format src/

# Frontend (React + Vite + TS, in frontend/)
cd frontend && npm install && npm run dev  # :5173, proxies /api to :8000
npm run build                              # → frontend/dist
npm run test:run                           # Vitest + React Testing Library

# Production (see docs/DEPLOYMENT.md)
./upgrade.sh          # on the VPS: build + start the whole stack, verify (deploy.yml runs this)
```

**Local gates before every push** (mirrors CI):

```bash
ruff check src/
bandit -q -r src/ -ll                      # CI's `security` check; pip install bandit
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=95
coverage report --fail-under=80
cd frontend && npx tsc -b --noEmit && npm run test:coverage && npm run build
```

The coverage floors (engine 95, total 80, frontend thresholds in `frontend/vite.config.ts`)
sit two to three points under the measured numbers: room to delete covered dead code, not
to stop testing. **Every test must be able to fail** — `tests/test_suite_hygiene.py`
rejects a test with no assertion. Assert the exact value or message, never "one of these
status codes": a test that accepts 500 hides the bug it should catch.

### Test database

DB-dependent tests need `SQLALCHEMY_DATABASE_URL` (or `DIPLOMACY_DATABASE_URL`); a `.env` in
the repository root is picked up automatically via `python-dotenv`. **Without it they skip
silently — a no-DB run looks falsely green.** A skip means something is wrong, not that the
DB is unavailable.

## Architecture

Five components, all over one Postgres database, all running as containers on one VPS in
production (see [Deployment](#deployment-one-vps)):

```
Telegram Bot ──┐
React SPA ─────┼──► FastAPI (:8000) ──► GameService ──► GameRepo ──► Postgres
DAIDE clients ─┘         │                   │
                         └── engine.Game (pure logic, no I/O) ──► src/rendering (PNG maps)
```

The bot never receives pushes. The API writes notifications (player DMs and group posts) to
the `bot_outbox` table and the bot pulls them; the bot keeps its own durable SQLite queue of
player writes (orders, messages) and replays them with an `Idempotency-Key` and the original
`client_timestamp` when the API is unreachable (a restart, a deploy).
`docs/specs/architecture.md` §Notifications and §Deployment have the full contract.

Full writeups: [`docs/specs/architecture.md`](docs/specs/architecture.md) (packages, boundaries, DAIDE), [`docs/specs/adjudication.md`](docs/specs/adjudication.md) (the resolver), [`docs/specs/data_spec.md`](docs/specs/data_spec.md) (types, serialization, DB columns, API view shape).

### Game engine (`src/engine/`)

**Pure rules logic — stdlib only, no I/O, DB, rendering, or framework deps** (`tests/engine/test_purity.py` checks every import). All values are **frozen, hashable dataclasses** in `types.py` (`Location(province, coast)`, `Unit`, the `Order` variants, `GameState`, `DislodgedUnit`, `Resolution`/`OrderResult`, plus the enums). Adjudication is a pure function `(map, state, orders) -> (Resolution, new_state)`.

- `game.py` — `Game` (frozen snapshot: map, state, history) + the phase machine `S{y}M → [S{y}R] → F{y}M → [F{y}R] → [W{y}A] → S{y+1}M`. Retreat phase only on dislodgement; adjustment only when a power's unit and center counts differ; SC ownership recomputed after Fall; victory at 18.
- `map_loader.py` — parses `maps/standard.map` into `MapData`. **The sole topology source** — no hardcoded adjacency or coast tables anywhere. Multi-coast provinces (BUL, SPA, STP) have per-coast fleet adjacency; check here before assuming a single adjacency list. It is also the only alias source: to teach the parser a new province alias, edit the `.map` file's `=` line rather than adding a table. `display_names` are for client output only and deliberately do not parse.
- `adjudicator/movement.py` — Kruijswijk fixed-point resolver. `retreats.py` — retreat legality (`compute_retreat_options`) + resolution. `adjustments.py` — builds/disbands/waives + the civil-disorder distance rule.
- `orders/parser.py` + `orders/validation.py` — one grammar, one validation path (coasts, VIA convoy, aliases).
- `serialization.py` — canonical JSON for `GameState`/`Order`/`Resolution`, the one place that conversion happens. `simple_ai.py` — dumb heuristic order generator (the demo game's opponents).

DATC conformance lives in `tests/datc/`: 144/154 green plus **10 documented `xfail`s** — second-order convoy paradoxes 6.F.16/17/18/23/24, convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8. Do not un-xfail any of them without an iterative-Szykman resolver.

### Persistence (`src/persistence/`) and rendering (`src/rendering/`)

- `database.py` / `database_service.py` — SQLAlchemy models plus the DAL for everything **not** engine-coupled (users, players, messages, channels, tournaments). `game_repo.py` — `GameRepo`, the only persistence path for game state: `state_json` (a serialized `GameState`), `pending_orders`, `last_resolution`, `order_history`, `resolution_history`. The legacy `units`/`orders`/`supply_centers` tables still exist in the schema but are never read or written; don't add code that touches them.
- `server/game_service.py` — `GameService` is the **single entry point from server code into the engine** (`create_game`/`submit_orders`/`process_turn`/`view`/`last_resolution`/`order_history`). Non-engine code goes through `GameService` or `DatabaseService`, never ORM models or engine internals directly.
- `rendering/` — the SVG → PNG pipeline (Pillow + CairoSVG), fed a plain-dict view by `view_adapter.py`. Split into focused modules (`board`, `overlays`, `arrows`, `svg_paths`, `legend`, `icons`, `cache`); `map.py` is a thin `Map` facade of staticmethods. `order_overlay.py` adapts `Order`/`Resolution` into arrow primitives. Results are cached in memory and at `/tmp/diplomacy_map_cache` (the key covers everything that changes the picture, centre ownership included).

**Timestamps:** every `datetime` column is a naive `TIMESTAMP`. Use `persistence.database.utcnow_naive()`, which returns **naive UTC on purpose** — handing Postgres a tz-aware value makes it convert to the connection's session timezone and store it shifted. Do not "modernize" it to `datetime.now(timezone.utc)`. New `datetime` columns must either be `timestamptz` or normalize on write.

### Server (`src/server/`)

FastAPI app assembled in `_api_module.py`:

- Routes in `src/server/api/routes/` (`games`, `orders`, `users`, `auth`, `messages`, `maps`, `channels`, `admin`, `tournaments`, `waiting_list`, `bot_outbox`, `archive`); `/health`, `/healthz` and `/version` are defined in `_api_module.py` itself. `shared.py` holds the singletons `db_service` / `game_service`, notification helpers, loggers, and the deadline-scheduler background task. Game endpoints return the GameState-native view shape (`units`/`units_by_power`/`ownership`/`phase`/`phase_type`/`players`/`dislodged`/`contested`/`orders`).
- `legal_orders.py` — pure, phase-aware enumeration of every legal order for a power, exposed as `GET /games/{id}/legal_orders/{power}`. Both the frontend and the bot's interactive order UI drive off it. Two gotchas: `format_order` renders fleets as `A` unless passed an explicit `kind_by_province` map, and `orders_by_unit` keys (`"F STP/SC"`) match builds and disbands as a *suffix*, because that grammar is verb-first (`D A PAR`, `BUILD F BRE`).
- `server.py` — a text-command CLI surface (`CREATE_GAME`, `ADD_PLAYER`, ...) used by tests; the HTTP API does not depend on it.
- `daide/` — a real DAIDE wire-protocol implementation (`tokens`, `wire`, `clauses`, `session`, `server`), started as an `asyncio` listener on port 8432 alongside the API. **Press content is relayed opaquely, not parsed** — a permanent scope decision, not a gap.
- `response_cache.py` — TTL+LRU caching of `GET /games/{id}/state`, `/players` and `/users/{id}/games`. **A write that changes one of them must call `invalidate_cache`** (`games/{id}`, `users/{telegram_id}`); `tests/test_cache_coherence.py` checks each write path.

**Auth has two modes that coexist**: JWT Bearer (browser) and `telegram_id` plus the bot secret (the Telegram bot). `routes/auth.py`: `resolve_user_or_telegram` turns either into a user; `require_bot_or_user` (a dependency) admits either kind of caller; `require_bot_secret` admits only the bot. Per-power authorization (only the assigned user may act for a power) is enforced in route handlers — preserve it when editing.

**Concurrency:** `GameRepo.save_state` (and `update_state_json`, used by concede) takes an `expected_phase_code` and raises `StaleGameError` → HTTP 409, checking it on a row taken `FOR UPDATE` — a plain read would let two workers both pass. Every other per-phase JSON column (`pending_orders`, `draw_votes`, `wait_flags`, `pending_deadline_proposal`) changes only through a locked `modify_*` read-modify-write; add `populate_existing()` to a locked query when the row may already be in the session, or it returns the stale cached copy. That is the cross-process guard; an `asyncio.Lock` cannot be one, since each uvicorn worker has its own.

### Telegram bot (`src/server/telegram_bot/`)

A thin client over the HTTP API (`api_client.py`) — it never talks to the engine or DB, and never renders maps locally. Its only dependencies are `python-telegram-bot` and `requests` (`requirements-bot.txt`; the Docker image installs nothing else, and `tests/test_execution_context.py` rejects any other import). Entry point is `app.py` / `__main__.py`; **there must never be a `telegram_bot.py` module**, which shadows the package and breaks `python -m server.telegram_bot`. Command modules are split by domain (`games`, `orders`, `messages`, `maps`, `admin`, `channels`, `channel_commands`, `ui`), plus `hub.py` (the per-game menu and the `g|{game_id}|{action}` callbacks that game-menu and notification buttons use) and `game_context.py` (`resolve_game_and_power`, with a per-user cache so it resolves offline, and each player's remembered current game).

**Reliability.** `outbox.py` is a SQLite-backed durable queue under `DIPLOMACY_BOT_DATA_DIR`. Writes that must never be lost — orders and diplomatic messages — go through `api_client.api_post_reliable`, which enqueues *before* attempting and returns `delivered` / `queued` / `rejected`; the handler shows the matching reply. `notifications.py` runs two background loops from `post_init`: one pulls `GET /bot/outbox` and sends each row (acking only after Telegram accepts), one replays the local queue in order and DMs each result. There is no inbound listener of any kind. When adding a new player *write*, use `api_post_reliable`; reads and retryable interactive actions (join, waiting list) keep using `api_post`/`api_get`, which raise `ApiUnreachableError` with a player-ready message.

All bot and group messages use legacy `parse_mode='Markdown'`: bold is `*single*`, and user text goes through `utils.escape_markdown` (which escapes only `_ * \` [`).

### Frontend (`frontend/`)

React 18 + Vite + TypeScript SPA with Tailwind + shadcn/ui. Routes: `/`, `/login`, `/register`, `/link-telegram`, `/forgot-password`, `/reset-password`, `/games`, `/games/:id`. Add a component with `npx shadcn@latest add <component>`. Any test touching a `/games/:id` page must wrap it in `<Routes><Route path="/games/:gameId" …>` — a bare `MemoryRouter` leaves `useParams()` unresolved and silently tests the loading spinner.

## Deployment (one VPS)

Production is **one host**, the UpCloud VPS `87.58.144.64` (login `root`; the checkout is
`/root/diplomacy`), running `docker-compose.yml`: `postgres`, `diplomacy_api`
(`docker/api.Dockerfile`; migrations run in the entrypoint), `diplomacy_bot`
(`docker/bot.Dockerfile`, only `requirements-bot.txt`), `diplomacy_web` (nginx serving the
built SPA and proxying `/api/` to the API), `caddy` (HTTPS for `DOMAIN`; `docker/Caddyfile`)
and `diplomacy_docs` (the `docs/` site via MkDocs, served by Caddy at `DOCS_DOMAIN`; built
with `--strict`, so a broken doc link fails the deploy). **Only Caddy is public.** The API
is published on `127.0.0.1` only — never a bare `8000:8000` — and Postgres not at all; the
bot and nginx reach the API by service name. p2p's bot shares the VPS and is not ours.

Scripts, all in the repository root: `install.sh` (first-time host setup: Docker, swap,
`.env`, backup cron), `ensure_env.sh` (creates `.env` and generates any blank secret — never
prints one), `upgrade.sh` (build, restart, verify; fails if the API or site is down),
`backup.sh` (nightly `pg_dump`, copied to Proton Drive with rclone), `harden_host.sh`
(sshd, fail2ban, unattended upgrades). Every secret except the Telegram token is generated
**on the host** and never leaves it; the bot and the API read `DIPLOMACY_BOT_SECRET` from the
same `.env`, so it cannot drift.

**Deploy-on-merge:** `.github/workflows/deploy.yml` SSHes in as `root` after a green Test
Suite on `main`, checks out that exact SHA, writes `TELEGRAM_BOT_TOKEN` (the only secret
GitHub holds for the host) into `.env`, and runs `./upgrade.sh`. Gated on the
`DEPLOY_CONTROL_ENABLED` repository variable.

**Read-only checks on production** are fine: `ssh diplomacy-vps`, then e.g.
`docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA'`
with the SQL on stdin (never prints a secret).

**The full operational guide — setup, ports and the UpCloud firewall, TLS, backups,
monitoring, troubleshooting — is [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).**

## Conventions and gotchas

- **License: GNU AGPL v3 or later** (`LICENSE`), inherited from diplomacy/diplomacy, whose
  map data (`maps/standard.map`, `maps/standard.svg`) this project adapts. Keep the
  "Source code" links (web footer `AppLayout.SOURCE_URL`, bot `/help` via
  `help_text.SOURCE_URL`): section 13 requires offering the source to network users. Don't
  add code or assets under an AGPL-incompatible license.
- **`PYTHONPATH=src` is required** to import `server.*` and `engine.*`. Forgetting it produces `ModuleNotFoundError`. Tests handle it via `pytest.ini` (`pythonpath = . src`).
- **Type hints are mandatory** on new code. Ruff is in strict mode; CI fails on lint errors.
- **Never add a blanket `except Exception`.** `src/rendering/` uses specific exception tuples so that a real programming bug raises instead of being logged and swallowed behind a subtly wrong image. Where a route already has a generic `except Exception`, it must be preceded by `except HTTPException: raise`, or the route's own 404/403 comes out as a 500.
- **Never write to an ORM row returned by a `DatabaseService` getter.** It is detached once the getter's session closes, and `DatabaseService.commit()` is a no-op, so `row.x = y` is silently discarded. Add a DAL method that opens its own session and commits.
- **`require_bot_or_user` proves the caller is *someone*, not the person the request acts on.** A route taking a `telegram_id` or `power` must resolve the caller (`resolve_user_or_telegram`) and check membership itself, or use `require_bot_secret`. Auth on a `@cached_response` route must be a *dependency*: a check in the body runs only on cache misses.
- **`Game.history` does not survive a `GameRepo` round-trip** (`GameService.load` builds `Game` without it). Anything that needs the pre-adjudication board must compute it during `process_turn` and persist it.
- **Specs are load-bearing.** [`docs/specs/`](docs/specs/) is the source of truth for rules and design — `architecture.md`, `adjudication.md`, `data_spec.md`, `diplomacy_rules.md`. Update them in the same commit when behavior changes, and keep every document describing the system as it is now (history belongs in commit messages).
- **[`docs/specs/fix_plan.md`](docs/specs/fix_plan.md) holds open work only.** Check tasks off in the same commit as the work, keep its Status block current, and never do newly discovered work silently — add it there first. When a track completes, delete its section; the commit message carries the write-up.
- **Game rule questions**: cross-check `docs/reference/rules.pdf` (the official rulebook, authoritative) and, for the pre-rewrite engine's behavior, `git show v2.7.68:old_implementation/diplomacy/engine/` before changing adjudication logic.
- **Map rendering** requires CairoSVG (`libcairo2`). Tests that need it are marked `@pytest.mark.map`. When changing `src/rendering/`, compare rendered PNG bytes before and after, with the map cache cleared (`Map.clear_map_cache()` and `/tmp/diplomacy_map_cache`), or you compare two copies of the same stale image.
- **Migrations:** after adding an Alembic revision, `alembic heads` must print exactly one head (a copied revision id only warns, then `upgrade head` fails), and the revision must round-trip (`upgrade` → `downgrade -1` → `upgrade`) against a real Postgres; CI never runs a downgrade. `alembic/env.py` loads `.env` *over* the environment, so a URL on the command line is ignored while `.env` exists.
- **Out of scope** unless the maintainer explicitly asks: tournaments, Discord, observer/spectator mode, AI-powered analysis, map variants beyond `standard`, full DAIDE press-grammar parsing. Existing code in those areas (`api/routes/tournaments.py`, `discord_bot/`, the spectator routes) is kept for backward compatibility — don't extend it.
- **Schema changes**: update `src/persistence/database.py`, add an Alembic revision under `alembic/versions/`, and add the corresponding method(s) to `DatabaseService`. The schema autoupdater in `_api_module.py` is a safety net, not a substitute for migrations.
