# Deployment: the whole stack on one VPS

Diplomacy runs on **one host**, the UpCloud VPS (`87.58.144.64`, Debian/Ubuntu,
1 vCPU / 2 GB + 2 GB swap), from a single `docker-compose.yml`. The same VPS
also runs p2p's bot, which this stack does not touch.

```
  Players                         VPS (87.58.144.64)
  ─────────                       ┌────────────────────────────────────────────────┐
  Telegram app ── Telegram ─────► │ diplomacy_bot   long-polls Telegram;           │
                                  │                 durable queue (SQLite, /data)  │
                                  │        │ http://diplomacy_api:8000             │
                                  │        ▼                                       │
  Browser ──── http://…:80 ─────► │ diplomacy_web   nginx: SPA + /api/ ──► API     │
                                  │ diplomacy_api   FastAPI + engine + renderer    │
                                  │                 127.0.0.1:8000, DAIDE :8432    │
                                  │ postgres        not published; pg_data volume  │
                                  └────────────────────────────────────────────────┘
```

Only nginx is reachable from the internet. The API is published on loopback
only (for `upgrade.sh` and debugging); the bot and nginx reach it by its
compose service name. Postgres is not published at all.

Until `v2.7.85` the stack was split across the VPS (bot + web) and a home
server (API + Postgres) joined by p2p's WireGuard tunnel. That layout was
retired for simplicity: one host, one `.env`, every merge deploys everything.
`done_fixes.md` Track V has the history.

## Secrets

All live in `new_implementation/.env` on the VPS (mode 600).

| Key | Where it comes from |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The `TELEGRAM_BOT_TOKEN` repository secret; the deploy workflow writes it on every run. |
| `POSTGRES_PASSWORD`, `DIPLOMACY_JWT_SECRET`, `DIPLOMACY_ADMIN_TOKEN`, `DIPLOMACY_BOT_SECRET` | Generated **on the host** by `ensure_env.sh` the first time they are blank. They never leave the host; GitHub does not have them. |

`DIPLOMACY_BOT_SECRET` is what the bot sends as `X-Bot-Secret` and the API
checks. Both containers read it from the same `.env`, so it cannot drift.
`ensure_env.sh` also regenerates it if it ever equals the Telegram token, and
removes the old tunnel keys (`DIPLOMACY_API_URL`, `DIPLOMACY_API_UPSTREAM`,
`WG_IP`) left from the two-host layout.

## What "no message is ever lost" means

The API restarts on every deploy, and it can crash. That costs players
nothing but latency:

**Player → server (orders, messages).** The bot writes every such command to a
durable SQLite queue *before* the first delivery attempt
(`src/server/telegram_bot/outbox.py`, in the `bot_data` volume). If the API is
unreachable the player is told, immediately, that it is queued and when it
was sent; a background loop retries in order and DMs the result. Each queued
request carries:

- `client_timestamp` — when the player composed it. A message is stored with
  that time, not the delivery time, and the recipient's notification says
  "(sent 14:02 UTC)" when it was delayed. Orders composed *before the current
  phase began* are **refused** (HTTP 409 against `games.phase_started_at`)
  and the player is told exactly which orders did not make it, rather than
  having last turn's orders silently applied to this turn's board.
- `Idempotency-Key` — a UUID the server stores the first response under. A
  retry of a request whose response was lost is answered from that store, so
  nothing is ever applied twice.

**Server → player (turn processed, reminders, joins, messages).** The API
never talks to Telegram. It commits each notification to the `bot_outbox`
table and the bot *pulls* them (`GET /bot/outbox`, `POST /bot/outbox/ack`)
every few seconds. A notification is only acked after Telegram accepted it.
Delivered late, it is prefixed with the time it was created.

`/queue` in Telegram shows what is waiting and whether the server is
reachable.

## First-time setup (a fresh host)

```bash
git clone https://github.com/tenderi/diplomacy.git ~/diplomacy
cd ~/diplomacy/new_implementation
./install.sh        # Docker, a 2 GB swap file if none, .env + secrets, nightly backup
```

Put the bot token in `.env` (`TELEGRAM_BOT_TOKEN=` from @BotFather), or let
the deploy workflow write it. Optionally set `DIPLOMACY_PASSWORD_RESET_BASE_URL`
and `DIPLOMACY_CORS_ORIGINS` to the site's public URL (e.g.
`http://87.58.144.64`). Then:

```bash
./upgrade.sh        # build, start (migrations run in the API entrypoint), verify
```

### Ports and the UpCloud firewall

The site needs **inbound TCP 80** (and 443 once TLS is set up). UpCloud applies
a network-level firewall in front of the host, separate from `ufw`; on a trial
account it cannot be edited. Check that 80/443 are permitted before assuming
nginx is broken -- a `tcpdump -ni any tcp port 80` that shows nothing is the
signature. Nothing else needs to be open: the bot dials out to Telegram.

### TLS

Nothing here terminates TLS. The login form must not stay on plain HTTP once
anyone but you uses it. The least-effort path is a hostname pointed at the
VPS and Caddy in front of `diplomacy_web` (Caddy fetches certificates on its
own); set `WEB_BIND=127.0.0.1` in `.env` so nginx only answers to Caddy, and
set `DIPLOMACY_PASSWORD_RESET_BASE_URL` to the `https://` URL.

## Deploy-on-merge (GitHub Actions)

`.github/workflows/deploy.yml` deploys automatically after the Test Suite is
green on `main` (or on demand: *Run workflow*, optionally with a SHA or tag).
It SSHes in as `root`, fetches and checks out the exact SHA that passed
(detached), writes `TELEGRAM_BOT_TOKEN` into `.env` (only that line), and runs
`./upgrade.sh`, which:

1. runs `ensure_env.sh` (fills any missing secret);
2. `docker compose build` -- a failed build leaves the running stack alone;
3. `docker compose up -d --remove-orphans`;
4. installs the nightly backup cron job if missing;
5. waits for `http://127.0.0.1:8000/healthz` and checks
   `http://127.0.0.1/api/healthz` (nginx → API), and **fails the workflow** if
   either does not answer.

The token travels on stdin, never in a command line.

One-time setup (done on 2026-09-23), from a machine that can SSH into the VPS:

```bash
# 1. A dedicated deploy key for GitHub (no passphrase), installed for root.
ssh-keygen -t ed25519 -f ~/.ssh/diplomacy_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/diplomacy_deploy.pub | ssh root@87.58.144.64 'cat >> ~/.ssh/authorized_keys'

# 2. Secrets and the gate. TELEGRAM_BOT_TOKEN is already set.
gh secret set VPS_SSH_KEY  -R tenderi/diplomacy < ~/.ssh/diplomacy_deploy
gh secret set VPS_HOST_KEY -R tenderi/diplomacy --body "$(ssh-keyscan -t ed25519 87.58.144.64 2>/dev/null)"
gh variable set DEPLOY_CONTROL_ENABLED --body true -R tenderi/diplomacy
```

The gate's name predates the single-host layout. Optional repository
variables override the defaults: `VPS_HOST` (`87.58.144.64`), `VPS_USER`
(`root` — the VPS has no other login user), `VPS_REPO_DIR`
(`~/diplomacy/new_implementation`). Until `DEPLOY_CONTROL_ENABLED` is `true`
the workflow is skipped, not red. The `DIPLOMACY_BOT_SECRET` repository secret
from the two-host layout is no longer read and can be deleted.

## Running by hand

On the VPS, in `/root/diplomacy/new_implementation`:

```bash
./upgrade.sh                           # the same thing the workflow runs
docker compose ps
docker compose logs -f diplomacy_bot   # or diplomacy_api, diplomacy_web, postgres
docker compose restart diplomacy_bot
```

The deploy leaves the checkout on a detached SHA; `upgrade.sh` by hand there
rebuilds that SHA without pulling. `git checkout main` first to pull.

## Backups

`backup.sh` writes `pg_dump | gzip` to `/var/backups/diplomacy/` and keeps 14
days (`BACKUP_DIR`, `BACKUP_KEEP_DAYS` override), then **copies the folder to
Proton Drive** with rclone and deletes remote copies older than 60 days
(`BACKUP_REMOTE_KEEP_DAYS`). `/etc/cron.d/diplomacy-backup` runs it nightly at
03:17 UTC, logging to `/var/log/diplomacy-backup.log`. `upgrade.sh` runs
`./backup.sh --install` on every deploy, which (re)installs that job and
installs rclone from rclone.org (checksum-verified) if it is missing or older
than 1.64 -- Ubuntu's own package is too old to have the Proton Drive backend.

The remote is `BACKUP_RCLONE_REMOTE` (in `.env`; default
`proton:diplomacy-backups`). Until a remote with that name exists, the upload
is skipped with a note in the log and backups stay on the VPS disk only. Once
it exists, a failed upload makes the run exit non-zero with an `ERROR:` line
(the local dump is kept either way).

### One-time Proton Drive setup

rclone logs in as a whole Proton account, and Proton has no scoped tokens, so
whoever controls the VPS can read and delete that account's entire drive.
A separate, backups-only Proton account (the free tier is enough) would limit
a compromise of the public host to the Diplomacy dumps; production uses the
maintainer's own account, a choice made knowingly (keep `rclone.conf` at mode
600, and if the stack ever leaves this host, `rclone config delete proton`
and end the session in Proton's account settings). Then, over SSH on the VPS:

```bash
rclone config
#   n                      (new remote)
#   name>     proton       (backup.sh's default remote name)
#   Storage>  protondrive
#   username> the backups account's email
#   password> y, then its password (stored obscured in /root/.config/rclone/rclone.conf)
#   2fa>      leave blank -- rclone only stores this, and a code is stale by first use
#   mailbox_password> blank unless the account uses Proton's two-password mode
#   everything else: the default; then y to keep the remote, q to quit
chmod 600 /root/.config/rclone/rclone.conf
# The first real login happens here, so give a *fresh* 2FA code now (omit the
# flag if 2FA is off). After it succeeds rclone keeps a refreshing session and
# never needs a code again. A stale code fails with
# "422 POST .../auth/v4/2fa: Incorrect login credentials".
rclone mkdir proton:diplomacy-backups --protondrive-2fa=123456
cd /root/diplomacy/new_implementation && ./backup.sh   # expect "off-host copy done"
```

rclone's Proton Drive backend is **unofficial** (Proton publishes no Drive
API), so a change on Proton's side can break uploads until rclone catches
up. `./backup.sh --install` only installs rclone when it is missing or too
old; to take a newer release, `dpkg -r rclone && ./backup.sh --install`. If
Proton ends the saved session, `rclone config reconnect proton:` asks for the
password and 2FA code again. Check the tail of
`/var/log/diplomacy-backup.log` now and then; every successful night ends with
`off-host copy done`.

Restore into an empty database:

```bash
docker compose stop diplomacy_api diplomacy_bot
docker compose exec -T postgres dropdb -U diplomacy diplomacy_db
docker compose exec -T postgres createdb -U diplomacy diplomacy_db
gunzip -c /var/backups/diplomacy/diplomacy-<stamp>.sql.gz \
  | docker compose exec -T postgres psql -q -U diplomacy diplomacy_db
docker compose up -d
```

## Monitoring

- `/queue` in Telegram: server reachability, this player's queued writes, and
  the last few delivered/refused ones.
- `docker compose ps` -- all four services report `healthy` (Postgres, the
  API and nginx have healthchecks; the bot's watches a heartbeat file both of
  its background loops touch, so a wedged bot is restarted by Docker).
- `docker compose logs diplomacy_bot` logs `API unreachable; player writes are
  being queued locally` once when the API drops and `API reachable again; N
  queued write(s) waiting` once when it returns, not on every poll.
- Pending notifications:
  `curl -H "X-Bot-Secret: $(grep ^DIPLOMACY_BOT_SECRET= .env | cut -d= -f2-)" http://127.0.0.1:8000/bot/outbox/stats`.

## Troubleshooting

- **Bot replies "The game server is unreachable right now".** The API is
  down or restarting. Writes are queued; reads fail until it returns.
  `docker compose ps`, `docker compose logs diplomacy_api`.
- **The site returns 502 on `/api/…`.** Same cause, seen from nginx. nginx
  resolves the API per request, so a recreated API container is picked up
  within 10 seconds without restarting nginx.
- **401 "requires the 'X-Bot-Secret' header" in the bot log.** The bot and
  API disagree on `DIPLOMACY_BOT_SECRET`, which should be impossible with one
  `.env`: a container is running from an older `.env`. `docker compose up -d`
  recreates it.
- **A queued order was refused: "composed at ... but the turn was processed
  at ...".** Working as designed: the deadline passed while the API was down.
  The player is told; the orders were not applied to the new phase.
- **A notification arrived twice.** The bot sent it, then could not reach the
  API to ack it, so the row came back on the next poll. At-least-once is the
  deliberate side of this trade.
- **`/queue` shows attempts climbing but the server is reachable.** The entry
  at the head of the queue is being refused with a *transient* status
  (502/503/504) -- the API is up but unhealthy, most likely Postgres.
  `docker compose logs diplomacy_api postgres`.
- **The deploy failed at "API not healthy after 90s".** Usually a migration
  error: `docker compose logs diplomacy_api` shows the Alembic traceback. The
  old containers were already replaced, so fix forward (or deploy an older
  SHA via *Run workflow*).
