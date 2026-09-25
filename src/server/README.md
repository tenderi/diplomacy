# Server Module

The FastAPI HTTP API, a text-command CLI surface, and the DAIDE TCP server. All three route
through `GameService`, the single entry point into the game engine.

The authoritative endpoint list is the generated OpenAPI schema at
**http://localhost:8000/docs** (on in development; production sets `DIPLOMACY_API_DOCS=0`).
This file is the orientation map. Environment variables are listed in
[`docs/LOCAL_DEVELOPMENT.md`](../../docs/LOCAL_DEVELOPMENT.md).

## Auth and authorization

Two authentication modes coexist and resolve to the same user:

- **JWT Bearer** — `Authorization: Bearer <access_token>`, used by the browser client.
- **`telegram_id` + the bot secret** — in the request body (or query string on GET routes),
  or the `X-Bot-Secret` header, used by the Telegram bot.

`routes/auth.py` provides `resolve_user_or_telegram` (either mode → the user),
`require_bot_or_user` (a dependency admitting either kind of caller) and
`require_bot_secret` (the bot only). Every endpoint that acts for a power checks that the
caller holds it and answers **403** otherwise. Admin routes take `X-Admin-Token`. Every
secret comparison is constant-time.

## Endpoints by area

### Auth (`/auth`)

`register`, `login`, `token`, `refresh`, `me`, `forgot_password`, `reset_password`,
`me/link_code`, `telegram/link`, `me/unlink_telegram`.

`forgot_password` always answers the same way (no account enumeration) and sends a
single-use reset link: through the bot to an account linked to Telegram, otherwise by email
when `DIPLOMACY_SMTP_HOST` is configured. `telegram/link` is called by the bot with a
`telegram_id` and the short-lived code `me/link_code` generated.

### Users and the waiting list

`POST /users/persistent_register` (bot secret); `GET /users/{telegram_id}/games` (bot
secret, or a Bearer user reading their own linked id); `GET /users/me/games` (Bearer).
`POST /waiting_list/join` / `leave` and `GET /waiting_list` (bot secret): the automatic
match queue; the server creates a game when seven players are waiting.

### Games

- **Lifecycle:** `POST /games/create`, `GET /games`, `GET /games/{id}/state` (the
  GameState-native view — see [`data_spec.md`](../../docs/specs/data_spec.md)), `players`,
  `join`, `quit`, `replace`, `players/{power}/mark_inactive` (admin).
- **Settings:** `join_password` (private games), `dummies` (civil-disorder seats),
  `auto_process` (process as soon as every order is in), `wait` (a player's "wait for me").
- **Turns:** `POST /process_turn` — the game's creator, the bot or an admin;
  `require_all=true` refuses while a power that has something to order has not. `orders_status`,
  `last_resolution`, `resolutions`, `history/{turn}`.
- **Deadlines:** `GET`/`POST /deadline` (a member sets or clears it), and
  `deadline/propose`, `deadline/vote`, `deadline/withdraw` for a majority vote.
- **Endings:** `draw_vote`, `draw_vote_status`, `concede`.
- **Snapshots:** `snapshot` (any authenticated caller), `snapshots`,
  `restore/{snapshot_id}` (admin only — it rewinds the game; players are told).
- **Legal orders:** `GET /games/{id}/legal_orders/{power}` (and a per-unit variant) — the
  phase-aware list of everything legal right now, which the web client and the bot's order
  menus are built on.

A finished game accepts no writes (**409**). A write that loses a race with a concurrent
turn gets **409** too.

### Orders

`POST /games/set_orders` (`merge: true` adds to the power's orders, one per unit; without
it the request replaces them); `GET /games/{id}/orders` and `/orders/{power}`;
`POST /games/{id}/orders/{power}/clear`; `GET /games/{id}/orders/history`.

Order and clear requests accept an optional `client_timestamp` (ISO-8601 UTC, when the
player composed them). One older than the game's `phase_started_at` is refused with
**409** and a `detail` the bot shows verbatim — the turn was processed without it.

### Messages

`POST /games/{id}/message` (to one power), `POST /games/{id}/broadcast`,
`GET /games/{id}/messages` (what the caller may see). Both sends accept
`client_timestamp`; the message is stored with it and the notification says
"(sent HH:MM UTC)" when it was delayed.

### Maps

PNGs: `/games/{id}/map` (the board), `/map/orders` (with pending orders),
`/map/resolution` (the last turn's results), `/map/history/{turn}` (the board when turn
*turn* began), `/map/turn/{turn}/orders` (turn *turn*'s orders on that board, coloured by
result), `/maps/{map}/preview.png`. `GET /maps/{map}/provinces` gives full names, types and
coasts. `POST /games/{id}/generate_map[/orders|/resolution]` renders to a file.

### Telegram groups (`/games/{id}/channel…`)

Link, unlink, read and change the settings of the game's group; queue posts for it (the
current map, a broadcast, the timeline, the player dashboard, battle results, a discussion
thread). A player of the game, the bot or an admin only.

### Bot outbox and idempotency

`GET /bot/outbox?limit=&after_id=` returns undelivered notifications oldest first;
`POST /bot/outbox/ack {"delivered": [ids], "failed": {id: error}}` marks them done;
`GET /bot/outbox/stats` counts what is waiting. All three require `X-Bot-Secret` — a JWT is
**not** accepted. Server code creates rows through `api/shared.notify_user` /
`notify_players` / `post_to_game_group`, never directly.

Any mutating request that carries both `X-Bot-Secret` and an `Idempotency-Key` header has its
first response stored (statuses below 500) and replayed to every later request with the same
key, marked `Idempotent-Replayed: true`. This is how the bot's retry queue is safe.

### Admin and health

`/admin/*` (delete a game or all games, cache and connection-pool management, counts) and
`GET /games/{id}/export` / `POST /games/import` (saved games; they contain private messages)
require `X-Admin-Token`. There is no admin web page: the host is administered over SSH
([`docs/DEPLOYMENT.md`](../../docs/DEPLOYMENT.md)). `GET /health` and `GET /healthz` (both
check the database) and `GET /version` are open.

## Errors

HTTP errors are FastAPI's `{"detail": "<human-readable reason>"}`; the bot shows `detail`
verbatim. Notably **403** for acting on a power you don't hold, **404** for an unknown game,
**409** for a finished game or a stale write, **429** for rate-limited auth.

## CLI surface

`Server` (`server.py`) processes text commands and is used by tests; the HTTP API does not
depend on it. Its responses carry `status: "ok"` or `status: "error"` with an `error_code`
(`UNKNOWN_COMMAND`, `MISSING_ARGUMENTS`, `GAME_NOT_FOUND`, `INVALID_ORDER`).

```python
from server.server import Server
server = Server()
game_id = server.process_command("CREATE_GAME standard")["game_id"]
server.process_command(f"ADD_PLAYER {game_id} FRANCE")
server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
server.process_command(f"PROCESS_TURN {game_id}")
print(server.process_command(f"GET_GAME_STATE {game_id}"))
```

## DAIDE

`daide/` implements the DAIDE wire protocol (binary DCSP framing, token streams) and
listens on **port 8432**, started alongside the API. DAIDE bots connect, handshake (IM/RM),
negotiate (NME/HLO/MAP/MDF) and submit orders (SUB/THX) against a live `GameService` game.
Press content is relayed opaquely rather than parsed — a deliberate, permanent scope
limit. See [`architecture.md`](../../docs/specs/architecture.md).
