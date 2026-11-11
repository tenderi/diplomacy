"""Unit tokens: a cannon on a rounded square (army), a sailing ship on a disc (fleet).

Kind is coded twice, by the token's outline and by the pictogram on it, both in
the power's colour scheme: the outline (square or round) still tells the two
apart after Telegram shrinks the picture to two thirds, where a letter ``A`` and
a letter ``F`` on identical discs did not. The pictogram is a flat silhouette
that fills the token (the cannon and ship this project first drew were 11 px
tall inside a white disc, so the power had to be read off a few coloured
pixels). It is white on dark colours and near-black on light ones (Turkey's
yellow), chosen by the fill's luminance.

Sprites are drawn once per (kind, colour, style) at 4x and downsampled, so every
edge is anti-aliased, then pasted.
"""
from __future__ import annotations

from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

from .visualization_config import get_config

_SS = 4


def rgb(colour: str | tuple[int, ...]) -> tuple[int, int, int]:
    """Any PIL colour (name, hex or tuple) as an RGB tuple."""
    if isinstance(colour, tuple):
        return (colour[0], colour[1], colour[2])
    r, g, b = ImageColor.getrgb(colour)[:3]
    return (r, g, b)


def luminance(fill: tuple[int, int, int]) -> float:
    """Perceived brightness of ``fill`` (ITU-R BT.601 weights), 0 to 255."""
    return 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]


def text_colour_on(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    """The ink that contrasts with ``fill``: white, or near-black on a light fill."""
    threshold = get_config().get_unit_specs()["light_fill_luminance"]
    return (255, 255, 255) if luminance(fill) < threshold else (26, 26, 26)


Point = tuple[float, float]

# The pictograms, in token units: (0, 0) is the token's centre and 1.0 its
# radius, y down. Each is a list of (shape, points, ink) drawn in order; ink
# ``True`` is the contrast colour, ``False`` the token's own fill (a cut-out).
# A "polygon" takes its corners, a "disc" its centre and a point on its edge.
_BARREL_BREECH, _BARREL_MUZZLE = (-0.44, 0.07), (0.58, -0.39)
_BARREL_HALF_WIDTHS = (0.19, 0.115)  # at the breech, at the muzzle
_WHEEL = (-0.11, 0.25)


def _barrel() -> list[Point]:
    (ax, ay), (bx, by) = _BARREL_BREECH, _BARREL_MUZZLE
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    nx, ny = -(by - ay) / length, (bx - ax) / length
    w0, w1 = _BARREL_HALF_WIDTHS
    return [(ax + nx * w0, ay + ny * w0), (bx + nx * w1, by + ny * w1),
            (bx - nx * w1, by - ny * w1), (ax - nx * w0, ay - ny * w0)]


def _disc(centre: Point, radius: float) -> list[Point]:
    return [centre, (centre[0] + radius, centre[1])]


Shape = tuple[str, list[Point], bool]

PICTOGRAMS: dict[str, list[Shape]] = {
    # A field gun: a tapered barrel raised to the right, on one open wheel.
    "A": [
        ("polygon", _barrel(), True),
        ("disc", _disc(_BARREL_BREECH, _BARREL_HALF_WIDTHS[0]), True),
        ("disc", _disc(_WHEEL, 0.32), True),
        ("disc", _disc(_WHEEL, 0.18), False),
    ],
    # A sailing ship: a hull, a mainsail and a smaller foresail.
    "F": [
        ("polygon", [(-0.58, 0.22), (0.58, 0.22), (0.37, 0.54), (-0.37, 0.54)], True),
        ("polygon", [(0.03, -0.57), (0.03, 0.13), (0.50, 0.13)], True),
        ("polygon", [(-0.07, -0.38), (-0.07, 0.13), (-0.42, 0.13)], True),
    ],
}


def token_outline(kind: str) -> str:
    """``"square"`` for an army's token, ``"disc"`` for a fleet's and for a bare swatch."""
    return "square" if kind == "A" else "disc"


@lru_cache(maxsize=None)
def font(size: int, bold: bool = True) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """DejaVu Sans at ``size``, or Pillow's bundled scalable font at ``size`` where
    DejaVu is not installed (``load_default()`` without a size is an 11 px bitmap
    font that ignores the request)."""
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except (OSError, TypeError):
            return ImageFont.load_default()


@lru_cache(maxsize=256)
def token_sprite(kind: str, fill: tuple[int, int, int], *, outline: tuple[int, int, int], alpha: int = 255) -> Image.Image:
    """The token image for a unit of ``kind`` (``"A"``/``"F"``; ``""`` for a bare
    colour swatch), ``diameter + 2`` px square."""
    specs = get_config().get_unit_specs()
    d = specs["diameter"]
    size = (d + 2) * _SS
    big = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(big)
    ow = specs["outline_width"] * _SS
    centre, radius = size / 2, d / 2 * _SS
    if token_outline(kind) == "square":
        half = radius * specs["square_half_side"]
        draw.rounded_rectangle(
            [centre - half, centre - half, centre + half, centre + half],
            radius=radius * specs["square_corner_radius"], fill=(*fill, 255), outline=(*outline, 255), width=ow,
        )
    else:
        draw.ellipse([_SS, _SS, size - _SS - 1, size - _SS - 1], fill=(*fill, 255), outline=(*outline, 255), width=ow)
    ink = (*text_colour_on(fill), 255)
    for shape, points, inked in PICTOGRAMS.get(kind, []):
        colour = ink if inked else (*fill, 255)
        scaled = [(centre + x * radius, centre + y * radius) for x, y in points]
        if shape == "polygon":
            draw.polygon(scaled, fill=colour)
        else:
            (cx, cy), (ex, _) = scaled
            r = ex - cx
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour)
    sprite = big.resize((d + 2, d + 2), Image.LANCZOS)
    if alpha < 255:
        sprite.putalpha(sprite.getchannel("A").point(lambda a: a * alpha // 255))
    return sprite


def token_radius() -> float:
    return get_config().get_unit_specs()["diameter"] / 2


def paste_token(
    image: Image.Image, center: tuple[float, float], kind: str, fill: str | tuple[int, ...], *,
    outline: str | tuple[int, ...] | None = None, alpha: int = 255,
) -> None:
    """Composite a token centred on ``center``."""
    casing = rgb(outline if outline is not None else get_config().get_color("casing"))
    sprite = token_sprite(kind if kind in ("A", "F", "") else "A", rgb(fill), outline=casing, alpha=alpha)
    # alpha_composite refuses a negative destination; no unit sits that close to an edge.
    x = max(0, round(center[0] - sprite.width / 2))
    y = max(0, round(center[1] - sprite.height / 2))
    image.alpha_composite(sprite, (x, y))
