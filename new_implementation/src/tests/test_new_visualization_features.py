#!/usr/bin/env python3
"""
Test new visualization features: orders map, resolution map, conflict markers, status indicators.
"""

import os
import sys
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.engine.map import Map


def test_orders_map_generation():
    """Test render_board_png_orders method"""
    print("🧪 Testing orders map PNG generation...")
    
    # Create test orders
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "pending"},
            {"type": "hold", "unit": "A MAR", "status": "pending"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "pending"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "pending"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "pending"}
        ]
    }
    
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN"]
    }
    
    phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")
    
    output_path = os.path.join(BASE_DIR, "test_maps", "test_orders_map.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generate orders map
    img_bytes = Map.render_board_png_orders(
        svg_path=svg_path,
        units=units,
        orders=orders,
        phase_info=phase_info,
        output_path=output_path
    )
    
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
    
    print(f"✅ Orders map generated: {output_path}")


def test_resolution_map_generation():
    """Test render_board_png_resolution method"""
    print("🧪 Testing resolution map PNG generation...")
    
    # Create test orders with final status
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "failed", "reason": "bounced"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "bounced"}
        ]
    }
    
    units = {
        "FRANCE": ["A BUR", "A MAR", "F BRE"],  # PAR moved to BUR
        "GERMANY": ["A BER", "A MUN"]  # Both bounced, still in place
    }
    
    resolution_data = {
        "conflicts": [
            {
                "province": "BUR",
                "attackers": ["FRANCE"],
                "defender": None,
                "strengths": {"FRANCE": 2},
                "result": "victory"
            }
        ],
        "dislodgements": []
    }
    
    phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")
    
    output_path = os.path.join(BASE_DIR, "test_maps", "test_resolution_map.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generate resolution map
    img_bytes = Map.render_board_png_resolution(
        svg_path=svg_path,
        units=units,
        orders=orders,
        resolution_data=resolution_data,
        phase_info=phase_info,
        output_path=output_path
    )
    
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
    
    print(f"✅ Resolution map generated: {output_path}")


def test_retreat_order_visualization():
    """Test retreat order drawing"""
    print("🧪 Testing retreat order visualization...")
    
    orders = {
        "AUSTRIA": [
            {"type": "retreat", "unit": "A BUD", "target": "VIE", "status": "success"},
            {"type": "retreat", "unit": "F TRI", "target": "VEN", "status": "failed"}
        ]
    }
    
    units = {
        "AUSTRIA": ["DISLODGED_A BUD", "DISLODGED_F TRI"]
    }
    
    phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Retreat",
        "phase_code": "S1901R"
    }
    
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")
    
    output_path = os.path.join(BASE_DIR, "test_maps", "test_retreat_orders.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generate map with retreat orders
    img_bytes = Map.render_board_png_with_orders(
        svg_path=svg_path,
        units=units,
        orders=orders,
        phase_info=phase_info,
        output_path=output_path
    )
    
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
    
    print(f"✅ Retreat order map generated: {output_path}")


def test_conflict_markers():
    """Test conflict marker visualization"""
    print("🧪 Testing conflict markers...")
    
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A MUN", "target": "BUR", "status": "failed", "reason": "bounced"}
        ]
    }
    
    units = {
        "FRANCE": ["A BUR"],
        "GERMANY": ["A MUN"]
    }
    
    resolution_data = {
        "conflicts": [
            {
                "province": "BUR",
                "attackers": ["FRANCE", "GERMANY"],
                "defender": None,
                "strengths": {"FRANCE": 2, "GERMANY": 1},
                "result": "victory"  # FRANCE won
            }
        ],
        "dislodgements": []
    }
    
    phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")
    
    output_path = os.path.join(BASE_DIR, "test_maps", "test_conflict_markers.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generate resolution map with conflicts
    img_bytes = Map.render_board_png_resolution(
        svg_path=svg_path,
        units=units,
        orders=orders,
        resolution_data=resolution_data,
        phase_info=phase_info,
        output_path=output_path
    )
    
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
    
    print(f"✅ Conflict marker map generated: {output_path}")


def test_status_indicators():
    """Test success/failure status indicators"""
    print("🧪 Testing status indicators...")
    
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "move", "unit": "A MAR", "target": "PIE", "status": "failed", "reason": "bounced"}
        ],
        "ENGLAND": [
            {"type": "support", "unit": "F LON", "supporting": "A PAR - BUR", "status": "failed", "reason": "cut"}
        ]
    }
    
    units = {
        "FRANCE": ["A BUR", "A MAR"],
        "ENGLAND": ["F LON"]
    }
    
    phase_info = {
        "year": "1901",
        "season": "Spring",
        "phase": "Movement",
        "phase_code": "S1901M"
    }
    
    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")
    
    output_path = os.path.join(BASE_DIR, "test_maps", "test_status_indicators.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Generate resolution map with status indicators
    resolution_data = {"conflicts": [], "dislodgements": []}
    
    img_bytes = Map.render_board_png_resolution(
        svg_path=svg_path,
        units=units,
        orders=orders,
        resolution_data=resolution_data,
        phase_info=phase_info,
        output_path=output_path
    )
    
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
    
    print(f"✅ Status indicators map generated: {output_path}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

