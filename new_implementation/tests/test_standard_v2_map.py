#!/usr/bin/env python3
"""
Test standard-v2 map generation
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_standard_v2_map():
    """Test standard-v2 map generation"""
    print("🧪 Testing Standard-v2 Map Generation...")
    print("=" * 50)
    
    try:
        from engine.map import Map
        
        # Test that Map can be initialized with standard-v2
        print("📊 Testing Map initialization with standard-v2...")
        map_instance = Map("standard-v2")
        print(f"✅ Map initialized with map_name: {map_instance.map_name}")
        
        # Verify it uses standard map logic (same adjacencies)
        assert map_instance.is_adjacent("PAR", "BUR"), "PAR should be adjacent to BUR"
        assert map_instance.is_adjacent("LON", "YOR"), "LON should be adjacent to YOR"
        print("✅ Adjacencies verified (same as standard map)")
        
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
        
        # Resolve maps dir: under new_implementation (parent of tests/)
        impl_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        maps_dir = os.path.join(impl_root, "maps")
        base_path = os.environ.get("DIPLOMACY_MAP_PATH", os.path.join(maps_dir, "standard.svg"))
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else maps_dir
        svg_path = os.path.join(base_dir, "v2.svg")
        if not os.path.exists(svg_path):
            svg_path = os.path.join(impl_root, "maps", "v2.svg")
        if not os.path.exists(svg_path):
            raise FileNotFoundError(f"v2.svg not found at {svg_path}")
        
        print(f"📊 Using SVG path: {svg_path}")
        print("📊 Generating map with proper unit data...")
        print("   • Map variant: standard-v2")
        print("   • Colored area opacity: 35%")
        print("   • Unit marker font size: 30")
        print("   • Units per power:")
        for power, power_units in units.items():
            print(f"     {power}: {', '.join(power_units)}")
        
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        # Save the map to test_maps folder
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        map_filename = "test_standard_v2_map.png"
        output_path = os.path.join(test_maps_dir, map_filename)
        with open(output_path, 'wb') as f:
            f.write(img_bytes)
        
        print(f"✅ Map generated: {output_path}")
        print(f"📊 Map size: {len(img_bytes)} bytes")
        
        print("\n🔍 Expected Results:")
        print("   ✅ Colored provinces for each power")
        print("   ✅ Unit markers (A/F letters) in correct positions")
        print("   ✅ Phase info in bottom right corner")
        print("   ✅ v2 map visual style (different from standard)")
        
        assert len(img_bytes) > 0, "Map should have content"
        assert os.path.exists(output_path), "Map file should be created"
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        test_standard_v2_map()
        print("\n🎉 Standard-v2 map generation test completed!")
        print("💡 Check test_maps/test_standard_v2_map.png to verify the map")
    except Exception:
        print("\n💥 Standard-v2 map generation test failed!")
        sys.exit(1)

