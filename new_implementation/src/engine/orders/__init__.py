"""Order grammar: parsing, canonical formatting, and validation.

``parser`` owns the one grammar for turning order text into ``engine.types``
``Order`` dataclasses (and back). ``validation`` owns the one structural
validation path used everywhere an order needs a legality check before
adjudication.
"""

from __future__ import annotations

from engine.orders.parser import OrderParseError, format_order, parse_order
from engine.orders.validation import ValidationResult, validate

__all__ = [
    "OrderParseError",
    "ValidationResult",
    "format_order",
    "parse_order",
    "validate",
]
