#!/usr/bin/env python3
"""
Example usage of the Order Visualization System.
Demonstrates how to use both orders dictionary and moves dictionary formats.
"""

import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from engine.map import Map

def example_orders_dictionary():
    """Example using orders dictionary format"""
    print("📋 Example: Orders Dictionary Format")
    
    # Define orders in the comprehensive format
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"},
            {"type": "build", "unit": "", "target": "PAR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
            {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"},
            {"type": "destroy", "unit": "A PRU", "status": "success"}
        ]
    }
    
    # Define units
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN", "F KIE", "A PRU"]
    }
    
    # Generate map
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    output_path = os.path.join(BASE_DIR, "test_maps", "example_orders_dict.png")
    
    img_bytes = Map.render_board_png_with_orders(
        svg_path=svg_path,
        units=units,
        orders=orders,
        phase_info={"turn": 1, "season": "Spring", "phase": "Movement"},
        output_path=output_path
    )
    
    print(f"✅ Generated: {output_path}")
    return img_bytes

def example_moves_dictionary():
    """Example using moves dictionary format"""
    print("\n📋 Example: Moves Dictionary Format")
    
    # Define moves in the alternative format
    moves = {
        "FRANCE": {
            "successful": ["A PAR - BUR", "F BRE - ENG"],
            "failed": ["A MAR - SPA"],
            "bounced": ["F ENG - IRI"],
            "holds": ["A BUR"],
            "supports": ["A BUR S A PAR - HOL"],
            "convoys": ["F ENG C A PAR - HOL"],
            "builds": ["BUILD A PAR"],
            "destroys": ["DESTROY A MAR"]
        },
        "GERMANY": {
            "successful": ["A BER - SIL", "F KIE - BAL"],
            "failed": ["A MUN - TYR"],
            "bounced": ["F BAL - BOT"],
            "holds": ["A SIL"],
            "supports": ["A SIL S A BER - PRU"],
            "convoys": ["F BAL C A BER - LVN"],
            "builds": ["BUILD F KIE"],
            "destroys": ["DESTROY A MUN"]
        }
    }
    
    # Define units
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE", "F ENG", "A BUR"],
        "GERMANY": ["A BER", "A MUN", "F KIE", "F BAL", "A SIL"]
    }
    
    # Generate map
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    output_path = os.path.join(BASE_DIR, "test_maps", "example_moves_dict.png")
    
    img_bytes = Map.render_board_png_with_moves(
        svg_path=svg_path,
        units=units,
        moves=moves,
        phase_info={"turn": 1, "season": "Spring", "phase": "Movement"},
        output_path=output_path
    )
    
    print(f"✅ Generated: {output_path}")
    return img_bytes

def main():
    """Run examples"""
    print("🎯 Order Visualization System Examples")
    print("=" * 50)
    
    # Ensure test_maps directory exists
    os.makedirs(os.path.join(BASE_DIR, "test_maps"), exist_ok=True)
    
    # Run examples
    example_orders_dictionary()
    example_moves_dictionary()
    
    print("\n" + "=" * 50)
    print("🎉 Examples completed!")
    print("\n📁 Generated example maps:")
    print("   - example_orders_dict.png")
    print("   - example_moves_dict.png")
    print("\n🔍 Check the test_maps directory to see the visual results!")

if __name__ == "__main__":
    main()
