#!/usr/bin/env python3
"""
Test using SVG paths directly without coordinate transformation.
"""

import sys
import os
sys.path.append('src')

from src.engine.map import Map

def test_svg_paths_direct():
    """Test using SVG paths directly without transformation."""
    
    print("🎨 Testing SVG Paths Direct (No Transformation)...")
    
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
    output_path = "test_maps/svg_paths_direct_test.png"
    
    print("🎯 Testing SVG paths direct approach with all 7 powers...")
    for power, units in test_units.items():
        print(f"  {power}: {', '.join(units)}")
    
    try:
        # Use the corrected render method
        map_instance.render_board_png(
            svg_path="maps/standard.svg",
            units=test_units,
            output_path=output_path
        )
        print(f"\n✅ SVG paths direct test map generated successfully!")
        print(f"📁 Output: {output_path}")
        print(f"📊 Total units: {sum(len(units) for units in test_units.values())}")
        print(f"🎨 SVG paths direct approach features:")
        print(f"   • Uses actual SVG path data for province shapes")
        print(f"   • NO coordinate transformation needed")
        print(f"   • SVG paths are already in correct position")
        print(f"   • 80% transparency (51/255) - background shows through")
        print(f"   • Actual province boundaries colored, not circles")
        print(f"   • Units drawn on top with solid colors")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to generate SVG paths direct test map: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_svg_paths_direct()
    if success:
        print("\n🎉 SVG paths direct test completed successfully!")
        print("🔍 Check the generated map to see correctly positioned province coloring!")
    else:
        print("\n💥 SVG paths direct test failed!")
        sys.exit(1)
