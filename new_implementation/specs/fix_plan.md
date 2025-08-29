# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 1. 🚨 **Standard Map Province Coloring Coordinate Alignment - ACTIVE ISSUE**
- [ ] **Fix province coloring coordinate alignment** - Province coloring areas are approximately the right size but located to the right and down from where they should be.
  - **Current Status**: Province coloring is working but coordinates are still misaligned
  - **User Feedback**: "The areas are now approximately the right size, but they are located to the right and down"
  - **Root Cause Investigation Completed**: 
    - **PNG Output Scaling**: Initially PNG was hardcoded to 2202x1632 (1.2x larger than SVG viewBox 1835x1360)
    - **SVG Zoom Factor**: Found `<jdipNS:ZOOM factor="1.2">` in SVG file causing coordinate skewing
    - **Coordinate System Mismatch**: SVG paths vs jdipNS coordinates were in different systems
  - **Solutions Attempted**:
    1. ✅ **PNG Output Scaling Fixed**: Changed PNG output from 2202x1632 to 1835x1360 (exact SVG size)
    2. ✅ **SVG Zoom Factor Fixed**: Changed zoom factor from 1.2 to 1.0 in SVG file
    3. ✅ **All Explicit Scaling Removed**: Removed all coordinate scaling from map.py
    4. ✅ **Province Coloring Implemented**: SVG path-based province coloring with 80% transparency
  - **Current Technical State**:
    - PNG output: 1835x1360 (exact SVG viewBox size)
    - SVG zoom factor: 1.0 (no zoom)
    - Units: Raw SVG path centers (no scaling)
    - Province coloring: Raw SVG coordinates (no scaling)
    - Transparency: 80% (allows background to show through)
  - **Remaining Issue**: Province coloring areas still offset to the right and down
  - **Next Steps**:
    1. Investigate if there are remaining coordinate system differences
    2. Check if SVG paths and unit coordinates use different reference systems
    3. Implement coordinate alignment fix for province coloring
    4. Test with various provinces to ensure consistent alignment
  - **Priority**: HIGH - Standard map is primary solution but needs final coordinate alignment
  - **Files Modified**: 
    - `new_implementation/src/engine/map.py` (all scaling removed)
    - `new_implementation/maps/standard.svg` (zoom factor fixed)

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

## Status: 🟡 **STANDARD MAP FUNCTIONAL BUT NEEDS FINAL COORDINATE ALIGNMENT**

The standard map is now fully functional with:
- ✅ Units rendering correctly
- ✅ Province coloring working
- ✅ All scaling removed from the system
- ✅ PNG output matching SVG size exactly
- ✅ SVG zoom factor removed

**REMAINING ISSUE**: Province coloring areas are offset to the right and down from their correct positions. This is the final coordinate alignment issue that needs to be resolved.

**NEXT PRIORITY**: Fix the province coloring coordinate alignment to ensure provinces are colored in exactly the right locations. 