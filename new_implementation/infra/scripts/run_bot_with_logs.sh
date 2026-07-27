#!/usr/bin/env bash

# Script to run the telegram bot with enhanced logging
set -e

# Resolve new_implementation/ regardless of caller's cwd, so PYTHONPATH is
# set consistently with the systemd unit (WorkingDirectory=new_implementation,
# PYTHONPATH=<new_implementation>/src).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEW_IMPL_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
export PYTHONPATH="$NEW_IMPL_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

# Default log file
LOG_FILE="${DIPLOMACY_LOG_FILE:-./bot.log}"
LOG_LEVEL="${DIPLOMACY_LOG_LEVEL:-INFO}"

echo "🤖 Starting Telegram Bot with enhanced logging"
echo "📝 Log file: $LOG_FILE"
echo "📊 Log level: $LOG_LEVEL"

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Set environment variables for logging
export DIPLOMACY_LOG_FILE="$LOG_FILE"
export DIPLOMACY_LOG_LEVEL="$LOG_LEVEL"

# Run the bot with logging
echo "🚀 Starting bot... (logs will appear below and in $LOG_FILE)"
python3 -m server.telegram_bot 2>&1 | tee -a "$LOG_FILE" 