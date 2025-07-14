# Map Module Specification

## Purpose
Handles map representation, loading, and validation for standard and variant maps.

## API
- `Map`: Class for representing the board, locations, and adjacency.
  - Methods:
    - `__init__(self, map_name: str = 'standard')`
    - `get_locations(self) -> list[str]`
    - `get_adjacency(self, location: str) -> list[str]`
    - `validate_location(self, location: str) -> bool`

## Expected Behavior
- Loads map data from file or built-in resource.
- Provides access to locations and adjacency information.
- Validates location names.

## Example Usage
```python
from engine.map import Map

map_obj = Map('standard')
locations = map_obj.get_locations()
adj = map_obj.get_adjacency('PAR')
```

## Test Cases
- Test loading standard and variant maps
- Test location and adjacency queries
- Test location validation

---

Update this spec as the module evolves.
