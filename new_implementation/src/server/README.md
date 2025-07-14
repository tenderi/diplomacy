# Diplomacy Server Module

Implements the server loop, command processing, and network interface (CLI or API) for managing games.

## API
- `Server`: Main class for accepting and processing game commands.

## Configuration
- `DIPLOMACY_LOG_LEVEL`: Set the logging level (e.g., DEBUG, INFO, WARNING, ERROR). Default: INFO.
- `DIPLOMACY_LOG_FILE`: If set, log output will go to this file instead of stdout.

## Logging
- Logs startup, shutdown, all processed commands, errors, and game state changes (creation, player add/remove, phase advance).
- Log format: `[timestamp] LEVEL logger: message`

## Usage Example

```python
from server.server import Server
server = Server()
result = server.process_command("CREATE_GAME standard")
game_id = result["game_id"]
server.process_command(f"ADD_PLAYER {game_id} FRANCE")
server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
server.process_command(f"PROCESS_TURN {game_id}")
state = server.process_command(f"GET_GAME_STATE {game_id}")
print(state)
```

## DAIDE Protocol
- The DAIDEServer class provides a TCP interface for DAIDE protocol bots/clients.
- Example: send `HLO (FRANCE)` to create a game and add a player, then `ORD (A PAR - BUR)` to submit an order.

## Build/Test Loop
- Run all tests: `pytest new_implementation/src/ --maxfail=5 --disable-warnings`
- All code must be strictly typed and Ruff-compliant.
- Update documentation and specs after each increment.

## Why tests and implementation matter
Tests ensure the server correctly processes commands and manages game state, which is critical for reliability and correctness. Full test coverage and strict validation are required for production use.
