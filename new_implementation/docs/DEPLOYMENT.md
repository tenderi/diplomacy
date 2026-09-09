# Deployment: VPS control layer + home game layer

Diplomacy runs split across **two hosts**, the same shape as the `p2p` repo:

- **Control layer** — the Telegram bot and the browser client, on the small
  public VPS that already runs p2p's bot. It holds a Telegram token and one
  shared secret. No database, no engine, no player data.
- **Game layer** — Postgres and the FastAPI server, on the home server
  (`kattotuuletin.local`). Everything that matters lives here.

They meet over the **WireGuard tunnel p2p already established** (VPS
`10.8.0.1`, home `10.8.0.2`). Nothing new is opened at home, and the only
thing crossing the tunnel is the API's HTTP.

```
  VPS (public IP)                             Home server (kattotuuletin)
  ┌───────────────────────────────────┐       ┌──────────────────────────────────┐
  │ diplomacy_bot                     │       │ diplomacy_api  :8000             │
  │  - Telegram long polling          │  WG   │  - FastAPI + engine + renderer   │
  │  - durable outbox (SQLite, /data) │◄─────►│  - bot_outbox table (Postgres)   │
  │  - pulls GET /bot/outbox          │       │  - DAIDE :8432 (loopback)        │
  │ diplomacy_web  :80                │       │ postgres                         │
  │  - nginx: SPA + /api/ -> :8000    │       │                                  │
  │ wg0 10.8.0.1                      │       │ wg0 10.8.0.2 (dials out)         │
  └───────────────────────────────────┘       └──────────────────────────────────┘
```

## Why it is split, and what "no message is ever lost" means

The home server sits on a residential connection. The tunnel *will* be down at
some point when a player presses send, and a deadline *will* pass while it is.
The split is designed so that costs nothing but latency:

**Player → server (orders, messages).** The bot writes every such command to a
durable SQLite queue on the VPS *before* the first delivery attempt
(`src/server/telegram_bot/outbox.py`). If the API is unreachable the player is
told, immediately, that it is queued and when it was sent; a background loop
retries in order and DMs the result. Each queued request carries:

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

## Sizing

The VPS already hosts p2p's bot and is sized for it (1 vCPU / 1 GB). The
diplomacy bot idles on a long-poll socket and two short polls; nginx serves a
few hundred KB of static files. Budget another ~150 MB RAM. The home server
does everything else: Postgres plus the API (map rendering is the only
CPU-noticeable work).

## First-time setup

### 1. Home server (game layer)

`~/p2p/install.sh` must already have run here: it set up Docker, wg0, the
WireGuard watchdog, and the `docker.service` drop-in that waits for wg0.

```bash
git clone https://github.com/tenderi/diplomacy.git ~/diplomacy
cd ~/diplomacy/new_implementation
./install_home.sh
```

Generates `POSTGRES_PASSWORD`, `DIPLOMACY_JWT_SECRET`, `DIPLOMACY_ADMIN_TOKEN`
and `DIPLOMACY_BOT_SECRET` into `.env` and **prints the bot secret** -- the
VPS needs the same value. Then edit `.env`:

- `DIPLOMACY_PASSWORD_RESET_BASE_URL` / `DIPLOMACY_CORS_ORIGINS` — the URL the
  web client is served from (the VPS).
- `WG_IP` — this host's tunnel address (default `10.8.0.2`).

```bash
docker compose up -d          # builds the API image, runs migrations, starts
curl -sS http://127.0.0.1:8000/healthz
```

### 2. VPS (control layer)

```bash
git clone https://github.com/tenderi/diplomacy.git ~/diplomacy
cd ~/diplomacy/new_implementation
./install_vps.sh
```

Edit `.env`: `TELEGRAM_BOT_TOKEN` from @BotFather and the
`DIPLOMACY_BOT_SECRET` printed at home. **The two secrets must match exactly.**

```bash
docker compose -f docker-compose.control.yml up -d
curl -sS http://10.8.0.2:8000/healthz     # the API, over the tunnel
curl -sS http://127.0.0.1/healthz         # nginx
```

Then message the bot.

### 3. Ports and the UpCloud firewall

The tunnel needs nothing beyond what p2p opened (UDP 33500). The **web
frontend needs inbound TCP 80** (and 443 once TLS is set up) on the VPS.
UpCloud applies a network-level firewall in front of the host, separate from
`ufw`; on a trial account it cannot be edited. Check that 80/443 are permitted
before assuming nginx is broken -- a `tcpdump -ni any tcp port 80` that shows
nothing is the same signature p2p's README describes for UDP.

### 4. TLS

Nothing here terminates TLS. The login form must not stay on plain HTTP once
anyone but you uses it. The least-effort path is a hostname pointed at the
VPS and Caddy in front of `diplomacy_web` (Caddy fetches certificates on its
own); set `WEB_BIND=127.0.0.1` in the VPS `.env` so nginx only answers to
Caddy, and set `DIPLOMACY_PASSWORD_RESET_BASE_URL` at home to the `https://`
URL.

## Running

```bash
# --- home ---
docker compose up -d
docker compose logs -f diplomacy_api
docker compose up -d --build diplomacy_api     # after editing src/
./upgrade.sh                                   # pull, rebuild, restart, verify

# --- VPS ---
docker compose -f docker-compose.control.yml up -d
docker compose -f docker-compose.control.yml logs -f diplomacy_bot
./upgrade_control.sh
```

Migrations run in the API container's entrypoint on every start. The bot's
queue lives in the `bot_data` volume and is untouched by rebuilds.

## Monitoring

- `/queue` in Telegram: server reachability, this player's queued writes, and
  the last few delivered/refused ones.
- **Home:** `docker compose ps`, `curl http://127.0.0.1:8000/healthz`,
  `sudo wg show` (last handshake).
- **VPS:** `docker compose -f docker-compose.control.yml logs diplomacy_bot`
  logs `API unreachable; player writes are being queued locally` once when
  the link drops and `API reachable again; N queued write(s) waiting` once
  when it returns, not on every poll.
- Pending server-side notifications: from the VPS,
  `curl -H "X-Bot-Secret: $DIPLOMACY_BOT_SECRET" http://10.8.0.2:8000/bot/outbox/stats`.
- The bot container's healthcheck watches a heartbeat file both background
  loops touch; a wedged bot is restarted by Docker.

## Troubleshooting

- **Bot replies "The game server is unreachable right now".** The tunnel or
  the API is down. Writes are queued; reads fail until it returns. On the
  VPS: `sudo wg show`, `ping 10.8.0.2`. At home: `systemctl status
  wg-quick@wg0`, `docker compose ps`, `docker compose logs diplomacy_api`.
- **`diplomacy_api` restart-loops with a bind error.** wg0 is not up, so
  `10.8.0.2` does not exist yet. `sudo systemctl start wg-quick@wg0`. If it
  happens on every reboot the docker.service drop-in is missing -- re-run
  `~/p2p/install.sh`.
- **401 "requires the 'X-Bot-Secret' header" in the bot log.**
  `DIPLOMACY_BOT_SECRET` differs between the two `.env` files.
- **A queued order was refused: "composed at ... but the turn was processed
  at ...".** Working as designed: the deadline passed while the link was down.
  The player is told; the orders were not applied to the new phase.
- **A notification arrived twice.** The bot sent it, then could not reach the
  API to ack it, so the row came back on the next poll. At-least-once is the
  deliberate side of this trade.
- **`/queue` shows attempts climbing but the server is reachable.** The entry
  at the head of the queue is being refused with a *transient* status
  (502/503/504) -- the API is up but unhealthy, most likely Postgres. Check
  `docker compose logs diplomacy_api` at home.

## What the old AWS deployment was

Until this split, `infra/terraform/` described a single EC2 instance running
nginx + uvicorn + the bot + Postgres, deployed from CI over OIDC/SSM. It was
never left running (see `docs/specs/done_fixes.md`, Track H). The Terraform and
`infra/scripts/deploy.sh` are kept in the tree as reference but are
**superseded by this document**; nothing in them is exercised, and
`.github/workflows/deploy.yml` stays gated off.
