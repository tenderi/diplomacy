#!/bin/bash

# Quick diagnostic script to check dashboard deployment

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== Dashboard Diagnostic ===${NC}"

# Get instance IP
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform not found${NC}"
    exit 1
fi

INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)
if [ -z "$INSTANCE_IP" ]; then
    read -p "Enter instance IP: " INSTANCE_IP
fi

echo -e "Instance: ${BLUE}$INSTANCE_IP${NC}"

# Get key
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)
if [ -z "$KEY_NAME" ]; then
    read -p "Enter key name: " KEY_NAME
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"
KEY_PATH="${KEY_PATH/#\~/$HOME}"

echo -e "${YELLOW}Checking dashboard files...${NC}"
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "
    echo 'Dashboard directory:'
    ls -la /opt/diplomacy/src/server/dashboard/ 2>&1 || echo 'NOT FOUND'
    echo ''
    echo 'Dashboard index.html:'
    ls -la /opt/diplomacy/src/server/dashboard/index.html 2>&1 || echo 'NOT FOUND'
    echo ''
    echo 'Dashboard static files:'
    ls -la /opt/diplomacy/src/server/dashboard/static/ 2>&1 || echo 'NOT FOUND'
"

echo ""
echo -e "${YELLOW}Checking API service...${NC}"
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "
    sudo systemctl status diplomacy --no-pager | head -5
    echo ''
    echo 'Testing dashboard endpoint locally:'
    curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost:8000/dashboard || echo 'FAILED'
    echo ''
    echo 'Checking if dashboard route exists in Python:'
    sudo -u diplomacy python3 -c \"
import sys
sys.path.insert(0, '/opt/diplomacy/src')
from server.api import app
routes = [r.path for r in app.routes]
if '/dashboard' in routes:
    print('✅ /dashboard route found')
else:
    print('❌ /dashboard route NOT found')
    print('Available routes:', [r for r in routes if 'dashboard' in r.lower()])
\" 2>&1
"

echo ""
echo -e "${YELLOW}Checking Nginx...${NC}"
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "
    sudo nginx -t 2>&1
    echo ''
    echo 'Testing via Nginx:'
    curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost/dashboard || echo 'FAILED'
"

echo ""
echo -e "${GREEN}=== Summary ===${NC}"
echo -e "If files are missing, run: ${YELLOW}./deploy_dashboard.sh${NC}"
echo -e "If service needs restart, run: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo systemctl restart diplomacy'${NC}"
echo -e "If code changed, run: ${YELLOW}./deploy_app.sh${NC}"

