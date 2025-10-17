#!/usr/bin/env python3
"""
Test script for new data models and order parsing.

This script tests the new data models, database schema, and order parsing
to ensure they work correctly and fix the order visualization issues.
"""

import os
import sys
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from engine.data_models import (
    GameState, PowerState, Unit, OrderType, OrderStatus, GameStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder,
    MapData, Province
)
from engine.order_parser import OrderParser, OrderParseError, OrderValidationError
from engine.database_service import DatabaseService


def test_data_models():
    """Test basic data model functionality"""
    print("🧪 Testing data models...")
    
    # Test Unit creation
    unit = Unit(unit_type="A", province="PAR", power="FRANCE")
    assert str(unit) == "A PAR"
    assert unit.to_dict()["unit_type"] == "A"
    assert unit.to_dict()["province"] == "PAR"
    assert unit.to_dict()["power"] == "FRANCE"
    
    # Test PowerState creation
    power_state = PowerState(
        power_name="FRANCE",
        units=[unit],
        controlled_supply_centers=["PAR", "MAR"]
    )
    assert power_state.get_unit_count() == 1
    assert power_state.get_supply_center_count() == 2
    assert power_state.needs_builds() == True  # 2 supply centers > 1 unit
    
    print("✅ Data models working correctly!")


def test_order_parsing():
    """Test order parsing functionality"""
    print("🧪 Testing order parsing...")
    
    parser = OrderParser()
    
    # Test move order parsing
    parsed = parser.parse_order_text("A PAR - BUR", "FRANCE")
    assert parsed.order_type == OrderType.MOVE
    assert parsed.power == "FRANCE"
    assert parsed.unit_type == "A"
    assert parsed.unit_province == "PAR"
    assert parsed.target_province == "BUR"
    
    # Test hold order parsing
    parsed = parser.parse_order_text("F LON H", "ENGLAND")
    assert parsed.order_type == OrderType.HOLD
    assert parsed.power == "ENGLAND"
    assert parsed.unit_type == "F"
    assert parsed.unit_province == "LON"
    
    # Test support order parsing
    parsed = parser.parse_order_text("A BUR S A PAR - MAR", "FRANCE")
    assert parsed.order_type == OrderType.SUPPORT
    assert parsed.power == "FRANCE"
    assert parsed.unit_type == "A"
    assert parsed.unit_province == "BUR"
    assert parsed.supported_unit_type == "A"
    assert parsed.supported_unit_province == "PAR"
    assert parsed.supported_target == "MAR"
    
    # Test convoy order parsing
    parsed = parser.parse_order_text("F NTH C A LON - BEL", "ENGLAND")
    assert parsed.order_type == OrderType.CONVOY
    assert parsed.power == "ENGLAND"
    assert parsed.unit_type == "F"
    assert parsed.unit_province == "NTH"
    assert parsed.convoyed_unit_type == "A"
    assert parsed.convoyed_unit_province == "LON"
    assert parsed.convoyed_target == "BEL"
    
    # Test build order parsing
    parsed = parser.parse_order_text("BUILD A PAR", "FRANCE")
    assert parsed.order_type == OrderType.BUILD
    assert parsed.power == "FRANCE"
    assert parsed.build_type == "A"
    assert parsed.build_province == "PAR"
    
    # Test destroy order parsing
    parsed = parser.parse_order_text("DESTROY A MUN", "GERMANY")
    assert parsed.order_type == OrderType.DESTROY
    assert parsed.power == "GERMANY"
    assert parsed.destroy_unit_type == "A"
    assert parsed.destroy_unit_province == "MUN"
    
    # Test power name removal
    parsed = parser.parse_order_text("GERMANY A BER - SIL", "GERMANY")
    assert parsed.order_type == OrderType.MOVE
    assert parsed.power == "GERMANY"
    assert parsed.unit_type == "A"
    assert parsed.unit_province == "BER"
    assert parsed.target_province == "SIL"
    
    print("✅ Order parsing working correctly!")


def test_database_operations():
    """Test database operations"""
    print("🧪 Testing database operations...")
    
    # Use in-memory SQLite for testing
    database_url = "sqlite:///:memory:"
    
    # Create schema first
    from engine.database import create_database_schema
    engine = create_database_schema(database_url)
    
    # Create DatabaseService with the same engine
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine)
    db_service = DatabaseService(database_url)
    db_service.session_factory = session_factory
    
    # Create a game
    game_state = db_service.create_game("test_game_1", "standard")
    assert game_state.game_id == "test_game_1"
    assert game_state.map_name == "standard"
    assert game_state.current_turn == 0
    assert game_state.current_year == 1901
    assert game_state.current_season == "Spring"
    assert game_state.current_phase == "Movement"
    assert game_state.phase_code == "S1901M"
    assert game_state.status == GameStatus.ACTIVE
    
    # Add a player
    power_state = db_service.add_player("test_game_1", "FRANCE")
    assert power_state.power_name == "FRANCE"
    assert power_state.is_active == True
    assert power_state.is_eliminated == False
    
    # Add a unit
    unit = Unit(unit_type="A", province="PAR", power="FRANCE")
    db_service.add_unit("test_game_1", "FRANCE", unit)
    
    # Get game state
    retrieved_state = db_service.get_game_state("test_game_1")
    assert retrieved_state is not None
    assert retrieved_state.game_id == "test_game_1"
    assert "FRANCE" in retrieved_state.powers
    assert len(retrieved_state.powers["FRANCE"].units) == 1
    assert retrieved_state.powers["FRANCE"].units[0].unit_type == "A"
    assert retrieved_state.powers["FRANCE"].units[0].province == "PAR"
    
    print("✅ Database operations working correctly!")


def test_order_creation_and_validation():
    """Test order creation and validation"""
    print("🧪 Testing order creation and validation...")
    
    # Create a test game state
    unit = Unit(unit_type="A", province="PAR", power="FRANCE")
    power_state = PowerState(
        power_name="FRANCE",
        units=[unit],
        controlled_supply_centers=["PAR", "MAR"]
    )
    
    map_data = MapData(
        map_name="standard",
            provinces={
                "PAR": Province(name="PAR", province_type="land", is_supply_center=True, is_home_supply_center=True),
                "BUR": Province(name="BUR", province_type="land", is_supply_center=False, is_home_supply_center=False),
                "MAR": Province(name="MAR", province_type="coastal", is_supply_center=True, is_home_supply_center=True),
                "MOS": Province(name="MOS", province_type="land", is_supply_center=True, is_home_supply_center=True)
            },
        supply_centers=["PAR", "MAR"],
        home_supply_centers={"FRANCE": ["PAR", "MAR"]},
        starting_positions={}
    )
    
    # Add adjacency
    map_data.provinces["PAR"].adjacent_provinces = ["BUR"]
    map_data.provinces["BUR"].adjacent_provinces = ["PAR"]
    
    game_state = GameState(
        game_id="test_game_2",
        map_name="standard",
        current_turn=1,
        current_year=1901,
        current_season="Spring",
        current_phase="Movement",
        phase_code="S1901M",
        status=GameStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        powers={"FRANCE": power_state},
        map_data=map_data,
        orders={}
    )
    
    # Test order creation
    parser = OrderParser()
    
    # Parse and create move order
    parsed = parser.parse_order_text("A PAR - BUR", "FRANCE")
    move_order = parser.create_order_from_parsed(parsed, game_state)
    
    assert isinstance(move_order, MoveOrder)
    assert move_order.power == "FRANCE"
    assert move_order.unit.unit_type == "A"
    assert move_order.unit.province == "PAR"
    assert move_order.target_province == "BUR"
    assert move_order.order_type == OrderType.MOVE
    
    # Test order validation
    valid, reason = move_order.validate(game_state)
    assert valid == True, f"Move order validation failed: {reason}"
    
    # Test invalid order (non-adjacent move) - use a truly non-adjacent province
    parsed_invalid = parser.parse_order_text("A PAR - MOS", "FRANCE")
    try:
        invalid_order = parser.create_order_from_parsed(parsed_invalid, game_state)
        valid, reason = invalid_order.validate(game_state)
        assert valid == False, "Non-adjacent move should be invalid"
        assert "non-adjacent" in reason.lower()
    except OrderValidationError:
        # This is also acceptable - validation can fail during creation
        pass
    
    print("✅ Order creation and validation working correctly!")


def test_multiple_orders_parsing():
    """Test parsing multiple orders"""
    print("🧪 Testing multiple orders parsing...")
    
    parser = OrderParser()
    
    orders_text = """
    A PAR - BUR;
    F BRE H;
    A MAR S A PAR - BUR
    """
    
    parsed_orders = parser.parse_orders(orders_text, "FRANCE")
    
    assert len(parsed_orders) == 3
    
    # Check first order (move)
    assert parsed_orders[0].order_type == OrderType.MOVE
    assert parsed_orders[0].unit_type == "A"
    assert parsed_orders[0].unit_province == "PAR"
    assert parsed_orders[0].target_province == "BUR"
    
    # Check second order (hold)
    assert parsed_orders[1].order_type == OrderType.HOLD
    assert parsed_orders[1].unit_type == "F"
    assert parsed_orders[1].unit_province == "BRE"
    
    # Check third order (support)
    assert parsed_orders[2].order_type == OrderType.SUPPORT
    assert parsed_orders[2].unit_type == "A"
    assert parsed_orders[2].unit_province == "MAR"
    assert parsed_orders[2].supported_unit_type == "A"
    assert parsed_orders[2].supported_unit_province == "PAR"
    assert parsed_orders[2].supported_target == "BUR"
    
    print("✅ Multiple orders parsing working correctly!")


def main():
    """Run all tests"""
    print("🚀 Starting comprehensive data model tests...\n")
    
    try:
        test_data_models()
        print()
        
        test_order_parsing()
        print()
        
        test_database_operations()
        print()
        
        test_order_creation_and_validation()
        print()
        
        test_multiple_orders_parsing()
        print()
        
        print("🎉 All tests passed successfully!")
        print("✅ New data models are working correctly!")
        print("🔧 Ready to fix order visualization issues!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
