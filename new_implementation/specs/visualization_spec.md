# Visualization Specification for Diplomacy Game

## Purpose
This document defines the complete visualization requirements for the Diplomacy game engine, specifying what maps should be generated, when they should be created, and what visual elements they must contain. These visualizations serve multiple purposes:
- **Player Communication**: Help players understand game state and submitted orders
- **Educational**: Demonstrate game mechanics through visual representation
- **Analysis**: Enable strategic analysis and game review
- **Debugging**: Assist developers in understanding game state transitions

## Overview

The visualization system generates maps at key points during game progression, showing:
1. **Game State**: Current unit positions and supply center control
2. **Order Intent**: Submitted orders before processing (with clear visual distinction between order types)
3. **Resolution Results**: Order outcomes, conflicts, and dislodgements
4. **Phase Completion**: Final stable state after phase processing

**Visual Clarity Principle**: Each order type uses distinct colors and styles to minimize visual clutter and clearly communicate order intent.

---

## 1. Phases Requiring Visualization

### 1.1 Movement Phase
**When**: Spring and Autumn turns, before Retreat/Adjustment phases
**Required Maps**:
- Initial state (before orders submitted)
- Orders map (showing all submitted orders)
- Resolution map (showing order results and conflicts)
- Final state (after movement adjudication)

**Special Cases**:
- If no orders submitted: Still generate initial and final maps
- If all orders are holds: Orders map shows hold indicators
- If conflicts occur: Resolution map shows detailed conflict information

### 1.2 Retreat Phase
**When**: After Movement phase if any units are dislodged
**Required Maps**:
- Initial state (showing dislodged units)
- Orders map (showing retreat/disband orders)
- Resolution map (showing retreat outcomes)
- Final state (after retreats processed)

**Special Cases**:
- If no valid retreats: Show forced disbands
- If retreat fails: Show unit elimination
- If multiple retreat options: Show all options with selected retreat

### 1.3 Build/Destroy Phase (Adjustment Phase)
**When**: After Fall turns (Autumn completion)
**Required Maps**:
- Initial state (showing supply center control and unit count)
- Orders map (showing build/destroy orders)
- Resolution map (showing new units and eliminated units)
- Final state (after builds/destroys processed)

**Special Cases**:
- If no builds/destroys needed: Still generate initial and final maps
- If units must be destroyed: Show destroy indicators
- If units can be built: Show build locations and unit types

---

## 2. Map Types and Their Content

### 2.1 Initial State Map
**Purpose**: Show game state before orders are submitted or processed
**Content**:
- All current unit positions (by power color)
- Supply center ownership (colored by controlling power)
- Phase information overlay (year, season, phase)
- Turn number indicator

**Visual Elements**:
- Units drawn as colored circles with type indicators (A/F)
- Provinces colored by controlling power
- Unoccupied supply centers shown in owner's color
- No order indicators visible (clean state view)

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_initial.png`
**Example**: `demo_01_1901_Spring_Movement_initial.png`

### 2.2 Orders Map
**Purpose**: Show all submitted orders before adjudication with clear visual distinction
**Content**: All current unit positions plus order indicators (movement arrows, support lines, convoy routes, hold indicators, retreat arrows, build/destroy markers). See section 3.4 for detailed marker specifications.

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_orders.png`
**Example**: `demo_01_1901_Spring_Movement_orders.png`

### 2.3 Resolution Map
**Purpose**: Show order adjudication results, conflicts, and outcomes
**Content**: Final unit positions plus status indicators (success checkmarks, failure X marks, dislodged units, conflict markers, standoff indicators, bounce indicators). See section 3.4 for detailed marker specifications.

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_resolution.png`
**Example**: `demo_01_1901_Spring_Movement_resolution.png`

### 2.4 Final State Map
**Purpose**: Show stable game state after phase completion
**Content**: All final unit positions, updated supply center control, phase information overlay. No order indicators (clean state view).

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_final.png`
**Example**: `demo_01_1901_Spring_Movement_final.png`

---

## 3. Visual Element Specifications

**Note**: All visual specifications in this section should be configurable via a configuration file (see section 4.0). The values provided here are defaults/recommendations that can be overridden through configuration. Where possible, common variables should be used (e.g., all arrows share the same shape and size, differing only in color and line style).

### 3.1 Power Colors
- **AUSTRIA**: `#c48f85` (light brown)
- **ENGLAND**: `darkviolet` (purple)
- **FRANCE**: `royalblue` (blue)
- **GERMANY**: `#a08a75` (gray-brown)
- **ITALY**: `forestgreen` (green)
- **RUSSIA**: `#757d91` (blue-gray)
- **TURKEY**: `#b9a61c` (yellow-brown)

### 3.2 Supply Center Visualization
**Ownership**:
- Province filled with controlling power's color (light tint, ~30% opacity)
- Border highlighted if supply center

**Unoccupied Supply Centers**:
- Filled with owner's color (lighter tint)
- Unit placement override: If unit occupies, province shows unit's power color

**Control Changes**:
- In resolution maps, show previous owner (faded) and new owner (solid)
- Transition indicators if ownership changes

### 3.3 Phase Information Overlay
**Required Information**:
- Year (e.g., "1901")
- Season ("Spring" or "Autumn")
- Phase ("Movement", "Retreat", "Builds")
- Turn number (optional, for multi-year games)
- Phase code (optional, e.g., "S1901M")

**Display Format**:
- Text overlay in corner (typically top-left or top-right)
- Background for readability (semi-transparent or solid)
- Font size: 14-18 points
- Color: Black or white (depending on background)

---

## 3.4 Detailed Marker Specifications

This section provides comprehensive visual specifications for all markers used in map visualizations. All values are defaults that should be configurable via configuration file (see section 4.0).

### 3.4.1 Unit Markers

#### Standard Unit Marker (Army/Fleet)
**Shape**: Circle
**Size**: 20-25 pixels diameter
**Fill Color**: Power color (see section 3.1 for power colors)
**Border**: 
  - Width: 2-3 pixels
  - Color: Black (`#000000`)
  - Style: Solid
**Label**:
  - Text: "A" for Army, "F" for Fleet
  - Font: Sans-serif, bold
  - Font size: 10-12 points
  - Color: White or black (contrasting with power color)
  - Position: Centered within circle
**Position**: Province center coordinates (from SVG path data)

#### Dislodged Unit Marker
**Shape**: Circle (same as standard unit)
**Size**: 20-25 pixels diameter
**Fill Color**: Power color (same as standard unit)
**Border**:
  - Width: 3-4 pixels
  - Color: Red (`#FF0000` or `#DC143C`)
  - Style: Solid, thicker than standard
**Label**: Same as standard unit ("A" or "F")
**Dislodged Indicator**:
  - Shape: Small circle or square
  - Size: 8-10 pixels
  - Color: Red (`#FF0000`)
  - Label: "D" (white text, 8-10 point font)
  - Position: Top-right corner of unit circle (offset by 5-7 pixels)
**Position**: Offset from province center by (+20, +20) pixels
**Visibility**: Only shown during Resolution and Retreat phases

### 3.4.2 Movement Order Markers

#### Movement Arrow
**Shape**: Straight line with arrowhead
**Line**:
  - Width: 3-4 pixels
  - Color: Power color of moving unit
  - Style: Solid
  - Start: Origin province center
  - End: Destination province center
**Arrowhead**:
  - Shape: Triangular arrowhead
  - Size: 12-15 pixels (base width)
  - Color: Same as line (power color)
  - Position: At destination province center
  - Fill: Solid (same color as line)
**Status Indicators** (on Resolution maps):
  - **Success**: Green checkmark (✓) at arrow tip
    - Size: 12-15 pixels
    - Color: Green (`#00FF00` or `#32CD32`)
    - Position: Overlapping arrowhead
  - **Failure**: Red X (✗) at arrow tip
    - Size: 12-15 pixels
    - Color: Red (`#FF0000`)
    - Position: Overlapping arrowhead
    - Line width: 2-3 pixels
  - **Bounce**: Curved arrow showing return path
    - Style: Dashed or dotted
    - Color: Orange or yellow (`#FFA500` or `#FFD700`)
    - Width: 2-3 pixels
    - Path: Destination → Origin (curved)

### 3.4.3 Hold Order Markers

#### Hold Indicator
**Shape**: Circle or dashed border around unit
**Size**: 30-35 pixels diameter (larger than unit circle)
**Border**:
  - Width: 2-3 pixels
  - Color: Power color of holding unit
  - Style: Dashed or dotted
  - Dash pattern: 4-5 pixels dash, 2-3 pixels gap
**Position**: Centered on unit (unit circle inside hold indicator)
**Label** (optional):
  - Text: "H"
  - Font: Sans-serif, regular
  - Font size: 8-10 points
  - Color: Power color
  - Position: Below or to the side of unit marker

### 3.4.4 Support Order Markers

#### Defensive Support (Hold Support)
**Support Line**:
  - Shape: Straight dashed line
  - Width: 2-3 pixels
  - Color: Light green (`#90EE90`)
  - Style: Dashed
  - Dash pattern: 3-4 pixels dash, 2-3 pixels gap
  - Start: Supporting unit center
  - End: Defended unit center
**Defended Unit Circle**:
  - Shape: Circle around defended unit
  - Size: 30-35 pixels diameter
  - Border:
    - Width: 3-4 pixels
    - Color: Supporting unit's power color (not light green)
    - Style: Solid
  - Position: Centered on defended unit
**Support Cut Indicator** (if support is cut):
  - Shape: Red X (✗) across support line
  - Size: 15-18 pixels
  - Color: Red (`#FF0000`)
  - Line width: 3-4 pixels
  - Position: Center of support line

#### Offensive Support (Move Support)
**Support Arrow**:
  - Shape: Dashed arrow path with two segments
  - Path: Supporting unit → Supported unit's province → Attack target
  - Width: 2-3 pixels
  - Color: Light pink (`#FFB6C1`) or sky blue (`#87CEEB`)
  - Style: Dashed
  - Dash pattern: 3-4 pixels dash, 2-3 pixels gap
  - Arrowhead: At attack target (same style as movement arrow)
**Support Cut Indicator** (if support is cut):
  - Same as defensive support: Red X across support line
  - Position: Center of support line segment

### 3.4.5 Convoy Order Markers

#### Convoy Route
**Shape**: Curved path connecting convoyed army, convoying fleets, and destination
**Path**:
  - Start: Convoyed army position
  - Waypoints: Each convoying fleet position
  - End: Destination province center
  - Style: Curved (bezier curve) to show flow
**Line**:
  - Width: 2-3 pixels
  - Color: Gold (`#FFD700`) or dark orange (`#FF8C00`)
  - Style: Solid (distinct from support dashed lines)
**Arrowhead**:
  - Shape: Triangular arrowhead
  - Size: 12-15 pixels
  - Color: Same as line (gold/orange)
  - Position: At destination province center
**Convoying Fleet Markers**:
  - Shape: Circle around convoying fleet
  - Size: 28-32 pixels diameter
  - Border:
    - Width: 2-3 pixels
    - Color: Gold (`#FFD700`) or dark orange (`#FF8C00`)
    - Style: Solid or dashed
  - Position: Centered on convoying fleet unit

### 3.4.6 Retreat Order Markers

#### Retreat Arrow
**Shape**: Dotted line with arrowhead
**Line**:
  - Width: 2-3 pixels
  - Color: Power color (if valid retreat) or red (`#FF0000` if invalid)
  - Style: Dotted
  - Dot pattern: 2-3 pixels dot, 2-3 pixels gap
  - Start: Dislodged unit position (offset position)
  - End: Retreat destination province center
**Arrowhead**:
  - Shape: Triangular arrowhead
  - Size: 10-12 pixels
  - Color: Same as line
  - Position: At retreat destination
**Invalid Retreat Indicator**:
  - Shape: Red X (✗) at arrow tip
  - Size: 12-15 pixels
  - Color: Red (`#FF0000`)
  - Position: Overlapping arrowhead

### 3.4.7 Build Order Markers

#### Build Marker
**Shape**: Circle with plus sign (+) or green circle
**Size**: 15-20 pixels diameter
**Fill Color**: Green (`#00FF00` or `#32CD32`)
**Border**:
  - Width: 2-3 pixels
  - Color: Power color of building power
  - Style: Solid
**Label**:
  - Text: "A" or "F" (unit type being built)
  - Font: Sans-serif, bold
  - Font size: 10-12 points
  - Color: White or black (contrasting with green)
  - Position: Centered within marker
**Plus Sign** (alternative):
  - Shape: Plus (+) symbol
  - Size: 10-12 pixels
  - Color: White
  - Line width: 2-3 pixels
  - Position: Centered within green circle
**Position**: Build location (home supply center province center)

### 3.4.8 Destroy Order Markers

#### Destroy Marker
**Shape**: Circle with X or red circle with X
**Size**: 15-20 pixels diameter
**Fill Color**: Red (`#FF0000` or `#DC143C`)
**Border**:
  - Width: 2-3 pixels
  - Color: Power color of destroying power
  - Style: Solid
**X Symbol**:
  - Shape: X (cross)
  - Size: 10-12 pixels
  - Color: White
  - Line width: 2-3 pixels
  - Position: Centered within red circle
**Label** (optional):
  - Text: "A" or "F" (unit type being destroyed)
  - Font: Sans-serif, bold
  - Font size: 8-10 points
  - Color: White
  - Position: Below or to the side of X symbol
**Position**: Unit location (province center where unit is being destroyed)

### 3.4.9 Conflict Markers

#### Battle Indicator
**Shape**: Star, shield, or crossed swords symbol
**Size**: 20-25 pixels
**Color**: Red (`#FF0000`) or orange (`#FFA500`)
**Border**: 
  - Width: 2-3 pixels
  - Color: Black or dark red
  - Style: Solid
**Position**: At conflict location (province center where battle occurs)
**Label** (optional):
  - Text: Strength numbers (e.g., "3v2" for 3 attackers vs 2 defenders)
  - Font: Sans-serif, bold
  - Font size: 10-12 points
  - Color: White or black (contrasting with marker)
  - Position: Centered within or below marker

#### Standoff Indicator
**Shape**: Equal sign (=) or balanced scales symbol
**Size**: 18-22 pixels
**Color**: Yellow (`#FFD700`) or orange (`#FFA500`)
**Border**:
  - Width: 2-3 pixels
  - Color: Black
  - Style: Solid
**Position**: At standoff location (province center)
**Label** (optional):
  - Text: "Standoff" or "="
  - Font: Sans-serif, bold
  - Font size: 8-10 points
  - Color: Black
  - Position: Below marker

#### Bounce Indicator
**Shape**: Curved arrow showing return path
**Line**:
  - Width: 2-3 pixels
  - Color: Orange (`#FFA500`) or yellow (`#FFD700`)
  - Style: Dashed or dotted
  - Path: Curved from destination back to origin
**Arrowhead**: At origin (showing return)
**Position**: Overlapping or near the failed movement arrow

### 3.4.10 Status Indicators

#### Success Checkmark
**Shape**: Checkmark (✓)
**Size**: 12-15 pixels
**Color**: Green (`#00FF00` or `#32CD32`)
**Line Width**: 2-3 pixels
**Position**: At arrow tip or order completion point
**Usage**: Movement success, successful retreat, successful build

#### Failure X Mark
**Shape**: X (✗)
**Size**: 12-15 pixels
**Color**: Red (`#FF0000`)
**Line Width**: 2-3 pixels
**Position**: At arrow tip or order failure point
**Usage**: Movement failure, retreat failure, support cut

### 3.4.11 Visual Layer Priority

Markers are drawn in the following order (bottom to top) to ensure clarity:
1. **Base map** (SVG background)
2. **Province fills** (supply center control colors)
3. **Hold indicators** (dashed circles around units)
4. **Support lines and circles** (defensive and offensive support)
5. **Convoy routes** (curved gold/orange paths)
6. **Movement arrows** (primary actions, on top)
7. **Retreat arrows** (if in retreat phase)
8. **Unit markers** (standard and dislodged)
9. **Build/Destroy markers** (if in build phase)
10. **Conflict markers** (battles, standoffs)
11. **Status indicators** (checkmarks, X marks)
12. **Phase information overlay** (text in corner)

This layering ensures that:
- Movement arrows (primary actions) remain clearly visible
- Support and convoy indicators provide context without obscuring primary actions
- Unit markers are always visible
- Status indicators appear on top for immediate feedback

---

## 4. Technical Specifications

### 4.0 Configuration-Driven Visual Guidelines

**Important**: All visual specifications described in section 3.4 should be configurable via a configuration file (e.g., `visualization_config.json` or `visualization_config.yaml`). This allows for easy customization and maintenance of visual elements without modifying code.

**Configuration Principles**:
1. **Single Source of Truth**: All visual parameters (sizes, colors, styles) should be defined in one configuration file
2. **Common Variables**: Use shared variables for common elements:
   - **Arrow Specifications**: All arrows (movement, retreat, support, convoy) should use the same base shape and size, differing only in color and line style (solid/dashed/dotted)
   - **Arrowhead Size**: Single variable for all arrowheads (12-15 pixels)
   - **Line Widths**: Common variables for different line types (e.g., `line_width_primary`, `line_width_secondary`)
   - **Unit Marker Size**: Single variable for all unit markers (standard and dislodged)
   - **Circle Sizes**: Common variables for different circle types (hold indicators, support circles, convoy markers)
3. **Color Palette**: Define all colors in a central palette with semantic names (e.g., `color_success`, `color_failure`, `color_convoy`, `power_colors`)
4. **Style Patterns**: Define dash/dot patterns as reusable templates

**Configuration File Structure** (example):
```json
{
  "arrows": {
    "arrowhead_size": 12,
    "arrowhead_base_width": 15,
    "line_width_primary": 3,
    "line_width_secondary": 2,
    "shape": "triangular"
  },
  "colors": {
    "success": "#00FF00",
    "failure": "#FF0000",
    "convoy": "#FFD700",
    "support_defensive": "#90EE90",
    "support_offensive": "#FFB6C1",
    "power_colors": {
      "AUSTRIA": "#c48f85",
      "ENGLAND": "darkviolet",
      ...
    }
  },
  "units": {
    "diameter": 22,
    "border_width": 2,
    "dislodged_border_width": 3,
    "dislodged_offset": [20, 20]
  },
  "line_styles": {
    "solid": {},
    "dashed": {"dash": 4, "gap": 2},
    "dotted": {"dot": 2, "gap": 2}
  }
}
```

**Benefits**:
- Easy adjustment of visual elements from a single configuration file
- Consistent sizing across all similar elements (all arrows same size)
- Simplified maintenance (change once, applies everywhere)
- Theme customization without code changes
- A/B testing of visual styles

**Implementation Note**: The rendering code should read from this configuration file at initialization and use the values throughout. Default values should be provided if the configuration file is missing or incomplete.

### 4.1 Image Format
- **Format**: PNG (lossless compression)
- **Resolution**: Minimum 1920x1080 pixels
- **Color Depth**: 24-bit RGB (8 bits per channel)
- **Alpha Channel**: Supported for overlays
- **File Size**: Target < 2MB per image (with compression)

### 4.2 Map Base
- **Source**: SVG file (`standard.svg` or variant)
- **Rendering**: CairoSVG or similar SVG-to-PNG conversion
- **Coordinate System**: SVG-native coordinates (no scaling)
- **Province Coordinates**: Extracted from SVG path data

### 4.3 Rendering Pipeline
1. Load SVG base map
2. Parse province coordinates
3. Fill provinces with power colors (supply center control)
4. Draw units at province centers
5. Draw order indicators in order of visual priority (see section 3.4.11)
6. Draw conflict markers and dislodged units
7. Add phase information overlay
8. Export to PNG

### 4.4 Performance Requirements
- **Generation Time**: < 2 seconds per map
- **Caching**: Cache generated maps (keyed by state + orders)
- **Memory Usage**: < 100MB per map generation
- **Concurrent Generation**: Support multiple maps in parallel

---

## 5. Map Generation Timing

### 5.1 Movement Phase Sequence
```
1. Initial State Map (before orders)
   ↓
2. Orders Map (after orders submitted, before processing)
   ↓
3. Resolution Map (after adjudication, showing results)
   ↓
4. Final State Map (after phase completes, clean state)
```

### 5.2 Retreat Phase Sequence
```
1. Initial State Map (showing dislodged units)
   ↓
2. Orders Map (showing retreat/disband orders)
   ↓
3. Resolution Map (showing retreat outcomes)
   ↓
4. Final State Map (after retreats processed)
```

### 5.3 Build/Destroy Phase Sequence
```
1. Initial State Map (showing supply center control)
   ↓
2. Orders Map (showing build/destroy orders)
   ↓
3. Resolution Map (showing new/eliminated units)
   ↓
4. Final State Map (after builds/destroys processed)
```

### 5.4 Conditional Generation
- **Skip if empty**: If no orders submitted, skip orders map
- **Skip if no dislodgements**: If no units dislodged, skip retreat phase maps
- **Always generate**: Initial and final maps always generated for phase tracking

---

## 6. Special Cases and Edge Cases

### 6.1 No Orders Submitted
- Generate initial and final maps only
- Show message in map overlay: "No orders submitted"

### 6.2 All Orders Hold
- Orders map shows hold indicators for all units
- Resolution map shows no changes
- Final map identical to initial map

### 6.3 Multiple Support Orders
- **Multiple units supporting same defense**: All support lines visible, overlapping colored circles around defended unit
- **Multiple units supporting same attack**: All support arrows converge at target via supported unit's location
- **Visual clarity**: Ensure overlapping support lines are distinguishable (slightly offset or transparent)

### 6.4 Complex Convoy Chains
- Show full convoy route with all intermediate fleets in convoy color
- Curved path clearly indicating: army → fleet1 → fleet2 → ... → destination
- Each convoying fleet marked as waypoint
- Label convoy chains if multiple exist simultaneously

### 6.5 Multiple Conflicts
- Show all conflict markers clearly
- Use different marker styles if conflicts overlap
- Text labels if necessary to distinguish

### 6.6 Retreat Failures
- Show invalid retreats with red indicators
- Show forced disbands clearly
- Indicate why retreat failed (occupied, invalid province)

### 6.7 Build Constraints
- Show available build locations if power has options
- Indicate why certain locations cannot build (occupied, not home SC)
- Show destroy requirements clearly (more units than SCs)

---

## 7. File Naming Convention

### 7.1 Format
`demo_{counter:02d}_{year}_{season}_{phase}_{type}.png`

**Components**:
- `demo`: Prefix indicating automated demo game
- `{counter}`: Sequential phase counter (2-digit, zero-padded)
- `{year}`: Year (e.g., "1901", "1902")
- `{season}`: Season ("Spring" or "Autumn")
- `{phase}`: Phase name ("Movement", "Retreat", "Builds")
- `{type}`: Map type ("initial", "orders", "resolution", "final")

### 7.2 Examples
```
demo_01_1901_Spring_Movement_initial.png
demo_01_1901_Spring_Movement_orders.png
demo_01_1901_Spring_Movement_resolution.png
demo_01_1901_Spring_Movement_final.png
demo_02_1901_Spring_Builds_initial.png
demo_02_1901_Spring_Builds_orders.png
demo_02_1901_Spring_Builds_resolution.png
demo_02_1901_Spring_Builds_final.png
demo_03_1901_Autumn_Movement_initial.png
```

### 7.3 Text Files
For debugging or fallback, generate corresponding `.txt` files:
- Same naming convention but `.txt` extension
- Contains text representation of game state
- Includes orders and resolution details

---

## 8. Integration Points

### 8.1 Game Engine Integration
- Maps generated via `Map.render_board_png()` methods
- Game state passed to rendering functions
- Orders passed for order visualization

### 8.2 Automated Demo Game
- Maps generated at each phase transition
- Saved to `test_maps/` directory
- Automatic generation during demo game execution

### 8.3 API Integration
- Maps can be generated on-demand via API endpoints
- Caching layer for frequently accessed maps
- Real-time generation for live games

### 8.4 Telegram Bot Integration
- Maps shared via Telegram channels
- Automatic map generation on phase completion
- Map viewing commands for players

---

## 9. Quality Assurance

### 9.1 Visual Quality Checks
- Units clearly visible and identifiable
- Arrows clearly indicate direction
- Colors distinguishable for all powers
- Text readable at target resolution
- Province boundaries clearly defined

### 9.2 Accuracy Requirements
- Unit positions match game state exactly
- Supply center colors match actual control
- Order visualization matches submitted orders exactly
- Support indicators correctly show:
  - Which units are supporting (defensive vs offensive)
  - Which units are being supported
  - Support paths clearly visible
- Convoy routes show complete chain from army to destination
- Resolution visualization matches adjudication results

### 9.3 Performance Checks
- Generation time within limits
- File size within acceptable range
- Memory usage within limits
- Caching working effectively

---

## 10. Future Enhancements

### 10.1 Game Scenario Visualizations (Future Development)
**Note**: Not currently required, but planned for future development:
- **Stalemate Visualization**: Special indicators and overlays showing stalemate lines, locked positions, and game-ending conditions
- **Elimination Visualization**: Visual indicators showing power elimination, last stand scenarios, and victory conditions
- **Victory Visualization**: Special maps showing game completion, winner announcement, and final territory control

### 10.2 Interactive Features
- Clickable provinces showing details
- Hover tooltips for units and orders
- Zoom/pan capabilities
- Animation between states

### 10.3 Enhanced Visualization
- 3D rendering options
- Different map styles/themes
- Customizable color schemes
- Historical replay visualization

### 10.4 Analysis Tools
- Strategic overlay indicators
- Territory control heatmaps
- Movement probability visualizations
- Conflict prediction indicators

---

## References

- [automated_demo_game_spec.md](automated_demo_game_spec.md) - Automated demo game specification
- [game_phases_design.md](game_phases_design.md) - Phase design and visualization rules
- [data_spec.md](data_spec.md) - Data model specification
- [diplomacy_rules.md](diplomacy_rules.md) - Game rules and mechanics

---

**Status**: This specification is current as of 2025-11-03. The visualization system is implemented and operational. Recent enhancements include:
- Enhanced support order visualization with distinct colors for defensive and offensive support
- Improved convoy route visualization with dedicated convoy color
- Clearer visual distinction between order types to reduce map clutter
- Maps generated automatically during demo games and available on-demand via API.

