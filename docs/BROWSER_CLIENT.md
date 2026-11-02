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

**Register** → email, password (minimum 8 characters), optional nickname. You are logged in
immediately; from there use **My games / All games** and **Link Telegram**.

The nickname is what other players see next to your power; change or clear it on the home
page (the header shows it, or **Set a nickname**), or on a game page while you have none.
Please don't use your real name: the system keeps none.

## Games

**Games** lists your games and all open ones, and has a form to **Create new game**: choose
which powers are left to civil disorder (for fewer than seven players), whether turns are
processed as soon as every order is in, whether the powers are dealt at random, whether
players are **Public** (nicknames shown) or **Anonymous**, and an optional password that makes
the game private. The player naming and random powers cannot be changed afterwards. A game
that belongs to a Telegram group is joined through the bot, not here.

## The game page

Open a game to see, from the top:

- **Turn status**: the deadline as a countdown with your local weekday and time, the weekly
  schedule if there is one, which powers have ordered, and **Auto-process** on or off (with
  **Wait - still negotiating** / **I'm ready** while it is on).
- **What happened last turn**: your orders and how they resolved first, the other powers'
  behind a disclosure; after a retreat phase, the movement results come first. **Previous
  turns** below it shows any earlier phase, newest first.
- **The map**, as **Board**, **My pending orders** (seated players) or **Last resolution**.
  Click or tap it to enlarge; it opens fitted to the screen.
- **Join game**, if you have no seat: pick a power, or **Join (random power)**, and give the
  password of a private game.
- **Orders**: choose each unit's order from the menus, or the builds and disbands of a winter;
  an unordered unit holds (a dislodged one is disbanded). The server's note on each accepted
  order is shown after you submit, and the status line says whether your orders are in.
- **Messages**: the log shows each message's phase and local time, marks new ones, and lets
  you write to a power or to everyone; tick **Send anonymously (rumour)** to hide who sent a
  message to everyone.
- **Players**: who holds each power, which are in civil disorder, which are out.
- **Telegram group**: link the game to a group, or unlink it.
- **Draw vote**: vote for a draw or withdraw your vote; it ends when every surviving power has voted.
- **Leave game**: **Quit** hands your seat back and your units stay; **Concede** removes your
  units for good. Both ask first.
- **Process turn**, for the game's creator only: resolve the phase now.

If your power is out of the game (conceded or eliminated) the page says so and drops the
order panel, the draw vote, quit and concede and the message form: you can still follow the game.
Deadlines are proposed and voted on in the bot (**⏰ Deadline** in the game menu), not here.

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
- The map shows the board (**Board**), the orders you have entered (**Orders**), or the last
  resolution (**Last resolution**), and **What happened in ...** lists the results.
- **Step back** undoes the last resolution; **Start over** returns to where you began.

Nothing in the sandbox affects the real game, and nothing is saved: leaving the page ends it.

## Link Telegram

1. In the browser: **Link Telegram → Generate link code**.
2. In Telegram, send `/link <code>` to the bot.

Both clients now act as the same account, and the **Link Telegram** button becomes inactive
with "You are already linked". To unlink, open `/link-telegram` directly; you can re-link
later with a new code.

If you played through Telegram before registering on the web, your Telegram already has an
account (with your games). Linking then moves your web email and password onto that account
and removes the new, empty web one: log in again in the browser and your games are there.
That only happens while the web account is empty (no games joined, no messages); otherwise
the bot refuses, so nothing is ever merged away.

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
