"""The ``DISLODGED_UNIT`` positions in ``maps/standard.svg`` (written by
``maps/place_dislodged_anchors.py``): a dislodged unit must be visible beside the
unit that took its place, and must not land on a neighbour's unit either."""
from __future__ import annotations

import math

import pytest

from rendering.board import get_dislodged_unit_coordinates, get_svg_province_coordinates
from rendering.tokens import token_radius

pytestmark = pytest.mark.unit

SVG = "maps/standard.svg"
#: London and Yorkshire are too small for a full token's clearance; they settle for a
#: slight overlap (the script relaxes its gap only where it has to).
CRAMPED = {"LON", "YOR"}


def test_every_province_has_a_dislodged_position() -> None:
    assert set(get_dislodged_unit_coordinates(SVG)) == set(get_svg_province_coordinates(SVG))


@pytest.mark.parametrize("province", sorted(get_dislodged_unit_coordinates(SVG)))
def test_a_dislodged_unit_clears_every_unit_on_the_map(province: str) -> None:
    anchor = get_dislodged_unit_coordinates(SVG)[province]
    nearest = min(math.dist(anchor, unit) for unit in get_svg_province_coordinates(SVG).values())
    needed = 2 * token_radius() - 4 if province in CRAMPED else 2 * token_radius() + 4
    assert nearest >= needed
