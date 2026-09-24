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
