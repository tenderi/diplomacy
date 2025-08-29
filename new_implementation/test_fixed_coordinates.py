#!/usr/bin/env python3
"""
Test the fixed coordinate system using SVG paths instead of wrong jdipNS coordinates.
"""

import sys
import os
sys.path.append('src')

from src.engine.map import Map

def test_fixed_coordinates():
    """Test the fixed coordinate system."""
    
    print("🎯 Testing Fixed Coordinate System...")
    
    # Test units for different powers to show coloring
    test_units = {
        "ENGLAND": [
            "F LON",    # Fleet in London
            "A EDI",    # Army in Edinburgh
        ],
        "FRANCE": [
            "A PAR",    # Army in Paris
            "F MAR",    # Fleet in Marseilles
        ],
        "GERMANY": [
            "A BER",    # Army in Berlin
            "F KIE",    # Fleet in Kiel
        ],
        "RUSSIA": [
            "A WAR",    # Army in Warsaw
            "F STP",    # Fleet in St. Petersburg
        ],
        "ITALY": [
            "A ROM",    # Army in Rome
            "F VEN",    # Fleet in Venice
        ],
        "AUSTRIA": [
            "A VIE",    # Army in Vienna
            "F TRI",    # Fleet in Trieste
        ],
        "TURKEY": [
            "A CON",    # Army in Constantinople
            "F SMY",    # Fleet in Smyrna
        ]
    }
    
    map_instance = Map()
    output_path = "test_maps/fixed_coordinates_test.png"
    
    print("🎯 Testing fixed coordinate system with all 7 powers...")
    for power, units in test_units.items():
        print(f"  {power}: {', '.join(units)}")
    
    try:
        # Test the coordinate system first
        print(f"\n🔍 Testing coordinate system...")
        coords = Map.get_svg_province_coordinates("maps/standard.svg")
        
        print(f"   Found {len(coords)} province coordinates")
        
        # Check some key provinces
        test_provinces = ['LON', 'EDI', 'MAR', 'VEN', 'ROM', 'PAR', 'BER']
        for prov in test_provinces:
            if prov in coords:
                x, y = coords[prov]
                print(f"   ✅ {prov}: ({x:.1f}, {y:.1f})")
            else:
                print(f"   ❌ {prov}: NOT FOUND")
        
        # Now test the map rendering
        print(f"\n🎨 Testing map rendering with fixed coordinates...")
        map_instance.render_board_png(
            svg_path="maps/standard.svg",
            units=test_units,
            output_path=output_path
        )
        
        print(f"\n✅ Fixed coordinate system test map generated successfully!")
        print(f"📁 Output: {output_path}")
        print(f"📊 Total units: {sum(len(units) for units in test_units.values())}")
        print(f"🎨 Fixed coordinate system features:")
        print(f"   • Uses SVG path centers for unit placement (correct coordinates)")
        print(f"   • Uses SVG paths for province coloring (correct boundaries)")
        print(f"   • NO coordinate transformation needed")
        print(f"   • Units should now be positioned correctly on the map")
        print(f"   • Province coloring should align perfectly with units")
        print(f"   • 80% transparency (51/255) - background shows through")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate fixed coordinate system test map: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fixed_coordinates()
    if success:
        print("\n🎉 Fixed coordinate system test completed successfully!")
        print("🔍 Check the generated map to see correctly positioned units and province coloring!")
    else:
        print("\n💥 Fixed coordinate system test failed!")
        sys.exit(1)
