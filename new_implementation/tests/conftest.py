"""
Shared pytest fixtures for Diplomacy tests.

This module provides common fixtures used across test modules to ensure
consistent test setup and reduce code duplication.
"""

import pytest
import tempfile
import os
from typing import Generator, Dict, Any
from unittest.mock import Mock, MagicMock

# Load environment variables from .env file if it exists
# This allows tests to automatically pick up database URL configuration
# MUST happen before any database imports
try:
    from dotenv import load_dotenv
    # Look for .env file in new_implementation/ (one level up from tests)
    project_root = os.path.join(os.path.dirname(__file__), '..')
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

# Set a test bot secret so /users/persistent_register works in tests.
# Uses setdefault so it doesn't override a value set in the real environment.
os.environ.setdefault("DIPLOMACY_BOT_SECRET", "test_bot_secret_for_tests")

# Initialize database schema BEFORE importing any database-dependent modules
# This ensures schema exists before pytest imports test modules that might connect to DB
_db_schema_initialized = False

def _ensure_db_schema():
    """Ensure database schema is initialized before tests run."""
    global _db_schema_initialized
    if _db_schema_initialized:
        return
    
    try:
        from sqlalchemy import create_engine, inspect, text
        db_url = os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")
        
        if db_url:
            # Check if schema exists and is complete
            engine = create_engine(db_url)
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
                    # Auth: users.email, link_codes, password_reset_tokens (run Alembic if missing)
                    if 'email' not in users_columns or 'link_codes' not in tables or 'password_reset_tokens' not in tables:
                        try:
                            import alembic.config
                            import alembic.command
                            _tests_dir = os.path.dirname(os.path.abspath(__file__))
                            _root = os.path.abspath(os.path.join(_tests_dir, ".."))
                            _alembic_ini = os.path.join(_root, "alembic.ini")
                            _cwd = os.getcwd()
                            try:
                                os.chdir(_root)
                                alembic_cfg = alembic.config.Config(_alembic_ini)
                                alembic.command.upgrade(alembic_cfg, "head")
                            finally:
                                os.chdir(_cwd)
                        except Exception:
                            pass  # tests may skip if auth schema missing
                
                if needs_schema_create or needs_column_update:
                    # Schema missing or incomplete, create/update it
                    from persistence.database import create_database_schema
                    schema_engine = create_database_schema(db_url)
                    schema_engine.dispose()
                    # Verify creation
                    verify_engine = create_engine(db_url)
                    verify_inspector = inspect(verify_engine)
                    verify_tables = verify_inspector.get_table_names()
                    verify_engine.dispose()
                    
                    if 'games' not in verify_tables:
                        print("⚠️  Warning: Could not initialize database schema. Tests requiring database will be skipped.")
                    else:
                        print("✅ Database schema initialized/updated before test collection")
                # If schema exists and is complete, no action needed
            except Exception as e:
                # If we can't check/create schema, that's okay - tests will skip
                pass
            finally:
                engine.dispose()
    except Exception:
        # If schema initialization fails, tests will handle it gracefully
        pass
    
    _db_schema_initialized = True

# Initialize schema immediately when conftest is loaded (before test collection)
_ensure_db_schema()

# Also use pytest_configure hook as a backup - runs very early in pytest lifecycle
def pytest_configure(config):
    """Pytest hook that runs before test collection - ensures schema is ready."""
    _ensure_db_schema()

# Now safe to import database-dependent modules
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Old-engine fixtures were removed in the M6 rewrite; the new engine is tested via
# tests/engine, tests/datc and tests/test_game_service.py.
# Legacy DB modules removed in spec-only implementation; keep tests resilient
Base = None  # type: ignore
SessionLocal = None  # type: ignore


def _get_db_url() -> str:
    """Get database URL if a reachable database is configured.

    Checks SQLALCHEMY_DATABASE_URL / DIPLOMACY_DATABASE_URL env vars, then the
    server.db_config default.  Unlike a simple URL check, this function also
    verifies that a TCP connection to the database host:port is possible so
    that @pytest.mark.skipif(not _get_db_url(), ...) skips correctly in
    environments where PostgreSQL is not running.
    """
    db_url = os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")

    if not db_url:
        try:
            from server.db_config import SQLALCHEMY_DATABASE_URL as default_url
            if default_url and "localhost" in default_url:
                db_url = default_url
        except ImportError:
            pass

    if not db_url:
        return ""

    # Verify the database is actually reachable before returning the URL.
    import socket
    try:
        # Parse host and port from the URL (handles postgresql://user:pass@host:port/db)
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 5432
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
    except (OSError, ValueError):
        return ""

    return db_url


@pytest.fixture
def temp_db():
    """Optional database engine for tests that need it; skips if DB URL missing.
    
    To enable database-dependent tests, set one of these environment variables:
    - SQLALCHEMY_DATABASE_URL (e.g., postgresql+psycopg2://user:pass@localhost:5432/dbname)
    - DIPLOMACY_DATABASE_URL
    
    You can also create a .env file in the project root with:
    SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/dbname
    """
    db_url = _get_db_url()
    if not db_url:
        pytest.skip(
            "Database URL not configured. Set SQLALCHEMY_DATABASE_URL or DIPLOMACY_DATABASE_URL "
            "environment variable, or create a .env file in the project root. "
            "Example: postgresql+psycopg2://user:pass@localhost:5432/dbname"
        )
    engine = create_engine(db_url, echo=False)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(temp_db):
    """Create a database session for testing using sessionmaker; skips if not configured."""
    Session = sessionmaker(bind=temp_db)  # type: ignore
    session = Session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram bot context for testing."""
    context = Mock()
    context.bot = Mock()
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    
    # Mock common bot methods
    context.bot.send_message = Mock()
    context.bot.edit_message_text = Mock()
    context.bot.answer_callback_query = Mock()
    
    return context


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram update for testing."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_chat = Mock()
    update.effective_chat.id = 67890
    update.callback_query = None
    update.message = Mock()
    update.message.text = "/test"
    update.message.reply_text = Mock()
    update.message.reply_markup = Mock()
    
    return update


@pytest.fixture
def sample_orders():
    """Sample orders for testing."""
    return {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR", "supported_target": "BUR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
            {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"}
        ]
    }


@pytest.fixture
def mock_map():
    """Create a mock map object for testing."""
    mock_map = Mock()
    mock_map.provinces = {
        "PAR": Mock(type="land", is_supply_center=True),
        "MAR": Mock(type="land", is_supply_center=True),
        "BRE": Mock(type="coast", is_supply_center=True),
        "BER": Mock(type="land", is_supply_center=True),
        "MUN": Mock(type="land", is_supply_center=True),
        "KIE": Mock(type="coast", is_supply_center=True),
        "BUR": Mock(type="land", is_supply_center=True),
        "SIL": Mock(type="land", is_supply_center=True),
        "TYR": Mock(type="land", is_supply_center=True),
        "BAL": Mock(type="sea", is_supply_center=False)
    }
    
    # Mock adjacency data (bot/UI tests; optionally use real map adjacencies for consistency)
    mock_map.get_adjacency = Mock(return_value=["BUR", "PIC"])
    mock_map.get_coast_adjacency = Mock(return_value=["ENG"])
    
    return mock_map


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "test_data")


@pytest.fixture
def cleanup_temp_files():
    """Fixture to clean up temporary files after tests."""
    temp_files = []
    
    def add_temp_file(filepath: str):
        temp_files.append(filepath)
    
    yield add_temp_file
    
    # Cleanup
    for filepath in temp_files:
        if os.path.exists(filepath):
            os.remove(filepath)


@pytest.fixture
def api_client():
    """Return a FastAPI TestClient for integration tests that need a running app."""
    from fastapi.testclient import TestClient
    from server.api import app
    return TestClient(app)


@pytest.fixture
def auth_headers(api_client):
    """Register a test user and return Bearer auth headers.

    Use this fixture in tests that call endpoints protected by require_bot_or_user.
    """
    import time
    email = f"testuser_{int(time.time() * 1000)}@example.com"
    db_url = _get_db_url()
    if not db_url:
        pytest.skip("Database URL not configured")
    reg = api_client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert reg.status_code == 200, f"Failed to register test user: {reg.text}"
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_auth_rate_limiters():
    """Clear all in-memory auth rate-limit buckets before each test.

    Covers /auth/login, /auth/token, /auth/register, and /auth/telegram/link --
    all share the same module-level dict in server.api.routes.auth (see
    `_rate_limit_attempts`), which otherwise accumulates across the whole
    test session and causes 429s once the real thresholds are crossed by
    tests that register/log in repeatedly from the same TestClient IP.
    """
    try:
        from server.api.routes.auth import reset_rate_limits
        reset_rate_limits()
    except ImportError:
        pass
    yield
    try:
        from server.api.routes.auth import reset_rate_limits
        reset_rate_limits()
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def _reset_province_name_cache():
    """Clear the bot's process-wide province-name cache around every test.

    `telegram_bot.orders` fetches `GET /maps/{map}/provinces` once per process and
    caches it in a module global (G2). Without this, whichever test happens to run
    first pays the HTTP call and every later test sees a warm cache — so the number
    of `api_get` calls a bot test observes depends on test *order*. That is exactly
    how `test_convoy_functions.py`'s `assert_called_once_with` passed locally and
    failed only when the suite order shifted.
    """
    try:
        from server.telegram_bot.orders import _reset_province_names_cache
    except ImportError:
        yield
        return
    _reset_province_names_cache()
    yield
    _reset_province_names_cache()


# Markers for test categorization
pytestmark = [
    pytest.mark.unit,  # Default to unit tests
]
