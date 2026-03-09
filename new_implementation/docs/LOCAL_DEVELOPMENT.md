# Running the Diplomacy Server Locally

This guide walks you through installing dependencies, configuring the database, and running the API server and optional components (frontend, Telegram bot) on your machine.

---

## Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **PostgreSQL** (for the API and most features)
- **Node.js 18+** and **npm** (only if you want to run the browser frontend)
- **Git** (to clone the repo)

Optional (for map image rendering and Telegram/Discord bots):

- **Chrome or Chromium** and **ChromeDriver** (see [BROWSER_SETUP_INSTRUCTIONS.md](BROWSER_SETUP_INSTRUCTIONS.md))
- **Telegram Bot Token** (from [@BotFather](https://t.me/BotFather)) for the Telegram bot
- **Discord Bot Token** for the Discord bot

---

## Installing prerequisites

You can install everything with one script (Arch, Debian/Ubuntu, or macOS with Homebrew):

```bash
cd new_implementation
./install_prerequisites.sh
```

Or install manually using the commands below for your OS.

### Arch Linux

```bash
# Python (usually pre-installed; includes pip)
sudo pacman -S python python-pip

# PostgreSQL server and client
sudo pacman -S postgresql

# Node.js and npm (for the browser frontend)
sudo pacman -S nodejs npm

# Start PostgreSQL (enable on boot: sudo systemctl enable postgresql)
sudo systemctl start postgresql
```

### Ubuntu / Debian

```bash
# Python and venv
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# PostgreSQL
sudo apt-get install -y postgresql postgresql-client

# Node.js 18+ and npm (NodeSource repo for current LTS)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Start PostgreSQL
sudo systemctl start postgresql
```

### macOS (Homebrew)

```bash
# Python
brew install python@3.12

# PostgreSQL
brew install postgresql@16
brew services start postgresql@16

# Node.js and npm
brew install node@20
```

### Verify installations

```bash
python3 --version   # 3.8 or higher
node --version      # v18 or higher (only needed for frontend)
npm --version       # 9 or higher (only needed for frontend)
psql --version      # PostgreSQL client (only needed if you use psql manually)
```

---

## 1. Clone and enter the project

```bash
git clone <repository-url>
cd diplomacy/new_implementation
```

All following commands assume you are in `new_implementation/`.

---

## 2. Python virtual environment and packages

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Recommended: upgrade pip first:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. PostgreSQL database

The API expects a PostgreSQL database. The default URL is:

`postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db`

### 3.1 Install PostgreSQL

- **Ubuntu/Debian:** `sudo apt-get install postgresql postgresql-client`
- **Arch:** `sudo pacman -S postgresql`
- **macOS:** `brew install postgresql@16` (or current) and start the service

Ensure the PostgreSQL server is running (e.g. `sudo systemctl start postgresql` or `brew services start postgresql`).

### 3.2 Create user and database

Connect as the postgres superuser and run:

```bash
sudo -u postgres psql
```

In the `psql` prompt:

```sql
CREATE USER diplomacy_user WITH PASSWORD 'password';
CREATE DATABASE diplomacy_db OWNER diplomacy_user;
GRANT ALL PRIVILEGES ON DATABASE diplomacy_db TO diplomacy_user;
\q
```

To use a different user, database name, or password, set `SQLALCHEMY_DATABASE_URL` (see step 4).

### 3.3 Run migrations

From `new_implementation/` with your venv activated:

```bash
alembic upgrade head
```

This creates/updates tables. For more detail, see [README_postgres.md](README_postgres.md).

---

## 4. Environment variables (optional)

You can rely on defaults or use a `.env` file in `new_implementation/` so you don’t have to export variables every time.

Create `new_implementation/.env` (do not commit secrets):

```env
# Database (default if omitted: postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db)
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db

# Optional: JWT secret for auth (use a long random string in production)
DIPLOMACY_JWT_SECRET=dev-secret-change-in-production

# Optional: Telegram bot (only if you run the Telegram bot)
# TELEGRAM_BOT_TOKEN=your-bot-token-from-BotFather

# Optional: CORS origins (default *); restrict in production
# DIPLOMACY_CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Optional: Map file path (default: maps/standard.svg relative to project)
# DIPLOMACY_MAP_PATH=maps/standard.svg
```

The app loads `.env` via `python-dotenv` where used (e.g. tests, Alembic). For the API server you can also export variables in the shell instead of using `.env`.

| Variable | Purpose |
|----------|--------|
| `SQLALCHEMY_DATABASE_URL` | PostgreSQL connection URL |
| `DIPLOMACY_JWT_SECRET` | Secret for JWT auth (set in production) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (for Telegram bot process) |
| `DIPLOMACY_API_URL` | API base URL used by Telegram/Discord bots (default `http://localhost:8000`) |
| `DIPLOMACY_CORS_ORIGINS` | Allowed CORS origins (default `*`) |
| `DIPLOMACY_MAP_PATH` | Path to map SVG (default `maps/standard.svg`) |
| `DIPLOMACY_DEV_SHOW_RESET_LINK` | Set to `1` to show password reset link in response (dev only) |
| `DIPLOMACY_PASSWORD_RESET_BASE_URL` | Base URL for password reset links (e.g. `http://localhost:5173`) |

---

## 5. Run the API server

From `new_implementation/` with the venv activated, set `PYTHONPATH` so the `server` and `engine` packages are found (they live under `src/`):

```bash
export PYTHONPATH=src
uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
```

Or in one line:

```bash
cd new_implementation && source venv/bin/activate && PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
```

- **Without `--reload`:** no auto-restart on code changes (better for debugging some issues).
- The API will be at **http://localhost:8000**.
- Open **http://localhost:8000/docs** for Swagger UI.

### Verify

```bash
curl http://localhost:8000/health
```

You should get a JSON response with status and environment info.

---

## 6. Run the browser frontend (optional)

To use the React web app (register, login, games, orders, messages):

In a **second terminal**, from the repo:

```bash
cd new_implementation/frontend
npm install
npm run dev
```

- App: **http://localhost:5173**
- Vite proxies `/auth`, `/games`, `/users`, etc. to the API (default `http://localhost:8000`). Set `VITE_API_URL` in the frontend if the API is elsewhere.

See [BROWSER_CLIENT.md](BROWSER_CLIENT.md) and `frontend/README.md` for more.

---

## 7. Run the Telegram bot (optional)

Only if you want the Telegram bot and have a bot token:

```bash
cd new_implementation
source venv/bin/activate
export TELEGRAM_BOT_TOKEN=your-token-from-BotFather
export PYTHONPATH=src
python -m server.telegram_bot
```

Or use a `.env` in `new_implementation/` with `TELEGRAM_BOT_TOKEN` and run:

```bash
PYTHONPATH=src python -m server.telegram_bot
```

The bot talks to the API using `DIPLOMACY_API_URL` (default `http://localhost:8000`). The API server must be running. Commands: [TELEGRAM_BOT_COMMANDS.md](TELEGRAM_BOT_COMMANDS.md).

---

## 8. Run the Discord bot (optional)

If you use the Discord bot:

```bash
cd new_implementation
source venv/bin/activate
export DIPLOMACY_DISCORD_BOT_TOKEN=your-discord-bot-token
export PYTHONPATH=src
python -m server.run_discord_bot
```

See [DISCORD_BOT.md](DISCORD_BOT.md) for details.

---

## 9. Run tests

From `new_implementation/` with venv activated:

```bash
pytest tests/ -v
```

Database-dependent tests need `SQLALCHEMY_DATABASE_URL` (or `DIPLOMACY_DATABASE_URL`) set, or a `.env` with that variable; otherwise they are skipped.

With coverage:

```bash
pytest tests/ --cov=src --cov-report=term-missing
```

---

## Quick reference

| Task | Command (from `new_implementation/`, venv active) |
|------|--------------------------------------------------|
| API server | `PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload` |
| Migrations | `alembic upgrade head` |
| Tests | `pytest tests/ -v` |
| Frontend dev | `cd frontend && npm run dev` |
| Telegram bot | `PYTHONPATH=src python -m server.telegram_bot` |

---

## Troubleshooting

- **ImportError / ModuleNotFoundError for `server` or `engine`**  
  Run the API (and bots) from `new_implementation/` with `PYTHONPATH=src`.

- **Database connection errors**  
  Check that PostgreSQL is running, the user/database exist, and `SQLALCHEMY_DATABASE_URL` (or `.env`) matches your setup. Test with:  
  `psql -U diplomacy_user -h localhost -d diplomacy_db`

- **Migrations out of date**  
  Run `alembic upgrade head` from `new_implementation/`.

- **Auth (JWT) or CORS issues**  
  Set `DIPLOMACY_JWT_SECRET` and, if needed, `DIPLOMACY_CORS_ORIGINS` (e.g. `http://localhost:5173` for the Vite frontend).

- **Map images or rendering**  
  See [BROWSER_SETUP_INSTRUCTIONS.md](BROWSER_SETUP_INSTRUCTIONS.md) for Chrome/Chromium and Selenium.

- **More docs**  
  [FAQ.md](FAQ.md), [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md), [README_postgres.md](README_postgres.md).
