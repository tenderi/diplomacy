"""What the board image shows, checked on the pixels: centre ownership and a fleet at
sea tint their provinces, and the render cache never serves one board's image for
another's."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from unittest.mock import patch

from rendering import board
from rendering.board import get_svg_province_coordinates, render_board_png
from rendering.cache import _map_cache

pytestmark = pytest.mark.map

SVG = str(Path(__file__).parent.parent / "maps" / "standard.svg")
PHASE = {"turn": 5, "year": 1903, "season": "Fall", "phase": "Movement", "phase_code": "F1903M"}


@pytest.fixture(autouse=True)
def _cold_cache():
    _map_cache.clear()
    yield
    _map_cache.clear()


def _region(png: bytes, province: str, half: int = 18) -> Image.Image:
    x, y = get_svg_province_coordinates(SVG)[province]
    return Image.open(BytesIO(png)).convert("RGB").crop((int(x) - half, int(y) - half, int(x) + half, int(y) + half))


def _differs(a: Image.Image, b: Image.Image) -> bool:
    return ImageChops.difference(a, b).getbbox() is not None


def test_same_units_different_owners_are_different_boards() -> None:
    """Ownership outlives occupancy, so two games can share every unit position and
    phase while their centres differ; the cache key ignored ownership."""
    units = {"FRANCE": ["A PAR"]}
    french_belgium = render_board_png(SVG, units, phase_info=PHASE, supply_center_control={"PAR": "FRANCE", "BEL": "FRANCE"})
    german_belgium = render_board_png(SVG, units, phase_info=PHASE, supply_center_control={"PAR": "FRANCE", "BEL": "GERMANY"})
    assert _differs(_region(french_belgium, "BEL"), _region(german_belgium, "BEL"))
    assert not _differs(_region(french_belgium, "PAR"), _region(german_belgium, "PAR"))


def test_a_fleet_tints_the_sea_it_occupies() -> None:
    empty_sea = render_board_png(SVG, {"ENGLAND": ["A LVP"]}, phase_info=PHASE)
    fleet_in_nth = render_board_png(SVG, {"ENGLAND": ["A LVP", "F NTH"]}, phase_info=PHASE)
    assert _differs(_region(empty_sea, "NTH", half=40), _region(fleet_in_nth, "NTH", half=40))


def test_a_repeat_render_is_served_from_the_cache() -> None:
    args = dict(phase_info=PHASE, supply_center_control={"PAR": "FRANCE"})
    first = render_board_png(SVG, {"FRANCE": ["A PAR"]}, **args)
    with patch.object(board.cairosvg, "svg2png", side_effect=AssertionError("re-rendered")):
        assert render_board_png(SVG, {"FRANCE": ["A PAR"]}, **args) == first


def _image(png: bytes) -> Image.Image:
    return Image.open(BytesIO(png)).convert("RGB")


def test_a_unit_is_a_disc_in_its_powers_colour() -> None:
    from rendering.visualization_config import get_config

    x, y = get_svg_province_coordinates(SVG)["MOS"]
    png = render_board_png(SVG, {"RUSSIA": ["A MOS"]}, phase_info=PHASE)
    # A pixel inside the disc but off the letter: left of centre, half way out.
    r, g, b = _image(png).getpixel((int(x) - 9, int(y) + 6))
    expected = Image.new("RGB", (1, 1), get_config().get_power_color("RUSSIA")).getpixel((0, 0))
    assert max(abs(r - expected[0]), abs(g - expected[1]), abs(b - expected[2])) <= 3


def test_a_dislodged_unit_is_drawn_clear_of_and_above_the_unit_that_replaced_it() -> None:
    """It used to sit 15 px off-centre, mostly under the victor."""
    from rendering.board import get_dislodged_unit_coordinates
    from rendering.visualization_config import get_config

    ax, ay = get_dislodged_unit_coordinates(SVG)["BUR"]
    png = render_board_png(SVG, {"FRANCE": ["A BUR"], "GERMANY": ["A DISLODGED_BUR"]}, phase_info=PHASE)
    r, g, b = _image(png).getpixel((int(ax) - 9, int(ay) + 6))
    germany = Image.new("RGB", (1, 1), get_config().get_power_color("GERMANY")).getpixel((0, 0))
    assert max(abs(r - germany[0]), abs(g - germany[1]), abs(b - germany[2])) <= 3


def test_the_key_is_below_the_map_and_covers_no_province() -> None:
    """The old legend box sat on Portugal and the Mid-Atlantic."""
    x, y = get_svg_province_coordinates(SVG)["POR"]
    bare = board.render_base(SVG, {})
    png = render_board_png(SVG, {"FRANCE": ["A PAR"]}, phase_info=PHASE)
    img = _image(png)
    assert img.width == bare.width and img.height > bare.height
    box = (int(x) - 25, int(y) - 25, int(x) + 25, int(y) + 25)
    assert not _differs(img.crop(box), bare.convert("RGB").crop(box))


def test_retreat_options_are_drawn_from_the_dislodged_unit() -> None:
    units = {"FRANCE": ["A BUR"], "GERMANY": ["A DISLODGED_BUR"]}
    without = render_board_png(SVG, units, phase_info=PHASE)
    with_options = render_board_png(SVG, units, phase_info=PHASE, retreat_options={"BUR": ["PIC"]})
    assert _differs(_region(without, "PIC", 10), _region(with_options, "PIC", 10))
    assert not _differs(_region(without, "GAS", 10), _region(with_options, "GAS", 10))


def test_a_fleet_tints_the_gulf_of_lyon() -> None:
    """The SVG calls that sea's shape ``_gol``; the engine calls it LYO."""
    empty_sea = render_board_png(SVG, {"FRANCE": ["A PAR"]}, phase_info=PHASE)
    fleet = render_board_png(SVG, {"FRANCE": ["A PAR", "F LYO"]}, phase_info=PHASE)
    x, y = get_svg_province_coordinates(SVG)["LYO"]
    box = (int(x) + 20, int(y) + 20, int(x) + 50, int(y) + 50)  # off the token
    assert _differs(_image(empty_sea).crop(box), _image(fleet).crop(box))
