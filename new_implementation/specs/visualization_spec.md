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
**Content**:
- All current unit positions
- Movement arrows (solid lines, power-colored)
- Support order indicators:
  - **Defensive support**: Light green dashed lines from supporter to defending unit, with defending unit circled in supporter's power color
  - **Offensive support**: Light pink/sky blue dashed arrows: supporter → supported unit location → attack target
- Convoy route indicators (curved gold/orange arrows: convoyed army → convoying fleet(s) → destination)
- Hold indicators (circles or markers around holding units)
- Retreat arrows (if in retreat phase)
- Build markers (if in build phase)
- Destroy markers (if in destroy phase)

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_orders.png`
**Example**: `demo_01_1901_Spring_Movement_orders.png`

### 2.3 Resolution Map
**Purpose**: Show order adjudication results, conflicts, and outcomes
**Content**:
- Final unit positions after adjudication
- Successful moves (green checkmark or highlight)
- Failed moves (red X or highlight)
- Dislodged units (offset position with red border and "D" marker)
- Conflict markers (battle indicators)
- Support cut indicators
- Standoff indicators (equal strength conflicts)

**Visual Elements**:
- **Successful Orders**: Green checkmark or highlight
- **Failed Orders**: Red X or highlight with reason (if space permits)
- **Dislodged Units**: Drawn offset (+20, +20 pixels) with red border and "D" marker
- **Conflicts**: Special markers showing battle locations
- **Standoffs**: Indicator showing equal strength (beleaguered garrison)
- **Support Cuts**: Visual indication when support was disrupted
- **Bounces**: Indicators showing units that bounced back

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_resolution.png`
**Example**: `demo_01_1901_Spring_Movement_resolution.png`

### 2.4 Final State Map
**Purpose**: Show stable game state after phase completion
**Content**:
- All final unit positions
- Updated supply center control (if changed)
- Phase information overlay showing next phase
- No order indicators (clean state view)

**Visual Elements**:
- Units in final positions
- Provinces colored by current controller
- Supply centers shown in owner's color
- Clean presentation suitable for archival

**File Naming**: `demo_{counter:02d}_{year}_{season}_{phase}_final.png`
**Example**: `demo_01_1901_Spring_Movement_final.png`

---

## 3. Visual Element Specifications

### 3.1 Unit Representation
**Armies**:
- Circle with "A" label
- Colored by power (see power colors below)
- Size: ~20-25 pixels diameter
- Black border (or red if dislodged)

**Fleets**:
- Circle with "F" label
- Colored by power
- Size: ~20-25 pixels diameter
- Black border (or red if dislodged)

**Dislodged Units**:
- Same as above but:
  - Red border instead of black
  - Offset position (+20, +20 pixels from province center)
  - "D" marker in top-right corner
  - Visible during Resolution and Retreat phases only

**Power Colors**:
- **AUSTRIA**: `#c48f85` (light brown)
- **ENGLAND**: `darkviolet` (purple)
- **FRANCE**: `royalblue` (blue)
- **GERMANY**: `#a08a75` (gray-brown)
- **ITALY**: `forestgreen` (green)
- **RUSSIA**: `#757d91` (blue-gray)
- **TURKEY**: `#b9a61c` (yellow-brown)

### 3.2 Order Visualization Color Scheme

**Purpose**: Distinct colors reduce visual clutter and clearly distinguish order types.

**Color Assignments** (detailed specifications in section 3.3):
- **Movement Arrows**: Power colors (solid lines, 3-4px width) - primary action, highest visual priority
- **Defensive Support**: Light green `#90EE90` (lines) + supporting unit's power color (defender circles)
- **Offensive Support**: Light pink `#FFB6C1` or sky blue `#87CEEB` (dashed arrows)
- **Convoy Routes**: Gold `#FFD700` or dark orange `#FF8C00` (curved lines)
- **Hold Indicators**: Power-colored borders (2-3px dashed border)
- **Retreat Arrows**: Power color for valid, red for invalid (dotted, 2-3px width)

### 3.3 Order Visualization Details

#### Movement Orders
- **Arrow Type**: Solid line with arrowhead
- **Color**: Power color of unit making move (unchanged from current implementation)
- **Width**: 3-4 pixels
- **Style**: Straight line from origin to destination center
- **Status Indicators**:
  - Success: Green checkmark at arrow tip
  - Failure: Red X at arrow tip
  - Bounce: Curved arrow showing return to origin

#### Hold Orders
- **Indicator**: Circle around unit (2-3 pixel border)
- **Color**: Power color of unit
- **Style**: Dashed or dotted border
- **Label**: Optional "H" text near unit
- **Note**: If unit is supported (hold support), it will have an additional colored circle as specified in defensive support above

#### Support Orders

**Defensive Support (Hold Support)**:
- **Visual Elements**:
  - Dashed line from supporting unit to the defending unit (light green `#90EE90`)
  - Circle around the defending unit in the supporting unit's power color (3-4px border)
- **Purpose**: Clearly show which unit is providing defensive support to a unit holding
- **Width**: 2-3 pixels (support line)
- **Support Cut**: Red X through support line if cut

**Offensive Support (Move Support)**:
- **Visual Elements**:
  - Dashed arrow path: supporting unit → supported unit's province → attack target
  - Color: Light pink `#FFB6C1` or sky blue `#87CEEB` (distinct from defensive support)
- **Purpose**: Show support is flowing through the attacking unit to the target province
- **Width**: 2-3 pixels
- **Support Cut**: Red X through support line if cut

#### Convoy Orders
- **Visual Elements**:
  - Curved arrow starting from convoyed army
  - Path: convoyed army → first convoying fleet → subsequent convoying fleets → destination province
  - Dedicated convoy color: `#FFD700` (gold) or `#FF8C00` (dark orange)
  - Circles/markers around convoying fleets in convoy color
- **Style**: Curved path showing complete convoy chain with each fleet as waypoint
- **Width**: 2-3 pixels
- **Purpose**: Clearly show convoy route distinct from movement and support orders

#### Retreat Orders
- **Arrow Type**: Dotted line with arrowhead
- **Color**: Power color (red if invalid retreat)
- **Width**: 2-3 pixels
- **Style**: Dotted line from dislodged unit to retreat destination
- **Failure**: Red X if retreat to occupied province

#### Build Orders
- **Indicator**: Green circle or plus sign (+) at build location
- **Color**: Green with power-colored border
- **Size**: ~15-20 pixels
- **Label**: Unit type (A/F) inside marker
- **Style**: Prominent marker clearly showing new unit location

#### Destroy Orders
- **Indicator**: Red X or circle with X
- **Color**: Red with power-colored border
- **Size**: ~15-20 pixels
- **Style**: Prominent marker clearly showing destroyed unit location

### 3.4 Supply Center Visualization
**Ownership**:
- Province filled with controlling power's color (light tint, ~30% opacity)
- Border highlighted if supply center

**Unoccupied Supply Centers**:
- Filled with owner's color (lighter tint)
- Unit placement override: If unit occupies, province shows unit's power color

**Control Changes**:
- In resolution maps, show previous owner (faded) and new owner (solid)
- Transition indicators if ownership changes

### 3.5 Conflict Markers
**Battle Indicators**:
- Special marker at conflict location
- Show attacking powers and defenders
- Strength indicators if possible (numbers)

**Standoff Indicators**:
- Special marker showing equal strength
- "Standoff" label or symbol
- Beleaguered garrison indicator

**Bounce Indicators**:
- Curved arrow showing units bouncing back
- Multiple bounce markers if multiple units bounced

### 3.6 Phase Information Overlay
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

## 4. Technical Specifications

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
5. Draw order indicators in order of visual priority:
   a. Hold indicators (underneath, so other indicators appear on top)
   b. Support lines and circles (defensive and offensive)
   c. Convoy routes
   d. Movement arrows (on top, as primary actions)
6. Draw conflict markers and dislodged units
7. Add phase information overlay
8. Export to PNG

**Visual Layer Order**: Ensures movement arrows remain clearly visible while support and convoy indicators provide context without obscuring primary actions

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

