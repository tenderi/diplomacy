#!/bin/bash
# Re-read all /diplomacy/* SecureStrings from SSM Parameter Store and
# rewrite /opt/diplomacy/.env. Run as root on the EC2 instance after
# rotating any secret in SSM, then `systemctl restart diplomacy-{api,bot}`.
#
# Idempotent. Missing parameters in SSM are written as empty values —
# the systemd units will log loudly when an empty required secret is
# observed.
set -euo pipefail

APP_DIR="/opt/diplomacy"
APP_USER="diplomacy"
SSM_PREFIX="/diplomacy"
AWS_REGION="${AWS_REGION:-$(curl -fsS http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null || echo eu-north-1)}"

fetch() {
  aws ssm get-parameter --name "$SSM_PREFIX/$1" --with-decryption --region "$AWS_REGION" \
    --query 'Parameter.Value' --output text 2>/dev/null || echo ""
}

DB_PASSWORD=$(fetch db_password)
TELEGRAM_BOT_TOKEN=$(fetch telegram_bot_token)
JWT_SECRET=$(fetch jwt_secret)
ADMIN_TOKEN=$(fetch admin_token)
BOT_SECRET=$(fetch bot_secret)

if [ -z "$DB_PASSWORD" ]; then
  echo "ERROR: $SSM_PREFIX/db_password is missing — refusing to rewrite .env" >&2
  exit 1
fi

install -o "$APP_USER" -g "$APP_USER" -m 0600 /dev/null "$APP_DIR/.env"
cat >"$APP_DIR/.env" <<EOF
SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://diplomacy:$DB_PASSWORD@localhost:5432/diplomacy_db
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
DIPLOMACY_JWT_SECRET=$JWT_SECRET
DIPLOMACY_ADMIN_TOKEN=$ADMIN_TOKEN
DIPLOMACY_BOT_SECRET=$BOT_SECRET
PYTHONPATH=$APP_DIR/new_implementation/src
EOF
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"
chmod 0600 "$APP_DIR/.env"

echo ".env refreshed from $SSM_PREFIX/* in $AWS_REGION."
echo "Now: sudo systemctl restart diplomacy-api diplomacy-bot"
