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
[`frontend/README.md`](../frontend/README.md).

## Register

**Register** → email, password (minimum 8 characters), optional full name. You are logged in
immediately; from there use **My games / All games** and **Link Telegram**.

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
- **Production:** set `DIPLOMACY_SMTP_HOST` (plus the other SMTP variables) so links are
  emailed. See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md#3-environment-variables).

## Production build

```bash
cd frontend && npm run build
```

FastAPI serves `frontend/dist` at `/app` when it exists. Set `DIPLOMACY_JWT_SECRET` for the
API. If you serve the build from a separate static host, configure **SPA fallback** (serve
`index.html` for unmatched routes) or `/games/123` and refresh will 404.

## Troubleshooting

- **Register does nothing / "Server unavailable"** — the frontend can't reach the API. Check
  it's running on port 8000, or set `VITE_API_URL` in `frontend/.env` and restart `npm run dev`.
- **Registration errors** — the app surfaces the API message ("Password must be at least 8
  characters", "Email already registered"). If registration fails silently, check Postgres is
  up and `alembic upgrade head` has run.
