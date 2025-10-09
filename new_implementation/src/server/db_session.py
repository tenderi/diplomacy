"""
Database session and engine setup for Diplomacy server (PostgreSQL).
Optimized with comprehensive connection pooling for high-performance operation.
"""
import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from .db_config import SQLALCHEMY_DATABASE_URL

# Configure logging
logger = logging.getLogger(__name__)

# Use echo=False for production, echo=True for debugging
echo_sql = os.environ.get("DIPLOMACY_ECHO_SQL", "false").lower() == "true"

# Enhanced connection pool configuration for optimal performance
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    echo=echo_sql, 
    future=True,
    
    # Optimized connection pool settings
    poolclass=QueuePool,  # Use QueuePool for better performance
    pool_size=20,         # Increased from 10 - number of persistent connections
    max_overflow=30,      # Increased from 20 - additional connections when needed
    pool_pre_ping=True,   # Test connections before use
    pool_recycle=1800,    # Recycle connections every 30 minutes (reduced from 1 hour)
    pool_timeout=30,      # Timeout for getting connection from pool
    
    # Connection optimization settings
    connect_args={
        "connect_timeout": 10,      # Connection timeout
        "application_name": "diplomacy_server",  # Identify connections in PostgreSQL
        "options": "-c default_transaction_isolation=read_committed"  # Optimize transaction isolation
    },
    
    # Query optimization
    execution_options={
        "autocommit": False,
        "isolation_level": "READ_COMMITTED"
    }
)

# Add connection pool event listeners for monitoring
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set connection-level optimizations."""
    if "postgresql" in SQLALCHEMY_DATABASE_URL:
        with dbapi_connection.cursor() as cursor:
            # Optimize PostgreSQL connection settings
            cursor.execute("SET statement_timeout = '30s'")  # Prevent long-running queries
            cursor.execute("SET lock_timeout = '10s'")       # Prevent lock waits
            cursor.execute("SET idle_in_transaction_session_timeout = '60s'")  # Prevent idle transactions

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    """Log connection checkout for monitoring."""
    logger.debug("Connection checked out from pool")

@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_connection, connection_record):
    """Log connection checkin for monitoring."""
    logger.debug("Connection checked in to pool")

# Create session factory with optimized settings
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # Prevent lazy loading issues
)

# Connection pool monitoring functions
def get_pool_status():
    """Get current connection pool status for monitoring."""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_connections": pool.size() + pool.overflow(),
        "pool_class": pool.__class__.__name__
    }

def log_pool_status():
    """Log current pool status."""
    status = get_pool_status()
    logger.info(f"📊 Connection Pool Status: {status}")

# Log initial pool status
logger.info("🔗 Database engine created with optimized connection pooling")
log_pool_status()
