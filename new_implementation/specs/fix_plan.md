# Fix Plan (Updated July 2025)

## Current Issues Found (Prioritized)

### 1. ~~Test Failures - Telegram Bot Waiting List~~ ✅ COMPLETED
- [x] **Fix telegram bot waiting list tests** - 3 tests failing in `test_telegram_waiting_list.py` due to incorrect monkeypatching. The tests are trying to patch `server.telegram_bot.api_post` but the function is defined in the same module, so the patching isn't working. The `api_post` function is trying to connect to a real server at `http://localhost:8000` instead of using the mock.
  - **Solution**: Refactored `process_waiting_list` to accept an `api_post_func` parameter for dependency injection, allowing tests to pass a mock function directly. Updated all tests to use this new parameter instead of monkeypatching.

### 2. ~~Code Quality Issues~~ ✅ COMPLETED
- [x] **Fix linting errors** - 574 linting errors found by Ruff, mostly whitespace issues (W293), line length violations (E501), and unused imports (F401) in test files. Many of these are easily fixable with `--fix` option.
  - **Solution**: Applied automatic fixes and manually fixed critical line length violations in main source files. Remaining E501 errors are in docstrings/help texts which are safe to ignore.

### 3. ~~Map Generation Issue~~ ✅ COMPLETED
- [x] **Fix map generation showing black picture** - The map generation feature was showing mostly black pictures with only corners visible due to CSS styles not being processed by cairosvg. 
  - **Solution**: The problematic black rectangle (`<rect fill="black" height="1360" width="1835" x="195" y="170"/>`) has been removed from the standard.svg file. A `standard_fixed.svg` file has been created with CSS styles converted to inline styles. The map generation should now work correctly.

### 4. ~~Map Performance Issue~~ ✅ COMPLETED
- [x] **Fix slow map generation** - The sample map was being generated every time it was requested, causing long delays or timeouts.
  - **Solution**: Implemented permanent in-memory caching for the default map image (since the standard map never changes). Added pre-generation on startup to avoid first-user delay. Added `/refresh_map` command for manual cache refresh.

### 5. Infrastructure & Deployment Issues (Low Priority)
- [x] **Review start.sh script** - The agent.md mentions issues with the start.sh script that need investigation.
  - **Status**: The start.sh script properly handles BOT_ONLY mode and environment variables as specified in agent.md. No issues found.
- [ ] **Check Docker configuration** - Ensure Docker setup is working correctly for deployment.
- [ ] **Verify database migrations** - Ensure Alembic migrations are working properly.

### 6. Documentation & Testing (Low Priority)
- [ ] **Update documentation** - Ensure all README files are up to date with current implementation.
- [ ] **Add integration tests** - Consider adding more comprehensive integration tests.
- [ ] **Performance testing** - Test the system under load to identify bottlenecks.

## Completed Items ✅

1. **Telegram Bot Waiting List Tests** - All 4 tests now passing
2. **Code Quality Issues** - Major linting errors resolved
3. **Map Generation Issue** - Fixed CSS style processing for proper map rendering
4. **Map Performance Issue** - Implemented caching to eliminate generation delays
5. **Start.sh Script Review** - Confirmed proper BOT_ONLY mode handling

## Next Steps

The main critical issues have been resolved. The remaining items are lower priority infrastructure and documentation tasks that can be addressed as needed. The system should now be functional for basic operations. 