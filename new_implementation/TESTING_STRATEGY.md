# Testing Strategy for Diplomacy Implementation

## Overview

This document outlines the comprehensive testing strategy for the Diplomacy Python implementation. Our testing approach ensures correctness, reliability, and maintainability through multiple layers of testing.

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

**Location**: `src/tests/test_*.py`

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
- Use test database (SQLite in-memory or separate PostgreSQL)
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

## Running Tests

### Quick Test Run (Unit Tests Only)
```bash
./run_tests_fast.sh
```

### Full Test Suite
```bash
./run_tests.sh
```

### Specific Test Categories
```bash
# Integration tests only
pytest -m integration

# Database tests only
pytest -m database

# Slow tests only
pytest -m slow

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

### .coveragerc
- Source paths to include/exclude
- Coverage thresholds
- Report formats

### conftest.py
- Shared fixtures for all tests
- Database setup/teardown
- Mock configurations

## Test Fixtures

### Database Fixtures
- `temp_db`: Temporary SQLite database
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

## CI/CD Integration

### GitHub Actions Workflow
- Runs on every push and pull request
- Tests Python 3.10, 3.11, 3.12
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
# src/tests/test_new_module.py
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
pytest src/tests/test_module.py::TestClass::test_method
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

## Future Enhancements

### Planned Improvements
- Property-based testing with Hypothesis
- Visual regression testing for maps
- Performance profiling integration
- Test result analytics

### Monitoring
- Track test execution times
- Monitor coverage trends
- Alert on test failures
- Performance regression detection

---

This testing strategy ensures the Diplomacy implementation maintains high quality and reliability as it evolves. All team members should follow these guidelines when adding new features or fixing bugs.
