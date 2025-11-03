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

# Check if coverage is installed (optional)
HAS_COVERAGE=false
if command -v coverage &> /dev/null; then
    HAS_COVERAGE=true
    echo -e "${GREEN}✅ Coverage tool found${NC}"
else
    echo -e "${YELLOW}⚠️  Coverage not found (optional)${NC}"
    echo "   Install with: pip install coverage pytest-cov"
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

# Set PYTHONPATH to include src directory FIRST (before schema initialization)
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# Set database URL if not already set (for integration tests)
# Use default local PostgreSQL connection if no .env file or env var exists
if [[ -z "$SQLALCHEMY_DATABASE_URL" ]] && [[ -z "$DIPLOMACY_DATABASE_URL" ]]; then
    # Try to load from .env file first
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        echo -e "${BLUE}📝 Loading database URL from .env file...${NC}"
        set -a  # automatically export all variables
        source "$PROJECT_ROOT/.env"
        set +a
    fi
    
    # If still not set, use default local PostgreSQL
    if [[ -z "$SQLALCHEMY_DATABASE_URL" ]] && [[ -z "$DIPLOMACY_DATABASE_URL" ]]; then
        export SQLALCHEMY_DATABASE_URL="postgresql+psycopg2://postgres@localhost:5432/postgres"
        echo -e "${YELLOW}⚠️  Using default database URL: ${SQLALCHEMY_DATABASE_URL}${NC}"
        echo "   Set SQLALCHEMY_DATABASE_URL or create .env file to customize"
    fi
fi

# Initialize database schema if needed (only if connection works)
# PYTHONPATH is already set above, but ensure it's available to the Python subprocess
echo -e "${BLUE}🔧 Checking database schema...${NC}"
PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH" python3 << PYTHON_SCRIPT
import sys
import os
# Ensure PROJECT_ROOT is in path (from environment or calculate)
project_root = os.environ.get('PROJECT_ROOT', os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, os.path.join(project_root, 'src'))
# Also try the direct path
sys.path.insert(0, os.path.join('${PROJECT_ROOT}', 'src'))

# Ensure environment variables are available
if 'SQLALCHEMY_DATABASE_URL' in os.environ:
    db_url_env = os.environ['SQLALCHEMY_DATABASE_URL']
elif 'DIPLOMACY_DATABASE_URL' in os.environ:
    db_url_env = os.environ['DIPLOMACY_DATABASE_URL']
else:
    db_url_env = None

try:
    from engine.database import Base, create_database_schema
    from sqlalchemy import create_engine, inspect
    
    db_url = db_url_env
    if db_url:
        engine = create_engine(db_url)
        
        # Test connection
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            print(f'⚠️  Could not connect to database: {e}')
            print('   Tests that require database will be skipped')
            sys.exit(0)
        
        # Check if schema exists and is complete
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            needs_schema_create = 'games' not in tables
            needs_column_update = False
            
            if 'users' in tables:
                # Check if users table has all required columns
                users_columns = [col['name'] for col in inspector.get_columns('users')]
                required_columns = ['is_active', 'created_at', 'updated_at']
                missing_columns = [col for col in required_columns if col not in users_columns]
                if missing_columns:
                    needs_column_update = True
            
            if needs_schema_create or needs_column_update:
                if needs_column_update:
                    print('📦 Updating database schema (adding missing columns)...')
                else:
                    print('📦 Creating database schema...')
                schema_engine = create_database_schema(db_url)
                # Dispose the engine to ensure connection is closed and committed
                schema_engine.dispose()
                
                # Verify with a fresh connection
                verify_engine = create_engine(db_url)
                verify_inspector = inspect(verify_engine)
                verify_tables = verify_inspector.get_table_names()
                verify_engine.dispose()
                
                if 'games' in verify_tables:
                    print('✅ Database schema created/updated and verified')
                else:
                    print('⚠️  Schema creation reported success but verification failed')
            else:
                print('✅ Database schema already exists')
        except Exception as e:
            # If inspection fails, try to create schema anyway
            print(f'⚠️  Could not inspect tables, attempting to create schema: {e}')
            try:
                schema_engine = create_database_schema(db_url)
                schema_engine.dispose()
                
                # Verify with a fresh connection
                verify_engine = create_engine(db_url)
                verify_inspector = inspect(verify_engine)
                verify_tables = verify_inspector.get_table_names()
                verify_engine.dispose()
                
                if 'games' in verify_tables:
                    print('✅ Database schema created and verified')
                else:
                    print('⚠️  Schema creation may have failed (verification unsuccessful)')
            except Exception as e2:
                print(f'⚠️  Could not create database schema: {e2}')
                print('   Tests that require database will be skipped')
    else:
        print('⚠️  No database URL configured')
        print('   Tests that require database will be skipped')
except Exception as e:
    print(f'⚠️  Could not initialize database: {e}')
    print('   Tests that require database will be skipped')
PYTHON_SCRIPT

# Capture exit code
SCHEMA_INIT_EXIT=$?
if [[ $SCHEMA_INIT_EXIT -ne 0 ]]; then
    echo -e "${YELLOW}⚠️  Database initialization check had warnings${NC}"
fi

# Final verification right before tests run - ensure schema is definitely available
if [[ -n "$SQLALCHEMY_DATABASE_URL" ]] || [[ -n "$DIPLOMACY_DATABASE_URL" ]]; then
    db_url_final="${SQLALCHEMY_DATABASE_URL:-${DIPLOMACY_DATABASE_URL}}"
    PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH" python3 << EOF
import sys, os
sys.path.insert(0, os.path.join('${PROJECT_ROOT}', 'src'))
from sqlalchemy import create_engine, inspect

db_url = '${db_url_final}'
engine = create_engine(db_url)
inspector = inspect(engine)
tables = inspector.get_table_names()
engine.dispose()

if 'games' not in tables:
    # Schema missing, try to create it one more time
    from engine.database import create_database_schema
    schema_engine = create_database_schema(db_url)
    schema_engine.dispose()
    print('⚠️  Schema was missing, recreated before tests')
else:
    print('✅ Schema verified before test execution')
EOF
fi

# Execute the command with proper environment inheritance
# Ensure PYTHONPATH and database URL are available to pytest
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
# Force schema check one more time right before pytest (in case of any race conditions)
if [[ -n "$SQLALCHEMY_DATABASE_URL" ]] || [[ -n "$DIPLOMACY_DATABASE_URL" ]]; then
    db_url_final="${SQLALCHEMY_DATABASE_URL:-${DIPLOMACY_DATABASE_URL}}"
    PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH" python3 -c "
import sys, os
sys.path.insert(0, '${PROJECT_ROOT}/src')
from sqlalchemy import create_engine, inspect
from engine.database import create_database_schema
engine = create_engine('${db_url_final}')
inspector = inspect(engine)
tables = inspector.get_table_names()
engine.dispose()
if 'games' not in tables:
    schema_engine = create_database_schema('${db_url_final}')
    schema_engine.dispose()
" >/dev/null 2>&1 || true
fi

if eval $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    
    # Show coverage summary if available
    if [[ "$HAS_COVERAGE" == true ]]; then
    echo ""
    echo -e "${BLUE}📊 Coverage Summary:${NC}"
        coverage report --show-missing || true
    
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
