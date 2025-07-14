# Diplomacy Map Module

Handles map representation, loading, and validation for standard and variant maps.

## API
- `Map`: Class for representing the board, locations, and adjacency.
  - Methods:
    - `__init__(self, map_name: str = 'standard')`
    - `get_locations(self) -> list[str]`
    - `get_adjacency(self, location: str) -> list[str]`
    - `validate_location(self, location: str) -> bool`

## Usage Example
```python
from engine.map import Map

# Load the standard map
map_obj = Map('standard')
locations = map_obj.get_locations()
adj = map_obj.get_adjacency('PAR')

# Load a variant map (see maps/mini_variant.json for format)
variant_map = Map('mini_variant')
print(variant_map.get_locations())
```

## Map Variants
- Standard map is built-in.
- Additional variants can be loaded from JSON files in the `/maps/` directory (see `mini_variant.json` for format).

## Why tests and implementation matter
Tests ensure map logic is correct, all locations and adjacencies are valid, and variants load as expected. Strict validation prevents game logic errors.

## See Also
- [../specs/map_spec.md](../../specs/map_spec.md) for detailed map specification.
