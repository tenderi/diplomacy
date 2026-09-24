# Visualization Specification

What the map renderer draws and why. Implementation lives in
[`src/rendering/`](../../src/rendering/); every size, colour, and line style is data in
[`visualization_config.json`](../../src/rendering/visualization_config.json), not a constant
in code. **That file is the source of truth for values — this document is the source of
truth for meaning.**

## Map types

Three renders, all produced from a `GameService.view` dict plus optional order/resolution
data (never from engine internals):

| Type | Entry point | Content |
|---|---|---|
| **Board** | `render_board_png` | Unit positions, supply-center ownership, phase overlay. No order indicators. |
| **Orders** | `render_board_png_orders` | The board plus every submitted order, before adjudication. |
| **Resolution** | `render_board_png_resolution` | The board plus order outcomes: successes, failures, bounces, cuts, dislodgements. |

Available on demand via the map endpoints, on each phase transition for channel posting, and
per-phase during the demo game (see
[`automated_demo_game_spec.md`](automated_demo_game_spec.md)).

**Visual clarity principle:** each order type gets a distinct colour *and* line style, so a
crowded board stays readable.

## Province and supply-center colouring

- Provinces are filled with the controlling power's colour at a light tint.
- Supply centers keep the **owner's** colour when unoccupied — ownership persists, it isn't
  derived from unit presence.
- When a unit occupies a province, that province shows the **occupying** unit's power colour.
- Ownership is recomputed only after the Fall turn fully settles, so resolution and retreat
  maps still show the pre-Fall controller. This is deliberate: it matches when the engine
  actually flips ownership.

Power colours (`colors.power_colors`): Austria `#c48f85`, England `darkviolet`, France
`royalblue`, Germany `#a08a75`, Italy `forestgreen`, Russia `#757d91`, Turkey `#b9a61c`.

## Markers

All arrows share one shape and arrowhead size (`arrows.*` in the config) and differ only in
colour and dash pattern. Two line widths exist: `line_width_primary` for movement,
`line_width_secondary` for everything else.

| Element | Style |
|---|---|
| **Unit** | Filled circle in the power colour, black border, `A`/`F` label centred. |
| **Dislodged unit** | Same circle, red border, a `D` badge, drawn at `units.dislodged_offset` from the province center. Only shown on resolution and retreat maps. |
| **Move** | Solid arrow in the mover's power colour. |
| **Hold** | Dashed circle around the unit, larger than the unit marker. |
| **Support (hold)** | Dashed line to the defended unit plus a solid ring around it in the *supporter's* power colour. |
| **Support (move)** | Dashed two-segment arrow: supporter → supported unit → target. |
| **Convoy** | Solid curved path in the convoy colour through every convoying fleet to the destination, with a ring on each fleet. A multi-fleet chain renders as **one** merged path, not one arrow per fleet. |
| **Retreat** | Dotted arrow from the dislodged unit's offset position to the destination. |
| **Build / disband** | Green circle with `+` and the unit letter / red circle with `×`. |
| **Success / failure** | Green checkmark / red `×` at the arrow tip. |
| **Dislodged (order status)** | A heavy hollow ring, visually distinct from both success and failure. Only `Hold` and `Convoy` orders can carry this status. |
| **Support cut** | Red `×` across the middle of the support line. |
| **Standoff / bounce** | Standoff marker at the contested province; bounce shown as a dashed return curve. |

### Draw order (bottom to top)

Base map → province fills → hold indicators → support lines and rings → convoy routes →
movement arrows → retreat arrows → unit markers → build/disband markers → conflict markers
→ status indicators → phase overlay → legend.

This keeps primary actions (movement arrows) visible above context (support, convoy), unit
markers always visible, and status indicators on top.

### Legend

Bottom-left, semi-transparent white with a black border, and **context-aware** — an orders
map legends move/hold/support/convoy, a resolution map legends success/failed/bounced/
dislodged/support-cut, an adjustment map legends build/disband. Every legend includes the
power colour swatches for the powers actually on the board.

## Phase overlay

Top corner, on a readable background: year, season, phase name, and optionally the phase
code (`S1901M`).

## Technical

- **Format:** PNG, 24-bit RGB with alpha for overlays. Base render is the SVG's native
  resolution.
- **Pipeline:** load `standard.svg` → parse province coordinates from path data → fill
  provinces → draw units → draw overlays in priority order → phase text → legend → export
  via CairoSVG + Pillow.
- **Caching:** in memory and on disk at `/tmp/diplomacy_map_cache`, keyed by state plus
  orders. First render of a map is slow; the rest are not.
- **Determinism:** the same state and orders must render byte-identically. Any change meant
  to be behaviour-preserving should be validated by comparing PNG sha256 before and after
  with the cache cleared — see [`testing_and_validation.md`](testing_and_validation.md).

## Configuration

`visualization_config.json` groups values under `arrows`, `colors` (including
`power_colors`), `units`, `line_styles`, and `legend`. Add new visual constants there rather
than in code; the loader falls back to built-in defaults for anything missing.

> The config file lives in `src/rendering/`, next to its loader. It was briefly stranded in
> `src/engine/` after the rendering split, which silently disabled every override — if arrow
> styling ever looks like the built-in defaults, check that the file is beside
> `visualization_config.py`.

## Out of scope

Interactive/clickable maps, animation, 3D or alternate themes, heatmaps and strategic
overlays, and stalemate/elimination/victory special renders. Map variants beyond `standard`
are out of scope for the whole project.
