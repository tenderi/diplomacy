#!/bin/bash

# Simple deployment script for the bot fixes
# Uses hardcoded server details since we know them

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Quick Fix Deployment Script ===${NC}"

# Known server details
INSTANCE_IP="18.201.18.123"
KEY_PATH="~/.ssh/helgeKeyPair.pem"

echo -e "${GREEN}Deploying to: $INSTANCE_IP${NC}"
echo -e "${YELLOW}Using key: $KEY_PATH${NC}"

# Function to run SSH command
run_ssh() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "$1"
}

# Function to copy files via SCP
copy_files() {
    scp -i "$KEY_PATH" -o StrictHostKeyChecking=no -r "$1" ubuntu@$INSTANCE_IP:"$2"
}

# Check if key file exists
if [ ! -f "${KEY_PATH/#\~/$HOME}" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_PATH${NC}"
    exit 1
fi

# Test connection
echo -e "${YELLOW}Testing connection...${NC}"
if ! run_ssh "echo 'Connection successful'" &>/dev/null; then
    echo -e "${RED}Error: Cannot connect to server${NC}"
    exit 1
fi

echo -e "${GREEN}Connection successful!${NC}"

# Copy the fixed files
echo -e "${YELLOW}Copying fixed files...${NC}"
copy_files "../../src/server/telegram_bot.py" "/tmp/"
copy_files "../../src/engine/map.py" "/tmp/"
copy_files "../../alembic/env.py" "/tmp/"
copy_files "../../maps/standard_fixed.svg" "/tmp/"

# Deploy the files
echo -e "${YELLOW}Deploying files to server...${NC}"
run_ssh "
    sudo cp /tmp/telegram_bot.py /opt/diplomacy/src/server/telegram_bot.py
    sudo cp /tmp/map.py /opt/diplomacy/src/engine/map.py
    sudo cp /tmp/env.py /opt/diplomacy/alembic/env.py
    sudo cp /tmp/standard_fixed.svg /opt/diplomacy/maps/standard_fixed.svg
    sudo chown diplomacy:diplomacy /opt/diplomacy/src/server/telegram_bot.py
    sudo chown diplomacy:diplomacy /opt/diplomacy/src/engine/map.py
    sudo chown diplomacy:diplomacy /opt/diplomacy/alembic/env.py
    sudo chown diplomacy:diplomacy /opt/diplomacy/maps/standard_fixed.svg
    echo '✅ Files deployed'
"

# Set environment variable to skip map pre-generation
echo -e "${YELLOW}Setting environment variable to skip map pre-generation...${NC}"
run_ssh "sudo systemctl set-environment SKIP_MAP_PREGEN=true"

# Restart the bot service
echo -e "${YELLOW}Restarting bot service...${NC}"
run_ssh "sudo systemctl restart diplomacy-bot"

# Wait for bot to start up
sleep 3

# Refresh the map cache by calling the refresh command via API
echo -e "${YELLOW}Refreshing map cache...${NC}"
run_ssh "curl -X POST http://localhost:8081/refresh_map_cache || echo 'Map cache refresh failed (normal if endpoint not available)'"

# Wait a moment for service to start
sleep 5

# Check service status
echo -e "${YELLOW}Checking bot service status...${NC}"
BOT_STATUS=$(run_ssh "sudo systemctl is-active diplomacy-bot" || echo "failed")

if [ "$BOT_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ Bot service is running!${NC}"
else
    echo -e "${RED}✗ Bot service failed to start${NC}"
    echo -e "${YELLOW}Checking logs...${NC}"
    run_ssh "sudo journalctl -u diplomacy-bot -n 10 --no-pager"
fi

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo -e "${YELLOW}You can now test the bot with the /start command${NC}" 