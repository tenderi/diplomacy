# Diplomacy browser client

React 18 + Vite + TypeScript SPA. Register/login with email and password, link Telegram via code, list games, view map.

## Dev

```bash
npm install
npm run dev
```

Runs on http://localhost:5173. Vite proxy forwards `/auth`, `/games`, `/users` to the API (default http://localhost:8000). Set `VITE_API_URL` if the API is elsewhere.

## Build

```bash
npm run build
```

Output in `dist/`. The FastAPI server serves it at `/app` when `frontend/dist` exists.

## Routes

- `/` — Home (login/register or links to games, link Telegram)
- `/login`, `/register` — Auth
- `/link-telegram` — Generate code to link Telegram (requires login)
- `/games` — My games + all games
- `/games/:id` — Game view (map, phase)
