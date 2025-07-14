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

## Why tests and implementation matter
Tests ensure the server correctly processes commands and manages game state, which is critical for reliability and correctness.
