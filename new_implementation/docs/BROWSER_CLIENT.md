# Browser client (web app)

You can play Diplomacy in a browser: register with email and password, then optionally link the same account to Telegram.

## Run locally

**Backend** (from repo root; API must listen on 8000 for Vite proxy):
```bash
cd new_implementation && source venv/bin/activate
PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal):
```bash
cd new_implementation/frontend
npm install && npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` to the API so that app routes (e.g. `/games`, `/games/123`) are served by the frontend; **refresh and back/forward work correctly**. The frontend uses Tailwind CSS and shadcn/ui for the UI.

## First time: register

1. Open the app → **Register**.
2. Enter email, password (min 8 characters), and optional full name.
3. You are logged in; use **My games / All games** and **Link Telegram** as needed.

## Link Telegram

1. In the browser: **Link Telegram** → **Generate link code**.
2. In Telegram: send `/link <code>` (e.g. `/link 123456`) to the bot.
3. This Telegram account is now linked to your browser account; you can use either.

## Forgot password

1. On the login page, click **Forgot password?**.
2. Enter your email and submit. If an account exists, a reset link is generated (and optionally sent by email if you configure SMTP).
3. For development: set `DIPLOMACY_PASSWORD_RESET_BASE_URL` (e.g. `http://localhost:5173`) and `DIPLOMACY_DEV_SHOW_RESET_LINK=1`; the reset link will appear on the confirmation page so you can copy it and open the reset-password form.
4. Set your new password; you can then log in with the new password.

## Troubleshooting: Register does nothing or shows error

- **API must be running** and reachable. The Vite dev server proxies `/api` to `http://localhost:8000`. If your API runs on another port, set `VITE_API_URL=http://localhost:PORT` in `frontend/.env` and restart `npm run dev`.
- **Database**: Registration uses the API database; ensure PostgreSQL is up and migrations are applied (`alembic upgrade head`).
- **Error message**: The app now shows the API error message (e.g. "Password must be at least 8 characters", "Email already registered"). If you see "Server unavailable", the frontend could not reach the API.

## Production

- Set `DIPLOMACY_JWT_SECRET` for the API.
- Build the frontend: `cd frontend && npm run build`. The API can serve `frontend/dist` at `/app` when present (e.g. open `https://your-api-host/app`).
- If you serve the built app from a static server (e.g. nginx, Netlify), configure **SPA fallback**: serve `index.html` for routes that do not match a file (so `/games/123` and refresh/back work). With Vite preview: `npm run preview` already does this.

See `frontend/README.md` for more details.
