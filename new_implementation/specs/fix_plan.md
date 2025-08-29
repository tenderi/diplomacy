# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 11. 🔧 **V2 Map Coordinate Fine-Tuning - NEW ISSUE**
- [ ] **Fine-tune V2 map unit positioning** - Units are appearing in approximately correct locations but still have a slight offset to the right and down from their ideal positions.
  - **Current Status**: V2 map coordinate system is functional but units need final positioning adjustment
  - **User Feedback**: "Units are less skewed now, but they are still a bit to the right and to down than where they should be"
  - **Investigation Completed**: Generated test maps with various offset values (-100 to +100 pixels) for analysis
  - **Test Maps Created**: 
    - `test_v2_offset_x-100_y-100.png` (units moved left and up)
    - `test_v2_offset_x-050_y-050.png` (units moved left and up)
    - `test_v2_offset_x-025_y-025.png` (units moved left and up)
    - `test_v2_offset_x+000_y+000.png` (current positioning)
    - `test_v2_offset_x+025_y+025.png` (units moved right and down)
    - `test_v2_offset_x+050_y+050.png` (units moved right and down)
    - `test_v2_offset_x+100_y+100.png` (units moved right and down)
  - **Next Steps**: 
    - Analyze test maps to determine optimal offset values
    - Implement final coordinate adjustment in `v2_map_coordinates.py`
    - Verify units appear in exact correct positions
  - **Priority**: Medium - V2 map is functional but needs precision improvement

## Remaining Tasks (Lower Priority)

### 7. Documentation Updates
- [ ] Update README files with new map generation instructions
- [ ] Document environment variable configuration
- [ ] Add troubleshooting guide for map generation issues

### 8. Infrastructure Improvements
- [ ] Add Docker volume mounting for maps directory
- [ ] Implement map generation monitoring
- [ ] Add map quality validation in CI/CD

### 9. Performance Optimizations
- [ ] Implement map generation caching with Redis
- [ ] Add map generation metrics
- [ ] Optimize SVG processing pipeline

## Status: 🔧 **CRITICAL ISSUE PARTIALLY RESOLVED - V2 MAP COORDINATE SYSTEM NEEDS FINE-TUNING**

The map generation issue has been successfully fixed with comprehensive testing verification including color analysis with 20% black pixel threshold. The telegram bot now uses the original `standard.svg` file and all tests are passing. The Qt environment issue has been resolved using the `QT_QPA_PLATFORM=offscreen` environment variable for headless test execution. All map file references have been cleaned up to use only the original `standard.svg` and `svg.dtd` files. 

**V2 MAP COORDINATE SYSTEM ISSUE RESOLVED**: The V2 map coordinate system has been completely fixed by correcting the viewBox dimensions from the assumed "6591x4535" to the actual "7016x4960". All 70 province coordinates have been recalculated and the scaling factors updated. Units now appear in correct locations and the V2 map is fully functional for gameplay.

### 10. 🔧 **V2 Map Coordinate System Bug - PARTIALLY RESOLVED**
- [x] **Fix V2 map unit placement coordinates** - Units are appearing in completely wrong locations on the V2 map, with Russian units appearing in Galicia (GAL) instead of Warsaw (WAR), and all units appearing systematically skewed downwards.
  - **Root Cause**: The coordinate mapping system for the V2 map was using incorrect viewBox dimensions. The V2 map actually has viewBox="0 0 7016 4960", not the assumed "0 0 6591 4535".
  - **Resolution**: 
    - Updated `v2_map_coordinates.py` with correct viewBox dimensions (7016x4960)
    - Recalculated all 70 province coordinates to match actual V2 map dimensions
    - Fixed scaling factors in `map.py`: x * (2202/7016) ≈ 0.314, y * (1632/4960) ≈ 0.329
    - Removed hardcoded +100 pixel offset that was masking the real issue
  - **Technical Details**:
    - V2 map actual viewBox: 7016x4960 (professional cartographic dimensions)
    - Target output: 2202x1632 pixels
    - Correct scaling: x * (2202/7016) ≈ 0.314, y * (1632/4960) ≈ 0.329
    - Coordinate source: Manual mapping in `v2_map_coordinates.py` (70 provinces)
    - Rendering system: Confirmed working with correct coordinates
  - **Impact**: V2 map can now be used for gameplay with units appearing in correct provinces
  - **Status**: PARTIALLY RESOLVED - V2 map coordinate system functional but needs fine-tuning
  - **Verification**: 
    - Test script `test_v2_map_fixed.py` passes successfully
    - All existing tests continue to pass (68 passed, 4 skipped)
    - Units now appear in correct locations (WAR in eastern Europe, MOS in far east, LON in western Europe)
  - **Remaining Issue**: Units are still slightly offset to the right and down from their ideal positions
    - **User Feedback**: "Units are less skewed now, but they are still a bit to the right and to down than where they should be"
    - **Investigation**: Generated test maps with various offset values (-100 to +100 pixels) for analysis
    - **Next Steps**: Analyze test maps to determine optimal offset values and implement final coordinate adjustment 