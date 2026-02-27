# Browser client (web app)

You can play Diplomacy in a browser: register with email and password, then optionally link the same account to Telegram.

## Run locally

**Backend** (from repo root):
```bash
cd new_implementation && source venv/bin/activate
uvicorn server.api:app --host 0.0.0.0 --port 8000
```

**Frontend** (separate terminal):
```bash
cd new_implementation/frontend
npm install && npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/auth`, `/games`, `/users` to the API.

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

## Production

- Set `DIPLOMACY_JWT_SECRET` for the API.
- Build the frontend: `cd frontend && npm run build`. The API serves `frontend/dist` at `/app` when present (e.g. open `https://your-api-host/app`).

See `frontend/README.md` for more details.
