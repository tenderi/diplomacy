# Testing Gaps Analysis

This document identifies gaps between the testing strategy requirements and the current test coverage.

**Last Updated**: Based on codebase exploration of `new_implementation/` directory

## Summary

- **Total Test Files**: ~80 test files
- **Coverage**: Good coverage in many areas, but several critical gaps identified
- **Priority**: Focus on P0 (Critical) and P1 (High Priority) gaps first

---

## Critical Gaps (P0 - Must-Have)

### 1. Game Engine - Adjudication Edge Cases

#### Missing Tests:
- ❌ **Circular Supports**: A supports B, B supports C, C supports A (all hold)
  - **Status**: Not found in test files
  - **Location**: Should be in `test_adjudication.py` or new `test_circular_supports.py`
  - **Priority**: CRITICAL

- ❌ **Self-Support**: Unit supports its own move (should be invalid)
  - **Status**: Not explicitly tested
  - **Location**: `test_adjudication.py` or `test_order_validation.py`
  - **Priority**: CRITICAL

- ❌ **Support Cut by Move**: Supporting unit moves, cutting its own support
  - **Status**: Partially covered (`test_support_cut_by_dislodgement` exists)
  - **Gap**: Need explicit test for support cut by move (not dislodgement)
  - **Priority**: CRITICAL

- ✅ **Self-Dislodgement Prevention**: Already tested (`test_self_dislodgement_prohibited`)
- ✅ **Convoy Disruption**: Already tested (`test_complex_convoy_disruption`)

### 2. Game Engine - Phase Transition Edge Cases

#### Missing Tests:
- ❌ **No Dislodgements → Skip Retreat**: Movement phase with no dislodgements should skip Retreat phase
  - **Status**: Not explicitly tested
  - **Location**: `test_consecutive_phases.py` or new `test_phase_skipping.py`
  - **Priority**: CRITICAL

- ❌ **All Units Disband**: All dislodged units disband → skip Retreat phase
  - **Status**: Not tested
  - **Location**: `test_consecutive_phases.py`
  - **Priority**: CRITICAL

- ❌ **Victory During Movement**: Power reaches 18 SCs during movement phase
  - **Status**: `test_victory_condition_standard_map` exists but may not cover movement phase
  - **Gap**: Need explicit test for victory during movement (not just builds)
  - **Priority**: CRITICAL

- ❌ **Victory During Builds**: Power reaches 18 SCs after builds
  - **Status**: Partially covered in `test_game.py`
  - **Gap**: Need comprehensive test
  - **Priority**: CRITICAL

- ✅ **Spring/Autumn Transitions**: Covered in `test_consecutive_phases.py`

### 3. Game Engine - Order Validation Edge Cases

#### Missing Tests:
- ❌ **Duplicate Orders**: Multiple orders for same unit
  - **Status**: Not explicitly tested
  - **Location**: `test_order_parser.py` or `test_enhanced_validation.py`
  - **Priority**: HIGH

- ❌ **Order for Non-Existent Unit**: Order for unit that doesn't exist
  - **Status**: Not explicitly tested
  - **Location**: `test_order_validation.py` or new test file
  - **Priority**: HIGH

- ❌ **Order for Wrong Power**: Order submitted for another power's unit
  - **Status**: Not explicitly tested
  - **Location**: `test_order_validation.py`
  - **Priority**: HIGH

- ❌ **Order in Wrong Phase**: Movement order in Retreat phase, etc.
  - **Status**: Not explicitly tested
  - **Location**: `test_order_validation.py` or `test_game.py`
  - **Priority**: HIGH

- ❌ **Convoy Order Without Convoy Path**: Convoy order where no path exists
  - **Status**: Not explicitly tested
  - **Location**: `test_convoy_functions.py`
  - **Priority**: HIGH

- ❌ **Support Order for Non-Move**: Support order for unit that's holding
  - **Status**: Not explicitly tested
  - **Location**: `test_order_validation.py`
  - **Priority**: HIGH

- ❌ **Move to Own Province**: Move to province already occupied by own unit
  - **Status**: Partially covered (self-dislodgement test)
  - **Gap**: Need explicit test for this validation
  - **Priority**: HIGH

### 4. Server/API - Authorization and Security

#### Missing Tests:
- ❌ **Power Ownership Validation**: Users can only submit orders for their assigned power
  - **Status**: Partially covered in API route tests
  - **Gap**: Need comprehensive test suite for all authorization scenarios
  - **Location**: `test_api_routes_orders.py` or new `test_authorization.py`
  - **Priority**: CRITICAL

- ❌ **403 Forbidden Responses**: Comprehensive test for all unauthorized actions
  - **Status**: Some tests exist but not comprehensive
  - **Location**: `test_api_routes_*.py` files
  - **Priority**: CRITICAL

- ❌ **User Registration Required**: Users must register before joining games
  - **Status**: Partially tested
  - **Gap**: Need explicit test for unregistered user attempting game actions
  - **Location**: `test_user_registration.py` or `test_api_routes_games.py`
  - **Priority**: CRITICAL

- ✅ **Auth Routes**: Well covered in `test_auth.py`

### 5. Server/API - Game Management Edge Cases

#### Missing Tests:
- ❌ **Game Already Started**: Attempt to join game that's already in progress
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_games.py`
  - **Priority**: HIGH

- ❌ **User Already in Game**: Attempt to join game user is already in
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_games.py`
  - **Priority**: HIGH

- ❌ **Process Turn Without Orders**: Process turn when no orders submitted
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_games.py` or `test_integration.py`
  - **Priority**: HIGH

- ❌ **Process Turn in Wrong Phase**: Attempt to process turn in Retreat/Builds phase
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_games.py`
  - **Priority**: HIGH

- ✅ **Game Not Found**: Covered in various API route tests
- ✅ **Power Already Taken**: Partially covered

### 6. Server/API - Order Submission Edge Cases

#### Missing Tests:
- ❌ **Empty Order List**: Submit empty order list (should clear orders)
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_orders.py`
  - **Priority**: HIGH

- ❌ **Partial Order Submission**: Submit orders for some but not all units
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_orders.py`
  - **Priority**: HIGH

- ❌ **Order for Eliminated Power**: Submit orders for eliminated power
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_orders.py`
  - **Priority**: HIGH

- ❌ **Order After Turn Processed**: Submit orders after turn already processed
  - **Status**: Not explicitly tested
  - **Location**: `test_api_routes_orders.py`
  - **Priority**: HIGH

- ❌ **Concurrent Order Submission**: Multiple users submit orders simultaneously
  - **Status**: Not tested (requires threading/concurrency tests)
  - **Location**: New `test_concurrent_operations.py`
  - **Priority**: MEDIUM (nice-to-have)

---

## High Priority Gaps (P1 - Should-Have)

### 7. Database Persistence Edge Cases

#### Missing Tests:
- ❌ **Database Connection Loss**: Handle database disconnection gracefully
  - **Status**: Not tested
  - **Location**: `test_database_service.py` or new `test_database_resilience.py`
  - **Priority**: HIGH

- ❌ **Concurrent Writes**: Multiple processes write to database simultaneously
  - **Status**: Not tested
  - **Location**: New `test_database_concurrency.py`
  - **Priority**: MEDIUM

- ❌ **Transaction Rollback**: Failed transaction rolls back correctly
  - **Status**: Not explicitly tested
  - **Location**: `test_database_service.py`
  - **Priority**: HIGH

- ❌ **Orphaned Records**: Clean up orphaned game/order records
  - **Status**: Not tested
  - **Location**: `test_database_service.py`
  - **Priority**: MEDIUM

- ✅ **Basic CRUD Operations**: Covered in `test_database_service.py`

### 8. Telegram Bot - Command Edge Cases

#### Missing Tests:
- ❌ **User Not Registered**: Commands from unregistered users
  - **Status**: Not explicitly tested
  - **Location**: `test_telegram_bot.py` or `test_telegram_bot_enhanced.py`
  - **Priority**: HIGH

- ❌ **User in No Games**: Commands when user has no active games
  - **Status**: Partially tested
  - **Gap**: Need comprehensive coverage
  - **Location**: `test_telegram_bot.py`
  - **Priority**: HIGH

- ❌ **User in Multiple Games**: Commands when game_id ambiguous
  - **Status**: Partially tested
  - **Gap**: Need comprehensive coverage
  - **Location**: `test_telegram_bot.py`
  - **Priority**: HIGH

- ❌ **Button Callback Timeout**: Callback queries that expire
  - **Status**: Not tested
  - **Location**: `test_telegram_bot.py` or `test_interactive_orders.py`
  - **Priority**: MEDIUM

- ❌ **Concurrent Button Presses**: Multiple button presses simultaneously
  - **Status**: Not tested
  - **Location**: New `test_telegram_concurrency.py`
  - **Priority**: MEDIUM

### 9. Telegram Bot - Link Account Feature

#### Missing Tests:
- ❌ **Link Account Command**: `/link <code>` functionality
  - **Status**: Not tested
  - **Location**: New `test_telegram_link_account.py`
  - **Priority**: HIGH
  - **Note**: Module exists at `src/server/telegram_bot/link_account.py` but no tests

### 10. Telegram Bot - Notifications

#### Missing Tests:
- ❌ **Notification Endpoint**: `/notify` endpoint functionality
  - **Status**: Not tested
  - **Location**: New `test_telegram_notifications.py`
  - **Priority**: MEDIUM
  - **Note**: Module exists at `src/server/telegram_bot/notifications.py` but no tests

### 11. API Routes - Auth Routes

#### Missing Tests:
- ❌ **Password Reset Flow**: Forgot password and reset password endpoints
  - **Status**: Not tested
  - **Location**: `test_auth.py` (extend existing)
  - **Priority**: HIGH

- ❌ **Token Refresh**: Refresh token expiration and renewal
  - **Status**: Partially tested
  - **Gap**: Need comprehensive refresh token tests
  - **Location**: `test_auth.py`
  - **Priority**: HIGH

- ✅ **Register/Login**: Well covered in `test_auth.py`
- ✅ **Link Telegram**: Partially covered

### 12. API Routes - Channels

#### Missing Tests:
- ✅ **Channel Analytics**: Analytics endpoints (`get_channel_analytics`, `get_channel_analytics_summary`, engagement, players) — covered in `test_channel_analytics.py`

- ✅ **Channel Battle Results**: Covered in `test_channel_battle_results.py`
- ✅ **Channel Dashboard**: Covered in `test_channel_dashboard.py`
- ✅ **Channel Voting**: Covered in `test_channel_voting.py`
- ✅ **Channel Timeline**: Covered in `test_channel_timeline.py`

### 13. API Routes - Dashboard

#### Missing Tests:
- ❌ **Service Management**: Restart service, get service logs
  - **Status**: Not tested
  - **Location**: `test_api_routes_dashboard.py` (extend existing)
  - **Priority**: MEDIUM

- ❌ **Database Inspection**: Get database tables, table data
  - **Status**: Not tested
  - **Location**: `test_api_routes_dashboard.py`
  - **Priority**: MEDIUM

- ✅ **Service Status**: Partially covered

### 14. Power Module

#### Missing Tests:
- ❌ **Power Class Methods**: Comprehensive tests for `Power` class
  - **Status**: Basic tests in `test_map_and_power.py`
  - **Gap**: Need tests for all methods (add_unit, remove_unit, get_unit_at_province, etc.)
  - **Location**: `test_map_and_power.py` or new `test_power.py`
  - **Priority**: HIGH

---

## Medium Priority Gaps (P2 - Nice-to-Have)

### 15. Map Edge Cases

#### Missing Tests:
- ❌ **Multi-Coast Provinces**: Comprehensive tests for Spain (NC/SC), Bulgaria (EC/SC), St. Petersburg (NC/SC)
  - **Status**: Partially covered
  - **Gap**: Need explicit tests for all multi-coast scenarios
  - **Location**: `test_map_*.py` files
  - **Priority**: MEDIUM

- ❌ **Special Adjacencies**: Special cases like Kiel, Constantinople
  - **Status**: Not explicitly tested
  - **Location**: `test_adjacency_validation.py`
  - **Priority**: MEDIUM

### 16. Performance Testing

#### Missing Tests:
- ❌ **Response Time Benchmarks**: API endpoint response times
  - **Status**: Not tested
  - **Location**: New `test_performance.py`
  - **Priority**: MEDIUM

- ❌ **Load Testing**: Multiple concurrent users
  - **Status**: Not tested
  - **Location**: New `test_load.py`
  - **Priority**: MEDIUM

- ❌ **Database Query Performance**: Query optimization tests
  - **Status**: Not tested
  - **Location**: New `test_database_performance.py`
  - **Priority**: MEDIUM

### 17. State Consistency Validation

#### Missing Tests:
- ❌ **State Validation**: Comprehensive tests for `GameState.validate_game_state()`
  - **Status**: Not explicitly tested
  - **Location**: New `test_state_validation.py`
  - **Priority**: MEDIUM

- ❌ **Phase Consistency**: Phase matches expected state
  - **Status**: Partially covered
  - **Gap**: Need comprehensive phase consistency tests
  - **Location**: `test_consecutive_phases.py`
  - **Priority**: MEDIUM

---

## Low Priority Gaps (P3 - Future Enhancements)

### 18. Property-Based Testing
- ❌ **Hypothesis Tests**: Property-based testing for order parsing
- ❌ **Fuzz Testing**: Fuzz testing for order validation

### 19. Visual Regression Testing
- ❌ **Map Rendering Comparison**: Visual diff tests for map generation
- ❌ **UI Screenshot Comparison**: Screenshot comparison for bot UI

### 20. End-to-End Service Testing
- ❌ **Systemd Service Startup**: Full service startup tests
- ❌ **Container-Based Testing**: Docker container testing

---

## Test File Organization Recommendations

### New Test Files Needed:
1. `test_circular_supports.py` - Circular support scenarios
2. `test_phase_skipping.py` - Phase skipping edge cases
3. `test_order_validation_comprehensive.py` - Comprehensive order validation
4. `test_authorization.py` - Authorization and security tests
5. `test_concurrent_operations.py` - Concurrency tests
6. `test_database_resilience.py` - Database failure handling
7. `test_telegram_link_account.py` - Link account command
8. `test_telegram_notifications.py` - Notification endpoint
9. `test_power.py` - Comprehensive Power class tests
10. `test_state_validation.py` - State consistency validation
11. `test_performance.py` - Performance benchmarks
12. `test_load.py` - Load testing

### Files to Extend:
1. `test_adjudication.py` - Add circular supports, self-support
2. `test_consecutive_phases.py` - Add phase skipping tests
3. `test_api_routes_orders.py` - Add order submission edge cases
4. `test_api_routes_games.py` - Add game management edge cases
5. `test_telegram_bot.py` - Add command edge cases
6. `test_auth.py` - Add password reset, comprehensive refresh token tests
7. `test_database_service.py` - Add transaction rollback, resilience tests

---

## Priority Implementation Plan

### Phase 1: Critical Gaps (Week 1)
1. Circular supports test
2. Self-support validation test
3. Phase skipping tests (no dislodgements, all disband)
4. Victory condition tests (during movement and builds)
5. Comprehensive authorization tests
6. Order validation edge cases (duplicate, wrong power, wrong phase)

### Phase 2: High Priority Gaps (Week 2-3)
1. Game management edge cases
2. Order submission edge cases
3. Database resilience tests
4. Telegram bot command edge cases
5. Link account tests
6. Power class comprehensive tests

### Phase 3: Medium Priority (Week 4+)
1. Performance testing
2. Load testing
3. State validation tests
4. Multi-coast province tests
5. Channel analytics tests

---

## Coverage Metrics

### Current Coverage (Estimated):
- **Game Engine Core**: ~85%
- **API Routes**: ~80%
- **Telegram Bot**: ~75%
- **Database**: ~70%
- **Edge Cases**: ~60%

### Target Coverage:
- **Game Engine Core**: >95%
- **API Routes**: >90%
- **Telegram Bot**: >85%
- **Database**: >85%
- **Edge Cases**: >80%

---

## Notes

- Many tests exist but may not cover all edge cases explicitly
- Some functionality exists in code but lacks dedicated tests
- Focus on P0 and P1 gaps first for maximum impact
- Consider using property-based testing (Hypothesis) for order parsing validation
- Consider visual regression testing for map generation
