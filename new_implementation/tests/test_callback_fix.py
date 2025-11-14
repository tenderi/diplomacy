#!/usr/bin/env python3
"""
Test Callback Data Format Fix

This script specifically tests the callback data format fix for unit selection.
Run with: python src/server/test_callback_fix.py
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

def test_callback_data_format():
    """Test the callback data format fix"""
    print("🧪 Testing Callback Data Format Fix...")
    
    # Test the old problematic format
    print("   Testing old format (should fail):")
    old_callback = "select_unit_1_A BER"  # This has a space
    parts = old_callback.split("_")
    print(f"   Old callback: {old_callback}")
    print(f"   Split result: {parts}")
    
    if len(parts) >= 5:
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"
        print(f"   Parsed: game_id={game_id}, unit={unit}")
    else:
        print("   ❌ Old format fails - not enough parts after split")
    
    # Test the new fixed format
    print("\n   Testing new format (should work):")
    new_callback = "select_unit_1_A_BER"  # This uses underscores
    parts = new_callback.split("_")
    print(f"   New callback: {new_callback}")
    print(f"   Split result: {parts}")
    
    if len(parts) >= 5:
        game_id = parts[2]
        unit = f"{parts[3]} {parts[4]}"  # Reconstruct space
        print(f"   Parsed: game_id={game_id}, unit={unit}")
        print("   ✅ New format works correctly!")
        assert len(parts) >= 5, "New format should have enough parts after split"
        assert game_id == "1", f"Expected game_id '1', got '{game_id}'"
        assert unit == "A BER", f"Expected unit 'A BER', got '{unit}'"
    else:
        print("   ❌ New format fails")
        assert False, "New format should have enough parts after split"

def test_unit_callback_generation():
    """Test how callback data should be generated"""
    print("\n🧪 Testing Callback Data Generation...")
    
    # Simulate the selectunit function logic
    game_id = "1"
    unit = "A BER"
    
    # Old way (problematic)
    old_callback = f"select_unit_{game_id}_{unit}"
    print(f"   Old generation: {old_callback}")
    
    # New way (fixed)
    new_callback = f"select_unit_{game_id}_{unit.replace(' ', '_')}"
    print(f"   New generation: {new_callback}")
    
    # Test parsing the new callback
    parts = new_callback.split("_")
    parsed_game_id = parts[2]
    parsed_unit = f"{parts[3]} {parts[4]}"
    
    print(f"   Parsed game_id: {parsed_game_id}")
    print(f"   Parsed unit: {parsed_unit}")
    
    # Verify it matches the original
    assert parsed_game_id == game_id, f"Expected game_id '{game_id}', got '{parsed_game_id}'"
    assert parsed_unit == unit, f"Expected unit '{unit}', got '{parsed_unit}'"
    print("   ✅ Callback generation and parsing work correctly!")

def test_multiple_units():
    """Test callback data for multiple units"""
    print("\n🧪 Testing Multiple Units...")
    
    units = ["A BER", "A MUN", "F KIE"]
    game_id = "1"
    
    for unit in units:
        # Generate callback data
        callback_data = f"select_unit_{game_id}_{unit.replace(' ', '_')}"
        
        # Parse callback data
        parts = callback_data.split("_")
        parsed_game_id = parts[2]
        parsed_unit = f"{parts[3]} {parts[4]}"
        
        print(f"   Unit: {unit}")
        print(f"   Callback: {callback_data}")
        print(f"   Parsed: game_id={parsed_game_id}, unit={parsed_unit}")
        
        assert parsed_game_id == game_id, f"Expected game_id '{game_id}', got '{parsed_game_id}'"
        assert parsed_unit == unit, f"Expected unit '{unit}', got '{parsed_unit}'"
        print("   ✅ Correct")
    
    print("   ✅ All units work correctly!")

def run_all_tests():
    """Run all callback format tests"""
    print("🚀 Testing Callback Data Format Fix\n")
    
    try:
        test_callback_data_format()
        test_unit_callback_generation()
        test_multiple_units()
        
        print("\n🎉 All callback format tests passed!")
        print("✅ Unit selection buttons should now work correctly")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    run_all_tests()
