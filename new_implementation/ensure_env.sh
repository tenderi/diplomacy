#!/bin/bash
#
# ensure_env.sh — make sure .env exists and every generated secret in it is
# set. Idempotent; install.sh and upgrade.sh (and so every deploy) run it.
#
# Never overwrites a value that is already set, with one exception:
# DIPLOMACY_BOT_SECRET is regenerated if it equals TELEGRAM_BOT_TOKEN (that
# happened once, when the secret was copied from the wrong line). The bot and
# the API both read the secret from this same file, so a fresh value needs no
# coordination.
#
# Prints the NAMES of what it generated, never the values.
#
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"
ENV_FILE=.env

if [ ! -f "$ENV_FILE" ]; then
    echo "==> Creating .env from .env.example"
    cp .env.example "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

get_var() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }
set_var() {  # set_var NAME VALUE -- replace the line or append it
    if grep -q "^$1=" "$ENV_FILE"; then
        awk -v k="$1" -v v="$2" 'BEGIN{FS=OFS="="} $1==k{$0=k"="v} {print}' "$ENV_FILE" > "$ENV_FILE.tmp"
        mv "$ENV_FILE.tmp" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
    else
        printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE"
    fi
}
random_hex() { od -An -tx1 -N32 /dev/urandom | tr -d ' \n'; }

# Keys from the retired two-host layout (VPS + home server over WireGuard).
# Compose no longer reads them; drop them so nobody edits them expecting an effect.
for key in DIPLOMACY_API_URL DIPLOMACY_API_UPSTREAM WG_IP; do
    if grep -q "^$key=" "$ENV_FILE"; then
        grep -v "^$key=" "$ENV_FILE" > "$ENV_FILE.tmp" || true
        mv "$ENV_FILE.tmp" "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        echo "==> Removed obsolete $key (the API is on this host now)."
    fi
done

token="$(get_var TELEGRAM_BOT_TOKEN)"
if [ -n "$token" ] && [ "$(get_var DIPLOMACY_BOT_SECRET)" = "$token" ]; then
    echo "==> DIPLOMACY_BOT_SECRET equals TELEGRAM_BOT_TOKEN; replacing it."
    set_var DIPLOMACY_BOT_SECRET ""
fi

for key in POSTGRES_PASSWORD DIPLOMACY_JWT_SECRET DIPLOMACY_ADMIN_TOKEN DIPLOMACY_BOT_SECRET; do
    if [ -z "$(get_var "$key")" ]; then
        set_var "$key" "$(random_hex)"
        echo "==> Generated $key."
    fi
done

if [ -z "$token" ]; then
    echo "==> NOTE: TELEGRAM_BOT_TOKEN is empty; the bot will not start until it is set."
fi
