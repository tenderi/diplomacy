"""Unit tokens: an army is a cannon on a rounded square, a fleet a ship on a disc.

The pixels are checked, not that "a sprite came back": the outline that tells
the two kinds apart (and still does at Telegram's reduced size), where each
pictogram's ink is and is not, the ink's contrast on every power's colour, and
the Army/Fleet key in the footer.
"""
from __future__ import annotations

from typing import Any

import pytest
from PIL import Image, ImageColor

from rendering import legend
from rendering.tokens import PICTOGRAMS, luminance, text_colour_on, token_outline, token_radius, token_sprite
from rendering.visualization_config import get_config

pytestmark = pytest.mark.unit

_cfg = get_config()
CASING = ImageColor.getrgb(_cfg.get_color("casing"))[:3]
POWERS = {p: ImageColor.getrgb(c)[:3] for p, c in _cfg.get_power_colors().items()}
RED = POWERS["AUSTRIA"]
WHITE, DARK = (255, 255, 255), (26, 26, 26)


def _sprite(kind: str, fill: tuple[int, int, int] = RED) -> Image.Image:
    return token_sprite(kind, fill, outline=CASING)


def _at(sprite: Image.Image, x: float, y: float) -> tuple[int, int, int, int]:
    """The pixel at token coordinates (centre 0,0; radius 1; y down)."""
    c, r = sprite.width / 2, token_radius() * sprite.width / (2 * token_radius() + 2)
    return sprite.getpixel((int(c + x * r), int(c + y * r)))


def _near(pixel: tuple[int, ...], colour: tuple[int, int, int], tolerance: int = 40) -> bool:
    return pixel[3] > 200 and all(abs(pixel[i] - colour[i]) <= tolerance for i in range(3))


class TestOutline:
    def test_an_army_is_square_a_fleet_and_a_swatch_are_discs(self) -> None:
        assert (token_outline("A"), token_outline("F"), token_outline("")) == ("square", "disc", "disc")

    def test_the_square_fills_the_corner_the_disc_leaves_empty(self) -> None:
        # 0.72 along both axes is past a circle of radius 1 (0.72 * sqrt 2 = 1.02)
        # and inside the rounded square; 0.80 is clear of the disc's soft edge.
        assert _at(_sprite("A"), -0.72, -0.72)[3] > 200
        assert _at(_sprite("F"), -0.80, -0.80)[3] < 20
        assert _at(_sprite(""), -0.80, -0.80)[3] < 20

    def test_the_disc_reaches_the_edge_the_square_stops_short_of(self) -> None:
        # The middle of the left edge, where the disc is at its full radius.
        assert _near(_at(_sprite("F"), -0.96, 0), CASING, 60)
        assert _at(_sprite("A"), -0.96, 0)[3] < 40

    @pytest.mark.parametrize("scale", [1.0, 2 / 3, 0.5])
    def test_the_outlines_still_differ_when_the_picture_is_shrunk(self, scale: float) -> None:
        """Telegram shows the picture at about two thirds: a disc reaches as far
        along a diagonal as along an axis, the square a quarter further."""

        def reach(sprite: Image.Image, dx: float, dy: float) -> float:
            c, d = sprite.width / 2, 0.0
            while d < c and sprite.getpixel((int(c + dx * d), int(c + dy * d)))[3] >= 128:
                d += 0.1
            return d

        def diagonal_over_axis(kind: str) -> float:
            size = round(_sprite(kind).width * scale)
            sprite = _sprite(kind).resize((size, size), Image.LANCZOS)
            return reach(sprite, -(0.5**0.5), -(0.5**0.5)) / reach(sprite, -1, 0)

        assert diagonal_over_axis("A") > 1.15
        assert diagonal_over_axis("F") < 1.07

    def test_both_tokens_have_the_same_size_and_a_dark_casing(self) -> None:
        assert _sprite("A").size == _sprite("F").size == (2 * token_radius() + 2,) * 2
        specs = _cfg.get_unit_specs()
        assert _near(_at(_sprite("A"), -specs["square_half_side"] + 0.03, 0), CASING, 60)

    def test_the_square_stays_inside_the_ring_drawn_round_a_unit(self) -> None:
        """Hold octagons and dislodged rings are drawn at the token radius plus
        a gap: the square's rounded corner must not reach them."""
        specs = _cfg.get_unit_specs()
        half, corner = specs["square_half_side"], specs["square_corner_radius"]
        reach = ((half - corner) * 2**0.5 + corner) * token_radius()
        gaps = _cfg.get_marker_specs()
        assert reach < token_radius() + min(gaps["hold_gap"], gaps["dislodged_gap"]) - 1


class TestPictograms:
    def test_a_cannon_barrel_and_open_wheel(self) -> None:
        army = _sprite("A")
        assert _near(_at(army, 0.30, -0.27), WHITE)  # the barrel, towards the muzzle
        assert _near(_at(army, -0.11, 0.50), WHITE)  # the wheel's rim, at its lowest point
        assert _near(_at(army, -0.11, 0.25), RED)  # the wheel is open: the fill shows through
        assert _near(_at(army, -0.50, -0.50), RED)  # nothing above the breech
        assert _near(_at(army, 0.50, 0.45), RED)  # nothing under the muzzle

    def test_a_ship_hull_and_two_sails(self) -> None:
        fleet = _sprite("F")
        assert _near(_at(fleet, 0.0, 0.38), WHITE)  # the hull
        assert _near(_at(fleet, 0.15, -0.10), WHITE)  # the mainsail
        assert _near(_at(fleet, -0.17, -0.02), WHITE)  # the foresail
        assert _near(_at(fleet, -0.02, -0.10), RED)  # the gap between the sails
        assert _near(_at(fleet, 0.45, -0.40), RED)  # open sky beside the mainsail
        assert _near(_at(fleet, 0.0, 0.75), RED)  # water under the hull

    def test_the_two_pictograms_do_not_look_alike(self) -> None:
        def ink(kind: str) -> set[tuple[int, int]]:
            sprite = _sprite(kind)
            return {(x, y) for x in range(sprite.width) for y in range(sprite.height) if _near(sprite.getpixel((x, y)), WHITE)}

        army, fleet = ink("A"), ink("F")
        assert len(army) > 90 and len(fleet) > 90  # each covers a real share of the 30 px token
        assert len(army & fleet) / len(army | fleet) < 0.5

    def test_a_swatch_carries_no_pictogram(self) -> None:
        swatch = _sprite("")
        assert all(_near(_at(swatch, x, y), RED) for x in (-0.4, 0, 0.4) for y in (-0.4, 0, 0.4))

    @pytest.mark.parametrize("kind", ["A", "F"])
    def test_every_shape_lies_inside_its_token(self, kind: str) -> None:
        specs = _cfg.get_unit_specs()
        for shape, points, _inked in PICTOGRAMS[kind]:
            if shape == "disc":
                (cx, cy), (ex, _) = points
                r = ex - cx
                points = [(cx - r, cy - r), (cx + r, cy + r)]
            for x, y in points:
                if kind == "A":
                    assert max(abs(x), abs(y)) < specs["square_half_side"] - 0.12, (shape, x, y)
                else:
                    assert (x * x + y * y) ** 0.5 < 0.82, (shape, x, y)


class TestInk:
    @pytest.mark.parametrize(
        ("power", "ink"),
        [("AUSTRIA", WHITE), ("ENGLAND", WHITE), ("FRANCE", WHITE), ("GERMANY", WHITE),
         ("ITALY", WHITE), ("RUSSIA", WHITE), ("TURKEY", DARK)],
    )
    def test_the_ink_on_each_power(self, power: str, ink: tuple[int, int, int]) -> None:
        assert text_colour_on(POWERS[power]) == ink

    @pytest.mark.parametrize("power", sorted(POWERS))
    def test_the_ink_contrasts_with_the_fill(self, power: str) -> None:
        fill = POWERS[power]
        assert abs(luminance(text_colour_on(fill)) - luminance(fill)) > 100

    def test_luminance_weighs_green_most(self) -> None:
        assert luminance((255, 0, 0)) == pytest.approx(76.245)
        assert luminance((0, 255, 0)) == pytest.approx(149.685)
        assert luminance((0, 0, 255)) == pytest.approx(29.07)

    def test_turkeys_pictogram_is_drawn_dark(self) -> None:
        assert _near(_at(_sprite("F", POWERS["TURKEY"]), 0.0, 0.38), DARK)
        assert _near(_at(_sprite("A", POWERS["TURKEY"]), 0.30, -0.27), DARK)


class TestFooterKey:
    def _pasted(self, monkeypatch: pytest.MonkeyPatch, powers: list[str]) -> list[tuple[str, tuple[int, ...], float]]:
        calls: list[tuple[str, tuple[int, ...], float]] = []

        def paste(image: Any, center: tuple[float, float], kind: str, fill: Any, **_: Any) -> None:
            calls.append((kind, ImageColor.getrgb(fill)[:3] if isinstance(fill, str) else tuple(fill)[:3], center[0]))

        monkeypatch.setattr(legend, "paste_token", paste)
        legend.add_footer(Image.new("RGBA", (1800, 100), (255, 255, 255, 255)), None, set(), powers)
        return calls

    def test_the_footer_shows_an_army_and_a_fleet_before_the_powers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self._pasted(monkeypatch, ["AUSTRIA", "TURKEY"])
        grey = ImageColor.getrgb(_cfg.get_color("void"))[:3]
        assert [(kind, fill) for kind, fill, _ in calls] == [
            ("A", grey), ("F", grey), ("", POWERS["AUSTRIA"]), ("", POWERS["TURKEY"]),
        ]
        xs = [x for _, _, x in calls]
        assert xs == sorted(xs) and len(set(xs)) == 4

    def test_a_picture_with_no_powers_has_no_unit_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._pasted(monkeypatch, []) == []

    def test_the_key_is_labelled(self) -> None:
        assert legend.UNIT_KEY == (("A", "Army"), ("F", "Fleet"))
