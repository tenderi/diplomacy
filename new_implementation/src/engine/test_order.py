"""
Tests for order parsing and validation.
"""
import pytest
from engine.order import OrderParser, Order

def test_order_parse():
    order_str = "FRANCE A PAR - BUR"
    order = OrderParser.parse(order_str)
    assert order.power == "FRANCE"
    assert order.unit == "A PAR"
    assert order.action == "-"
    assert order.target == "BUR"

    # Test invalid order (too short)
    try:
        OrderParser.parse("FRANCE A PAR")
        assert False, "Should raise ValueError for invalid order format"
    except ValueError:
        pass


def test_order_validate():
    # Valid order
    order = Order("FRANCE", "A PAR", "-", "BUR")
    game_state = {"powers": ["FRANCE"], "orders": {"FRANCE": ["A PAR - BUR"]}}
    assert OrderParser.validate(order, game_state)
    # Invalid power
    order2 = Order("GERMANY", "A BER", "-", "MUN")
    assert not OrderParser.validate(order2, game_state)
    # Invalid action
    order3 = Order("FRANCE", "A PAR", "X", "BUR")
    assert not OrderParser.validate(order3, game_state)
    # Missing target for move
    order4 = Order("FRANCE", "A PAR", "-", None)
    assert not OrderParser.validate(order4, game_state)
