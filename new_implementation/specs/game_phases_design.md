# Game Phases Design for Diplomacy Python Implementation

## Overview
This document outlines the design for supporting multiple game phases in the Diplomacy engine: Movement, Retreat, and Adjustment (Build/Disband). The goal is to achieve full rules compliance and enable a complete play experience.

---

## 1. Phase Model
- The `Game` class will track the current phase using a new attribute, e.g., `self.phase`.
- Phases:
  - `movement`: Players submit movement, support, and convoy orders.
  - `retreat`: Players with dislodged units submit retreat or disband orders.
  - `adjustment`: Players submit build or disband orders (typically after Fall turn).
- The phase will be included in the game state output for API/UI.

## 2. Phase Transitions
- **Movement → Retreat**: After resolving movement, if any units are dislodged, enter the retreat phase. Only affected players submit retreat/disband orders.
- **Retreat → Adjustment**: After all retreats are resolved, if it's the end of a Fall turn, enter the adjustment phase. Otherwise, return to movement.
- **Adjustment → Movement**: After all builds/disbands are processed, increment the year/turn and return to movement.

## 3. Order Types
- **Movement Phase**: Move, Hold, Support, Convoy orders (existing).
- **Retreat Phase**: Retreat (e.g., `A PAR R BUR`), Disband (e.g., `A PAR D`).
- **Adjustment Phase**: Build (e.g., `A PAR B` or `F MAR B`), Disband (e.g., `A PAR D`).
- The order parser and validator will be extended to support these new order types.

## 4. State Changes
- The game state will include:
  - `phase`: Current phase name.
  - `pending_retreats`: Dict of dislodged units and valid retreat options.
  - `pending_adjustments`: Dict of powers and required builds/disbands.
  - `orders`: Orders for the current phase.
- The state will be updated after each phase resolution.

## 5. API Integration
- The server API will allow order submission for the current phase only.
- Endpoints will validate that submitted orders match the expected type for the phase.
- Notifications will be sent to affected players when a new phase begins or when their input is required.

## 6. Refactoring Plan
1. Add `phase` attribute and phase logic to `Game`.
2. Refactor `process_turn` to handle phase transitions and call new methods for retreat/adjustment resolution.
3. Extend order parsing/validation for retreat/build/disband orders.
4. Update game state output and API to reflect phase and pending actions.
5. Add/expand tests for all phase transitions and edge cases.

## 7. Map Visualization Rules

### 7.1 Supply Center Coloring
- **Persistent Control**: Supply centers maintain their power's color based on control, not unit presence
- **Unit Override**: When a unit occupies a supply center, the province shows the occupying unit's power color
- **Empty Supply Centers**: Unoccupied supply centers show the controlling power's color
- **Implementation**: Uses `GameState.get_supply_centers()` to determine control, passed to map rendering methods

### 7.2 Dislodged Unit Visualization
- **Visibility**: Dislodged units remain visible during resolution and retreat phases
- **Positioning**: Dislodged units are drawn offset (+20, +20 pixels) from their original province center
- **Styling**: 
  - Red border instead of black to indicate dislodged status
  - "D" marker in top-right corner of unit circle
  - Same power color as original unit
- **Province Coloring**: Original province remains colored by original controller until retreat phase completes

### 7.3 Support Order Visualization
- **Resolution Maps**: Support orders that contributed to successful attacks are visible
- **Order Maps**: All support orders are shown with arrows/indicators
- **Styling**: Support arrows use dashed lines to distinguish from movement arrows

### 7.4 Phase-Aware Coloring
- **Resolution Phase**: Provinces colored by original controller, dislodged units visible
- **Retreat Phase**: Same as resolution phase
- **Post-Retreat**: Province coloring updates to new controller after retreat resolution
- **Implementation**: Current phase passed to coloring logic for appropriate behavior

### 7.5 Visual Conflict Resolution
- **Clear Attribution**: Support orders visible so players understand why units were dislodged
- **Retreat Options**: Dislodged units clearly marked with retreat options available
- **Province Control**: Clear visual indication of who controls each province
- **Phase Context**: Map shows appropriate information for current game phase

## 8. Testing
- Unit and integration tests will cover:
  - Movement → Retreat → Adjustment → Movement cycle
  - Valid/invalid retreat and build/disband orders
  - Edge cases (no valid retreats, forced disbands, simultaneous builds/disbands)
  - State output and API correctness

---

## References
- [diplomacy_rules.md](diplomacy_rules.md)
- [engine_game_spec.md](engine_game_spec.md)
- [fix_plan.md](fix_plan.md) 