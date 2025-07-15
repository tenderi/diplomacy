# Client Module Specification

## Purpose
Implements a minimal client interface for testing and interacting with the server (CLI or API).

## API
- `Client`: Class for sending commands to the server and receiving updates.
  - Methods:
    - `__init__(self, server_address: str)`
    - `send_command(self, command: str)`
    - `get_update(self) -> dict`

## Expected Behavior
- Connects to the server (local or remote).
- Sends commands and receives updates.
- Used for testing and development.

## Example Usage
```python
from client.client import Client

client = Client('localhost:5000')
client.send_command('CREATE_GAME standard')
update = client.get_update()
```

## Test Cases
- Test client-server connection
- Test sending commands and receiving updates
- Test error handling for invalid commands

## User Registration and Multi-Game Participation

- Users must register persistently via `/register` (Telegram bot) or `/users/persistent_register` (API).
- Users can join any number of games as different powers using `/join <game_id> <power>` (bot) or `/games/{game_id}/join` (API).
- Users can list their games with `/games` (bot) or `/users/{telegram_id}/games` (API).
- Users can quit a game with `/quit <game_id>` (bot) or `/games/{game_id}/quit` (API).
- All order commands must specify the game context if the user is in multiple games.

### Example Bot Interactions
```
/register
# -> Registered as Test User (id: 12345). Use /join <game_id> <power> to join a game.
/join 1 FRANCE
# -> You have joined game 1 as FRANCE.
/games
# -> Your games:
#    Game 1 as FRANCE
/quit 1
# -> You have quit game 1.
```

### Example API Interactions
See server README for endpoint details and usage examples.

---

Update this spec as the module evolves.
