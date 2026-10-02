"""Recompute the ``jdipNS:DISLODGED_UNIT`` positions in ``standard.svg``.

A dislodged unit is drawn beside the unit that took its place, so its position
must be clear of that unit, clear of every neighbouring province's unit, and
inside its own province. The positions the SVG shipped with were the unit
position moved a flat 15 px up-left, which hid most of the dislodged token under
the victor. This script derives better ones from the rendered map itself:

1. Render the bare map and flood-fill each province from its unit position over
   the plain land or sea colour. Borders, coastlines, labels and supply-centre
   dots are all darker, so the fill is the open part of the province.
2. Measure each open pixel's distance to the nearest closed one (a breadth-first
   distance transform), so a token placed there stays off borders and labels.
3. Pick the nearest point to the unit position that is at least ``GAPS[0]`` from
   every unit position on the map and ``MARGIN`` from the region's edge,
   relaxing the margin where a province is too small to allow it.

Run from the repository root; it rewrites the SVG in place and prints what moved.
``tests/test_dislodged_anchors.py`` checks the result.

    PYTHONPATH=src python maps/place_dislodged_anchors.py
"""
from __future__ import annotations

import io
import math
import re
import sys
from collections import deque
from pathlib import Path

import cairosvg  # type: ignore
import numpy as np
from PIL import Image

SVG = Path(__file__).with_name("standard.svg")
WIDTH, HEIGHT = 1835, 1360
#: Unit token diameter plus a few pixels: two tokens this far apart do not touch. A
#: province too small for that (London, Yorkshire) settles for a slight overlap.
GAPS = (34.0, 30.0, 26.0)
#: Preferred distance from the token centre to the region's edge (its radius).
MARGINS = (15, 12, 9, 6, 3)
OPEN_COLOURS = [(250, 235, 215), (197, 223, 234)]
TOLERANCE = 12


def _open_mask(img: np.ndarray) -> np.ndarray:
    mask = np.zeros(img.shape[:2], dtype=bool)
    for colour in OPEN_COLOURS:
        mask |= (np.abs(img.astype(int) - colour).max(axis=2) <= TOLERANCE)
    return mask


def _region(open_mask: np.ndarray, seed: tuple[int, int]) -> np.ndarray:
    """Flood-fill the open pixels connected to the nearest open pixel to ``seed``."""
    sx, sy = seed
    best = None
    for r in range(0, 30):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                x, y = sx + dx, sy + dy
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and open_mask[y, x]:
                    best = (x, y)
                    break
            if best:
                break
        if best:
            break
    if best is None:
        raise ValueError(f"no open pixel near {seed}")
    region = np.zeros_like(open_mask)
    queue = deque([best])
    region[best[1], best[0]] = True
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < WIDTH and 0 <= ny < HEIGHT and open_mask[ny, nx] and not region[ny, nx]:
                region[ny, nx] = True
                queue.append((nx, ny))
    return region


def _edge_distance(region: np.ndarray) -> np.ndarray:
    """Chessboard distance from each region pixel to the nearest non-region pixel."""
    ys, xs = np.nonzero(region)
    y0, y1, x0, x1 = ys.min() - 1, ys.max() + 2, xs.min() - 1, xs.max() + 2
    sub = region[max(y0, 0):y1, max(x0, 0):x1]
    dist = np.full(sub.shape, -1, dtype=int)
    queue: deque[tuple[int, int]] = deque()
    h, w = sub.shape
    for y in range(h):
        for x in range(w):
            if not sub[y, x]:
                dist[y, x] = 0
                queue.append((x, y))
    # Pixels on the bounding box edge that are in the region still border the outside.
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                       (x + 1, y + 1), (x - 1, y - 1), (x + 1, y - 1), (x - 1, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and dist[ny, nx] < 0:
                dist[ny, nx] = dist[y, x] + 1
                queue.append((nx, ny))
    full = np.zeros(region.shape, dtype=int)
    full[max(y0, 0):y1, max(x0, 0):x1] = dist
    return full


def main() -> int:
    text = SVG.read_text()
    img = np.array(Image.open(io.BytesIO(cairosvg.svg2png(
        url=str(SVG), output_width=WIDTH, output_height=HEIGHT))).convert("RGB"))
    open_mask = _open_mask(img)

    block = re.compile(
        r'(<jdipNS:PROVINCE name="([^"]+)">\s*<jdipNS:UNIT x="([\d.]+)" y="([\d.]+)"/>\s*'
        r'<jdipNS:DISLODGED_UNIT x=")([\d.]+)(" y=")([\d.]+)("/>)'
    )
    entries = [(m.group(2), float(m.group(3)), float(m.group(4))) for m in block.finditer(text)]
    unit_points = [(x, y) for _, x, y in entries]
    anchors: dict[str, tuple[float, float]] = {}
    for name, ux, uy in entries:
        region = _region(open_mask, (round(ux), round(uy)))
        edge = _edge_distance(region)
        ys, xs = np.nonzero(region)
        nearest_unit = np.full(len(xs), np.inf)
        for px, py in unit_points:
            nearest_unit = np.minimum(nearest_unit, np.hypot(xs - px, ys - py))
        own = np.hypot(xs - ux, ys - uy)
        choice = None
        for gap in GAPS:
            for margin in MARGINS:
                ok = (nearest_unit >= gap) & (edge[ys, xs] >= margin)
                if ok.any():
                    i = int(np.argmin(np.where(ok, own, np.inf)))
                    choice = (float(xs[i]), float(ys[i]))
                    break
            if choice is not None:
                break
        if choice is None:
            raise SystemExit(f"{name}: no clear spot in its region")
        anchors[name] = choice
        print(f"{name:8} unit=({ux:.0f},{uy:.0f}) dislodged=({choice[0]:.0f},{choice[1]:.0f}) "
              f"d={math.hypot(choice[0] - ux, choice[1] - uy):.0f}")

    def replace(m: re.Match[str]) -> str:
        x, y = anchors[m.group(2)]
        return f"{m.group(1)}{x:.1f}{m.group(6)}{y:.1f}{m.group(8)}"

    SVG.write_text(block.sub(replace, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
