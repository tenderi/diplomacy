"""The footer strip under the map: what the picture shows, and its key.

The old legend was a box drawn *on* the map's bottom-left corner, over Portugal
and the Mid-Atlantic, two provinces a unit can stand in. The footer is appended
below the map instead, so it can never hide anything, and it lists only the
symbols the picture actually uses (each drawing function reports its keys).
"""
from __future__ import annotations

import math
from typing import Any, Callable

from PIL import Image, ImageDraw

from .antialias import DrawTarget, antialiased_overlay
from .arrows import (
    burst,
    catmull_rom,
    draw_arrow,
    draw_bar,
    draw_cross,
    draw_polygon_outline,
    draw_ring,
    octagon,
    stroke_path,
)
from .tokens import font, paste_token, rgb, token_radius
from .visualization_config import get_config

_cfg = get_config()

_SEASONS = {"SPRING": "Spring", "FALL": "Fall", "AUTUMN": "Fall", "WINTER": "Winter"}
_PHASES = {"MOVEMENT": "movement", "RETREAT": "retreats", "ADJUSTMENT": "builds"}

#: Neutral ink for symbols that are drawn in a power's colour on the map.
_INK = (70, 70, 70)


def phase_title(phase_info: dict | None) -> str:
    """``"Spring 1901 movement · S1901M"`` from the renderer's phase dict."""
    if not phase_info:
        return ""
    season = _SEASONS.get(str(phase_info.get("season", "")).upper(), str(phase_info.get("season") or ""))
    phase = _PHASES.get(str(phase_info.get("phase", "")).upper(), str(phase_info.get("phase") or "").lower())
    words = " ".join(str(w) for w in (season, phase_info.get("year") or "", phase) if w)
    code = phase_info.get("phase_code")
    return f"{words} · {code}" if code and words else (words or str(code or ""))


def _casing() -> tuple[int, int, int]:
    return rgb(_cfg.get_color("casing"))


def _arrow(draw: DrawTarget, pts: list[tuple[float, float]], colour: Any, width: float,
           dash: tuple[float, float] | None = None) -> None:
    a = _cfg.get_arrow_specs()
    draw_arrow(draw, pts, colour, width, casing=_casing(), casing_width=a["casing"],
               head_length=12, head_half_width=6, head_notch=3, dash=dash)


def _dash(style: str) -> tuple[float, float]:
    s = _cfg.get_line_style(style)
    return (s["dash"], s["gap"])


def _sym_move(d: DrawTarget, x: float, y: float, w: float) -> None:
    _arrow(d, [(x, y), (x + w, y)], _INK, 4)


def _sym_hold(d: DrawTarget, x: float, y: float, w: float) -> None:
    draw_polygon_outline(d, octagon((x + w / 2, y), 10), _INK, 3)


def _sym_support_hold(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w - 14, y)], _INK, 2.5, dash=(6, 4))
    draw_ring(d, (x + w - 7, y), 6, _INK, 2.5)


def _sym_support_move(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w - 5, y)], _INK, 2.5, dash=(6, 4))
    d.ellipse([x + w - 9, y - 4, x + w - 1, y + 4], fill=_INK)


def _sym_convoy(d: DrawTarget, x: float, y: float, w: float) -> None:
    curve = catmull_rom([(x, y + 6), (x + w / 2, y - 4), (x + w, y + 6)], 8)
    _arrow(d, curve, _INK, 3)
    for k in range(0, 12, 2):
        a0, a1 = k * math.pi / 6, (k + 1) * math.pi / 6
        stroke_path(d, [(x + w / 2 + 7 * math.cos(a0 + (a1 - a0) * t / 3), y - 4 + 7 * math.sin(a0 + (a1 - a0) * t / 3))
                        for t in range(4)], _INK, 2)


def _sym_retreat(d: DrawTarget, x: float, y: float, w: float) -> None:
    _arrow(d, [(x, y), (x + w, y)], _INK, 3, dash=_dash("dashed"))


def _sym_bounce(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w - 6, y)], _INK, 4, casing=_casing(), casing_width=1)
    draw_bar(d, (x + w - 4, y), (1.0, 0.0), rgb(_cfg.get_color("failure")), half_length=8, width=4,
             casing=_casing(), casing_width=1)


def _sym_standoff(d: DrawTarget, x: float, y: float, w: float) -> None:
    d.polygon(burst((x + w / 2, y), 11, 5), fill=rgb(_cfg.get_color("standoff")), outline=_casing())


def _sym_dislodged(d: DrawTarget, x: float, y: float, w: float) -> None:
    draw_ring(d, (x + w / 2, y), 9, rgb(_cfg.get_color("failure")), 3, casing=(255, 255, 255), casing_width=1)


def _sym_cut(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w, y)], _INK, 2.5, dash=(6, 4))
    draw_cross(d, (x + w / 2, y), 6, rgb(_cfg.get_color("failure")), 3, casing=(255, 255, 255), casing_width=1)


def _sym_void(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w, y)], rgb(_cfg.get_color("void")), 2.5, dash=(6, 4))


def _sym_failed(d: DrawTarget, x: float, y: float, w: float) -> None:
    _arrow(d, [(x, y), (x + w - 8, y)], _INK, 3, dash=_dash("dashed"))
    draw_cross(d, (x + w - 4, y), 5, rgb(_cfg.get_color("failure")), 3, casing=(255, 255, 255), casing_width=1)


def _sym_retreat_option(d: DrawTarget, x: float, y: float, w: float) -> None:
    stroke_path(d, [(x, y), (x + w - 8, y)], _INK, 2.5, dash=_dash("dotted"))
    d.ellipse([x + w - 8, y - 5, x + w + 2, y + 5], outline=_INK, width=3)


def _sym_no_retreat(d: DrawTarget, x: float, y: float, w: float) -> None:
    draw_cross(d, (x + w / 2, y), 6, rgb(_cfg.get_color("failure")), 3, casing=(255, 255, 255), casing_width=1)


Symbol = Callable[[DrawTarget, float, float, float], None]

#: key -> (label, symbol). The order here is the order in the footer.
LEGEND: dict[str, tuple[str, Symbol | None]] = {
    "move": ("Move", _sym_move),
    "hold": ("Hold", _sym_hold),
    "support_hold": ("Support to hold", _sym_support_hold),
    "support_move": ("Support to move", _sym_support_move),
    "convoy": ("Convoy", _sym_convoy),
    "retreat": ("Retreat", _sym_retreat),
    "build": ("Build", None),
    "disband": ("Disband", None),
    "bounce": ("Bounced", _sym_bounce),
    "standoff": ("Standoff", _sym_standoff),
    "dislodged": ("Dislodged", _sym_dislodged),
    "cut": ("Support cut", _sym_cut),
    "void": ("Had no effect", _sym_void),
    "failed": ("Failed", _sym_failed),
    "dislodged_unit": ("Dislodged unit", None),
    "retreat_option": ("May retreat to", _sym_retreat_option),
    "no_retreat": ("No retreat: disbands", _sym_no_retreat),
}


def _token_symbol(image: Image.Image, key: str, x: float, y: float, w: float) -> None:
    """Symbols built from a unit token are pasted, not drawn."""
    center = (x + w / 2, y)
    grey = "#9E9E9E"
    if key == "build":
        paste_token(image, center, "A", grey, alpha=_cfg.get_unit_specs()["build_alpha"])
    else:
        paste_token(image, center, "A", grey)


def _token_marks(d: DrawTarget, key: str, x: float, y: float, w: float) -> None:
    center = (x + w / 2, y)
    r = token_radius()
    if key == "build":
        _plus_badge(d, (center[0] + r * 0.7, center[1] - r * 0.7))
    elif key == "disband":
        draw_cross(d, center, r * 0.75, rgb(_cfg.get_color("failure")), 4, casing=(255, 255, 255), casing_width=1.5)
    elif key == "dislodged_unit":
        draw_ring(d, center, r + 1, rgb(_cfg.get_color("failure")), 3)


def _plus_badge(d: DrawTarget, at: tuple[float, float]) -> None:
    m = _cfg.get_marker_specs()
    br = m["build_badge_radius"]
    x, y = at
    d.ellipse([x - br, y - br, x + br, y + br], fill=rgb(_cfg.get_color("build")), outline=(255, 255, 255), width=2)
    d.line([(x - br * 0.55, y), (x + br * 0.55, y)], fill=(255, 255, 255), width=2.5)
    d.line([(x, y - br * 0.55), (x, y + br * 0.55)], fill=(255, 255, 255), width=2.5)


def add_footer(
    image: Image.Image,
    phase_info: dict | None,
    legend_keys: set[str],
    powers: list[str],
    title_prefix: str = "",
) -> Image.Image:
    """``image`` with the footer strip appended below it: the title (phase, with an
    optional prefix such as ``"Orders"``), then the key for ``legend_keys`` in
    ``LEGEND`` order, then a swatch per power in ``powers``, wrapping onto as many
    rows as needed."""
    spec = _cfg.get_footer_specs()
    pad, row_h, gap, sym_w = spec["padding"], spec["row_height"], spec["item_gap"], spec["symbol_width"]
    title_font = font(spec["title_font_size"])
    item_font = font(spec["item_font_size"], bold=False)
    title = " — ".join(t for t in (title_prefix, phase_title(phase_info)) if t)
    measure = ImageDraw.Draw(image)

    # Lay the items out first, to know how many rows the strip needs.
    items: list[tuple[str, str, Any]] = []  # (kind, key/power, label)
    if title:
        items.append(("title", "", title))
    items += [("legend", key, LEGEND[key][0]) for key in LEGEND if key in legend_keys]
    items += [("power", p, p.capitalize()) for p in powers]
    placed: list[tuple[tuple[str, str, Any], float, int]] = []
    x, row = float(pad), 0
    for item in items:
        kind, _, label = item
        f = title_font if kind == "title" else item_font
        width = measure.textlength(label, font=f) + (0 if kind == "title" else sym_w + 8)
        if x > pad and x + width > image.width - pad:
            x, row = float(pad), row + 1
        placed.append((item, x, row))
        x += width + gap * (1.5 if kind == "title" else 1)

    rows = max(1, row + 1) if items else 0
    height = rows * row_h + 2 * pad if rows else 0
    out = Image.new("RGBA", (image.width, image.height + height), rgb(_cfg.get_color("footer_background")) + (255,))
    out.alpha_composite(image, (0, 0))
    if not rows:
        return out
    draw = ImageDraw.Draw(out)
    draw.line([(0, image.height), (image.width, image.height)], fill=_casing(), width=2)
    ink = rgb(_cfg.get_color("footer_text"))

    def mid(r: int) -> float:
        return image.height + pad + r * row_h + row_h / 2

    for (kind, key, label), x, r in placed:
        y = mid(r)
        if kind == "title":
            draw.text((x, y), label, fill=ink, font=title_font, anchor="lm")
            continue
        if kind == "power":
            paste_token(out, (x + sym_w / 2, y), "", _cfg.get_power_color(key))
        elif LEGEND[key][1] is None:
            _token_symbol(out, key, x, y, sym_w)
        draw.text((x + sym_w + 8, y), label, fill=ink, font=item_font, anchor="lm")
    with antialiased_overlay(out) as d:
        for (kind, key, _), x, r in placed:
            if kind != "legend":
                continue
            symbol = LEGEND[key][1]
            if symbol is not None:
                symbol(d, x, mid(r), sym_w)
            else:
                _token_marks(d, key, x, mid(r), sym_w)
    return out
