# Server Module Specification

## Purpose
Implements the server loop, command processing, and network interface (CLI or API) for managing games.

## API
- `Server`: Main class for accepting and processing game commands.
  - Methods:
    - `__init__(self)`
    - `start(self)`
    - `process_command(self, command: str)`
    - `get_game_state(self, game_id: str) -> dict`

## Expected Behavior
- Starts a server loop to accept commands.
- Processes commands to create games, add players, set orders, and advance turns.
- Provides access to current game state.

## Example Usage
```python
from server.server import Server

server = Server()
server.start()
server.process_command('CREATE_GAME standard')
server.process_command('ADD_PLAYER 1 FRANCE')
server.process_command('SET_ORDERS 1 FRANCE "A PAR - BUR"')
state = server.get_game_state('1')
print(state)  # Should show current game state as a dict
```

## Game State Structure
The dictionary returned by `get_game_state(game_id)` should include at least:
- `game_id`: Unique identifier for the game
- `phase`: Current phase (e.g., 'Spring 1901 Movement')
- `players`: List or dict of players in the game
- `units`: Mapping of player to their units and locations
- `orders`: Mapping of player to their current orders (if any)
- Any other relevant game metadata (e.g., status, turn number)

Keep this structure up to date as the server and engine evolve.

## Example Game State Output
Example output from `get_game_state('1')`:
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
    'turn_number': 1
}
```
Field types and nested structures should be documented and updated as the game model evolves.

## Test Cases
- Test server startup and shutdown
- Test command processing for all game actions
- Test game state queries (using `get_game_state`)
- Test error handling for invalid commands and duplicate player/game creation

## Error Handling

When an invalid command is processed or `get_game_state` is called with an invalid game ID, the server should return a structured error response. Example:

```python
# For invalid game ID
{
    'error': 'Game not found',
    'game_id': '999'
}

# For invalid command
{
    'error': 'Invalid command',
    'details': 'Unrecognized command: FLY_TO_THE_MOON'
}
```

Error formats should be consistent and updated in this spec as the server evolves.

## Extensibility and Future Features

As the server evolves, consider supporting additional commands and features, such as:
- `REMOVE_PLAYER <game_id> <player>`: Remove a player from a game
- `ADVANCE_PHASE <game_id>`: Manually advance the game phase
- `SAVE_GAME <game_id>` / `LOAD_GAME <game_id>`: Persistence for game state
- Support for multiple concurrent games
- User authentication and permissions
- Web or API interface in addition to CLI

If the API changes, document versioning and backward compatibility requirements here.

Always update this spec and the corresponding tests as new features are implemented.

## Logging and Monitoring

The server should log key events for debugging and operational monitoring, including:
- Startup and shutdown events
- All processed commands (with timestamps)
- Errors and exceptions (with stack traces if possible)
- Game state changes (optional, for auditability)

Recommended log format: timestamped, structured (e.g., JSON or key-value pairs), with log levels (INFO, WARNING, ERROR).

Update this section as logging and monitoring requirements evolve.

## Configuration and Deployment

The server should support configuration for key operational parameters, such as:
- Host and port for network interface
- Persistence backend (e.g., file, database)
- Debug or production mode
- Logging level and output location

Configuration can be provided via environment variables, command-line arguments, or configuration files (e.g., YAML, JSON, .env).

Deployment considerations:
- Should be runnable as a background service (e.g., systemd, supervisor)
- Optionally provide a Dockerfile for containerized deployment
- Document any dependencies or setup steps required for deployment

Update this section as configuration and deployment practices evolve.

## Security Considerations

The server should implement basic security measures, including:
- Input validation and sanitization for all commands and parameters
- Safe error reporting (avoid leaking sensitive information)
- (Future) Authentication for command and state queries
- (Future) Support for encrypted connections (e.g., TLS/SSL)
- (Future) Rate limiting and abuse prevention

Update this section as security requirements and features evolve.

## Interoperability and Integration

The server should be designed for interoperability with other clients and systems. Considerations include:
- Support for standard protocols (e.g., DAIDE, REST API, WebSocket) for client-server communication
- Clear and up-to-date API documentation (e.g., OpenAPI/Swagger for REST)
- Versioning of public APIs to ensure backward compatibility
- Integration testing with external clients and tools

Update this section as integration requirements and supported protocols evolve.

## Documentation and Maintainability

- All public classes and methods should have clear docstrings describing their purpose, parameters, and return values.
- User and developer documentation (e.g., README, API docs) must be kept up to date with new features and changes.
- Maintain a changelog or release notes for significant updates.
- Use code comments to clarify complex logic or design decisions.

Update this section as documentation and maintainability practices evolve.

---

Note: As new commands or features are added, update this spec with usage examples, expected outputs, and new test cases to ensure extensibility and clarity.
