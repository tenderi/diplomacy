# Diplomacy Client Module

Minimal client interface for testing and interacting with the server (CLI or API).

## API
- `Client`: Class for sending commands to the server and receiving updates.
  - Methods:
    - `__init__(self, server_address: str)`
    - `send_command(self, command: str)`
    - `get_update(self) -> dict`

## Usage Example
```python
from client import Client

client = Client('localhost:5000')
client.send_command('CREATE_GAME standard')
update = client.get_update()
```

## Why tests and implementation matter
Tests ensure the client can communicate with the server, send commands, and receive updates reliably. This is essential for integration and end-to-end testing.

## See Also
- [../specs/client_spec.md](../../specs/client_spec.md) for detailed client specification.
