#!/bin/bash

# Script to retrieve logs from remote Diplomacy server
# Usage: ./get_server_logs.sh [--all] [--tail N]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
SHOW_ALL=false
TAIL_LINES=50

for arg in "$@"; do
    case $arg in
        --all|-a)
            SHOW_ALL=true
            shift
            ;;
        --tail|-t)
            shift
            TAIL_LINES="$1"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--all] [--tail N]"
            echo ""
            echo "Options:"
            echo "  --all, -a              Show all logs (not just recent)"
            echo "  --tail, -t N           Show last N lines (default: 50)"
            echo "  --help, -h             Show this help message"
            exit 0
            ;;
        *)
            ;;
    esac
done

# Check if terraform is available
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

# Get key name from Terraform
KEY_NAME=$(terraform output -raw key_name 2>/dev/null)

if [ -z "$KEY_NAME" ]; then
    KEY_NAME=$(terraform output -json 2>/dev/null | jq -r '.key_name.value // empty' 2>/dev/null)
fi

if [ -z "$KEY_NAME" ]; then
    echo -e "${YELLOW}Warning: Could not get key name from Terraform output${NC}"
    read -p "Please enter your EC2 key pair name: " KEY_NAME
fi

KEY_PATH="~/.ssh/${KEY_NAME}.pem"

# Check if key file exists
if [ ! -f "${KEY_PATH/#\~/$HOME}" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_PATH${NC}"
    exit 1
fi

# Function to run SSH command
run_ssh() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no ubuntu@$INSTANCE_IP "$1"
}

echo -e "${GREEN}=== Retrieving Diplomacy Server Logs ===${NC}"
echo -e "Server: ${BLUE}$INSTANCE_IP${NC}"
echo ""

# Get API service logs
echo -e "${YELLOW}📋 API Service Logs (diplomacy)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$SHOW_ALL" = "true" ]; then
    run_ssh "sudo journalctl -u diplomacy --no-pager" || echo "Could not retrieve logs"
else
    run_ssh "sudo journalctl -u diplomacy -n $TAIL_LINES --no-pager" || echo "Could not retrieve logs"
fi
echo ""

# Get Bot service logs
echo -e "${YELLOW}📋 Bot Service Logs (diplomacy-bot)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$SHOW_ALL" = "true" ]; then
    run_ssh "sudo journalctl -u diplomacy-bot --no-pager" || echo "Could not retrieve logs"
else
    run_ssh "sudo journalctl -u diplomacy-bot -n $TAIL_LINES --no-pager" || echo "Could not retrieve logs"
fi
echo ""

# Get recent error logs only
echo -e "${YELLOW}🚨 Recent Errors (last 30 lines)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
run_ssh "sudo journalctl -u diplomacy --no-pager -p err -n 30" || echo "No error-level logs found"
echo ""

# Check service status
echo -e "${YELLOW}📊 Service Status${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
run_ssh "sudo systemctl status diplomacy --no-pager -l || true"
echo ""
run_ssh "sudo systemctl status diplomacy-bot --no-pager -l || true"
echo ""

# Check database schema initialization
echo -e "${YELLOW}🗄️  Database Schema Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
run_ssh "
    cd /opt/diplomacy
    export PYTHONPATH=\"/opt/diplomacy/src:\${PYTHONPATH:-}\"
    export SQLALCHEMY_DATABASE_URL=\$(grep '^SQLALCHEMY_DATABASE_URL=' /opt/diplomacy/.env 2>/dev/null | cut -d '=' -f2- | tr -d '\"\"\\\"''' | xargs)
    
    if [ -z \"\$SQLALCHEMY_DATABASE_URL\" ]; then
        echo '❌ SQLALCHEMY_DATABASE_URL not found in .env file'
    else
        echo 'Checking database schema...'
        sudo -u diplomacy env PYTHONPATH=\"/opt/diplomacy/src\" SQLALCHEMY_DATABASE_URL=\"\$SQLALCHEMY_DATABASE_URL\" python3 << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, '/opt/diplomacy/src')

try:
    from sqlalchemy import create_engine, inspect
    
    db_url = os.environ.get('SQLALCHEMY_DATABASE_URL')
    if not db_url:
        env_file = '/opt/diplomacy/.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if line.startswith('SQLALCHEMY_DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
                        break
    
    if db_url:
        engine = create_engine(db_url)
        try:
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            print(f'✅ Database connection successful')
            print(f'   Found tables: {len(tables)}')
            if 'games' in tables:
                print('✅ Schema exists: games table found')
            else:
                print('❌ Schema missing: games table not found')
            if 'users' in tables:
                print('✅ Schema exists: users table found')
            else:
                print('❌ Schema missing: users table not found')
        except Exception as e:
            print(f'❌ Error checking schema: {e}')
        finally:
            engine.dispose()
    else:
        print('❌ Could not determine database URL')
except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
PYTHON_SCRIPT
    fi
" || echo "Could not check database schema"
echo ""

# Check .env file (sanitized)
echo -e "${YELLOW}⚙️  Environment Configuration (sanitized)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
run_ssh "
    if [ -f /opt/diplomacy/.env ]; then
        echo 'Environment variables in .env:'
        grep -E '^(SQLALCHEMY_DATABASE_URL|db_|PYTHONPATH)=' /opt/diplomacy/.env | sed 's/=.*/=***/' || echo 'No relevant variables found'
    else
        echo '❌ .env file not found'
    fi
"
echo ""

echo -e "${GREEN}=== Log Retrieval Complete ===${NC}"
echo ""
echo -e "${YELLOW}To view logs in real-time:${NC}"
echo -e "  ${BLUE}ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'sudo journalctl -u diplomacy -f'${NC}"
echo ""

