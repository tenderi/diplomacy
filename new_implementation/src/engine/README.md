# Diplomacy Engine Module

Implements the core game logic, including game state, turn processing, and order resolution.

## API
- `Game`: Main class for managing the game state, phases, and turn processing.
- `Map`: Handles map representation, loading, and validation (see map.py).
- `Power`: Manages player (power) information and unit ownership (see power.py).
- `Order`/`OrderParser`: Handles order representation, parsing, and validation (see order.py).

## Usage Example
```python
from engine.game import Game

game = Game(map_name='standard')
game.add_player('FRANCE')
game.set_orders('FRANCE', ['A PAR - BUR'])
game.process_turn()
state = game.get_state()
print(state)
```

## Module Structure
- `game.py`: Game state, turn processing, and adjudication logic.
- `map.py`: Map and province representation, variant loading.
- `power.py`: Player (power) management.
- `order.py`: Order parsing, validation, and representation.

## Why tests and implementation matter
Tests ensure the game logic is correct and reliable, which is critical for the integrity of the Diplomacy server. All features are covered by unit and integration tests. Strict typing and Ruff compliance are enforced for maintainability.

## Multi-Phase Engine
The engine now uses `process_phase()` to advance the game through movement, retreat, and adjustment phases. All server, API, and tests are fully compatible with this logic. Starting units for each power are assigned per official Diplomacy rules for the standard map.

## See Also
- [server/README.md](../server/README.md) for server usage and integration.
- [../specs/engine_game_spec.md](../../specs/engine_game_spec.md) for detailed engine specification.

## Adjudication Edge Cases
- **Self-dislodgement prohibited:** The engine enforces the Diplomacy rule that a power cannot dislodge its own unit. If a move would dislodge a unit of the same power, both units remain in place. This is covered by automated tests in `test_adjudication.py`.
