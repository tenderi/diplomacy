#!/usr/bin/env python3
"""Debug database connection issue"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.database_service import DatabaseService
from server.db_config import SQLALCHEMY_DATABASE_URL

print("=== Database Connection Debug ===")
print(f"Environment SQLALCHEMY_DATABASE_URL: {os.environ.get('SQLALCHEMY_DATABASE_URL')}")
print(f"Config SQLALCHEMY_DATABASE_URL: {SQLALCHEMY_DATABASE_URL}")

# Test direct connection
print("\n=== Testing Direct Connection ===")
try:
    service = DatabaseService(SQLALCHEMY_DATABASE_URL)
    print("✓ DatabaseService created successfully")
    
    game_state = service.create_game("debug_test", "standard")
    print(f"✓ Game created successfully: {game_state.game_id}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test with temp_db fixture
print("\n=== Testing temp_db Fixture ===")
try:
    from tests.conftest import temp_db
    from sqlalchemy import create_engine
    
    db_url = "postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"
    print(f"Using database URL: {db_url}")
    
    engine = create_engine(db_url, echo=False)
    print("✓ Engine created successfully")
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        print("✓ Connection test successful")
    
    # Test session factory
    from engine.database import get_session_factory
    session_factory = get_session_factory(db_url)
    print("✓ Session factory created successfully")
    
    # Test session
    with session_factory() as session:
        print("✓ Session created successfully")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
