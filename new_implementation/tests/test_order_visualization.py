"""Tests for order visualization rendering: orders dict -> PNG bytes."""
from __future__ import annotations

import os

import pytest

from rendering.map import Map

pytestmark = pytest.mark.map

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_STANDARD_SVG = os.path.join(BASE_DIR, "..", "maps", "standard.svg")

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_orders_dictionary_format_renders_png(tmp_path):
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"},
            {"type": "build", "unit": "", "target": "PAR", "status": "success"},
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
            {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"},
            {"type": "destroy", "unit": "A PRU", "status": "success"},
        ],
        "ENGLAND": [
            {"type": "move", "unit": "F LON", "target": "NTH", "status": "bounced"},
            {
                "type": "support",
                "unit": "A LVP",
                "supporting": "F LON - NTH",
                "status": "failed",
                "reason": "cut_support",
            },
        ],
    }
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
        "GERMANY": ["A BER", "A MUN", "F KIE", "A PRU"],
        "ENGLAND": ["F LON", "A LVP"],
    }
    phase_info = {"turn": 1, "season": "Spring", "phase": "Movement", "phase_code": "S1901M"}
    output_path = str(tmp_path / "test_orders_visualization.png")

    img_bytes = Map.render_board_png_orders(
        svg_path=_STANDARD_SVG,
        units=units,
        orders=orders,
        phase_info=phase_info,
        output_path=output_path,
    )

    assert img_bytes.startswith(_PNG_MAGIC)
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)


def test_comprehensive_order_types_render_png(tmp_path):
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "move", "unit": "A MAR", "target": "SPA", "status": "failed", "reason": "bounced"},
            {"type": "move", "unit": "F BRE", "target": "ENG", "status": "bounced"},
            {"type": "hold", "unit": "A BUR", "status": "success"},
            {"type": "support", "unit": "F ENG", "supporting": "A PAR - HOL", "status": "success"},
            {"type": "support", "unit": "A PIC", "supporting": "A BUR", "status": "success"},
            {
                "type": "support",
                "unit": "A GAS",
                "supporting": "A MAR - SPA",
                "status": "failed",
                "reason": "cut_support",
            },
            {"type": "convoy", "unit": "F ENG", "target": "HOL", "via": ["ENG"], "status": "success"},
            {
                "type": "convoy",
                "unit": "F IRI",
                "target": "WAL",
                "via": ["IRI"],
                "status": "failed",
                "reason": "convoy_disrupted",
            },
            {"type": "build", "unit": "", "target": "PAR", "status": "success"},
            {"type": "build", "unit": "", "target": "MAR", "status": "failed", "reason": "no_supply_center"},
            {"type": "destroy", "unit": "A MAR", "status": "success"},
        ]
    }
    units = {"FRANCE": ["A PAR", "A MAR", "F BRE", "F ENG", "A BUR", "A PIC", "A GAS", "F IRI"]}
    phase_info = {"turn": 1, "season": "Spring", "phase": "Movement", "phase_code": "S1901M"}
    output_path = str(tmp_path / "test_comprehensive_orders.png")

    img_bytes = Map.render_board_png_orders(
        svg_path=_STANDARD_SVG,
        units=units,
        orders=orders,
        phase_info=phase_info,
        output_path=output_path,
    )

    assert img_bytes.startswith(_PNG_MAGIC)
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
