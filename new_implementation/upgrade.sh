#!/bin/bash
#
# upgrade.sh — update the whole stack in place: pull (unless the deploy
# workflow has already checked out a SHA), fill in any missing secrets,
# rebuild, restart (migrations run in the API container's entrypoint), make
# sure the nightly backup is scheduled, and check that everything answers.
#
# Postgres data (pg_data) and the bot's queue (bot_data) are named volumes and
# survive every rebuild. While the API restarts the bot queues player writes
# and replays them once it is back.
#
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

# By hand this runs on the main branch and pulls. The deploy workflow checks
# out the exact SHA the Test Suite passed on (a detached HEAD) before calling
# this script, and a pull would then fail with "not on a branch".
if git symbolic-ref -q HEAD >/dev/null; then
    echo "==> Pulling latest code..."
    git pull --ff-only
else
    echo "==> Detached at $(git rev-parse --short HEAD); not pulling."
fi

./ensure_env.sh

echo "==> Rebuilding images..."
docker compose build

echo "==> Recreating containers..."
docker compose up -d --remove-orphans

echo "==> Cleaning up old images..."
docker image prune -f

./backup.sh --install

WEB_PORT=$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- || true)
WEB_PORT=${WEB_PORT:-80}
echo "==> Waiting for the API..."
api_ok=0
for _ in $(seq 1 45); do
    if curl -fsS -m 3 -o /dev/null http://127.0.0.1:8000/healthz; then
        api_ok=1
        break
    fi
    sleep 2
done
if [ "$api_ok" = 1 ]; then
    echo "    API healthy."
else
    echo "    ERROR: API not healthy after 90s; check: docker compose logs diplomacy_api"
fi
echo "==> Checking the web frontend..."
web_ok=0
if curl -fsS -m 5 -o /dev/null "http://127.0.0.1:${WEB_PORT}/api/healthz"; then
    web_ok=1
    echo "    nginx answering on :${WEB_PORT} and reaching the API."
else
    echo "    ERROR: http://127.0.0.1:${WEB_PORT}/api/healthz failed; check: docker compose logs diplomacy_web"
fi

# HTTPS (DOMAIN set): check Caddy answers with a valid certificate. Only a
# warning -- the certificate depends on DNS and the UpCloud firewall, which a
# deploy can't fix, and nginx behind it was checked above. Asks this host
# (--resolve) so it doesn't depend on DNS or hairpin routing.
DOMAIN=$(grep -E '^DOMAIN=' .env 2>/dev/null | cut -d= -f2- || true)
if [ -n "$DOMAIN" ]; then
    echo "==> Checking https://${DOMAIN} ..."
    tls_ok=0
    for _ in $(seq 1 30); do
        if curl -fsS -m 5 -o /dev/null --resolve "${DOMAIN}:443:127.0.0.1" "https://${DOMAIN}/api/healthz"; then
            tls_ok=1
            break
        fi
        sleep 3
    done
    if [ "$tls_ok" = 1 ]; then
        echo "    https://${DOMAIN} is up with a valid certificate."
    else
        echo "    WARNING: https://${DOMAIN} not answering yet. Check that ${DOMAIN}'s A record"
        echo "    points here and TCP 80/443 are open, then: docker compose logs caddy"
    fi
fi

echo "==> Container status:"
docker compose ps
# A deploy that leaves the API or the site down must fail the workflow.
[ "$api_ok" = 1 ] && [ "$web_ok" = 1 ]
