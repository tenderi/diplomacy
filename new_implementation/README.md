# Diplomacy — Python Implementation

A modern, fully-tested Diplomacy board game server. Correctness first: a pure, immutable
rules engine with a DATC conformance suite, exposed over a REST API to a Telegram bot, a
React browser client, and DAIDE protocol bots.

Requires **Python 3.14** (pinned in [`pyproject.toml`](./pyproject.toml)).

## Quick start

```bash
python3.14 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./setup_database.sh
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --reload
```

API at http://localhost:8000, Swagger UI at `/docs`. Full walkthrough (database, env vars,
frontend, Telegram bot, tests): **[docs/LOCAL_DEVELOPMENT.md](./docs/LOCAL_DEVELOPMENT.md)**.

## Documentation

| Doc | Contents |
|---|---|
| [Local development](./docs/LOCAL_DEVELOPMENT.md) | Setup, database, environment, running everything, troubleshooting. |
| [Telegram bot commands](./docs/TELEGRAM_BOT_COMMANDS.md) | Complete command reference. |
| [Browser client](./docs/BROWSER_CLIENT.md) | Register, log in, link Telegram, play in the browser. |
| [Server API reference](./src/server/README.md) | REST endpoints, the CLI surface, and DAIDE. |
| [`docs/specs/`](./docs/specs/) | Authoritative design and rules specs. |
| [`CODEBASE_OVERVIEW.md`](../CODEBASE_OVERVIEW.md) | Per-module breakdown of the whole repository. |

Start with [`docs/specs/architecture.md`](./docs/specs/architecture.md) for package
boundaries, [`adjudication.md`](./docs/specs/adjudication.md) for the resolver, and
[`data_spec.md`](./docs/specs/data_spec.md) for the data model and API shapes.

## Deployment

Production runs on a single AWS EC2 instance provisioned by Terraform, deployed from CI over
GitHub OIDC + SSM. See [infra/terraform/README.md](./infra/terraform/README.md).

## Authorization

Endpoints that let a player act for a power — submit or clear orders, quit, replace, send
messages, vote — enforce that only the assigned user may act for that power. Both JWT Bearer
(browser) and `telegram_id` (bot) authentication resolve to the same user.

## Contributing

- Strict typing and Ruff linting are required; CI enforces both.
- Add or update tests for every change. DB-dependent tests skip silently without a database
  configured — check before trusting a green run.
- Update the relevant spec under [`docs/specs/`](./docs/specs/) when behaviour changes.
- [`docs/specs/fix_plan.md`](./docs/specs/fix_plan.md) is the living tracker of what to work
  on next; keep it current in the same commit as the work.

**Out of scope** unless explicitly requested: tournaments, Discord, observer/spectator mode,
AI-powered analysis, map variants beyond `standard`, and full DAIDE press-grammar parsing.
