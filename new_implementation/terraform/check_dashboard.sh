#!/bin/bash

# Script to check dashboard deployment status on the server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Dashboard Status Check ===${NC}"

# Check if terraform is available and get instance IP
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed or not in PATH${NC}"
    exit 1
fi

# Get instance IP from Terraform output
INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)

if [ -z "$INSTANCE_IP" ]; then
    echo -e "${RED}Error: Could not get instance IP from Terraform output${NC}"
    exit 1
fi

echo -e "${GREEN}Found instance IP: $INSTANCE_IP${NC}"

# Get key name
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)
if [ -z "$KEY_NAME" ]; then
    KEY_NAME=$(terraform output -json 2>/dev/null | jq -r '.key_name.value // empty' 2>/dev/null)
fi

if [ -z "$KEY_NAME" ]; then
    read -p "Please enter your EC2 key pair name: " KEY_NAME
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"

if [ ! -f "${KEY_PATH/#\~/$HOME}" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_PATH${NC}"
    exit 1
fi

# Function to run SSH command
run_ssh() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "$1"
}

echo -e "${BLUE}=== Checking Dashboard Files ===${NC}"
run_ssh "
    echo 'Checking if dashboard directory exists...'
    if [ -d '/opt/diplomacy/src/server/dashboard' ]; then
        echo '✅ Dashboard directory exists'
        
        echo ''
        echo 'Dashboard directory contents:'
        ls -la /opt/diplomacy/src/server/dashboard/ 2>/dev/null || echo 'Directory empty or not accessible'
        
        echo ''
        echo 'Checking for index.html...'
        if [ -f '/opt/diplomacy/src/server/dashboard/index.html' ]; then
            echo '✅ index.html exists'
            echo \"   Size: \$(stat -c%s /opt/diplomacy/src/server/dashboard/index.html) bytes\"
        else
            echo '❌ index.html NOT found'
        fi
        
        echo ''
        echo 'Checking for static directory...'
        if [ -d '/opt/diplomacy/src/server/dashboard/static' ]; then
            echo '✅ static directory exists'
            ls -la /opt/diplomacy/src/server/dashboard/static/ 2>/dev/null || echo 'Directory empty'
        else
            echo '❌ static directory NOT found'
        fi
    else
        echo '❌ Dashboard directory does NOT exist'
        echo ''
        echo 'To deploy the dashboard, run:'
        echo '  ./deploy_dashboard.sh'
    fi
"

echo ""
echo -e "${BLUE}=== Checking Service Status ===${NC}"
run_ssh "
    echo 'Diplomacy service status:'
    sudo systemctl status diplomacy --no-pager -l | head -10 || echo 'Service check failed'
"

echo ""
echo -e "${BLUE}=== Testing Dashboard Endpoint ===${NC}"
echo "Testing http://$INSTANCE_IP/dashboard..."
run_ssh "
    echo 'Testing local endpoint...'
    curl -s -o /dev/null -w 'HTTP Status: %{http_code}\nContent-Type: %{content_type}\nContent-Length: %{size_download} bytes\n' http://localhost:8000/dashboard || echo 'Endpoint test failed'
    echo ''
    echo 'First 200 characters of response:'
    curl -s http://localhost:8000/dashboard | head -c 200
    echo ''
"

echo ""
echo -e "${YELLOW}=== Summary ===${NC}"
echo -e "Dashboard URL: ${GREEN}http://$INSTANCE_IP/dashboard${NC}"
echo -e "Direct API: ${GREEN}http://$INSTANCE_IP:8000/dashboard${NC}"
echo ""
echo -e "If dashboard files are missing, run: ${YELLOW}./deploy_dashboard.sh${NC}"
echo -e "If service needs restart after code update, run: ${YELLOW}./deploy_app.sh${NC}"

