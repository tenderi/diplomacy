# Test Coverage Improvements

This document describes the new tests added to fill the coverage gaps identified in `TEST_COVERAGE_GAPS.md`.

## New Test Files

### 1. `test_execution_context.py` ✅

**Purpose**: Tests that verify code works when executed in production-like contexts (as scripts, with different PYTHONPATH, etc.)

**Test Classes**:

- **`TestTelegramBotExecutionContext`**: Tests that telegram_bot.py can be executed as a script
  - `test_telegram_bot_runs_as_script_with_pythonpath`: Verifies script execution with PYTHONPATH
  - `test_telegram_bot_wrapper_script_works`: Tests the wrapper script
  - `test_telegram_bot_imports_from_different_contexts`: Tests imports from different working directories

- **`TestPackageStructure`**: Tests package structure compatibility
  - `test_telegram_bot_package_and_file_coexist`: Verifies package and file don't conflict
  - `test_relative_imports_work_in_production_context`: Tests relative imports work

- **`TestImportPaths`**: Tests imports with different PYTHONPATH configurations
  - `test_imports_with_production_pythonpath`: Tests with production-like PYTHONPATH
  - `test_imports_without_explicit_pythonpath`: Tests with sys.path setup

- **`TestServiceExecution`**: Tests service execution contexts
  - `test_telegram_bot_main_function_importable`: Tests main() can be imported
  - `test_imports_dont_fail_in_service_context`: Tests all imports work in service context

### 2. `test_deployment_infrastructure.py` ✅

**Purpose**: Tests deployment scripts and infrastructure configuration

**Test Classes**:

- **`TestSystemdServiceConfiguration`**: Tests systemd service file generation
  - `test_systemd_service_file_exists_in_user_data`: Verifies service config exists
  - `test_diplomacy_service_has_correct_execstart`: Tests API service ExecStart
  - `test_telegram_bot_service_has_correct_execstart`: Tests bot service ExecStart
  - `test_telegram_bot_service_has_environment_file`: Tests EnvironmentFile
  - `test_services_have_correct_user`: Tests user configuration
  - `test_services_have_restart_policy`: Tests restart configuration

- **`TestNginxConfiguration`**: Tests Nginx configuration
  - `test_nginx_config_exists_in_user_data`: Verifies Nginx config exists
  - `test_nginx_has_dashboard_location`: Tests explicit /dashboard location
  - `test_nginx_proxies_to_localhost_8000`: Tests proxy configuration

- **`TestDeployScript`**: Tests deploy_app.sh script
  - `test_deploy_script_exists`: Verifies script exists
  - `test_deploy_script_is_executable`: Tests executable permissions
  - `test_deploy_script_has_shebang`: Tests shebang
  - `test_deploy_script_fixes_telegram_bot_service`: Tests service fix logic
  - `test_deploy_script_fixes_nginx_config`: Tests Nginx fix logic

- **`TestWrapperScript`**: Tests run_telegram_bot.py wrapper
  - `test_wrapper_script_exists`: Verifies wrapper exists
  - `test_wrapper_script_has_shebang`: Tests shebang
  - `test_wrapper_script_sets_pythonpath`: Tests PYTHONPATH setup
  - `test_wrapper_script_imports_telegram_bot_package`: Tests package import

- **`TestDeploymentScriptExecution`**: Integration tests (marked with @pytest.mark.integration)
  - `test_deploy_script_syntax_is_valid`: Tests bash syntax
  - `test_user_data_script_syntax_is_valid`: Tests user_data.sh syntax

## Running the New Tests

### Run All New Tests

```bash
# Execution context tests
pytest src/tests/test_execution_context.py -v

# Deployment/infrastructure tests
pytest src/tests/test_deployment_infrastructure.py -v

# Both together
pytest src/tests/test_execution_context.py src/tests/test_deployment_infrastructure.py -v
```

### Run Specific Test Categories

```bash
# Execution context tests only
pytest -m execution_context -v

# Deployment tests only
pytest -m deployment -v

# Infrastructure tests only
pytest -m infrastructure -v
```

### Run Integration Tests

```bash
# Deployment script syntax tests (integration)
pytest -m integration src/tests/test_deployment_infrastructure.py::TestDeploymentScriptExecution -v
```

## Test Markers

New pytest markers added to `pytest.ini`:

- `execution_context`: Tests for execution context (script vs module execution)
- `deployment`: Tests for deployment scripts and infrastructure
- `infrastructure`: Tests for infrastructure configuration (systemd, nginx, etc.)

## What These Tests Catch

### Execution Context Tests

✅ **Import errors when running as script**
- Would catch: `ModuleNotFoundError: No module named 'server.telegram_bot.config'`
- Would catch: `ImportError: attempted relative import with no known parent package`

✅ **Package structure conflicts**
- Would catch: Conflicts between `telegram_bot.py` file and `telegram_bot/` package
- Would catch: Relative import failures in `server.server`

✅ **PYTHONPATH issues**
- Would catch: Import failures with different PYTHONPATH configurations
- Would catch: Missing path setup in service configurations

### Deployment/Infrastructure Tests

✅ **Systemd service configuration errors**
- Would catch: Incorrect ExecStart commands
- Would catch: Missing EnvironmentFile
- Would catch: Wrong user or working directory

✅ **Nginx configuration errors**
- Would catch: Missing /dashboard location block
- Would catch: Incorrect proxy_pass configuration

✅ **Deployment script errors**
- Would catch: Bash syntax errors
- Would catch: Missing fix logic for services
- Would catch: Missing wrapper script

## Integration with CI/CD

These tests should be added to your CI/CD pipeline:

```yaml
# In .github/workflows/test.yml or similar
- name: Run execution context tests
  run: pytest -m execution_context -v

- name: Run deployment tests
  run: pytest -m deployment -v

- name: Run infrastructure tests
  run: pytest -m infrastructure -v
```

## Future Improvements

These tests provide a foundation, but could be extended with:

1. **Full Service Startup Tests**: Use systemd-nspawn or containers to test actual service startup
2. **Terraform Testing**: Test Terraform configurations
3. **End-to-End Deployment Tests**: Test full deployment process in a test environment
4. **Configuration Validation**: More comprehensive validation of generated configs

## Summary

These new tests fill the critical gaps identified in the test coverage analysis:

- ✅ Execution context testing
- ✅ Deployment/infrastructure testing
- ✅ Package structure testing
- ✅ Import path testing

The tests are designed to catch the types of issues that surfaced in production:
- Import errors in different execution contexts
- Service configuration issues
- Deployment script problems
- Package structure conflicts

Running these tests as part of the development and CI/CD process will help catch these issues before they reach production.

