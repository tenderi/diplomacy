# Diplomacy Development Plan - Current Priorities

## 🎯 HIGH PRIORITY - IMMEDIATE FIXES NEEDED

### 1. Production Deployment Issues 🔥
- **Fix Telegram bot connection errors** - Bot can't connect to API (localhost:8000 connection refused)
- **Fix map viewing functionality** - 500 error on `/games/{game_id}/state` endpoint
- **Fix database migration issues** - Alembic migrations failing due to import errors
- **Fix API endpoint routing** - Missing `/games` endpoint for listing games
- **Verify service startup** - Ensure both API and bot services start correctly

### 2. Import System Cleanup ✅ COMPLETED
- **Fixed all relative imports** - Server and engine modules now use proper relative imports
- **Fixed test import issues** - Critical test files updated to use full paths
- **Removed import conflicts** - Cleaned up `__init__.py` files to prevent conflicts
- **Verified all modules import correctly** - All key modules tested and working

## 🔧 MEDIUM PRIORITY - CODE QUALITY

### 3. Test Infrastructure Enhancements
- **Fix remaining test import issues** - Update remaining test files to use proper import paths
- **Convert manual test scripts to pytest** - Convert `bot_test_runner.py` to proper pytest tests
- **Add comprehensive API endpoint tests** - Test all REST API endpoints with proper fixtures
- **Enhance integration test coverage** - Add tests for full game workflows

### 4. Documentation and Type Safety
- **Add comprehensive type hints** - Run mypy validation on all modules
- **Add docstrings to public methods** - Complete API documentation
- **Update module documentation** - Ensure all modules have proper README files

## 🚀 LOW PRIORITY - FUTURE ENHANCEMENTS

### 5. Advanced Features
- **Enhance DAIDE protocol tests** - Add comprehensive tests for all message types
- **Improve order parser edge cases** - Add tests for complex order scenarios
- **Add performance tests** - Benchmark critical operations
- **Add security tests** - Test for common vulnerabilities

## 📊 CURRENT STATUS

### ✅ COMPLETED (Recent Fixes)
- **Import system** - All relative imports working correctly
- **Database migrations** - Alembic can run successfully
- **API server startup** - Server can start without import errors
- **Test infrastructure** - Core testing framework in place
- **Code organization** - Clean directory structure

### 🔄 IN PROGRESS
- **Production deployment** - Working on fixing bot connection issues
- **API endpoint fixes** - Resolving map viewing and game listing issues

### ⚠️ KNOWN ISSUES
- **Telegram bot registration** - Users can't register due to API connection issues
- **Map viewing** - 500 error when trying to view game maps
- **Game listing** - Missing endpoint for listing available games

## 🎯 SUCCESS CRITERIA

### Immediate (This Week)
- [ ] Telegram bot can register users successfully
- [ ] Map viewing works without errors
- [ ] All API endpoints respond correctly
- [ ] Services start reliably on deployment

### Short Term (Next 2 Weeks)
- [ ] All tests pass consistently
- [ ] Complete API endpoint test coverage
- [ ] Type hints added to all modules
- [ ] Documentation updated

### Long Term (Next Month)
- [ ] Performance benchmarks established
- [ ] Security testing implemented
- [ ] Advanced feature testing complete
- [ ] Production monitoring in place

## 🔧 DEVELOPMENT WORKFLOW

### Before Making Changes
1. Run tests: `./run_tests_fast.sh`
2. Check imports: `python -c "from src.server.api import app"`
3. Verify database: `python -m alembic check`

### After Making Changes
1. Run full test suite: `./run_tests.sh`
2. Test API endpoints locally
3. Deploy to staging environment
4. Test bot functionality end-to-end

### Deployment Checklist
- [ ] All imports working
- [ ] Database migrations applied
- [ ] Services starting correctly
- [ ] API endpoints responding
- [ ] Bot connecting to API
- [ ] Map viewing functional