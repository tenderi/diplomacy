# Diplomacy Python Implementation

A modern, fully-tested Diplomacy board game server in Python. This project is designed for correctness, extensibility, and ease of use for both players and developers.

## Features
- Full implementation of Diplomacy rules and adjudication
- Modular architecture: engine, server, client
- DAIDE protocol support for bots/AI
- Map variants and extensibility
- Comprehensive test suite
- Strict typing and Ruff compliance

## Installation
1. Clone the repository
2. (Optional) Create a virtual environment: `python3 -m venv venv && source venv/bin/activate`
3. Install requirements: `pip install -r requirements.txt`

## How to Run
- **Start the server:**
  ```bash
  python -m server.server
  ```
- **Use the client:**
  See [README_client.md](./src/README_client.md) for usage examples.
- **Run all tests:**
  ```bash
  pytest new_implementation/src/ --maxfail=5 --disable-warnings
  ```

## Quickstart Example (CLI)
1. Start the server (see above)
2. In the server CLI, type:
   ```
   CREATE_GAME standard
   ADD_PLAYER 1 FRANCE
   SET_ORDERS 1 FRANCE A PAR - BUR
   PROCESS_TURN 1
   GET_GAME_STATE 1
   ```

## Project Structure
- `src/engine/`: Core game logic (game, map, power, order)
- `src/server/`: Server loop, command processing, DAIDE protocol
- `src/client.py`: Minimal client interface
- `examples/`: Example games and usage scenarios
- `specs/`: Specifications for all modules

## Contributing
- Follow strict typing and Ruff linting rules
- Add or update tests for all new features
- Update documentation after each increment
- See [documentation_plan.md](./specs/documentation_plan.md) for more

## FAQ & Troubleshooting
- See [specs/](./specs/) for rules, requirements, and troubleshooting
- For issues, check the logs and ensure all dependencies are installed

## Why tests and implementation matter
Tests ensure correctness, reliability, and maintainability. All features are covered by tests, and strict typing and Ruff compliance are enforced.

## See Also
- [specs/](./specs/) for all specifications
- [engine/README.md](./src/engine/README.md)
- [server/README.md](./src/server/README.md)
- [README_client.md](./src/README_client.md)

## Production Deployment (Docker)

### Prerequisites
- Docker and docker-compose installed
- A valid Telegram bot token (set as TELEGRAM_BOT_TOKEN)

### Quick Start

1. Build and start the stack:

```bash
export TELEGRAM_BOT_TOKEN=your-telegram-bot-token
cd new_implementation
cp ../alembic.ini .
docker-compose up --build
```

2. The API will be available at http://localhost:8000
3. The Telegram bot will run in the same container (make sure your token is valid)
4. PostgreSQL will be available at localhost:5432 (user/pass/db: diplomacy)

### Notes
- All migrations are run automatically on startup.
- The API and bot will restart on failure.
- Data is persisted in a Docker volume (`pgdata`).

## Scaling and Performance

- Database indexes are in place for all key queries (game_id, power, user_id, turn).
- For production, use a connection pooler (e.g., PgBouncer) if running many app containers.
- To scale horizontally, increase the number of `app` containers in `docker-compose.yml` and place a load balancer (e.g., Nginx, Traefik) in front of them.
- All logs are output to stdout/stderr for aggregation by Docker or cloud logging solutions.

## Security Hardening and Code Quality (2024)
- All endpoints that allow a player to act for a power (submit orders, clear orders, quit, replace, send messages) now enforce authorization: only the assigned user can act for a power.
- Linter and code quality issues in the server code are resolved.
- All tests pass.
- The codebase is production-ready for deployment.

## Next Steps
- Improve documentation and code comments for new/changed endpoints and logic.
- Implement observer mode (lowest priority).
- Address any remaining enhancements or bugfixes.
