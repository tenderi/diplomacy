# Diplomacy Order Module

Handles order representation, parsing, validation, and execution.

## API
- `Order`: Class representing a single order (move, support, hold, etc.).
- `OrderParser`: Parses and validates orders.

## Usage Example
```python
from engine.order import Order, OrderParser

order = Order('FRANCE', 'A PAR', '-', 'BUR')
parser = OrderParser()
parsed_order = parser.parse('FRANCE A PAR - BUR')
```

## Why tests and implementation matter
Tests ensure order parsing and validation are robust, preventing illegal moves and ensuring correct adjudication. All order types and edge cases are covered by tests.

## Edge Cases
- **Self-dislodgement prohibited:** Orders that would dislodge a unit of the same power are not allowed. The engine ensures both units remain in place if such an order is attempted. See engine/README.md for details.

## See Also
- [../specs/order_spec.md](../../specs/order_spec.md) for detailed order specification.
