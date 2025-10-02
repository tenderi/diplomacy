# Fix Plan (Updated October 2025)

## Current Issues Found (Prioritized)

### 1. 🔧 **V2 Map Development - SUSPENDED INDEFINITELY**
- **Current Status**: V2 map is not usable for gameplay due to fundamental projection distortion
- **Issues Encountered**:
  - **Projection Distortion**: V2 map uses Albers Equal-Area projection causing coordinate skewing
  - **Failed Fix Attempts**: Projection-aware coordinate transformation made coordinates worse
  - **Coordinate System**: Units appearing in wrong provinces despite correct calculations
- **Decision**: Focus on standard map solution instead
- **Priority**: LOW - V2 map development suspended indefinitely

## Remaining Tasks (Lower Priority)

### 2. **Multiple Order Submission Bug** (CRITICAL - HIGH PRIORITY)
- **Current Status**: Bug identified and partially investigated, requires further debugging
- **Issue Description**: When submitting multiple orders one-by-one using `/selectunit`, only the last order is saved
  - User submitted 3 orders: `A BER - SIL`, `A MUN - TYR`, `F KIE - BAL`
  - Only `F KIE - BAL` (the last one) was processed and stored
  - Issue affects both individual order submission and batch order submission
- **Root Cause Analysis**: 
  - **Initial Hypothesis**: Server command was replacing orders instead of appending
  - **Investigation Findings**: 
    - Server logs show each order is processed individually: `DEBUG: Set orders for GERMANY: ['A BER - SIL']`, then `['A MUN - TYR']`, then `['F KIE - BAL']`
    - Each order appears to be processed correctly in the server command
    - Issue persists even when submitting all orders at once via API
    - Game state retrieval shows only the last order: `{"GERMANY": ["F KIE - BAL"]}`
- **Attempted Fixes**:
  - **Fix 1**: Modified `server.py` SET_ORDERS command to append instead of replace
    - Changed from `game.set_orders(power_name, [order_str])` to `game.orders[power_name].append(order_str)`
    - Added duplicate checking to prevent duplicate orders
    - **Result**: Issue persisted
  - **Fix 2**: Modified API order cleanup logic in `api.py`
    - Removed premature database order deletion before processing
    - Added post-processing cleanup to sync database with game object
    - **Result**: Issue persisted
  - **Fix 3**: Added orders restoration in game restoration logic
    - Added orders restoration when game is restored from database
    - **Result**: Issue persisted
  - **Fix 4**: Modified database order management
    - Changed from deleting all orders to only deleting current turn orders
    - Added logic to sync game object orders with database after processing
    - **Result**: Issue persisted
- **Technical Details**:
  - **Server Command Flow**: `/selectunit` → `submit_interactive_order` → `api_post("/games/set_orders")` → `server.process_command("SET_ORDERS")`
  - **Database vs Game Object**: Game state is retrieved from `server.games[game_id].get_state()`, not database
  - **Order Storage**: Orders stored in both `game.orders[power_name]` (in-memory) and `OrderModel` (database)
  - **Synchronization Issue**: Possible mismatch between in-memory game object and database state
- **Debugging Evidence**:
  - Server logs show each order processed individually with correct debug output
  - Game state retrieval consistently shows only last order
  - Issue affects both individual and batch order submission
  - Problem appears to be in order persistence/retrieval, not order processing
- **Next Investigation Steps**:
  1. **Game Object State**: Check if game object is being overwritten between order submissions
  2. **Database Synchronization**: Verify if database state is overwriting game object state
  3. **Game Restoration**: Check if game is being restored from database between calls
  4. **Race Conditions**: Investigate potential race conditions in order processing
  5. **State Persistence**: Verify game state persistence mechanism
- **Workaround**: Use `/orders <game_id> <order1>; <order2>; <order3>` format (though this may have same issue)
- **Priority**: CRITICAL - Affects core gameplay functionality
- **Estimated Effort**: 1-2 days for root cause identification and fix

### 3. **Retreat, Build, and Destroy Order Implementation** (NEW - HIGH PRIORITY)
- **Current Status**: Order specification updated with comprehensive retreat/build/destroy rules
- **Test Coverage Analysis**: Current test suite covers ~40% of order specification
  - ✅ **Currently Tested**: Movement (`-`), Support (`S`), Convoy (`C`), Hold (`H`) orders
  - ❌ **Missing Tests**: Retreat, Build, Destroy orders and phase-specific validation
  - ❌ **Missing Implementation**: All three new order types not implemented in OrderParser
- **Implementation Required**:
  - **OrderParser Updates**:
    - Add parsing for `BUILD` and `DESTROY` order types
    - Add parsing for retreat orders (same format as moves but different validation)
    - Update validation to check phase appropriateness
    - Add validation for retreat destination constraints
    - Add validation for build/destroy eligibility
    - Add comprehensive test coverage for all legal/illegal examples from order_spec.md
  - **Game Engine Updates**:
    - Modify `_process_retreat_phase()` to handle retreat orders and automatic destruction
    - Modify `_process_builds_phase()` to handle build and destroy orders
    - Add logic to determine valid retreat destinations
    - Add logic to calculate supply center ownership after Fall moves
    - Add logic to determine build/destroy eligibility per power
  - **Phase System Updates**:
    - Ensure retreats only happen after movement phases with dislodged units
    - Ensure builds only happen after Fall moves (not Spring)
    - Add proper phase transition logic
  - **Database Updates**:
    - Update order storage to handle new order types
    - Add fields for retreat destinations and build/destroy specifications
  - **API Updates**:
    - Update order submission endpoints to handle new order types
    - Add validation for phase-appropriate orders
    - Update order display to show retreat/build/destroy orders
  - **Telegram Bot Updates**:
    - Add UI for retreat order submission
    - Add UI for build/destroy order submission
    - Update order display to show new order types
  - **Comprehensive Test Suite**:
    - Add tests for all legal examples from order_spec.md
    - Add tests for all illegal examples from order_spec.md
    - Add phase-specific validation tests
    - Add complex edge case scenarios (retreat conflicts, build restrictions, etc.)
- **Priority**: HIGH - Essential for complete Diplomacy gameplay
- **Estimated Effort**: 3-4 days (including comprehensive test coverage)

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

## Recently Completed Tasks ✅

### ✅ **Major Issues Resolved (October 2025)**
- **Telegram Bot AttributeError**: Fixed callback query handling in menu functions
- **Codebase Housekeeping**: Organized tests and archived unused scripts
- **Movement Processing Bug**: Fixed unit disappearance and movement failures
- **Admin Delete All Games Bug**: Fixed foreign key constraint violations in game deletion
- **Demo Game Issues**: Fixed 404 errors and non-functional buttons
- **Map File Path Error**: Fixed incorrect map file references
- **Database Migration Issue**: Fixed missing migrations in deployment
- **Standard Map Coordinate Alignment**: Achieved perfect coordinate alignment
- **Missing set_orders Method**: Fixed Game class missing set_orders method causing order submission errors

### 🔄 **Issues Under Investigation (October 2025)**
- **Multiple Order Submission Bug**: Identified critical bug where only last order is saved when submitting multiple orders
  - **Investigation Status**: Partially investigated, 4 attempted fixes unsuccessful
  - **Current Status**: Requires deeper debugging to identify root cause
  - **Version**: v1.10.1 contains WIP fixes for future investigation

### ✅ **Features Completed**
- **Game State Snapshots with Phase Tracking**: Complete game history with proper Diplomacy phases
- **Sample Game Test**: Successfully ran official Diplomacy rules sample game with map generation
- **Map Generation Fix**: Fixed units not appearing on generated maps (units dictionary format issue)
- **Interactive Order Input System**: Step-by-step order creation with visual feedback
- **Live Game Map Functionality**: Real-time map viewing with move visualization
- **Admin Menu**: Admin controls for game management
- **Demo Mode Feature**: Single-player demo with standard starting positions
- **Comprehensive Order System**: Complete BUILD/DESTROY/RETREAT order parsing and validation with 34 comprehensive tests
- **Game Engine Phase Integration**: Complete retreat and builds phase processing with OrderParser integration

## Current Status: ⚠️ **CRITICAL BUG IDENTIFIED** - **MULTIPLE ORDER SUBMISSION ISSUE**

**CRITICAL ISSUE**: Multiple order submission bug prevents proper gameplay - only last order is saved when submitting multiple orders via `/selectunit`.

The Diplomacy bot has complete Diplomacy rule implementation with:
- ✅ **Standard Map**: Perfect coordinate alignment and visible background
- ✅ **Movement Processing**: All movement bugs resolved
- ✅ **Telegram Bot**: All menu buttons working correctly
- ✅ **Admin Functions**: Complete admin controls
- ✅ **Demo Mode**: Fully functional single-player demo
- ✅ **Interactive Orders**: Step-by-step order creation
- ✅ **Live Maps**: Real-time game state visualization
- ✅ **Game Snapshots**: Complete game history with phase tracking
- ✅ **Phase System**: Proper Diplomacy phase progression (Spring/Autumn/Retreat/Builds)
- ✅ **Codebase Organization**: Tests centralized, unused scripts archived
- ✅ **Order Specification**: Comprehensive documentation for all order types
- ✅ **Complete Order System**: All 7 order types (Movement, Support, Convoy, Hold, Retreat, Build, Destroy)
- ✅ **Comprehensive Validation**: Phase-aware validation with 34 comprehensive tests
- ✅ **Game Engine Integration**: Complete retreat and builds phase processing

**CURRENT STATUS**: Full Diplomacy rule implementation is complete, but **CRITICAL BUG** prevents proper gameplay. **IMMEDIATE PRIORITY**: Fix multiple order submission bug before any other development.
