# Browser Client

Play Diplomacy in a browser: register with email and password, then optionally link the same
account to Telegram and use either.

## Run locally

Backend (must be on port 8000 for the Vite proxy):

```bash
source venv/bin/activate
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000
```

Frontend, in a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. Vite proxies API calls to the backend and serves the SPA for app
routes, so refresh and back/forward work correctly. UI is Tailwind CSS + shadcn/ui — see
[`frontend/README.md`](https://github.com/tenderi/diplomacy/blob/main/frontend/README.md).

## Register

**Register** → email, password (minimum 8 characters), optional full name. You are logged in
immediately; from there use **My games / All games** and **Link Telegram**.

## Sandbox

**Sandbox** (in the header, or **Try orders in the sandbox** on a game's page) opens a scratch
board where you give orders for all seven powers: to see how the rules resolve a position,
or to play out what your neighbours might do. From a game it starts at that game's current
position; from the header, at the opening position of 1901.

- Pick a power, then choose each unit's order from the menus, or type them
  (**Type ... orders instead**, one per line, e.g. `A PAR - BUR`). Units without an order hold.
- **Resolve** adjudicates everyone's orders and moves to the next phase: retreats, then winter
  builds and disbands, then the next spring, exactly as a real game would. Orders the rules
  refuse are listed, and those units hold.
- The map shows the board, the orders you have entered, or the last resolution.
- **Step back** undoes the last resolution; **Start over** returns to where you began.

Nothing in the sandbox affects the real game, and nothing is saved: leaving the page ends it.

## Link Telegram

1. In the browser: **Link Telegram → Generate link code**.
2. In Telegram, send `/link <code>` to the bot.

Both clients now act as the same account. Unlink from the same page; you can re-link later
with a new code.

## Forgot password

Click **Forgot password?** on the login page and submit your email. The response is always
the same whether or not the account exists.

- **Development:** set `DIPLOMACY_PASSWORD_RESET_BASE_URL=http://localhost:5173` and
  `DIPLOMACY_DEV_SHOW_RESET_LINK=1` — the reset link appears on the confirmation page.
- **Production:** an account linked to Telegram gets the link from the bot; any other gets
  it by email once `DIPLOMACY_SMTP_HOST` (plus the other SMTP variables) is set. See
  [DEPLOYMENT.md](DEPLOYMENT.md) and
  [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md#3-environment-variables).

## Production build

```bash
cd frontend && npm run build
```

In production the `diplomacy_web` image builds this and nginx serves it, proxying `/api/` to
the API (`docker/web-nginx.conf.template`). If you serve the build from another static host,
configure **SPA fallback** (serve `index.html` for unmatched routes) or `/games/123` and
refresh will 404, and point `VITE_API_URL` at the API.

## Troubleshooting

- **Register does nothing / "Server unavailable"** — the frontend can't reach the API. Check
  it's running on port 8000, or set `VITE_API_URL` in `frontend/.env` and restart `npm run dev`.
- **Registration errors** — the app surfaces the API message ("Password must be at least 8
  characters", "Email already registered"). If registration fails silently, check Postgres is
  up and `alembic upgrade head` has run.
