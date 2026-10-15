"""``antialiased_overlay`` downscales only the drawn window; the pixels must equal
a full-layer LANCZOS resize (the reference algorithm)."""
import sys

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, "src")
from rendering.antialias import SUPERSAMPLE, antialiased_overlay  # noqa: E402

pytestmark = pytest.mark.map


def _reference(base: Image.Image, draw_fn) -> Image.Image:
    out = base.copy()
    f = SUPERSAMPLE
    layer = Image.new("RGBA", (out.width * f, out.height * f), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer), f)
    out.alpha_composite(layer.resize(out.size, Image.LANCZOS))
    return out


def _windowed(base: Image.Image, draw_fn) -> Image.Image:
    out = base.copy()
    with antialiased_overlay(out) as d:
        draw_fn(d, 1)
    return out


def _two_far_apart(d, k):
    d.ellipse([3 * k, 3 * k, 9 * k, 9 * k], fill=(1, 2, 3, 255))
    d.ellipse([85 * k, 65 * k, 97 * k, 77 * k], fill=(250, 250, 0, 128))


SHAPES = {
    "interior": lambda d, k: d.ellipse([40 * k, 30 * k, 61 * k, 47 * k], fill=(200, 10, 10, 180), outline=(0, 0, 0, 255)),
    "top_left_edge": lambda d, k: d.line([(0, 0), (25 * k, 9 * k)], fill=(0, 0, 255, 255), width=3 * k),
    "bottom_right_edge": lambda d, k: d.rectangle([90 * k, 70 * k, 99 * k, 79 * k], fill=(0, 200, 0, 90)),
    "two_far_apart": _two_far_apart,
}


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_window_matches_full_resize(name: str) -> None:
    base = Image.new("RGBA", (100, 80), (255, 255, 255, 255))
    base.paste((30, 60, 90, 255), (20, 20, 70, 60))
    shape = SHAPES[name]
    expected = _reference(base, shape)
    assert expected.tobytes() != base.tobytes()
    assert _windowed(base, shape).tobytes() == expected.tobytes()


def test_nothing_drawn_leaves_base_untouched() -> None:
    base = Image.new("RGBA", (50, 40), (10, 20, 30, 255))
    with antialiased_overlay(base):
        pass
    assert base.tobytes() == Image.new("RGBA", (50, 40), (10, 20, 30, 255)).tobytes()
