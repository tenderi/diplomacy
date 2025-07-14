# Diplomacy Power Module

Manages player (power) information, assignments, and unit ownership.

## API
- `Power`: Class representing a player and their units.
  - Methods:
    - `__init__(self, name: str)`
    - `add_unit(self, unit: str)`
    - `remove_unit(self, unit: str)`
    - `get_units(self) -> list[str]`
    - `get_name(self) -> str`

## Usage Example
```python
from engine.power import Power

power = Power('FRANCE')
power.add_unit('A PAR')
units = power.get_units()
```

## Why tests and implementation matter
Tests ensure player management is robust, units are tracked correctly, and game state is consistent.

## See Also
- [../specs/power_spec.md](../../specs/power_spec.md) for detailed power specification.
