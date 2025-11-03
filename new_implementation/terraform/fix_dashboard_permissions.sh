#!/bin/bash

# Script to fix dashboard permissions by configuring sudo access for diplomacy user
# This allows the dashboard to run systemctl commands

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Fix Dashboard Permissions ===${NC}"

# Check if terraform is available
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed or not in PATH${NC}"
    exit 1
fi

# Get instance IP
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

echo -e "${YELLOW}Configuring sudo access for diplomacy user...${NC}"

run_ssh "
    # Create sudoers configuration for diplomacy user
    echo 'Creating sudoers configuration...'
    sudo tee /etc/sudoers.d/diplomacy-systemctl > /dev/null << 'SUDO_EOF'
# Allow diplomacy user to run systemctl and journalctl commands for dashboard
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status diplomacy, /usr/bin/systemctl status diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active diplomacy, /usr/bin/systemctl is-active diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart diplomacy, /usr/bin/systemctl restart diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u diplomacy *, /usr/bin/journalctl -u diplomacy-bot *
SUDO_EOF

    # Set correct permissions
    sudo chmod 0440 /etc/sudoers.d/diplomacy-systemctl
    
    # Validate sudoers file
    if sudo visudo -cf /etc/sudoers.d/diplomacy-systemctl; then
        echo '✅ Sudo configuration is valid'
    else
        echo '❌ Error: Sudo configuration is invalid'
        exit 1
    fi
    
    echo '✅ Sudo access configured successfully'
"

echo ""
echo -e "${GREEN}=== Permissions Fixed! ===${NC}"
echo -e "The dashboard should now be able to check service status and view logs."
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Deploy the updated API code: ${YELLOW}./deploy_app.sh${NC}"
echo -e "2. Restart the diplomacy service if needed"
echo -e "3. Refresh your dashboard at: ${GREEN}http://$INSTANCE_IP/dashboard${NC}"

