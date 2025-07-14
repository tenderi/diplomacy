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
```

## Test Cases
- Test server startup and shutdown
- Test command processing for all game actions
- Test game state queries

---

Update this spec as the module evolves.
