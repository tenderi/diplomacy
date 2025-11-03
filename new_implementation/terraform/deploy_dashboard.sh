#!/bin/bash

# Deployment script for Diplomacy Dashboard
# This script copies the dashboard files and restarts the API service
#
# Usage:
#   ./deploy_dashboard.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Diplomacy Dashboard Deployment Script ===${NC}"

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

# Check if dashboard directory exists locally
DASHBOARD_DIR="../src/server/dashboard"
if [ ! -d "$DASHBOARD_DIR" ]; then
    echo -e "${RED}Error: Dashboard directory not found at $DASHBOARD_DIR${NC}"
    echo "Make sure you're running this script from the terraform directory"
    echo "Expected path: new_implementation/terraform/deploy_dashboard.sh"
    exit 1
fi

echo -e "${GREEN}Found dashboard directory: $DASHBOARD_DIR${NC}"

# Copy dashboard files to server
echo -e "${BLUE}=== Transferring Dashboard Files ===${NC}"
echo -e "${YELLOW}📁 Copying dashboard files...${NC}"

# Copy the dashboard directory to /tmp on the server
copy_files "$DASHBOARD_DIR" "/tmp/dashboard"

echo -e "${YELLOW}Deploying dashboard on instance...${NC}"
run_ssh "
    # Create dashboard directory if it doesn't exist
    sudo mkdir -p /opt/diplomacy/src/server/dashboard
    
    # Remove old dashboard files
    sudo rm -rf /opt/diplomacy/src/server/dashboard/*
    
    # Copy new dashboard files
    sudo cp -r /tmp/dashboard/* /opt/diplomacy/src/server/dashboard/
    
    # Set correct ownership
    sudo chown -R diplomacy:diplomacy /opt/diplomacy/src/server/dashboard
    
    # Verify dashboard files are in place
    if [ -f '/opt/diplomacy/src/server/dashboard/index.html' ]; then
        echo '✅ Dashboard HTML file deployed'
    else
        echo '❌ Error: Dashboard HTML file not found after deployment'
        exit 1
    fi
    
    if [ -d '/opt/diplomacy/src/server/dashboard/static' ]; then
        echo '✅ Dashboard static directory deployed'
    else
        echo '❌ Error: Dashboard static directory not found after deployment'
        exit 1
    fi
    
    echo '🎯 Dashboard deployment completed'
"

# Restart the diplomacy service to load new routes
echo -e "${YELLOW}Restarting diplomacy service to load dashboard routes...${NC}"
run_ssh "
    sudo systemctl restart diplomacy
    sleep 2
    
    # Check if service is running
    if sudo systemctl is-active --quiet diplomacy; then
        echo '✅ Diplomacy service restarted successfully'
    else
        echo '⚠️  Warning: Diplomacy service may not be running'
        echo 'Checking service status...'
        sudo systemctl status diplomacy --no-pager -l || true
    fi
"

# Test dashboard endpoint
echo -e "${YELLOW}Testing dashboard endpoint...${NC}"
if run_ssh "curl -f -s http://localhost:8000/dashboard > /dev/null 2>&1"; then
    echo -e "${GREEN}✅ Dashboard endpoint is responding!${NC}"
else
    echo -e "${YELLOW}⚠️  Dashboard endpoint may not be accessible yet (service may still be starting)${NC}"
fi

# Show final status
echo ""
echo -e "${GREEN}=== Dashboard Deployment Complete! ===${NC}"
echo ""
echo -e "${GREEN}Your dashboard is now available at:${NC}"
echo -e "Dashboard: ${GREEN}http://$INSTANCE_IP/dashboard${NC}"
echo -e "Via Nginx: ${GREEN}http://$INSTANCE_IP/dashboard${NC}"
echo -e "Direct API: ${GREEN}http://$INSTANCE_IP:8000/dashboard${NC}"
echo ""
echo -e "${BLUE}Deployment Summary:${NC}"
echo -e "  📊 Dashboard files: ${GREEN}Deployed${NC}"
echo -e "  🔄 Service restart: ${GREEN}Completed${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "SSH to instance: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP${NC}"
echo -e "View dashboard: ${YELLOW}http://$INSTANCE_IP/dashboard${NC}"
echo -e "Check service: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo systemctl status diplomacy'${NC}"
echo -e "View logs: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -f'${NC}"

