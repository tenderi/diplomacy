#!/bin/bash

# Deployment script for Diplomacy app to single EC2 instance
# This script copies the application code and starts the service
#
# Usage:
#   ./deploy_app.sh              # Normal deployment
#   ./deploy_app.sh --reset-db   # Reset database and deploy

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
RESET_DB=false
for arg in "$@"; do
    case $arg in
        --reset-db|--reset-database)
            RESET_DB=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--reset-db]"
            echo ""
            echo "Options:"
            echo "  --reset-db, --reset-database    Drop and recreate the database before deployment"
            echo "  --help, -h                      Show this help message"
            exit 0
            ;;
        *)
            ;;
    esac
done

echo -e "${GREEN}=== Diplomacy App Deployment Script (Diff-Based) ===${NC}"
if [ "$RESET_DB" = true ]; then
    echo -e "${YELLOW}⚠️  DATABASE RESET MODE: Database will be dropped and recreated${NC}"
fi

# Check if terraform is available and get instance IP
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed or not in PATH${NC}"
    exit 1
fi

# Get instance IP from Terraform output
echo -e "${YELLOW}Getting instance IP from Terraform...${NC}"
INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)

if [ -z "$INSTANCE_IP" ]; then
    echo -e "${RED}Error: Could not get instance IP from Terraform output${NC}"
    echo "Make sure you've run 'terraform apply' successfully"
    exit 1
fi

echo -e "${GREEN}Found instance IP: $INSTANCE_IP${NC}"

# Get key name from Terraform (with improved method)
echo -e "${YELLOW}Retrieving SSH key name from Terraform...${NC}"
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)

if [ -z "$KEY_NAME" ]; then
    # Fallback: try JSON method
    KEY_NAME=$(terraform output -json 2>/dev/null | jq -r '.key_name.value // empty' 2>/dev/null)
fi

if [ -z "$KEY_NAME" ]; then
    echo -e "${YELLOW}Warning: Could not get key name from Terraform output${NC}"
    echo -e "${YELLOW}This usually means terraform hasn't been applied yet or there's an issue with the configuration${NC}"
    read -p "Please enter your EC2 key pair name: " KEY_NAME
else
    echo -e "${GREEN}Retrieved key name from Terraform: $KEY_NAME${NC}"
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"

# Check if key file exists
if [ ! -f "${KEY_PATH/#\~/$HOME}" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_PATH${NC}"
    echo -e "${YELLOW}Please ensure:${NC}"
    echo -e "  1. The key pair '$KEY_NAME' exists in AWS"
    echo -e "  2. You have downloaded the .pem file to ~/.ssh/"
    echo -e "  3. The file has correct permissions (chmod 400 ~/.ssh/${KEY_NAME}.pem)"
    exit 1
fi

echo -e "${YELLOW}Using key file: $KEY_PATH${NC}"

# Function to run SSH command (Ubuntu uses 'ubuntu' user)
run_ssh() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "$1"
}

# Function to copy files via SCP
copy_files() {
    scp -i "$KEY_PATH" -o StrictHostKeyChecking=no -r "$1" ubuntu@$INSTANCE_IP:"$2"
}

# Function to create file checksums for comparison
create_checksums() {
    local dir="$1"
    local checksum_file="$2"
    
    if [ -d "$dir" ]; then
        find "$dir" -type f \( -name "*.py" -o -name "*.txt" -o -name "*.ini" -o -name "*.json" -o -name "*.svg" -o -name "*.html" -o -name "*.css" -o -name "*.js" \) | \
        xargs md5sum > "$checksum_file" 2>/dev/null || true
    else
        touch "$checksum_file"
    fi
}

# Function to check if files have changed
check_file_changes() {
    local local_checksum="$1"
    local remote_checksum="$2"
    
    # Get remote checksums if they exist
    run_ssh "test -f $remote_checksum && cat $remote_checksum || echo 'NO_PREVIOUS_CHECKSUM'" > /tmp/remote_checksums
    
    # Compare checksums
    if [ -f "$local_checksum" ] && [ -s "$local_checksum" ]; then
        if diff "$local_checksum" /tmp/remote_checksums > /dev/null 2>&1; then
            echo "false"  # No changes
        else
            echo "true"   # Changes detected
        fi
    else
        echo "true"  # No local checksum, assume changes
    fi
}

# Wait for instance to be ready
echo -e "${YELLOW}Waiting for instance to be ready...${NC}"
for i in {1..30}; do
    if run_ssh "echo 'Instance ready'" &>/dev/null; then
        echo -e "${GREEN}Instance is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Error: Instance is not responding after 5 minutes${NC}"
        exit 1
    fi
    echo "Waiting... ($i/30)"
    sleep 10
done

# Check if setup is complete
echo -e "${YELLOW}Checking if instance setup is complete...${NC}"
if ! run_ssh "test -f /opt/diplomacy/.env"; then
    echo -e "${RED}Error: Instance setup is not complete yet${NC}"
    echo "Please wait for the user-data script to finish, then try again"
    echo "You can check the setup progress with:"
    echo "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo tail -f /var/log/user-data.log'"
    exit 1
fi

# Verify and ensure SQLALCHEMY_DATABASE_URL is defined in .env file
echo -e "${YELLOW}Verifying SQLALCHEMY_DATABASE_URL configuration...${NC}"
run_ssh "
    if ! grep -q '^SQLALCHEMY_DATABASE_URL=' /opt/diplomacy/.env 2>/dev/null; then
        echo '⚠️  Warning: SQLALCHEMY_DATABASE_URL not found in .env file'
        echo '   Attempting to construct from .env file contents...'
        
        # Try to construct from individual components if they exist
        DB_USER=\$(grep '^db_username=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' || echo '')
        DB_PASS=\$(grep '^db_password=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' || echo '')
        DB_HOST=\$(grep '^db_host=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' || echo 'localhost')
        DB_PORT=\$(grep '^db_port=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' || echo '5432')
        DB_NAME=\$(grep '^db_name=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' || echo '')
        
        if [ -n \"\$DB_USER\" ] && [ -n \"\$DB_PASS\" ] && [ -n \"\$DB_NAME\" ]; then
            SQLALCHEMY_DATABASE_URL=\"postgresql+psycopg2://\${DB_USER}:\${DB_PASS}@\${DB_HOST}:\${DB_PORT}/\${DB_NAME}\"
            echo \"SQLALCHEMY_DATABASE_URL=\$SQLALCHEMY_DATABASE_URL\" | sudo tee -a /opt/diplomacy/.env > /dev/null
            echo '✅ Added SQLALCHEMY_DATABASE_URL to .env file'
        else
            echo '❌ Error: Cannot construct SQLALCHEMY_DATABASE_URL from .env components'
            echo '   Required components: db_username, db_password, db_name'
            exit 1
        fi
    else
        # Verify it's not empty
        DB_URL=\$(grep '^SQLALCHEMY_DATABASE_URL=' /opt/diplomacy/.env | cut -d '=' -f2- | tr -d '\"\"\\\"''' | xargs)
        if [ -z \"\$DB_URL\" ]; then
            echo '❌ Error: SQLALCHEMY_DATABASE_URL is empty in .env file'
            exit 1
        else
            echo '✅ SQLALCHEMY_DATABASE_URL is properly configured'
        fi
    fi
" || {
    echo -e "${RED}Error: Failed to verify/configure SQLALCHEMY_DATABASE_URL${NC}"
    echo -e "${YELLOW}Please ensure the .env file contains SQLALCHEMY_DATABASE_URL or the required database components${NC}"
    exit 1
}

# Create temporary directory for checksums
TEMP_DIR="/tmp/diplomacy_deploy_$$"
mkdir -p "$TEMP_DIR"

echo -e "${BLUE}=== Analyzing File Changes ===${NC}"

# Create checksums for local files
echo -e "${YELLOW}Creating local file checksums...${NC}"
create_checksums "../src" "$TEMP_DIR/src_checksums.txt"
create_checksums "../maps" "$TEMP_DIR/maps_checksums.txt"
create_checksums "../alembic" "$TEMP_DIR/alembic_checksums.txt"

# Check for changes in each component
SRC_CHANGED=$(check_file_changes "$TEMP_DIR/src_checksums.txt" "/opt/diplomacy/src_checksums.txt")
MAPS_CHANGED=$(check_file_changes "$TEMP_DIR/maps_checksums.txt" "/opt/diplomacy/maps_checksums.txt")
ALEMBIC_CHANGED=$(check_file_changes "$TEMP_DIR/alembic_checksums.txt" "/opt/diplomacy/alembic_checksums.txt")

# Always check requirements.txt (small file, quick to transfer)
REQUIREMENTS_CHANGED="true"

echo -e "${BLUE}Change Analysis Results:${NC}"
echo -e "  📁 Source code: $([ "$SRC_CHANGED" = "true" ] && echo "${GREEN}Changed${NC}" || echo "${YELLOW}No changes${NC}")"
echo -e "  🗺️ Maps: $([ "$MAPS_CHANGED" = "true" ] && echo "${GREEN}Changed${NC}" || echo "${YELLOW}No changes${NC}")"
echo -e "  ��️ Alembic: $([ "$ALEMBIC_CHANGED" = "true" ] && echo "${GREEN}Changed${NC}" || echo "${YELLOW}No changes${NC}")"
echo -e "  📦 Requirements: ${GREEN}Checking${NC}"

# Copy only changed components
echo -e "${BLUE}=== Transferring Changed Files ===${NC}"

if [ "$SRC_CHANGED" = "true" ]; then
    echo -e "${YELLOW}📁 Copying updated source code...${NC}"
    copy_files "../src" "/tmp/"
    copy_files "$TEMP_DIR/src_checksums.txt" "/tmp/"
else
    echo -e "${GREEN}📁 Source code unchanged, skipping...${NC}"
fi

if [ "$MAPS_CHANGED" = "true" ]; then
    echo -e "${YELLOW}🗺️ Copying updated maps...${NC}"
    copy_files "../maps" "/tmp/"
    copy_files "$TEMP_DIR/maps_checksums.txt" "/tmp/"
else
    echo -e "${GREEN}🗺️ Maps unchanged, skipping...${NC}"
fi

if [ "$ALEMBIC_CHANGED" = "true" ]; then
    echo -e "${YELLOW}🗄️ Copying updated alembic...${NC}"
    copy_files "../alembic" "/tmp/"
    copy_files "$TEMP_DIR/alembic_checksums.txt" "/tmp/"
else
    echo -e "${GREEN}��️ Alembic unchanged, skipping...${NC}"
fi

# Always copy requirements.txt (it's small and important)
echo -e "${YELLOW}📦 Copying requirements.txt and config files...${NC}"
copy_files "../requirements.txt" "/tmp/"
copy_files "../alembic.ini" "/tmp/"

# Copy demo script if it exists
if [ -f "../demo_perfect_game.py" ]; then
    echo -e "${YELLOW}📄 Copying demo_perfect_game.py...${NC}"
    copy_files "../demo_perfect_game.py" "/tmp/"
fi

# Copy dashboard files if they exist
DASHBOARD_DIR="../src/server/dashboard"
if [ -d "$DASHBOARD_DIR" ]; then
    echo -e "${YELLOW}📊 Copying dashboard files...${NC}"
    copy_files "$DASHBOARD_DIR" "/tmp/dashboard"
fi

# Deploy the application
echo -e "${YELLOW}Deploying application on instance...${NC}"
run_ssh "
    # Deploy source code if changed
    if [ -d '/tmp/src' ]; then
        sudo rm -rf /opt/diplomacy/src
        sudo cp -r /tmp/src /opt/diplomacy/
        sudo chown -R diplomacy:diplomacy /opt/diplomacy/src
        echo '✅ Source code deployed'
    fi
    
    # Deploy maps if changed
    if [ -d '/tmp/maps' ]; then
        sudo rm -rf /opt/diplomacy/maps
        sudo cp -r /tmp/maps /opt/diplomacy/
        sudo chown -R diplomacy:diplomacy /opt/diplomacy/maps
        echo '✅ Maps deployed'
    fi
    
    # Deploy alembic if changed
    if [ -d '/tmp/alembic' ]; then
        sudo rm -rf /opt/diplomacy/alembic
        sudo cp -r /tmp/alembic /opt/diplomacy/
        sudo chown -R diplomacy:diplomacy /opt/diplomacy/alembic
        echo '✅ Alembic deployed'
    fi
    
    # Always deploy requirements and config
    sudo cp /tmp/requirements.txt /opt/diplomacy/
    sudo cp /tmp/alembic.ini /opt/diplomacy/ 2>/dev/null || true
    sudo chown diplomacy:diplomacy /opt/diplomacy/requirements.txt
    sudo chown diplomacy:diplomacy /opt/diplomacy/alembic.ini 2>/dev/null || true
    
    # Deploy dashboard if it exists
    if [ -d '/tmp/dashboard' ]; then
        sudo mkdir -p /opt/diplomacy/src/server/dashboard
        sudo rm -rf /opt/diplomacy/src/server/dashboard/*
        sudo cp -r /tmp/dashboard/* /opt/diplomacy/src/server/dashboard/
        sudo chown -R diplomacy:diplomacy /opt/diplomacy/src/server/dashboard
        echo '✅ Dashboard deployed'
    fi
    
    # Deploy demo script if it exists
    if [ -f '/tmp/demo_perfect_game.py' ]; then
        sudo cp /tmp/demo_perfect_game.py /opt/diplomacy/
        sudo chown diplomacy:diplomacy /opt/diplomacy/demo_perfect_game.py
        sudo chmod +x /opt/diplomacy/demo_perfect_game.py
        echo '✅ Demo script deployed'
    fi
    
    # Update checksums on server
    if [ -f '/tmp/src_checksums.txt' ]; then
        sudo cp /tmp/src_checksums.txt /opt/diplomacy/
    fi
    if [ -f '/tmp/maps_checksums.txt' ]; then
        sudo cp /tmp/maps_checksums.txt /opt/diplomacy/
    fi
    if [ -f '/tmp/alembic_checksums.txt' ]; then
        sudo cp /tmp/alembic_checksums.txt /opt/diplomacy/
    fi
    
    echo '🎯 Deployment completed'
"

# Install/update Python dependencies only if requirements changed
echo -e "${YELLOW}Checking Python dependencies...${NC}"
if [ "$SRC_CHANGED" = "true" ] || [ "$REQUIREMENTS_CHANGED" = "true" ]; then
    echo -e "${YELLOW}Installing/updating Python dependencies...${NC}"
    run_ssh "
        # Install dependencies with better error handling
        echo 'Installing Python dependencies...'
        # Check pip version - --break-system-packages is only available in pip 23.0+
        PIP_VERSION=\$(pip3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)
        if [ \"\$PIP_VERSION\" -ge 23 ] 2>/dev/null; then
            sudo -u diplomacy pip3 install --user --no-warn-script-location --break-system-packages -r /opt/diplomacy/requirements.txt
        else
            sudo -u diplomacy pip3 install --user --no-warn-script-location -r /opt/diplomacy/requirements.txt
        fi
        
        # Verify critical dependencies are installed
        echo 'Verifying critical dependencies...'
        sudo -u diplomacy python3 -c 'import PIL; print(\"PIL/Pillow: OK\")' || echo 'ERROR: PIL/Pillow not installed'
        sudo -u diplomacy python3 -c 'import fastapi; print(\"FastAPI: OK\")' || echo 'ERROR: FastAPI not installed'
        sudo -u diplomacy python3 -c 'import sqlalchemy; print(\"SQLAlchemy: OK\")' || echo 'ERROR: SQLAlchemy not installed'
        
        echo 'Dependency installation completed'
    "
else
    echo -e "${GREEN}No source changes, skipping dependency update...${NC}"
fi

# Reset database if requested
if [ "$RESET_DB" = true ]; then
    echo -e "${RED}⚠️  RESETTING DATABASE - This will delete ALL data!${NC}"
    echo -e "${YELLOW}Dropping and recreating database...${NC}"
    
    # Create a temporary script on the remote server to avoid heredoc issues
    run_ssh "cat > /tmp/reset_db.sh << 'SCRIPT_EOF'
#!/bin/bash
set -e
cd /opt/diplomacy

# Get database connection URL from .env file
if [ ! -f /opt/diplomacy/.env ]; then
    echo 'Error: .env file not found'
    exit 1
fi

export SQLALCHEMY_DATABASE_URL=\$(grep SQLALCHEMY_DATABASE_URL /opt/diplomacy/.env | cut -d '=' -f2- | tr -d '\"\"\\\"''')

if [ -z \"\$SQLALCHEMY_DATABASE_URL\" ]; then
    echo 'Error: SQLALCHEMY_DATABASE_URL not found in .env file'
    exit 1
fi

# Parse PostgreSQL connection string: postgresql+psycopg2://user:password@host:port/database
# More robust parsing using sed patterns
# Remove protocol prefix (postgresql+psycopg2:// or postgresql://)
DB_CONN=\$(echo \"\$SQLALCHEMY_DATABASE_URL\" | sed -E 's|^postgresql(\+psycopg2)?://||')
# Extract user (everything before first colon)
DB_USER=\$(echo \"\$DB_CONN\" | sed -E 's|:.*$||')
# Extract password (between first colon and @)
DB_PASS=\$(echo \"\$DB_CONN\" | sed -E 's|^[^:]+:([^@]+)@.*|\1|')
# Extract host (between @ and / or :)
DB_HOST=\$(echo \"\$DB_CONN\" | sed -E 's|^[^@]+@([^:/]+)[:/].*|\1|')
# Extract port (after : but before /, optional)
DB_PORT=\$(echo \"\$DB_CONN\" | sed -E 's|^[^@]+@[^:]+:([^/]+)/.*|\1|' 2>/dev/null || echo '5432')
# Extract database name (after last /, before ? or end)
DB_NAME=\$(echo \"\$DB_CONN\" | sed -E 's|^.+/([^?]+).*|\1|')

# If port is empty, default to 5432
if [ -z \"\$DB_PORT\" ]; then
    DB_PORT=5432
fi

# Validate extracted values
if [ -z \"\$DB_NAME\" ] || [ \"\$DB_NAME\" = \"\$DB_CONN\" ] || [ -z \"\$DB_USER\" ]; then
    echo \"Error: Could not extract DB_NAME or DB_USER from connection string\"
    echo \"Original connection string (sanitized): \$(echo \$SQLALCHEMY_DATABASE_URL | sed 's/:[^:@]*@/:***@/')\"
    echo \"Parsed DB_CONN: \$DB_CONN\"
    echo \"Parsed values: DB_NAME=\$DB_NAME, DB_USER=\$DB_USER, DB_HOST=\$DB_HOST, DB_PORT=\$DB_PORT\"
    exit 1
fi

echo \"Resetting database: \$DB_NAME for user: \$DB_USER\"

# Terminate active connections (ignore errors)
sudo -u postgres psql -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\$DB_NAME' AND pid <> pg_backend_pid();\" 2>/dev/null || true

# Drop and recreate database
sudo -u postgres psql -c \"DROP DATABASE IF EXISTS \\\"\$DB_NAME\\\";\" || true
sudo -u postgres psql -c \"CREATE DATABASE \\\"\$DB_NAME\\\" OWNER \\\"\$DB_USER\\\";\" || {
    echo \"Error: Failed to create database\"
    exit 1
}

# Grant privileges
sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE \\\"\$DB_NAME\\\" TO \\\"\$DB_USER\\\";\" || {
    echo \"Error: Failed to grant privileges\"
    exit 1
}

echo '✅ Database reset completed'
SCRIPT_EOF
chmod +x /tmp/reset_db.sh"
    
    # Execute the script
    run_ssh "sudo bash /tmp/reset_db.sh" || {
        echo -e "${RED}Error: Database reset failed${NC}"
        exit 1
    }
    
    # Clean up temporary script
    run_ssh "rm -f /tmp/reset_db.sh"
    
    echo -e "${GREEN}✅ Database reset completed${NC}"
fi

# Copy reset script if it exists locally
if [ -f "../reset_database.py" ]; then
    echo -e "${YELLOW}📄 Copying database reset script...${NC}"
    copy_files "../reset_database.py" "/tmp/"
    run_ssh "
        sudo cp /tmp/reset_database.py /opt/diplomacy/
        sudo chown diplomacy:diplomacy /opt/diplomacy/reset_database.py
        sudo chmod +x /opt/diplomacy/reset_database.py
    "
fi

# Run database migrations if alembic is present and changed, or if this is a fresh deployment, or if DB was reset
if ([ "$RESET_DB" = "true" ] || [ "$ALEMBIC_CHANGED" = "true" ] || [ "$SRC_CHANGED" = "true" ]) && run_ssh "test -f /opt/diplomacy/alembic.ini"; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    run_ssh "
        cd /opt/diplomacy
        export PYTHONPATH=\"/opt/diplomacy/src:\${PYTHONPATH:-}\"
        export SQLALCHEMY_DATABASE_URL=\$(grep SQLALCHEMY_DATABASE_URL /opt/diplomacy/.env | cut -d '=' -f2- | tr -d '\"\"\\\"''')
        
        # Handle migrations - always use 'heads' which works for both single and multiple heads
        # 'alembic upgrade heads' works correctly whether there's one head or multiple heads
        echo 'Running database migrations...'
        sudo -u diplomacy /home/diplomacy/.local/bin/alembic upgrade heads
    " || {
        echo -e "${RED}⚠️  Migration failed!${NC}"
        echo -e "${YELLOW}Attempting to diagnose the issue...${NC}"
        run_ssh "
            cd /opt/diplomacy
            export PYTHONPATH=\"/opt/diplomacy/src:\${PYTHONPATH:-}\"
            sudo -u diplomacy env PYTHONPATH=\"/opt/diplomacy/src\" python3 -c 'import sys; sys.path.insert(0, \"/opt/diplomacy/src\"); from engine.database import Base; print(\"✅ Import successful\")' || echo '❌ Import failed'
        "
        echo -e "${YELLOW}Continuing deployment despite migration failure...${NC}"
    }
else
    echo -e "${GREEN}No alembic changes, skipping migrations...${NC}"
fi

# Ensure database schema is initialized (even if migrations don't run or fail)
echo -e "${YELLOW}Ensuring database schema is initialized...${NC}"
run_ssh "
    cd /opt/diplomacy
    
    # Read SQLALCHEMY_DATABASE_URL from .env file (handle quotes)
    SQLALCHEMY_DATABASE_URL=\$(grep '^SQLALCHEMY_DATABASE_URL=' /opt/diplomacy/.env | cut -d '=' -f2- | tr -d '\"\"\\\"''' | xargs)
    
    if [ -z \"\$SQLALCHEMY_DATABASE_URL\" ]; then
        echo '⚠️  Warning: SQLALCHEMY_DATABASE_URL not found in .env file'
        echo '   Schema initialization will be skipped'
    else
        echo 'Initializing database schema...'
        # Pass environment variables explicitly to sudo, and read .env in Python as fallback
        sudo -u diplomacy env PYTHONPATH=\"/opt/diplomacy/src\" SQLALCHEMY_DATABASE_URL=\"\$SQLALCHEMY_DATABASE_URL\" python3 << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, '/opt/diplomacy/src')

try:
    from sqlalchemy import create_engine, inspect
    from engine.database import create_database_schema
    
    # Try to get from environment first, then read from .env file as fallback
    db_url = os.environ.get('SQLALCHEMY_DATABASE_URL')
    if not db_url:
        # Fallback: read directly from .env file
        env_file = '/opt/diplomacy/.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('SQLALCHEMY_DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip()
                        # Remove quotes if present
                        db_url = db_url.strip('\"').strip(\"'\")
                        break
    
    if not db_url:
        print('❌ SQLALCHEMY_DATABASE_URL not set and could not be read from .env file')
        sys.exit(1)
    
    # Check if schema exists
    engine = create_engine(db_url)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if 'games' not in tables:
            print('📊 Database schema not found, creating...')
            schema_engine = create_database_schema(db_url)
            schema_engine.dispose()
            
            # Verify creation
            verify_engine = create_engine(db_url)
            verify_inspector = inspect(verify_engine)
            verify_tables = verify_inspector.get_table_names()
            verify_engine.dispose()
            
            if 'games' in verify_tables:
                print('✅ Database schema initialized successfully')
            else:
                print('❌ Schema creation failed verification')
                sys.exit(1)
        else:
            print('✅ Database schema already exists')
    except Exception as e:
        print(f'❌ Error checking/creating schema: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        engine.dispose()
except ImportError as e:
    print(f'❌ Failed to import database modules: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT
    fi
" || {
    echo -e "${RED}⚠️  Schema initialization failed, but continuing deployment...${NC}"
    echo -e "${YELLOW}The server will attempt to initialize schema on startup${NC}"
}

# Fix systemd service configurations (telegram bot and Nginx)
echo -e "${YELLOW}Ensuring service configurations are correct...${NC}"
run_ssh "
    # Fix telegram bot service configuration
    sudo tee /etc/systemd/system/diplomacy-bot.service > /dev/null << 'BOTSERVICEEOF'
[Unit]
Description=Diplomacy Telegram Bot
After=network.target postgresql.service diplomacy.service
Requires=postgresql.service

[Service]
Type=simple
User=diplomacy
WorkingDirectory=/opt/diplomacy
EnvironmentFile=/opt/diplomacy/.env
ExecStart=/usr/bin/python3 /opt/diplomacy/src/server/run_telegram_bot.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
BOTSERVICEEOF

    # Fix Nginx configuration with explicit dashboard routing
    sudo tee /etc/nginx/sites-available/diplomacy > /dev/null << 'NGINXCONFEOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    server_name _;
    
    client_max_body_size 10M;
    
    # Explicit dashboard location (must come before location /)
    location /dashboard {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_redirect off;
        proxy_buffering off;
    }
    
    # Dashboard static files
    location /dashboard/static {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        expires 1h;
    }
    
    # Health check
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
    
    # API endpoints
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_redirect off;
    }
    
    # Default location
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \"upgrade\";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        proxy_redirect off;
        proxy_buffering off;
    }
}
NGINXCONFEOF

    # Test and reload Nginx
    if sudo nginx -t > /dev/null 2>&1; then
        sudo systemctl reload nginx
        echo '✅ Nginx configuration updated'
    else
        echo '⚠️  Nginx configuration test failed, but continuing...'
        sudo nginx -t || true
    fi
    
    # Reload systemd to pick up service changes
    sudo systemctl daemon-reload
    echo '✅ Systemd configuration reloaded'
"

# Restart services only if code changed or if schema was initialized
if [ "$SRC_CHANGED" = "true" ] || [ "$RESET_DB" = "true" ]; then
    echo -e "${YELLOW}Restarting diplomacy services (code changed or database reset)...${NC}"
    run_ssh "sudo systemctl restart diplomacy"
    run_ssh "sudo systemctl restart diplomacy-bot"
    echo -e "${GREEN}Services restarted with updated configuration${NC}"
else
    echo -e "${GREEN}No code changes, services remain running...${NC}"
    # Still restart telegram bot to ensure it's using the correct configuration
    echo -e "${YELLOW}Restarting telegram bot to ensure correct configuration...${NC}"
    run_ssh "sudo systemctl restart diplomacy-bot"
fi

# Wait a moment for service to start
sleep 3

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
SERVICE_STATUS=$(run_ssh "sudo systemctl is-active diplomacy" || echo "failed")
BOT_STATUS=$(run_ssh "sudo systemctl is-active diplomacy-bot" || echo "failed")

if [ "$SERVICE_STATUS" = "active" ] && [ "$BOT_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ Both services are running!${NC}"
elif [ "$SERVICE_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ API service is running${NC}"
    echo -e "${YELLOW}⚠ Bot service status: $BOT_STATUS${NC}"
else
    echo -e "${RED}✗ Services failed to start properly${NC}"
    echo "Check the logs with:"
    echo "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -n 20'"
    echo "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy-bot -n 20'"
fi

# Test the API endpoint
echo -e "${YELLOW}Testing API endpoint...${NC}"
if run_ssh "curl -f http://localhost:8000/ > /dev/null 2>&1"; then
    echo -e "${GREEN}✓ API is responding!${NC}"
else
    echo -e "${YELLOW}⚠ API is not responding yet (may still be starting up)${NC}"
fi

# Show final status
echo -e "${YELLOW}Getting final status...${NC}"
# Run status.sh without sudo - it can check status without elevated privileges for most things
run_ssh "/opt/diplomacy/status.sh || echo 'Status check completed (some commands may require sudo)'"

# Clean up temporary files
rm -rf "$TEMP_DIR"

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo -e "${GREEN}Your Diplomacy server is now running at:${NC}"
echo -e "API: ${GREEN}http://$INSTANCE_IP:8000${NC}"
echo -e "API Docs: ${GREEN}http://$INSTANCE_IP:8000/docs${NC}"
echo -e "Dashboard: ${GREEN}http://$INSTANCE_IP/dashboard${NC}"
echo -e "Via Nginx: ${GREEN}http://$INSTANCE_IP${NC}"
echo ""
echo -e "${BLUE}Deployment Summary:${NC}"
echo -e "  📁 Source: $([ "$SRC_CHANGED" = "true" ] && echo "Updated" || echo "Unchanged")"
echo -e "  🗺️ Maps: $([ "$MAPS_CHANGED" = "true" ] && echo "Updated" || echo "Unchanged")"
echo -e "  ��️ Alembic: $([ "$ALEMBIC_CHANGED" = "true" ] && echo "Updated" || echo "Unchanged")"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "SSH to instance: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP${NC}"
echo -e "View logs: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -f'${NC}"
echo -e "Check status: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo /opt/diplomacy/status.sh'${NC}"
echo ""
echo -e "${GREEN}Happy gaming!${NC} 🎲"