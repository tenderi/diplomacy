#!/usr/bin/env python3
"""
Database reset script for Diplomacy.
Drops and recreates the database with fresh schema.

Usage:
    python reset_database.py [database_name] [--user username] [--password password] [--host host]
    
    Defaults:
    - database_name: diplomacy_db
    - user: diplomacy_user
    - password: password
    - host: localhost
"""

import os
import sys
import argparse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Reset Diplomacy database')
    parser.add_argument('database', nargs='?', default='diplomacy_db', 
                       help='Database name (default: diplomacy_db)')
    parser.add_argument('--user', '-u', default='diplomacy_user',
                       help='Database user (default: diplomacy_user)')
    parser.add_argument('--password', '-p', default='password',
                       help='Database password (default: password)')
    parser.add_argument('--host', '-H', default='localhost',
                       help='Database host (default: localhost)')
    parser.add_argument('--port', '-P', default='5432',
                       help='Database port (default: 5432)')
    parser.add_argument('--use-postgres-user', action='store_true',
                       help='Try to use postgres superuser (for local development)')
    return parser.parse_args()


def reset_database(db_name: str, db_user: str, db_password: str, db_host: str, db_port: str, use_postgres_user: bool = False) -> bool:
    """
    Drop and recreate the database.
    
    Args:
        use_postgres_user: If True, try to use 'postgres' superuser (no password prompt)
    
    Returns True if successful, False otherwise.
    """
    # Try to connect as postgres superuser first if requested
    postgres_superuser = None
    if use_postgres_user:
        # Try connecting as postgres user (common default)
        try:
            test_url = f"postgresql+psycopg2://postgres@{db_host}:{db_port}/postgres"
            test_engine = create_engine(test_url, isolation_level="AUTOCOMMIT")
            with test_engine.connect():
                postgres_superuser = "postgres"
            test_engine.dispose()
        except:
            pass
    
    # Connect to postgres database to drop/create target database
    if postgres_superuser:
        postgres_url = f"postgresql+psycopg2://{postgres_superuser}@{db_host}:{db_port}/postgres"
    else:
        postgres_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/postgres"
    
    try:
        print(f"🔗 Connecting to PostgreSQL server at {db_host}:{db_port}...")
        postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
        
        with postgres_engine.connect() as conn:
            # Terminate all connections to the target database
            print(f"🔌 Terminating existing connections to database '{db_name}'...")
            try:
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :db_name AND pid <> pg_backend_pid()
                """), {"db_name": db_name})
            except Exception as e:
                print(f"⚠️  Note: {e}")
            
            # Drop the database if it exists
            print(f"🗑️  Dropping database '{db_name}' if it exists...")
            try:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
                print(f"✅ Database '{db_name}' dropped")
            except Exception as e:
                if "permission denied" in str(e).lower() or "insufficient privilege" in str(e).lower():
                    print(f"❌ Permission denied: Cannot drop database as user '{db_user}'")
                    print(f"💡 Solution: Run as postgres superuser or use: sudo -u postgres psql")
                    postgres_engine.dispose()
                    return False
                print(f"⚠️  Note: {e}")
            
            # Create the database
            print(f"🏗️  Creating database '{db_name}'...")
            try:
                conn.execute(text(f'CREATE DATABASE "{db_name}" OWNER "{db_user}"'))
                print(f"✅ Database '{db_name}' created")
            except Exception as e:
                if "permission denied" in str(e).lower() or "insufficient privilege" in str(e).lower():
                    print(f"❌ Permission denied: Cannot create database as user '{db_user}'")
                    print(f"💡 Solution: Run as postgres superuser or use:")
                    print(f"   sudo -u postgres psql -c \"DROP DATABASE IF EXISTS {db_name};\"")
                    print(f"   sudo -u postgres psql -c \"CREATE DATABASE {db_name} OWNER {db_user};\"")
                    postgres_engine.dispose()
                    return False
                raise
            
            # Grant privileges
            conn.execute(text(f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO "{db_user}"'))
            print(f"✅ Privileges granted")
        
        postgres_engine.dispose()
        
        # Now connect to the new database and run migrations
        print(f"\n📊 Connecting to '{db_name}' and running migrations...")
        target_url = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        target_engine = create_engine(target_url)
        
        # Import and run Alembic migrations
        try:
            from alembic import command
            from alembic.config import Config
            
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", target_url)
            
            print("🔄 Running Alembic migrations...")
            command.upgrade(alembic_cfg, "head")
            print("✅ Migrations completed")
        except ImportError:
            print("⚠️  Alembic not available, skipping migrations")
            print("   Run 'alembic upgrade head' manually after this script")
        except Exception as e:
            print(f"⚠️  Migration error: {e}")
            print("   Database created but migrations may need to be run manually")
        
        target_engine.dispose()
        return True
        
    except OperationalError as e:
        print(f"❌ Database connection error: {e}")
        print("\n💡 Troubleshooting:")
        print("   - Ensure PostgreSQL is running")
        print(f"   - Check user '{db_user}' exists and has privileges")
        print(f"   - Verify host '{db_host}' and port '{db_port}' are correct")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function."""
    args = parse_args()
    
    print("=" * 60)
    print("🗄️  Diplomacy Database Reset Script")
    print("=" * 60)
    print(f"Database: {args.database}")
    print(f"User: {args.user}")
    print(f"Host: {args.host}:{args.port}")
    print("=" * 60)
    print()
    
    # Confirm if not using defaults
    if args.database != 'diplomacy_db' or args.user != 'diplomacy_user':
        response = input(f"This will DROP database '{args.database}'. Continue? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Aborted")
            sys.exit(1)
    else:
        print("⚠️  This will DROP and RECREATE the database!")
        response = input("Continue? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Aborted")
            sys.exit(1)
    
    success = reset_database(
        args.database,
        args.user,
        args.password,
        args.host,
        args.port,
        use_postgres_user=args.use_postgres_user
    )
    
    if success:
        print("\n🎉 Database reset completed successfully!")
        print(f"📝 Database URL: postgresql+psycopg2://{args.user}:{args.password}@{args.host}:{args.port}/{args.database}")
    else:
        print("\n❌ Database reset failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()

