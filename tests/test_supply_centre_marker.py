"""The ownership tint is laid under the province names and the supply-centre markers
(#417, #418): a name in an owned province is as dark as in a neutral one, and an owned
centre is a small crisp disc in its owner's colour, not a ghost of a unit token."""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image

from rendering.board import render_base, supply_centre_positions
from rendering.visualization_config import get_config

pytestmark = pytest.mark.map

SVG = str(Path(__file__).parent.parent / "maps" / "standard.svg")
ENGLAND = (0x7B, 0x1F, 0xA2)
CASING = (0x11, 0x11, 0x11)


def _darkest(image: Image.Image, x: int, y: int) -> int:
    """The darkest luminance in a box under a name (below any centre marker)."""
    box = image.convert("L").crop((x - 18, y - 9, x + 18, y + 3))
    return min(box.getdata())


def test_name_in_owned_province_is_as_dark_as_in_a_neutral_one() -> None:
    board = render_base(SVG, {}, {"LON": "ENGLAND", "YOR": "ENGLAND"})
    neutral = render_base(SVG, {}, None)
    owned_lon, owned_yor = _darkest(board, 500, 734), _darkest(board, 496, 655)
    assert owned_lon <= _darkest(neutral, 500, 734) + 8
    assert owned_yor <= _darkest(neutral, 496, 655) + 8
    assert owned_lon < 40  # under the old tint-over-text drawing this was ~90


def test_owned_centre_is_a_crisp_disc_in_the_owners_colour() -> None:
    spec = get_config().get_marker_specs()
    radius, outline = spec["supply_centre_radius"], spec["supply_centre_outline"]
    cx, cy = supply_centre_positions(SVG)["MOS"]
    board = render_base(SVG, {}, {"MOS": "ENGLAND"}).convert("RGB")
    assert board.getpixel((round(cx), round(cy))) == ENGLAND
    ring = board.getpixel((round(cx + radius + outline / 2), round(cy)))
    assert max(abs(a - b) for a, b in zip(ring, CASING)) <= 40
    assert radius + outline < get_config().get_unit_specs()["diameter"] / 2 / 2  # well under a token
    extent = max(
        math.dist((cx, cy), (x, y))
        for x in range(round(cx) - 16, round(cx) + 17)
        for y in range(round(cy) - 16, round(cy) + 17)
        if sum(board.getpixel((x, y))) < 120 and math.dist((cx, cy), (x, y)) < 12
    )
    assert extent <= radius + outline + 1


def test_neutral_centre_is_a_plain_dark_disc() -> None:
    cx, cy = supply_centre_positions(SVG)["SPA"]
    board = render_base(SVG, {}, {"EDI": "ENGLAND"}).convert("RGB")
    assert board.getpixel((round(cx), round(cy))) == CASING
    assert board.getpixel((round(cx + 9), round(cy))) != CASING
