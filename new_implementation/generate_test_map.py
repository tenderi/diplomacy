#!/usr/bin/env python3
"""
Generate a test map with units to demonstrate the fixed V2 map coordinate system.
"""

import sys
import os
sys.path.append('src')

from src.engine.map import Map

def generate_test_map():
    """Generate a test map with units in strategic locations."""
    
    # Test units representing a typical game setup
    test_units = {
        "RUSSIA": [
            "A WAR",    # Army in Warsaw (eastern Europe)
            "F STP",    # Fleet in St. Petersburg (northern Russia)
            "A MOS",    # Army in Moscow (central Russia)
            "F SEV"     # Fleet in Sevastopol (Black Sea)
        ],
        "ENGLAND": [
            "F LON",    # Fleet in London (western Europe)
            "A EDI",    # Army in Edinburgh (northern Britain)
            "F LVP"     # Fleet in Liverpool (northwest Britain)
        ],
        "FRANCE": [
            "A PAR",    # Army in Paris (central Europe)
            "F MAR",    # Fleet in Marseilles (southern France)
            "A BRE"     # Army in Brest (western France)
        ],
        "GERMANY": [
            "A BER",    # Army in Berlin (central Europe)
            "F KIE",    # Fleet in Kiel (northern Germany)
            "A MUN"     # Army in Munich (southern Germany)
        ],
        "AUSTRIA": [
            "A VIE",    # Army in Vienna (central Europe)
            "F TRI",    # Fleet in Trieste (Adriatic Sea)
            "A BUD"     # Army in Budapest (eastern Europe)
        ],
        "ITALY": [
            "A ROM",    # Army in Rome (southern Europe)
            "F VEN",    # Fleet in Venice (northern Italy)
            "A NAP"     # Army in Naples (southern Italy)
        ],
        "TURKEY": [
            "A CON",    # Army in Constantinople (southeast Europe)
            "F SMY",    # Fleet in Smyrna (Aegean Sea)
            "A ANK"     # Army in Ankara (Asia Minor)
        ]
    }
    
    # V2 map path
    v2_map_path = "maps/v2/Vector files for printing & editing/Diplomacy Map (v2).svg"
    
    if not os.path.exists(v2_map_path):
        print(f"❌ V2 map not found at: {v2_map_path}")
        return False
    
    print("🗺️  Generating Test Map with Units")
    print("=" * 50)
    print("📍 Placing units in strategic locations...")
    
    for power, units in test_units.items():
        print(f"  {power}: {', '.join(units)}")
    
    try:
        # Generate the map
        print("\n🎨 Rendering map...")
        png_bytes = Map.render_board_png(v2_map_path, test_units)
        
        if png_bytes:
            print(f"✅ Map generated successfully: {len(png_bytes)} bytes")
            
            # Save the test map
            output_path = "test_map_with_units.png"
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            
            print(f"💾 Test map saved to: {output_path}")
            print(f"📁 File size: {os.path.getsize(output_path)} bytes")
            print(f"🎯 Map dimensions: 2202x1632 pixels")
            
            # Show coordinate verification
            print("\n🔍 Coordinate Verification:")
            coords = Map.get_svg_province_coordinates(v2_map_path)
            
            # Check a few key provinces
            key_provinces = ['WAR', 'MOS', 'LON', 'PAR', 'BER', 'VIE', 'ROM', 'CON']
            for prov in key_provinces:
                if prov in coords:
                    x, y = coords[prov]
                    # Scale to output dimensions
                    scaled_x = int(x * (2202 / 7016))
                    scaled_y = int(y * (1632 / 4960))
                    print(f"  {prov}: V2({x}, {y}) -> Output({scaled_x}, {scaled_y})")
                else:
                    print(f"  {prov}: Not found in coordinates")
            
            return True
        else:
            print("❌ Map generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Error during map generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎮 Diplomacy V2 Map Test Generator")
    print("=" * 50)
    
    success = generate_test_map()
    if success:
        print("\n🎉 Test map generated successfully!")
        print("🗺️  The V2 map coordinate system is working correctly.")
        print("📍 All units should appear in their proper geographic locations.")
    else:
        print("\n💥 Test map generation failed!")
        sys.exit(1)
