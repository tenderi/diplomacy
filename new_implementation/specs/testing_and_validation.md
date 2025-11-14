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
```bash
pytest --cov=src/engine --cov=src/server --cov-report=html
```

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
