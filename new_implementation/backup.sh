#!/bin/bash
#
# backup.sh — dump the game database to a dated, gzipped file and keep the
# last BACKUP_KEEP_DAYS days of them.
#
#   ./backup.sh                 take a backup now
#   ./backup.sh --install-cron  (root) install the nightly cron job; idempotent,
#                               upgrade.sh runs it on every deploy
#
# Restore:  gunzip -c <file> | docker compose exec -T postgres psql -U diplomacy diplomacy_db
# (into an empty database; see docs/DEPLOYMENT.md).
#
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/diplomacy}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
CRON_FILE=/etc/cron.d/diplomacy-backup

if [ "${1:-}" = "--install-cron" ]; then
    if [ "$(id -u)" -ne 0 ] || [ ! -d /etc/cron.d ]; then
        echo "==> Not root or no /etc/cron.d; skipping the backup cron job."
        exit 0
    fi
    line="17 3 * * * root $HERE/backup.sh >> /var/log/diplomacy-backup.log 2>&1"
    if [ "$(cat "$CRON_FILE" 2>/dev/null)" != "$line" ]; then
        printf '%s\n' "$line" > "$CRON_FILE"
        chmod 644 "$CRON_FILE"
        echo "==> Installed nightly backup: $CRON_FILE"
    fi
    exit 0
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
out="$BACKUP_DIR/diplomacy-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
# Write to a temp name first so a failed dump never looks like a good backup.
docker compose exec -T postgres pg_dump -U diplomacy --no-owner diplomacy_db | gzip > "$out.part"
mv "$out.part" "$out"
find "$BACKUP_DIR" -name 'diplomacy-*.sql.gz' -mtime +"$BACKUP_KEEP_DAYS" -delete
echo "$(date -u +%FT%TZ) backup written: $out ($(du -h "$out" | cut -f1))"
