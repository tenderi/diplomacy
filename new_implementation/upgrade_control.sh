#!/bin/bash
#
# upgrade_control.sh — update the CONTROL layer on the VPS: pull, rebuild the
# bot and web images, restart, check the tunnel to the home server.
#
# The bot's queue (the bot_data volume) is untouched by a rebuild; anything a
# player sent while the home server was unreachable is still delivered.
#
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f docker-compose.control.yml"

echo "==> Pulling latest code..."
git pull --ff-only

echo "==> Rebuilding images..."
$COMPOSE build

echo "==> Recreating containers..."
$COMPOSE up -d --remove-orphans

echo "==> Cleaning up old images..."
docker image prune -f

API_URL=$(grep -E '^DIPLOMACY_API_URL=' .env 2>/dev/null | cut -d= -f2- || true)
API_URL=${API_URL:-http://10.8.0.2:8000}
WEB_PORT=$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- || true)
WEB_PORT=${WEB_PORT:-80}
echo "==> Checking the tunnel to the home server..."
if curl -fsS -m 5 -o /dev/null "$API_URL/healthz"; then
    echo "    API reachable at $API_URL."
else
    echo "    Warning: cannot reach the API at $API_URL."
    echo "    The bot still runs and queues player writes; check: sudo wg show"
fi
echo "==> Checking the web frontend..."
if curl -fsS -m 5 -o /dev/null "http://127.0.0.1:${WEB_PORT}/healthz"; then
    echo "    nginx answering on :${WEB_PORT}."
else
    echo "    Warning: nginx not answering on :${WEB_PORT}; check: $COMPOSE logs diplomacy_web"
fi

echo "==> Done. Container status:"
$COMPOSE ps
