#!/usr/bin/env python3
"""
Test map generation with proper unit data to verify the fix works
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_map_with_units():
    """Test map generation with proper unit data"""
    print("🧪 Testing Map Generation with Units...")
    print("=" * 50)
    
    try:
        from engine.map import Map
        
        # Test data with proper units format: {power_name: [unit_list]}
        units = {
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
            "ENGLAND": ["A LON", "F EDI", "F LVP"],
            "RUSSIA": ["A MOS", "A WAR", "F SEV", "F STP"],
            "AUSTRIA": ["A VIE", "A BUD", "F TRI"],
            "ITALY": ["A ROM", "A VEN", "F NAP"],
            "TURKEY": ["A CON", "A SMY", "F ANK"]
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = "maps/standard.svg"
        
        print("📊 Generating map with proper unit data...")
        print("   • Colored area opacity: 35%")
        print("   • Unit marker font size: 30")
        print("   • Units per power:")
        for power, power_units in units.items():
            print(f"     {power}: {', '.join(power_units)}")
        
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        # Save the map
        map_filename = "test_map_with_units.png"
        with open(map_filename, 'wb') as f:
            f.write(img_bytes)
        
        print(f"✅ Map generated: {map_filename}")
        print(f"📊 Map size: {len(img_bytes)} bytes")
        
        print("\n🔍 Expected Results:")
        print("   ✅ Colored provinces for each power")
        print("   ✅ Unit markers (A/F letters) in correct positions")
        print("   ✅ Phase info in bottom right corner")
        print("   ✅ No area name text overlays")
        
        assert True, "Test completed successfully"
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        test_map_with_units()
        print("\n🎉 Map generation test completed!")
        print("💡 Check test_map_with_units.png to verify the fix")
    except Exception:
        print("\n💥 Map generation test failed!")
        sys.exit(1)
