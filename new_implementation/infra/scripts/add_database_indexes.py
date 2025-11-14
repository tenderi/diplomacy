#!/usr/bin/env python3
"""
Database index optimization script for Diplomacy game engine.

This script adds comprehensive database indexes to improve query performance
for the most common database operations in the Diplomacy game system.

Usage:
    python add_database_indexes.py

The script will:
1. Connect to the database using SQLALCHEMY_DATABASE_URL
2. Add indexes for frequently queried columns
3. Add composite indexes for common query patterns
4. Report on the optimization results
"""

import os
import sys
from sqlalchemy import create_engine, text, Index
from sqlalchemy.exc import SQLAlchemyError
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from server.db_config import SQLALCHEMY_DATABASE_URL
from engine.database import Base

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_database_indexes():
    """Add comprehensive database indexes for performance optimization."""
    
    try:
        # Create database engine
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        
        logger.info("🔗 Connected to database successfully")
        
        # Define indexes to add
        indexes_to_add = [
            # GameModel indexes
            ("ix_games_map_name", "games", "map_name"),
            ("ix_games_is_active", "games", "is_active"),
            ("ix_games_deadline", "games", "deadline"),
            ("ix_games_active_deadline", "games", "is_active, deadline"),
            ("ix_games_map_active", "games", "map_name, is_active"),
            
            # UserModel indexes
            ("ix_users_telegram_id", "users", "telegram_id"),
            ("ix_users_full_name", "users", "full_name"),
            
            # PlayerModel indexes
            ("ix_players_game_id", "players", "game_id"),
            ("ix_players_power", "players", "power"),
            ("ix_players_telegram_id", "players", "telegram_id"),
            ("ix_players_user_id", "players", "user_id"),
            ("ix_players_is_active", "players", "is_active"),
            ("ix_players_game_id_power", "players", "game_id, power"),
            ("ix_players_game_id_user_id", "players", "game_id, user_id"),
            ("ix_players_game_active", "players", "game_id, is_active"),
            ("ix_players_user_active", "players", "user_id, is_active"),
            ("ix_players_power_active", "players", "power, is_active"),
            
            # OrderModel indexes
            ("ix_orders_player_id", "orders", "player_id"),
            ("ix_orders_order_text", "orders", "order_text"),
            ("ix_orders_turn", "orders", "turn"),
            ("ix_orders_created_at", "orders", "created_at"),
            ("ix_orders_player_id_turn", "orders", "player_id, turn"),
            ("ix_orders_turn_created", "orders", "turn, created_at"),
            ("ix_orders_player_created", "orders", "player_id, created_at"),
            
            # MessageModel indexes
            ("ix_messages_game_id", "messages", "game_id"),
            ("ix_messages_sender_user_id", "messages", "sender_user_id"),
            ("ix_messages_recipient_user_id", "messages", "recipient_user_id"),
            ("ix_messages_recipient_power", "messages", "recipient_power"),
            ("ix_messages_timestamp", "messages", "timestamp"),
            ("ix_messages_game_timestamp", "messages", "game_id, timestamp"),
            ("ix_messages_sender_timestamp", "messages", "sender_user_id, timestamp"),
            ("ix_messages_recipient_timestamp", "messages", "recipient_user_id, timestamp"),
            ("ix_messages_game_recipient", "messages", "game_id, recipient_power"),
            
            # GameSnapshotModel indexes (already exist, but ensure they're there)
            ("ix_snapshots_game_id", "game_snapshots", "game_id"),
            ("ix_snapshots_turn", "game_snapshots", "turn"),
            ("ix_snapshots_year", "game_snapshots", "year"),
            ("ix_snapshots_season", "game_snapshots", "season"),
            ("ix_snapshots_phase", "game_snapshots", "phase"),
            ("ix_snapshots_phase_code", "game_snapshots", "phase_code"),
            ("ix_snapshots_created_at", "game_snapshots", "created_at"),
            ("ix_snapshots_game_turn", "game_snapshots", "game_id, turn"),
            ("ix_snapshots_game_phase", "game_snapshots", "game_id, phase_code"),
            
            # GameHistoryModel indexes
            ("ix_history_game_id", "game_history", "game_id"),
            ("ix_history_turn", "game_history", "turn"),
            ("ix_history_phase", "game_history", "phase"),
            ("ix_history_timestamp", "game_history", "timestamp"),
            ("ix_history_game_turn", "game_history", "game_id, turn"),
            ("ix_history_game_phase", "game_history", "game_id, phase"),
            ("ix_history_turn_timestamp", "game_history", "turn, timestamp"),
        ]
        
        # Track success/failure
        successful_indexes = []
        failed_indexes = []
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                for index_name, table_name, columns in indexes_to_add:
                    try:
                        # Check if index already exists
                        check_sql = text(f"""
                            SELECT COUNT(*) 
                            FROM pg_indexes 
                            WHERE indexname = :index_name
                        """)
                        
                        result = conn.execute(check_sql, {"index_name": index_name}).scalar()
                        
                        if result > 0:
                            logger.info(f"✅ Index {index_name} already exists, skipping")
                            successful_indexes.append(index_name)
                            continue
                        
                        # Create index
                        create_sql = text(f"""
                            CREATE INDEX CONCURRENTLY {index_name} 
                            ON {table_name} ({columns})
                        """)
                        
                        conn.execute(create_sql)
                        logger.info(f"✅ Created index {index_name} on {table_name}({columns})")
                        successful_indexes.append(index_name)
                        
                    except SQLAlchemyError as e:
                        logger.warning(f"⚠️  Failed to create index {index_name}: {e}")
                        failed_indexes.append((index_name, str(e)))
                
                # Commit transaction
                trans.commit()
                
                # Report results
                logger.info(f"\n📊 INDEX OPTIMIZATION SUMMARY:")
                logger.info(f"   ✅ Successfully created: {len(successful_indexes)} indexes")
                logger.info(f"   ❌ Failed to create: {len(failed_indexes)} indexes")
                
                if successful_indexes:
                    logger.info(f"\n✅ SUCCESSFUL INDEXES:")
                    for index in successful_indexes:
                        logger.info(f"   - {index}")
                
                if failed_indexes:
                    logger.info(f"\n❌ FAILED INDEXES:")
                    for index, error in failed_indexes:
                        logger.info(f"   - {index}: {error}")
                
                # Performance recommendations
                logger.info(f"\n🚀 PERFORMANCE RECOMMENDATIONS:")
                logger.info(f"   1. Run ANALYZE on all tables to update statistics:")
                logger.info(f"      ANALYZE games, players, orders, messages, game_snapshots, game_history;")
                logger.info(f"   2. Monitor query performance with pg_stat_statements")
                logger.info(f"   3. Consider VACUUM ANALYZE during low-traffic periods")
                logger.info(f"   4. Monitor index usage with pg_stat_user_indexes")
                
                return len(successful_indexes) > 0
                
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Transaction failed: {e}")
                return False
                
    except SQLAlchemyError as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def analyze_tables():
    """Run ANALYZE on all tables to update statistics."""
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        
        with engine.connect() as conn:
            tables = ['games', 'users', 'players', 'orders', 'messages', 'game_snapshots', 'game_history']
            
            for table in tables:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    logger.info(f"✅ Analyzed table {table}")
                except SQLAlchemyError as e:
                    logger.warning(f"⚠️  Failed to analyze table {table}: {e}")
        
        logger.info("📊 Table analysis completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Table analysis failed: {e}")
        return False

def main():
    """Main function to run database optimization."""
    logger.info("🚀 Starting database index optimization...")
    
    # Add indexes
    success = add_database_indexes()
    
    if success:
        # Analyze tables
        logger.info("\n📊 Updating table statistics...")
        analyze_tables()
        
        logger.info("\n🎉 Database optimization completed successfully!")
        logger.info("   The database is now optimized for better query performance.")
    else:
        logger.error("\n❌ Database optimization failed!")
        logger.error("   Please check the error messages above and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()
