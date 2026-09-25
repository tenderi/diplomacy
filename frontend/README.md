# Diplomacy browser client

React 18 + Vite + TypeScript SPA: register and log in with email and password, link Telegram
with a code, list and create games, and play them — the board, orders, results, messages,
draw votes.

**UI stack:** Tailwind CSS + shadcn/ui. To add a shadcn component:
`npx shadcn@latest add <component>` (e.g. `npx shadcn@latest add dialog`).

## Dev

```bash
npm install
npm run dev
```

Runs on http://localhost:5173. Vite proxies `/api` to the API (http://localhost:8000). Set
`VITE_API_URL` if the API is elsewhere.

## Build and test

```bash
npm run build          # → dist/; in production nginx serves it (docker/web.Dockerfile)
npm run test:run       # Vitest + React Testing Library
npm run test:coverage  # the same, with the coverage thresholds CI enforces
```

See [`docs/TESTING.md`](docs/TESTING.md).

## Routes

- `/` — Home (login/register, or links to games and Link Telegram)
- `/login`, `/register`, `/forgot-password`, `/reset-password` — Auth
- `/link-telegram` — Generate a code to link Telegram (requires login)
- `/games` — My games, all games, create a game
- `/games/:id` — The game: map, orders, results, messages
