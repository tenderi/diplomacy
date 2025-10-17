#!/bin/bash
# Unified test runner with coverage reporting for Diplomacy project

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
COVERAGE_DIR="$PROJECT_ROOT/htmlcov"
COVERAGE_XML="$PROJECT_ROOT/coverage.xml"

echo -e "${BLUE}🧪 Diplomacy Test Suite${NC}"
echo "=================================="

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo -e "${YELLOW}⚠️  Warning: No virtual environment detected${NC}"
    echo "Consider activating your virtual environment first:"
    echo "  source venv/bin/activate  # or similar"
    echo ""
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Please install requirements:${NC}"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Check if coverage is installed
if ! command -v coverage &> /dev/null; then
    echo -e "${RED}❌ coverage not found. Please install requirements:${NC}"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Parse command line arguments
RUN_INTEGRATION=false
RUN_SLOW=false
VERBOSE=false
FAIL_FAST=false
MARKERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --integration)
            RUN_INTEGRATION=true
            MARKERS="$MARKERS integration"
            shift
            ;;
        --slow)
            RUN_SLOW=true
            MARKERS="$MARKERS slow"
            shift
            ;;
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
            echo "Options:"
            echo "  --integration    Run integration tests (slower)"
            echo "  --slow          Run slow tests"
            echo "  --verbose, -v   Verbose output"
            echo "  --fail-fast, -x Stop on first failure"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run unit tests only"
            echo "  $0 --integration      # Run all tests including integration"
            echo "  $0 --slow --verbose   # Run slow tests with verbose output"
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"

# Add markers if specified
if [[ -n "$MARKERS" ]]; then
    PYTEST_CMD="$PYTEST_CMD -m \"unit or$MARKERS\""
else
    PYTEST_CMD="$PYTEST_CMD"  # Run all tests by default
fi

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
echo -e "${BLUE}📊 Coverage report:${NC} $COVERAGE_DIR"
echo ""

# Run tests
echo -e "${BLUE}🚀 Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

# Set PYTHONPATH to include src directory
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# Execute the command
if eval $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    
    # Show coverage summary
    echo ""
    echo -e "${BLUE}📊 Coverage Summary:${NC}"
    coverage report --show-missing
    
    # Open HTML coverage report if available
    if [[ -d "$COVERAGE_DIR" ]]; then
        echo ""
        echo -e "${BLUE}📈 HTML coverage report available at:${NC}"
        echo "  file://$COVERAGE_DIR/index.html"
        
        # Try to open in browser (optional)
        if command -v xdg-open &> /dev/null; then
            echo -e "${YELLOW}🌐 Opening coverage report in browser...${NC}"
            xdg-open "$COVERAGE_DIR/index.html" 2>/dev/null || true
        fi
    fi
    
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo ""
    echo -e "${YELLOW}💡 Tips:${NC}"
    echo "  - Run with --verbose for more details"
    echo "  - Run with --fail-fast to stop on first failure"
    echo "  - Check the HTML coverage report for uncovered code"
    echo ""
    exit 1
fi
