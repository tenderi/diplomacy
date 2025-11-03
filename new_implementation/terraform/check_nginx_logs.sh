#!/bin/bash

# Quick script to check Nginx logs for dashboard 404 errors

set -e

INSTANCE_IP=$(terraform output -raw public_ip 2>/dev/null)
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)
KEY_PATH="~/.ssh/${KEY_NAME}.pem"
KEY_PATH="${KEY_PATH/#\~/$HOME}"

echo "Checking Nginx access and error logs..."
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "
    echo '=== Recent Nginx Access Log ==='
    sudo tail -20 /var/log/nginx/access.log 2>/dev/null | grep dashboard || echo 'No dashboard requests found'
    echo ''
    echo '=== Recent Nginx Error Log ==='
    sudo tail -20 /var/log/nginx/error.log 2>/dev/null || echo 'No errors'
    echo ''
    echo '=== Testing proxy directly ==='
    curl -v http://localhost:8000/dashboard 2>&1 | head -15
"

