#!/bin/bash

# User data script to set up Diplomacy app on single EC2 instance
# This script installs PostgreSQL, Python, and sets up the application

set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== Starting Diplomacy Server Setup ==="
echo "Date: $(date)"

# Update system
yum update -y

# Find and install the latest PostgreSQL version available via Amazon Linux Extras
echo "Finding latest available PostgreSQL version..."
AVAILABLE_POSTGRES=$(amazon-linux-extras list | grep -E 'postgresql[0-9]+' | grep -E '\bavailable\b' | tail -1 | awk '{print $2}')

if [ -z "$AVAILABLE_POSTGRES" ]; then
    # Fallback to known good versions in order of preference
    for version in postgresql17 postgresql16 postgresql15 postgresql14 postgresql13; do
        if amazon-linux-extras list | grep -q "$version.*available"; then
            AVAILABLE_POSTGRES="$version"
            break
        fi
    done
fi

if [ -z "$AVAILABLE_POSTGRES" ]; then
    echo "❌ No PostgreSQL version found in amazon-linux-extras!"
    exit 1
fi

echo "🎯 Installing PostgreSQL version: $AVAILABLE_POSTGRES"
amazon-linux-extras install $AVAILABLE_POSTGRES -y

# Extract major version number (e.g., postgresql17 -> 17)
PG_MAJOR_VERSION=$(echo $AVAILABLE_POSTGRES | sed 's/postgresql//')
echo "PostgreSQL major version: $PG_MAJOR_VERSION"

# Install additional required packages
yum install -y \
    git \
    python3 \
    python3-pip \
    postgresql-devel \
    nginx \
    htop \
    tmux \
    gcc \
    python3-devel \
    curl

# Create diplomacy user
useradd -m -s /bin/bash diplomacy || true

# Create postgres user if it doesn't exist (required for PostgreSQL)
echo "Creating postgres user..."
if ! id postgres &>/dev/null; then
    useradd -r -s /bin/false postgres
    echo "✓ Created postgres user"
else
    echo "✓ postgres user already exists"
fi

# Initialize PostgreSQL (correct method for amazon-linux-extras installation)
echo "Initializing PostgreSQL database..."

# Create the data directory
mkdir -p /var/lib/pgsql/data
chown postgres:postgres /var/lib/pgsql/data

# Initialize the database as the postgres user
sudo -u postgres /usr/bin/initdb -D /var/lib/pgsql/data

# Enable and start PostgreSQL service
systemctl enable postgresql
systemctl start postgresql

# Wait for PostgreSQL to be ready
sleep 10

# Check PostgreSQL status
echo "PostgreSQL status: $(systemctl is-active postgresql)"

# Get actual PostgreSQL version that was installed
PG_VERSION=$(sudo -u postgres psql -t -c "SHOW server_version;" 2>/dev/null | head -1 | awk '{print $1}' | cut -d. -f1 || echo "unknown")
echo "✅ PostgreSQL $PG_VERSION is now running!"

# Configure PostgreSQL
echo "Configuring PostgreSQL database and user..."
sudo -u postgres createdb ${db_name} || true
sudo -u postgres psql -c "CREATE USER ${db_username} WITH PASSWORD '${db_password}';" || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_username};" || true
sudo -u postgres psql -c "ALTER USER ${db_username} CREATEDB;" || true

# Configure PostgreSQL to accept connections
echo "Configuring PostgreSQL for local connections..."
cat >> /var/lib/pgsql/data/postgresql.conf << EOF
# Optimized settings for single-instance deployment
listen_addresses = 'localhost'
port = 5432

# Performance tuning for t3.micro (1GB RAM)
shared_buffers = 128MB
effective_cache_size = 768MB
work_mem = 4MB
maintenance_work_mem = 64MB

# Connection settings
max_connections = 20

# Logging
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_statement = 'all'
EOF

# Update pg_hba.conf for local connections (Amazon Linux 2 specific)
cp /var/lib/pgsql/data/pg_hba.conf /var/lib/pgsql/data/pg_hba.conf.bak
sed -i 's/peer/md5/g' /var/lib/pgsql/data/pg_hba.conf
sed -i 's/ident/md5/g' /var/lib/pgsql/data/pg_hba.conf

# Restart PostgreSQL to apply changes
systemctl restart postgresql

# Wait for restart
sleep 5

# Test PostgreSQL connection
echo "Testing PostgreSQL connection..."
if sudo -u postgres psql -c "SELECT version();" 2>/dev/null; then
    echo "✓ PostgreSQL is running and accessible"
else
    echo "✗ PostgreSQL test failed"
fi

# Test database connection with the created user
echo "Testing database connection with diplomacy user..."
if sudo -u diplomacy PGPASSWORD='${db_password}' psql -h localhost -U ${db_username} -d ${db_name} -c "SELECT 'Connection successful!' as status;" 2>/dev/null; then
    echo "✓ Database connection successful!"
else
    echo "✗ Database connection failed!"
fi

# Set up application directory
mkdir -p /opt/diplomacy
chown diplomacy:diplomacy /opt/diplomacy

# Create application directory structure
sudo -u diplomacy mkdir -p /opt/diplomacy/new_implementation

# Create environment file
cat > /opt/diplomacy/.env << EOF
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://${db_username}:${db_password}@localhost:5432/${db_name}
TELEGRAM_BOT_TOKEN=${telegram_bot_token}
DIPLOMACY_API_URL=${diplomacy_api_url}
BOT_ONLY=false
PYTHONPATH=/opt/diplomacy/new_implementation/src
EOF

chown diplomacy:diplomacy /opt/diplomacy/.env

# Create requirements.txt with updated versions
cat > /opt/diplomacy/requirements.txt << EOF
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.0
python-telegram-bot==21.10
pydantic==2.10.3
python-multipart==0.0.12
jinja2==3.1.4
pytz==2024.2
EOF

# Install Python dependencies
echo "Installing Python dependencies..."
sudo -u diplomacy pip3 install --user -r /opt/diplomacy/requirements.txt

# Create systemd service for the diplomacy app
cat > /etc/systemd/system/diplomacy.service << EOF
[Unit]
Description=Diplomacy Game Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=diplomacy
WorkingDirectory=/opt/diplomacy/new_implementation
EnvironmentFile=/opt/diplomacy/.env
ExecStart=/home/diplomacy/.local/bin/uvicorn src.server.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Create nginx configuration
cat > /etc/nginx/conf.d/diplomacy.conf << EOF
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Remove default nginx config
rm -f /etc/nginx/conf.d/default.conf

# Create deployment script
cat > /opt/diplomacy/deploy.sh << 'EOF'
#!/bin/bash
echo "=== Deploying Diplomacy App ==="
cd /opt/diplomacy

echo "Installing/updating Python dependencies..."
pip3 install --user -r requirements.txt

echo "Restarting diplomacy service..."
sudo systemctl restart diplomacy

echo "Deployment complete!"
EOF

chmod +x /opt/diplomacy/deploy.sh
chown diplomacy:diplomacy /opt/diplomacy/deploy.sh

# Create health check script
cat > /opt/diplomacy/health_check.sh << 'EOF'
#!/bin/bash
curl -f http://localhost:8000/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Diplomacy service is healthy"
    exit 0
else
    echo "✗ Diplomacy service is unhealthy"
    exit 1
fi
EOF

chmod +x /opt/diplomacy/health_check.sh
chown diplomacy:diplomacy /opt/diplomacy/health_check.sh

# Create comprehensive status script
cat > /opt/diplomacy/status.sh << 'EOF'
#!/bin/bash
echo "=== Diplomacy Server Status ==="
echo "Date: $(date)"
echo ""
echo "=== Service Status ==="
echo "PostgreSQL: $(systemctl is-active postgresql)"
echo "Diplomacy App: $(systemctl is-active diplomacy)"
echo "Nginx: $(systemctl is-active nginx)"
echo ""
echo "=== PostgreSQL Information ==="
if sudo -u postgres psql -c "SELECT version();" 2>/dev/null; then
    echo "PostgreSQL is running properly"
else
    echo "PostgreSQL version check failed"
fi
echo ""
echo "=== Database Connection Test ==="
if sudo -u diplomacy PGPASSWORD='${db_password}' psql -h localhost -U ${db_username} -d ${db_name} -c "SELECT 'Database connection OK!' as status;" 2>/dev/null; then
    echo "✓ Database connection successful"
else
    echo "✗ Database connection failed"
fi
echo ""
echo "=== Listening Ports ==="
ss -tlpn | grep -E ':(5432|8000|80)\s' || echo "No services found on expected ports"
echo ""
echo "=== System Resources ==="
echo "Memory usage:"
free -h
echo "Disk usage:"
df -h /
echo ""
echo "=== Recent Application Logs ==="
if systemctl is-active diplomacy >/dev/null 2>&1; then
    echo "Last 10 lines of diplomacy service logs:"
    journalctl -u diplomacy -n 10 --no-pager || echo "No logs available"
else
    echo "Diplomacy service is not running"
fi
EOF

chmod +x /opt/diplomacy/status.sh
chown diplomacy:diplomacy /opt/diplomacy/status.sh

# Enable and start services
systemctl enable diplomacy
systemctl enable nginx
systemctl start nginx

echo "=== Setup Summary ==="
echo "PostgreSQL Status: $(systemctl is-active postgresql)"
echo "Nginx Status: $(systemctl is-active nginx)"
echo "PostgreSQL Version: $AVAILABLE_POSTGRES"
echo ""
echo "=== Final Verification ==="
if sudo -u postgres psql -c "SELECT version();" 2>/dev/null; then
    echo "✅ PostgreSQL installation verified"
else
    echo "❌ PostgreSQL verification failed"
fi

if sudo -u diplomacy PGPASSWORD='${db_password}' psql -h localhost -U ${db_username} -d ${db_name} -c "SELECT 'Setup completed successfully!' as message;" 2>/dev/null; then
    echo "✅ Database setup completed successfully!"
else
    echo "❌ Database setup may have issues"
fi

echo ""
echo "=== Next Steps ==="
echo "1. SSH to the instance and deploy your application code"
echo "2. Copy your code to /opt/diplomacy/new_implementation/"
echo "3. Start the diplomacy service: sudo systemctl start diplomacy"
echo "4. Check status: /opt/diplomacy/status.sh"
echo ""
echo "🎯 Using PostgreSQL $AVAILABLE_POSTGRES for optimal performance!"
echo "Instance setup completed at: $(date)" 