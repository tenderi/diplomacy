#!/bin/bash

# Quick fix script for missing PIL/Pillow dependency
# This script can be run immediately to fix the current deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Diplomacy Dependency Fix Script ===${NC}"

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

# Get key name from Terraform
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)
if [ -z "$KEY_NAME" ]; then
    KEY_NAME=$(terraform output -json 2>/dev/null | jq -r '.key_name.value // empty' 2>/dev/null)
fi

if [ -z "$KEY_NAME" ]; then
    echo -e "${YELLOW}Warning: Could not get key name from Terraform output${NC}"
    read -p "Please enter your EC2 key pair name: " KEY_NAME
else
    echo -e "${GREEN}Retrieved key name from Terraform: $KEY_NAME${NC}"
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"

# Check if key file exists
if [ ! -f "${KEY_PATH/#\~/$HOME}" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_PATH${NC}"
    exit 1
fi

echo -e "${YELLOW}Using key file: $KEY_PATH${NC}"

# Function to run SSH command
run_ssh() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "$1"
}

# Wait for instance to be ready
echo -e "${YELLOW}Waiting for instance to be ready...${NC}"
for i in {1..10}; do
    if run_ssh "echo 'Instance ready'" &>/dev/null; then
        echo -e "${GREEN}Instance is ready!${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}Error: Instance is not responding${NC}"
        exit 1
    fi
    echo "Waiting... ($i/10)"
    sleep 5
done

echo -e "${BLUE}=== Installing Missing Dependencies ===${NC}"

# Install missing dependencies
run_ssh "
    echo 'Installing missing Python dependencies...'
    
    # Update pip first
    sudo -u diplomacy pip3 install --user --upgrade pip
    
    # Check pip version - --break-system-packages is only available in pip 23.0+
    PIP_VERSION=\$(pip3 --version | grep -oE '[0-9]+\.[0-9]+' | head -1 | cut -d. -f1)
    if [ \"\$PIP_VERSION\" -ge 23 ] 2>/dev/null; then
        PIP_EXTRA_FLAGS=\"--break-system-packages\"
    else
        PIP_EXTRA_FLAGS=\"\"
    fi
    
    # Install Pillow specifically (this is the missing dependency)
    if [ -n \"\$PIP_EXTRA_FLAGS\" ]; then
        sudo -u diplomacy pip3 install --user \$PIP_EXTRA_FLAGS Pillow
        sudo -u diplomacy pip3 install --user \$PIP_EXTRA_FLAGS fastapi uvicorn sqlalchemy psycopg2-binary
    else
        sudo -u diplomacy pip3 install --user Pillow
        sudo -u diplomacy pip3 install --user fastapi uvicorn sqlalchemy psycopg2-binary
    fi
    
    # Verify installation
    echo 'Verifying PIL/Pillow installation...'
    sudo -u diplomacy python3 -c 'import PIL; print(\"✅ PIL/Pillow: OK\")' || echo '❌ ERROR: PIL/Pillow still not installed'
    
    echo 'Dependency installation completed'
"

echo -e "${BLUE}=== Restarting Services ===${NC}"

# Restart the services
run_ssh "
    echo 'Restarting diplomacy services...'
    sudo systemctl restart diplomacy
    sudo systemctl restart diplomacy-bot
    
    # Wait a moment for services to start
    sleep 3
    
    # Check service status
    echo 'Checking service status...'
    sudo systemctl is-active diplomacy && echo '✅ diplomacy service: active' || echo '❌ diplomacy service: failed'
    sudo systemctl is-active diplomacy-bot && echo '✅ diplomacy-bot service: active' || echo '❌ diplomacy-bot service: failed'
"

# Check final status
echo -e "${YELLOW}Checking final service status...${NC}"
SERVICE_STATUS=$(run_ssh "sudo systemctl is-active diplomacy" || echo "failed")
BOT_STATUS=$(run_ssh "sudo systemctl is-active diplomacy-bot" || echo "failed")

if [ "$SERVICE_STATUS" = "active" ] && [ "$BOT_STATUS" = "active" ]; then
    echo -e "${GREEN}✅ Both services are running!${NC}"
elif [ "$SERVICE_STATUS" = "active" ]; then
    echo -e "${GREEN}✅ API service is running${NC}"
    echo -e "${YELLOW}⚠ Bot service status: $BOT_STATUS${NC}"
else
    echo -e "${RED}❌ Services failed to start properly${NC}"
    echo "Check the logs with:"
    echo "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy-bot -n 20'"
fi

echo -e "${GREEN}=== Fix Complete! ===${NC}"
echo ""
echo -e "${GREEN}Your Diplomacy server should now be running at:${NC}"
echo -e "API: ${GREEN}http://$INSTANCE_IP:8000${NC}"
echo -e "API Docs: ${GREEN}http://$INSTANCE_IP:8000/docs${NC}"
echo ""
echo -e "${YELLOW}If services are still not working, check the logs:${NC}"
echo -e "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy-bot -f'"