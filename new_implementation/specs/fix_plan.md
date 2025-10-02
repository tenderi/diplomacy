# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 1. ✅ **Bot Map File Path Error - RESOLVED**
- [x] **Fixed incorrect map file path reference** - Bot was trying to access non-existent `standard_fixed.svg` instead of `standard.svg`
  - **Root Cause**: Hardcoded reference to `standard_fixed.svg` in `telegram_bot.py` line 43
  - **Error**: `<urlopen error [Errno 2] No such file or directory: '/opt/diplomacy/maps/standard_fixed.svg'>`
  - **Solution**: Changed default path from `maps/standard_fixed.svg` to `maps/standard.svg` in `generate_default_map()` function
  - **Verification**: ✅ Bot now successfully generates default map (751KB PNG output)
  - **Files Modified**: `new_implementation/src/server/telegram_bot.py`
  - **Status**: ✅ **FULLY RESOLVED** - Bot can now generate default map without errors

### 2. ✅ **Database Migration Issue - RESOLVED**
- [x] **Fixed missing database migrations in deployment** - Server was failing with "relation 'users' does not exist" error
  - **Root Cause**: Database migrations were not being run during deployment, causing missing tables
  - **Error**: `psycopg2.errors.UndefinedTable: relation "users" does not exist`
  - **Solution**: 
    - Added `alembic upgrade head` to `user_data.sh` for initial deployment
    - Modified `deploy_app.sh` to run migrations when source code changes (not just alembic changes)
    - Ensures database tables are created before services start
  - **Files Modified**: 
    - `new_implementation/terraform/single-ec2/user_data.sh` (added migration step)
    - `new_implementation/terraform/single-ec2/deploy_app.sh` (enhanced migration logic)
  - **Status**: ✅ **FULLY RESOLVED** - Database migrations now run during deployment

### 3. ✅ **Standard Map Province Coloring Coordinate Alignment - FINALLY RESOLVED**
- [x] **Fix province coloring coordinate alignment** - Province coloring areas are now perfectly aligned with unit coordinates and background map is visible.
  - **Root Cause Identified**: Fundamental coordinate system mismatch between unit placement and province coloring:
    - **Unit coordinates**: Used `jdipNS` coordinates from SVG file
    - **Province coloring**: Used SVG path coordinates in different coordinate system
    - **Transform offset**: SVG paths affected by transform group, but actual offset was different than expected
  - **Solution Implemented**: 
    - **Updated `get_svg_province_coordinates`**: Now uses `jdipNS` coordinates consistently for both units and province coloring
    - **Fixed province coloring**: Updated `_color_provinces_by_power` to use SVG paths with correct coordinate transform
    - **Fine-tuned alignment**: Through iterative testing, found perfect offset values:
      - **X offset**: 195 (fine-tuned from original 251)
      - **Y offset**: 169 (fine-tuned from original 174)
    - **Added province labels**: Province names displayed on colored areas for better visibility
  - **Technical Details**:
    - **Coordinate system**: Both units and province coloring now use `jdipNS` coordinates
    - **Transform applied**: `Map._fill_svg_path_with_transform(draw, path_data, solid_color, power_color, 195, 169)`
    - **Transparency**: 25% opacity achieved using separate overlay layer with proper alpha compositing (no checkerboard issues)
    - **Labels**: White text with black outline for province names
    - **Full starting units**: All 22 standard Diplomacy starting units (3-4 per power) display correctly
  - **Verification**: 
    - ✅ Unit placement works correctly with full starting units (3-4 per power)
    - ✅ Province coloring aligns perfectly with unit positions
    - ✅ Province names are visible on colored areas
    - ✅ Background map is clearly visible (no checkerboard transparency issues)
    - ✅ All powers display correctly with proper colors
    - ✅ True transparency implemented using separate overlay layer with 25% opacity
    - ✅ Province names and supply points remain clearly visible through colored areas
  - **Files Modified**: 
    - `new_implementation/src/engine/map.py` (coordinate handling and province coloring logic updated)
  - **Status**: ✅ **FULLY RESOLVED** - Perfect coordinate alignment achieved with fine-tuned transforms

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

## Status: ✅ **STANDARD MAP FULLY FUNCTIONAL WITH PERFECT COORDINATE ALIGNMENT AND VISIBLE BACKGROUND**

The standard map is now fully functional with:
- ✅ Units rendering correctly
- ✅ Province coloring working and perfectly aligned
- ✅ Background map visible through province coloring
- ✅ All scaling removed from the system
- ✅ PNG output matching SVG size exactly
- ✅ SVG zoom factor removed
- ✅ Coordinate system mismatch resolved with inverse transform
- ✅ Transparency optimized for visibility

**FULLY RESOLVED**: Province coloring areas are now perfectly aligned with unit coordinates and the background map is visible through the province coloring. The coordinate system mismatch between underscore-prefixed paths (offset by translate(-195 -170)) and non-underscore paths has been resolved by applying inverse transform compensation.

**CURRENT STATUS**: Standard map is production-ready with all coordinate alignment and transparency issues resolved. 