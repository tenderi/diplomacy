"""``rendering.arrows`` geometry, asserted as numbers: a picture can only be checked
by the shapes it is made of."""
import math

import pytest

from rendering.arrows import (
    bar_segment,
    burst,
    catmull_rom,
    dash_segments,
    draw_arrow,
    head_polygon,
    octagon,
    offset,
    path_length,
    point_at,
    trim,
)

pytestmark = pytest.mark.unit


class Spy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, name: str):
        return lambda *a, **k: self.calls.append((name, a, k))


def test_trim_cuts_by_arc_length_on_both_ends() -> None:
    line = [(0.0, 0.0), (100.0, 0.0)]
    assert trim(line, 10, 25) == [(10.0, 0.0), (75.0, 0.0)]
    assert trim(line, 60, 50) == []


def test_trim_keeps_the_bends_of_a_polyline() -> None:
    path = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)]
    out = trim(path, 10, 10)
    assert out == [(10.0, 0.0), (50.0, 0.0), (50.0, 40.0)]
    assert path_length(out) == pytest.approx(80)


def test_point_at_reports_position_and_direction() -> None:
    p, d = point_at([(0.0, 0.0), (0.0, 40.0)], 10)
    assert p == pytest.approx((0, 10)) and d == pytest.approx((0, 1))


def test_opposed_moves_end_up_on_opposite_sides() -> None:
    """A→B and B→A, both offset to their own right, separate by twice the offset."""
    a, b = (0.0, 0.0), (100.0, 0.0)
    there, back = offset([a, b], 9), offset([b, a], 9)
    assert there[0][1] == pytest.approx(9) and back[0][1] == pytest.approx(-9)


def test_catmull_rom_passes_through_every_fleet() -> None:
    points = [(0.0, 0.0), (50.0, 40.0), (120.0, 10.0), (160.0, 60.0)]
    curve = catmull_rom(points, 8)
    for p in points:
        assert min(math.dist(p, c) for c in curve) < 1e-9
    assert curve[0] == points[0] and curve[-1] == points[-1]


def test_head_polygon_points_along_the_direction() -> None:
    head = head_polygon((100.0, 0.0), (1.0, 0.0), 18, 9, 5)
    assert head[0] == (100.0, 0.0)
    assert head[1] == pytest.approx((82, 9)) and head[3] == pytest.approx((82, -9))
    assert head[2] == pytest.approx((87, 0))


def test_bar_is_across_the_path() -> None:
    a, b = bar_segment((10.0, 10.0), (1.0, 0.0), 8)
    assert a == pytest.approx((10, 18)) and b == pytest.approx((10, 2))


def test_hold_octagon_and_standoff_burst_shapes() -> None:
    oct_ = octagon((0.0, 0.0), 20)
    assert len(oct_) == 8 and all(math.hypot(*p) == pytest.approx(20) for p in oct_)
    star = burst((0.0, 0.0), 15, 7)
    assert sorted({round(math.hypot(*p), 6) for p in star}) == [7, 15]


def test_dashes_follow_the_path_and_leave_gaps() -> None:
    dashes = dash_segments([(0.0, 0.0), (40.0, 0.0)], 9, 6)
    assert [(d[0][0], d[-1][0]) for d in dashes] == [(0, 9), (15, 24), (30, 39)]


def test_arrow_shaft_stops_at_the_heads_notch() -> None:
    spy = Spy()
    head = draw_arrow(spy, [(0.0, 0.0), (100.0, 0.0)], (1, 2, 3), 5, casing=(0, 0, 0), casing_width=1.5,
                      head_length=18, head_half_width=9, head_notch=5)
    assert head is not None and head[0] == (100.0, 0.0)
    shaft = [a[0] for name, a, k in spy.calls if name == "line" and k["fill"] == (1, 2, 3)]
    assert shaft[-1][-1] == pytest.approx((87, 0))


def test_a_short_arrow_shrinks_its_head_rather_than_poking_backwards() -> None:
    spy = Spy()
    head = draw_arrow(spy, [(0.0, 0.0), (20.0, 0.0)], (1, 2, 3), 5, casing=None, casing_width=0,
                      head_length=18, head_half_width=9, head_notch=5)
    assert head is not None
    assert all(0 <= x <= 20 for x, _ in head)


def test_a_degenerate_arrow_draws_nothing() -> None:
    spy = Spy()
    assert draw_arrow(spy, [(0.0, 0.0), (2.0, 0.0)], (1, 2, 3), 5, casing=None, casing_width=0,
                      head_length=18, head_half_width=9, head_notch=5) is None
    assert spy.calls == []
