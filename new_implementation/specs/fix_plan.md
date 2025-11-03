# Fix Plan - Actionable Items

## Overview

This document contains actionable implementation tasks and fixes for the Diplomacy game engine.

## New Feature: Supply Center Persistence

### Overview

Implement Diplomacy rule: **Supply centers remain under control of a power even after the unit leaves, until another power moves a unit into that province.**

### Requirements

1. **Control Persistence**
   - When an army/fleet leaves a supply center province, that power retains control
   - Control only changes when another power successfully moves a unit into the province
   - This affects build/destroy calculations at end of Fall season

2. **Visualization**
   - Map coloring should show supply center control (not just unit positions)
   - Supply centers controlled but not occupied should be colored appropriately
   - Both occupied and unoccupied controlled supply centers should be visible

3. **Build/Destroy Logic**
   - Supply center count = units in supply centers + controlled but unoccupied supply centers
   - Powers can build if `controlled_supply_centers > units`
   - Powers must destroy if `units > controlled_supply_centers`

### Implementation Details

#### 1. Game Engine Changes (`src/engine/game.py`)

**Current Behavior:**
- `_update_supply_center_ownership()` only considers units currently occupying supply centers
- Control is lost immediately when unit leaves

**Required Changes:**
- Track previous supply center control (persist across turns)
- Only update control when:
  - A unit successfully moves into a supply center (new power takes control)
  - A unit holds in a supply center (maintains control)
- If a supply center becomes empty but was previously controlled, maintain that control

**Key Methods to Modify:**
- `_update_supply_center_ownership()`: Persist control when units leave
- `_process_movement_phase()`: Update control only when units successfully move into supply centers

#### 2. Data Model Changes (`src/engine/data_models.py`)

**PowerState additions:**
- Already has `controlled_supply_centers` list
- Need to ensure this persists correctly when units move away

**GameState additions:**
- May need to track "last occupier" for supply centers if not already tracked
- Ensure `controlled_supply_centers` is correctly maintained

#### 3. Visualization Changes (`src/engine/map.py`)

**Current Behavior:**
- `_color_provinces_by_power_with_transparency()` uses `supply_center_control` parameter
- Colors provinces based on unit positions primarily

**Required Changes:**
- Ensure `supply_center_control` includes both occupied and unoccupied controlled centers
- Unoccupied controlled supply centers should be colored with appropriate transparency
- Visual distinction between occupied vs. unoccupied but controlled centers (optional enhancement)

#### 4. Map Generation Updates

**Files to update:**
- `demo_perfect_game.py`: Ensure supply center control is passed correctly to map generation
- `server/api.py`: Ensure supply center control in game state is correctly calculated and returned

### Testing Strategy

1. **Unit Test Cases:**
   - Unit moves from supply center A to province B (non-SC) → A remains controlled
   - Unit moves from supply center A to supply center C → A remains controlled, C changes control
   - Enemy unit successfully moves into controlled but empty supply center → control changes
   - Build phase: Power has 5 controlled SCs, 3 units → can build 2 units

2. **Integration Test:**
   - Create scenario where France moves A PAR to BUR (PAR is supply center)
   - Verify PAR remains French-controlled even when empty
   - Move another power's unit to PAR → verify control changes
   - Check build/destroy calculations work correctly

3. **Visualization Test:**
   - Generate map with unoccupied but controlled supply center
   - Verify province is colored appropriately
   - Verify control is visible in all map types (initial, orders, resolution, final)

### Success Criteria

1. ✅ Supply centers persist control when units leave
2. ✅ Control only changes when another power successfully moves in
3. ✅ Build/destroy calculations use persistent control (not just unit positions)
4. ✅ Maps correctly visualize controlled but unoccupied supply centers
5. ✅ All existing tests pass
6. ✅ New test cases pass for control persistence

### Implementation Notes

- This is a standard Diplomacy rule, so implementation should match official game behavior
- Control persistence is critical for build/destroy phase calculations
- Visualization helps players understand why they can build even if they don't have units in all their controlled SCs
