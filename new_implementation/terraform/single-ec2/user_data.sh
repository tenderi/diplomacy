#!/bin/bash

# User data script to set up Diplomacy app on Ubuntu 22.04 LTS
# This script installs PostgreSQL, Python, and sets up the application

set -e

# Log all output
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== Starting Diplomacy Server Setup on Ubuntu 22.04 ==="
echo "Date: $(date)"

# Update system
apt update && apt upgrade -y

# Install required packages (much simpler on Ubuntu!)
echo "Installing required packages..."
apt install -y \
    postgresql \
    postgresql-contrib \
    python3 \
    python3-pip \
    python3-venv \
    git \
    nginx \
    curl \
    unzip \
    build-essential \
    libpq-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    pkg-config

echo "✓ Packages installed successfully"

# PostgreSQL setup (dramatically simpler on Ubuntu!)
echo "Setting up PostgreSQL..."

# Start and enable PostgreSQL service
systemctl enable postgresql
systemctl start postgresql

# Wait for PostgreSQL to be ready
sleep 5

# Create database and user (simple on Ubuntu - postgres user exists by default)
echo "Creating database and user..."
sudo -u postgres createdb ${db_name} || echo "Database already exists"
sudo -u postgres psql -c "CREATE USER ${db_username} WITH PASSWORD '${db_password}';" || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_username};" || true
sudo -u postgres psql -c "ALTER USER ${db_username} CREATEDB;" || true

echo "✓ Database setup complete"

# Configure PostgreSQL for optimal performance on t3.micro
echo "Optimizing PostgreSQL configuration..."
PG_VERSION=$(sudo -u postgres psql -c "SHOW server_version;" -t | awk '{print $1}' | sed 's/\..*//') 
PG_CONFIG_DIR="/etc/postgresql/$PG_VERSION/main"

# Backup original config
cp $PG_CONFIG_DIR/postgresql.conf $PG_CONFIG_DIR/postgresql.conf.backup

# Add optimized settings
cat >> $PG_CONFIG_DIR/postgresql.conf << EOF

# Optimized settings for single-instance t3.micro deployment
listen_addresses = 'localhost'
port = 5432

# Performance tuning for t3.micro (1GB RAM)
shared_buffers = 128MB
effective_cache_size = 768MB
work_mem = 4MB
maintenance_work_mem = 64MB
max_connections = 20

# Logging
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_statement = 'all'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
EOF

# Configure authentication (allow local md5 connections)
PG_HBA_FILE="$PG_CONFIG_DIR/pg_hba.conf"
cp $PG_HBA_FILE $PG_HBA_FILE.backup

# Update pg_hba.conf for local connections with password authentication
sed -i 's/local   all             all                                     peer/local   all             all                                     md5/' $PG_HBA_FILE

# Restart PostgreSQL to apply changes
systemctl restart postgresql
sleep 5

# Test PostgreSQL connection
echo "Testing PostgreSQL setup..."
if sudo -u postgres psql -c "SELECT version();" > /dev/null 2>&1; then
    echo "✓ PostgreSQL is running and accessible"
    sudo -u postgres psql -c "SELECT version();"
else
    echo "✗ PostgreSQL test failed"
    exit 1
fi

# Test database connection with the created user
echo "Testing database connection with diplomacy user..."
if PGPASSWORD='${db_password}' psql -h localhost -U ${db_username} -d ${db_name} -c "SELECT 'Connection successful!' as status;" > /dev/null 2>&1; then
    echo "✓ Database connection successful!"
    PGPASSWORD='${db_password}' psql -h localhost -U ${db_username} -d ${db_name} -c "SELECT 'Connection successful!' as status;"
else
    echo "✗ Database connection failed!"
    exit 1
fi

# Create diplomacy user
echo "Creating diplomacy application user..."
useradd -m -s /bin/bash diplomacy || echo "User already exists"

# Set up application directory
echo "Setting up application directories..."
mkdir -p /opt/diplomacy
chown diplomacy:diplomacy /opt/diplomacy

# Create application directory structure
sudo -u diplomacy mkdir -p /opt/diplomacy/src
sudo -u diplomacy mkdir -p /opt/diplomacy/maps

# Create environment file
echo "Creating environment file..."
cat > /opt/diplomacy/.env << EOF
db_username=${db_username}
db_password=${db_password}
db_host=localhost
db_port=5432
db_name=${db_name}
telegram_bot_token=${telegram_bot_token}
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://${db_username}:${db_password}@localhost:5432/${db_name}
DIPLOMACY_API_URL=${diplomacy_api_url}
BOT_ONLY=false
PYTHONPATH=/opt/diplomacy/src
EOF

chown diplomacy:diplomacy /opt/diplomacy/.env

# Create requirements.txt with latest versions (Ubuntu supports them!)
echo "Creating requirements.txt with latest package versions..."
cat > /opt/diplomacy/requirements.txt << EOF
fastapi==0.115.6
uvicorn[standard]==0.32.1
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
alembic==1.14.0
python-telegram-bot==21.10
pydantic==2.10.3
python-multipart==0.0.17
jinja2==3.1.4
pytz==2024.2
python-dotenv==1.0.1
httpx==0.28.1
aiofiles==24.1.0
EOF

# Install Python dependencies (latest versions work on Ubuntu!)
echo "Installing Python dependencies..."
sudo -u diplomacy pip3 install --user -r /opt/diplomacy/requirements.txt

echo "✓ Python dependencies installed successfully"

# Create systemd service for the diplomacy app
echo "Creating systemd service..."
cat > /etc/systemd/system/diplomacy.service << EOF
[Unit]
Description=Diplomacy Game Server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=diplomacy
WorkingDirectory=/opt/diplomacy
EnvironmentFile=/opt/diplomacy/.env
ExecStart=/home/diplomacy/.local/bin/uvicorn src.server.api:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for the telegram bot
cat > /etc/systemd/system/diplomacy-bot.service << EOF
[Unit]
Description=Diplomacy Telegram Bot
After=network.target postgresql.service diplomacy.service
Requires=postgresql.service

[Service]
Type=simple
User=diplomacy
WorkingDirectory=/opt/diplomacy
EnvironmentFile=/opt/diplomacy/.env
ExecStart=/usr/bin/python3 -m src.server.telegram_bot
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set up Nginx reverse proxy
echo "Configuring Nginx reverse proxy..."
cat > /etc/nginx/sites-available/diplomacy << EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout       60s;
        proxy_send_timeout          60s;
        proxy_read_timeout          60s;
    }
    
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
EOF

# Enable the Nginx site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/diplomacy /etc/nginx/sites-enabled/

# Test Nginx configuration
nginx -t

# Enable and start services
echo "Enabling and starting services..."
systemctl daemon-reload
systemctl enable nginx
systemctl enable diplomacy.service
systemctl enable diplomacy-bot.service

# Start Nginx
systemctl start nginx

# Services will be started by deploy script after code is uploaded

echo "Creating status script..."
cat > /opt/diplomacy/status.sh << 'EOF'
#!/bin/bash
echo "=== Diplomacy Server Status ==="
echo ""
echo "📁 Directory Structure:"
ls -la /opt/diplomacy/ | head -10
echo ""
echo "🐘 PostgreSQL Status:"
systemctl is-active postgresql
echo ""
echo "🎯 Diplomacy API Status:"
systemctl is-active diplomacy
echo ""
echo "🤖 Telegram Bot Status:"
systemctl is-active diplomacy-bot
echo ""
echo "🌐 Network Status:"
ss -tlnp | grep ":8000\|:80\|:5432"
echo ""
echo "💾 Disk Usage:"
df -h /opt
echo ""
echo "🧠 Memory Usage:"
free -h
echo ""
echo "📊 API Health Check:"
curl -s http://localhost:8000/ | head -100
echo ""
echo "📋 Recent Logs:"
echo "API Logs:"
journalctl -u diplomacy --no-pager -n 5 | cat
echo ""
echo "Bot Logs:"
journalctl -u diplomacy-bot --no-pager -n 5 | cat
EOF

chmod +x /opt/diplomacy/status.sh
chown diplomacy:diplomacy /opt/diplomacy/status.sh

echo ""
echo "=== Setup Complete! ==="
echo "✓ Ubuntu 22.04 LTS system updated"
echo "✓ PostgreSQL $(sudo -u postgres psql -c "SHOW server_version;" -t | awk '{print $1}') installed and configured"
echo "✓ Python $(python3 --version) with latest packages installed"
echo "✓ Nginx reverse proxy configured"
echo "✓ Systemd services created"
echo "✓ Application user and directories prepared"
echo ""
echo "Next steps:"
echo "1. Upload application code to /opt/diplomacy/"
echo "2. Run database migrations"
echo "3. Start services: systemctl start diplomacy.service diplomacy-bot.service"
echo ""
echo "Use '/opt/diplomacy/status.sh' to check server status"
echo "=== Setup Log Complete ===" 