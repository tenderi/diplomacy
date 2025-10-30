#!/usr/bin/env python3
"""Minimal database test"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from engine.database_service import DatabaseService

print("=== Minimal Database Test ===")

# Test 1: Direct engine creation
print("\n1. Testing direct engine creation...")
db_url = "postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"
print(f"Database URL: {db_url}")

try:
    engine = create_engine(db_url, echo=False)
    print("✓ Engine created successfully")
    
    # Test connection
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        print("✓ Connection test successful")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: DatabaseService creation
print("\n2. Testing DatabaseService creation...")
try:
    service = DatabaseService(db_url)
    print("✓ DatabaseService created successfully")
    
    # Test game creation
    game_state = service.create_game("minimal_test", "standard")
    print(f"✓ Game created successfully: {game_state.game_id}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Test with environment variable
print("\n3. Testing with environment variable...")
os.environ['SQLALCHEMY_DATABASE_URL'] = db_url

try:
    from server.db_config import SQLALCHEMY_DATABASE_URL
    print(f"Config URL: {SQLALCHEMY_DATABASE_URL}")
    
    service2 = DatabaseService(SQLALCHEMY_DATABASE_URL)
    print("✓ DatabaseService with env var created successfully")
    
    game_state2 = service2.create_game("env_test", "standard")
    print(f"✓ Game with env var created successfully: {game_state2.game_id}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
