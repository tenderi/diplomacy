#!/usr/bin/env python3
"""
Test script for order visualization system using new data models.

This script tests the enhanced order visualization system to ensure
it correctly handles order-to-unit mapping and power ownership validation.
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
from engine.order_visualization import OrderVisualizationService


def create_test_game_state():
    """Create a test game state with proper data"""
    # Create test units
    france_units = [
        Unit(unit_type="A", province="PAR", power="FRANCE"),
        Unit(unit_type="A", province="MAR", power="FRANCE"),
        Unit(unit_type="F", province="BRE", power="FRANCE")
    ]
    
    germany_units = [
        Unit(unit_type="A", province="BER", power="GERMANY"),
        Unit(unit_type="A", province="MUN", power="GERMANY"),
        Unit(unit_type="F", province="KIE", power="GERMANY")
    ]
    
    england_units = [
        Unit(unit_type="A", province="LON", power="ENGLAND"),
        Unit(unit_type="F", province="NTH", power="ENGLAND"),
        Unit(unit_type="F", province="ENG", power="ENGLAND")
    ]
    
    # Create power states
    france_state = PowerState(
        power_name="FRANCE",
        units=france_units,
        controlled_supply_centers=["PAR", "MAR", "BRE"]
    )
    
    germany_state = PowerState(
        power_name="GERMANY",
        units=germany_units,
        controlled_supply_centers=["BER", "MUN", "KIE"]
    )
    
    england_state = PowerState(
        power_name="ENGLAND",
        units=england_units,
        controlled_supply_centers=["LON", "NTH", "ENG"]
    )
    
    # Create map data
    provinces = {
        "PAR": Province(name="PAR", province_type="land", is_supply_center=True, is_home_supply_center=True),
        "MAR": Province(name="MAR", province_type="coastal", is_supply_center=True, is_home_supply_center=True),
        "BRE": Province(name="BRE", province_type="coastal", is_supply_center=True, is_home_supply_center=True),
        "BER": Province(name="BER", province_type="land", is_supply_center=True, is_home_supply_center=True),
        "MUN": Province(name="MUN", province_type="land", is_supply_center=True, is_home_supply_center=True),
        "KIE": Province(name="KIE", province_type="coastal", is_supply_center=True, is_home_supply_center=True),
        "LON": Province(name="LON", province_type="coastal", is_supply_center=True, is_home_supply_center=True),
        "NTH": Province(name="NTH", province_type="sea", is_supply_center=True, is_home_supply_center=True),
        "ENG": Province(name="ENG", province_type="sea", is_supply_center=True, is_home_supply_center=True),
        "BUR": Province(name="BUR", province_type="land", is_supply_center=False, is_home_supply_center=False),
        "BEL": Province(name="BEL", province_type="coastal", is_supply_center=False, is_home_supply_center=False),
        "HOL": Province(name="HOL", province_type="coastal", is_supply_center=False, is_home_supply_center=False)
    }
    
    # Add adjacencies
    provinces["PAR"].adjacent_provinces = ["BUR", "MAR"]
    provinces["MAR"].adjacent_provinces = ["PAR", "BRE"]
    provinces["BRE"].adjacent_provinces = ["MAR", "ENG"]
    provinces["BER"].adjacent_provinces = ["MUN", "KIE"]
    provinces["MUN"].adjacent_provinces = ["BER", "BUR"]
    provinces["KIE"].adjacent_provinces = ["BER", "HOL"]
    provinces["LON"].adjacent_provinces = ["NTH", "ENG", "BEL"]  # Add BEL adjacency
    provinces["NTH"].adjacent_provinces = ["LON", "HOL"]
    provinces["ENG"].adjacent_provinces = ["LON", "BRE"]
    provinces["BUR"].adjacent_provinces = ["PAR", "MUN", "BEL"]
    provinces["BEL"].adjacent_provinces = ["BUR", "HOL", "LON"]  # Add LON adjacency
    provinces["HOL"].adjacent_provinces = ["BEL", "KIE", "NTH"]
    
    map_data = MapData(
        map_name="test",
        provinces=provinces,
        supply_centers=["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "LON", "NTH", "ENG"],
        home_supply_centers={
            "FRANCE": ["PAR", "MAR", "BRE"],
            "GERMANY": ["BER", "MUN", "KIE"],
            "ENGLAND": ["LON", "NTH", "ENG"]
        },
        starting_positions={}
    )
    
    # Create test orders
    france_orders = [
        MoveOrder(
            power="FRANCE",
            unit=france_units[0],  # A PAR
            order_type=OrderType.MOVE,
            phase="Movement",
            target_province="BUR",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        HoldOrder(
            power="FRANCE",
            unit=france_units[1],  # A MAR
            order_type=OrderType.HOLD,
            phase="Movement",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        SupportOrder(
            power="FRANCE",
            unit=france_units[2],  # F BRE
            order_type=OrderType.SUPPORT,
            phase="Movement",
            supported_unit=france_units[0],  # A PAR
            supported_action="move",
            supported_target="BUR",
            status=OrderStatus.SUCCESS  # Set to success for testing
        )
    ]
    
    germany_orders = [
        MoveOrder(
            power="GERMANY",
            unit=germany_units[0],  # A BER
            order_type=OrderType.MOVE,
            phase="Movement",
            target_province="MUN",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        HoldOrder(
            power="GERMANY",
            unit=germany_units[1],  # A MUN
            order_type=OrderType.HOLD,
            phase="Movement",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        ConvoyOrder(
            power="GERMANY",
            unit=germany_units[2],  # F KIE
            order_type=OrderType.CONVOY,
            phase="Movement",
            convoyed_unit=germany_units[0],  # A BER
            convoyed_target="HOL",
            status=OrderStatus.SUCCESS  # Set to success for testing
        )
    ]
    
    england_orders = [
        MoveOrder(
            power="ENGLAND",
            unit=england_units[0],  # A LON
            order_type=OrderType.MOVE,
            phase="Movement",
            target_province="BEL",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        HoldOrder(
            power="ENGLAND",
            unit=england_units[1],  # F NTH
            order_type=OrderType.HOLD,
            phase="Movement",
            status=OrderStatus.SUCCESS  # Set to success for testing
        ),
        SupportOrder(
            power="ENGLAND",
            unit=england_units[2],  # F ENG
            order_type=OrderType.SUPPORT,
            phase="Movement",
            supported_unit=england_units[0],  # A LON
            supported_action="move",
            supported_target="BEL",
            status=OrderStatus.SUCCESS  # Set to success for testing
        )
    ]
    
    # Create game state
    game_state = GameState(
        game_id="test_game",
        map_name="test",
        current_turn=1,
        current_year=1901,
        current_season="Spring",
        current_phase="Movement",
        phase_code="S1901M",
        status=GameStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        powers={
            "FRANCE": france_state,
            "GERMANY": germany_state,
            "ENGLAND": england_state
        },
        map_data=map_data,
        orders={
            "FRANCE": france_orders,
            "GERMANY": germany_orders,
            "ENGLAND": england_orders
        }
    )
    
    return game_state


def test_order_visualization():
    """Test order visualization system"""
    print("🧪 Testing order visualization system...")
    
    # Create test game state
    game_state = create_test_game_state()
    
    # Create visualization service
    viz_service = OrderVisualizationService()
    
    # Test order visualization data creation
    viz_data = viz_service.create_visualization_data(game_state)
    
    # Verify visualization data structure
    assert "FRANCE" in viz_data
    assert "GERMANY" in viz_data
    assert "ENGLAND" in viz_data
    
    # Check France orders
    france_orders = viz_data["FRANCE"]
    assert len(france_orders) == 3
    
    # Check move order
    move_order = next((o for o in france_orders if o["type"] == "move"), None)
    assert move_order is not None
    assert move_order["unit"] == "A PAR"
    assert move_order["target"] == "BUR"
    assert move_order["power"] == "FRANCE"
    
    # Check hold order
    hold_order = next((o for o in france_orders if o["type"] == "hold"), None)
    assert hold_order is not None
    assert hold_order["unit"] == "A MAR"
    assert hold_order["power"] == "FRANCE"
    
    # Check support order
    support_order = next((o for o in france_orders if o["type"] == "support"), None)
    assert support_order is not None
    assert support_order["unit"] == "F BRE"
    assert support_order["supporting"] == "A PAR"
    assert support_order["supported_target"] == "BUR"
    assert support_order["power"] == "FRANCE"
    
    # Test validation
    valid, errors = viz_service.validate_visualization_data(viz_data, game_state)
    assert valid, f"Validation failed: {errors}"
    
    # Test moves visualization data
    moves_data = viz_service.create_moves_visualization_data(game_state)
    
    assert "FRANCE" in moves_data
    assert "GERMANY" in moves_data
    assert "ENGLAND" in moves_data
    
    # Check France moves
    france_moves = moves_data["FRANCE"]
    print(f"France moves: {france_moves}")  # Debug output
    assert len(france_moves["successful"]) == 1  # Move order
    assert len(france_moves["holds"]) == 1      # Hold order
    assert len(france_moves["supports"]) == 1   # Support order
    
    print("✅ Order visualization system working correctly!")


def test_validation_system():
    """Test state validation system"""
    print("🧪 Testing state validation system...")
    
    # Create test game state
    game_state = create_test_game_state()
    
    # Test overall game state validation
    valid, errors = game_state.validate_game_state()
    assert valid, f"Game state validation failed: {errors}"
    
    # Test unit positions validation
    valid, errors = game_state.validate_unit_positions()
    assert valid, f"Unit positions validation failed: {errors}"
    
    # Test supply centers validation
    valid, errors = game_state.validate_supply_centers()
    assert valid, f"Supply centers validation failed: {errors}"
    
    # Test power states validation
    valid, errors = game_state.validate_power_states()
    assert valid, f"Power states validation failed: {errors}"
    
    # Test orders validation
    valid, errors = game_state.validate_orders_for_phase()
    assert valid, f"Orders validation failed: {errors}"
    
    # Test validation report
    report = game_state.get_validation_report()
    assert "VALID" in report
    assert "INVALID" not in report
    
    print("✅ State validation system working correctly!")


def test_corrupted_data_detection():
    """Test detection of corrupted data"""
    print("🧪 Testing corrupted data detection...")
    
    # Create test game state
    game_state = create_test_game_state()
    
    # Corrupt the data by adding an order with wrong power
    corrupted_order = MoveOrder(
        power="GERMANY",  # Wrong power!
        unit=game_state.powers["FRANCE"].units[0],  # French unit
        order_type=OrderType.MOVE,
        phase="Movement",
        target_province="BUR"
    )
    game_state.orders["FRANCE"].append(corrupted_order)
    
    # Test validation - should detect the corruption
    valid, errors = game_state.validate_game_state()
    print(f"Game state validation: valid={valid}, errors={errors}")  # Debug output
    assert not valid, "Should detect corrupted data"
    assert any("belongs to GERMANY but is in FRANCE's orders" in error for error in errors)
    
    # Test visualization - should handle corruption gracefully by filtering invalid orders
    viz_service = OrderVisualizationService()
    viz_data = viz_service.create_visualization_data(game_state)
    
    # The corrupted order should be filtered out, so validation should pass
    valid, errors = viz_service.validate_visualization_data(viz_data, game_state)
    print(f"Validation result: valid={valid}, errors={errors}")  # Debug output
    assert valid, "Visualization should handle corruption gracefully by filtering invalid orders"
    
    print("✅ Corrupted data detection working correctly!")


def test_order_visualization_report():
    """Test order visualization report generation"""
    print("🧪 Testing order visualization report...")
    
    # Create test game state
    game_state = create_test_game_state()
    
    # Create visualization service
    viz_service = OrderVisualizationService()
    
    # Generate report
    report = viz_service.get_visualization_report(game_state)
    
    # Check report content
    assert "Order Visualization Report" in report
    assert "FRANCE Orders" in report
    assert "GERMANY Orders" in report
    assert "ENGLAND Orders" in report
    assert "A PAR → BUR" in report  # France move order
    assert "A MAR H" in report       # France hold order
    assert "F BRE S A PAR → BUR" in report  # France support order
    
    print("✅ Order visualization report working correctly!")


def main():
    """Run all tests"""
    print("🚀 Starting order visualization system tests...\n")
    
    try:
        test_order_visualization()
        print()
        
        test_validation_system()
        print()
        
        test_corrupted_data_detection()
        print()
        
        test_order_visualization_report()
        print()
        
        print("🎉 All tests passed successfully!")
        print("✅ Order visualization system is working correctly!")
        print("🔧 Order visualization data corruption issues are FIXED!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
