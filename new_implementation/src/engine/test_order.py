"""
Tests for order parsing and validation.
"""
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
    game_state: dict[str, object] = {
        "powers": ["FRANCE"],
        "units": {"FRANCE": ["A PAR"]},
        "map_obj": None  # Could mock for adjacency tests
    }
    valid, msg = OrderParser.validate(order, game_state)
    assert valid, f"Expected valid order, got error: {msg}"
    # Invalid power
    order2 = Order("GERMANY", "A BER", "-", "MUN")
    valid, msg = OrderParser.validate(order2, game_state)
    assert not valid and "Power 'GERMANY' does not exist" in msg
    # Invalid action
    order3 = Order("FRANCE", "A PAR", "X", "BUR")
    valid, msg = OrderParser.validate(order3, game_state)
    assert not valid and "Invalid action" in msg
    # Missing target for move
    order4 = Order("FRANCE", "A PAR", "-", None)
    valid, msg = OrderParser.validate(order4, game_state)
    assert not valid and "missing target" in msg
    # Unit does not belong to power
    order5 = Order("FRANCE", "A MAR", "-", "BUR")
    valid, msg = OrderParser.validate(order5, game_state)
    assert not valid and "does not belong" in msg
    # Hold order with target
    order6 = Order("FRANCE", "A PAR", "H", "BUR")
    valid, msg = OrderParser.validate(order6, game_state)
    assert not valid and "Hold order should not have a target" in msg
    # Convoy order with army
    order7 = Order("FRANCE", "A PAR", "C", "BUR")
    valid, msg = OrderParser.validate(order7, game_state)
    assert not valid and "Only fleets can perform convoy orders" in msg
