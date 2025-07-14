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
