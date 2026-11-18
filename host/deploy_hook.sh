#!/bin/bash
#
# deploy_hook.sh -- the ONLY command the GitHub Actions deploy key can run. Its
# authorized_keys line is
#   restrict,command="/usr/local/lib/diplomacy/deploy_hook.sh" ssh-ed25519 ... github-actions-deploy
# (harden_host.sh writes it), so whatever the client asks for arrives here as
# SSH_ORIGINAL_COMMAND and nothing else runs.
#
#   ssh <host> "deploy <full 40-hex commit sha>"   with   TELEGRAM_BOT_TOKEN=<token>   on stdin
#
# This copy is the installed one, root-owned, in /usr/local/lib/diplomacy (the
# "host toolkit"; install.sh --toolkit puts it there). A deploy never runs code
# from the checkout as root: the checkout only supplies the compose file and
# images, and the two files that decide what the containers may touch on the
# host -- docker-compose.yml and docker/Caddyfile (imported into the Caddy that
# also serves the host's other sites) -- must match the copies the maintainer
# reviewed when they installed the toolkit (reviewed.sha256). So a commit that
# reaches main, from whoever, can change what runs inside the containers, but
# not the host.
#
# Refuses: any other command; a commit that is not on origin/main (GitHub serves
# fork and pull-request commits by SHA too); a token that is not a Telegram bot
# token; a changed docker-compose.yml or docker/Caddyfile.
#
set -euo pipefail
umask 077

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
[ -f "$HERE/toolkit.env" ] && . "$HERE/toolkit.env"
REVIEWED="$HERE/reviewed.sha256"

fail() {
    echo "deploy_hook: $*" >&2
    exit 1
}

[ -n "${DIPLOMACY_DIR:-}" ] || fail "DIPLOMACY_DIR is not set ($HERE/toolkit.env); run install.sh --toolkit"
[ -s "$REVIEWED" ] || fail "no $REVIEWED; run install.sh --toolkit"

# --- the request ---------------------------------------------------------------------
read -r verb sha extra <<<"${SSH_ORIGINAL_COMMAND:-}" || true
if [ "${verb:-}" != "deploy" ] || [ -n "${extra:-}" ] || ! [[ "${sha:-}" =~ ^[0-9a-f]{40}$ ]]; then
    fail "the only command is: deploy <full 40-hex commit sha>"
fi

line=""
IFS= read -r line || true
case "$line" in
    TELEGRAM_BOT_TOKEN=*) token="${line#TELEGRAM_BOT_TOKEN=}" ;;
    *) fail "expected TELEGRAM_BOT_TOKEN=<token> on stdin" ;;
esac
# The shape of a bot token, which also keeps it safe to hand to awk below.
[[ "$token" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail "the TELEGRAM_BOT_TOKEN on stdin is not a Telegram bot token"

cd "$DIPLOMACY_DIR"

# --- only commits on main ----------------------------------------------------------------
echo "==> Fetching $sha"
# The clone may be single-branch on an old branch, so fetch main into its
# remote-tracking ref explicitly, and the target itself.
git fetch --quiet origin "+refs/heads/main:refs/remotes/origin/main" "$sha" \
    || fail "could not fetch $sha from origin"
git merge-base --is-ancestor "$sha" refs/remotes/origin/main \
    || fail "$sha is not on origin/main; only main's commits (and so its tags) are deployed"

# --- files that reach the host must be the reviewed ones ---------------------------------
changed=()
while read -r want path; do
    [ -n "$path" ] || continue
    # A regular file at exactly that path: a symlink or a path through one
    # (docker -> /root) would make the reviewed hash mean nothing.
    mode="$(git ls-tree "$sha" -- "$path" | awk '{print $1}')"
    if [ "$mode" != "100644" ] && [ "$mode" != "100755" ]; then
        changed+=("$path (not a regular file at $sha)")
        continue
    fi
    got="$(git cat-file blob "$sha:$path" | sha256sum | cut -d' ' -f1)"
    [ "$got" = "$want" ] || changed+=("$path")
done <"$REVIEWED"
if [ "${#changed[@]}" -gt 0 ]; then
    {
        echo "::error::Not deploying $sha: it changes ${changed[*]}, which decide what the"
        echo "containers may touch on the host. The maintainer reviews the change and"
        echo "approves it on the host:"
        echo "  cd $DIPLOMACY_DIR && git fetch origin && git checkout --detach $sha"
        echo "  git diff $(cat "$HERE/installed-from" 2>/dev/null || echo '<installed>') $sha -- docker-compose.yml docker/Caddyfile host/ '*.sh'"
        echo "  sudo ./install.sh --toolkit"
        echo "then re-runs the Deploy workflow. Until then production stays on the deployed commit."
    } >&2
    exit 3
fi

# --- check out, write the token, run the installed upgrade ------------------------------
echo "==> Checking out $sha"
git checkout --quiet --detach "$sha"

[ -f .env ] || cp .env.example .env
chmod 600 .env
if grep -q '^TELEGRAM_BOT_TOKEN=' .env; then
    awk -v v="$token" 'BEGIN{FS=OFS="="} $1=="TELEGRAM_BOT_TOKEN"{$0="TELEGRAM_BOT_TOKEN="v} {print}' .env >.env.tmp
    cat .env.tmp >.env # keeps .env's owner and mode
    rm -f .env.tmp
else
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$token" >>.env
fi

# The checkout's copies of the toolkit only take effect when the maintainer
# installs them; say so when they differ, so it is not forgotten.
for f in upgrade.sh ensure_env.sh backup.sh host/deploy_hook.sh host/agent_shell.sh host/agent_db_role.sql; do
    if [ -f "$f" ] && ! cmp -s "$f" "$HERE/$(basename "$f")"; then
        echo "::warning::$f differs from the installed host toolkit; it takes effect once the maintainer reviews it and runs: sudo ./install.sh --toolkit"
    fi
done

DIPLOMACY_IMAGE_TAG="$sha" exec "$HERE/upgrade.sh"
