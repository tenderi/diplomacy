#!/bin/bash
# Fast test runner for unit tests only (no integration/slow tests)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$PROJECT_ROOT/src/tests"

echo -e "${BLUE}⚡ Fast Test Runner (Unit Tests Only)${NC}"
echo "======================================"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Please install requirements:${NC}"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Parse command line arguments
VERBOSE=false
FAIL_FAST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --fail-fast|-x)
            FAIL_FAST=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Fast test runner for unit tests only (excludes integration and slow tests)"
            echo ""
            echo "Options:"
            echo "  --verbose, -v   Verbose output"
            echo "  --fail-fast, -x Stop on first failure"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run unit tests quickly"
            echo "  $0 --verbose         # Run with verbose output"
            echo "  $0 --fail-fast -v    # Stop on first failure with verbose output"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command for unit tests only
PYTEST_CMD="pytest -m unit"

# Add verbosity
if [[ "$VERBOSE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -v -s"
fi

# Add fail-fast
if [[ "$FAIL_FAST" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -x"
fi

# Add test directory
PYTEST_CMD="$PYTEST_CMD $TEST_DIR"

echo -e "${BLUE}📁 Test directory:${NC} $TEST_DIR"
echo -e "${BLUE}⚡ Mode:${NC} Unit tests only (fast)"
echo ""

# Run tests
echo -e "${BLUE}🚀 Running unit tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

# Execute the command
if eval $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All unit tests passed!${NC}"
    echo ""
    echo -e "${YELLOW}💡 For full test suite with coverage, run:${NC}"
    echo "  ./run_tests.sh"
    echo ""
    echo -e "${YELLOW}💡 For integration tests, run:${NC}"
    echo "  ./run_tests.sh --integration"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some unit tests failed!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  - Run with --verbose for more details"
    echo "  - Run with --fail-fast to stop on first failure"
    echo "  - Check individual test files for specific failures"
    echo ""
    exit 1
fi
