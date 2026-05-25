"""
Real-scenario map rendering tests.

Verifies that render_board_png / render_board_png_with_orders produce valid PNG
output for representative game states and that dislodged-unit coordinates differ
from regular province coordinates.
"""
import io
import os
import pytest
from PIL import Image

from engine.game import Game
from engine.data_models import Unit
from engine.map import Map

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_PATH = os.path.join(BASE_DIR, "maps", "standard.svg")

pytestmark = pytest.mark.map


@pytest.fixture(autouse=True)
def require_svg():
    if not os.path.exists(SVG_PATH):
        pytest.skip(f"SVG map not found at {SVG_PATH}")


def test_dislodged_unit_rendering():
    """Dislodged coords from SVG differ from regular coords; map renders with dislodged unit."""
    regular = Map.get_svg_province_coordinates(SVG_PATH)
    dislodged = Map.get_dislodged_unit_coordinates(SVG_PATH)
    assert len(dislodged) > 0, "SVG should define DISLODGED_UNIT elements"
    if "PAR" in regular and "PAR" in dislodged:
        assert regular["PAR"] != dislodged["PAR"], "Dislodged coords should differ from regular for PAR"

    units = {"FRANCE": ["A DISLODGED_PAR"]}
    img_bytes = Map.render_board_png(SVG_PATH, units)
    assert img_bytes is not None
    assert len(img_bytes) > 0
    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1835, 1360)


def test_full_7_power_initial_state():
    """All 7 powers with 22 starting units renders correctly."""
    game = Game("standard")
    for power in ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]:
        game.add_player(power)

    units: dict = {}
    for power_name, power_state in game.game_state.powers.items():
        for u in power_state.units:
            units.setdefault(power_name, []).append(f"{u.unit_type} {u.province}")

    total = sum(len(v) for v in units.values())
    assert total == 22

    supply_center_control: dict = {}
    for power_name, power_state in game.game_state.powers.items():
        for sc in power_state.controlled_supply_centers:
            supply_center_control[sc] = power_name

    img_bytes = Map.render_board_png(SVG_PATH, units, supply_center_control=supply_center_control)
    assert img_bytes is not None
    assert len(img_bytes) > 500_000

    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1835, 1360)
    assert img.mode in ("RGB", "RGBA")


def test_supply_center_capture_rendering():
    """France capturing MUN renders with updated supply-center control."""
    game = Game("standard")
    game.add_player("FRANCE")
    game.add_player("GERMANY")

    game.game_state.powers["FRANCE"].units = [Unit(unit_type="A", province="MUN", power="FRANCE")]
    game.game_state.powers["GERMANY"].units = []

    units = {"FRANCE": ["A MUN"]}
    supply_center_control = {
        "MUN": "FRANCE", "PAR": "FRANCE", "MAR": "FRANCE", "BRE": "FRANCE",
        "BER": "GERMANY", "KIE": "GERMANY",
    }

    img_bytes = Map.render_board_png(SVG_PATH, units, supply_center_control=supply_center_control)
    assert img_bytes is not None
    assert len(img_bytes) > 0


def test_real_adjudication_multiple_orders():
    """PAR→BUR + MUN→BUR both bounce; render post-adjudication state."""
    game = Game("standard")
    game.add_player("FRANCE")
    game.add_player("GERMANY")

    game.game_state.powers["FRANCE"].units = [Unit(unit_type="A", province="PAR", power="FRANCE")]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type="A", province="MUN", power="GERMANY")]

    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A MUN - BUR"])
    game.process_turn()

    assert any(u.province == "PAR" for u in game.game_state.powers["FRANCE"].units), \
        "France should stay in PAR after bounce"
    assert any(u.province == "MUN" for u in game.game_state.powers["GERMANY"].units), \
        "Germany should stay in MUN after bounce"

    units: dict = {}
    for power_name, power_state in game.game_state.powers.items():
        for u in power_state.units:
            units.setdefault(power_name, []).append(f"{u.unit_type} {u.province}")

    img_bytes = Map.render_board_png(SVG_PATH, units)
    assert img_bytes is not None
    assert len(img_bytes) > 0


def test_order_visualization_with_game_orders():
    """render_board_png_with_orders with move + support produces valid 1835×1360 PNG."""
    units = {
        "FRANCE": ["A PAR", "A MAR", "F BRE"],
    }
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "support", "unit": "A MAR", "supporting": "A PAR - BUR", "status": "success"},
        ]
    }
    phase_info = {"turn": 1, "season": "Spring", "phase": "Movement", "phase_code": "S1901M"}

    img_bytes = Map.render_board_png_with_orders(SVG_PATH, units, orders, phase_info=phase_info)
    assert img_bytes is not None
    assert len(img_bytes) > 0

    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1835, 1360)
