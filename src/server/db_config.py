# Database configuration for Diplomacy server (PostgreSQL)
import os

# Read database URL from environment variable, with localhost fallback for development
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "SQLALCHEMY_DATABASE_URL",
    "postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"
)
