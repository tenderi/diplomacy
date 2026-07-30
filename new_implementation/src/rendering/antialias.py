"""Anti-aliased overlay drawing for the order visualizations.

**Why this module exists (Track I2).** Every order arrow, curve, dash and status
marker is drawn with ``PIL.ImageDraw``, whose ``line``/``polygon``/``ellipse``
primitives do **no anti-aliasing at all** -- verified empirically: a 3px diagonal
black line on white produces exactly two distinct tones, ``{0, 255}``. Only PIL's
*font* rasterizer anti-aliases, which is why the province labels always looked
fine and the arrows never did. Zooming the map (I1) made the staircase edges
plainly visible rather than merely present.

**The approach: supersample, then downscale.** Draw the whole overlay onto a
transparent layer ``SUPERSAMPLE`` times larger, then resize it down with LANCZOS
and alpha-composite it over the board. Downscaling is what produces the
intermediate tones, so every primitive becomes smooth at once.

**Why a proxy rather than editing the primitives.** Scaling by a constant is an
affine map, so any shape built from *absolute* coordinates scales correctly if you
simply multiply every coordinate by the factor -- including shapes whose size comes
from ``visualization_config`` (e.g. ``[x - size, y - size, x + size, y + size]``),
because that arithmetic has already happened by the time the coordinates reach
``ImageDraw``. ``ScaledDraw`` therefore multiplies coordinates and the ``width=``
keyword and forwards the call, leaving all ~20 drawing primitives in ``arrows.py``
and ``overlays.py`` untouched. The alternative -- threading a scale factor through
every primitive and every config lookup -- would have rewritten all of them.

Not everything routes through here: ``legend.py`` and the phase banner draw
directly onto the base image. That is deliberate. They are text and axis-aligned
boxes, so anti-aliasing buys them nothing (text is already anti-aliased by the font
rasterizer, and axis-aligned rectangle edges have no staircase to remove), and
keeping them off the supersampled layer keeps its cost to the part that needs it.
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from PIL import Image, ImageDraw, ImageFont

#: Linear supersampling factor. 3x costs ~9x the overlay pixels but is visibly
#: cleaner than 2x on the thin diagonal support lines, which are the worst case;
#: 4x is not distinguishable from 3x once downscaled. The overlay layer is
#: transparent and short-lived, so the memory is a transient 3x-area RGBA buffer.
SUPERSAMPLE = 3


def _scale_font(font: Any, factor: int) -> Any:
    """Return ``font`` re-instantiated ``factor`` times larger, or ``font`` unchanged.

    Text on the supersampled layer must be drawn at ``factor`` times the intended
    size or it shrinks to illegibility on downscale. Only truetype fonts can be
    resized; PIL's built-in bitmap font cannot, so it is returned as-is (it renders
    small, which is the pre-existing behavior, not a new defect).
    """
    if isinstance(font, ImageFont.FreeTypeFont):
        try:
            return font.font_variant(size=int(font.size * factor))
        except (OSError, ValueError):
            return font
    return font


class ScaledDraw:
    """An ``ImageDraw``-compatible facade that scales coordinates, widths and fonts.

    Only the methods the overlay code actually calls are implemented (``line``,
    ``polygon``, ``ellipse``, ``rectangle``, ``text``, ``textbbox``) -- deliberately,
    so that a primitive reaching for an unscaled method raises ``AttributeError``
    instead of silently drawing at 1/``factor`` size in the corner of the layer.
    """

    def __init__(self, draw: ImageDraw.ImageDraw, factor: int) -> None:
        self._draw = draw
        self._factor = factor

    # -- coordinate helpers -------------------------------------------------

    def _xy(self, xy: Any) -> Any:
        """Scale a coordinate argument in any of the shapes ImageDraw accepts.

        ImageDraw takes both flat sequences (``[x1, y1, x2, y2]``) and sequences of
        point tuples (``[(x1, y1), (x2, y2)]``), and the overlay code uses both --
        sometimes mixed within one call, as ``_draw_arrow`` does when it passes
        ``[from_x, from_y, base_center_x, base_center_y]`` to ``line`` but
        ``[(x1, y1), (x2, y2)]`` to another. Both are handled here rather than at
        the ~30 call sites.
        """
        f = self._factor
        if isinstance(xy, (int, float)):
            return xy * f
        if isinstance(xy, Sequence) and not isinstance(xy, (str, bytes)):
            return [self._xy(item) for item in xy]
        return xy

    def _width(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        width = kwargs.get("width")
        if isinstance(width, (int, float)):
            # Round up: a 1px hairline must stay visible after downscaling, and
            # int() would floor a scaled 0.5 to 0 and drop the stroke entirely.
            kwargs = {**kwargs, "width": max(1, round(width * self._factor))}
        return kwargs

    # -- forwarded primitives ----------------------------------------------

    def line(self, xy: Any, *args: Any, **kwargs: Any) -> None:
        self._draw.line(self._xy(xy), *args, **self._width(kwargs))

    def polygon(self, xy: Any, *args: Any, **kwargs: Any) -> None:
        self._draw.polygon(self._xy(xy), *args, **self._width(kwargs))

    def ellipse(self, xy: Any, *args: Any, **kwargs: Any) -> None:
        self._draw.ellipse(self._xy(xy), *args, **self._width(kwargs))

    def rectangle(self, xy: Any, *args: Any, **kwargs: Any) -> None:
        self._draw.rectangle(self._xy(xy), *args, **self._width(kwargs))

    def text(self, xy: Any, text: str, *args: Any, **kwargs: Any) -> None:
        if "font" in kwargs:
            kwargs = {**kwargs, "font": _scale_font(kwargs["font"], self._factor)}
        self._draw.text(self._xy(xy), text, *args, **kwargs)

    def textbbox(self, xy: Any, text: str, *args: Any, **kwargs: Any) -> tuple:
        """Measure at the supersampled size, then report in board coordinates.

        Callers use the result to position other board-space geometry, so the
        scaling has to be undone on the way out -- otherwise a caller that centres
        text on its own measurement would offset it by ``factor``.
        """
        if "font" in kwargs:
            kwargs = {**kwargs, "font": _scale_font(kwargs["font"], self._factor)}
        box = self._draw.textbbox(self._xy(xy), text, *args, **kwargs)
        return tuple(v / self._factor for v in box)


#: What the overlay primitives accept: a raw ``ImageDraw`` when drawing straight onto
#: the board, or a :class:`ScaledDraw` when drawing onto the supersampled layer. The
#: primitives use only the subset above, so the two are interchangeable to them.
DrawTarget = ImageDraw.ImageDraw | ScaledDraw


@contextmanager
def antialiased_overlay(base: Image.Image, factor: int = SUPERSAMPLE) -> Iterator[ScaledDraw]:
    """Yield a :class:`ScaledDraw` whose output lands anti-aliased on ``base``.

    ``base`` is mutated in place on clean exit, matching how the callers already
    treat their ``bg`` image. On an exception nothing is composited -- an overlay
    that failed halfway through is a bug to surface, not a partial image to ship
    (see the module-wide rule against swallowing rendering errors).
    """
    if factor < 1:
        raise ValueError(f"supersample factor must be >= 1, got {factor}")
    layer = Image.new("RGBA", (base.width * factor, base.height * factor), (0, 0, 0, 0))
    yield ScaledDraw(ImageDraw.Draw(layer), factor)
    if factor > 1:
        layer = layer.resize(base.size, Image.LANCZOS)
    base.alpha_composite(layer)
