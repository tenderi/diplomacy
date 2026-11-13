"""Exact values for the SVG path helpers behind the province fills (issue #411, DI2).

``_extract_polygon_points_from_path`` turns a province's path into polygon points,
``cubic_bezier_point`` samples its curves, and ``_draw_ocean_pattern`` hatches a sea.
A one-token slip in any of them moves a province fill, and nothing else looks.
"""
from __future__ import annotations

import pytest
from PIL import Image

from rendering.svg_paths import _BEZIER_SAMPLES, _draw_ocean_pattern, _extract_polygon_points_from_path, cubic_bezier_point

pytestmark = [pytest.mark.unit, pytest.mark.map]


def test_cubic_bezier_endpoints_and_midpoint() -> None:
    p0, p1, p2, p3 = (0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.0) == (0.0, 0.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 1.0) == (10.0, 0.0)
    # B(1/2) = (p0 + 3 p1 + 3 p2 + p3) / 8
    assert cubic_bezier_point(p0, p1, p2, p3, 0.5) == (5.0, 7.5)


def test_cubic_bezier_uses_both_axes_and_all_four_points() -> None:
    # Distinct x and y for every control point: each weight shows in the result.
    p0, p1, p2, p3 = (8.0, 16.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.5) == (1.0, 2.0)
    p0, p1, p2, p3 = (0.0, 0.0), (8.0, 16.0), (0.0, 0.0), (0.0, 0.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.5) == (3.0, 6.0)
    p0, p1, p2, p3 = (0.0, 0.0), (0.0, 0.0), (8.0, 16.0), (0.0, 0.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.5) == (3.0, 6.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.25) == (8 * 3 * 0.25**2 * 0.75, 16 * 3 * 0.25**2 * 0.75)
    p0, p1, p2, p3 = (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (8.0, 16.0)
    assert cubic_bezier_point(p0, p1, p2, p3, 0.5) == (1.0, 2.0)


def test_polygon_points_subtract_the_offset() -> None:
    pts = _extract_polygon_points_from_path("M 200 180 L 210 180 L 210 190 z", 195, 170)
    assert pts == [(5.0, 10.0), (15.0, 10.0), (15.0, 20.0), (5.0, 10.0)]


def test_polygon_points_negative_offset_and_decimals() -> None:
    pts = _extract_polygon_points_from_path("M 1.5 2.5 L 3.25 4.75 L -1 -2 Z", -10, -20)
    assert pts == [(11.5, 22.5), (13.25, 24.75), (9.0, 18.0), (11.5, 22.5)]


def test_polygon_close_adds_the_start_when_only_one_coordinate_differs() -> None:
    pts = _extract_polygon_points_from_path("M 0 0 L 4 0 L 4 4 L 0 4 z", 1, 1)
    assert pts == [(-1.0, -1.0), (3.0, -1.0), (3.0, 3.0), (-1.0, 3.0), (-1.0, -1.0)]
    pts = _extract_polygon_points_from_path("M 0 0 L 0 4 L 4 4 L 4 0 Z", 0, 0)
    assert pts[-1] == (0.0, 0.0) and len(pts) == 5


def test_polygon_closing_a_closed_path_adds_nothing() -> None:
    pts = _extract_polygon_points_from_path("M 0 0 L 4 0 L 4 4 L 0 0 z", 0, 0)
    assert pts == [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 0.0)]


def test_polygon_cubic_is_sampled_eight_times_from_the_current_point() -> None:
    pts = _extract_polygon_points_from_path("M 0 0 C 0 10 10 10 10 0 L 10 -10", 3, 5)
    assert len(pts) == 1 + 8 + 1
    assert pts[0] == (-3.0, -5.0)
    want = [cubic_bezier_point((0, 0), (0, 10), (10, 10), (10, 0), t) for t in _BEZIER_SAMPLES]
    assert pts[1:9] == [(x - 3, y - 5) for x, y in want]
    assert pts[8] == (7.0, -5.0)  # t = 1 lands on the curve's end
    assert pts[9] == (7.0, -15.0)  # and the next segment starts from there


def test_polygon_chained_cubics_start_where_the_last_ended() -> None:
    pts = _extract_polygon_points_from_path("M 0 0 C 0 4 4 4 4 0 4 -4 8 -4 8 0", 0, 0)
    assert len(pts) == 1 + 16
    assert pts[8] == (4.0, 0.0)
    assert pts[16] == (8.0, 0.0)
    assert pts[9] == cubic_bezier_point((4, 0), (4, -4), (8, -4), (8, 0), 0.125)


def test_polygon_with_fewer_than_three_points_is_none() -> None:
    assert _extract_polygon_points_from_path("M 0 0 L 5 5", 0, 0) is None
    assert _extract_polygon_points_from_path("", 0, 0) is None


def test_polygon_with_three_points_is_kept() -> None:
    assert _extract_polygon_points_from_path("M 0 0 L 5 5 L 9 1", 0, 0) == [(0.0, 0.0), (5.0, 5.0), (9.0, 1.0)]


def test_polygon_command_missing_coordinates_is_none() -> None:
    assert _extract_polygon_points_from_path("M 0 0 L 5 L 9 1 L 3 3", 0, 0) is None
    assert _extract_polygon_points_from_path("M 7 L 5 5 L 9 1", 0, 0) is None


def test_polygon_ignores_commands_the_map_does_not_use() -> None:
    assert _extract_polygon_points_from_path("M 0 0 h 5 v 5 l 1 1 Q 1 1 2 2 L 4 4 L 9 1", 0, 0) == [
        (0.0, 0.0), (4.0, 4.0), (9.0, 1.0)]


SPACING = 10
RGBA = (0, 0, 255, 200)


def _alpha(img: Image.Image, x: int, y: int) -> int:
    return img.getpixel((x, y))[3]


def _hatch(angle: int, polygon: list[tuple[float, float]] | None = None) -> Image.Image:
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    square = polygon or [(20, 20), (80, 20), (80, 80), (20, 80)]
    _draw_ocean_pattern(img, square, RGBA, spacing=SPACING, angle=angle, line_width=3)
    return img


def test_ocean_hatch_runs_along_the_diagonal_through_the_centre() -> None:
    img = _hatch(45)
    painted = _alpha(img, 50, 50)
    assert painted > 100
    assert _alpha(img, 40, 40) == painted and _alpha(img, 60, 60) == painted
    # Perpendicular to the lines, the next one is spacing away: x - y shifts by spacing * sqrt(2).
    assert _alpha(img, 43, 57) > 100  # on the line through (42.93, 57.07)
    assert _alpha(img, 57, 43) > 100  # and the one on the other side
    # Half way between two lines, and on the anti-diagonal, there is no ink.
    assert _alpha(img, 54, 46) == 0 and _alpha(img, 46, 54) == 0 and _alpha(img, 50, 57) == 0
    assert _alpha(img, 50, 43) == 0
    assert img.getpixel((50, 50)) == (0, 0, 200, 157)  # paste blends the line over transparent black


def test_ocean_hatch_is_clipped_to_the_polygon() -> None:
    img = _hatch(45)
    assert _alpha(img, 10, 10) == 0  # on the centre line, outside the polygon
    assert _alpha(img, 90, 90) == 0
    assert _alpha(img, 19, 19) == 0 and _alpha(img, 81, 81) == 0
    assert _alpha(img, 21, 21) > 100 and _alpha(img, 79, 79) > 100


def test_ocean_hatch_clips_to_a_triangle() -> None:
    img = _hatch(45, [(20, 20), (80, 20), (20, 80)])
    assert _alpha(img, 30, 30) > 100  # inside, on the line x == y
    assert _alpha(img, 70, 70) == 0  # outside the hypotenuse


def test_ocean_hatch_at_zero_degrees_is_horizontal_rows() -> None:
    img = _hatch(0)
    for y in (30, 40, 50, 60, 70):  # the centre row, and whole spacings either side
        assert all(_alpha(img, x, y) > 100 for x in (30, 50, 70))
        assert _alpha(img, 10, y) == 0 and _alpha(img, 90, y) == 0  # clipped sideways
    for y in (35, 45, 55, 65, 75):  # between rows
        assert all(_alpha(img, x, y) == 0 for x in (30, 50, 70))


def test_ocean_hatch_with_spacing_wider_than_the_polygon_is_the_centre_line() -> None:
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    _draw_ocean_pattern(img, [(20, 20), (80, 20), (80, 80), (20, 80)], RGBA, spacing=100, angle=45, line_width=3)
    assert _alpha(img, 50, 50) > 100 and _alpha(img, 30, 30) > 100 and _alpha(img, 70, 70) > 100
    assert _alpha(img, 30, 70) == 0 and _alpha(img, 70, 30) == 0 and _alpha(img, 40, 60) == 0


def test_ocean_hatch_needs_three_points() -> None:
    img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    _draw_ocean_pattern(img, [(0, 0), (40, 40)], RGBA)
    assert img.getbbox() is None


def test_ocean_hatch_reaches_the_polygon_corners() -> None:
    img = _hatch(45)
    # The lines four spacings either side of the centre one cut the (20, 80) and (80, 20) corners.
    assert _alpha(img, 21, 77) > 100 and _alpha(img, 79, 23) > 100
    assert _alpha(img, 25, 77) == 0 and _alpha(img, 75, 23) == 0  # between lines
