#!/usr/bin/env python3
"""
Simple coordinate test to debug V2 map unit placement.
"""

import os
import datetime
from src.engine.map import Map

def test_simple_coordinates():
    """Test with just a few units in very different locations."""
    
    # Test with just 3 units in very different locations
    test_units = {
        'ENGLAND': ['F LON'],      # Top-left area
        'RUSSIA': ['F STP'],       # Top-right area  
        'TURKEY': ['F CON']        # Bottom-right area
    }
    
    svg_path = "maps/v2/Vector files for printing & editing/Diplomacy Map (v2).svg"
    
    print("🧪 Simple Coordinate Test")
    print("=" * 40)
    print(f"Testing: {svg_path}")
    
    # Get coordinates
    coords = Map.get_svg_province_coordinates(svg_path)
    print(f"\n📍 Coordinates found:")
    for prov in ['LON', 'STP', 'CON']:
        if prov in coords:
            print(f"  {prov}: {coords[prov]}")
        else:
            print(f"  {prov}: NOT FOUND")
    
    # Render map
    print(f"\n🎯 Rendering map with {sum(len(units) for units in test_units.values())} units...")
    png_bytes = Map.render_board_png(svg_path, test_units)
    
    # Save
    os.makedirs("test_maps", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_simple_coordinates_test.png"
    output_file = os.path.join("test_maps", filename)
    
    with open(output_file, 'wb') as f:
        f.write(png_bytes)
    
    print(f"✅ Saved as: {filename}")
    print(f"📁 Output: {output_file}")
    
    return True

if __name__ == "__main__":
    test_simple_coordinates()
