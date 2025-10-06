#!/usr/bin/env python3
"""
Database migration script for Diplomacy game engine.

This script clears the existing database and sets up the new schema
with proper data models and relationships.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.engine.database import clear_database, create_database_schema


def main():
    """Main migration function"""
    # Get database URL from environment or use default
    database_url = os.getenv('SQLALCHEMY_DATABASE_URL', 'sqlite:///diplomacy.db')
    
    print(f"🔄 Starting database migration...")
    print(f"📊 Database URL: {database_url}")
    
    try:
        # Clear existing database and create new schema
        print("🗑️  Clearing existing database...")
        engine = clear_database(database_url)
        
        print("✅ Database cleared successfully!")
        print("🏗️  Creating new schema...")
        
        # Create new schema
        engine = create_database_schema(database_url)
        
        print("✅ New schema created successfully!")
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """))
            tables = [row[0] for row in result]
            
            print(f"📋 Created tables: {', '.join(tables)}")
            
            # Check table counts
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f"   {table}: {count} rows")
        
        print("\n🎉 Database migration completed successfully!")
        print("🚀 Ready to use the new data models!")
        
    except SQLAlchemyError as e:
        print(f"❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
