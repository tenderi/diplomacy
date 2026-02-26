#!/usr/bin/env python3
"""
Generate a test map from a real adjudication so you can see what happened.

Runs Game('standard') with a real scenario (e.g. PAR-BUR vs BUR-PAR standoff),
process_turn(), then renders the resulting state to test_maps/test_adjudication_result.png.
"""

import os
import sys
import pytest

# Project root (new_implementation)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from engine.game import Game
from engine.data_models import Unit
from engine.map import Map


def test_generated_map_from_real_adjudication():
    """Run real adjudication and write board state to test_maps for visual inspection."""
    game = Game("standard")
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    # Standoff: PAR-BUR and BUR-PAR (both bounce)
    game.game_state.powers["FRANCE"].units = [Unit(unit_type="A", province="PAR", power="FRANCE")]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type="A", province="BUR", power="GERMANY")]
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A BUR - PAR"])
    game.process_turn()
    # Post-standoff: both units still in place
    assert any(u.province == "PAR" for u in game.game_state.powers["FRANCE"].units)
    assert any(u.province == "BUR" for u in game.game_state.powers["GERMANY"].units)

    # Build units dict for Map: "A PAR" -> "FRANCE", etc.
    units = {}
    for power_name, power in game.game_state.powers.items():
        for u in power.units:
            units[f"{u.unit_type} {u.province}"] = power_name

    phase_info = {
        "turn": game.turn,
        "year": game.year,
        "season": game.season,
        "phase": game.phase,
        "phase_code": game.phase_code,
    }
    supply_center_control = {}
    for power_name, power in game.game_state.powers.items():
        for sc in power.controlled_supply_centers:
            supply_center_control[sc] = power_name

    svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG map not found at {svg_path}")

    test_maps_dir = os.path.join(BASE_DIR, "test_maps")
    os.makedirs(test_maps_dir, exist_ok=True)
    output_path = os.path.join(test_maps_dir, "test_adjudication_result.png")

    img_bytes = Map.render_board_png(
        svg_path,
        units,
        output_path=output_path,
        phase_info=phase_info,
        supply_center_control=supply_center_control,
    )
    assert img_bytes is not None
    assert len(img_bytes) > 0
    assert os.path.exists(output_path)
