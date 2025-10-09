# Unsolicited Movement Bug Investigation Plan (HIGHEST PRIORITY)

## Problem Statement

Between phases 08 (autumn_movement) and 09 (autumn_retreat), units are moving without proper orders:

1. **A VEN -> TYR**: Italy army moving from Venice to Tyrolia (previously reported and supposedly fixed)
2. **A LVP -> CLY**: England army moving from Liverpool to Clyde (should not move during retreat phase - not dislodged)

## Root Cause Hypotheses

### Hypothesis 1: Retreat Order Generation for Non-Dislodged Units

**Location**: `src/engine/strategic_ai.py` lines 82-103

The `_generate_retreat_orders()` method may be generating retreat orders for units that are NOT dislodged:

```python
def _generate_retreat_orders(self, game_state: GameState, power_state: PowerState) -> List[Order]:
    for unit in power_state.units:
        if unit.is_dislodged and unit.can_retreat:  # Check may be insufficient
            if unit.retreat_options:
                retreat_province = unit.retreat_options[0]
                order = RetreatOrder(...)
```

**Issue**: The condition `unit.is_dislodged and unit.can_retreat` may not be properly set, or units may have `retreat_options` populated even when not dislodged.

### Hypothesis 2: Retreat Processing Executes All Movement Orders

**Location**: `src/engine/game.py` lines 614-649

The `_process_retreat_phase()` method may be processing movement orders instead of only retreat orders:

```python
def _process_retreat_phase(self) -> Dict[str, Any]:
    for power_name, orders in self.game_state.orders.items():
        for order in orders:
            if isinstance(order, RetreatOrder):  # May not be filtering correctly
                # Execute retreat
                order.unit.province = order.retreat_province
```

**Issue**: The type check `isinstance(order, RetreatOrder)` may not be catching all non-retreat orders, OR the orders dictionary still contains movement orders from previous phase.

### Hypothesis 3: Order Clearing Not Working Between Phases

**Location**: `demo_automated_game.py` lines 477-507

Orders from the movement phase may not be cleared before generating retreat orders:

```python
if game_state.current_phase == "Retreat":
    retreats = self.generate_dynamic_orders(game_state)  # Are old orders still present?
    for power, power_retreats in retreats.items():
        self.submit_orders(power, power_retreats)
```

**Issue**: If `game_state.orders` still contains movement orders when entering retreat phase, those might be processed again.

### Hypothesis 4: Phase Transition Not Updating Unit Positions

**Location**: `src/engine/game.py` line 629

Units may have their province updated during movement phase but the game state isn't properly saved:

```python
order.unit.province = order.retreat_province
```

**Issue**: If units are being moved during retreat processing but their position was already changed during movement, this could create phantom movements.

### Hypothesis 5: Map Rendering Showing Wrong Phase Data

**Location**: `demo_automated_game.py` lines 474, 507

The maps labeled "autumn_movement" (08) and "autumn_retreat" (09) may be generated with incorrect game state:

```python
# Line 474: After movement processing
self.generate_and_save_map(game_state, "compliant_demo_08_autumn_movement.png")

# Line 507: After retreat processing
self.generate_and_save_map(game_state, "compliant_demo_09_autumn_retreat.png")
```

**Issue**: `game_state` may be stale or showing units in wrong positions due to timing.

## Investigation Steps

### Step 1: Add Debug Logging to Retreat Order Generation

**File**: `src/engine/strategic_ai.py`

**Location**: Lines 82-103

Add logging to track:

- Which units are considered for retreat orders
- Unit dislodged status: `unit.is_dislodged`
- Unit retreat options: `unit.retreat_options`
- Whether retreat orders are actually generated
```python
def _generate_retreat_orders(self, game_state: GameState, power_state: PowerState) -> List[Order]:
    logger.info(f"=== Generating retreat orders for {power_state.power_name} ===")
    orders = []
    
    for unit in power_state.units:
        logger.info(f"  Unit {unit}: is_dislodged={unit.is_dislodged}, can_retreat={unit.can_retreat}, retreat_options={unit.retreat_options}")
        if unit.is_dislodged and unit.can_retreat:
            if unit.retreat_options:
                retreat_province = unit.retreat_options[0]
                logger.info(f"    -> Generating retreat order to {retreat_province}")
                order = RetreatOrder(...)
                orders.append(order)
```


### Step 2: Add Debug Logging to Retreat Processing

**File**: `src/engine/game.py`

**Location**: Lines 614-649

Add logging to track:

- What orders exist at start of retreat phase
- Order types being processed
- Which units are actually moving
```python
def _process_retreat_phase(self) -> Dict[str, Any]:
    logger.info(f"=== Processing retreat phase ===")
    logger.info(f"Orders at start of retreat phase:")
    for power_name, orders in self.game_state.orders.items():
        logger.info(f"  {power_name}: {[f'{type(o).__name__}: {o}' for o in orders]}")
    
    for power_name, orders in self.game_state.orders.items():
        for order in orders:
            logger.info(f"Processing order: {type(order).__name__}: {order}")
            if isinstance(order, RetreatOrder):
                logger.info(f"  -> Retreat order detected, executing...")
            else:
                logger.warning(f"  -> Non-retreat order in retreat phase: {type(order).__name__}")
```


### Step 3: Add Debug Logging to Demo Game Order Submission

**File**: `demo_automated_game.py`

**Location**: Lines 477-507

Add logging before and after retreat order generation:

```python
if game_state.current_phase == "Retreat":
    logger.info(f"=== Entering retreat phase ===")
    logger.info(f"Current orders before generating retreats:")
    for power_name, orders in game_state.orders.items():
        logger.info(f"  {power_name}: {[str(o) for o in orders]}")
    
    retreats = self.generate_dynamic_orders(game_state)
    logger.info(f"Generated retreat orders: {retreats}")
```

### Step 4: Verify Order Clearing Between Phases

**File**: `src/engine/game.py`

**Search for**: Phase transition methods and `clear_orders()` calls

Check if orders are properly cleared when transitioning between phases. Look for:

- Where `game_state.orders` is modified
- Whether old orders persist across phase boundaries
- If `set_orders()` replaces or appends

### Step 5: Check Unit Position Updates

**File**: `src/engine/game.py`

**Location**: Movement resolution logic

Verify that:

- Units only move during movement phase, not retreat phase
- Dislodged units have correct `is_dislodged` flag
- Unit positions are saved correctly after movement
- No duplicate movement logic exists

### Step 6: Inspect Actual Game State at Phase Boundaries

**File**: `demo_automated_game.py`

**Location**: Before/after each `process_turn()` call

Add comprehensive state dumps:

```python
# Before processing
logger.info(f"=== State before processing turn ===")
logger.info(f"Phase: {game_state.current_phase}")
for power_name, power_state in game_state.powers.items():
    logger.info(f"{power_name} units: {[f'{u.unit_type} {u.province} (dislodged={u.is_dislodged})' for u in power_state.units]}")

self.process_turn()

# After processing
game_state = self.get_game_state()
logger.info(f"=== State after processing turn ===")
logger.info(f"Phase: {game_state.current_phase}")
for power_name, power_state in game_state.powers.items():
    logger.info(f"{power_name} units: {[f'{u.unit_type} {u.province} (dislodged={u.is_dislodged})' for u in power_state.units]}")
```

### Step 7: Check A VEN -> TYR Specifically

**Investigation**: Why was this supposedly fixed but still happening?

Review:

- Previous fix for Italy A VEN movement issue
- Order splitting logic in `src/server/server.py`
- Order parsing in `src/engine/order.py`
- Whether Italy has ANY orders for A VEN in autumn movement

### Step 8: Run Demo with Debug Logging

**Command**: `cd /home/tenderi/diplomacy/new_implementation && python3 demo_automated_game.py > debug_output.txt 2>&1`

Capture all debug output and analyze:

- What orders are generated for each phase
- Unit positions at each phase boundary
- Whether non-dislodged units get retreat orders
- Order type distribution in each phase

## Expected Findings

Based on the symptoms, the most likely issues are:

1. **Retreat options populated for non-dislodged units**: Units that didn't move or weren't attacked still have `retreat_options` populated, causing AI to generate retreat orders for them

2. **Order clearing failure**: Movement orders persist into retreat phase and get processed again

3. **Incorrect dislodged status**: Units are marked as `is_dislodged=True` even when they shouldn't be

## Files to Modify

1. `src/engine/strategic_ai.py` - Add debug logging to retreat order generation
2. `src/engine/game.py` - Add debug logging to retreat processing and verify order clearing
3. `demo_automated_game.py` - Add comprehensive state logging at phase boundaries
4. `src/engine/data_models.py` - Possibly add validation to prevent retreat orders for non-dislodged units

## Success Criteria

- [ ] Debug logging shows exactly which units are moving and why
- [ ] Root cause identified (retreat options, order clearing, or dislodged status)
- [ ] Fix prevents non-dislodged units from moving during retreat phase
- [ ] A VEN stays in VEN (or moves only if ordered during movement phase)
- [ ] A LVP stays in LVP during retreat phase
- [ ] All unit movements can be traced to explicit orders

## Future Enhancement Opportunities 📋

### **Phase 1: Performance and Scalability** 

#### **1.1 Optimize Map Generation**
- [ ] **Implement Map Caching**: Cache generated maps to avoid regeneration
- [ ] **Optimize SVG Processing**: Improve SVG to PNG conversion performance
- [ ] **Add Map Compression**: Compress map images for faster transmission
- [ ] **Implement Map Preloading**: Preload common map states

#### **1.2 Database Optimization**
- [ ] **Add Database Indexes**: Add indexes for frequently queried fields
- [ ] **Implement Connection Pooling**: Use connection pooling for better performance
- [ ] **Add Query Optimization**: Optimize database queries for better performance
- [ ] **Implement Caching Layer**: Add Redis caching for frequently accessed data

#### **1.3 API Performance**
- [ ] **Add Response Caching**: Cache API responses where appropriate
- [ ] **Implement Pagination**: Add pagination for large data sets
- [ ] **Add Rate Limiting**: Implement rate limiting to prevent abuse
- [ ] **Optimize Serialization**: Improve JSON serialization performance

### **Phase 2: User Experience Enhancements**

#### **2.1 Telegram Bot Improvements**
- [ ] **Add Order Templates**: Provide common order templates for new players
- [ ] **Implement Order Suggestions**: Suggest legal orders based on current position
- [ ] **Add Game Statistics**: Show player statistics and game history
- [ ] **Improve Error Messages**: Provide user-friendly error messages

#### **2.2 Interactive Features**
- [ ] **Add Order Preview**: Show order effects before submission
- [ ] **Implement Order History**: Show complete order history for each game
- [ ] **Add Turn Notifications**: Notify players when it's their turn
- [ ] **Implement Game Reminders**: Remind players of upcoming deadlines

#### **2.3 Map Visualization Enhancements**
- [ ] **Add Province Labels**: Show province names on maps
- [ ] **Implement Zoom Functionality**: Allow zooming in/out on maps
- [ ] **Add Unit Animations**: Animate unit movements on maps
- [ ] **Implement Map Layers**: Add toggleable map layers (units, orders, etc.)

### **Phase 3: Advanced Features** 

#### **3.1 Game Variants**
- [ ] **Implement Map Variants**: Support for different map variants
- [ ] **Add Custom Rules**: Allow custom rule modifications
- [ ] **Implement Scenario Mode**: Pre-defined game scenarios
- [ ] **Add Tournament Mode**: Support for tournament play

#### **3.2 AI Integration**
- [ ] **Implement AI Players**: Add AI players for incomplete games
- [ ] **Add Difficulty Levels**: Different AI difficulty levels
- [ ] **Implement AI Analysis**: AI analysis of game positions
- [ ] **Add AI Suggestions**: AI suggestions for player moves

#### **3.3 Advanced Analytics**
- [ ] **Add Game Analytics**: Track game statistics and trends
- [ ] **Implement Player Ratings**: ELO-style player ratings
- [ ] **Add Performance Metrics**: Track bot performance metrics
- [ ] **Implement Reporting**: Generate game reports and statistics

### **Phase 4: Infrastructure and DevOps** 

#### **4.1 Monitoring and Logging**
- [ ] **Implement Comprehensive Logging**: Add structured logging throughout the system
- [ ] **Add Performance Monitoring**: Monitor system performance metrics
- [ ] **Implement Error Tracking**: Track and alert on errors
- [ ] **Add Health Checks**: Implement health check endpoints

#### **4.2 Security Enhancements**
- [ ] **Implement Authentication**: Add proper user authentication
- [ ] **Add Authorization**: Implement role-based access control
- [ ] **Add Input Sanitization**: Sanitize all user inputs
- [ ] **Implement Rate Limiting**: Prevent abuse and DoS attacks

#### **4.3 Deployment Improvements**
- [ ] **Add CI/CD Pipeline**: Implement continuous integration/deployment
- [ ] **Add Automated Testing**: Automated test execution in CI
- [ ] **Implement Blue-Green Deployment**: Zero-downtime deployments
- [ ] **Add Rollback Capability**: Quick rollback for failed deployments

## Code Quality Improvements 📋

### **Code Organization**
- [ ] **Consolidate Duplicate Code**: Remove duplicate code across modules
- [ ] **Improve Module Structure**: Better organization of related functionality
- [ ] **Add Type Hints**: Add comprehensive type hints throughout codebase
- [ ] **Improve Documentation**: Add comprehensive docstrings and comments

### **Testing Improvements**
- [ ] **Increase Test Coverage**: Achieve >90% test coverage
- [ ] **Add Integration Tests**: Comprehensive integration test suite
- [ ] **Add Performance Tests**: Test system performance under load
- [ ] **Add End-to-End Tests**: Complete end-to-end test scenarios

### **Code Standards**
- [ ] **Enforce Code Style**: Consistent code formatting and style
- [ ] **Add Linting Rules**: Comprehensive linting rules
- [ ] **Implement Code Reviews**: Mandatory code review process
- [ ] **Add Static Analysis**: Static code analysis tools

## Technical Debt Reduction 📋

### **Legacy Code Cleanup**
- [ ] **Remove Unused Files**: Clean up unused scripts and files
- [ ] **Consolidate Similar Functions**: Merge similar functionality
- [ ] **Simplify Complex Methods**: Break down complex methods
- [ ] **Remove Dead Code**: Remove unreachable code paths

### **Dependency Management**
- [ ] **Update Dependencies**: Keep all dependencies up to date
- [ ] **Remove Unused Dependencies**: Remove unnecessary dependencies
- [ ] **Add Dependency Security Scanning**: Scan for security vulnerabilities
- [ ] **Implement Dependency Pinning**: Pin dependency versions

### **Configuration Management**
- [ ] **Centralize Configuration**: Single source of truth for configuration
- [ ] **Add Environment-Specific Configs**: Different configs for different environments
- [ ] **Implement Configuration Validation**: Validate configuration on startup
- [ ] **Add Configuration Documentation**: Document all configuration options

## Success Metrics 📊

### **Immediate Goals (Phase 1)**
- [ ] System performance is acceptable under load
- [ ] Database queries are optimized
- [ ] Map generation is fast and reliable
- [ ] User experience is smooth and intuitive

### **Short-term Goals (Phases 2-3)**
- [ ] Advanced features are implemented
- [ ] User experience is enhanced
- [ ] System is scalable and maintainable
- [ ] Security is robust and comprehensive

### **Long-term Goals (Phase 4)**
- [ ] Deployment process is automated and reliable
- [ ] Monitoring and logging are comprehensive
- [ ] System is production-ready at scale
- [ ] All advanced features are implemented

## Implementation Strategy

1. **Focus on Performance**: Optimize map generation and database queries
2. **Enhance User Experience**: Improve bot interface and interactive features
3. **Add Advanced Features**: Implement AI players and game variants
4. **Improve Infrastructure**: Add monitoring, security, and deployment automation
5. **Maintain Code Quality**: Keep codebase clean and well-documented

---

**CURRENT STATUS**: Full Diplomacy rule implementation is complete and **PRODUCTION READY**. All critical bugs resolved, core gameplay functionality working correctly, and comprehensive demo game showcasing all mechanics. **Next priority**: Performance optimization and user experience enhancements.