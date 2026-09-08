#!/bin/bash
#
# upgrade.sh — update the GAME layer on the home server: pull, rebuild,
# restart (migrations run in the API container's entrypoint), then verify the
# API answers on loopback and on the tunnel address.
#
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

echo "==> Pulling latest code..."
git pull --ff-only

echo "==> Rebuilding images..."
docker compose build

echo "==> Recreating containers..."
docker compose up -d --remove-orphans

echo "==> Cleaning up old images..."
docker image prune -f

WG_IP=$(grep -E '^WG_IP=' .env 2>/dev/null | cut -d= -f2- || true)
WG_IP=${WG_IP:-10.8.0.2}
echo "==> Waiting for the API..."
for i in $(seq 1 30); do
    if curl -fsS -m 3 -o /dev/null http://127.0.0.1:8000/healthz; then
        echo "    API healthy on loopback."
        break
    fi
    sleep 2
    [ "$i" -eq 30 ] && echo "    WARNING: API not healthy after 60s; check: docker compose logs diplomacy_api"
done
if curl -fsS -m 3 -o /dev/null "http://${WG_IP}:8000/healthz"; then
    echo "    API reachable on the tunnel address ${WG_IP}."
else
    echo "    WARNING: API not answering on ${WG_IP}:8000 -- is wg0 up? (sudo wg show)"
fi

echo "==> Done. Container status:"
docker compose ps
