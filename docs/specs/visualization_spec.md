# Visualization Specification

What the map renderer draws and why. Implementation lives in
[`src/rendering/`](https://github.com/tenderi/diplomacy/tree/main/src/rendering/); every size, colour, and line style is data in
[`visualization_config.json`](https://github.com/tenderi/diplomacy/blob/main/src/rendering/visualization_config.json), not a constant
in code. **That file is the source of truth for values — this document is the source of
truth for meaning.**

## Map types

Three renders, all produced from a `GameService.view`-shaped dict plus optional order or
resolution data (never from engine internals):

| Type | Entry point | Content |
|---|---|---|
| **Board** | `render_board_png` | Units, centre ownership, dislodged units with where they may retreat. |
| **Orders** | `render_board_png_orders` | The board plus every submitted order, before adjudication. |
| **Orders and results** | `render_board_png_resolution` | A processed turn's orders, each drawn with its outcome, **on the board they were given on**. |

The results picture is always drawn on the board the turn was played on (snapshot `n` for
turn `n`; the opening position for turn 0). Drawn over the board the turn *produced*, the
unit in a province is often not the one that gave or received the order there, and every
marker lands on the wrong unit. `/games/{id}/map/resolution` is the last processed turn's
picture; `/games/{id}/map/turn/{n}/orders` is any turn's. After every processed turn a
game's Telegram group gets that picture and the board the turn produced
(`/games/{id}/map/history/{n+1}`).

## The one rule

**Every marker belongs to the unit that gave the order and is drawn at that unit**, never
at a province centre where another unit may stand. A bounced attack is marked on the
attacker's arrow, not on the defender; a dislodgement is marked on the unit dislodged.

## Units and provinces

- **Unit:** a disc in the power's colour with a bold `A` or `F` (white on dark colours,
  near-black on light ones). A letter survives Telegram's downscaling; a silhouette did not.
- **Dislodged unit** (on a retreat board): the same disc with a red ring, drawn at its
  province's `DISLODGED_UNIT` position — a spot clear of the province's own unit and of every
  neighbour's (`maps/place_dislodged_anchors.py` derives them from the rendered map) — and
  drawn last, so it is never under the unit that replaced it.
- **Retreat options** (retreat board): a thin dotted line from the dislodged unit to each
  province it may retreat to, ending in a small open circle; a red ✗ beside a unit with
  nowhere to go.
- **Provinces** are tinted with the owner's colour; an occupied province shows the
  occupant's. Seas are hatched instead of filled. Ownership is recomputed only after Fall
  settles, matching the engine.
- **Power colours** (`colors.power_colors`): Austria red, England purple, France blue,
  Germany charcoal, Italy green, Russia teal, Turkey yellow — seven hues no two of which are
  close, and none of which is an outcome colour.

## Orders

Lines are in the ordering power's colour with a dark casing, so they read on land, sea and
any tint. Order lines run **under** the unit tokens; markers sit **over** them.

| Order | Drawn as |
|---|---|
| **Move** | Solid arrow from the unit to the destination; it stops short of a unit standing there and reaches the centre of an empty province. |
| **Opposed moves** (A→B and B→A) | The two arrows side by side, each offset to its own right, never on top of each other. |
| **Convoyed move** | The same arrow, curving through every convoying fleet in route order. |
| **Hold** | An octagon round the unit, outside the disc. (A unit with no order holds too, but is not marked.) |
| **Support to hold** | A dashed line, no arrowhead, ending in a ring round the supported unit (rings stack outward when several powers support one unit). |
| **Support to move** | A dashed line, no arrowhead, ending in a dot on the supported move's arrow. |
| **Convoy** | A dashed ring round the convoying fleet. A route no army took is shown as a thin dotted arrow. |
| **Retreat** | A dashed arrow from the dislodged unit. |
| **Build** | The new unit, translucent, with a green `+` badge. |
| **Disband** | A red ✗ over the unit. |

## Outcomes (results picture)

Success is the default and is not marked. Only what went wrong is.

| Outcome | Drawn as |
|---|---|
| **Bounced** | The move's arrow stops at the border (half way along its last leg) on a red bar. |
| **Standoff** | An orange burst in the province nobody got into — at its centre, or at its free spot when a unit (one that moved out) is drawn there. |
| **Dislodged** | A red ring round the unit, whatever its own order did (the engine's `dislodged` flag, not only the `DISLODGED` result). |
| **Support cut** | The support line faded, with a red ✗ across it near the supporter. |
| **Had no effect** (void) | The support line grey. |
| **Failed** (void move, no convoy path) | The arrow dashed and faded, with a red ✗ at its tip. |
| **Retreat failed** | The retreat arrow stops on a red bar, like a bounce. |

The orders picture shows no outcome at all: nothing red, nothing grey.

## Footer

A strip **below** the map, never on it (a key drawn on the map covered Portugal and the
Mid-Atlantic): the title (`Orders` / `Orders and results`, then the phase, e.g. `Spring 1901 movement ·
S1901M`), the key for exactly the symbols the picture uses, and a swatch per power on the
board, wrapping onto more rows when needed.

## Technical

- **Format:** PNG; the SVG is rasterized at its native 1835×1360 and flattened onto white
  (the raster is transparent along every border, which a dark viewer showed as black), then
  the footer is appended below.
- **Layers:** base map and tints → order lines → unit tokens → build tokens → markers →
  footer. Overlays are drawn on a 3× supersampled layer and downscaled (`antialias.py`).
- **Caching:** in memory and on disk at `/tmp/diplomacy_map_cache`, keyed by everything that
  changes the picture, plus `cache.RENDERER_VERSION`. **Bump `RENDERER_VERSION` whenever the
  drawing for the same inputs changes**, or a restart serves the old picture from disk.
- **Determinism:** the same state and orders render byte-identically.
- **Tests** check the picture by its numbers, not by "a PNG came back": geometry in
  `tests/test_arrow_geometry.py`, every symbol's placement against real adjudications in
  `tests/test_order_symbols.py`, pixels in `tests/test_board_render.py`, the dislodged spots
  in `tests/test_dislodged_anchors.py`.

## Configuration

`visualization_config.json` groups values under `colors` (including `power_colors`),
`units`, `arrows`, `line_styles`, `markers` and `footer`. Add new visual constants there
rather than in code. `VisualizationConfig.DEFAULT_CONFIG` holds the same values so a missing
file still renders; a test keeps the two identical.

## Out of scope

Interactive/clickable maps, animation, 3D or alternate themes, heatmaps and strategic
overlays, and stalemate/elimination/victory special renders. Map variants beyond `standard`
are out of scope for the whole project.
