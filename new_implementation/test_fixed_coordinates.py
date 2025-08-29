#!/usr/bin/env python3
"""
Test with fixed, known coordinates to debug the rendering system.
"""

import os
import datetime
from src.engine.map import Map

def test_fixed_coordinates():
    """Test with fixed coordinates to see if rendering works."""
    
    # Test with units at fixed, known coordinates
    # These are just test coordinates to see if the rendering system works
    test_units = {
        'ENGLAND': ['F TEST1'],      # Top-left
        'RUSSIA': ['F TEST2'],       # Top-right  
        'TURKEY': ['F TEST3']        # Bottom-right
    }
    
    svg_path = "maps/v2/Vector files for printing & editing/Diplomacy Map (v2).svg"
    
    print("🧪 Fixed Coordinate Test")
    print("=" * 40)
    print(f"Testing: {svg_path}")
    
    # Override coordinates with fixed test values
    coords = {
        'TEST1': (100, 100),    # Top-left area
        'TEST2': (2000, 100),   # Top-right area
        'TEST3': (2000, 1500)   # Bottom-right area
    }
    
    print(f"\n📍 Using fixed test coordinates:")
    for prov, coord in coords.items():
        print(f"  {prov}: {coord}")
    
    # Render map with fixed coordinates
    print(f"\n🎯 Rendering map with {sum(len(units) for units in test_units.values())} units...")
    
    # Temporarily override the coordinate system
    original_get_coords = Map.get_svg_province_coordinates
    Map.get_svg_province_coordinates = lambda x: coords
    
    try:
        png_bytes = Map.render_board_png(svg_path, test_units)
        
        # Save
        os.makedirs("test_maps", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_fixed_coordinates_test.png"
        output_file = os.path.join("test_maps", filename)
        
        with open(output_file, 'wb') as f:
            f.write(png_bytes)
        
        print(f"✅ Saved as: {filename}")
        print(f"📁 Output: {output_file}")
        
    finally:
        # Restore original method
        Map.get_svg_province_coordinates = original_get_coords
    
    return True

if __name__ == "__main__":
    test_fixed_coordinates()
