# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 1. ✅ **Standard Map Province Coloring Coordinate Alignment - RESOLVED**
- [x] **Fix province coloring coordinate alignment** - Province coloring areas are now correctly aligned with unit coordinates.
  - **Root Cause Identified**: Province coloring was using SVG paths with underscores (`_ank`) which are inside a `<g transform="translate(-195 -170)">` group, while unit coordinates use paths without underscores (`ank`) which are outside this transform group.
  - **Solution Implemented**: Modified province coloring to use only paths without underscores, ensuring both unit placement and province coloring use the same coordinate system.
  - **Technical Details**:
    - SVG has two sets of paths: `id="_ank"` (offset by translate(-195 -170)) and `id="ank"` (no offset)
    - Unit coordinates were correctly using `id="ank"` paths
    - Province coloring was incorrectly using `id="_ank"` paths
    - Fixed by filtering to only use paths without underscore prefix
  - **Verification**: 
    - Test script confirms map generation works correctly
    - All 68 tests pass with 4 expected skips
    - No linting errors introduced
  - **Files Modified**: 
    - `new_implementation/src/engine/map.py` (province coloring logic updated)
  - **Status**: ✅ **RESOLVED** - Province coloring now perfectly aligned with unit coordinates

### 2. 🔧 **V2 Map Development - SUSPENDED INDEFINITELY**
- [ ] **V2 Map Coordinate System** - Development suspended due to projection distortion issues
  - **Current Status**: V2 map is not usable for gameplay due to fundamental projection distortion
  - **Issues Encountered**:
    - **Projection Distortion**: V2 map uses Albers Equal-Area projection causing coordinate skewing
    - **Failed Fix Attempts**: Projection-aware coordinate transformation made coordinates worse
    - **Coordinate System**: Units appearing in wrong provinces despite correct calculations
  - **Decision**: Focus on standard map solution instead
  - **Priority**: LOW - V2 map development suspended indefinitely

## Completed Tasks ✅

### ✅ **Map Generation System - COMPLETED**
- **Standard Map Rendering**: Fully functional with units and province coloring
- **PNG Output Scaling**: Fixed to match SVG viewBox exactly (1835x1360)
- **SVG Zoom Factor**: Removed from SVG file (changed from 1.2 to 1.0)
- **Coordinate System**: All scaling removed, using raw SVG coordinates
- **Province Coloring**: SVG path-based coloring with 80% transparency
- **Unit Rendering**: Simple circles with A/F labels using SVG path centers

### ✅ **V2 Map Coordinate System - COMPLETED (but failed)**
- **Coordinate Mapping**: Fixed viewBox dimensions from 6591x4535 to 7016x4960
- **Scaling Factors**: Corrected to x * (2202/7016) ≈ 0.314, y * (1632/4960) ≈ 0.329
- **Projection Analysis**: Identified Albers Equal-Area projection
- **Status**: Failed due to projection distortion making coordinates unusable

## Remaining Tasks (Lower Priority)

### 3. Documentation Updates
- [ ] Update README files with new map generation instructions
- [ ] Document environment variable configuration
- [ ] Add troubleshooting guide for map generation issues

### 4. Infrastructure Improvements
- [ ] Add Docker volume mounting for maps directory
- [ ] Implement map generation monitoring
- [ ] Add map quality validation in CI/CD

### 5. Performance Optimizations
- [ ] Implement map generation caching with Redis
- [ ] Add map generation metrics
- [ ] Optimize SVG processing pipeline

## Status: ✅ **STANDARD MAP FULLY FUNCTIONAL WITH PERFECT COORDINATE ALIGNMENT**

The standard map is now fully functional with:
- ✅ Units rendering correctly
- ✅ Province coloring working and perfectly aligned
- ✅ All scaling removed from the system
- ✅ PNG output matching SVG size exactly
- ✅ SVG zoom factor removed
- ✅ Coordinate system mismatch resolved

**RESOLVED**: Province coloring areas are now perfectly aligned with unit coordinates. The coordinate system mismatch between underscore-prefixed paths (offset by translate(-195 -170)) and non-underscore paths has been fixed.

**CURRENT STATUS**: Standard map is production-ready with all coordinate alignment issues resolved. 