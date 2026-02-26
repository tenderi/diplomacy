# Complete user database + browser auth + Telegram linking

## Goals

- **Complete user database**: One user record per account; can have email (for browser) and/or Telegram (for bot).
- **Browser**: Register and login with email + password; session via JWT (access + refresh).
- **Link Telegram**: Logged-in user can generate a short-lived code on web; in Telegram they send `/link <code>`; bot calls API to attach `telegram_id` to that user.
- **Dual client support**: Same API serves Telegram bot (identifies by `telegram_id` in body) and browser (identifies by `Authorization: Bearer <access_token>`). Game actions resolve to a single `user_id` either way.
- **Modern stack**: No legacy tech — PyJWT + passlib on backend; React 18 + Vite + TypeScript on frontend.

---

## 1. Database and user model

**Current** UserModel: `id`, `telegram_id` (unique, required), `full_name`, `username`, `is_active`, `created_at`, `updated_at`. No email or password.

**Changes:**

- **users table**
  - Add `email` — String(255), unique, nullable (Telegram-only users have no email initially).
  - Add `password_hash` — String(255), nullable (Telegram-only users may have no password).
  - Make `telegram_id` nullable and keep unique when not null (browser-only users have no telegram_id until they link).
- **link_codes table** (new) — for Telegram linking: `id`, `user_id` (FK users), `code` (e.g. 6-char, unique), `expires_at`, `created_at`. Expire after e.g. 10 minutes.

**Migration:** New Alembic revision: add columns to users, create link_codes. Existing users keep telegram_id set, email/password_hash null.

**DatabaseService:** Add `get_user_by_email`, `create_user_with_password`, `set_user_telegram_id`, `create_link_code`, `consume_link_code`; keep `get_user_by_telegram_id`, `create_user` for Telegram-first registration.

---

## 2. Backend auth (FastAPI)

**Stack:** PyJWT, passlib with bcrypt, OAuth2PasswordBearer.

**Auth routes:** POST /auth/register, POST /auth/login, POST /auth/token, POST /auth/refresh, GET /auth/me, POST /auth/me/link_code, POST /auth/telegram/link. Tokens: access (short-lived), refresh (longer). Dependency: get_current_user (Bearer).

---

## 3. Dual auth for game routes

Dependency `get_current_user_or_telegram`: if Bearer present and valid → user from token; else if telegram_id in body → get_user_by_telegram_id; else 401. Use in join, quit, replace, set_orders, clear_orders, message, broadcast, get messages, user games. Keep telegram_id optional in request bodies for backward compatibility.

---

## 4. Telegram bot: /link command

Bot receives /link <code>, calls POST /auth/telegram/link with telegram_id + code. Success: "Telegram linked." Invalid/expired: "Invalid or expired code. Get a new code from the web app."

---

## 5. Map from DB

GET /games/{game_id}/map.png — load state via get_game_state, build units/phase_info/supply_center_control, Map.render_board_png, return PNG. No server.games required.

---

## 6. Frontend

React 18 + Vite + TypeScript, React Router 6, auth context, API client with Bearer + refresh. Pages: Register, Login, Link Telegram, Home, game list, lobby, game view (map, orders, messages). Forms: React Hook Form + Zod. UI: Tailwind; optionally shadcn/ui. Build served by FastAPI (e.g. /app).

---

## 7. Implementation order

1. User schema + migration + DatabaseService
2. Auth backend (register, login, refresh, me, link_code, link_telegram)
3. Dual auth dependency + update game routes
4. Telegram /link command
5. GET /games/{id}/map.png from DB state
6. Frontend scaffold (Vite + React + TS)
7. Frontend auth pages + game UI

---

## 8. Security notes

- Passwords: bcrypt via passlib; never log or return password/hash.
- JWT secret from env (DIPLOMACY_JWT_SECRET).
- Link codes: short expiry, single-use; rate-limit if needed.
- CORS: allow frontend origin only.
