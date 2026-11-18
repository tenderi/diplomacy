# Deployment: the whole stack on one VPS

Diplomacy runs on **one host**, a Debian/Ubuntu VPS (1 vCPU / 2 GB RAM + 2 GB swap
is enough), from a single `docker-compose.yml`. This guide is everything needed to
run your own instance; [Running your own instance](#running-your-own-instance) lists
what to change from the defaults. The stack touches nothing else on the host, so it
can share a VPS with other services.

```
  Players                         VPS
  ─────────                       ┌────────────────────────────────────────────────┐
  Telegram app ── Telegram ─────► │ diplomacy_bot   long-polls Telegram;           │
                                  │                 durable queue (SQLite, /data)  │
                                  │        │ http://diplomacy_api:8000             │
                                  │        ▼                                       │
  Browser ─── https://DOMAIN ───► │ caddy           HTTPS, Let's Encrypt           │
                                  │   ├─► diplomacy_web  nginx: SPA + /api/ ─► API │
                                  │   └─► diplomacy_docs this site (DOCS_DOMAIN)   │
                                  │ diplomacy_api   FastAPI + engine + renderer    │
                                  │                 127.0.0.1:8000, DAIDE :8432    │
                                  │ postgres        not published; pg_data volume  │
                                  └────────────────────────────────────────────────┘
```

With a `DOMAIN`, only Caddy (ports 80/443) is reachable from the internet:
`ensure_env.sh` then sets `WEB_BIND=127.0.0.1` and `WEB_PORT=8080`, so nginx is on
loopback. The API is published on loopback only (for `upgrade.sh` and debugging); the
bot and nginx reach the API by its compose service name. DAIDE is published on
`${DAIDE_BIND:-127.0.0.1}:8432` -- loopback unless you set `DAIDE_BIND` in `.env`
(`ensure_env.sh` never does). Postgres is not published at all.
Without a `DOMAIN`, Caddy does not run and nginx serves plain HTTP on
`${WEB_BIND:-0.0.0.0}`, i.e. publicly unless you set `WEB_BIND`.

## Secrets

All live in `.env` in the checkout on the VPS (mode 600).

| Key | Where it comes from |
|---|---|
| `TELEGRAM_BOT_TOKEN` | The `TELEGRAM_BOT_TOKEN` repository secret; the deploy workflow writes it on every run. |
| `POSTGRES_PASSWORD`, `DIPLOMACY_JWT_SECRET`, `DIPLOMACY_ADMIN_TOKEN`, `DIPLOMACY_BOT_SECRET` | Generated **on the host** by `ensure_env.sh` the first time they are blank. They never leave the host; GitHub does not have them. |

`DIPLOMACY_BOT_SECRET` is what the bot sends as `X-Bot-Secret` and the API
checks. Both containers read it from the same `.env`, so it cannot drift.
`ensure_env.sh` also regenerates it if it ever equals the Telegram token.

`DIPLOMACY_ADMIN_TELEGRAM_ID` (optional, not a secret) is the maintainer's numeric
Telegram id. With it set, every error the API or the bot logs is DMed there
(throttled: once per 15 minutes per kind of error, 20 an hour in all; the next alert
of a kind counts the ones held back), and so is every player's `/feedback`. Set it in
`.env`, then `docker compose up -d`. You must have sent the bot `/start` once, or
Telegram will not let it message you.

`DIPLOMACY_BOT_USERNAME` (optional, not a secret) is the bot's Telegram username, without
the `@`; blank means `IronChancellorBot`. The web game page's "Link a Telegram group"
opens `https://t.me/<it>?startgroup=link_<game_id>`, so set it if you run your own bot. The `/link-telegram` page reads it from the API too.

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
with a long-poll: the API holds each request up to 25 s and answers as soon
as a notification is committed. A notification is only acked after Telegram
accepted it. Healthy `/healthz` and `/health` checks and empty outbox polls
are left out of the API's access log; errors on them are not.
Delivered late, it is prefixed with the time it was created.

`/queue` in Telegram shows what is waiting and whether the server is
reachable.

## First-time setup (a fresh host)

You need a Debian or Ubuntu host you can SSH into **with a key** (see the warning
below), a Telegram bot token from [@BotFather](https://t.me/BotFather), and
optionally a domain name for HTTPS.

```bash
git clone https://github.com/tenderi/diplomacy.git ~/diplomacy   # or your fork
cd ~/diplomacy
./install.sh        # Docker, a 2 GB swap file if none, .env + secrets, nightly backup, hardening
```

> **`install.sh` runs `harden_host.sh`, which turns off SSH password logins** (keys
> only, root by key only) and installs fail2ban and automatic security reboots at
> 04:30 UTC. Install your SSH public key in `authorized_keys` *before* running it,
> or read [Hardening](#hardening) and skip that step on a host you share.

Put the bot token in `.env` (`TELEGRAM_BOT_TOKEN=` from @BotFather), or let
the deploy workflow write it. Set `DOMAIN` for HTTPS (below); without one, set
`DIPLOMACY_PASSWORD_RESET_BASE_URL` and `DIPLOMACY_CORS_ORIGINS` to the site's
public URL. Then:

```bash
./upgrade.sh        # pull the images, start (migrations run in the API entrypoint), verify
```

`upgrade.sh` pulls the prebuilt images for the checked-out commit from GHCR and
builds them on the host when they are not there (any commit of yours that the
upstream Deploy workflow never built), so a fork works without a registry of its own.
Open the site, register an account, and send your bot `/start` in Telegram.

### Running your own instance

The defaults point at the upstream project. On your own instance:

- **Bot username:** set `DIPLOMACY_BOT_USERNAME` in `.env` to your bot's username
  (the web app's "Link a Telegram group" opens it).
- **Your Telegram id** (optional): `DIPLOMACY_ADMIN_TELEGRAM_ID` gets error alerts and
  player feedback ([Secrets](#secrets)).
- **Source links (AGPL):** if you change the code, point the web footer
  (`SOURCE_URL` in `frontend/src/components/AppLayout.tsx`) and the bot's `/help`
  (`SOURCE_URL` in `src/server/telegram_bot/help_text.py`) at your fork. The bot's
  `/help` also links the upstream new-player guide; change that line too if you run
  your own docs site.
- **Deploy-on-merge** is optional. Without it, update by hand: `git pull` and
  `./upgrade.sh` ([Running by hand](#running-by-hand)).
- **Backups:** configure an rclone remote ([Backups](#backups)); until you do, dumps
  stay on the host's disk.

### Ports and the firewall

The site needs **inbound TCP 80 and 443** (443 for HTTPS; see below). Nothing else
needs to be open besides SSH: the bot dials out to Telegram. Many cloud providers
apply a network-level firewall in front of the host, separate from `ufw`; check that
80/443 are permitted there before assuming nginx is broken -- a
`tcpdump -ni any tcp port 80` that shows nothing is the signature.

### HTTPS (a domain name)

Set **`DOMAIN`** in `.env` and the next `./upgrade.sh` (or deploy) serves the site
over HTTPS:

1. Point the name at the VPS: an **A record** for it → the host's public IP address
   (wherever the domain's DNS is). Check with `dig +short <name>`.
2. Allow inbound **TCP 80 and 443** (ufw and any provider firewall). Port 80 is needed even
   for HTTPS: Let's Encrypt checks it before issuing the certificate, and Caddy
   redirects plain HTTP there.
3. On the VPS: `DOMAIN=<name>` in the checkout's `.env`, then
   `./upgrade.sh`.

`ensure_env.sh` then sets `COMPOSE_PROFILES=tls`, which starts the `caddy` service
(`docker/Caddyfile`): it gets and renews a Let's Encrypt certificate for `DOMAIN` by
itself (kept in the `caddy_data` volume) and redirects `http://` to `https://`. Caddy
owns the public ports 80/443, so nginx moves to `WEB_BIND=127.0.0.1`,
`WEB_PORT=8080`; password-reset links become `https://<DOMAIN>`. `upgrade.sh` checks
`https://<DOMAIN>/api/healthz` against this host and warns (without failing the
deploy) if it doesn't answer: a certificate that can't be issued is DNS or the
firewall, and `docker compose logs caddy` says which.

Clearing `DOMAIN` turns Caddy off again; nginx stays on loopback until `WEB_BIND`
is changed by hand.

**Client addresses.** Behind Caddy every request reaches nginx from Caddy's
container. nginx takes the client's address from the `X-Forwarded-For` Caddy sets
(`real_ip`, trusted only from Docker network addresses) and passes the API that one
address, replacing any `X-Forwarded-For` the client sent -- the API's per-IP login
and registration rate limits depend on it.

### The documentation site

`https://<DOCS_DOMAIN>` serves
`docs/` as a website: `mkdocs.yml` (Material for MkDocs) is built into the
`diplomacy_docs` image (`docker/docs.Dockerfile`, `mkdocs build --strict`, so a broken
link fails the build) and Caddy serves it under its own certificate. To turn it on:
an A record for the name → the VPS, then `DOCS_DOMAIN=<name>` in `.env` and
`./upgrade.sh` (needs `DOMAIN` too; the docs container runs with Caddy).
`upgrade.sh` warns if it doesn't answer. Its image is rebuilt for every deploy, so a merged
doc change is live minutes later. Preview locally:
`pip install "mkdocs>=1.6,<2" "mkdocs-material>=9.5,<10" && mkdocs serve`.

### Password reset ("Forgot password?")

The web login page's *Forgot password?* sends a single-use link, valid for an
hour, to `https://<DOMAIN>/reset-password?token=…`
(`DIPLOMACY_PASSWORD_RESET_BASE_URL`, set from `DOMAIN`). Telegram is preferred,
email is the fallback:

- an account **linked to Telegram** (the web app's *Link Telegram*) gets it as a
  message from the bot, and no email -- nothing to configure;
- any other account gets it **by email**, once `DIPLOMACY_SMTP_HOST` (and `_PORT`,
  `_USER`, `_PASSWORD`, `_FROM`) are set in `.env`. Email is also used if the
  Telegram message could not be queued.

With neither, nothing arrives and the API logs a warning naming the address.
The reply never says whether the address has an account. Limits: 10 requests
per IP per hour (then 429), and at most 3 links per address per hour (further
requests are answered the same but send nothing).

### Hardening

What protects the host and the site, and where it lives:

- **Network.** Set ufw up yourself (no script does it, so a shared host's rules stay
  untouched): deny inbound by default, allow SSH rate-limited (`ufw limit 22/tcp`).
  Docker-published ports bypass ufw, so the compose file
  publishes only Caddy's 80/443 publicly; the API, DAIDE and nginx are on
  `127.0.0.1`, Postgres nowhere (`tests/test_deployment_infrastructure.py`).
- **OS** (`harden_host.sh`, idempotent, run by `install.sh`; re-run by hand after
  editing it): sshd keys only and root by key only, no X11 or agent forwarding,
  `MaxAuthTries 3`, idle sessions dropped; the GitHub Actions key is `restrict`ed
  (it only pipes a script into `bash -s`); fail2ban bans an IP for an hour after
  five failed SSH logins; unattended-upgrades installs security updates daily and
  reboots at 04:30 UTC when one needs it (every container restarts itself). The
  sshd change is validated with `sshd -t` before the reload.
- **Containers.** Every service has `no-new-privileges`; the API and the bot
  run as an unprivileged user with all Linux capabilities dropped.
- **HTTP** (`docker/Caddyfile`, `docker/web-nginx.conf.template`): HSTS, a strict
  Content-Security-Policy (scripts from the site only), `nosniff`,
  `X-Frame-Options: DENY`, no server versions. The API's Swagger/ReDoc/OpenAPI
  pages are off in production (`DIPLOMACY_API_DOCS=0`; on by default for local
  development). Admin routes need `X-Admin-Token`; every token and bot-secret
  check is a constant-time comparison (`api.shared.is_admin_token`/`is_bot_secret`).
- **Secrets** are generated on the host by `ensure_env.sh` and never leave it,
  except the Telegram token, which GitHub holds (see *Deploy-on-merge*).

## Deploy-on-merge (GitHub Actions)

`.github/workflows/deploy.yml` deploys automatically after the Test Suite is
green on `main` (or on demand: *Run workflow*, optionally with a SHA, short
or full, or a tag). Nothing is built on the VPS. The workflow has three jobs:

0. **`gate`** skips an automatic deploy whose commit is no longer the tip of
   `main`. Two merges minutes apart give two Test Suite runs, and the older one
   can finish last; deploying it would roll the host back. The newer tip has its
   own Test Suite run and its own deploy. A deploy started by hand (a rollback)
   is never skipped.
1. **`images`** builds the four images of our own (`api`, `bot`, `web`, `docs`,
   from `docker/*.Dockerfile`) in GitHub Actions, with the Actions layer cache,
   and pushes them to GHCR as `ghcr.io/tenderi/diplomacy-<service>:<full commit
   SHA>`. A tag that already exists is not rebuilt.
2. **`deploy`** SSHes in as `root`, fetches and checks out that SHA (detached),
   writes `TELEGRAM_BOT_TOKEN` into `.env` (only that line), and runs
   `DIPLOMACY_IMAGE_TAG=<sha> ./upgrade.sh`, which:
   1. runs `ensure_env.sh` (fills any missing secret);
   2. `docker compose pull` of the four services (`docker-compose.yml` names
      them `ghcr.io/tenderi/diplomacy-<service>:${DIPLOMACY_IMAGE_TAG}`;
      `postgres` and `caddy` are left as they are). **If the pull fails**, it
      prints a `::warning::` (shown on the workflow run) and builds the images
      on the host instead, as every deploy did before: a slower deploy, not a
      broken one. A failed build leaves the running stack alone;
   3. `docker compose up -d --no-build --remove-orphans`;
   4. removes the images of ours that no container uses (by label: never
      another project's) and the dangling ones; after a build on the host it
      also empties the BuildKit build cache (`docker builder prune -af`),
      printing its size;
   5. installs the nightly backup cron job if missing;
   6. waits for `http://127.0.0.1:8000/healthz` and checks
      `http://127.0.0.1/api/healthz` (nginx → API), and **fails the workflow** if
      either does not answer.

The token travels on stdin, never in a command line.

**The GHCR packages must be public**, because the VPS pulls anonymously and
holds no registry credential. A package GitHub creates on the first push may
start out private, and the workflow's token cannot change that: on GitHub,
*Packages* → `diplomacy-api` (and `-bot`, `-web`, `-docs`) → *Package
settings* → *Change visibility* → *Public*. Until then every deploy falls back
to building on the host (the `::warning::` above). To check from anywhere:

```bash
tok=$(curl -fsS "https://ghcr.io/token?scope=repository:tenderi/diplomacy-api:pull" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
curl -fsSI -H "Authorization: Bearer $tok" \
  -H "Accept: application/vnd.oci.image.index.v1+json" \
  https://ghcr.io/v2/tenderi/diplomacy-api/manifests/<full sha>   # 200: public
```

**Rollback** is a deploy of the previous commit: *Actions* → *Deploy* → *Run
workflow* with the last good SHA (`gh workflow run deploy.yml -R
tenderi/diplomacy -f ref=<sha>`). Its images are still in GHCR, so `images`
skips the build and the host pulls exactly what ran before. Database
migrations are not rolled back; a rollback across a migration needs its
`downgrade` run by hand first.

One-time setup, from a machine that can SSH into the VPS (`HOST` is its address,
`REPO` your GitHub repository, e.g. `you/diplomacy`):

```bash
# 1. A dedicated deploy key for GitHub (no passphrase), installed for root.
ssh-keygen -t ed25519 -f ~/.ssh/diplomacy_deploy -N "" -C "github-actions-deploy"
cat ~/.ssh/diplomacy_deploy.pub | ssh root@$HOST 'cat >> ~/.ssh/authorized_keys'

# 2. Secrets and the gate.
gh secret set TELEGRAM_BOT_TOKEN -R $REPO           # paste the token from @BotFather
gh secret set VPS_HOST     -R $REPO --body "$HOST"
gh secret set VPS_SSH_KEY  -R $REPO < ~/.ssh/diplomacy_deploy
gh secret set VPS_HOST_KEY -R $REPO --body "$(ssh-keyscan -t ed25519 $HOST 2>/dev/null)"
gh variable set DEPLOY_CONTROL_ENABLED --body true -R $REPO
```

The host's address is a secret rather than a variable so that it is masked in the
(public) workflow logs. Optional repository variables override the defaults:
`VPS_USER` (`root`) and `VPS_REPO_DIR` (`~/diplomacy`). Until
`DEPLOY_CONTROL_ENABLED` is `true` the workflow is skipped, not red. On a fork, the
images go to your own GHCR namespace only if you change `ghcr.io/tenderi/` in
`docker-compose.yml`, `upgrade.sh` and `deploy.yml`; otherwise the host builds them.

## Running by hand

On the VPS, in the checkout (`~/diplomacy`):

```bash
./upgrade.sh                           # the same thing the workflow runs
./upgrade.sh --build                   # build the images here instead of pulling them
docker compose ps
docker compose logs -f diplomacy_bot   # or diplomacy_api, diplomacy_web, postgres
docker compose restart diplomacy_bot
```

Every container logs to the host's systemd journal, so logs survive the container
being recreated on each deploy (a Docker json-file log is deleted with its container).
`docker compose logs` shows the current containers; to read further back:

```bash
journalctl COM_DOCKER_COMPOSE_SERVICE=diplomacy_api --since -2d        # or diplomacy_bot, ...
journalctl COM_DOCKER_COMPOSE_SERVICE=diplomacy_api -p err --since -7d  # errors only
```

The deploy leaves the checkout on a detached SHA; `upgrade.sh` by hand there
redeploys that SHA without pulling the code. `git checkout main` first to pull.
By hand, the image tag is the checked-out commit (`git rev-parse HEAD`): a commit
of `main` that went through the Deploy workflow has its images in GHCR; any other
falls back to building on the host, as does `--build` (use it when GHCR or
Actions is down). The host build needs the 2 GB swap and pins the CPU for a few
minutes (a cold build measured 138 s with the CPU saturated throughout), so
prefer pulling. After a successful start `upgrade.sh` records the tag as
`DIPLOMACY_IMAGE_TAG` in `.env`, so a bare `docker compose up -d` by hand keeps
the deployed images instead of building new ones.

## Admin operations

Admin routes take the `X-Admin-Token` header (`DIPLOMACY_ADMIN_TOKEN` in `.env`). They are
not exposed through the bot, which holds no admin token by design. On the VPS:

```bash
cd ~/diplomacy
ADMIN="X-Admin-Token: $(grep ^DIPLOMACY_ADMIN_TOKEN= .env | cut -d= -f2-)"
curl -X DELETE -H "$ADMIN" http://127.0.0.1:8000/admin/games/42    # delete one game (players are told)
curl -H "$ADMIN" http://127.0.0.1:8000/games/42/export > game42.json  # saved-game export
curl -H "$ADMIN" "http://127.0.0.1:8000/admin/feedback?limit=50"      # player feedback, newest first
```

## Backups

`backup.sh` writes `pg_dump | gzip` to `/var/backups/diplomacy/` and keeps 14
days (`BACKUP_DIR`, `BACKUP_KEEP_DAYS` override), then **copies the folder off-host**
with rclone (any rclone remote; the default is Proton Drive) and deletes remote copies older than 60 days
(`BACKUP_REMOTE_KEEP_DAYS`). `/etc/cron.d/diplomacy-backup` runs it nightly at
03:17 UTC, logging to `/var/log/diplomacy-backup.log`. `upgrade.sh` runs
`./backup.sh --install` on every deploy, which (re)installs that job and
installs rclone from rclone.org (checksum-verified) if it is missing or older
than 1.64 -- Ubuntu's own package is too old to have the Proton Drive backend.

The remote is `BACKUP_RCLONE_REMOTE` (in `.env`; default
`proton:diplomacy-backups`; set it to e.g. `s3:my-bucket/diplomacy` for any other
rclone backend, after `rclone config` has created that remote). Until a remote with that name exists, the upload
is skipped with a note in the log and backups stay on the VPS disk only. Once
it exists, a failed upload makes the run exit non-zero with an `ERROR:` line
(the local dump is kept either way).

### One-time Proton Drive setup

rclone logs in as a whole Proton account, and Proton has no scoped tokens, so
whoever controls the VPS can read and delete that account's entire drive.
A separate, backups-only Proton account (the free tier is enough) limits
a compromise of the public host to the Diplomacy dumps. Keep `rclone.conf` at mode
600, and if the stack ever leaves the host, `rclone config delete proton`
and end the session in Proton's account settings. Then, over SSH on the VPS:

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
cd ~/diplomacy && ./backup.sh   # expect "off-host copy done"
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

- **Error alerts** in Telegram, with `DIPLOMACY_ADMIN_TELEGRAM_ID` set (see
  [Secrets](#secrets)). Every 5xx the API returns is logged at ERROR with its method
  and path, including a 500 a route raised on purpose, so it is alerted like any other
  error. The API's alerts travel the bot outbox; the bot sends its own directly,
  since they mostly happen while the API is down.
- `/queue` in Telegram: server reachability, this player's queued writes, and
  the last few delivered/refused ones.
- `docker compose ps` -- Postgres, the API, the bot, nginx and the docs site
  report `healthy` (Caddy has no healthcheck; `upgrade.sh` checks the site
  through it). The bot's healthcheck watches a heartbeat file both of its
  background loops touch, so a wedged bot is restarted by Docker. The checks are cheap on purpose: the API's is a
  bash `/dev/tcp` request to `/healthz` (no Python start-up), and both it and Postgres's
  poll every 60 s, every 2 s (`start_interval`, Docker >= 25) until first healthy.
- `docker compose logs diplomacy_bot` logs `API unreachable; player writes are
  being queued locally` once when the API drops and `API reachable again; N
  queued write(s) waiting` once when it returns, not on every poll.
- Disk: `df -h /` and `docker system df`. Every deploy empties the build
  cache, which once took 6.5 GB of the 20 GB disk unpruned. A capped prune
  (`--max-used-space`) is not enough: it skips the records `docker system df`
  calls shared, and those held 2.8 GB of real disk.
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
  at the head of the queue is being answered with a 5xx -- the API is up but
  unhealthy, most likely Postgres. `docker compose logs diplomacy_api postgres`.
  A 502/503/504 is retried for as long as it lasts; any other 5xx (a 500) only
  8 times, after which the entry is reported to its player as not
  delivered ("The server kept failing") and the queue moves on.
- **The deploy failed at "API not healthy after 90s".** Usually a migration
  error: `docker compose logs diplomacy_api` shows the Alembic traceback. The
  old containers were already replaced, so fix forward (or deploy an older
  SHA via *Run workflow*).
