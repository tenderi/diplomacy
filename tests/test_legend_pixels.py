"""The footer legend, rendered alone (issue #411, DI2).

Each symbol must be drawn inside its own row's box, in the symbol column, and not be
empty; the layout numbers come from the footer specs. Nothing here goes through the
map cache.
"""
from __future__ import annotations

import math

import pytest
from PIL import Image, ImageChops, ImageColor, ImageDraw

from rendering import legend
from rendering.antialias import antialiased_overlay
from rendering.legend import LEGEND, UNIT_KEY, add_footer
from rendering.map import Map
from rendering.tokens import font, token_radius
from rendering.visualization_config import get_config

pytestmark = [pytest.mark.unit, pytest.mark.map]

_cfg = get_config()
SPEC = _cfg.get_footer_specs()
PAD, ROW_H, SYM_W = SPEC["padding"], SPEC["row_height"], SPEC["symbol_width"]
BOARD = (400, 50)
FOOTER_BG = ImageColor.getrgb(_cfg.get_color("footer_background"))[:3]
POWERS = ["england", "france", "germany", "italy", "austria", "russia", "turkey"]


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    Map.clear_map_cache()


def blank(width: int = BOARD[0]) -> Image.Image:
    return Image.new("RGBA", (width, BOARD[1]), (255, 255, 255, 255))


def inked(px: tuple[int, ...]) -> bool:
    return max(abs(a - b) for a, b in zip(px[:3], FOOTER_BG)) > 40


def ink_bbox(img: Image.Image, box: tuple[int, int, int, int]) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1), inclusive, of the footer-background-differing pixels in ``box``."""
    x0, y0, x1, y1 = box
    pts = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if inked(img.getpixel((x, y)))]  # type: ignore[arg-type]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def lone_symbol_bbox(key: str) -> tuple[int, int, int, int]:
    """The ink of one legend symbol drawn alone, at the first column of the first
    row of a footer-coloured strip as wide as the board: any spill shows."""
    strip = Image.new("RGBA", (BOARD[0], ROW_H + 2 * PAD), FOOTER_BG + (255,))
    mid = PAD + ROW_H / 2
    symbol = LEGEND[key][1]
    if symbol is None:
        legend._token_symbol(strip, key, PAD, mid, SYM_W)
    with antialiased_overlay(strip) as d:
        if symbol is None:
            legend._token_marks(d, key, PAD, mid, SYM_W)
        else:
            symbol(d, PAD, mid, SYM_W)
    box = ink_bbox(strip, (0, 0, strip.width, strip.height))
    assert box is not None, f"legend symbol {key!r} draws nothing"
    return box[0], box[1] + BOARD[1], box[2], box[3] + BOARD[1]  # in a footer under a BOARD-high map


# (x0 .. x1 of the ink, as an offset from the left of the symbol column, +-2).
# Symbols centred on the column span (SYM_W - ink) / 2 on each side.
EXPECTED_X = {
    "move": (0, SYM_W),
    "support_hold": (0, SYM_W),
    "support_move": (0, SYM_W),
    "retreat": (0, SYM_W),
    "bounce": (0, SYM_W - 2),
    "cut": (0, SYM_W),
    "void": (0, SYM_W - 1),  # the last dash is cut at the end of the line
    "failed": (0, SYM_W),
    "retreat_option": (0, SYM_W + 2),
}


@pytest.mark.parametrize("key", [k for k, (_, sym) in LEGEND.items() if sym is not None or k in ("build", "disband", "dislodged_unit")])
def test_each_symbol_is_inside_its_own_row_box_and_not_empty(key: str) -> None:
    x0, y0, x1, y1 = lone_symbol_bbox(key)
    top, bottom = BOARD[1] + PAD, BOARD[1] + PAD + ROW_H
    assert top - 4 <= y0 and y1 < bottom + 4, (key, y0, y1)  # a ring or badge may touch the row padding
    assert PAD - 3 <= x0 and x1 <= PAD + SYM_W + 5, (key, x0, x1)
    assert y1 - y0 >= 1 and x1 - x0 >= 6, (key, "too small to be a symbol")


@pytest.mark.parametrize("key", [k for k, (_, sym) in LEGEND.items() if sym is not None])
def test_drawn_symbols_sit_on_the_row_centre_line(key: str) -> None:
    x0, y0, x1, y1 = lone_symbol_bbox(key)
    mid = BOARD[1] + PAD + ROW_H / 2
    assert abs((y0 + y1) / 2 - mid) <= 3, (key, y0, y1, mid)


@pytest.mark.parametrize("key", ["hold", "convoy", "standoff", "dislodged", "no_retreat"])
def test_centred_symbols_are_centred_in_the_symbol_column(key: str) -> None:
    x0, _, x1, _ = lone_symbol_bbox(key)
    assert abs((x0 + x1) / 2 - (PAD + SYM_W / 2)) <= 1, (key, x0, x1)


@pytest.mark.parametrize("key", sorted(EXPECTED_X))
def test_line_symbols_span_the_symbol_column(key: str) -> None:
    x0, _, x1, _ = lone_symbol_bbox(key)
    lo, hi = EXPECTED_X[key]
    assert abs(x0 - (PAD + lo)) <= 1 and abs(x1 - (PAD + hi)) <= 1, (key, x0, x1)


@pytest.mark.parametrize("key", ["build", "disband", "dislodged_unit"])
def test_token_symbols_are_a_token_centred_in_the_symbol_column(key: str) -> None:
    x0, y0, x1, y1 = lone_symbol_bbox(key)
    r = token_radius()
    mid = BOARD[1] + PAD + ROW_H / 2
    # The token is centred on the column and row; the build badge adds a corner to its upper right.
    if key == "build":
        assert PAD + SYM_W / 2 - r - 2 <= x0 <= PAD + SYM_W / 2 - r + 2
        assert x1 > PAD + SYM_W / 2 + r
        assert y0 < mid - r + 2
    else:
        assert abs((x0 + x1) / 2 - (PAD + SYM_W / 2)) <= 2, (key, x0, x1)
        assert abs((y0 + y1) / 2 - mid) <= 2, (key, y0, y1)
        assert y1 - y0 >= r * 2 - 6


def test_each_token_symbol_has_its_mark() -> None:
    # build: green badge; disband: red cross over the token; dislodged unit: red ring.
    def colours(key: str) -> set[tuple[int, int, int]]:
        out = add_footer(blank(), None, {key}, [])
        return {out.getpixel((x, y))[:3] for y in range(BOARD[1], out.height) for x in range(PAD, PAD + SYM_W)}  # type: ignore[misc]

    def has(key: str, name: str) -> bool:
        want = ImageColor.getrgb(_cfg.get_color(name))[:3]
        return any(all(abs(a - b) <= 20 for a, b in zip(c, want)) for c in colours(key))

    assert has("build", "build") and not has("build", "failure")
    assert has("disband", "failure") and not has("disband", "build")
    assert has("dislodged_unit", "failure") and not has("dislodged_unit", "build")


def test_token_symbol_is_pasted_at_the_symbol_column_centre() -> None:
    img = Image.new("RGBA", (200, 60), (255, 255, 255, 255))
    legend._token_symbol(img, "disband", 20, 30, 34)
    bbox = img.convert("RGB").point(lambda v: 255 - v).getbbox()  # ink = non-white
    assert bbox is not None
    assert abs((bbox[0] + bbox[2]) / 2 - 37) <= 1 and abs((bbox[1] + bbox[3]) / 2 - 30) <= 1
    build = Image.new("RGBA", (200, 60), (255, 255, 255, 255))
    legend._token_symbol(build, "build", 20, 30, 34)
    # the build token is translucent: lighter than the opaque one at its centre
    solid, faded = img.getpixel((37, 30 + 9))[:3], build.getpixel((37, 30 + 9))[:3]  # off the token's letter
    assert faded != solid and min(faded) > min(solid)


def test_token_marks_draw_nothing_for_other_keys() -> None:
    img = Image.new("RGBA", (200, 60), (255, 255, 255, 255))
    with antialiased_overlay(img) as d:
        legend._token_marks(d, "move", 20, 30, 34)
    assert img.convert("RGB").point(lambda v: 255 - v).getbbox() is None


# -- add_footer ---------------------------------------------------------------


def test_footer_with_nothing_to_say_adds_nothing() -> None:
    img = blank()
    out = add_footer(img, None, set(), [])
    assert out.size == img.size


def test_footer_height_background_and_separator() -> None:
    img = blank(900)
    out = add_footer(img, {"season": "SPRING", "year": 1901, "phase": "MOVEMENT", "phase_code": "S1901M"}, {"move"}, [])
    assert out.size == (900, BOARD[1] + ROW_H + 2 * PAD)
    assert out.crop((0, 0, BOARD[0], BOARD[1])).tobytes() != b""
    assert out.getpixel((897, BOARD[1] + ROW_H + PAD)) [:3] == FOOTER_BG
    assert out.getpixel((897, out.height - 1))[:3] == FOOTER_BG
    # a dark separator on the seam, the board untouched above it
    assert out.getpixel((897, BOARD[1]))[:3] == ImageColor.getrgb(_cfg.get_color("casing"))[:3]
    assert out.getpixel((897, BOARD[1] - 3))[:3] == (255, 255, 255)


def test_footer_rows_all_have_ink_and_padding_has_none() -> None:
    keys = set(LEGEND)
    out = add_footer(blank(300), {"season": "FALL", "year": 1902, "phase": "RETREAT", "phase_code": "F1902R"}, keys, POWERS,
                     title_prefix="Orders and results")
    rows = (out.height - BOARD[1] - 2 * PAD) // ROW_H
    assert rows >= 4  # a narrow board wraps
    assert out.height == BOARD[1] + rows * ROW_H + 2 * PAD
    for r in range(rows):
        top = BOARD[1] + PAD + r * ROW_H
        box = ink_bbox(out, (0, top, out.width, top + ROW_H))
        assert box is not None, f"row {r} is empty"
        assert top <= box[1] and box[3] < top + ROW_H, (r, box)
    assert ink_bbox(out, (0, BOARD[1] + 3, out.width, BOARD[1] + PAD)) is None  # padding above
    assert ink_bbox(out, (0, out.height - PAD, out.width, out.height)) is None  # and below


def test_footer_lists_every_power_and_both_unit_kinds() -> None:
    out = add_footer(blank(1400), None, set(), POWERS)
    row = (BOARD[1] + PAD, BOARD[1] + PAD + ROW_H)
    # one wide row: (Army, Fleet, 7 powers) each draw a token in the symbol column
    assert out.height == BOARD[1] + ROW_H + 2 * PAD
    items = len(UNIT_KEY) + len(POWERS)
    runs, inside = 0, False
    for x in range(out.width):
        col = ink_bbox(out, (x, row[0], x + 1, row[1])) is not None
        if col and not inside:
            runs += 1
        inside = col
    assert runs >= items  # each token and each label is its own run of ink, at least
    # the power colours really are there
    seen = {out.getpixel((x, y))[:3] for y in range(row[0], row[1]) for x in range(out.width)}
    for p in POWERS:
        want = ImageColor.getrgb(_cfg.get_power_color(p))[:3]
        assert any(all(abs(a - b) <= 6 for a, b in zip(c, want)) for c in seen), p


def test_footer_labels_start_after_the_symbol_column() -> None:
    out = add_footer(blank(), None, {"move"}, [])
    row = (BOARD[1] + PAD, BOARD[1] + PAD + ROW_H)
    label = ink_bbox(out, (PAD + SYM_W + 6, row[0], out.width, row[1]))
    assert label is not None
    assert PAD + SYM_W + 8 <= label[0] <= PAD + SYM_W + 14
    assert abs((label[1] + label[3]) / 2 - (BOARD[1] + PAD + ROW_H / 2)) <= 6


def test_standoff_symbol_has_its_inner_radius() -> None:
    strip = Image.new("RGBA", (100, 60), FOOTER_BG + (255,))
    with antialiased_overlay(strip) as d:
        legend._sym_standoff(d, 20, 30, 34)  # a burst of outer 11, inner 5 centred on (37, 30)
    star = ImageColor.getrgb(_cfg.get_color("standoff"))[:3]

    def p(r: float, deg: float) -> tuple[int, ...]:
        return strip.getpixel((round(37 + r * math.cos(math.radians(deg))), round(30 + r * math.sin(math.radians(deg)))))  # type: ignore[return-value]

    for k in range(8):
        valley = -67.5 + 45 * k
        assert all(abs(a - b) <= 40 for a, b in zip(p(3, valley), star)), k
        assert not inked(p(8, valley)), k  # the notch between two points


def test_footer_places_each_item_in_its_own_column() -> None:
    width = 1200
    out = add_footer(blank(width), None, {"move"}, ["england"])
    mid = BOARD[1] + PAD + ROW_H / 2
    f = font(SPEC["item_font_size"], bold=False)
    measure = ImageDraw.Draw(out)
    cols = [PAD]
    for label in ("Move", "Army", "Fleet"):
        cols.append(cols[-1] + measure.textlength(label, font=f) + SYM_W + 8 + SPEC["item_gap"])
    assert out.height == BOARD[1] + ROW_H + 2 * PAD
    void = ImageColor.getrgb(_cfg.get_color("void"))[:3]
    england = ImageColor.getrgb(_cfg.get_power_color("england"))[:3]

    def token_at(x0: float, want: tuple[int, int, int]) -> bool:
        # a point of the token off its letter, at the column's centre line
        px = out.getpixel((round(x0 + SYM_W / 2), round(mid + 9)))[:3]
        return all(abs(a - b) <= 25 for a, b in zip(px, want))

    assert token_at(cols[1], void)  # Army, grey
    assert token_at(cols[2], void)  # Fleet
    assert token_at(cols[3], england)  # the power's swatch comes after both
    assert ink_bbox(out, (round(cols[3] + SYM_W + 8), BOARD[1] + PAD, width, BOARD[1] + PAD + ROW_H)) is not None  # its label


def test_footer_wraps_at_the_right_margin() -> None:
    f = font(SPEC["item_font_size"], bold=False)
    probe = ImageDraw.Draw(blank())
    first = probe.textlength("Move", font=f) + SYM_W + 8
    right_edge = PAD + first + SPEC["item_gap"] + probe.textlength("Hold", font=f) + SYM_W + 8
    one_row = BOARD[1] + ROW_H + 2 * PAD
    fits = add_footer(blank(int(right_edge + PAD) + 1), None, {"move", "hold"}, [])
    assert fits.height == one_row
    wraps = add_footer(blank(int(right_edge + PAD) - 1), None, {"move", "hold"}, [])
    assert wraps.height == one_row + ROW_H


def test_disband_cross_spans_three_quarters_of_the_token_radius() -> None:
    strip = Image.new("RGBA", (100, 60), FOOTER_BG + (255,))
    with antialiased_overlay(strip) as d:
        legend._token_marks(d, "disband", 20, 30, 34)
    red = ImageColor.getrgb(_cfg.get_color("failure"))[:3]
    pts = [(x, y) for y in range(60) for x in range(100)
           if all(abs(a - b) <= 25 for a, b in zip(strip.getpixel((x, y))[:3], red))]  # type: ignore[arg-type]
    arm = token_radius() * 0.75  # the cross reaches arm from the centre along each diagonal
    width = max(x for x, _ in pts) - min(x for x, _ in pts)
    assert abs(width - 2 * arm) <= 2.5, (width, arm)  # a 0.6 radius cross is 3px narrower


def test_footer_tokens_are_centred_on_their_column_and_are_the_right_kind() -> None:
    from rendering.tokens import paste_token

    out = add_footer(blank(1200), None, {"move"}, ["england"])
    mid = BOARD[1] + PAD + ROW_H / 2
    f = font(SPEC["item_font_size"], bold=False)
    measure = ImageDraw.Draw(out)
    cols = [PAD]
    for label in ("Move", "Army", "Fleet"):
        cols.append(cols[-1] + measure.textlength(label, font=f) + SYM_W + 8 + SPEC["item_gap"])
    want = {1: ("A", _cfg.get_color("void")), 2: ("F", _cfg.get_color("void")), 3: ("", _cfg.get_power_color("england"))}
    for i, (kind, fill) in want.items():
        ref = Image.new("RGBA", out.size, FOOTER_BG + (255,))
        paste_token(ref, (cols[i] + SYM_W / 2, mid), kind, fill)
        box = (int(cols[i]) - 2, BOARD[1] + PAD, int(cols[i]) + SYM_W + 2, BOARD[1] + PAD + ROW_H)
        diff = max(ImageChops.difference(out.crop(box).convert("RGB"), ref.crop(box).convert("RGB")).getextrema(), key=lambda e: e[1])[1]
        assert diff <= 12, (i, kind, diff)


def test_footer_title_is_followed_by_one_and_a_half_gaps() -> None:
    title = "Orders"
    out = add_footer(blank(900), None, {"hold"}, [], title_prefix=title)
    mid = BOARD[1] + PAD + ROW_H / 2
    width = ImageDraw.Draw(out).textlength(title, font=font(SPEC["title_font_size"]))
    col = PAD + width + SPEC["item_gap"] * 1.5
    box = ink_bbox(out, (int(col) - 3, BOARD[1] + PAD, int(col) + SYM_W + 3, BOARD[1] + PAD + ROW_H))
    assert box is not None
    assert abs((box[0] + box[2]) / 2 - (col + SYM_W / 2)) <= 1, (box, col)  # the hold ring is centred on its column
    assert box[1] < mid < box[3]


def test_cut_symbol_has_its_cross_mid_line() -> None:
    strip = Image.new("RGBA", (100, 60), FOOTER_BG + (255,))
    with antialiased_overlay(strip) as d:
        legend._sym_cut(d, 20, 30, 34)
    red = ImageColor.getrgb(_cfg.get_color("failure"))[:3]
    xs = [x for y in range(60) for x in range(100)
          if all(abs(a - b) <= 25 for a, b in zip(strip.getpixel((x, y))[:3], red))]  # type: ignore[arg-type]
    assert abs((min(xs) + max(xs)) / 2 - 37) <= 0.5, (min(xs), max(xs))  # centred on x + w / 2
