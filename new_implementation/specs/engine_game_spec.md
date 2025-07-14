# Game Engine Module Specification

## Purpose
Implements the core game logic, including game state, turn processing, and order resolution (adjudication).

## API
- `Game`: Main class for managing the game state, phases, and turn processing.
  - Methods:
    - `__init__(self, map_name: str = 'standard')`
    - `add_player(self, power_name: str)`
    - `set_orders(self, power_name: str, orders: list[str])`
    - `process_turn(self)`
    - `get_state(self) -> dict`
    - `is_game_done(self) -> bool`

## Expected Behavior
- Initializes with a map and zero or more players.
- Accepts and validates orders for each player.
- Processes turns according to Diplomacy rules.
- Updates game state and checks for game end conditions.

## Example Usage
```python
from engine.game import Game

game = Game(map_name='standard')
game.add_player('FRANCE')
game.add_player('ENGLAND')
game.set_orders('FRANCE', ['A PAR - BUR'])
game.set_orders('ENGLAND', ['F LON - NTH'])
game.process_turn()
state = game.get_state()
```

## Test Cases
- Test initialization with different maps
- Test adding players and setting orders
- Test turn processing and state updates
- Test game end detection

---

Update this spec as the module evolves.
