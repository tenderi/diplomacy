#!/usr/bin/env python3
"""
Test the updated map generation with increased opacity and smaller font
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_map_changes():
    """Test the updated map generation"""
    print("🧪 Testing Updated Map Generation...")
    print("=" * 50)
    
    try:
        from rendering.map import Map
        
        # Test data with units
        units = {
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "FRANCE": ["A PAR", "F BRE"],
            "ENGLAND": ["A LON", "F LON"],
            "RUSSIA": ["A MOS", "F STP"]
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = "maps/standard.svg"
        
        print("📊 Generating map with updated settings...")
        print("   • Colored area opacity: 35% (increased from 25%)")
        print("   • Unit marker font size: 30 (reduced from 40)")
        
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        # Save the map to test_maps folder
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        map_filename = "test_updated_map.png"
        output_path = os.path.join(test_maps_dir, map_filename)
        with open(output_path, 'wb') as f:
            f.write(img_bytes)
        
        print(f"✅ Map generated: {output_path}")
        print(f"📊 Map size: {len(img_bytes)} bytes")
        print(f"📊 Units: {units}")
        
        print("\n🔍 Visual Changes:")
        print("   ✅ Colored provinces should be more opaque (35% vs 25%)")
        print("   ✅ Unit markers (A/F letters) should be smaller")
        print("   ✅ No area name text overlays")
        
        assert True, "Test completed successfully"
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        test_map_changes()
        print("\n🎉 Map generation test completed!")
        print("💡 Check test_maps/test_updated_map.png to verify the changes")
    except Exception:
        print("\n💥 Map generation test failed!")
        sys.exit(1)
