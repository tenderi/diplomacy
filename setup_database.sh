#!/bin/bash
# Database setup script for Diplomacy
# Run this script to install and configure PostgreSQL for local development

set -e

echo "=== Diplomacy Database Setup ==="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed."
    echo "Please install it first:"
    echo "  sudo pacman -S postgresql"
    echo ""
    read -p "Press Enter after installing PostgreSQL, or Ctrl+C to exit..."
fi

# Check if PostgreSQL service is running
if ! systemctl is-active --quiet postgresql; then
    echo "PostgreSQL service is not running."
    echo "Initializing and starting PostgreSQL..."
    
    # Check if data directory exists
    if [ ! -d "/var/lib/postgres/data" ]; then
        echo "Initializing PostgreSQL database cluster..."
        sudo -u postgres initdb -D /var/lib/postgres/data
    fi
    
    echo "Starting PostgreSQL service..."
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    echo "Waiting for PostgreSQL to start..."
    sleep 2
fi

echo "✅ PostgreSQL is running"
echo ""

# Create user and database
echo "Creating database user and database..."
sudo -u postgres psql <<EOF
-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'diplomacy_user') THEN
        CREATE USER diplomacy_user WITH PASSWORD 'password';
    END IF;
END
\$\$;

-- Create database if not exists
SELECT 'CREATE DATABASE diplomacy_db OWNER diplomacy_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'diplomacy_db')\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE diplomacy_db TO diplomacy_user;
EOF

echo "✅ Database user and database created"
echo ""

# Create .env file
ENV_FILE=".env"
DB_URL="postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"

if [ -f "$ENV_FILE" ]; then
    if grep -q "SQLALCHEMY_DATABASE_URL" "$ENV_FILE"; then
        echo "⚠️  .env file exists and already contains SQLALCHEMY_DATABASE_URL"
        echo "   Current value: $(grep SQLALCHEMY_DATABASE_URL "$ENV_FILE")"
        read -p "   Do you want to update it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Remove old line and add new one
            sed -i '/SQLALCHEMY_DATABASE_URL/d' "$ENV_FILE"
            echo "SQLALCHEMY_DATABASE_URL=$DB_URL" >> "$ENV_FILE"
            echo "✅ Updated .env file"
        fi
    else
        echo "SQLALCHEMY_DATABASE_URL=$DB_URL" >> "$ENV_FILE"
        echo "✅ Added SQLALCHEMY_DATABASE_URL to .env file"
    fi
else
    echo "SQLALCHEMY_DATABASE_URL=$DB_URL" > "$ENV_FILE"
    echo "✅ Created .env file"
fi

echo ""

# Run migrations
echo "Running database migrations..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi

if command -v alembic &> /dev/null; then
    # Check for multiple heads and merge if needed
    HEAD_COUNT=$(alembic heads 2>/dev/null | wc -l)
    if [ "$HEAD_COUNT" -gt 1 ]; then
        echo "⚠️  Multiple migration heads detected. Creating merge migration..."
        HEADS=$(alembic heads 2>/dev/null | tr '\n' ' ')
        alembic merge -m "merge migration branches" $HEADS
        echo "✅ Merge migration created"
    fi
    
    alembic upgrade head
    echo "✅ Database migrations completed"
else
    echo "⚠️  Alembic not found. Please run: alembic upgrade head"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Database connection string: $DB_URL"
echo ""
echo "To verify the connection, run:"
echo "  psql -U diplomacy_user -h localhost -d diplomacy_db"
echo ""
echo "To test the application, run:"
echo "  python -m pytest tests/ -v"
