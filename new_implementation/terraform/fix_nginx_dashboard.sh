#!/bin/bash

# Script to fix Nginx configuration and reload it

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}=== Fix Nginx Dashboard Routing ===${NC}"

# Get instance IP
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform not found${NC}"
    exit 1
fi

INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)
if [ -z "$INSTANCE_IP" ]; then
    read -p "Enter instance IP: " INSTANCE_IP
fi

# Get key
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)
if [ -z "$KEY_NAME" ]; then
    read -p "Enter key name: " KEY_NAME
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"
KEY_PATH="${KEY_PATH/#\~/$HOME}"

echo -e "${YELLOW}Reloading Nginx configuration...${NC}"
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "
    echo 'Testing Nginx configuration...'
    sudo nginx -t
    
    echo ''
    echo 'Reloading Nginx...'
    sudo systemctl reload nginx
    
    echo ''
    echo 'Checking Nginx status...'
    sudo systemctl status nginx --no-pager | head -5
    
    echo ''
    echo 'Testing dashboard via Nginx...'
    sleep 1
    curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost/dashboard || echo 'Still failing'
    
    echo ''
    echo 'Testing root endpoint...'
    curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost/ || echo 'Root failed'
"

echo ""
echo -e "${GREEN}=== Fix Complete ===${NC}"
echo -e "Try accessing: ${BLUE}http://$INSTANCE_IP/dashboard${NC}"

