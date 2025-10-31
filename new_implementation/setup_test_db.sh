#!/bin/bash
# Script to set up or reset the test database for Diplomacy

set -e

DB_NAME="${1:-diplomacy_test}"
DB_USER="${DB_USER:-diplomacy_user}"
DB_PASSWORD="${DB_PASSWORD:-password}"

echo "Setting up test database: $DB_NAME"

# Connect to postgres database to drop/create the test database
sudo -u postgres psql <<EOF
-- Terminate all connections to the database if it exists
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();

-- Drop the database if it exists
DROP DATABASE IF EXISTS $DB_NAME;

-- Create the database
CREATE DATABASE $DB_NAME OWNER $DB_USER;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

echo "✅ Database $DB_NAME created successfully"

# Run migrations
export SQLALCHEMY_DATABASE_URL="postgresql+psycopg2://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
echo "Running Alembic migrations..."
alembic upgrade head

echo "✅ Test database setup complete!"

