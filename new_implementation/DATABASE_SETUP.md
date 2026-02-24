# Local PostgreSQL Database Setup Guide

## Step 1: Install PostgreSQL

On Arch Linux, install PostgreSQL:

```bash
sudo pacman -S postgresql
```

## Step 2: Initialize and Start PostgreSQL

```bash
# Initialize the database cluster
sudo -u postgres initdb -D /var/lib/postgres/data

# Start PostgreSQL service
sudo systemctl start postgresql

# Enable PostgreSQL to start on boot (optional)
sudo systemctl enable postgresql
```

## Step 3: Create Database User and Database

```bash
# Switch to postgres user and open psql
sudo -u postgres psql
```

Then run these SQL commands:

```sql
-- Create the user
CREATE USER diplomacy_user WITH PASSWORD 'password';

-- Create the database
CREATE DATABASE diplomacy_db OWNER diplomacy_user;

-- Grant all privileges
GRANT ALL PRIVILEGES ON DATABASE diplomacy_db TO diplomacy_user;

-- Exit psql
\q
```

## Step 4: Configure Authentication (if needed)

Edit `/var/lib/postgres/data/pg_hba.conf` to allow local connections:

```
# Add or modify this line for local connections
local   all             all                                     peer
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
```

Then restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

## Step 5: Set Environment Variable

Create a `.env` file in the project root (`new_implementation/.env`):

```bash
cd /home/tenderi/diplomacy/new_implementation
cat > .env << 'EOF'
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db
EOF
```

Or export it in your shell:

```bash
export SQLALCHEMY_DATABASE_URL="postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db"
```

## Step 6: Run Database Migrations

```bash
cd /home/tenderi/diplomacy/new_implementation
source venv/bin/activate
alembic upgrade head
```

## Step 7: Verify Connection

Test the connection:

```bash
psql -U diplomacy_user -h localhost -d diplomacy_db
```

If you see a PostgreSQL prompt, the connection works! Type `\q` to exit.

## Troubleshooting

### PostgreSQL service won't start
```bash
# Check status
sudo systemctl status postgresql

# Check logs
sudo journalctl -u postgresql -n 50
```

### Permission denied errors
- Make sure you're using `sudo -u postgres` for database operations
- Check that the data directory has correct permissions: `sudo chown -R postgres:postgres /var/lib/postgres/data`

### Connection refused
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check if PostgreSQL is listening: `sudo ss -tlnp | grep 5432`
- Verify `pg_hba.conf` allows your connection method

### Password authentication failed
- Reset the password: `sudo -u postgres psql -c "ALTER USER diplomacy_user WITH PASSWORD 'password';"`
- Make sure `.env` file has the correct password
