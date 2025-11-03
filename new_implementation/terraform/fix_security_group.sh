#!/bin/bash

# Quick fix script to add port 80 to the security group
# This script adds the missing HTTP ingress rule manually

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Fix Security Group - Add Port 80 ===${NC}"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed or not in PATH${NC}"
    exit 1
fi

# Get instance ID from Terraform
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed or not in PATH${NC}"
    exit 1
fi

INSTANCE_ID=$(terraform output -raw instance_id 2>/dev/null)

if [ -z "$INSTANCE_ID" ]; then
    echo -e "${RED}Error: Could not get instance ID from Terraform output${NC}"
    exit 1
fi

echo -e "${GREEN}Found instance ID: $INSTANCE_ID${NC}"

# Get security group ID from instance
echo -e "${YELLOW}Getting security group ID...${NC}"
SG_ID=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text 2>/dev/null)

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    echo -e "${RED}Error: Could not get security group ID${NC}"
    exit 1
fi

echo -e "${GREEN}Found security group ID: $SG_ID${NC}"

# Check if port 80 rule already exists
echo -e "${YELLOW}Checking if port 80 rule exists...${NC}"
EXISTING_RULE=$(aws ec2 describe-security-groups \
    --group-ids "$SG_ID" \
    --query "SecurityGroups[0].IpPermissions[?FromPort==\`80\` && ToPort==\`80\` && IpProtocol==\`tcp\`]" \
    --output json 2>/dev/null)

if [ "$EXISTING_RULE" != "[]" ] && [ -n "$EXISTING_RULE" ]; then
    echo -e "${GREEN}Port 80 rule already exists!${NC}"
    exit 0
fi

# Add port 80 ingress rule
echo -e "${YELLOW}Adding port 80 ingress rule...${NC}"
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --description "HTTP access for Nginx" \
    2>&1

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Port 80 rule added successfully!${NC}"
    echo ""
    echo -e "${GREEN}The dashboard should now be accessible at:${NC}"
    INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)
    if [ -n "$INSTANCE_IP" ]; then
        echo -e "  http://$INSTANCE_IP/dashboard"
    else
        echo -e "  http://YOUR_INSTANCE_IP/dashboard"
    fi
else
    echo -e "${RED}Failed to add port 80 rule${NC}"
    exit 1
fi

