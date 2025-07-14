# Player (Power) Module Specification

## Purpose
Manages player (power) information, assignments, and unit ownership.

## API
- `Power`: Class representing a player and their units.
  - Methods:
    - `__init__(self, name: str)`
    - `add_unit(self, unit: str)`
    - `remove_unit(self, unit: str)`
    - `get_units(self) -> list[str]`
    - `get_name(self) -> str`

## Expected Behavior
- Initializes with a player name.
- Manages units owned by the player.
- Provides access to player name and units.

## Example Usage
```python
from engine.power import Power

power = Power('FRANCE')
power.add_unit('A PAR')
units = power.get_units()
```

## Test Cases
- Test player creation
- Test adding and removing units
- Test unit queries

---

Update this spec as the module evolves.
