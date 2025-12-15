#!/bin/bash
# Fix sudoers configuration for diplomacy user to allow systemctl commands

echo "Fixing sudoers configuration..."

# Backup existing sudoers file
if [ -f "/etc/sudoers.d/diplomacy-systemctl" ]; then
    cp /etc/sudoers.d/diplomacy-systemctl /etc/sudoers.d/diplomacy-systemctl.backup
    echo "Backed up existing sudoers file"
fi

# Create fixed sudoers file
cat > /tmp/diplomacy-systemctl << 'SUDO_EOF'
# Allow diplomacy user to run systemctl and journalctl commands for dashboard
# Note: Each command must be on a separate line for proper sudoers syntax
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status diplomacy
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl status diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active diplomacy
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl is-active diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart diplomacy
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl start diplomacy
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl start diplomacy-bot
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop diplomacy
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop diplomacy-bot
# Allow journalctl with various flags
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u diplomacy *
diplomacy ALL=(ALL) NOPASSWD: /usr/bin/journalctl -u diplomacy-bot *
SUDO_EOF

# Validate sudoers syntax
if visudo -c -f /tmp/diplomacy-systemctl 2>/dev/null; then
    echo "✓ Sudoers syntax is valid"
    # Install the file
    sudo cp /tmp/diplomacy-systemctl /etc/sudoers.d/diplomacy-systemctl
    sudo chmod 0440 /etc/sudoers.d/diplomacy-systemctl
    echo "✓ Sudoers file updated"
    
    # Test one of the commands
    echo "Testing sudo access..."
    if sudo -u diplomacy sudo -n systemctl is-active diplomacy-bot 2>/dev/null; then
        echo "✓ Sudo access is working"
    else
        echo "⚠ Sudo access test failed (this might be expected if service is not running)"
    fi
else
    echo "✗ Sudoers syntax is invalid - not updating"
    exit 1
fi

echo ""
echo "Sudoers configuration fixed!"
echo "The dashboard should now be able to check service status without errors."

