# Testing and Validation Strategy

## Overview

Testing is critical for ensuring the correctness and reliability of the Diplomacy Python implementation. This strategy covers unit, integration, and end-to-end testing, as well as continuous integration (CI) setup.

## Testing Philosophy

- **Test-Driven Development**: Write tests before or alongside implementation
- **Comprehensive Coverage**: Aim for >90% code coverage
- **Fast Feedback**: Unit tests should run quickly (< 5 seconds total)
- **Isolation**: Tests should be independent and not rely on external state
- **Automation**: All tests run automatically on every commit

## Test Categories

### 1. Unit Tests (`@pytest.mark.unit`)

**Purpose**: Test individual functions, methods, and classes in isolation.

**Characteristics**:
- Fast execution (< 1 second per test)
- No external dependencies (database, network, files)
- Use mocks for external services
- Test edge cases and error conditions

**Location**: `tests/test_*.py`

**Examples**:
- `test_strategic_ai.py` - AI order generation logic
- `test_database_service.py` - Database operations with mocked sessions
- `test_response_cache.py` - Cache TTL, LRU eviction, thread safety

### 2. Integration Tests (`@pytest.mark.integration`)

**Purpose**: Test interactions between multiple modules and components.

**Characteristics**:
- Slower execution (1-10 seconds per test)
- May use real database connections
- Test complete workflows
- Verify data flow between components

**Examples**:
- Full game lifecycle (create → play → finish)
- API endpoint + database + engine integration
- Telegram bot + server + database integration

### 3. Slow Tests (`@pytest.mark.slow`)

**Purpose**: Tests that take significant time or resources.

**Characteristics**:
- Execution time > 10 seconds
- May involve complex scenarios
- Run separately from fast test suite
- Include performance benchmarks

**Examples**:
- Large-scale game simulations
- Performance stress tests
- Complex AI strategy evaluation

### 4. Database Tests (`@pytest.mark.database`)

**Purpose**: Tests requiring database access.

**Characteristics**:
- Use test database (PostgreSQL test databases)
- Clean up after each test
- Test transactions, constraints, and data integrity

**Examples**:
- Database service CRUD operations
- Game state persistence
- Order history tracking

### 5. Telegram Tests (`@pytest.mark.telegram`)

**Purpose**: Tests involving Telegram bot functionality.

**Characteristics**:
- Mock Telegram API calls
- Test message handling and callbacks
- Verify bot state management

**Examples**:
- Bot command processing
- Interactive order submission
- Error message formatting

### 6. Map Tests (`@pytest.mark.map`)

**Purpose**: Tests requiring map files or rendering.

**Characteristics**:
- May require SVG map files
- Test map generation and visualization
- Verify province adjacencies

**Examples**:
- Map rendering quality
- Order visualization
- Province validation

### 7. Execution Context Tests (`@pytest.mark.execution_context`)

**Purpose**: Tests that verify code works when executed in production-like contexts (as scripts, with different PYTHONPATH, etc.)

**Characteristics**:
- Test script execution (not just module imports)
- Verify imports work with production PYTHONPATH
- Test package structure compatibility
- Simulate systemd service execution

**Examples**:
- `test_execution_context.py` - Tests telegram_bot.py can be executed as a script
- Tests that verify imports work in different working directories
- Tests for relative vs absolute imports

### 8. Deployment/Infrastructure Tests (`@pytest.mark.deployment`, `@pytest.mark.infrastructure`)

**Purpose**: Tests deployment scripts and infrastructure configuration.

**Characteristics**:
- Test systemd service file generation
- Test Nginx configuration
- Test deployment script syntax and logic
- Verify infrastructure setup

**Examples**:
- `test_deployment_infrastructure.py` - Tests systemd, Nginx, and deployment scripts
- Tests for service file correctness
- Tests for deployment script error handling

## Core Behaviours to Test

### Game Engine Core Behaviours

#### 1. Order Adjudication (PRIORITY: CRITICAL - MUST-HAVE)
- **Move Resolution**: Units move correctly, bounce on equal strength, dislodge on higher strength
- **Support Calculation**: Support orders add strength correctly, support cutting works
- **Convoy Resolution**: Convoy chains work correctly, convoy disruption prevents moves
- **Self-Dislodgement Prevention**: Power cannot dislodge its own units (both units hold)
- **Standoff Detection**: Equal strength attacks result in bounces
- **Retreat Resolution**: Dislodged units retreat correctly or disband if no valid retreats
- **Build/Destroy Logic**: Builds match supply center count, destroys match unit excess

#### 2. Game State Management (PRIORITY: CRITICAL - MUST-HAVE)
- **State Consistency**: Units, supply centers, and orders remain consistent
- **Phase Transitions**: Movement → Retreat → Builds transitions correctly
- **Turn Advancement**: Year/season increment correctly (Spring → Autumn → Spring+1)
- **Victory Conditions**: Game ends when power controls 18+ supply centers
- **Elimination**: Powers with no units/supply centers are marked eliminated

#### 3. Order Validation (PRIORITY: CRITICAL - MUST-HAVE)
- **Syntax Validation**: Orders parse correctly from text format
- **Semantic Validation**: Orders are valid for current game state
- **Phase Compatibility**: Order types match current phase (movement in Movement, retreats in Retreat, etc.)
- **Power Ownership**: Orders can only be submitted for units owned by the power
- **Adjacency Validation**: Moves respect province adjacencies and unit type constraints
- **Coast Validation**: Fleet moves respect coast requirements for multi-coast provinces

#### 4. Map and Province Logic (PRIORITY: HIGH - MUST-HAVE)
- **Province Loading**: Map files load correctly with all provinces and adjacencies
- **Adjacency Calculation**: Correct adjacencies for armies (land/coastal) and fleets (sea/coastal)
- **Supply Center Tracking**: Supply center ownership updates correctly after moves
- **Home Supply Centers**: Initial supply centers assigned correctly per power
- **Multi-Coast Handling**: Multi-coast provinces (e.g., Spain, Bulgaria) handled correctly

### Server/API Core Behaviours

#### 5. Game Lifecycle Management (PRIORITY: CRITICAL - MUST-HAVE)
- **Game Creation**: Games created with correct initial state
- **Player Management**: Players can join/quit/replace powers correctly
- **Order Submission**: Orders submitted via API persist correctly
- **Turn Processing**: Turn processing advances game state correctly
- **Game State Retrieval**: Game state returned accurately via API

#### 6. Authorization and Security (PRIORITY: CRITICAL - MUST-HAVE)
- **Power Ownership**: Users can only submit orders for their assigned power
- **Authentication**: API endpoints require proper authentication where needed
- **Authorization Checks**: 403 errors returned for unauthorized actions
- **User Registration**: Users must register before joining games
- **Session Management**: User sessions tracked correctly

#### 7. Database Persistence (PRIORITY: HIGH - MUST-HAVE)
- **Game State Persistence**: Game state saved and loaded correctly
- **Order History**: Order history tracked across turns
- **User Data**: User registration and power assignments persist
- **Message History**: Messages stored and retrieved correctly
- **Transaction Integrity**: Database transactions complete or rollback correctly

### Telegram Bot Core Behaviours

#### 8. Command Processing (PRIORITY: HIGH - MUST-HAVE)
- **Command Parsing**: All bot commands parse correctly
- **Interactive Orders**: `/selectunit` shows units and possible moves
- **Order Submission**: Orders submitted via bot persist correctly
- **Error Messages**: Clear error messages for invalid commands/orders
- **Multi-Game Handling**: Bot handles users in multiple games correctly

#### 9. User Interface (PRIORITY: MEDIUM - NICE-TO-HAVE)
- **Button Callbacks**: Inline keyboard buttons work correctly
- **Message Formatting**: Messages formatted clearly with emojis and structure
- **Map Generation**: Map images generated and sent correctly
- **Help Commands**: Help text accurate and helpful

## Critical Use Cases and Edge Cases

### Game Engine Edge Cases

#### 1. Adjudication Edge Cases (PRIORITY: CRITICAL - MUST-HAVE)
- **Circular Supports**: A supports B, B supports C, C supports A (all hold)
- **Convoy Disruption**: Convoy disrupted by attack on convoying fleet
- **Multiple Supports**: Unit receives support from multiple units
- **Self-Support**: Unit supports its own move (invalid)
- **Support Cut by Move**: Supporting unit moves, cutting its own support
- **Convoy Chain Disruption**: One fleet in convoy chain attacked, entire chain fails
- **Retreat to Dislodged Province**: Retreat to province that was dislodged (invalid)
- **Retreat to Attacking Province**: Retreat to province of attacking unit (invalid)
- **Build on Occupied Province**: Attempt to build where unit exists (invalid)
- **Destroy Non-Existent Unit**: Attempt to destroy unit that doesn't exist (invalid)
- **Build/Destroy Count Mismatch**: Build/destroy orders don't match supply center count

#### 2. Phase Transition Edge Cases (PRIORITY: CRITICAL - MUST-HAVE)
- **No Dislodgements**: Movement phase with no dislodgements → skip Retreat phase
- **All Units Disband**: All dislodged units disband → skip Retreat phase
- **Spring with Dislodgements**: Spring Movement → Retreat → Autumn Movement
- **Autumn with Dislodgements**: Autumn Movement → Retreat → Builds
- **Autumn without Dislodgements**: Autumn Movement → Builds (skip Retreat)
- **Builds Phase**: After Builds → next Spring Movement, year increments
- **First Turn**: S1901M (no previous state)
- **Victory During Movement**: Power reaches 18 SCs during movement phase
- **Victory During Builds**: Power reaches 18 SCs after builds

#### 3. Order Validation Edge Cases (PRIORITY: HIGH - MUST-HAVE)
- **Invalid Province Names**: Orders with non-existent provinces
- **Wrong Unit Type**: Army order for fleet position or vice versa
- **Coast Mismatch**: Fleet order without required coast specification
- **Duplicate Orders**: Multiple orders for same unit
- **Order for Non-Existent Unit**: Order for unit that doesn't exist
- **Order for Wrong Power**: Order submitted for another power's unit
- **Order in Wrong Phase**: Movement order in Retreat phase, etc.
- **Convoy Order Without Convoy Path**: Convoy order where no path exists
- **Support Order for Non-Move**: Support order for unit that's holding
- **Move to Own Province**: Move to province already occupied by own unit

#### 4. Map Edge Cases (PRIORITY: MEDIUM - NICE-TO-HAVE)
- **Multi-Coast Provinces**: Spain (NC/SC), Bulgaria (EC/SC), St. Petersburg (NC/SC)
- **Landlocked Provinces**: Provinces with no sea access
- **Isolated Sea Provinces**: Sea provinces with limited connections
- **Supply Center on Border**: Supply centers shared between powers initially
- **Special Adjacencies**: Special cases like Kiel, Constantinople, etc.

### Server/API Edge Cases

#### 5. Game Management Edge Cases (PRIORITY: HIGH - MUST-HAVE)
- **Game Not Found**: API calls for non-existent game ID
- **Power Already Taken**: Attempt to join game with taken power
- **Power Not Found**: Attempt to submit orders for non-existent power
- **Game Already Started**: Attempt to join game that's already in progress
- **User Already in Game**: Attempt to join game user is already in
- **Replace Inactive Power**: Replace power that's inactive/vacated
- **Process Turn Without Orders**: Process turn when no orders submitted
- **Process Turn in Wrong Phase**: Attempt to process turn in Retreat/Builds phase

#### 6. Order Submission Edge Cases (PRIORITY: HIGH - MUST-HAVE)
- **Empty Order List**: Submit empty order list (should clear orders)
- **Partial Order Submission**: Submit orders for some but not all units
- **Order for Eliminated Power**: Submit orders for eliminated power
- **Order After Turn Processed**: Submit orders after turn already processed
- **Concurrent Order Submission**: Multiple users submit orders simultaneously
- **Order Clear**: Clear orders and resubmit

#### 7. Database Edge Cases (PRIORITY: MEDIUM - NICE-TO-HAVE)
- **Database Connection Loss**: Handle database disconnection gracefully
- **Concurrent Writes**: Multiple processes write to database simultaneously
- **Transaction Rollback**: Failed transaction rolls back correctly
- **Orphaned Records**: Clean up orphaned game/order records
- **Database Migration**: Handle schema changes during runtime

### Telegram Bot Edge Cases

#### 8. Bot Command Edge Cases (PRIORITY: MEDIUM - NICE-TO-HAVE)
- **User Not Registered**: Commands from unregistered users
- **User in No Games**: Commands when user has no active games
- **User in Multiple Games**: Commands when game_id ambiguous
- **Invalid Game ID**: Commands with non-existent game ID
- **Malformed Orders**: Orders with syntax errors
- **Button Callback Timeout**: Callback queries that expire
- **Concurrent Button Presses**: Multiple button presses simultaneously

## Error Conditions

### Game Engine Error Conditions

#### 1. Validation Errors (PRIORITY: CRITICAL - MUST-HAVE)
- **InvalidOrderError**: Order fails validation (syntax, semantics, phase)
- **PowerNotFoundError**: Power doesn't exist in game
- **UnitNotFoundError**: Unit doesn't exist for power
- **ProvinceNotFoundError**: Province doesn't exist on map
- **InvalidPhaseError**: Order type not valid for current phase
- **InvalidMoveError**: Move violates adjacency or unit type rules
- **InvalidRetreatError**: Retreat to invalid province
- **InvalidBuildError**: Build violates rules (occupied, wrong count, etc.)
- **InvalidDestroyError**: Destroy violates rules (unit doesn't exist, wrong count)

#### 2. State Consistency Errors (PRIORITY: CRITICAL - MUST-HAVE)
- **StateInconsistencyError**: Game state violates invariants (multiple units in province, etc.)
- **PhaseMismatchError**: Phase doesn't match expected state
- **SupplyCenterMismatchError**: Unit count doesn't match supply center count (outside Builds phase)
- **OrderCountMismatchError**: Order count doesn't match unit count

### Server/API Error Conditions

#### 3. HTTP Error Responses (PRIORITY: CRITICAL - MUST-HAVE)
- **400 Bad Request**: Invalid request format, missing required fields
- **403 Forbidden**: User not authorized for action (wrong power, not in game)
- **404 Not Found**: Game, power, user, or resource not found
- **409 Conflict**: Resource conflict (power already taken, user already in game)
- **500 Internal Server Error**: Unexpected server errors, database failures

#### 4. API-Specific Errors (PRIORITY: HIGH - MUST-HAVE)
- **GAME_NOT_FOUND**: Game ID doesn't exist
- **POWER_NOT_FOUND**: Power doesn't exist in game
- **POWER_ALREADY_EXISTS**: Power already assigned to user
- **INVALID_ORDER**: Order fails validation
- **MISSING_ARGUMENTS**: Required arguments missing from request
- **UNAUTHORIZED**: User not authenticated or authorized
- **INTERNAL_ERROR**: Unexpected server error

### Telegram Bot Error Conditions

#### 5. Bot-Specific Errors (PRIORITY: MEDIUM - NICE-TO-HAVE)
- **UserNotRegisteredError**: User must register before using bot
- **GameNotFoundError**: Game ID doesn't exist or user not in game
- **PowerNotAssignedError**: User doesn't control any power in game
- **OrderParseError**: Order text cannot be parsed
- **OrderValidationError**: Order fails game validation
- **APIError**: API server unavailable or returns error

## State Transitions

### Game Phase State Machine (PRIORITY: CRITICAL - MUST-HAVE)

#### 1. Normal Phase Flow
```
S1901M (Spring Movement)
  → [if dislodgements] S1901R (Spring Retreat)
  → A1901M (Autumn Movement)
  → [if dislodgements] A1901R (Autumn Retreat)
  → A1901B (Autumn Builds)
  → S1902M (Spring Movement, year increments)
```

#### 2. Phase Transition Conditions
- **Movement → Retreat**: Only if units dislodged
- **Movement → Movement**: Spring → Autumn (no dislodgements)
- **Movement → Builds**: Autumn → Builds (no dislodgements)
- **Retreat → Movement**: Spring Retreat → Autumn Movement
- **Retreat → Builds**: Autumn Retreat → Builds
- **Builds → Movement**: Always → next Spring Movement (year increments)

#### 3. Game Status Transitions
```
FORMING → ACTIVE (when game starts)
ACTIVE → PAUSED (admin action)
PAUSED → ACTIVE (admin action)
ACTIVE → COMPLETED (victory condition met)
```

#### 4. Power State Transitions
```
ACTIVE → INACTIVE (player quits, no orders)
INACTIVE → ACTIVE (player replaces)
ACTIVE → ELIMINATED (no units and no supply centers)
```

### Order State Transitions (PRIORITY: HIGH - MUST-HAVE)

#### 5. Order Lifecycle
```
PENDING → SUBMITTED (when order submitted)
SUBMITTED → SUCCESS (when order executes successfully)
SUBMITTED → FAILED (when order fails validation)
SUBMITTED → BOUNCED (when move bounces)
```

### Unit State Transitions (PRIORITY: CRITICAL - MUST-HAVE)

#### 6. Unit Dislodgement Flow
```
NORMAL → DISLODGED (when attacked with higher strength)
DISLODGED → RETREATING (retreat order submitted)
RETREATING → NORMAL (retreat successful) OR ELIMINATED (retreat fails/disbands)
```

## Priority Ordering

### Must-Have Tests (P0 - Critical)

These tests are **essential** for the system to function correctly. All must pass before any release.

1. **Order Adjudication Core Logic**
   - Move resolution with strength calculation
   - Support calculation and cutting
   - Convoy resolution and disruption
   - Self-dislodgement prevention
   - Standoff detection

2. **Game State Consistency**
   - State validation (no duplicate units, correct counts)
   - Phase transitions
   - Turn/year advancement
   - Victory condition detection

3. **Order Validation**
   - Syntax parsing
   - Semantic validation
   - Phase compatibility
   - Power ownership

4. **API Core Functionality**
   - Game creation and management
   - Order submission and retrieval
   - Turn processing
   - Authorization checks

5. **State Transitions**
   - All phase transitions
   - Game status transitions
   - Unit dislodgement flow

### Should-Have Tests (P1 - High Priority)

These tests are **important** for reliability and user experience. Should be implemented soon after P0.

1. **Edge Cases in Adjudication**
   - Circular supports
   - Complex convoy chains
   - Multiple simultaneous supports
   - Retreat edge cases

2. **Error Handling**
   - All error conditions return correct HTTP status codes
   - Error messages are clear and helpful
   - Invalid inputs handled gracefully

3. **Database Persistence**
   - Game state persistence
   - Order history tracking
   - User data persistence
   - Transaction integrity

4. **Telegram Bot Core Commands**
   - Command parsing
   - Order submission via bot
   - Interactive order selection
   - Error message formatting

### Nice-to-Have Tests (P2 - Medium Priority)

These tests improve quality and maintainability but are not blocking for releases.

1. **Performance Testing**
   - Response time benchmarks
   - Load testing with multiple concurrent users
   - Database query performance

2. **UI/UX Testing**
   - Button callback handling
   - Message formatting quality
   - Map generation quality
   - Help text accuracy

3. **Advanced Edge Cases**
   - Multi-coast province handling
   - Special adjacency cases
   - Complex game scenarios

4. **Infrastructure Testing**
   - Deployment script validation
   - Systemd service configuration
   - Nginx configuration

### Future Enhancements (P3 - Low Priority)

These are planned improvements that can be added over time.

1. **Property-Based Testing**
   - Hypothesis-based test generation
   - Fuzz testing for order parsing

2. **Visual Regression Testing**
   - Map rendering comparison
   - UI screenshot comparison

3. **End-to-End Service Testing**
   - Full systemd service startup
   - Container-based testing
   - Production-like environment testing

## Test Implementation Priority

### Phase 1: Critical Path (Week 1)
- Order adjudication core logic
- Game state consistency
- Basic phase transitions
- API core endpoints
- Authorization checks

### Phase 2: Reliability (Week 2-3)
- Edge cases in adjudication
- Error handling comprehensive coverage
- Database persistence
- Telegram bot core commands

### Phase 3: Quality (Week 4+)
- Performance testing
- UI/UX testing
- Advanced edge cases
- Infrastructure testing

## Running Tests

### Quick Test Run (Unit Tests Only)
```bash
./infra/scripts/run_tests_fast.sh
```

### Full Test Suite
```bash
./infra/scripts/run_tests.sh
```

### Specific Test Categories
```bash
# Integration tests only
pytest -m integration

# Database tests only
pytest -m database

# Slow tests only
pytest -m slow

# Execution context tests
pytest -m execution_context

# Deployment tests
pytest -m deployment

# Infrastructure tests
pytest -m infrastructure

# Multiple categories
pytest -m "unit or integration"
```

### With Coverage

Run tests with coverage from the project root (`new_implementation/`):

```bash
cd new_implementation
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:htmlcov
```

Then open `htmlcov/index.html` for line-by-line coverage. Alternatively use the test runner with coverage (requires `pytest-cov`):

```bash
./infra/scripts/run_tests.sh   # uses coverage if pytest-cov is installed
```

**Real-situation tests**: When testing adjacency, valid moves, or support/convoy logic, use `Game('standard')` (or state derived from it) so adjacency comes from the loaded map, not hand-built data.

## Test Configuration

### pytest.ini
- Test discovery patterns
- Coverage settings
- Markers for test categorization
- Output formatting

### conftest.py
- Shared fixtures for all tests
- Database setup/teardown
- Mock configurations

## Test Fixtures

### Database Fixtures
- `temp_db`: Temporary PostgreSQL database
- `db_session`: Database session for testing
- `mock_session_factory`: Mocked database sessions

### Game Fixtures
- `standard_game`: Standard Diplomacy game setup
- `mid_game_state`: Mid-game state with units
- `sample_orders`: Sample order data

### Bot Fixtures
- `mock_telegram_context`: Mock Telegram bot context
- `mock_telegram_update`: Mock Telegram update object

### Utility Fixtures
- `cleanup_temp_files`: Cleanup temporary files
- `test_data_dir`: Path to test data directory

## Coverage Requirements

### Minimum Coverage: 85%
- Critical modules (engine, server): >95%
- Utility modules: >80%
- Test files: Excluded from coverage

### Coverage Reports
- Terminal: `--cov-report=term-missing`
- HTML: `--cov-report=html:htmlcov`
- XML: `--cov-report=xml` (for CI/CD)

To enforce a minimum coverage in CI, uncomment the coverage lines in `pytest.ini` (e.g. `--cov=src`, `--cov-report=term-missing`, `--cov-report=html:htmlcov`, `--cov-fail-under=85`) once the baseline is acceptable.

## Test Coverage Gaps and Improvements

### Critical Gaps Identified

#### 1. Execution Context Testing

**Problem**: Tests run in a development context (pytest, direct Python execution) but production runs as a systemd service with different import paths and execution contexts.

**What's Missing**:
- Tests that verify imports work when running as a script (not a module)
- Tests that verify package structure works in different execution contexts
- Tests that simulate systemd service execution
- Tests that verify `__main__` execution paths

**Solution**: Added `test_execution_context.py` with tests for:
- Script execution with different PYTHONPATH configurations
- Package structure compatibility
- Import path resolution in different contexts
- Service execution simulation

#### 2. Deployment/Infrastructure Testing

**Problem**: No tests for deployment scripts, systemd configurations, or infrastructure setup.

**What's Missing**:
- Tests for `deploy_app.sh` script
- Tests for systemd service file generation
- Tests for Nginx configuration generation
- Tests for environment variable setup
- Tests for file permissions and ownership

**Solution**: Added `test_deployment_infrastructure.py` with tests for:
- Systemd service configuration validation
- Nginx configuration validation
- Deployment script syntax and logic
- Wrapper script functionality

#### 3. Package Structure Testing

**Problem**: Tests import modules directly but don't verify the package structure works when modules are imported differently.

**Solution**: Added tests that verify:
- `server.telegram_bot` package can be imported
- `telegram_bot.py` file doesn't conflict with `telegram_bot/` package
- Import resolution in different contexts
- Relative vs absolute imports

#### 4. End-to-End Service Testing

**Problem**: Tests verify individual components but not the full service startup and execution.

**Recommendation**: Future improvement - use systemd-nspawn or containers to test actual service startup.

### New Test Files Added

#### `test_execution_context.py`

**Purpose**: Tests that verify code works when executed in production-like contexts.

**Test Classes**:
- **`TestTelegramBotExecutionContext`**: Tests that telegram_bot.py can be executed as a script
- **`TestPackageStructure`**: Tests package structure compatibility
- **`TestImportPaths`**: Tests imports with different PYTHONPATH configurations
- **`TestServiceExecution`**: Tests service execution contexts

#### `test_deployment_infrastructure.py`

**Purpose**: Tests deployment scripts and infrastructure configuration.

**Test Classes**:
- **`TestSystemdServiceConfiguration`**: Tests systemd service file generation
- **`TestNginxConfiguration`**: Tests Nginx configuration
- **`TestDeployScript`**: Tests deploy_app.sh script
- **`TestWrapperScript`**: Tests run_telegram_bot.py wrapper
- **`TestDeploymentScriptExecution`**: Integration tests for script syntax

## CI/CD Integration

### GitHub Actions Workflow
- Runs on every push and pull request
- Tests Python 3.13
- Generates coverage reports
- Comments coverage on PRs
- Fails if coverage < 85%

### Security Scanning
- Safety check for known vulnerabilities
- Bandit security linting
- Dependency scanning

## Adding New Tests

### 1. Create Test File
```python
# tests/test_new_module.py
import pytest
from src.module import NewClass

@pytest.mark.unit
class TestNewClass:
    def test_basic_functionality(self):
        obj = NewClass()
        assert obj.method() == expected_result
```

### 2. Add Appropriate Markers
```python
@pytest.mark.integration
def test_full_workflow():
    # Test complete workflow
    pass

@pytest.mark.database
def test_database_operation():
    # Test database operations
    pass
```

### 3. Use Existing Fixtures
```python
def test_with_database(db_session):
    # Use database session fixture
    pass

def test_with_game_state(mid_game_state):
    # Use game state fixture
    pass
```

### 4. Add to CI/CD
- Tests run automatically on commit
- No additional configuration needed

## Mock Guidelines

### When to Mock
- External services (Telegram API, database)
- File system operations
- Network requests
- Random number generation (for deterministic tests)

### Mock Patterns
```python
@patch('src.module.external_function')
def test_with_mock(mock_external):
    mock_external.return_value = "mocked_value"
    # Test code
    mock_external.assert_called_once()
```

## Performance Testing

### Benchmark Tests
```python
@pytest.mark.slow
def test_performance_benchmark():
    import time
    start = time.time()
    # Perform operation
    duration = time.time() - start
    assert duration < 1.0  # Should complete in < 1 second
```

### Load Testing
- Test with multiple concurrent users
- Verify system stability under load
- Measure response times

## Debugging Tests

### Verbose Output
```bash
pytest -v -s  # Verbose with print statements
```

### Single Test
```bash
pytest tests/test_module.py::TestClass::test_method
```

### Debug Mode
```bash
pytest --pdb  # Drop into debugger on failure
```

## Test Data Management

### Test Data Directory
- `test_data/`: Static test files
- `test_maps/`: Generated test outputs
- Use fixtures for dynamic test data

### Data Cleanup
- Automatic cleanup via fixtures
- Temporary files removed after tests
- Database state reset between tests

## Best Practices

### Test Naming
- Use descriptive test names
- Include expected behavior
- Group related tests in classes

### Test Structure
- Arrange-Act-Assert pattern
- One assertion per test (when possible)
- Clear setup and teardown

### Error Testing
- Test both success and failure cases
- Verify error messages are helpful
- Test edge cases and boundary conditions

### Documentation
- Document complex test scenarios
- Explain why tests are needed
- Update tests when requirements change

## Troubleshooting

### Common Issues

**Tests not discovered**:
- Check file naming (`test_*.py`)
- Verify `__init__.py` in test directories
- Check pytest configuration

**Import errors**:
- Verify Python path setup
- Check module imports
- Use absolute imports

**Database issues**:
- Ensure test database is created
- Check transaction handling
- Verify cleanup after tests

**Coverage issues**:
- Check source path configuration
- Verify exclusions are correct
- Run coverage with appropriate markers

### Getting Help
- Check test output for specific errors
- Use verbose mode for detailed information
- Review existing test patterns
- Consult pytest documentation

## Telegram Bot Testing

### Available Test Scripts

#### `bot_test_runner.py` - Comprehensive Testing Framework
The main testing framework that can test any bot functionality.

**Usage**:
```bash
# Test everything
python3 tests/bot_test_runner.py --test all

# Test specific functionality
python3 tests/bot_test_runner.py --test selectunit
python3 tests/bot_test_runner.py --test button_callbacks
python3 tests/bot_test_runner.py --test help
python3 tests/bot_test_runner.py --test api
```

**What it tests**:
- `/selectunit` command (both message and callback contexts)
- Button callbacks (Submit Interactive Orders, etc.)
- Help command
- API functions
- Error scenarios (no games, multiple games)

#### Testing via API (Without Bot Token)

To test Telegram bot functionality via direct API calls:

1. **Start the API Server**:
   ```bash
   python infra/scripts/start_api_server.py
   ```

2. **Run Comprehensive Tests**:
   ```bash
   python test_telegram_bot_comprehensive.py
   ```

3. **Test Order Normalization**:
   ```bash
   python test_order_normalization.py
   ```

**API Endpoints Tested**:
- Game Management: Create, join, list players, get state
- Orders: Submit, retrieve, history
- Messaging: Private messages, broadcasts
- User Management: Registration, info retrieval
- Health & Status: Health checks, scheduler status

## Future Enhancements

### Planned Improvements
- Property-based testing with Hypothesis
- Visual regression testing for maps
- Performance profiling integration
- Test result analytics
- Full service startup tests using systemd-nspawn or containers
- Terraform configuration testing
- End-to-end deployment tests in test environment

### Monitoring
- Track test execution times
- Monitor coverage trends
- Alert on test failures
- Performance regression detection

---

This testing strategy ensures the Diplomacy implementation maintains high quality and reliability as it evolves. All team members should follow these guidelines when adding new features or fixing bugs.
