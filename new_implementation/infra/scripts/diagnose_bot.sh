#!/bin/bash
# Diagnostic script to check Telegram bot status and identify issues

echo "=== Telegram Bot Diagnostic ==="
echo ""

# Check if bot service exists
echo "1. Checking bot service..."
if systemctl list-unit-files | grep -q "diplomacy-bot.service"; then
    echo "   ✓ Service file exists"
else
    echo "   ✗ Service file NOT found"
    exit 1
fi

# Check service status
echo ""
echo "2. Service Status:"
SERVICE_STATUS=$(systemctl is-active diplomacy-bot 2>&1)
echo "   Status: $SERVICE_STATUS"

if [ "$SERVICE_STATUS" = "active" ]; then
    echo "   ✓ Service is running"
elif [ "$SERVICE_STATUS" = "inactive" ]; then
    echo "   ⚠ Service is stopped"
elif [ "$SERVICE_STATUS" = "failed" ]; then
    echo "   ✗ Service has failed"
elif [ "$SERVICE_STATUS" = "activating" ]; then
    echo "   ⏳ Service is starting..."
else
    echo "   ⚠ Unknown status: $SERVICE_STATUS"
fi

# Check recent logs
echo ""
echo "3. Recent Bot Logs (last 30 lines):"
echo "   ---"
journalctl -u diplomacy-bot -n 30 --no-pager 2>&1 | tail -30
echo "   ---"

# Check for errors in logs
echo ""
echo "4. Error Summary:"
ERROR_COUNT=$(journalctl -u diplomacy-bot --since "1 hour ago" --no-pager 2>&1 | grep -i "error\|exception\|failed\|traceback" | wc -l)
echo "   Errors in last hour: $ERROR_COUNT"

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo ""
    echo "   Recent errors:"
    journalctl -u diplomacy-bot --since "1 hour ago" --no-pager 2>&1 | grep -i "error\|exception\|failed\|traceback" | tail -10
fi

# Check environment file
echo ""
echo "5. Environment Configuration:"
if [ -f "/opt/diplomacy/.env" ]; then
    echo "   ✓ .env file exists"
    if grep -q "TELEGRAM_BOT_TOKEN" /opt/diplomacy/.env; then
        TOKEN_LINE=$(grep "TELEGRAM_BOT_TOKEN" /opt/diplomacy/.env | head -1)
        TOKEN_LENGTH=${#TOKEN_LINE}
        if [ "$TOKEN_LENGTH" -gt 30 ]; then
            echo "   ✓ TELEGRAM_BOT_TOKEN is set (length: $TOKEN_LENGTH chars)"
        else
            echo "   ⚠ TELEGRAM_BOT_TOKEN might be too short"
        fi
    else
        echo "   ✗ TELEGRAM_BOT_TOKEN NOT found in .env"
    fi
    
    if grep -q "DIPLOMACY_API_URL" /opt/diplomacy/.env; then
        API_URL=$(grep "DIPLOMACY_API_URL" /opt/diplomacy/.env | head -1 | cut -d'=' -f2)
        echo "   ✓ DIPLOMACY_API_URL is set: $API_URL"
    else
        echo "   ⚠ DIPLOMACY_API_URL not set (will use default: http://localhost:8000)"
    fi
else
    echo "   ✗ .env file NOT found at /opt/diplomacy/.env"
fi

# Check if bot script exists
echo ""
echo "6. Bot Script Check:"
if [ -f "/opt/diplomacy/src/server/run_telegram_bot.py" ]; then
    echo "   ✓ Bot script exists"
    if [ -x "/opt/diplomacy/src/server/run_telegram_bot.py" ]; then
        echo "   ✓ Bot script is executable"
    else
        echo "   ⚠ Bot script is not executable"
    fi
else
    echo "   ✗ Bot script NOT found"
fi

# Check Python dependencies
echo ""
echo "7. Python Dependencies:"
if python3 -c "import telegram" 2>/dev/null; then
    echo "   ✓ python-telegram-bot is installed"
else
    echo "   ✗ python-telegram-bot is NOT installed"
fi

# Check API connectivity
echo ""
echo "8. API Health Check:"
API_URL=${API_URL:-"http://localhost:8000"}
if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
    echo "   ✓ API is responding at $API_URL"
else
    echo "   ✗ API is NOT responding at $API_URL"
    echo "   Checking if API service is running..."
    if systemctl is-active --quiet diplomacy; then
        echo "   ✓ API service is running, but not responding to health check"
    else
        echo "   ✗ API service is NOT running"
    fi
fi

# Check file permissions
echo ""
echo "9. File Permissions:"
if [ -d "/opt/diplomacy" ]; then
    OWNER=$(stat -c '%U' /opt/diplomacy)
    if [ "$OWNER" = "diplomacy" ]; then
        echo "   ✓ /opt/diplomacy owned by diplomacy user"
    else
        echo "   ⚠ /opt/diplomacy owned by $OWNER (expected: diplomacy)"
    fi
else
    echo "   ✗ /opt/diplomacy directory not found"
fi

echo ""
echo "=== Diagnostic Complete ==="
echo ""
echo "To view full logs: sudo journalctl -u diplomacy-bot -f"
echo "To restart bot: sudo systemctl restart diplomacy-bot"
echo "To check service status: sudo systemctl status diplomacy-bot"

