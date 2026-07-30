"""Track I2: anti-aliased overlay compositing, shared arrow geometry, and the map
SVG's stale phase label.

**Why these exist.** The I2 rewrite replaced all four arrow variants' hand-rolled
arrowhead trigonometry and changed where every arrow starts and ends -- and the
existing suite went 1445/1445 green through the whole change. The rendering tests
assert only that PNG bytes come back, so they cannot distinguish a correct arrow
from an arrow drawn backwards through the middle of a unit icon. These tests assert
the geometry and the anti-aliasing directly.
"""
from __future__ import annotations

import math

import pytest
from PIL import Image, ImageDraw, ImageFont

from rendering.antialias import ScaledDraw, antialiased_overlay
from rendering.board import _get_cached_font
from rendering.arrows import (
    _arrow_geometry,
    _draw_curve_with_head,
    _head_polygon,
    _normalized,
    _quadratic_points,
    _reaimed,
)
from rendering.visualization_config import get_config

pytestmark = pytest.mark.map


def _tones(img: Image.Image) -> set[int]:
    """Distinct grey levels in the red channel."""
    return {px[0] for px in img.convert("RGB").get_flattened_data()}


class TestAntialiasing:
    """The whole point of rendering.antialias: intermediate tones on diagonals."""

    def test_raw_imagedraw_does_not_antialias(self):
        """Baseline for the claim in antialias.py's docstring -- if this ever fails,
        Pillow gained anti-aliasing and the supersampling layer can be deleted."""
        img = Image.new("RGB", (60, 40), "white")
        ImageDraw.Draw(img).line([2, 36, 57, 6], fill="black", width=3)
        assert _tones(img) == {0, 255}

    def test_overlay_produces_intermediate_tones(self):
        img = Image.new("RGBA", (60, 40), (255, 255, 255, 255))
        with antialiased_overlay(img) as draw:
            draw.line([2, 36, 57, 6], fill=(0, 0, 0), width=3)
        tones = _tones(img)
        assert len(tones) > 2, "supersampled overlay should smooth the diagonal"
        assert any(0 < t < 255 for t in tones)

    def test_factor_one_still_composites_without_resizing(self):
        img = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        with antialiased_overlay(img, factor=1) as draw:
            draw.rectangle([5, 5, 10, 10], fill=(0, 0, 0))
        assert img.getpixel((7, 7))[:3] == (0, 0, 0)

    def test_zero_factor_is_rejected(self):
        img = Image.new("RGBA", (10, 10))
        with pytest.raises(ValueError, match="supersample factor"):
            with antialiased_overlay(img, factor=0):
                pass

    def test_exception_in_body_composites_nothing(self):
        """A half-drawn overlay is a bug to surface, not a partial image to ship."""
        img = Image.new("RGBA", (20, 20), (255, 255, 255, 255))
        with pytest.raises(RuntimeError):
            with antialiased_overlay(img) as draw:
                draw.rectangle([0, 0, 19, 19], fill=(0, 0, 0))
                raise RuntimeError("boom")
        assert img.getpixel((10, 10))[:3] == (255, 255, 255)


class TestScaledDraw:
    """ScaledDraw must scale coordinates and widths, since the primitives it wraps
    pass absolute board coordinates and config-derived widths."""

    def _spy(self):
        calls: list[tuple] = []

        class Spy:
            def line(self, xy, *a, **k):
                calls.append(("line", xy, k))

            def polygon(self, xy, *a, **k):
                calls.append(("polygon", xy, k))

            def ellipse(self, xy, *a, **k):
                calls.append(("ellipse", xy, k))

            def rectangle(self, xy, *a, **k):
                calls.append(("rectangle", xy, k))

        return ScaledDraw(Spy(), 3), calls

    def test_scales_flat_coordinate_lists(self):
        draw, calls = self._spy()
        draw.line([1, 2, 3, 4], fill="black", width=2)
        assert calls[0][1] == [3, 6, 9, 12]

    def test_scales_point_tuple_sequences(self):
        draw, calls = self._spy()
        draw.polygon([(1, 2), (3, 4), (5, 6)], fill="black")
        assert calls[0][1] == [[3, 6], [9, 12], [15, 18]]

    def test_scales_width(self):
        draw, calls = self._spy()
        draw.line([0, 0, 1, 1], fill="black", width=4)
        assert calls[0][2]["width"] == 12

    def test_hairline_width_never_rounds_to_zero(self):
        """A 1px stroke must survive scaling; flooring would drop it entirely."""
        draw, calls = self._spy()
        draw.ellipse([0, 0, 1, 1], outline="black", width=1)
        assert calls[0][2]["width"] >= 1

    def test_leaves_non_numeric_kwargs_alone(self):
        draw, calls = self._spy()
        draw.rectangle([0, 0, 1, 1], fill="red", outline="blue")
        assert calls[0][2] == {"fill": "red", "outline": "blue"}

    def test_textbbox_reports_board_coordinates(self):
        """Callers position other board-space geometry off this, so the scaling has
        to be undone on the way out.

        Passes a font because that is what the overlay path does: ``_get_cached_font``
        always returns a *scalable* font now, so measuring at 3x and dividing back
        round-trips. With a non-scalable bitmap font it could not -- the glyphs would
        not grow -- which is exactly why the font fallback was fixed alongside this.
        """
        font = _get_cached_font(14)
        assert isinstance(font, ImageFont.FreeTypeFont), "overlay text must be scalable"
        base = Image.new("RGB", (400, 200), "white")
        raw = ImageDraw.Draw(base)
        plain = raw.textbbox((10, 10), "S1901M", font=font)
        scaled = ScaledDraw(raw, 3).textbbox((10, 10), "S1901M", font=font)
        for a, b in zip(plain, scaled):
            assert abs(a - b) <= 1

    def test_text_is_drawn_with_an_upscaled_font(self):
        """Text on the 3x layer must be drawn 3x larger or it downscales to mush."""
        seen: list[int] = []

        class Spy:
            def text(self, xy, text, *a, **k):
                seen.append(k["font"].size)

        ScaledDraw(Spy(), 3).text((0, 0), "12", font=_get_cached_font(11))
        assert seen == [33]


class TestArrowGeometry:
    """Both ends must stay clear of the 32px unit icons, and the head must point
    the right way."""

    FROM = (100.0, 100.0)
    TO = (400.0, 100.0)

    def _clearance(self) -> float:
        return get_config().get_arrow_specs().get("unit_clearance", 20)

    def test_start_is_clear_of_the_source_unit(self):
        geo = _arrow_geometry(self.FROM, self.TO)
        assert geo is not None
        assert math.dist(geo.start, self.FROM) == pytest.approx(self._clearance())

    def test_tip_is_clear_of_the_destination_unit(self):
        """The pre-I2 code pulled back a flat 4px, landing the head inside the icon."""
        geo = _arrow_geometry(self.FROM, self.TO)
        assert geo is not None
        assert math.dist(geo.tip, self.TO) == pytest.approx(self._clearance())
        unit_radius = get_config().get_unit_specs()["diameter"] / 2
        assert math.dist(geo.tip, self.TO) >= unit_radius

    def test_shaft_stops_at_the_head_notch_not_the_tip(self):
        geo = _arrow_geometry(self.FROM, self.TO)
        assert geo is not None
        # Shaft ends short of the tip by (head_len - notch), on the same axis.
        assert geo.shaft_end[0] == pytest.approx(geo.tip[0] - (geo.head_len - geo.notch))
        assert geo.shaft_end[1] == pytest.approx(geo.tip[1])

    def test_coincident_provinces_draw_nothing(self):
        """Rather than an arbitrary stub pointing along +x, as atan2(0, 0) would give."""
        assert _arrow_geometry((50.0, 50.0), (50.0, 50.0)) is None

    def test_short_span_shrinks_clearance_instead_of_inverting(self):
        """Some adjacent province centroids are only a few dozen px apart. The arrow
        must stay forward-pointing rather than doubling back on itself."""
        near = (self.FROM[0] + 30, self.FROM[1])
        geo = _arrow_geometry(self.FROM, near)
        if geo is not None:
            assert geo.tip[0] > geo.start[0], "arrow must still point towards the target"
            assert math.dist(geo.start, self.FROM) < self._clearance()

    def test_direction_is_a_unit_vector(self):
        geo = _arrow_geometry(self.FROM, (400.0, 400.0))
        assert geo is not None
        assert math.hypot(*geo.direction) == pytest.approx(1.0)

    def test_head_is_barbed_and_longer_than_wide(self):
        """A head as wide as it is long reads as a blunt stub at map scale."""
        geo = _arrow_geometry(self.FROM, self.TO)
        assert geo is not None
        assert len(geo.head) == 4, "tip, barb, notch, barb"
        xs = [p[0] for p in geo.head]
        ys = [p[1] for p in geo.head]
        assert (max(xs) - min(xs)) > (max(ys) - min(ys))

    def test_head_notch_lies_between_tip_and_barbs(self):
        head = _head_polygon((100.0, 0.0), (1.0, 0.0), length=26, half_width=9, notch=7)
        tip, barb_a, notch_pt, barb_b = head
        assert tip == (100.0, 0.0)
        assert barb_a[0] == pytest.approx(74.0)
        assert notch_pt[0] == pytest.approx(81.0)
        assert barb_a[1] == -barb_b[1], "barbs symmetric about the axis"

    def test_casing_is_larger_than_the_head_it_outlines(self):
        geo = _arrow_geometry(self.FROM, self.TO, casing=2)
        assert geo is not None

        def span(poly):
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            return (max(xs) - min(xs), max(ys) - min(ys))

        cw, ch = span(geo.head_casing)
        hw, hh = span(geo.head)
        assert cw > hw and ch > hh

    def test_reaim_points_the_head_along_a_new_direction(self):
        geo = _arrow_geometry(self.FROM, self.TO)
        assert geo is not None
        down = _reaimed(geo, (0.0, 1.0))
        assert down.direction == (0.0, 1.0)
        # Tip is unchanged; the shaft now approaches from above.
        assert down.tip == geo.tip
        assert down.shaft_end[1] < down.tip[1]
        assert down.shaft_end[0] == pytest.approx(down.tip[0])


class TestCurveGeometry:
    def test_quadratic_endpoints_are_exact(self):
        pts = _quadratic_points((0.0, 0.0), (5.0, 10.0), (10.0, 0.0), steps=8)
        assert len(pts) == 9
        assert pts[0] == (0.0, 0.0)
        assert pts[-1] == (10.0, 0.0)

    def test_quadratic_bows_towards_the_control_point(self):
        pts = _quadratic_points((0.0, 0.0), (5.0, 10.0), (10.0, 0.0), steps=8)
        assert pts[4][1] > 0

    def test_normalized_handles_the_zero_vector(self):
        assert _normalized(0.0, 0.0) == (1.0, 0.0)
        assert _normalized(0.0, 3.0) == (0.0, 1.0)

    def test_curved_arrow_head_follows_the_tangent_not_the_chord(self):
        """A head aimed along the chord sits visibly askew on the end of a bowed curve.

        This asserts the head's actual axis, not just that a head was drawn: an
        earlier version of this test only counted ``polygon`` calls and passed
        happily with the head aimed along the chord.
        """
        polys: list[list] = []
        lines = 0

        class Spy:
            def line(self, *a, **k):
                nonlocal lines
                lines += 1

            def polygon(self, xy, *a, **k):
                polys.append(list(xy))

        frm, to, bow = (100.0, 100.0), (400.0, 100.0), 40.0
        _draw_curve_with_head(Spy(), frm, to, (0, 0, 0), 4, bow=bow)

        assert lines > 0, "the curve itself must be stroked"
        assert len(polys) == 2, "head casing plus head fill"
        # Head polygon is [tip, barb, notch, barb]; its axis runs notch -> tip.
        tip, _barb_a, notch_pt, _barb_b = polys[1]
        head_dir = _normalized(tip[0] - notch_pt[0], tip[1] - notch_pt[1])

        chord = _arrow_geometry(frm, to)
        assert chord is not None
        assert chord.direction == pytest.approx((1.0, 0.0)), "chord is horizontal here"

        # Tangent of a quadratic bezier at its end point is (end - control). The
        # control point sits `bow` px perpendicular to the chord midpoint, so the
        # tangent must tilt away from horizontal.
        ctrl = ((chord.start[0] + chord.tip[0]) / 2, (chord.start[1] + chord.tip[1]) / 2 + bow)
        expected = _normalized(chord.tip[0] - ctrl[0], chord.tip[1] - ctrl[1])
        assert head_dir == pytest.approx(expected, abs=1e-6)
        assert head_dir[1] < -0.2, "head must tilt off the chord, not lie flat along it"

    def test_degenerate_curve_draws_nothing(self):
        drawn: list[str] = []

        class Spy:
            def line(self, *a, **k):
                drawn.append("line")

            def polygon(self, *a, **k):
                drawn.append("polygon")

        _draw_curve_with_head(Spy(), (10.0, 10.0), (10.0, 10.0), (0, 0, 0), 4, bow=30)
        assert drawn == []


class TestStalePhaseLabel:
    """``maps/standard.svg`` shipped a hardcoded ``S1901M`` in 2.5em type in the
    bottom-right corner, in an element (``id="CurrentPhase"``) that nothing in the
    codebase ever populated -- so every board displayed "Spring 1901 Movement" no
    matter what phase it actually was. The correct, dynamic banner is drawn by
    ``board._draw_phase_info`` in the top-right."""

    def _phase_element(self):
        import xml.etree.ElementTree as ET

        tree = ET.parse("maps/standard.svg")
        for el in tree.iter():
            if el.get("id") == "CurrentPhase":
                return el
        return None

    def test_svg_parses(self):
        """The element is emptied in place, and an XML comment explains why -- which
        must not itself break the document (an earlier attempt did, by using `--`
        inside the comment)."""
        assert self._phase_element() is not None

    def test_phase_element_carries_no_hardcoded_phase(self):
        el = self._phase_element()
        assert el is not None
        assert not (el.text or "").strip(), (
            "CurrentPhase must stay empty: any literal phase code here is wrong on "
            "every board except that one phase"
        )
