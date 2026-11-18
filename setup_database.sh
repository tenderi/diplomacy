#!/bin/bash
# Database setup script for Diplomacy
# Run this script to install and configure PostgreSQL for local development

set -e

echo "=== Diplomacy Database Setup ==="
echo ""

# PostgreSQL must be installed and running (./install_prerequisites.sh does both).
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Run ./install_prerequisites.sh, or install it with:"
    echo "  Arch:          sudo pacman -S postgresql && sudo -u postgres initdb -D /var/lib/postgres/data"
    echo "  Debian/Ubuntu: sudo apt-get install postgresql"
    echo "  macOS:         brew install postgresql@16"
    exit 1
fi
if ! pg_isready -q -h localhost; then
    echo "PostgreSQL is not accepting connections on localhost. Start it:"
    echo "  Linux: sudo systemctl start postgresql    macOS: brew services start postgresql@16"
    exit 1
fi

echo "✅ PostgreSQL is running"
echo ""

# Create user and database
echo "Creating database user and database..."
if [ "$(uname -s)" = "Darwin" ]; then PSQL_SUPER=(psql -d postgres); else PSQL_SUPER=(sudo -u postgres psql); fi
"${PSQL_SUPER[@]}" <<EOF
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
