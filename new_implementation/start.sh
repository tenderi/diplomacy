#!/usr/bin/env bash
set -e

# Debug environment variables
echo "🚀 Container startup - Environment variables:"
echo "BOT_ONLY: ${BOT_ONLY:-NOT_SET}"
echo "SQLALCHEMY_DATABASE_URL: ${SQLALCHEMY_DATABASE_URL:-NOT_SET}"
echo "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:-NOT_SET}"

# Run migrations
alembic upgrade head

# Check deployment mode
if [ "${BOT_ONLY}" = "true" ]; then
    echo "🤖 Starting in BOT_ONLY mode - telegram bot only"
    # In BOT_ONLY mode, don't start the main API server - it runs separately
    # Just start the telegram bot (which will start its own notification API on port 8081)
    python3 -m server.telegram_bot
else
    echo "🚀 Starting in FULL mode - API server + telegram bot"
    # Start API in background
    uvicorn server.api:app --host 0.0.0.0 --port 8000 &
    
    # Start Telegram bot (wait for API to be ready)
    sleep 3
    python3 -m server.telegram_bot
    
    wait
fi 