#!/bin/bash

# Deployment script for Diplomacy app to single EC2 instance
# This script copies the application code and starts the service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Diplomacy App Deployment Script ===${NC}"

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

# Copy application code
echo -e "${YELLOW}Copying application code to instance...${NC}"
copy_files "../../src" "/tmp/"
copy_files "../../maps" "/tmp/"
copy_files "../../requirements.txt" "/tmp/"
copy_files "../../alembic" "/tmp/"
copy_files "../../alembic.ini" "/tmp/"

# Deploy the application
echo -e "${YELLOW}Deploying application on instance...${NC}"
run_ssh "
    sudo rm -rf /opt/diplomacy/src
    sudo rm -rf /opt/diplomacy/maps
    sudo rm -rf /opt/diplomacy/alembic
    sudo mkdir -p /opt/diplomacy
    sudo cp -r /tmp/src /opt/diplomacy/
    sudo cp -r /tmp/maps /opt/diplomacy/
    sudo cp /tmp/requirements.txt /opt/diplomacy/
    sudo cp -r /tmp/alembic /opt/diplomacy/ 2>/dev/null || true
    sudo cp /tmp/alembic.ini /opt/diplomacy/ 2>/dev/null || true
    sudo chown -R diplomacy:diplomacy /opt/diplomacy/src
    sudo chown -R diplomacy:diplomacy /opt/diplomacy/maps
    sudo chown -R diplomacy:diplomacy /opt/diplomacy/alembic 2>/dev/null || true
    sudo chown diplomacy:diplomacy /opt/diplomacy/requirements.txt
    sudo chown diplomacy:diplomacy /opt/diplomacy/alembic.ini 2>/dev/null || true
"

# Install/update Python dependencies
echo -e "${YELLOW}Installing Python dependencies...${NC}"
run_ssh "sudo -u diplomacy pip3 install --user -r /opt/diplomacy/requirements.txt"

# Run database migrations if alembic is present
if run_ssh "test -f /opt/diplomacy/alembic.ini"; then
    echo -e "${YELLOW}Running database migrations...${NC}"
    run_ssh "cd /opt/diplomacy && sudo -u diplomacy /home/diplomacy/.local/bin/alembic upgrade head" || echo -e "${YELLOW}Note: Migration failed, but continuing...${NC}"
fi

# Restart the diplomacy service
echo -e "${YELLOW}Restarting diplomacy service...${NC}"
run_ssh "sudo systemctl restart diplomacy"

# Wait a moment for service to start
sleep 5

# Check service status
echo -e "${YELLOW}Checking service status...${NC}"
SERVICE_STATUS=$(run_ssh "sudo systemctl is-active diplomacy" || echo "failed")

if [ "$SERVICE_STATUS" = "active" ]; then
    echo -e "${GREEN}✓ Diplomacy service is running!${NC}"
else
    echo -e "${RED}✗ Diplomacy service failed to start${NC}"
    echo "Check the logs with:"
    echo "ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -n 20'"
    exit 1
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

echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo -e "${GREEN}Your Diplomacy server is now running at:${NC}"
echo -e "API: ${GREEN}http://$INSTANCE_IP:8000${NC}"
echo -e "API Docs: ${GREEN}http://$INSTANCE_IP:8000/docs${NC}"
echo -e "Via Nginx: ${GREEN}http://$INSTANCE_IP${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "SSH to instance: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP${NC}"
echo -e "View logs: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -f'${NC}"
echo -e "Check status: ${YELLOW}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo /opt/diplomacy/status.sh'${NC}"
echo ""
echo -e "${GREEN}Happy gaming!${NC} 🎲" 