# Map Module Specification

## Purpose
Handles map representation, loading, validation, and visualization for standard and variant maps. Provides comprehensive order visualization to show unit movements, holds, supports, convoys, builds, and destructions.

## Core API
- `Map`: Class for representing the board, locations, and adjacency.
  - Methods:
    - `__init__(self, map_name: str = 'standard')`
    - `get_locations(self) -> list[str]`
    - `get_adjacency(self, location: str) -> list[str]`
    - `validate_location(self, location: str) -> bool`

## Visualization API
- `Map`: Enhanced with order visualization capabilities.
  - Methods:
    - `render_board_png_with_orders(svg_path: str, units: dict, orders: dict, phase_info: dict, output_path: str = None) -> bytes`
    - `render_board_png_with_moves(svg_path: str, units: dict, moves: dict, phase_info: dict, output_path: str = None) -> bytes`

## Order Visualization Features

### 1. Movement Orders
- **Visual**: Arrow from source province to destination province
- **Color**: Power color of the moving unit
- **Style**: Solid arrow with arrowhead pointing to destination
- **Failed Moves**: Dashed arrow with red color to indicate failure
- **Bounced Moves**: Dashed arrow with orange color to indicate bounce

### 2. Hold Orders
- **Visual**: Circle around the unit
- **Color**: Power color of the holding unit
- **Style**: Solid circle outline (2-3px width)
- **Failed Holds**: Dashed circle outline with red color

### 3. Convoy Orders
- **Visual**: Arrow from convoying fleet through convoy chain to destination
- **Color**: Power color of the convoying fleet
- **Style**: Curved arrow following convoy route
- **Chain Display**: Show all fleets in convoy chain with connecting lines
- **Failed Convoys**: Dashed arrow with red color

### 4. Support Orders
- **Visual**: Circle around supporting unit + arrow to supported area
- **Supporting Unit**: Circle outline in power color
- **Support Arrow**: Arrow from supporting unit to target province
- **Style**: Solid circle + solid arrow
- **Failed Support**: Dashed circle + dashed arrow with red color

### 5. Build Orders
- **Visual**: Glowing circle around new unit location
- **Color**: Power color with enhanced brightness/glow effect
- **Style**: Animated glow effect or bright halo around unit
- **Failed Builds**: Red cross over build location

### 6. Destroy Orders
- **Visual**: Red cross (X) over destroyed unit
- **Color**: Red cross regardless of power color
- **Style**: Bold red X overlay on unit position
- **Auto-destructions**: Same red X for units destroyed due to insufficient supply centers

## Data Structures

### Orders Dictionary Format
```python
orders = {
    "power_name": [
        {
            "type": "move|hold|support|convoy|build|destroy",
            "unit": "A PAR",  # or "F ENG"
            "target": "BUR",  # destination province
            "via": ["ENG", "NTH"],  # convoy route (for convoy orders)
            "supporting": "A BUR - HOL",  # supported move (for support orders)
            "status": "success|failed|bounced",  # resolution status
            "reason": "cut_support|convoy_disrupted|etc"  # failure reason
        }
    ]
}
```

### Moves Dictionary Format (Alternative)
```python
moves = {
    "power_name": {
        "successful": ["A PAR - BUR", "F ENG - NTH"],
        "failed": ["A BUR - HOL"],  # with failure reasons
        "bounced": ["F NTH - HEL"],
        "holds": ["A MUN"],
        "supports": ["A BUR S A PAR - HOL"],
        "convoys": ["F ENG C A PAR - HOL"],
        "builds": ["BUILD A PAR"],
        "destroys": ["DESTROY A MUN"]
    }
}
```

## Visual Design Specifications

### Arrow Styles
- **Successful Moves**: Solid arrow, power color, 3px width
- **Failed Moves**: Dashed arrow, red color, 2px width
- **Bounced Moves**: Dashed arrow, orange color, 2px width
- **Convoy Routes**: Curved arrow, power color, 2px width
- **Support Arrows**: Solid arrow, power color, 2px width

### Circle Styles
- **Hold Orders**: Solid circle, power color, 2px width
- **Support Units**: Solid circle, power color, 2px width
- **Build Locations**: Glowing circle, enhanced power color, 4px width
- **Failed Orders**: Dashed circle, red color, 2px width

### Cross Styles
- **Destroyed Units**: Bold red X, 4px width, centered on unit
- **Failed Builds**: Red X over build location

## Implementation Requirements

### SVG Path Integration
- All visual elements must be drawn as SVG paths for scalability
- Arrow paths should follow natural curves between provinces
- Circles should be centered on unit positions
- Crosses should overlay unit positions

### Color Management
- Use existing power color scheme
- Failed orders always use red/orange regardless of power
- Glow effects for builds should enhance existing colors
- Ensure sufficient contrast for visibility

### Performance Considerations
- Cache SVG path calculations for common routes
- Optimize drawing order (background → units → orders → overlays)
- Support both high-resolution and standard resolution outputs

## Example Usage

### Basic Order Visualization
```python
from engine.map import Map

map_obj = Map('standard')

# Render map with orders
orders = {
    "FRANCE": [
        {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
        {"type": "hold", "unit": "A MAR", "status": "success"},
        {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"}
    ]
}

img_bytes = map_obj.render_board_png_with_orders(
    svg_path="maps/standard.svg",
    units={"FRANCE": ["A PAR", "A MAR", "F BRE"]},
    orders=orders,
    phase_info={"turn": 1, "season": "Spring", "phase": "Movement"}
)
```

### Advanced Visualization with Resolution
```python
# Show both successful and failed orders
orders = {
    "GERMANY": [
        {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
        {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
        {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "failed", "reason": "convoy_disrupted"}
    ]
}
```

## Test Cases
- Test loading standard and variant maps
- Test location and adjacency queries
- Test location validation
- Test order visualization rendering
- Test failed order visualization
- Test convoy chain visualization
- Test support order visualization
- Test build/destroy visualization
- Test color consistency across order types
- Test performance with large numbers of orders

## Future Enhancements
- Animation support for order resolution sequence
- Interactive order editing on map
- Order history visualization
- Customizable visual styles
- Export to different formats (SVG, PDF)

## Improvements (July 2025)
- Classic map now includes more provinces and adjacencies, with symmetric adjacency enforcement.
- Map initialization is structured for easy extension and future variant support.
- Tests cover invalid adjacency, all supply centers, and symmetric adjacency for land provinces.
- All map queries are strictly validated.
- Added comprehensive order visualization system for enhanced gameplay understanding.

---

Update this spec as the module evolves.
