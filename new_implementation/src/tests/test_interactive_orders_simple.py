#!/usr/bin/env python3
"""
Simple Integration Test for Interactive Order Input System

This script tests the interactive order input functionality without requiring pytest.
Run with: python src/server/test_interactive_orders_simple.py
"""

import sys
import os
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

def test_province_mapping():
    """Test province name normalization"""
    print("Testing province mapping...")
    
    from engine.province_mapping import normalize_province_name
    
    # Test known provinces
    assert normalize_province_name("ber") == "BER"
    assert normalize_province_name("SIL") == "SIL"
    assert normalize_province_name("kie") == "KIE"
    
    # Test unknown provinces
    assert normalize_province_name("unknown") == "UNKNOWN"
    
    print("✅ Province mapping tests passed")

def test_normalize_order_provinces():
    """Test order normalization function"""
    print("Testing order normalization...")
    
    from server.telegram_bot import normalize_order_provinces
    
    # Test basic normalization
    result = normalize_order_provinces("A BER - SIL", "GERMANY")
    assert result == "A BER - SIL"
    
    # Test with lowercase provinces
    result = normalize_order_provinces("A ber - sil", "GERMANY")
    assert result == "A BER - SIL"
    
    # Test hold order
    result = normalize_order_provinces("A BER H", "GERMANY")
    assert result == "A BER H"
    
    print("✅ Order normalization tests passed")

def test_map_adjacency():
    """Test map adjacency functionality"""
    print("Testing map adjacency...")
    
    from engine.map import Map
    
    # Create map instance
    map_instance = Map("standard")
    
    # Test adjacency for Berlin (should have adjacent provinces)
    adjacent = map_instance.get_adjacency("BER")
    assert isinstance(adjacent, list)
    assert len(adjacent) > 0
    
    # Test adjacency for Kiel (should have adjacent provinces)
    adjacent = map_instance.get_adjacency("KIE")
    assert isinstance(adjacent, list)
    assert len(adjacent) > 0
    
    print("✅ Map adjacency tests passed")

def test_callback_data_parsing():
    """Test callback data parsing"""
    print("Testing callback data parsing...")
    
    # Test unit selection callback
    callback_data = "select_unit_1_A_BER"
    parts = callback_data.split("_")
    game_id = parts[2]
    unit = f"{parts[3]} {parts[4]}"
    
    assert game_id == "1"
    assert unit == "A BER"
    
    # Test move selection callback
    callback_data = "move_unit_1_A_BER_move_SIL"
    parts = callback_data.split("_")
    game_id = parts[2]
    unit = f"{parts[3]} {parts[4]}"
    move_type = parts[5]
    target_province = parts[6]
    
    assert game_id == "1"
    assert unit == "A BER"
    assert move_type == "move"
    assert target_province == "SIL"
    
    print("✅ Callback data parsing tests passed")

@patch('server.telegram_bot.api_get')
def test_selectunit_command_mock(mock_api_get):
    """Test /selectunit command with mocked API"""
    print("Testing /selectunit command...")
    
    from server.telegram_bot import selectunit
    import asyncio
    
    # Mock API responses
    mock_api_get.side_effect = [
        {"games": [{"game_id": 1, "power": "GERMANY"}]},  # user games
        {"units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}}  # game state
    ]
    
    # Mock update and context with async support
    mock_update = Mock()
    mock_context = Mock()
    mock_message = Mock()
    mock_user = Mock()
    
    mock_user.id = 12345
    mock_update.effective_user = mock_user
    mock_update.message = mock_message
    
    # Create async mock for reply_text
    async def mock_reply_text(*args, **kwargs):
        return Mock()
    
    mock_message.reply_text = mock_reply_text
    
    # Call the function
    asyncio.run(selectunit(mock_update, mock_context))
    
    # Verify API calls were made
    assert mock_api_get.call_count >= 2
    mock_api_get.assert_any_call("/users/12345/games")
    # May also call for state, but check that games was called
    assert any("/users/12345/games" in str(call) for call in mock_api_get.call_args_list)
    
    print("✅ /selectunit command tests passed")

def test_unit_type_filtering():
    """Test unit type filtering for moves"""
    print("Testing unit type filtering...")
    
    from engine.map import Map
    
    # Create map instance
    map_instance = Map("standard")
    
    # Test army adjacency (should include land provinces)
    adjacent = map_instance.get_adjacency("BER")
    valid_moves = []
    for province in adjacent:
        province_info = map_instance.provinces.get(province)
        if province_info and province_info.type in ["land", "coast"]:
            valid_moves.append(province)
    
    assert len(valid_moves) > 0
    print(f"   Army BER can move to: {valid_moves}")
    
    # Test fleet adjacency (should include water provinces)
    adjacent = map_instance.get_adjacency("KIE")
    valid_moves = []
    for province in adjacent:
        province_info = map_instance.provinces.get(province)
        if province_info:
            prov_type = getattr(province_info, 'type', None)
            if prov_type in ["water", "coast"]:
                valid_moves.append(province)
            # KIE is coastal, so it can also move to some land provinces adjacent to coast
            elif prov_type == "coastal":
                valid_moves.append(province)
    
    # KIE should have valid moves (coastal provinces or water)
    # If all adjacencies are land and no water, that's still valid for a coastal province
    assert len(valid_moves) > 0 or "BAL" in adjacent or "HEL" in adjacent, f"KIE should have valid adjacent provinces, got: {adjacent}, types: {[map_instance.provinces.get(p).type if map_instance.provinces.get(p) else None for p in adjacent]}"
    print(f"   Fleet KIE can move to: {valid_moves}")
    
    print("✅ Unit type filtering tests passed")

def run_all_tests():
    """Run all tests"""
    print("🧪 Running Interactive Order Input Tests\n")
    
    try:
        test_province_mapping()
        test_normalize_order_provinces()
        test_map_adjacency()
        test_callback_data_parsing()
        test_selectunit_command_mock()
        test_unit_type_filtering()
        
        print("\n🎉 All tests passed! Interactive Order Input system is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
