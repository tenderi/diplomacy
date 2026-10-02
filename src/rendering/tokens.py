"""Unit tokens: a disc in the power's colour with a bold ``A`` or ``F``.

A letter stays legible after Telegram shrinks the picture; the cannon and ship
silhouettes this replaced were 32 px wide and 11 px tall inside a white disc, so
the power had to be read off a few coloured pixels. The letter is white on dark
colours and near-black on light ones (Turkey's yellow).

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


def text_colour_on(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    threshold = get_config().get_unit_specs()["light_text_threshold"]
    return (255, 255, 255) if sum(fill) < threshold else (26, 26, 26)


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
    draw.ellipse([_SS, _SS, size - _SS - 1, size - _SS - 1], fill=(*fill, 255), outline=(*outline, 255), width=ow)
    if kind:
        draw.text((size / 2, size / 2 + _SS * 0.5), kind, fill=(*text_colour_on(fill), 255),
                  font=font(specs["font_size"] * _SS), anchor="mm")
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
