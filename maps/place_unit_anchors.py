"""Recompute the ``jdipNS:UNIT`` positions in ``standard.svg``.

The positions the SVG shipped with were placed by hand for jDip's 40 px symbols,
and many sit on a border: London's was outside London altogether, and Holland,
Marseilles, Portugal and Tyrolia had their token half in the next province. This
script moves each unit that is badly placed, and leaves the others alone.

A position is good when the token is

- inside its own province, ``BORDER`` clear of the outline (the province's own
  path in the SVG's ``MouseLayer``; a coast's own area for ``stp-nc`` and the like),
- off the ink drawn inside the province: its name and its supply-centre dot,
- ``UNIT_GAP`` from every other unit position, so two tokens never touch.

A unit already there stays. Any other moves to the nearest point that is, so a
coast's fleet stays on its coast and a big province's unit stays where it was.
Where a province is too small for all three (Clyde, Naples), the demands are
relaxed in this order: cover the name, come closer to the border, and only then
touch the supply-centre dot.

A name left under a token is then moved (``move_labels``): set in the small
label size and shifted to the nearest spot clear of every token, dot, border and
other name, preferring its own province, then open sea, over a neighbour's land.

Run from the repository root, then recompute the dislodged positions, which are
placed beside these; ``tests/test_unit_anchors.py`` checks the result.

    PYTHONPATH=src python maps/place_unit_anchors.py
    PYTHONPATH=src python maps/place_dislodged_anchors.py
"""
from __future__ import annotations

import io
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cairosvg  # type: ignore
import numpy as np
from PIL import Image, ImageDraw

SVG = Path(__file__).with_name("standard.svg")
WIDTH, HEIGHT = 1835, 1360
SVG_NS = "{http://www.w3.org/2000/svg}"
#: The token's radius (``units.radius`` in the visualization config).
RADIUS = 15
#: Wanted distance from the token's centre to its province's outline, then what
#: a cramped province settles for.
BORDER = 20
BORDER_RELAXED = (18, 16, 14, 12, 10)
#: Distance from the token's centre to the nearest ink (name or supply centre).
INK = RADIUS + 1
#: A supply-centre dot is 20 px across: this keeps the token off it.
SC_RADIUS = 10
SC_CLEAR = RADIUS + SC_RADIUS + 1
#: Token diameter plus a few pixels.
UNIT_GAP = 2 * RADIUS + 4
#: Ink closer to the outline than this is the border's own stroke, not a label.
STROKE = 5
OPEN_COLOURS = [(250, 235, 215), (197, 223, 234)]
TOLERANCE = 12
#: Impassable: it has a unit entry but never a unit.
SKIPPED = {"swi"}
#: How far a name may move, and the attributes of the small label size.
LABEL_REACH = 50
SMALL_LABEL = ('text-anchor="middle" stroke-width="0.1" stroke="black" fill="black" '
               'font-family="serif,sans-serif" font-style="italic" font-size="1.1em"')
#: Unit entries that are a second name for the same sea: they share its position.
ALIASES = {"gol": "lyo", "mid": "mao", "nat": "nao", "nrg": "nwg", "tyn": "tys"}
#: The ``MouseLayer`` id of a province whose path is under its other name.
PATH_IDS = {"lyo": "gol"}


def flatten_path(d: str, dx: float, dy: float) -> list[list[tuple[float, float]]]:
    """An SVG path of ``M``/``C``/``L``/``z`` commands as polygons (one per subpath)."""
    tokens = re.findall(r"[MCLZz]|-?[\d.]+", d)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    pos, command, i = (0.0, 0.0), "L", 0
    while i < len(tokens):
        token = tokens[i]
        if token == "M":
            if current:
                subpaths.append(current)
            pos = (float(tokens[i + 1]), float(tokens[i + 2]))
            current, command, i = [pos], "L", i + 3
        elif token in "Zz":
            i += 1
        elif token in "CL":
            command, i = token, i + 1
        elif command == "C":
            x1, y1, x2, y2, x3, y3 = (float(t) for t in tokens[i:i + 6])
            for k in range(1, 9):
                u = k / 8
                v = 1 - u
                current.append((v**3 * pos[0] + 3 * v * v * u * x1 + 3 * v * u * u * x2 + u**3 * x3,
                                v**3 * pos[1] + 3 * v * v * u * y1 + 3 * v * u * u * y2 + u**3 * y3))
            pos, i = (x3, y3), i + 6
        else:
            pos, i = (float(tokens[i]), float(tokens[i + 1])), i + 2
            current.append(pos)
    if current:
        subpaths.append(current)
    return [[(x + dx, y + dy) for x, y in sub] for sub in subpaths]


def province_polygons(svg: Path = SVG) -> dict[str, list[list[tuple[float, float]]]]:
    """``{name: polygons}`` for every province and coast, in picture coordinates."""
    root = ET.parse(svg).getroot()  # nosec B314 -- the repository's own map
    layer = next(g for g in root.iter(f"{SVG_NS}g") if g.get("id") == "MouseLayer")
    match = re.search(r"translate\((-?[\d.]+)[ ,]+(-?[\d.]+)\)", layer.get("transform", ""))
    dx, dy = (float(match[1]), float(match[2])) if match else (0.0, 0.0)
    polygons: dict[str, list[list[tuple[float, float]]]] = {}
    for element in layer:
        paths = [element] if element.tag == f"{SVG_NS}path" else list(element)
        polygons[element.get("id", "")] = [sub for p in paths for sub in flatten_path(p.get("d", ""), dx, dy)]
    for name, path_id in PATH_IDS.items():
        polygons[name] = polygons[path_id]
    return polygons


def supply_centres(svg: Path = SVG) -> dict[str, tuple[float, float]]:
    """``{name: centre}`` of each supply-centre dot."""
    root = ET.parse(svg).getroot()  # nosec B314 -- the repository's own map
    layer = next(g for g in root.iter(f"{SVG_NS}g") if g.get("id") == "SupplyCenterLayer")
    return {
        use.get("id", "")[3:].lower(): (float(use.get("x", "0")) + SC_RADIUS, float(use.get("y", "0")) + SC_RADIUS)
        for use in layer
    }


def polygon_mask(polygons: list[list[tuple[float, float]]]) -> np.ndarray:
    """The pixels inside ``polygons`` (even-odd, so a lake in a province is out)."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    for polygon in polygons:
        layer = Image.new("1", (WIDTH, HEIGHT), 0)
        ImageDraw.Draw(layer).polygon(polygon, fill=1)
        mask ^= np.array(layer, dtype=bool)
    return mask


def _nearest(ys: np.ndarray, xs: np.ndarray, ty: np.ndarray, tx: np.ndarray) -> np.ndarray:
    """Distance from each (ys, xs) pixel to the nearest (ty, tx) pixel; inf with none."""
    out = np.full(len(ys), np.inf)
    if len(ty) == 0:
        return out
    step = max(1, 4_000_000 // len(ty))
    for i in range(0, len(ys), step):
        out[i:i + step] = np.sqrt(
            ((ys[i:i + step, None] - ty[None]) ** 2 + (xs[i:i + step, None] - tx[None]) ** 2).min(axis=1)
        )
    return out


def edge_distance(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(ys, xs, distance)``: each mask pixel and how far it is from the outside."""
    padded = np.pad(mask, 1, constant_values=False)
    inside = padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    ey, ex = np.nonzero(mask & ~inside)
    ys, xs = np.nonzero(mask)
    return ys, xs, _nearest(ys, xs, ey, ex) + 1


def choose(
    current: tuple[float, float],
    ys: np.ndarray, xs: np.ndarray,
    border: np.ndarray, ink: np.ndarray, centre: np.ndarray, others: np.ndarray,
) -> tuple[tuple[float, float], str]:
    """The position for one unit and the demand it was placed under."""
    apart = others >= UNIT_GAP
    off_dot = centre >= SC_CLEAR
    ladder = [("clear", (border >= BORDER) & (ink >= INK) & apart)]
    ladder += [(f"over its name, border {b}", (border >= b) & off_dot & apart) for b in (BORDER, *BORDER_RELAXED)]
    ladder += [(f"touching its dot, border {b}", (border >= b) & apart) for b in (BORDER, *BORDER_RELAXED[:2])]
    cx, cy = round(current[0]), round(current[1])
    here = (ys == cy) & (xs == cx)
    if here.any() and ladder[0][1][here].all():
        return current, "kept"
    own = np.hypot(xs - current[0], ys - current[1])
    for demand, ok in ladder:
        if ok.any():
            i = int(np.argmin(np.where(ok, own, np.inf)))
            return (float(xs[i]), float(ys[i])), demand
    i = int(np.argmax(np.where(apart, border, -1)))
    return (float(xs[i]), float(ys[i])), "deepest point"


def render(text: str) -> np.ndarray:
    """The SVG source ``text`` as an RGB array (relative references resolve beside the map)."""
    png = cairosvg.svg2png(bytestring=text.encode(), url=str(SVG), output_width=WIDTH, output_height=HEIGHT)
    return np.array(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)


def _matches(picture: np.ndarray, colour: tuple[int, int, int]) -> np.ndarray:
    return np.abs(picture - colour).max(axis=2) <= TOLERANCE


def _label(text: str, name: str) -> tuple[re.Match[str], float, float] | None:
    """The ``<text>`` element naming ``name`` and where it is anchored."""
    found = re.search(rf'<text[^>]*>{name.upper()}</text>', text)
    if found is None:
        return None
    turned = re.search(r'translate\(([\d.]+)[ ,]+([\d.]+)\)', found.group(0))
    if turned:  # a rotated name is anchored by its transform
        return found, float(turned[1]), float(turned[2])
    return found, float(re.search(r' x="([\d.]+)"', found.group(0))[1]), float(re.search(r' y="([\d.]+)"', found.group(0))[1])  # type: ignore[index]


def _spread(mask: np.ndarray, reach: int) -> np.ndarray:
    """``mask`` grown by about ``reach`` pixels in every direction."""
    out = mask.copy()
    for dy in range(-reach, reach + 1, 2):
        for dx in range(-reach, reach + 1, 2):
            out |= np.roll(mask, (dy, dx), axis=(0, 1))
    return out


def move_labels(
    text: str, placed: dict[str, tuple[float, float]], polygons: dict[str, list[list[tuple[float, float]]]],
) -> str:
    """Move each province name a token would cover; returns the new SVG source."""
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    tokens = np.zeros((HEIGHT, WIDTH), dtype=bool)
    for x, y in placed.values():
        tokens |= np.hypot(xx - x, yy - y) <= RADIUS + 2
    layer = re.search(r'(<g [^>]*id="BriefLabelLayer">)(.*?)(</g>)', text, re.S)
    assert layer is not None
    unlabelled = render(text[:layer.start(2)] + text[layer.end(2):])
    offsets = [(dx, dy) for dx in range(-LABEL_REACH, LABEL_REACH + 1, 2) for dy in range(-LABEL_REACH, LABEL_REACH + 1, 2)]
    for name in sorted(n for n in placed if "-" not in n and n not in ALIASES):
        label = _label(text, name)
        if label is None:
            continue
        found, x, y = label
        without = render(text[:found.start()] + text[found.end():])
        iy, ix = np.nonzero(np.abs(render(text) - without).max(axis=2) > 40)
        if not tokens[iy, ix].any():
            continue
        small = f'<text {SMALL_LABEL} x="{x}" y="{y}">{name.upper()}</text>'
        iy, ix = np.nonzero(np.abs(render(text[:found.start()] + small + text[found.end():]) - without).max(axis=2) > 40)
        own = polygon_mask(polygons[name])
        land, sea = _matches(without, OPEN_COLOURS[0]), _matches(without, OPEN_COLOURS[1])
        beside_a_name = _spread(np.abs(without - unlabelled).max(axis=2) > 40, 8)
        # Per pixel of the name: under a token, on other ink (a border, a dot,
        # another name), on a neighbour's land, on open sea, in its own province;
        # and right beside another name, where the two would read as one.
        cost = np.where(tokens, 10.0, np.where(~(land | sea), 4.0, np.where(own, 0.0, np.where(sea, 0.3, 2.0))))
        cost = cost + np.where(beside_a_name, 1.5, 0.0)
        best, best_cost = (0, 0), math.inf
        for dx, dy in offsets:
            ys, xs = iy + dy, ix + dx
            if ys.min() < 0 or xs.min() < 0 or ys.max() >= HEIGHT or xs.max() >= WIDTH:
                continue
            total = float(cost[ys, xs].sum()) + 3 * math.hypot(dx, dy)
            if total < best_cost:
                best, best_cost = (dx, dy), total
        moved = f'<text {SMALL_LABEL} x="{x + best[0]:.1f}" y="{y + best[1]:.1f}">{name.upper()}</text>'
        text = text[:found.start()] + moved + text[found.end():]
        print(f"{name:7} name ({x:.0f},{y:.0f}) -> ({x + best[0]:.0f},{y + best[1]:.0f})  cost {best_cost:.0f}")
    return text


def main() -> int:
    text = SVG.read_text()
    picture = render(text)
    is_open = _matches(picture, OPEN_COLOURS[0]) | _matches(picture, OPEN_COLOURS[1])

    entry = re.compile(r'(<jdipNS:PROVINCE name="([^"]+)">\s*<jdipNS:UNIT x=")([\d.]+)(" y=")([\d.]+)(")')
    positions = {m.group(2): (float(m.group(3)), float(m.group(5))) for m in entry.finditer(text)}
    polygons, centres = province_polygons(), supply_centres()
    names = sorted(n for n in positions if n not in ALIASES and n not in SKIPPED)

    fields = {}
    for name in names:
        ys, xs, border = edge_distance(polygon_mask(polygons[name]))
        inked = ~is_open[ys, xs] & (border >= STROKE)
        ink = _nearest(ys, xs, ys[inked], xs[inked])
        sx, sy = centres.get(name.split("-")[0], (math.inf, math.inf))
        centre = np.hypot(xs - sx, ys - sy) if math.isfinite(sx) else np.full(len(xs), np.inf)
        fields[name] = (ys, xs, border, ink, centre)

    placed = {name: positions[name] for name in names}
    demands: dict[str, str] = {}
    for _ in range(6):  # a move changes its neighbours' room: repeat until nothing moves
        moved = False
        for name in names:
            ys, xs, border, ink, centre = fields[name]
            others = np.full(len(xs), np.inf)
            for other, (ox, oy) in placed.items():
                if other != name:
                    others = np.minimum(others, np.hypot(xs - ox, ys - oy))
            spot, demand = choose(placed[name], ys, xs, border, ink, centre, others)
            if demand != "kept":
                demands[name] = demand
                moved = moved or spot != placed[name]
                placed[name] = spot
        if not moved:
            break
    else:
        raise SystemExit("the positions did not settle")

    for name in names:
        (ox, oy), (nx, ny) = positions[name], placed[name]
        if (ox, oy) != (nx, ny):
            print(f"{name:7} ({ox:.0f},{oy:.0f}) -> ({nx:.0f},{ny:.0f})  moved {math.hypot(nx - ox, ny - oy):3.0f}"
                  f"  {demands[name]}")
    text = move_labels(text, placed, polygons)
    for alias, name in ALIASES.items():
        placed[alias] = placed[name]

    def replace(m: re.Match[str]) -> str:
        x, y = placed.get(m.group(2), positions[m.group(2)])
        return f"{m.group(1)}{x:.1f}{m.group(4)}{y:.1f}{m.group(6)}"

    SVG.write_text(entry.sub(replace, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
