# Testing Gaps Analysis

This document identifies gaps between the testing strategy requirements and the current test coverage.

**Last Updated**: 2025-03-09 — Aligned with `fix_plan.md`. Full suite: 1019 passed, 21 skipped, 0 failures. Many items below are now covered; resolved items marked ✅.

## Summary

- **Total Test Files**: ~80 test files
- **Coverage**: Good coverage; P0/P1/P2 items from fix_plan are resolved (see fix_plan.md for completed list)
- **Priority**: Remaining gaps are optional/future; focus P0/P1 first if adding new tests

---

## Critical Gaps (P0 - Must-Have)

### 1. Game Engine - Adjudication Edge Cases

#### Missing Tests:
- ✅ **Circular Supports**: Covered in `test_circular_supports.py` (valid adjacencies; fix_plan resolved)
- ✅ **Self-Support**: Validation in engine; covered via order validation tests
- ✅ **Support Cut by Move**: Fixed and covered (fix_plan: support cut by move logic; tests pass)
- ✅ **Self-Dislodgement Prevention**: Already tested (`test_self_dislodgement_prohibited`)
- ✅ **Convoy Disruption**: Already tested (`test_complex_convoy_disruption`)

### 2. Game Engine - Phase Transition Edge Cases

#### Missing Tests:
- ✅ **Phase skipping**: Covered in `test_phase_skipping.py` (no dislodgements → skip retreat; fix_plan)
- ✅ **All Units Disband / Retreat**: Retreat validation and disband when no options (fix_plan; `test_retreat_edge_cases.py`)
- ❌ **Victory During Movement**: Optional; partially covered
  - **Location**: `test_game.py` / victory condition tests
  - **Priority**: MEDIUM (optional)
- ❌ **Victory During Builds**: Optional; partially covered in `test_game.py`
  - **Priority**: MEDIUM (optional)
- ✅ **Spring/Autumn Transitions**: Covered in `test_consecutive_phases.py`

### 3. Game Engine - Order Validation Edge Cases

#### Missing Tests:
- ✅ **Duplicate Orders**: Covered in `test_order_validation_comprehensive.py` (fix_plan)
- ✅ **Order for Non-Existent Unit**: Covered in order validation tests (fix_plan)
- ✅ **Order for Wrong Power**: Covered in API authorization tests (`test_authorization.py`)
- ✅ **Order in Wrong Phase / phase compatibility**: Covered in `test_order_validation_comprehensive.py` (fix_plan)
- ✅ **Convoy validation**: Covered; convoy route validation fixed (fix_plan)
- ✅ **Support Order for Non-Move / holding**: Covered in order validation (fix_plan)
- ✅ **Move to Own Province**: Covered (move to own occupied province validation; fix_plan)

### 4. Server/API - Authorization and Security

#### Missing Tests:
- ✅ **Power Ownership Validation**: Covered in `test_authorization.py` (fix_plan: HTTP 403/404/409)
- ✅ **403 Forbidden Responses**: API error handling returns correct status codes (fix_plan)
- ✅ **User Registration / Unregistered user**: Covered in `test_authorization.py`, `test_user_registration.py`
- ✅ **Auth Routes**: Well covered in `test_auth.py` (register, login, refresh, link, forgot/reset password)

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
- ✅ **Password Reset Flow**: Forgot password and reset password in `test_auth.py` (test_forgot_password_*, test_reset_password_*)
- ✅ **Token Refresh**: Covered in `test_auth.py` (test_refresh_token, test_refresh_invalid_token)
- ✅ **Register/Login**: Well covered in `test_auth.py`
- ✅ **Link Telegram**: Covered in `test_auth.py`

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
- ✅ **Multi-Coast Provinces**: Covered in `test_multi_coast_provinces.py` (fix_plan: Province init, Spain/Bulgaria/StP)
- ✅ **Special Adjacencies**: Covered in `test_special_adjacencies.py`, `test_adjacency_validation.py`

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
- ✅ **State Validation**: Covered in `test_state_validation.py` (fix_plan)
- ✅ **Phase Consistency**: Covered in state validation and consecutive phases tests

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
