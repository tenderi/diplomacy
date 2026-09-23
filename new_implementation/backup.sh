#!/bin/bash
#
# backup.sh — dump the game database to a dated, gzipped file, keep the last
# BACKUP_KEEP_DAYS days of them locally, and copy them off the host with
# rclone (Proton Drive in production).
#
#   ./backup.sh            take a backup now (the nightly cron job runs this)
#   ./backup.sh --install  (root) install rclone >= 1.64 and the nightly cron
#                          job; idempotent, upgrade.sh runs it on every deploy
#
# Off-host copy: BACKUP_RCLONE_REMOTE (default proton:diplomacy-backups; may be
# set in .env). Until that remote exists in rclone's config the upload is
# skipped with a note, so the local backup still happens. Once it exists, a
# failed upload makes the run exit non-zero with an ERROR line in the log.
# Remote copies older than BACKUP_REMOTE_KEEP_DAYS (60) are deleted.
# One-time remote setup is interactive (needs the Proton password + 2FA):
#   rclone config   (new remote "proton", type protondrive; docs/DEPLOYMENT.md)
#
# Restore:  gunzip -c <file> | docker compose exec -T postgres psql -U diplomacy diplomacy_db
# (into an empty database; see docs/DEPLOYMENT.md).
#
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

env_var() { [ -f .env ] && grep -E "^$1=" .env | tail -n1 | cut -d= -f2- || true; }
BACKUP_DIR="${BACKUP_DIR:-/var/backups/diplomacy}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
BACKUP_REMOTE_KEEP_DAYS="${BACKUP_REMOTE_KEEP_DAYS:-60}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-$(env_var BACKUP_RCLONE_REMOTE)}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-proton:diplomacy-backups}"
CRON_FILE=/etc/cron.d/diplomacy-backup
RCLONE_MIN_MINOR=64   # the protondrive backend arrived in rclone 1.64

rclone_ok() {
    command -v rclone >/dev/null 2>&1 || return 1
    local minor
    minor="$(rclone version 2>/dev/null | sed -nE '1s/^rclone v1\.([0-9]+).*/\1/p')"
    [ -n "$minor" ] && [ "$minor" -ge "$RCLONE_MIN_MINOR" ]
}

install_rclone() {
    # Distro packages lag (Ubuntu 26.04 ships 1.60), so take the official .deb
    # and check it against the release's SHA256SUMS before installing.
    local arch version tmp
    arch="$(dpkg --print-architecture)"
    version="$(curl -fsS https://downloads.rclone.org/version.txt | sed 's/^rclone //')"
    tmp="$(mktemp -d)"
    curl -fsS -o "$tmp/rclone-$version-linux-$arch.deb" \
        "https://downloads.rclone.org/$version/rclone-$version-linux-$arch.deb"
    curl -fsS "https://downloads.rclone.org/$version/SHA256SUMS" \
        | grep " rclone-$version-linux-$arch.deb\$" > "$tmp/SHA256SUMS"
    (cd "$tmp" && sha256sum -c --quiet SHA256SUMS)
    dpkg -i "$tmp/rclone-$version-linux-$arch.deb" >/dev/null
    rm -rf "$tmp"
    echo "==> Installed $(rclone version | head -n1)"
}

if [ "${1:-}" = "--install" ]; then
    if [ "$(id -u)" -ne 0 ] || [ ! -d /etc/cron.d ]; then
        echo "==> Not root or no /etc/cron.d; skipping the backup cron job and rclone."
        exit 0
    fi
    rclone_ok || install_rclone
    line="17 3 * * * root $HERE/backup.sh >> /var/log/diplomacy-backup.log 2>&1"
    if [ "$(cat "$CRON_FILE" 2>/dev/null)" != "$line" ]; then
        printf '%s\n' "$line" > "$CRON_FILE"
        chmod 644 "$CRON_FILE"
        echo "==> Installed nightly backup: $CRON_FILE"
    fi
    exit 0
fi

stamp() { date -u +%FT%TZ; }

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
out="$BACKUP_DIR/diplomacy-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
# Write to a temp name first so a failed dump never looks like a good backup.
docker compose exec -T postgres pg_dump -U diplomacy --no-owner diplomacy_db | gzip > "$out.part"
mv "$out.part" "$out"
find "$BACKUP_DIR" -name 'diplomacy-*.sql.gz' -mtime +"$BACKUP_KEEP_DAYS" -delete
echo "$(stamp) backup written: $out ($(du -h "$out" | cut -f1))"

remote_name="${BACKUP_RCLONE_REMOTE%%:*}:"
if ! rclone_ok; then
    echo "$(stamp) off-host copy skipped: rclone >= 1.$RCLONE_MIN_MINOR not installed (./backup.sh --install)"
    exit 0
fi
if ! rclone listremotes | grep -qx "$remote_name"; then
    echo "$(stamp) off-host copy skipped: rclone remote '$remote_name' not configured (docs/DEPLOYMENT.md, Backups)"
    exit 0
fi
# copy, not sync: a local file pruned after 14 days must not vanish remotely.
if ! rclone copy "$BACKUP_DIR" "$BACKUP_RCLONE_REMOTE" --include 'diplomacy-*.sql.gz'; then
    echo "$(stamp) ERROR: off-host copy to $BACKUP_RCLONE_REMOTE failed; the local backup is kept" >&2
    exit 1
fi
rclone delete "$BACKUP_RCLONE_REMOTE" --include 'diplomacy-*.sql.gz' --min-age "${BACKUP_REMOTE_KEEP_DAYS}d" \
    || echo "$(stamp) WARNING: pruning old copies in $BACKUP_RCLONE_REMOTE failed" >&2
echo "$(stamp) off-host copy done: $BACKUP_RCLONE_REMOTE"
