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


# ---- primitives: exact values and recorded strokes (issue #411, DI1) -------------

from PIL import ImageColor  # noqa: E402

from rendering.arrows import draw_cross, draw_ring  # noqa: E402
from rendering.tokens import text_colour_on  # noqa: E402
from rendering.visualization_config import get_config  # noqa: E402


def _flat(points) -> list[float]:
    return [c for p in points for c in p]


def _rgb(colour) -> tuple[int, ...]:
    return tuple(ImageColor.getrgb(colour) if isinstance(colour, str) else colour)[:3]


def test_bar_ends_are_symmetric_about_its_centre_for_any_direction() -> None:
    at = (30.0, 40.0)
    for direction in [(1.0, 0.0), (0.0, 1.0), (0.6, 0.8), (-0.8, 0.6)]:
        a, b = bar_segment(at, direction, 10)
        assert ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) == pytest.approx(at)
        assert math.dist(a, b) == pytest.approx(20)
        assert (a[0] - b[0]) * direction[0] + (a[1] - b[1]) * direction[1] == pytest.approx(0)
    a, b = bar_segment(at, (0.6, 0.8), 10)
    assert a == pytest.approx((22, 46)) and b == pytest.approx((38, 34))


def test_path_length_sums_the_legs() -> None:
    assert path_length([(0.0, 0.0), (3.0, 4.0), (3.0, 10.0)]) == pytest.approx(11)
    assert path_length([(5.0, 5.0)]) == 0


def test_trim_exact_points_on_a_bent_path() -> None:
    path = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert _flat(trim(path, 4, 3)) == pytest.approx(_flat([(4, 0), (10, 0), (10, 7)]))
    assert _flat(trim(path, 12, 2)) == pytest.approx(_flat([(10, 2), (10, 8)]))
    assert trim(path, 10, 10) == []


def test_catmull_rom_exact_samples() -> None:
    curve = catmull_rom([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], 2)
    assert _flat(curve) == pytest.approx(_flat([(0, 0), (5, -0.625), (10, 0), (10.625, 5), (10, 10)]))


def test_draw_cross_is_two_strokes_crossing_at_the_centre() -> None:
    spy = Spy()
    draw_cross(spy, (50.0, 40.0), 10, (1, 2, 3), 4)
    lines = [a[0] for name, a, k in spy.calls if name == "line"]
    assert lines == [[(40, 30), (60, 50)], [(40, 50), (60, 30)]]


def test_draw_cross_casing_is_the_same_x_a_little_larger() -> None:
    spy = Spy()
    draw_cross(spy, (50.0, 40.0), 10, (1, 2, 3), 4, casing=(0, 0, 0), casing_width=2)
    lines = [(a[0], k["fill"], k["width"]) for name, a, k in spy.calls if name == "line"]
    assert [fill for _, fill, _ in lines] == [(0, 0, 0), (0, 0, 0), (1, 2, 3), (1, 2, 3)]
    c = 10 + 2 * 0.7
    assert _flat(lines[0][0]) == pytest.approx(_flat([(50 - c, 40 - c), (50 + c, 40 + c)]))
    assert _flat(lines[1][0]) == pytest.approx(_flat([(50 - c, 40 + c), (50 + c, 40 - c)]))
    assert lines[0][2] == 8 and lines[2][2] == 4


def test_draw_ring_is_centred_with_the_stated_radius() -> None:
    spy = Spy()
    draw_ring(spy, (50.0, 40.0), 10, "#112233", 4)
    ((name, args, kw),) = spy.calls
    assert name == "ellipse" and args[0] == [38, 28, 62, 52]  # radius to the stroke's middle
    assert _rgb(kw["outline"]) == (0x11, 0x22, 0x33) and kw["width"] == 4


def test_draw_ring_casing_is_a_wider_ring_under_the_colour() -> None:
    spy = Spy()
    draw_ring(spy, (50.0, 40.0), 10, (1, 2, 3), 4, casing=(0, 0, 0), casing_width=1.5)
    (_, (box_c,), kw_c), (_, (box,), kw) = spy.calls
    assert box_c == [50 - 13.5, 40 - 13.5, 50 + 13.5, 40 + 13.5] and kw_c["width"] == 7
    assert box == [38, 28, 62, 52] and kw["width"] == 4


def _arrow_calls(path):
    spy = Spy()
    head = draw_arrow(spy, path, (1, 2, 3), 5, casing=(0, 0, 0), casing_width=1.5,
                      head_length=18, head_half_width=9, head_notch=5)
    return spy, head


def test_a_short_arrow_head_is_at_most_sixty_percent_of_the_shaft() -> None:
    _, head = _arrow_calls([(0.0, 0.0), (20.0, 0.0)])
    assert head is not None
    assert 20 - head[1][0] == pytest.approx(12)  # 0.6 * 20, not the 18 asked for


def test_a_long_arrow_keeps_its_full_head() -> None:
    _, head = _arrow_calls([(0.0, 0.0), (100.0, 0.0)])
    assert 100 - head[1][0] == pytest.approx(18)
    assert abs(head[1][1]) == pytest.approx(9)


def test_arrow_casing_is_wider_than_the_shaft() -> None:
    spy, _ = _arrow_calls([(0.0, 0.0), (100.0, 0.0)])
    widths = {k["fill"]: k["width"] for name, a, k in spy.calls if name == "line"}
    assert widths[(0, 0, 0)] == 8 and widths[(1, 2, 3)] == 5


def test_arrow_head_casing_surrounds_the_head_by_the_casing_width() -> None:
    spy, head = _arrow_calls([(0.0, 0.0), (100.0, 0.0)])
    polys = [(a[0], k["fill"]) for name, a, k in spy.calls if name == "polygon"]
    (cased, cased_fill), (drawn, drawn_fill) = polys
    assert cased_fill == (0, 0, 0) and drawn_fill == (1, 2, 3) and drawn == head
    # tip pushed out by the casing, barbs one casing width back and out, notch kept
    assert _flat(cased) == pytest.approx(_flat([(101.5, 0), (100 - 18 - 1.5, 10.5), (101.5 - 18 - 3 + 5, 0), (100 - 18 - 1.5, -10.5)]))


@pytest.mark.parametrize(
    ("power", "ink"),
    [("AUSTRIA", (255, 255, 255)), ("ENGLAND", (255, 255, 255)), ("FRANCE", (255, 255, 255)),
     ("GERMANY", (255, 255, 255)), ("ITALY", (255, 255, 255)), ("RUSSIA", (255, 255, 255)),
     ("TURKEY", (26, 26, 26))],
)
def test_text_colour_on_each_power_colour(power: str, ink: tuple[int, int, int]) -> None:
    fill = _rgb(get_config().get_power_color(power))
    assert text_colour_on(fill) == ink  # type: ignore[arg-type]
