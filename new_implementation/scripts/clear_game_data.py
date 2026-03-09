#!/usr/bin/env python3
"""
Clear all game data from the local database. Keeps users, link codes, and auth data.
Uses SQLALCHEMY_DATABASE_URL from environment or .env in new_implementation.
"""
import os
import sys

# Load .env from new_implementation if present
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

db_url = os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")
if not db_url:
    db_url = "postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"
    print("Using default database URL (set SQLALCHEMY_DATABASE_URL to override)")

def main():
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    # Tables that reference games (delete these first; order avoids cross-FK issues)
    child_tables = [
        "messages", "orders", "units", "supply_centers", "turn_history",
        "map_snapshots", "spectators", "channel_messages", "channel_timeline_events",
        "channel_analytics", "channel_proposals", "tournament_games", "players",
    ]
    with engine.connect() as conn:
        for table in child_tables:
            try:
                r = conn.execute(text(f"DELETE FROM {table}"))
                if r.rowcount:
                    print(f"  {table}: {r.rowcount} rows")
            except Exception as e:
                if "does not exist" in str(e):
                    pass  # table may not exist in older migrations
                else:
                    raise
        result = conn.execute(text("DELETE FROM games"))
        conn.commit()
        deleted = result.rowcount
    engine.dispose()
    print(f"Cleared all game data ({deleted} games removed). Users and auth data are unchanged.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
