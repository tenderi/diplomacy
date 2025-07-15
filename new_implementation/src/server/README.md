# Diplomacy Server Module

Implements the server loop, command processing, and network interface (CLI or API) for managing games.

## API
- `Server`: Main class for accepting and processing game commands.
- `DAIDEServer`: TCP server for DAIDE protocol (bot/server communication).

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
- The `DAIDEServer` class provides a TCP interface for DAIDE protocol bots/clients.
- Example: send `HLO (FRANCE)` to create a game and add a player, then `ORD (A PAR - BUR)` to submit an order.

## User and Multi-Game API
- `/users/persistent_register`: Register a user persistently (POST, json: `{telegram_id, full_name}`)
- `/users/{telegram_id}/games`: List all games a user is in (GET)
- `/games/{game_id}/join`: Join a game as a power (POST, json: `{telegram_id, game_id, power}`)
- `/games/{game_id}/quit`: Quit a game (POST, json: `{telegram_id, game_id}`)

### Example Usage
```python
import requests
# Register user
requests.post("/users/persistent_register", json={"telegram_id": "12345", "full_name": "Test User"})
# Join a game
requests.post(f"/games/1/join", json={"telegram_id": "12345", "game_id": 1, "power": "FRANCE"})
# List user games
requests.get("/users/12345/games")
# Quit a game
requests.post(f"/games/1/quit", json={"telegram_id": "12345", "game_id": 1})
```

- Each user can join multiple games as different powers.
- Player-to-user mapping is persistent in the database.

## Build/Test Loop
- Run all tests: `