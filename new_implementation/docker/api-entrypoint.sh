#!/bin/sh
# Apply migrations, then serve. Compose only starts this container once
# Postgres reports healthy, so a failed upgrade here is a real error, not a
# race -- let it exit and `restart: always` retry with the log visible.
set -eu

echo "==> alembic upgrade head"
alembic upgrade head

# 0.0.0.0 inside the container is fine: what the outside world can reach is
# decided by the host-side port binding in docker-compose.yml (loopback and
# the WireGuard address only).
echo "==> starting uvicorn on :8000"
exec uvicorn server._api_module:app --host 0.0.0.0 --port 8000 --proxy-headers
