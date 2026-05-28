#!/bin/bash
# Deploy a specific commit to the running EC2 instance.
#
# This script lives in the repo so it can evolve with the code. It's
# invoked remotely via:
#   aws ssm send-command --document-name AWS-RunShellScript \
#     --parameters 'commands=["/opt/diplomacy/new_implementation/infra/scripts/deploy.sh <SHA>"]'
#
# The first thing the script does is `git fetch && git checkout`, so the
# version of this script that actually runs the deploy is the one from
# the target commit — not the one from whatever was checked out before.
# This is intentional: it lets us improve the deploy script atomically
# with the code it deploys. The downside is a buggy commit can break its
# own deploy and require manual intervention via `aws ssm start-session`.
set -euo pipefail

TARGET_REF="${1:-main}"
APP_DIR="/opt/diplomacy"
APP_USER="diplomacy"

echo "=== diplomacy deploy: $TARGET_REF @ $(date -Iseconds) ==="

# Fetch + check out. Reset hard so any drift on the instance is overwritten.
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --tags origin
sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard "$TARGET_REF"
DEPLOYED_SHA=$(sudo -u "$APP_USER" git -C "$APP_DIR" rev-parse HEAD)
echo "  HEAD now at $DEPLOYED_SHA"

# Install Python deps. pip is fast when the lockfile is unchanged.
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/new_implementation/requirements.txt"

# Run migrations. EnvironmentFile is the source of truth for DB URL.
sudo -u "$APP_USER" bash -c "cd $APP_DIR/new_implementation && \
  set -a && source $APP_DIR/.env && set +a && \
  $APP_DIR/venv/bin/alembic upgrade head"

# Restart services. Order matters: API before bot, since bot talks to API.
systemctl restart diplomacy-api.service
systemctl restart diplomacy-bot.service

# Give services a moment, then sanity-check they're up.
sleep 3
systemctl is-active --quiet diplomacy-api.service || { echo "FAIL: diplomacy-api is not running"; journalctl -u diplomacy-api -n 30 --no-pager; exit 1; }
systemctl is-active --quiet diplomacy-bot.service || { echo "FAIL: diplomacy-bot is not running"; journalctl -u diplomacy-bot -n 30 --no-pager; exit 1; }

# Local API smoke test through the loopback (Nginx not involved).
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "  /health OK"
else
  echo "WARN: /health did not respond. Check journalctl -u diplomacy-api."
fi

echo "=== deploy complete: $DEPLOYED_SHA ==="
