# What to do next

Suggested next steps, in priority order.

---

## 1. Complete browser gameplay (high impact) — DONE

The browser client now supports full gameplay:

| Feature | Status |
|--------|--------|
| **Create game** | Button on game list; `POST /games/create` then navigate to game. |
| **Join game** | On game view: power dropdown (available powers only) + Join button; `POST /games/{id}/join` with Bearer. |
| **Submit orders** | Orders textarea (pre-filled from `GET .../orders/{power}`), Submit button; `POST /games/set_orders` with Bearer. |
| **Process turn** | Button on game view; `POST /games/{id}/process_turn`. |
| **Messages** | List + form (private: select recipient power; broadcast: checkbox); send via `POST .../message` or `.../broadcast`. |

Backend fix: messages filter now uses OR so broadcasts and private messages to/from the user are returned (`get_game_messages`).

---

## 2. CORS (if frontend is on another origin) — DONE

CORS middleware is enabled in both `server/api.py` and `server/_api_module.py`. Origins are controlled by `DIPLOMACY_CORS_ORIGINS` (comma-separated; default `*`). Use specific origins in production (e.g. `https://app.example.com`).

---

## 3. Tests for auth and linking — DONE

- **API** (`tests/test_auth.py`): Register, login, `/auth/me` (with Bearer), link code + telegram link, invalid code, refresh token, join game with Bearer, set orders with Bearer.
- **Password hashing**: Auth uses the `bcrypt` library directly (not passlib) for compatibility. Ensure `bcrypt` is installed (`pip install bcrypt`).
- **DB**: Auth flows covered by API tests; optional dedicated DB tests for `create_user_with_password`, `create_link_code`, `consume_link_code` can be added later.

---

## 4. Optional product/UX improvements

- **Unlink Telegram** — DONE: `POST /auth/me/unlink_telegram` (Bearer); "Unlink Telegram" on Link Telegram page when linked; test in `test_auth.py::test_unlink_telegram`.
- **Email verification**: Require verified email before full access (optional, from plan "out of scope").
- **Forgot password** — DONE: `POST /auth/forgot_password` (email), `POST /auth/reset_password` (token, new_password); `password_reset_tokens` table; frontend Forgot password / Reset password pages and "Forgot password?" on Login. Set `DIPLOMACY_PASSWORD_RESET_BASE_URL` for reset links; set `DIPLOMACY_DEV_SHOW_RESET_LINK=1` to return/log the link when email is not configured.

---

## 5. Later / from fix_plan.md

- **Channel Phase 3**: Analytics, tournament integration, spectator mode, cross-platform (e.g. Discord).
- **Visualization**: Interactive map (clickable provinces, tooltips), more themes, analysis overlays.

---

## Test coverage

- **Failing tests fixed**: `test_user_registration` (duplicate/empty telegram_id expectations and unique IDs); all tests pass.
- **Auth and users coverage**: `server.api.routes.auth` ~87%, `server.api.routes.users` ~93%. Added tests for: register invalid email/short password, login wrong password/nonexistent, OAuth2 token endpoint, refresh invalid token, unlink when not linked, reset password invalid/short, forgot password invalid email and base_url-without-dev-link, telegram link 409 and already-linked, GET `/users/me/games` with Bearer.
- **Run coverage**: `pytest tests/ --cov=src --cov-report=term-missing`. For auth+users only: `pytest tests/test_auth.py tests/test_api_routes_users.py tests/test_user_registration.py --cov=server.api.routes.auth --cov=server.api.routes.users --cov-report=term-missing`.
- **100% on whole codebase**: Would require many more tests (e.g. `map`, `game`, channels, bot). `.coveragerc` sets `fail_under = 85` for `src/engine` and `src/server` when run via coverage.

---

## Quick reference

- **Browser client**: `frontend/` — run with `npm run dev`; build with `npm run build` (served at `/app` when `frontend/dist` exists).
- **Auth**: JWT in `Authorization: Bearer <access_token>`; refresh via `POST /auth/refresh`.
- **Plan**: `specs/browser_client_plan.md`.
- **Docs**: `docs/BROWSER_CLIENT.md`, `docs/TELEGRAM_BOT_COMMANDS.md` (includes `/link`).
