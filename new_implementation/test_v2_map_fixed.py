#!/usr/bin/env python3
"""
Test script to verify V2 map coordinate system is working correctly.
"""

import sys
import os
sys.path.append('src')

from src.engine.map import Map

def test_v2_map_coordinates():
    """Test V2 map coordinate system with known unit placements."""
    
    # Test units in strategic locations
    test_units = {
        "RUSSIA": ["A WAR", "F STP", "A MOS"],
        "ENGLAND": ["F LON", "A EDI", "F LVP"],
        "FRANCE": ["A PAR", "F MAR", "A BRE"],
        "GERMANY": ["A BER", "F KIE", "A MUN"],
        "AUSTRIA": ["A VIE", "F TRI", "A BUD"],
        "ITALY": ["A ROM", "F VEN", "A NAP"],
        "TURKEY": ["A CON", "F SMY", "A ANK"]
    }
    
    # V2 map path
    v2_map_path = "maps/v2/Vector files for printing & editing/Diplomacy Map (v2).svg"
    
    if not os.path.exists(v2_map_path):
        print(f"❌ V2 map not found at: {v2_map_path}")
        return False
    
    print("🗺️  Testing V2 Map Coordinate System")
    print("=" * 50)
    
    try:
        # Test coordinate extraction
        coords = Map.get_svg_province_coordinates(v2_map_path)
        print(f"✅ Extracted {len(coords)} province coordinates")
        
        # Test specific key provinces
        key_provinces = ['WAR', 'MOS', 'LON', 'PAR', 'BER', 'VIE', 'ROM', 'CON']
        for prov in key_provinces:
            if prov in coords:
                x, y = coords[prov]
                print(f"📍 {prov}: ({x}, {y})")
            else:
                print(f"❌ {prov}: Not found in coordinates")
        
        # Test map rendering
        print("\n🎨 Testing map rendering...")
        png_bytes = Map.render_board_png(v2_map_path, test_units)
        
        if png_bytes:
            print(f"✅ Map rendered successfully: {len(png_bytes)} bytes")
            
            # Save test output
            output_path = "test_v2_map_fixed.png"
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            print(f"💾 Test map saved to: {output_path}")
            
            return True
        else:
            print("❌ Map rendering failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_v2_map_coordinates()
    if success:
        print("\n🎉 V2 map coordinate system test PASSED!")
    else:
        print("\n💥 V2 map coordinate system test FAILED!")
        sys.exit(1)
