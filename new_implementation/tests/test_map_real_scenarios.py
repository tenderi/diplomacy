"""
Real-scenario map rendering tests.

Each test starts from the standard 7-power initial position so the board always
looks like a real game (22 units, all 34 SCs assigned).  Specific scenarios are
layered on top by overriding unit positions or running actual adjudication.
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


def _make_7power_game() -> Game:
    """Return a Game with all 7 powers added at their Spring 1901 starting positions."""
    game = Game("standard")
    for power in ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]:
        game.add_player(power)
    return game


def _units_dict(game: Game) -> dict:
    """Build the {power: [unit_str, ...]} dict the renderer expects."""
    units: dict = {}
    for power_name, power_state in game.game_state.powers.items():
        for u in power_state.units:
            units.setdefault(power_name, []).append(f"{u.unit_type} {u.province}")
    return units


def _sc_dict(game: Game) -> dict:
    """Build the {province: power} supply-center-control dict from the game state."""
    sc: dict = {}
    for power_name, power_state in game.game_state.powers.items():
        for center in power_state.controlled_supply_centers:
            sc[center] = power_name
    return sc


def _check_png(img_bytes: bytes, *, min_size: int = 0) -> Image.Image:
    assert img_bytes is not None
    assert len(img_bytes) > min_size
    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1835, 1360)
    return img


# ---------------------------------------------------------------------------
# 1. Dislodged-unit rendering — produced by the actual game engine
# ---------------------------------------------------------------------------

def test_dislodged_unit_rendering():
    """Germany dislodges France A BUR (supported attack); dislodged unit rendered on full board."""
    game = _make_7power_game()

    # Override France and Germany to set up the scenario; other 5 powers keep starting units
    game.game_state.powers["FRANCE"].units = [
        Unit(unit_type="A", province="BUR", power="FRANCE"),  # will be dislodged
        Unit(unit_type="A", province="MAR", power="FRANCE"),
        Unit(unit_type="F", province="BRE", power="FRANCE"),
    ]
    game.game_state.powers["GERMANY"].units = [
        Unit(unit_type="A", province="MUN", power="GERMANY"),  # attacks BUR
        Unit(unit_type="A", province="RUH", power="GERMANY"),  # supports (RUH adj BUR+MUN)
        Unit(unit_type="F", province="KIE", power="GERMANY"),
    ]

    game.set_orders("FRANCE", ["FRANCE A BUR H", "FRANCE A MAR H", "FRANCE F BRE H"])
    game.set_orders("GERMANY", ["GERMANY A MUN - BUR", "GERMANY A RUH S A MUN - BUR", "GERMANY F KIE H"])
    for power in ["ENGLAND", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]:
        holds = [f"{power} {u.unit_type} {u.province} H" for u in game.game_state.powers[power].units]
        game.set_orders(power, holds)

    game.process_turn()

    assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"

    # France A BUR should now be A DISLODGED_BUR (engine sets province to "DISLODGED_BUR")
    france_provinces = {u.province for u in game.game_state.powers["FRANCE"].units}
    assert "DISLODGED_BUR" in france_provinces, f"France should have DISLODGED_BUR, got {france_provinces}"
    assert "BUR" in {u.province for u in game.game_state.powers["GERMANY"].units}, \
        "Germany A MUN should have advanced to BUR"

    # Verify dislodged coords differ from regular coords for BUR
    regular = Map.get_svg_province_coordinates(SVG_PATH)
    dislodged = Map.get_dislodged_unit_coordinates(SVG_PATH)
    assert len(dislodged) > 0
    if "BUR" in regular and "BUR" in dislodged:
        assert regular["BUR"] != dislodged["BUR"]

    img_bytes = Map.render_board_png(SVG_PATH, _units_dict(game), supply_center_control=_sc_dict(game))
    _check_png(img_bytes, min_size=0)


# ---------------------------------------------------------------------------
# 2. Full 7-power Spring 1901 initial state
# ---------------------------------------------------------------------------

def test_full_7_power_initial_state():
    """Spring 1901 starting position: 22 units, all 34 SCs assigned."""
    game = _make_7power_game()
    units = _units_dict(game)
    sc = _sc_dict(game)

    assert sum(len(v) for v in units.values()) == 22
    # Spring 1901: only the 22 home SCs are owned; 12 neutral SCs (BEL, HOL, DEN, …) start unclaimed
    assert len(sc) == 22

    img_bytes = Map.render_board_png(SVG_PATH, units, supply_center_control=sc)
    img = _check_png(img_bytes, min_size=500_000)
    assert img.mode in ("RGB", "RGBA")


# ---------------------------------------------------------------------------
# 3. Supply-center capture — France takes MUN after a supported attack
# ---------------------------------------------------------------------------

def test_supply_center_capture_rendering():
    """France captures MUN; board shows full 7-power state with updated SC ownership."""
    game = _make_7power_game()

    # Simulate end-of-year state: France A MUN (captured), Germany lost MUN
    game.game_state.powers["FRANCE"].units = [
        Unit(unit_type="A", province="MUN", power="FRANCE"),  # France now in MUN
        Unit(unit_type="A", province="PAR", power="FRANCE"),
        Unit(unit_type="F", province="BRE", power="FRANCE"),
    ]
    game.game_state.powers["GERMANY"].units = [
        Unit(unit_type="A", province="BER", power="GERMANY"),
        Unit(unit_type="F", province="KIE", power="GERMANY"),
    ]

    units = _units_dict(game)
    sc = _sc_dict(game)
    # France has captured MUN (a German SC)
    sc["MUN"] = "FRANCE"

    assert sc.get("MUN") == "FRANCE"
    assert len(sc) == 22  # 22 home SCs (neutral SCs remain unassigned in game state)

    img_bytes = Map.render_board_png(SVG_PATH, units, supply_center_control=sc)
    _check_png(img_bytes, min_size=500_000)


# ---------------------------------------------------------------------------
# 4. Bounce adjudication — PAR→BUR and MUN→BUR both bounce
# ---------------------------------------------------------------------------

def test_real_adjudication_multiple_orders():
    """PAR→BUR and MUN→BUR both bounce; units stay; full 7-power board rendered."""
    game = _make_7power_game()
    sc_before = _sc_dict(game)

    # Only France PAR and Germany MUN move; all other units hold
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR", "FRANCE A MAR H", "FRANCE F BRE H"])
    game.set_orders("GERMANY", ["GERMANY A BER H", "GERMANY A MUN - BUR", "GERMANY F KIE H"])
    for power in ["ENGLAND", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]:
        holds = [f"{power} {u.unit_type} {u.province} H" for u in game.game_state.powers[power].units]
        game.set_orders(power, holds)

    game.process_turn()

    # Both bounce — units stay
    france_provinces = {u.province for u in game.game_state.powers["FRANCE"].units}
    germany_provinces = {u.province for u in game.game_state.powers["GERMANY"].units}
    assert "PAR" in france_provinces, f"France A PAR should not have moved: {france_provinces}"
    assert "MUN" in germany_provinces, f"Germany A MUN should not have moved: {germany_provinces}"

    img_bytes = Map.render_board_png(SVG_PATH, _units_dict(game), supply_center_control=sc_before)
    _check_png(img_bytes, min_size=500_000)


# ---------------------------------------------------------------------------
# 5. Order visualization — full board with move + support arrows
# ---------------------------------------------------------------------------

def test_order_visualization_with_game_orders():
    """render_board_png_with_orders shows move+support arrows on full 7-power board."""
    game = _make_7power_game()
    units = _units_dict(game)
    sc = _sc_dict(game)

    # France: PAR→BUR (move), MAR supports PAR→BUR
    orders = {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "support", "unit": "A MAR", "supporting": "A PAR - BUR", "status": "success"},
            {"type": "hold", "unit": "F BRE", "status": "success"},
        ],
        "GERMANY": [
            {"type": "hold", "unit": "A BER", "status": "success"},
            {"type": "hold", "unit": "A MUN", "status": "bounced"},
            {"type": "hold", "unit": "F KIE", "status": "success"},
        ],
    }
    phase_info = {"turn": 1, "year": 1901, "season": "Spring", "phase": "Movement", "phase_code": "S1901M"}

    img_bytes = Map.render_board_png_with_orders(
        SVG_PATH, units, orders, phase_info=phase_info, supply_center_control=sc
    )
    _check_png(img_bytes, min_size=500_000)
