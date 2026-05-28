#!/bin/bash
# Bootstrap a fresh Ubuntu 24.04 EC2 instance for the Diplomacy server.
# Runs once at instance launch. Idempotent — safe to re-run by `cloud-init clean`
# then rebooting, or by manually invoking sections.
#
# Conventions:
#   - All state on disk lives under /opt/diplomacy (a git checkout).
#   - The `diplomacy` system user owns /opt/diplomacy and runs the services.
#   - Python 3.14 comes from the deadsnakes PPA.
#   - Postgres is whatever Ubuntu 24.04 ships (16.x). Migrations work on
#     14, 15, 16 identically — CI runs 14, we accept the drift.
#   - Secrets are read from SSM Parameter Store at /diplomacy/* — they
#     must be set BEFORE the instance comes up:
#       aws ssm put-parameter --name /diplomacy/telegram_bot_token \
#         --type SecureString --value '...' --region ${aws_region}
set -euo pipefail

exec > >(tee -a /var/log/diplomacy-bootstrap.log)
exec 2>&1
echo "=== Diplomacy bootstrap started $(date -Iseconds) ==="

AWS_REGION="${aws_region}"
SSM_PREFIX="${ssm_prefix}"
GITHUB_REPO="${github_repo}"
APP_DIR="/opt/diplomacy"
APP_USER="diplomacy"

# --- 1. System packages ---
echo "--- apt update + install base packages ---"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y software-properties-common ca-certificates curl gnupg unzip
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -qq
apt-get install -y \
  python3.14 python3.14-venv python3.14-dev \
  postgresql postgresql-contrib \
  build-essential libpq-dev libcairo2 libcairo2-dev pkg-config \
  nginx git jq

# AWS CLI v2 — the snap-installed v1 in the default AMI doesn't speak SSM
# Parameter Store the same way.
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --update
rm -rf /tmp/awscliv2.zip /tmp/aws

# --- 2. Application user + clone ---
echo "--- create diplomacy user and clone repo ---"
id "$APP_USER" >/dev/null 2>&1 || useradd -m -s /bin/bash "$APP_USER"
mkdir -p "$APP_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git clone "https://github.com/$GITHUB_REPO.git" "$APP_DIR"
fi
sudo -u "$APP_USER" git -C "$APP_DIR" fetch --tags
sudo -u "$APP_USER" git -C "$APP_DIR" checkout main

# --- 3. Python venv with 3.14 ---
echo "--- python venv + dependencies ---"
sudo -u "$APP_USER" python3.14 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/new_implementation/requirements.txt"

# --- 4. PostgreSQL: database, user, tuning for 1 GB RAM ---
echo "--- postgres setup ---"
systemctl enable --now postgresql

# Read the db password from SSM. If absent, generate a fresh one and store it.
if ! aws ssm get-parameter --name "$SSM_PREFIX/db_password" --with-decryption --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "  /diplomacy/db_password not in SSM — generating and storing"
  GEN_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
  aws ssm put-parameter --name "$SSM_PREFIX/db_password" --type SecureString \
    --value "$GEN_PASS" --region "$AWS_REGION" >/dev/null
fi
DB_PASSWORD=$(aws ssm get-parameter --name "$SSM_PREFIX/db_password" --with-decryption --region "$AWS_REGION" --query 'Parameter.Value' --output text)

# Idempotent create: skip on duplicate.
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='diplomacy'" | grep -q 1 \
  || sudo -u postgres psql -c "CREATE USER diplomacy WITH PASSWORD '$DB_PASSWORD';"
# Always sync password (lets rotation happen by updating SSM + rebooting).
sudo -u postgres psql -c "ALTER USER diplomacy WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='diplomacy_db'" | grep -q 1 \
  || sudo -u postgres createdb -O diplomacy diplomacy_db

# Tune for t3.micro (1 GB RAM). Append once; subsequent runs are no-ops.
PG_CONF=$(ls /etc/postgresql/*/main/postgresql.conf | head -1)
if ! grep -q '# diplomacy-tuning' "$PG_CONF"; then
  cat >>"$PG_CONF" <<'PGCONF'

# diplomacy-tuning: conservative settings for a 1 GB t3.micro hosting
# Postgres + FastAPI + Telegram bot on the same box.
shared_buffers = 128MB
effective_cache_size = 512MB
work_mem = 4MB
maintenance_work_mem = 64MB
max_connections = 25
PGCONF
  systemctl restart postgresql
fi

# --- 5. Swap (1 GB RAM is tight; without swap, map rendering OOMs) ---
if ! swapon --show | grep -q '/swapfile'; then
  echo "--- creating 2 GB swap file ---"
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >>/etc/fstab
fi

# --- 6. Environment file (read by systemd) ---
# Delegated to refresh-env.sh, which is the same helper used for rotation
# after bootstrap. Keeps both paths consistent.
echo "--- write /opt/diplomacy/.env via refresh-env.sh ---"
AWS_REGION="$AWS_REGION" bash "$APP_DIR/new_implementation/infra/scripts/refresh-env.sh"

# --- 7. Database migrations ---
echo "--- alembic upgrade head ---"
sudo -u "$APP_USER" bash -c "cd $APP_DIR/new_implementation && \
  set -a && source $APP_DIR/.env && set +a && \
  $APP_DIR/venv/bin/alembic upgrade head"

# --- 8. systemd units ---
echo "--- systemd units ---"
cat >/etc/systemd/system/diplomacy-api.service <<EOF
[Unit]
Description=Diplomacy FastAPI server
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR/new_implementation
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/uvicorn server._api_module:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/diplomacy-bot.service <<EOF
[Unit]
Description=Diplomacy Telegram bot
After=network.target postgresql.service diplomacy-api.service
Requires=postgresql.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR/new_implementation
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/python -m server.telegram_bot
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now diplomacy-api.service
systemctl enable --now diplomacy-bot.service

# --- 9. Nginx reverse proxy (port 80 → 127.0.0.1:8000) ---
echo "--- nginx ---"
cat >/etc/nginx/sites-available/diplomacy <<'NGINX'
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  server_name _;

  client_max_body_size 10M;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 60s;
    proxy_buffering off;
  }
}
NGINX
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/diplomacy /etc/nginx/sites-enabled/diplomacy
nginx -t
systemctl enable --now nginx
systemctl reload nginx

echo "=== Diplomacy bootstrap finished $(date -Iseconds) ==="
