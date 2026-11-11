"""The ``UNIT`` positions in ``maps/standard.svg`` (written by
``maps/place_unit_anchors.py``): a token must sit inside its own province, clear
of the border, of the supply-centre dot, of the province's name and of every
other token. The geometry is measured from the SVG's own province outlines."""
from __future__ import annotations

import importlib.util
import math
import re
from pathlib import Path
from types import ModuleType

import pytest

from rendering.board import get_svg_province_coordinates
from rendering.tokens import token_radius

pytestmark = pytest.mark.unit

SVG = Path("maps/standard.svg")
#: Too narrow for a whole token: these settle for less room, never for none.
CRAMPED = {"LVP": 12, "NAP": 10, "ROM": 12}


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("place_unit_anchors", "maps/place_unit_anchors.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


placer = _script()
POLYGONS = {name.upper().replace("-", "/"): polys for name, polys in placer.province_polygons().items()}
UNITS = {name: xy for name, xy in get_svg_province_coordinates(str(SVG)).items() if name.lower() not in placer.SKIPPED}
ALIASES = {alias.upper(): name.upper() for alias, name in placer.ALIASES.items()}
PLACED = sorted(set(UNITS) - set(ALIASES))


def _inside(point: tuple[float, float], polygons: list[list[tuple[float, float]]]) -> bool:
    x, y = point
    crossings = 0
    for polygon in polygons:
        for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                crossings += 1
    return crossings % 2 == 1


def _to_outline(point: tuple[float, float], polygons: list[list[tuple[float, float]]]) -> float:
    best = math.inf
    for polygon in polygons:
        for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
            dx, dy = x2 - x1, y2 - y1
            t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((point[0] - x1) * dx + (point[1] - y1) * dy) / (dx * dx + dy * dy)))
            best = min(best, math.dist(point, (x1 + t * dx, y1 + t * dy)))
    return best


def test_the_script_and_the_renderer_agree_on_the_token_size() -> None:
    assert placer.RADIUS == token_radius()


def test_every_province_and_coast_has_an_outline() -> None:
    assert sorted(set(PLACED) - set(POLYGONS)) == []
    assert len(PLACED) == 81  # 75 provinces and 6 coasts


@pytest.mark.parametrize("province", PLACED)
def test_a_unit_is_inside_its_province_and_clear_of_the_border(province: str) -> None:
    assert _inside(UNITS[province], POLYGONS[province])
    # The script measures between pixel centres and this the exact outline, so
    # its 16 px can be 14.6 here: the token's edge is on the border line at worst.
    assert _to_outline(UNITS[province], POLYGONS[province]) >= CRAMPED.get(province, token_radius() - 1)


def test_the_cramped_provinces_are_the_only_ones_short_of_room() -> None:
    short = {p for p in PLACED if _to_outline(UNITS[p], POLYGONS[p]) < token_radius() - 1}
    assert short == set(CRAMPED)


@pytest.mark.parametrize("province", PLACED)
def test_a_unit_does_not_touch_any_other_unit(province: str) -> None:
    nearest = min(math.dist(UNITS[province], UNITS[other]) for other in PLACED if other != province)
    assert nearest >= placer.UNIT_GAP


@pytest.mark.parametrize("province", sorted(placer.supply_centres()))
def test_a_unit_does_not_cover_its_supply_centre(province: str) -> None:
    centre = placer.supply_centres()[province]
    assert math.dist(UNITS[province.upper()], centre) >= placer.SC_CLEAR


def test_a_sea_with_two_names_has_one_position() -> None:
    assert ALIASES == {"GOL": "LYO", "MID": "MAO", "NAT": "NAO", "NRG": "NWG", "TYN": "TYS"}
    assert [UNITS[alias] for alias in ALIASES] == [UNITS[name] for name in ALIASES.values()]


def test_no_province_name_is_anchored_under_a_token() -> None:
    """A name is centred on its anchor and stands on it: a token whose centre is
    within a token radius of the name's middle would cover it."""
    covered = []
    for x, y, name in re.findall(r'<text[^>]*? x="([\d.]+)" y="([\d.]+)">([A-Z]{3})</text>', SVG.read_text()):
        if "transform" in name or (x, y) == ("0", "0"):
            continue
        middle = (float(x), float(y) - 6)
        if min(math.dist(middle, unit) for unit in UNITS.values()) < token_radius():
            covered.append(name)
    assert covered == []
