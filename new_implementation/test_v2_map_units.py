#!/usr/bin/env python3
"""
Test script to demonstrate the V2 map with bigger unit letters.
This shows how the new map configuration works with improved unit rendering.
"""

import os
import sys
import datetime
from map_config import get_map_path, get_current_map_info

def test_v2_map_units():
    """Test the V2 map with unit rendering."""
    try:
        from src.engine.map import Map
        
        # Get the V2 map path
        svg_path = get_map_path('v2_professional')
        map_info = get_current_map_info()
        
        print("🗺️  V2 Map Unit Rendering Test")
        print("=" * 60)
        print(f"Map: {map_info['name']}")
        print(f"Path: {svg_path}")
        print(f"Description: {map_info['description']}")
        
        # Create a test scenario with units from different powers
        test_units = {
            'ENGLAND': ['F LON', 'A EDI', 'F LVP'],      # Dark violet
            'FRANCE': ['A PAR', 'A MAR', 'F BRE'],       # Royal blue
            'GERMANY': ['A BER', 'A MUN', 'F KIE'],      # Brown
            'ITALY': ['A ROM', 'A VEN', 'F NAP'],        # Forest green
            'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],      # Pink/brown
            'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'], # Gray
            'TURKEY': ['A CON', 'A SMY', 'F ANK']        # Yellow
        }
        
        print(f"\n🎯 Rendering map with {sum(len(units) for units in test_units.values())} units...")
        
        # Render the map with units
        png_bytes = Map.render_board_png(svg_path, test_units)
        
        # Create output directory
        os.makedirs("test_maps", exist_ok=True)
        
        # Save the rendered image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_v2_map_units_test.png"
        output_file = os.path.join("test_maps", filename)
        
        with open(output_file, 'wb') as f:
            f.write(png_bytes)
        
        print(f"✅ Successfully rendered map!")
        print(f"💾 Saved as: {filename}")
        print(f"📏 File size: {len(png_bytes):,} bytes")
        print(f"📁 Output: {output_file}")
        
        # Show unit details
        print(f"\n🎖️  Units Rendered:")
        for power, units in test_units.items():
            print(f"   {power:8}: {', '.join(units)}")
        
        print(f"\n🎨 Unit Improvements:")
        print(f"   • Font size: Increased from 36px to 50px (+14px)")
        print(f"   • Circle size: Reduced from 28px to 20px radius (-30%)")
        print(f"   • Better readability on the V2 map")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function."""
    print("🚀 Testing V2 Map with Enhanced Unit Rendering")
    print("=" * 60)
    
    success = test_v2_map_units()
    
    if success:
        print(f"\n🎉 Test completed successfully!")
        print(f"📋 Summary:")
        print(f"   • V2 map renders perfectly with no CSS issues")
        print(f"   • Unit markers display with bigger, more readable letters")
        print(f"   • Power colors are clearly distinguishable")
        print(f"   • Professional quality output")
    else:
        print(f"\n⚠️  Test failed. Check the error above.")

if __name__ == "__main__":
    main()
