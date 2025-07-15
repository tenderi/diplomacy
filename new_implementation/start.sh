#!/usr/bin/env bash
set -e

# Run migrations
alembic upgrade head

# Start API and Telegram bot
# Start API in background
uvicorn server.api:app --host 0.0.0.0 --port 8000 &

# Start Telegram bot (wait for API to be ready)
sleep 3
python3 -m server.telegram_bot

wait 