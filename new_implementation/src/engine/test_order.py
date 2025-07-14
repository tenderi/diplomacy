"""
Tests for order parsing and validation.
"""
import pytest
from engine.order import OrderParser, Order

def test_order_parse():
    order_str = "FRANCE A PAR - BUR"
    order = OrderParser.parse(order_str)
    assert order.power == "FRANCE"
    assert order.unit == "A"
    assert order.action == "PAR"
    assert order.target == "-"

def test_order_validate():
    order = Order("FRANCE", "A PAR", "-", "BUR")
    assert OrderParser.validate(order)
