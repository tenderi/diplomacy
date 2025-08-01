# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 1. ~~Test Failures - Telegram Bot Waiting List~~ ✅ COMPLETED
- [x] **Fix telegram bot waiting list tests** - 3 tests failing in `test_telegram_waiting_list.py` due to incorrect monkeypatching. The tests are trying to patch `server.telegram_bot.api_post` but the function is defined in the same module, so the patching isn't working. The `api_post` function is trying to connect to a real server at `http://localhost:8000` instead of using the mock.
  - **Solution**: Refactored `process_waiting_list` to accept an `api_post_func` parameter for dependency injection, allowing tests to pass a mock function directly. Updated all tests to use this new parameter instead of monkeypatching.

### 2. ~~Code Quality Issues~~ ✅ COMPLETED
- [x] **Fix linting issues** - Multiple Ruff linting errors in telegram_bot.py and other files
  - **Solution**: Applied Ruff auto-fixes and manual corrections for all linting issues

### 3. ~~Map Generation Issue - Black Pictures~~ ✅ COMPLETED
- [x] **Fix map generation producing black pictures** - The `standard.svg` file has CSS styles that cairosvg can't process, causing black pictures
  - **Root Cause**: 
    - Telegram bot was using Docker absolute path `/opt/diplomacy/maps/standard.svg` which doesn't exist locally
    - CSS styles in SVG file not being processed by cairosvg
    - Large black rectangle covering the entire map
  - **Solution**: 
    - Updated telegram bot to use configurable map paths via `DIPLOMACY_MAP_PATH` environment variable
    - Changed default path to use `maps/standard_fixed.svg` which has CSS styles removed
    - Verified that `standard_fixed.svg` has both CSS styles and problematic black rectangle removed
    - Updated all map generation functions to use the fixed SVG file

### 4. ~~Map Performance Issue~~ ✅ COMPLETED
- [x] **Fix map generation performance** - Map generation is expensive and should be cached
  - **Solution**: Implemented caching for map generation with configurable TTL

### 5. ~~Start.sh Script Review~~ ✅ COMPLETED
- [x] **Review start.sh script** - Ensure it properly handles BOT_ONLY mode and other configurations
  - **Solution**: Verified start.sh script properly handles BOT_ONLY mode and environment variables

### 6. ~~Qt/Display Environment Issue~~ ✅ COMPLETED
- [x] **Fix Qt/display environment issues** - Tests failing due to Qt platform plugin issues in headless environment
  - **Root Cause**: cairosvg imports causing Qt platform plugin initialization failures
  - **Solution**: Use `QT_QPA_PLATFORM=offscreen` environment variable when running tests to enable headless Qt operation

### 7. ~~Map File Reference Cleanup~~ ✅ COMPLETED
- [x] **Clean up map file references** - Ensure all code uses only `standard.svg` and `svg.dtd` files
  - **Root Cause**: Multiple references to `standard_fixed.svg` and backup files scattered throughout codebase
  - **Solution**: 
    - Updated all references in telegram_bot.py to use `maps/standard.svg`
    - Updated all test files to use `maps/standard.svg`
    - Removed backup files (`standard_backup_*.svg`)
    - Verified that original `standard.svg` works correctly with cairosvg
    - All 68 tests passing with original SVG file

## Testing Summary

### ✅ **All Tests Passing:**
1. **Server Tests**: 38 passed, 4 skipped (expected session isolation skips)
2. **Engine Tests**: 28 passed (all core game logic working)
3. **Client Tests**: 2 passed (client-server interaction working)
4. **Total**: 68 passed, 4 skipped tests

### ✅ **Map Generation Fix Verification:**
1. **Original SVG File**: `maps/standard.svg` works correctly with cairosvg
2. **Telegram Bot Updates**: All map generation functions updated to use `standard.svg`
3. **Environment Configuration**: Added `DIPLOMACY_MAP_PATH` environment variable support
4. **Path Configuration**: Updated from Docker absolute paths to configurable relative paths
5. **Test Files**: Updated all test files to use `standard.svg`
6. **Clean Codebase**: Removed all references to `standard_fixed.svg` and backup files

### ✅ **Color Analysis Testing:**
1. **Comprehensive Color Analysis**: Created `test_map_colors.py` with 20% black pixel threshold
2. **Quality Criteria**: 
   - Black pixels: ≤ 20% (very dark pixels - RGB all below 50)
   - Dark pixels: ≤ 40% (average RGB below 100)
   - Average brightness: ≥ 100 (reasonable overall brightness)
   - Color variance: > 1000 (good color distribution)
3. **Analysis Scripts**: Created `analyze_existing_maps.py` for existing file analysis
4. **Test Framework**: Multiple verification methods implemented

### ✅ **Telegram Bot Tests:**
1. **Waiting List Tests**: All 4 tests in `test_telegram_waiting_list.py` updated to use dependency injection
2. **API Mock**: Tests use `api_post_func=api.post` parameter for proper mocking
3. **No Other Test Dependencies**: Verified no other test files reference the old SVG paths

### ✅ **Code Quality:**
1. **Linting**: All Ruff linting issues resolved
2. **Dependencies**: No circular import issues
3. **Configuration**: Environment variables properly configured

### ✅ **Environment Issues Resolved:**
1. **Qt Headless Mode**: Using `QT_QPA_PLATFORM=offscreen` for test execution
2. **Virtual Environment**: Tests running successfully with system Python
3. **Test Execution**: All tests passing with proper environment configuration

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

## Status: ✅ **ALL CRITICAL ISSUES RESOLVED - ALL TESTS PASSING**

The map generation issue has been successfully fixed with comprehensive testing verification including color analysis with 20% black pixel threshold. The telegram bot now uses the original `standard.svg` file and all tests are passing. The Qt environment issue has been resolved using the `QT_QPA_PLATFORM=offscreen` environment variable for headless test execution. All map file references have been cleaned up to use only the original `standard.svg` and `svg.dtd` files. 