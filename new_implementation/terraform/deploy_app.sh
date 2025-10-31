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
        find "$dir" -type f \( -name "*.py" -o -name "*.txt" -o -name "*.ini" -o -name "*.json" -o -name "*.svg" \) | \
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
echo -e "${YELLOW}📦 Copying requirements.txt...${NC}"
copy_files "../requirements.txt" "/tmp/"
copy_files "../alembic.ini" "/tmp/"

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
        sudo -u diplomacy pip3 install --user --no-warn-script-location --break-system-packages -r /opt/diplomacy/requirements.txt
        
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
    run_ssh "
        cd /opt/diplomacy
        export SQLALCHEMY_DATABASE_URL=\$(grep SQLALCHEMY_DATABASE_URL /opt/diplomacy/.env | cut -d '=' -f2-)
        sudo -u diplomacy python3 reset_database.py diplomacy_db <<< 'y' || {
            echo 'Error: Database reset script not found or failed'
            echo 'Attempting manual reset via psql...'
            DB_NAME=\$(echo \$SQLALCHEMY_DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
            DB_USER=\$(echo \$SQLALCHEMY_DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
            sudo -u postgres psql <<EOF
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\$DB_NAME' AND pid <> pg_backend_pid();
            DROP DATABASE IF EXISTS \$DB_NAME;
            CREATE DATABASE \$DB_NAME OWNER \$DB_USER;
            GRANT ALL PRIVILEGES ON DATABASE \$DB_NAME TO \$DB_USER;
            EOF
        }
        echo '✅ Database reset completed'
    "
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
    run_ssh "cd /opt/diplomacy && sudo -u diplomacy /home/diplomacy/.local/bin/alembic upgrade head" || echo -e "${YELLOW}Note: Migration failed, but continuing...${NC}"
else
    echo -e "${GREEN}No alembic changes, skipping migrations...${NC}"
fi

# Restart services only if code changed
if [ "$SRC_CHANGED" = "true" ]; then
    echo -e "${YELLOW}Restarting diplomacy services (code changed)...${NC}"
    run_ssh "sudo systemctl restart diplomacy"
    run_ssh "sudo systemctl restart diplomacy-bot"
else
    echo -e "${GREEN}No code changes, services remain running...${NC}"
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
run_ssh "sudo /opt/diplomacy/status.sh"

# Clean up temporary files
rm -rf "$TEMP_DIR"

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo -e "${GREEN}Your Diplomacy server is now running at:${NC}"
echo -e "API: ${GREEN}http://$INSTANCE_IP:8000${NC}"
echo -e "API Docs: ${GREEN}http://$INSTANCE_IP:8000/docs${NC}"
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