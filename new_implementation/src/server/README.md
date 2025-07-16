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

## REST API Endpoints

### Game Management
- `POST /games/create` — Create a new game. `{map_name: str}` → `{game_id: str}`
- `POST /games/{game_id}/join` — Join a game as a power. `{telegram_id: str, game_id: int, power: str}`
- `POST /games/{game_id}/quit` — Quit a game. `{telegram_id: str, game_id: int}`
- `POST /games/{game_id}/replace` — Replace a vacated power. `{telegram_id: str, power: str}`
- `GET /games/{game_id}/players` — List all players in a game.
- `GET /games/{game_id}/state` — Get the current state of a game.
- `GET /games/{game_id}/deadline` — Get the current deadline for a game.
- `POST /games/{game_id}/deadline` — Set the deadline. `{deadline: ISO8601 str or null}`

### Orders
- `POST /games/set_orders` — Submit orders for a power. `{game_id: str, power: str, orders: [str], telegram_id: str}`
- `GET /games/{game_id}/orders` — List all orders for a game.
- `GET /games/{game_id}/orders/{power}` — Get orders for a specific power.
- `POST /games/{game_id}/orders/{power}/clear` — Clear orders for a power. (body: telegram_id as JSON string)
- `GET /games/{game_id}/orders/history` — Get order history grouped by turn and power.

### User Management
- `POST /users/persistent_register` — Register a user. `{telegram_id: str, full_name: str}`
- `GET /users/{telegram_id}/games` — List all games a user is in.
- `GET /users/{telegram_id}` — Get user session info (in-memory, for bot integration).
- `POST /users/register` — Register a user session (in-memory, for bot integration).

### Messaging
- `POST /games/{game_id}/message` — Send a private message. `{telegram_id: str, recipient_power: str, text: str}`
- `POST /games/{game_id}/broadcast` — Send a broadcast message. `{telegram_id: str, text: str}`
- `GET /games/{game_id}/messages` — Get all messages for a game (optionally filtered by user).

### Game History & Replay
- `GET /games/{game_id}/history/{turn}` — Get the board state for a specific turn.

### Health & Scheduler
- `GET /health` — Health check endpoint.
- `GET /scheduler/status` — Scheduler status.

## Error Handling
- All endpoints return JSON with `status: "ok"` or `status: "error"`.
- On error, a descriptive `message` and (optionally) an `error_code` are provided.
- Standard HTTP status codes are used (e.g., 400, 403, 404, 500).

## Security & Authorization
- Only the assigned user (by `telegram_id`) for a power can submit or clear orders, quit, or send messages as that power.
- Attempts to act for a power you do not control will return 403 Forbidden.
- User registration and persistent mapping are required for all player actions.

## Example Usage (Python)
```python
import requests
# Register user
requests.post("/users/persistent_register", json={"telegram_id": "12345", "full_name": "Test User"})
# Create a game
resp = requests.post("/games/create", json={"map_name": "standard"})
game_id = resp.json()["game_id"]
# Join as FRANCE
requests.post(f"/games/{game_id}/join", json={"telegram_id": "12345", "game_id": int(game_id), "power": "FRANCE"})
# Submit orders
requests.post("/games/set_orders", json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"], "telegram_id": "12345"})
# Get game state
requests.get(f"/games/{game_id}/state")
```

- Each user can join multiple games as different powers.
- Player-to-user mapping is persistent in the database.
- All player actions are authorized by `telegram_id`.