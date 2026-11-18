#!/bin/bash
#
# agent_shell.sh -- the ONLY command the lead agent's SSH key can run. Its
# authorized_keys line is
#   restrict,command="/usr/local/lib/diplomacy/agent_shell.sh" ssh-ed25519 ... diplomacy-lead-agent
# (harden_host.sh writes it). The agent reads untrusted text (issues, player
# feedback, logs), so its access to the host is read-only diagnostics of this
# stack and nothing else: no shell, no writes, no other project, no secrets.
# It changes production only through the repository and the Deploy workflow.
#
#   ssh <host> status                     deployed commit, containers, disk, memory
#   ssh <host> health                     the API directly and through nginx
#   ssh <host> logs <service> [since]     current containers' logs (since: 30m, 6h, 2d; default 1h)
#   ssh <host> journal <service> [since]  logs of replaced containers too (default 1d)
#   ssh <host> sql [-tA] < query.sql      one read-only query batch as the diplomacy_agent role
#   ssh <host> backup-status              the tail of the nightly backup log
#   ssh <host> toolkit                    which commit the host toolkit came from
#
# <service>: diplomacy_api diplomacy_bot diplomacy_web diplomacy_docs postgres caddy.
# The diplomacy_agent role (agent_db_role.sql) can read every table except the
# columns holding emails, password hashes, reset tokens and link codes, private
# message text, and bot notification payloads.
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[ -f "$HERE/toolkit.env" ] && . "$HERE/toolkit.env"
cd "${DIPLOMACY_DIR:?toolkit.env must set DIPLOMACY_DIR}"

SERVICES=(diplomacy_api diplomacy_bot diplomacy_web diplomacy_docs postgres caddy)
MAX_SQL_BYTES=65536
MAX_OUTPUT_BYTES=2000000

usage() {
    sed -n '/^#   ssh <host> status/,/^# columns holding/p' "$0" | sed 's/^# \{0,1\}//'
}
deny() {
    echo "agent_shell: $*" >&2
    exit 2
}
service_ok() {
    local s
    for s in "${SERVICES[@]}"; do [ "$s" = "$1" ] && return 0; done
    return 1
}
since_ok() { [[ "$1" =~ ^[0-9]{1,4}[smhd]$ ]]; }

# Split the request into words. `read -a` neither globs nor expands, so
# `logs x; rm -rf /` is just four odd words that fail the checks below.
read -r -a argv <<<"${SSH_ORIGINAL_COMMAND:-help}" || true
cmd="${argv[0]:-help}"
[ "${#argv[@]}" -le 3 ] || deny "too many arguments"

case "$cmd" in
    help | -h | --help)
        usage
        ;;
    status)
        [ "${#argv[@]}" -eq 1 ] || deny "status takes no arguments"
        git log -1 --format='deployed: %H %s (%cs)'
        docker compose ps
        uptime
        df -h /
        free -m
        ;;
    health)
        [ "${#argv[@]}" -eq 1 ] || deny "health takes no arguments"
        web_port="$(grep -E '^WEB_PORT=' .env 2>/dev/null | cut -d= -f2- || true)"
        echo "api:   $(curl -sS -m 5 http://127.0.0.1:8000/health 2>&1 || true)"
        echo "nginx: $(curl -sS -m 5 "http://127.0.0.1:${web_port:-80}/api/healthz" 2>&1 || true)"
        ;;
    logs | journal)
        svc="${argv[1]:-}"
        service_ok "$svc" || deny "unknown service '$svc' (one of: ${SERVICES[*]})"
        if [ "$cmd" = logs ]; then since="${argv[2]:-1h}"; else since="${argv[2]:-1d}"; fi
        since_ok "$since" || deny "since must look like 30m, 6h or 2d"
        if [ "$cmd" = logs ]; then
            docker compose logs --no-color --since "$since" "$svc" 2>&1 | tail -n 3000
        else
            journalctl --no-pager -o short-iso --since "-$since" \
                CONTAINER_NAME="diplomacy-${svc}-1" | tail -n 3000
        fi
        ;;
    sql)
        fmt=()
        case "${argv[1]:-}" in
            "") ;;
            -tA) fmt=(-t -A -F $'\t') ;;
            *) deny "sql takes no option but -tA" ;;
        esac
        [ "${#argv[@]}" -le 2 ] || deny "sql reads the query on stdin"
        query="$(head -c "$((MAX_SQL_BYTES + 1))")"
        [ "${#query}" -le "$MAX_SQL_BYTES" ] || deny "query longer than $MAX_SQL_BYTES bytes"
        [ -n "${query//[[:space:]]/}" ] || deny "empty query"
        # No psql meta-commands at all: `\!` would run a shell in the container.
        # (With -c psql sends the string to the server as SQL anyway; this is the
        # second lock.)
        case "$query" in *\\*) deny "backslashes are not allowed (no psql meta-commands)" ;; esac
        docker compose exec -T --user postgres postgres \
            psql -X -q -v ON_ERROR_STOP=1 -P pager=off "${fmt[@]}" \
            -U diplomacy_agent -d diplomacy_db -c "$query" 2>&1 | head -c "$MAX_OUTPUT_BYTES"
        ;;
    backup-status)
        [ "${#argv[@]}" -eq 1 ] || deny "backup-status takes no arguments"
        tail -n 20 /var/log/diplomacy-backup.log 2>/dev/null || echo "no backup log yet"
        ;;
    toolkit)
        [ "${#argv[@]}" -eq 1 ] || deny "toolkit takes no arguments"
        echo "host toolkit installed from: $(cat "$HERE/installed-from" 2>/dev/null || echo unknown)"
        echo "deployed checkout:           $(git rev-parse HEAD)"
        ;;
    *)
        usage >&2
        deny "unknown command '$cmd'"
        ;;
esac
