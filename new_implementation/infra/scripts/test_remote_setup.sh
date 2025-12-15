#!/bin/bash

# Integration test script for remote environment validation
# This script runs comprehensive tests to verify the remote server environment
# is correctly configured for running the Diplomacy application.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
FAIL_ON_WARNINGS=false
SKIP_TESTS=false
TEST_ONLY=false

for arg in "$@"; do
    case $arg in
        --fail-on-warnings)
            FAIL_ON_WARNINGS=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --test-only)
            TEST_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--fail-on-warnings] [--skip-tests] [--test-only]"
            echo ""
            echo "Options:"
            echo "  --fail-on-warnings    Treat warnings as errors"
            echo "  --skip-tests          Skip running tests (not recommended)"
            echo "  --test-only           Run tests without deployment checks"
            exit 0
            ;;
        *)
            ;;
    esac
done

if [ "$SKIP_TESTS" = true ]; then
    echo -e "${YELLOW}⚠️  Tests skipped (--skip-tests flag)${NC}"
    exit 0
fi

echo -e "${BLUE}=== Remote Environment Validation ===${NC}"

# Find project root
PROJECT_ROOT="/opt/diplomacy"
if [ ! -d "$PROJECT_ROOT" ]; then
    # Try to find it from script location
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
fi

if [ ! -d "$PROJECT_ROOT" ] || [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${RED}Error: Could not find project root directory${NC}"
    exit 1
fi

echo -e "${GREEN}Project root: $PROJECT_ROOT${NC}"

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_WARNINGS=0

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    local is_critical="${3:-true}"
    
    echo -e "${YELLOW}Running: $test_name${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ $test_name passed${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        if [ "$is_critical" = "true" ]; then
            echo -e "${RED}✗ $test_name failed (CRITICAL)${NC}"
            ((TESTS_FAILED++))
            return 1
        else
            echo -e "${YELLOW}⚠ $test_name failed (WARNING)${NC}"
            ((TESTS_WARNINGS++))
            if [ "$FAIL_ON_WARNINGS" = true ]; then
                return 1
            fi
            return 0
        fi
    fi
}

# Test 1: Python version
run_test "Python version check" \
    "python3 --version | grep -q 'Python 3\.[89]\|Python 3\.1[0-9]'" \
    true

# Test 2: Critical Python packages
run_test "Critical packages check" \
    "python3 -c 'import fastapi, sqlalchemy, telegram, PIL; print(\"OK\")'" \
    true

# Test 3: Project structure
run_test "Project structure check" \
    "[ -d \"$PROJECT_ROOT/src\" ] && [ -d \"$PROJECT_ROOT/maps\" ] && [ -f \"$PROJECT_ROOT/requirements.txt\" ]" \
    true

# Test 4: Map files
run_test "Map files check" \
    "[ -f \"$PROJECT_ROOT/maps/standard.svg\" ] && [ -r \"$PROJECT_ROOT/maps/standard.svg\" ]" \
    true

# Test 5: Test maps directory
run_test "Test maps directory" \
    "(mkdir -p \"$PROJECT_ROOT/test_maps\" 2>/dev/null || true) && [ -w \"$PROJECT_ROOT/test_maps\" ]" \
    true

# Test 6: Demo script
run_test "Demo script check" \
    "([ -f \"$PROJECT_ROOT/examples/demo_perfect_game.py\" ] || [ -f \"$PROJECT_ROOT/demo_perfect_game.py\" ])" \
    false

# Test 7: Source imports
run_test "Source module imports" \
    "cd \"$PROJECT_ROOT\" && PYTHONPATH=\"$PROJECT_ROOT/src:\$PYTHONPATH\" python3 -c 'from engine.map import Map; from engine.game import Game; print(\"OK\")'" \
    true

# Test 8: File permissions
run_test "File permissions check" \
    "[ -r \"$PROJECT_ROOT/src\" ] && [ -r \"$PROJECT_ROOT/maps\" ]" \
    true

# Test 9: Environment variables (non-critical)
run_test "Environment variables check" \
    "[ -n \"\$SQLALCHEMY_DATABASE_URL\" ] || echo 'SQLALCHEMY_DATABASE_URL not set (may be in .env file)'" \
    false

# Test 10: Run pytest tests if available
if [ -f "$PROJECT_ROOT/pytest.ini" ] && command -v pytest &> /dev/null; then
    run_test "Pytest environment tests" \
        "cd \"$PROJECT_ROOT\" && PYTHONPATH=\"$PROJECT_ROOT/src:\$PYTHONPATH\" python3 -m pytest tests/test_remote_environment.py -v --tb=short" \
        false
fi

# Test 11: Message formatting tests
if [ -f "$PROJECT_ROOT/pytest.ini" ] && command -v pytest &> /dev/null; then
    run_test "Telegram message formatting tests" \
        "cd \"$PROJECT_ROOT\" && PYTHONPATH=\"$PROJECT_ROOT/src:\$PYTHONPATH\" python3 -m pytest tests/test_telegram_messages.py -v --tb=short" \
        false
fi

# Summary
echo ""
echo -e "${BLUE}=== Test Summary ===${NC}"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [ $TESTS_WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Warnings: $TESTS_WARNINGS${NC}"
fi
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
fi

# Exit with appropriate code
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}❌ Critical tests failed!${NC}"
    exit 1
elif [ $TESTS_WARNINGS -gt 0 ] && [ "$FAIL_ON_WARNINGS" = true ]; then
    echo -e "${RED}❌ Warnings treated as errors!${NC}"
    exit 1
elif [ $TESTS_WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Some warnings detected (non-critical)${NC}"
    exit 0
else
    echo -e "${GREEN}✅ All tests passed!${NC}"
    exit 0
fi

