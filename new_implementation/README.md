# Diplomacy Python Implementation

A modern, fully-tested Diplomacy board game server in Python. This project is designed for correctness, extensibility, and ease of use for both players and developers.

## Features
- Full implementation of Diplomacy rules and adjudication
- Modular architecture: engine, server, client
- DAIDE protocol support for bots/AI
- Map variants and extensibility
- Comprehensive test suite
- Strict typing and Ruff compliance

## Quick start

See **[docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md)** for the full walkthrough (venv, PostgreSQL, env vars, API, frontend, Telegram bot, tests).

Minimum viable boot:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
```

## Documentation

- **[Local Development & Running the Server](./docs/LOCAL_DEVELOPMENT.md)** — Full setup guide
- **[Telegram Bot Commands](./docs/TELEGRAM_BOT_COMMANDS.md)** — Complete command reference
- **[Browser Client](./docs/BROWSER_CLIENT.md)** — Register, log in, link Telegram, play in the browser
- **[Browser Setup Instructions](./docs/BROWSER_SETUP_INSTRUCTIONS.md)** — Chrome/Selenium for SVG rendering
- **[FAQ & Troubleshooting](./docs/FAQ.md)** — Common questions and solutions
- **[Developer Guide](./docs/DEVELOPER_GUIDE.md)** — Contributor patterns and conventions
- **[Server API Reference](./src/server/README.md)** — REST and DAIDE endpoint reference
- **[docs/specs/](./docs/specs/)** — Detailed specifications and rules (authoritative)

## Production deployment (Docker)

Prerequisites: Docker and docker-compose, a valid `TELEGRAM_BOT_TOKEN`.

```bash
export TELEGRAM_BOT_TOKEN=your-telegram-bot-token
cd new_implementation
cp ../alembic.ini .
docker-compose up --build
```

- API at http://localhost:8000
- Telegram bot in the same container
- PostgreSQL at localhost:5432 (user/pass/db: `diplomacy`)
- Migrations run automatically on startup
- Data persisted in the `pgdata` Docker volume

For AWS EC2 single-instance deployment via Terraform, see [infra/terraform/README.md](./infra/terraform/README.md).

## Scaling notes

- Database indexes are in place for all key queries (game_id, power, user_id, turn).
- For production, use a connection pooler (e.g. PgBouncer) if running many app containers.
- Scale horizontally by increasing `app` containers in `docker-compose.yml` and fronting with a load balancer.
- All logs go to stdout/stderr for aggregation by Docker or cloud logging.

## Authorization

Endpoints that let a player act for a power (submit orders, clear orders, quit, replace, send messages) enforce authorization: only the assigned user can act for that power.

## Contributing

- Strict typing and Ruff linting are required.
- Add or update tests for all new features.
- Update specs under [`docs/specs/`](./docs/specs/) when behavior changes.
- Active development plan: [`docs/specs/fix_plan.md`](./docs/specs/fix_plan.md).

**Out of scope** unless explicitly requested: observer/spectator mode, tournament feature, Discord implementation, AI-powered analysis. See [`docs/specs/fix_plan.md`](./docs/specs/fix_plan.md) for the full list.
