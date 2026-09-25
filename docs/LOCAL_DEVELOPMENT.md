# Running the Diplomacy Server Locally

Install, configure, and run the API server plus the optional components (browser frontend,
Telegram bot). All commands assume you are in the repository root with the venv active.

## Prerequisites

- **Python 3.14** (pinned in [`pyproject.toml`](https://github.com/tenderi/diplomacy/blob/main/pyproject.toml))
- **PostgreSQL** — required by the API and most tests
- **libcairo2** — required by CairoSVG for map rendering
- **Node.js 18+ / npm** — only for the browser frontend
- **A Telegram bot token** from [@BotFather](https://t.me/BotFather) — only for the bot

One script installs everything on Arch, Debian/Ubuntu, or macOS with Homebrew:

```bash
./install_prerequisites.sh
```

Or by hand:

```bash
# Arch
sudo pacman -S python python-pip postgresql nodejs npm cairo
sudo systemctl start postgresql

# Debian / Ubuntu (Python 3.14 via deadsnakes on older releases)
sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt-get update
sudo apt-get install -y python3.14 python3.14-venv python3-pip postgresql postgresql-client libcairo2 libcairo2-dev
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs
sudo systemctl start postgresql

# macOS
brew install python@3.14 postgresql@16 node@20 cairo
brew services start postgresql@16
```

## 1. Virtual environment and packages

```bash
python3.14 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Database

The default connection URL is
`postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db`.

The quickest path creates the role, the database, and the schema in one go:

```bash
./setup_database.sh
```

To do it manually:

```bash
sudo -u postgres psql
```

```sql
CREATE USER diplomacy_user WITH PASSWORD 'password';
CREATE DATABASE diplomacy_db OWNER diplomacy_user;
GRANT ALL PRIVILEGES ON DATABASE diplomacy_db TO diplomacy_user;
\q
```

```bash
psql -U diplomacy_user -h localhost -d diplomacy_db   # verify the connection
alembic upgrade head                                  # create/update tables
```

To use different credentials, set `SQLALCHEMY_DATABASE_URL` (see step 3).

**Game IDs start high.** The displayed `game_id` is the `games.id` primary key, and the
Postgres sequence advances on every insert including tests and rolled-back transactions. To
restart numbering in development — only when `games` is empty or you're happy to wipe it:

```sql
TRUNCATE games CASCADE;
ALTER SEQUENCE games_id_seq RESTART WITH 1;
```

## 3. Environment variables

Everything has a working default. To avoid exporting variables each session, put them in
`.env` in the repository root (loaded via `python-dotenv`; never commit secrets).

| Variable | Purpose |
|---|---|
| `SQLALCHEMY_DATABASE_URL` | PostgreSQL connection URL (`DIPLOMACY_DATABASE_URL` is also accepted by the tests) |
| `DIPLOMACY_ENVIRONMENT` | `production` makes the API refuse to start with the default JWT secret or admin token |
| `DIPLOMACY_JWT_SECRET` | JWT signing secret — **must** be set in production |
| `DIPLOMACY_ADMIN_TOKEN` | The `X-Admin-Token` value for admin routes (default `changeme`, logged as insecure) |
| `DIPLOMACY_API_DOCS` | `0` turns off Swagger/ReDoc/OpenAPI (production does); on by default |
| `DIPLOMACY_DAIDE_PORT` | The DAIDE listener's port (default 8432) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (bot process only) |
| `DIPLOMACY_API_URL` | API base URL used by the bot (default `http://localhost:8000`) |
| `DIPLOMACY_BOT_SECRET` | Shared secret between bot and API; also arms `Idempotency-Key` replay and the `/bot/outbox` endpoints |
| `DIPLOMACY_BOT_DATA_DIR` | Where the bot keeps its durable queue (`outbox.sqlite3`; default `bot_data/`, git-ignored) |
| `DIPLOMACY_NOTIFY_POLL_SECONDS` / `DIPLOMACY_OUTBOX_POLL_SECONDS` | Bot poll intervals for pulling notifications / replaying its queue (defaults 3 / 5) |
| `DIPLOMACY_BOT_HEARTBEAT` | The file the bot's loops touch for its Docker healthcheck (default `/tmp/diplomacy-bot-heartbeat`) |
| `DIPLOMACY_CORS_ORIGINS` | Allowed CORS origins (default `*`; restrict in production) |
| `DIPLOMACY_MAP_PATH` | Path to the map SVG (default `maps/standard.svg`) |
| `DIPLOMACY_LOG_LEVEL` / `DIPLOMACY_LOG_FILE` | Log level (default `INFO`); log to a file instead of stdout |
| `DIPLOMACY_PASSWORD_RESET_BASE_URL` | Base URL for password-reset links (e.g. `http://localhost:5173`) |
| `DIPLOMACY_DEV_SHOW_RESET_LINK` | `1` returns the reset link in the response (**development only**) |
| `DIPLOMACY_SMTP_HOST` / `_PORT` / `_USE_TLS` / `_USER` / `_PASSWORD` / `_FROM` / `_FROM_NAME` | SMTP settings; if `HOST` is set, forgot-password sends real email |

## 4. Run the API server

```bash
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
```

`PYTHONPATH=src` is required — the `server` and `engine` packages live under `src/`. Drop
`--reload` when debugging startup issues.

- API: **http://localhost:8000**
- Swagger UI: **http://localhost:8000/docs**
- Verify: `curl http://localhost:8000/health`

## 5. Run the browser frontend (optional)

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

The app runs at **http://localhost:5173**; Vite proxies API routes to the backend. Set
`VITE_API_URL` in `frontend/.env` if the API is elsewhere. See
[BROWSER_CLIENT.md](BROWSER_CLIENT.md) and [`frontend/README.md`](https://github.com/tenderi/diplomacy/blob/main/frontend/README.md).

## 6. Run the Telegram bot (optional)

```bash
export TELEGRAM_BOT_TOKEN=your-token-from-BotFather
PYTHONPATH=src python -m server.telegram_bot
```

The bot starts whether or not the API is up. With the API down, reads answer with a clear
"server unreachable" message and writes (orders, messages) are queued in
`bot_data/outbox.sqlite3` and delivered once the API answers — a convenient way to exercise
the queue locally is to stop uvicorn, send `/order A PAR H`, check `/queue`, then start it
again. In production the bot is its own container next to the API; see
[DEPLOYMENT.md](DEPLOYMENT.md).

Commands: [TELEGRAM_BOT_COMMANDS.md](TELEGRAM_BOT_COMMANDS.md).

*(A minimal Discord bot exists at `src/server/discord_bot/` — set
`DIPLOMACY_DISCORD_BOT_TOKEN` and run `PYTHONPATH=src python -m server.run_discord_bot`. It
is **out of scope** for the current roadmap and is kept only for backward compatibility.)*

## 7. Run the tests

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=term-missing
```

**Database-dependent tests skip silently** without `SQLALCHEMY_DATABASE_URL` (or
`DIPLOMACY_DATABASE_URL`) set — a run without a database looks falsely green. Testing
strategy: [`specs/testing_and_validation.md`](specs/testing_and_validation.md).

## Quick reference

| Task | Command |
|---|---|
| API server | `PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload` |
| Migrations | `alembic upgrade head` |
| Tests | `pytest tests/ -v` |
| Lint | `ruff check src/` |
| Frontend dev | `cd frontend && npm run dev` |
| Telegram bot | `PYTHONPATH=src python -m server.telegram_bot` |

## Troubleshooting

**`ModuleNotFoundError: server` / `engine`** — run from the repository root with
`PYTHONPATH=src`.

**Database connection errors** — check that PostgreSQL is running (`pg_isready`), that the
role and database exist, and that `SQLALCHEMY_DATABASE_URL` matches. Test directly with
`psql -U diplomacy_user -h localhost -d diplomacy_db`. If columns are missing, run
`alembic upgrade head` — note that Alembic reads `.env` *over* your environment, so a
different URL must go in `.env`, not on the command line.

**401 on `/games/.../join` or `/auth/refresh`** — the access or refresh token is invalid or
expired. Changing `DIPLOMACY_JWT_SECRET` invalidates every existing token; log in again.

**CORS errors from the frontend** — set `DIPLOMACY_CORS_ORIGINS` (e.g.
`http://localhost:5173`).

**"Order failed"** — check the syntax, that the order type matches the current phase, that
the unit exists and belongs to your power, and that province names are valid. The canonical
list of what's legal right now is `GET /games/{id}/legal_orders/{power}`.

**Map generation is slow the first time** — maps are cached in memory and at
`/tmp/diplomacy_map_cache`; subsequent requests are fast. If CairoSVG fails to import,
install `libcairo2`.

**Bot doesn't respond** — confirm `TELEGRAM_BOT_TOKEN` is set, the bot process is running,
and the API is reachable at `DIPLOMACY_API_URL`. `/start` registers you.

**Tests fail or skip unexpectedly** — check the database URL first (see above), then re-run
the single test with `pytest tests/test_file.py::test_name -v`.

For production troubleshooting, see the *Troubleshooting* section of
[`docs/DEPLOYMENT.md`](./DEPLOYMENT.md).
