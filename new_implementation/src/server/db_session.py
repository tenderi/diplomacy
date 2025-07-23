"""
Database session and engine setup for Diplomacy server (PostgreSQL).
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .db_config import SQLALCHEMY_DATABASE_URL

# Use echo=False for production, echo=True for debugging
echo_sql = os.environ.get("DIPLOMACY_ECHO_SQL", "false").lower() == "true"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    echo=echo_sql, 
    future=True,
    # Connection pool settings to prevent connection issues
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600  # Recycle connections every hour
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
