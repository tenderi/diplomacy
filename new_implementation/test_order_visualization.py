#!/usr/bin/env python3
"""
Test script for order visualization system.
Tests both orders dictionary format and moves dictionary format.
"""

import os
import sys
sys.path.append('/home/helgejalonen/diplomacy/new_implementation')

from src.engine.map import Map

def test_orders_dictionary_format():
    """Test orders dictionary format visualization"""
    print("🧪 Testing Orders Dictionary Format Visualization...")
    
    # Create test orders in orders dictionary format
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"},
            {"type": "build", "unit": "", "target": "PAR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
            {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"},
            {"type": "destroy", "unit": "A PRU", "status": "success"}
        ],
        "ENGLAND": [
            {"type": "move", "unit": "F LON", "target": "NTH", "status": "bounced"},
            {"type": "support", "unit": "A LVP", "supporting": "F LON - NTH", "status": "failed", "reason": "cut_support"}
        ]
    }
    
    # Test units
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN", "F KIE", "A PRU"],
        "ENGLAND": ["F LON", "A LVP"]
    }
    
    # Phase info
    phase_info = {
        "turn": 1,
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    # Generate map with orders visualization
    svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
    output_path = "/home/helgejalonen/diplomacy/new_implementation/test_maps/test_orders_visualization.png"
    
    try:
        img_bytes = Map.render_board_png_with_orders(
            svg_path=svg_path,
            units=units,
            orders=orders,
            phase_info=phase_info,
            output_path=output_path
        )
        
        print(f"✅ Orders dictionary format test passed!")
        print(f"📁 Generated map: {output_path}")
        print(f"📊 Image size: {len(img_bytes)} bytes")
        
    except Exception as e:
        print(f"❌ Orders dictionary format test failed: {e}")
        return False
    
    return True

def test_moves_dictionary_format():
    """Test moves dictionary format visualization"""
    print("\n🧪 Testing Moves Dictionary Format Visualization...")
    
    # Create test moves in moves dictionary format
    moves = {
        "FRANCE": {
            "successful": ["A PAR - BUR", "F BRE - ENG"],
            "failed": ["A MAR - SPA"],
            "bounced": ["F ENG - IRI"],
            "holds": ["A BUR"],
            "supports": ["A BUR S A PAR - HOL", "F ENG S F BRE - NTH"],
            "convoys": ["F ENG C A PAR - HOL"],
            "builds": ["BUILD A PAR"],
            "destroys": ["DESTROY A MAR"]
        },
        "GERMANY": {
            "successful": ["A BER - SIL", "F KIE - BAL"],
            "failed": ["A MUN - TYR"],
            "bounced": ["F BAL - BOT"],
            "holds": ["A SIL"],
            "supports": ["A SIL S A BER - PRU"],
            "convoys": ["F BAL C A BER - LVN"],
            "builds": ["BUILD F KIE"],
            "destroys": ["DESTROY A MUN"]
        }
    }
    
    # Test units
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE", "F ENG", "A BUR"],
        "GERMANY": ["A BER", "A MUN", "F KIE", "F BAL", "A SIL"]
    }
    
    # Phase info
    phase_info = {
        "turn": 1,
        "season": "Spring", 
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    # Generate map with moves visualization
    svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
    output_path = "/home/helgejalonen/diplomacy/new_implementation/test_maps/test_moves_visualization.png"
    
    try:
        img_bytes = Map.render_board_png_with_moves(
            svg_path=svg_path,
            units=units,
            moves=moves,
            phase_info=phase_info,
            output_path=output_path
        )
        
        print(f"✅ Moves dictionary format test passed!")
        print(f"📁 Generated map: {output_path}")
        print(f"📊 Image size: {len(img_bytes)} bytes")
        
    except Exception as e:
        print(f"❌ Moves dictionary format test failed: {e}")
        return False
    
    return True

def test_comprehensive_order_types():
    """Test all order types comprehensively"""
    print("\n🧪 Testing Comprehensive Order Types...")
    
    # Create comprehensive test orders
    orders = {
        "FRANCE": [
            # Successful move
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            # Failed move
            {"type": "move", "unit": "A MAR", "target": "SPA", "status": "failed", "reason": "bounced"},
            # Bounced move
            {"type": "move", "unit": "F BRE", "target": "ENG", "status": "bounced"},
            # Hold
            {"type": "hold", "unit": "A BUR", "status": "success"},
            # Support move
            {"type": "support", "unit": "F ENG", "supporting": "A PAR - HOL", "status": "success"},
            # Support hold
            {"type": "support", "unit": "A PIC", "supporting": "A BUR", "status": "success"},
            # Failed support
            {"type": "support", "unit": "A GAS", "supporting": "A MAR - SPA", "status": "failed", "reason": "cut_support"},
            # Convoy
            {"type": "convoy", "unit": "F ENG", "target": "HOL", "via": ["ENG"], "status": "success"},
            # Failed convoy
            {"type": "convoy", "unit": "F IRI", "target": "WAL", "via": ["IRI"], "status": "failed", "reason": "convoy_disrupted"},
            # Build
            {"type": "build", "unit": "", "target": "PAR", "status": "success"},
            # Failed build
            {"type": "build", "unit": "", "target": "MAR", "status": "failed", "reason": "no_supply_center"},
            # Destroy
            {"type": "destroy", "unit": "A MAR", "status": "success"}
        ]
    }
    
    # Test units
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE", "F ENG", "A BUR", "A PIC", "A GAS", "F IRI"]
    }
    
    # Phase info
    phase_info = {
        "turn": 1,
        "season": "Spring",
        "phase": "Movement", 
        "phase_code": "S1901M"
    }
    
    # Generate comprehensive test map
    svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
    output_path = "/home/helgejalonen/diplomacy/new_implementation/test_maps/test_comprehensive_orders.png"
    
    try:
        img_bytes = Map.render_board_png_with_orders(
            svg_path=svg_path,
            units=units,
            orders=orders,
            phase_info=phase_info,
            output_path=output_path
        )
        
        print(f"✅ Comprehensive order types test passed!")
        print(f"📁 Generated map: {output_path}")
        print(f"📊 Image size: {len(img_bytes)} bytes")
        
    except Exception as e:
        print(f"❌ Comprehensive order types test failed: {e}")
        return False
    
    return True

def main():
    """Run all order visualization tests"""
    print("🎯 Order Visualization System Test Suite")
    print("=" * 50)
    
    # Ensure test_maps directory exists
    os.makedirs("/home/helgejalonen/diplomacy/new_implementation/test_maps", exist_ok=True)
    
    # Run tests
    tests = [
        test_orders_dictionary_format,
        test_moves_dictionary_format, 
        test_comprehensive_order_types
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All order visualization tests passed!")
        print("\n📁 Generated test maps:")
        print("   - test_orders_visualization.png")
        print("   - test_moves_visualization.png") 
        print("   - test_comprehensive_orders.png")
        print("\n🔍 Check the test_maps directory to verify visual results!")
    else:
        print("❌ Some tests failed. Check the error messages above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
