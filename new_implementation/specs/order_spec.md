# Order Module Specification

## Purpose
Handles order representation, parsing, validation, and execution.

## API
- `Order`: Class representing a single order (move, support, hold, etc.)
  - Methods:
    - `__init__(self, order_str: str)`
    - `is_valid(self, game_state: dict) -> bool`
    - `execute(self, game_state: dict) -> dict`
- `OrderParser`: Parses and validates orders
  - Methods:
    - `parse(self, order_str: str) -> Order`
    - `validate(self, order: Order, game_state: dict) -> bool`

## Expected Behavior
- Parses order strings into objects.
- Validates orders against the current game state.
- Executes orders to update game state.

## Example Usage
```python
from orders.order import Order
from orders.order_parser import OrderParser

order = Order('A PAR - BUR')
parser = OrderParser()
parsed_order = parser.parse('A PAR - BUR')
valid = parser.validate(parsed_order, game_state)
```

## Test Cases
- Test parsing valid and invalid orders
- Test order validation
- Test order execution and state updates

## Validation Details (July 2025)
- Validation now checks:
  - Power existence
  - Unit ownership (unit must belong to power)
  - Action validity (must be one of '-', 'H', 'S', 'C')
  - For moves: target must be present, valid, and adjacent (if map is provided)
  - For supports: target must be present
  - For convoys: only fleets can convoy, target must be present
  - For holds: must not have a target
- Validation returns a tuple (bool, str): pass/fail and error message.
- Tests cover valid, invalid, and edge-case orders, and check error messages.

---

Update this spec as the module evolves.
