# Server Module Specification

## Purpose
Implements the server loop, command processing, and network interface (CLI or API) for managing games. Supports DAIDE protocol for bot/server communication.

## API
- `Server`: Main class for accepting and processing game commands.
  - Methods:
    - `__init__(self)`
    - `start(self)`
    - `shutdown(self)`
    - `process_command(self, command: str)`
    - `get_game_state(self, game_id: str) -> dict`
- `DAIDEServer`: TCP server for DAIDE protocol (bot/server communication)
  - Methods:
    - `__init__(self, server, host: str, port: int)`
    - `start(self)`
    - `stop(self)`

## Expected Behavior
- Starts a server loop to accept commands.
- Processes commands to create games, add/remove players, set orders, advance turns, and manage phases.
- Provides access to current game state.
- Handles DAIDE protocol messages for bot integration.

## Example Usage
```python
from server.server import Server
from server.daide_protocol import DAIDEServer

server = Server()
daide_server = DAIDEServer(server, host="0.0.0.0", port=8432)
daide_server.start()
server.process_command('CREATE_GAME standard')
server.process_command('ADD_PLAYER 1 FRANCE')
server.process_command('SET_ORDERS 1 FRANCE "A PAR - BUR"')
state = server.get_game_state('1')
print(state)  # Should show current game state as a dict
```

## Game State Structure
The dictionary returned by `get_game_state(game_id)` includes:
- `game_id`: Unique identifier for the game
- `phase`: Current phase (e.g., 'Spring 1901 Movement')
- `players`: List of players in the game
- `units`: Mapping of player to their units and locations
- `orders`: Mapping of player to their current orders (if any)
- `status`: 'active' or 'done'
- `turn_number`: Current turn number
- `map`: Map name
- `powers`: List of powers (players)
- `done`: Boolean, whether the game is finished

## Example Game State Output
```python
{
    'game_id': '1',
    'phase': 'Spring 1901 Movement',
    'players': ['FRANCE'],
    'units': {
        'FRANCE': ['A PAR']
    },
    'orders': {
        'FRANCE': ['A PAR - BUR']
    },
    'status': 'active',
    'turn_number': 1,
    'map': 'standard',
    'powers': ['FRANCE'],
    'done': False
}
```

## Test Cases
- Test server startup and shutdown
- Test command processing for all game actions (CREATE_GAME, ADD_PLAYER, SET_ORDERS, PROCESS_TURN, REMOVE_PLAYER, ADVANCE_PHASE, SAVE_GAME, LOAD_GAME)
- Test game state queries (using `get_game_state`)
- Test error handling for invalid commands and duplicate player/game creation
- Test DAIDE protocol integration (HLO, order submission)

## Error Handling

When an invalid command is processed or `get_game_state` is called with an invalid game ID, the server returns a structured error response:

```python
# For invalid game ID
{
    'status': 'error',
    'message': 'Game 999 not found',
    'code': ErrorCode.GAME_NOT_FOUND
}

# For missing arguments
{
    'status': 'error',
    'message': 'REMOVE_PLAYER missing arguments',
    'code': ErrorCode.MISSING_ARGUMENTS
}

# For invalid command
{
    'status': 'error',
    'message': 'Unknown command: FLY_TO_THE_MOON',
    'code': ErrorCode.UNKNOWN_COMMAND
}
```

Error formats are consistent and updated as the server evolves.

## Extensibility and Future Features
- REMOVE_PLAYER <game_id> <player>: Remove a player from a game
- ADVANCE_PHASE <game_id>: Manually advance the game phase
- SAVE_GAME <game_id> / LOAD_GAME <game_id>: Persistence for game state
- Support for multiple concurrent games
- DAIDE protocol for bot/server communication
- User authentication and permissions (future)
- Web or API interface in addition to CLI (future)

## Logging and Monitoring
- Logs startup, shutdown, all processed commands, errors, and game state changes (creation, player add/remove, phase advance)
- Log format: `[timestamp] LEVEL logger: message`
- Log level and output are configurable via environment variables:
  - `DIPLOMACY_LOG_LEVEL` (default: INFO)
  - `DIPLOMACY_LOG_FILE` (default: stdout)

## Configuration and Deployment
- Host and port for DAIDE protocol are configurable in `DAIDEServer`
- Logging level/output configurable via environment variables
- Persistence backend is file-based (pickle), but can be extended
- Server can be run as a background service

## Security Considerations
- Input validation and sanitization for all commands and parameters
- Safe error reporting (no sensitive info)
- (Future) Authentication, encrypted connections, rate limiting

## Interoperability and Integration
- Supports DAIDE protocol for bot/server communication
- Designed for future REST API or WebSocket support
- API versioning and integration testing planned

## Documentation and Maintainability
- All public classes and methods have docstrings
- User and developer documentation is kept up to date
- Changelog and release notes maintained
- Code comments clarify complex logic

## User Registration and Multi-Game Participation

- Users are registered persistently via `/users/persistent_register` (POST, `{telegram_id, full_name}`)
- Users can join any number of games as different powers via `/games/{game_id}/join` (POST, `{telegram_id, game_id, power}`)
- Users can list their games via `/users/{telegram_id}/games` (GET)
- Users can quit a game via `/games/{game_id}/quit` (POST, `{telegram_id, game_id}`)
- Player-to-user mapping is persistent in the database (UserModel, PlayerModel)
- All order and game actions are scoped to the user-game-power relationship

### Example Data Flow
1. User registers: `{telegram_id: "12345", full_name: "Test User"}`
2. User joins game 1 as FRANCE: `{telegram_id: "12345", game_id: 1, power: "FRANCE"}`
3. User joins game 2 as GERMANY: `{telegram_id: "12345", game_id: 2, power: "GERMANY"}`
4. User lists games: returns `[{'game_id': 1, 'power': 'FRANCE'}, {'game_id': 2, 'power': 'GERMANY'}]`
5. User quits game 1: `{telegram_id: "12345", game_id: 1}`
6. User lists games: returns `[{'game_id': 2, 'power': 'GERMANY'}]`

---

Update this spec as the server evolves and new features are implemented.
