# Diplomacy

Play the board game **Diplomacy** over Telegram or in the browser. Behind both is a
rules engine that passes 144 of the 154 DATC adjudication tests (the other ten are
documented expected failures).

**Play:** [@IronChancellorBot](https://t.me/IronChancellorBot) on Telegram (send it `/start`), or
https://diplomacy.xn--jalluthti-02a.fi. **New here? Read the [new player guide](https://diplomacy-docs.xn--jalluthti-02a.fi/NEW_USER_GUIDE/)** (all docs:
https://diplomacy-docs.xn--jalluthti-02a.fi).

- **Telegram groups:** add the bot to your group and send `/newgame`. After every turn the
  group gets a map of the orders and one of the result, plus reminders, while orders stay
  in private chats, and a group's games are visible only to its members.
- **Telegram bot:** the main way to play. A menu per game has buttons for ordering every
  unit (or just one), the map, messages, deadline votes and ready/wait. Turn notifications
  come with an *Enter orders* button, and orders and messages survive server restarts. There
  is also a solo demo against computer players.
- **Web app:** the same games in a browser, with a zoomable board, last turn's results,
  messages, draw votes, private games, civil-disorder seats for small tables, and
  auto-processing once every order is in.
- **Engine:** a pure-Python rules core (immutable state, Kruijswijk adjudication, retreats
  and builds), with the board topology coming only from `maps/standard.map`.
- **DAIDE:** a wire-protocol server, so AI clients can play.

Latest release: [3.0.0](https://github.com/tenderi/diplomacy/releases/tag/v3.0.0).

## Repository layout

| Path | What |
|---|---|
| `src/engine/` | The rules engine: pure logic, stdlib only, no I/O |
| `src/server/` | FastAPI app (`api/`), Telegram bot (`telegram_bot/`), DAIDE server (`daide/`) |
| `src/persistence/`, `alembic/` | SQLAlchemy models and data access; database migrations |
| `src/rendering/`, `maps/`, `icons/` | SVG → PNG board rendering; map data |
| `frontend/` | React + Vite + TypeScript web app |
| `tests/` | pytest suite, including DATC conformance in `tests/datc/` |
| `docker/`, `docker-compose.yml`, `*.sh` | The production stack and the scripts that run it |
| `docs/` | User and operations guides; `docs/specs/` holds the design and rules specs |

[`CODEBASE_OVERVIEW.md`](CODEBASE_OVERVIEW.md) goes module by module.

## Development

Needs Python **3.14**, PostgreSQL, Node for the web app, and Cairo for map rendering.

```bash
python3.14 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./setup_database.sh                                   # Postgres user, database, migrations
PYTHONPATH=src uvicorn server._api_module:app --reload  # API on :8000, Swagger at /docs

cd frontend && npm install && npm run dev             # web app on :5173
TELEGRAM_BOT_TOKEN=<token> PYTHONPATH=src python -m server.telegram_bot
```

Tests and linting (the same checks CI runs):

```bash
ruff check src/ && bandit -q -r src/ -ll
PYTHONPATH=src python -m pytest tests/ -q      # needs SQLALCHEMY_DATABASE_URL, e.g. in .env
cd frontend && npx tsc -b --noEmit && npm run test:run
```

Without a database URL, the database tests skip silently, so a run with no database set up
can look green when it isn't. The full walkthrough is in
[docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

## Deployment

Production is one VPS running `docker-compose.yml`:
- **Services:** Postgres, the API, the bot, nginx serving the web app, and Caddy for HTTPS.
- **Deploys:** every green merge to `main` deploys automatically.
- **Backups:** nightly database backups are copied to Proton Drive.
- **Hardening:** `harden_host.sh` sets up the host.

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Documentation

| Doc | Contents |
|---|---|
| [New player guide](docs/NEW_USER_GUIDE.md) | Start here: playing with your Telegram group, a turn step by step |
| [Telegram bot commands](docs/TELEGRAM_BOT_COMMANDS.md) | Every command and button |
| [Browser client](docs/BROWSER_CLIENT.md) | Registering, logging in, linking Telegram |
| [Server API](src/server/README.md) | REST endpoints, the CLI surface, DAIDE |
| [Specs](docs/specs/) | Architecture, adjudication, data model, rules. These are authoritative |
| [Fix plan](docs/specs/fix_plan.md) | Open work |
| [CLAUDE.md](CLAUDE.md) | Conventions and gotchas for working on the code |

## License

Copyright © 2025–2026 Helge Jalonen and contributors. This project builds on
**[diplomacy/diplomacy](https://github.com/diplomacy/diplomacy)**, © 2019 Philip Paquette:
it began as a fork of it, and its map data (`maps/standard.map`, `maps/standard.svg`) is
adapted from that project's files. The code has since been rewritten.

Like the original, this program is free software under the **GNU Affero General Public
License, version 3 or (at your option) any later version**. See [LICENSE](LICENSE).
It comes with no warranty.

The AGPL also covers people who use the program over a network: anyone playing on a
running instance must be able to get its source code. The web app's footer and the bot's
`/help` link to this repository. If you run a modified version, point those links at your
own source.
