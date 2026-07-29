# Admin Dashboard

A minimal operations dashboard served by the API at `/dashboard` — service status, logs, and
read-only database inspection. No build step: plain HTML/CSS/JS in
[`src/server/dashboard/`](../../src/server/dashboard/), mounted by `_api_module.py` (`/` also
redirects here).

## Auth

Every endpoint requires the `X-Admin-Token` header matching `ADMIN_TOKEN`. In production the
token comes from SSM (`/diplomacy/admin_token`); the dashboard is reachable through nginx on
port 80, so the token is the only thing protecting it.

## Endpoints (`src/server/api/routes/dashboard.py`)

| Endpoint | Purpose |
|---|---|
| `GET /dashboard/api/services/status` | Status and uptime of the managed systemd units. |
| `POST /dashboard/api/services/restart` | Restart one unit. Body: `{"service": "diplomacy-bot"}`. |
| `GET /dashboard/api/logs/{service}?lines=N` | Recent journal lines via `journalctl -u <unit> --no-pager -n N`. |
| `GET /dashboard/api/database/tables` | List inspectable tables. |
| `GET /dashboard/api/database/table/{name}?limit=&offset=` | Paginated rows plus schema info. |
| `GET /dashboard/api/database/stats` | Totals: games, active games, players, recent activity. |

## Safety constraints

- **Service names are whitelisted** (`ALLOWED_SERVICES`) — `systemctl` is never handed
  user input.
- **Table names are whitelisted** (`ALLOWED_TABLES`: `games`, `players`, `users`, `orders`,
  `messages`, `game_snapshots`, `turn_history`) and queries are **SELECT only**. Pagination
  is mandatory so a large table can't be dumped in one request.
- Subprocess calls (`systemctl`, `journalctl`) parse their output defensively and surface
  failures as HTTP errors rather than tracebacks.

> **Known mismatch:** `ALLOWED_SERVICES` currently lists `["diplomacy", "diplomacy-bot"]`,
> but the units Terraform installs are `diplomacy-api` and `diplomacy-bot`
> (`infra/terraform/user_data.sh`). Status and log queries for the API service therefore
> fail in production until that list is corrected.

## Out of scope

Live log streaming (SSE), a query editor, log export, historical metrics or graphs. If the
dashboard needs to grow past read-only inspection plus restart, it wants real auth first.
