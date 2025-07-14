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

---

Update this spec as the module evolves.
