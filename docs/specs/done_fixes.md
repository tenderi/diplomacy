---

# Track AF — The documentation site (maintainer request, 2026-09-24) — **done, `v3.0.3`**

- [x] `docs/` published as a website at `https://<DOCS_DOMAIN>` (production
  `diplomacy-docs.xn--jalluthti-02a.fi`): `mkdocs.yml` (Material for MkDocs 9.x, pinned to
  MkDocs 1.x -- 2.0 drops the plugin/theme system), a landing page (`docs/index.md`),
  navigation Play / Run it / Design / Project. Built with `--strict` in
  `docker/docs.Dockerfile`, served by the `diplomacy_docs` nginx container through Caddy
  (its own certificate and security headers; `script-src 'unsafe-inline'` for the docs
  site only, which Material's inline page scripts need; no Google Fonts).
- [x] Caddy reads an *empty* site address as broken config and applies a `{$VAR:default}`
  only when the variable is unset, so compose passes `http://docs.invalid` when
  `DOCS_DOMAIN` is blank (a plain-HTTP name nobody uses; never a certificate request).
- [x] Links out of `docs/` (to `pyproject.toml`, the frontend README, source directories)
  became GitHub URLs; two in `testing_and_validation.md` had pointed above the repository
  root since the flatten.
- [x] The README and the bot's `/help` link to the site.

**Evidence:** strict build clean; image built and smoke-tested on the VPS (pages, 404),
`caddy validate` with and without `DOCS_DOMAIN`; `tests/test_deployment_infrastructure.py`.

---

# Track AE — Play in a Telegram group; the new player guide (maintainer request, 2026-09-24) — **done, `v3.0.2`**

Before the beta announcement. The maintainer's picture ("add the bot to a group; orders
in private; the bot posts announcements and broadcasts") existed only in part, behind
`/link_channel <game_id> <chat_id>` with an id from a third-party bot, and with holes:

- [x] **Orders could be entered in the group.** Every command worked in any chat, so
  `/orderall` in a group showed that player's order menu to everyone. Now a
  handler-group -1 guard (`app.group_command_guard`) answers private commands in a group
  with a link to a private chat; only `GROUP_COMMANDS` pass. Callback buttons pressed in a
  group only raise an alert. Group posts carry **link** buttons
  (`t.me/<bot>?start=orders_N`, `payload.dm_start`), never callbacks; `/start <payload>`
  (`join_N`, `orders_N`, `game_N`) continues in the private chat.
- [x] **`/newgame`, `/linkgroup`, `/unlinkgroup`, sent in the group:** create a game for
  the group (sender = creator, auto-process on) or attach/detach one, using the chat's own
  id. A group-scoped "/" menu (`BotCommandScopeAllGroupChats`).
- [x] **Only a group's members see its games** (maintainer, same day): `GET /games` lists
  group games only to the bot (with `channel_id`); the bot shows them only to members
  (`bot.get_chat_member`); joining one is refused unless through the bot (or by its
  creator), and the bot checks membership on every join path.
- [x] **Security holes in the channel routes:** unlink, settings and the map / broadcast /
  thread / timeline / dashboard / results posts had **no auth**; link needed any login.
  All now need the bot secret, the admin token or a player seated in the game
  (`require_game_player_or_bot`); so does reading a game's group.
- [x] **`/channel_settings` never worked** (the bot POSTed, the route was PUT-only): the route
  accepts both. **`/unlink_channel`** called the API without the bot secret: `api_delete`.
- [x] **Group announcements** added: deadline changes, the 10-minute reminder, and "game
  is full" (`api.shared.post_to_game_group`), next to the existing turn results + map and
  broadcasts.
- [x] **`docs/NEW_USER_GUIDE.md`** for beta players, linked from the README and `/help`.

**Evidence:** `tests/test_telegram_groups.py` (guard, button guard, `/newgame`,
membership filtering and join refusal, deep links, link buttons),
`tests/test_group_games_api.py` (hidden listing, join via bot only, guarded routes,
deadline and turn posts to the group).

---

# Track AD — Flat repository, README, and the license (maintainer request, 2026-09-24) — **done, `v3.0.1`**

- [x] **Everything at the root.** `new_implementation/` moved up with `git mv` (history
  follows); paths fixed in CI (`test.yml`), the deploy workflow (`~/diplomacy`), docs,
  CLAUDE.md, `.gitignore`, `.vscode`, `.cursor` rules. A stray empty root
  `package-lock.json` removed; `VERSION` said 2.0.0, now 3.0.0.
- [x] **Production cutover without data loss.** Compose had named the project (and so the
  volumes) after the directory. `docker-compose.yml` now pins `name: diplomacy` and the
  volumes' old names (tested on the VPS: a project reuses a volume labelled for another);
  `upgrade.sh` stops the old `new_implementation-*` containers first (two Postgres
  containers must never share the data volume); the deploy step moves the host `.env` up
  before anything can write a fresh one (a new `.env` would mint a POSTGRES_PASSWORD the
  database doesn't know) -- covered by an executed deploy-step test.
- [x] **Root README.md** rewritten for the flat layout: what it is, where to play, layout,
  development, deployment, docs, license.
- [x] **License.** Upstream diplomacy/diplomacy is AGPL-3.0-or-later (file headers: "either
  version 3 ... or (at your option) any later version"). This project was a fork of it, and
  its `maps/standard.map` (201 of 212 lines identical to upstream's) and
  `maps/standard.svg` (733 of 884) are adapted from upstream files, so it is a derivative
  work: `LICENSE` (upstream's AGPL-3.0 text) added, `license = "AGPL-3.0-or-later"` in
  `pyproject.toml` and `frontend/package.json`, attribution in the README. For section 13
  (network use) the web footer and the bot's `/help` link to the source.
- [x] **Missing tag `v2.7.68`** -- cited by CLAUDE.md and ~20 files as `git show
  v2.7.68:old_implementation/...` -- created on `8457eb0` (the v2.7.68 release commit).

---

# Track AC — Forgot password that actually delivers (maintainer request, 2026-09-24) — **done, `v2.7.111`**

The web app already had *Forgot password?* (login page → `/forgot-password` →
`/reset-password`) and both API routes, but in production it could never deliver: no SMTP
is configured on the VPS, so every reset link was created and silently dropped.

- [x] **Telegram first, email as the fallback** (maintainer's call): an account linked to
  Telegram gets the link from the bot through the durable outbox, and no email; email
  (SMTP) only for an account with no linked Telegram, or if the Telegram message could
  not be queued. With neither, the API logs a warning naming the address.
- [x] **Rate limits** where there were none (every request can message someone): 10 per IP
  per hour → 429; 3 links per address per hour, beyond which the reply is identical but
  nothing is sent (a 429 there would reveal that the address has an account).
- [x] The SMTP send's `except Exception` narrowed to `(smtplib.SMTPException, OSError)`.
- [x] Page copy says where the link goes.

**Evidence:** `tests/test_password_reset_delivery.py` (Telegram delivery and a full reset
with the delivered token, identical replies for unknown addresses, Telegram-not-email for
linked accounts, email for unlinked ones and when Telegram can't be queued, SMTP failure
not an error, both limits). Open: email for accounts without Telegram needs an SMTP
provider in the VPS `.env` (maintainer's choice).

---

# Track AB — Server hardening (maintainer request, 2026-09-24) — **done, `v2.7.110`**

Right after the site went public (F4). An audit of the VPS and the public surface found a
sound base -- key-only SSH, ufw deny-by-default, unattended security updates, API and bot
running as non-root -- and these gaps, all closed:

- [x] **Spoofable client IP (fixed in `v2.7.108`, recorded here):** nginx appended to a
  client's own `X-Forwarded-For` and uvicorn reads the first entry.
- [x] **Secrets compared with `==`** at ~20 sites (admin token, bot secret, and the
  idempotency middleware): all now `hmac.compare_digest` via `api.shared.is_admin_token` /
  `is_bot_secret`.
- [x] **Swagger UI, ReDoc and the OpenAPI schema were public** at `/api/docs`, `/api/redoc`,
  `/api/openapi.json`: off in production (`DIPLOMACY_API_DOCS=0`).
- [x] **No browser security headers:** Caddy now sends HSTS, a strict CSP (`script-src
  'self'`; the built SPA has no inline script and no third-party origin), `nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, and drops `Server`/`Via`;
  nginx `server_tokens off`.
- [x] **Containers:** `no-new-privileges` on every service; `cap_drop: ALL` on the API and
  the bot.
- [x] **Host** (`harden_host.sh`, run by `install.sh`): sshd drop-in (X11 and agent
  forwarding off, `MaxAuthTries 3`, `LoginGraceTime 30`, idle sessions dropped; validated
  with `sshd -t` before reload), `restrict` on the GitHub Actions deploy key, fail2ban for
  sshd (856 failed SSH attempts in the 24 hours before), and unattended-upgrades rebooting
  at 04:30 UTC when needed (a reboot had been pending).

Left as they are, deliberately: WireGuard `wg0`/UDP 33500 (the p2p bot on this host reaches
its agent through it); `/api/dashboard`'s HTML page (every data route behind it needs the
admin token); `/.env` answering 200 (that is the SPA's `index.html` fallback, not a file).

**Evidence:** `tests/test_deployment_infrastructure.py` (hardening script contents,
`no-new-privileges` on all five services, headers, docs off); full suite 1774 passed.

---

# Track AA — Telegram user flows, streamlined (maintainer request, 2026-09-24)

## Why this track exists

Asked whether the Telegram flows were actually good, a review found that the parts worked
but the paths between them were poor:

1. **You could not act from a notification.** "Turn processed" was plain text; the player
   had to remember `/orderall` (the bot could already render `payload.buttons`, but only for
   channel posts, and the API never sent any).
2. **A game id was needed as soon as you were in two games**, on almost every command.
3. **Button menus dropped the game they were opened from.** "🎯 Submit Interactive Orders"
   knew the game id and called `selectunit(update, context)` without it — an error for anyone
   in two games — and opened the one-unit picker, not the walk through every unit.
4. **Two navigation systems that never met**: an eight-key reply keyboard of global menus and
   43 commands, neither organised around a game.
5. **Duplicated or misleading commands**: `/order` vs `/orders` differed only in whether the
   id was required; `/wait` (queue for a new game) sat next to `/notready` (wait flag);
   `/deadline` had five subcommands; any member could `/processturn`, turning everyone else's
   unsent orders into holds.
6. **Onboarding**: a separate Register step; a welcome advertising "New Features: convoy
   chain validation"; a private game's password typeable only as a command argument.
7. **The demo said something false**: "other powers are AI-controlled (they won't move)" —
   six fake users who never ordered.

Found on the way: the queue buttons (`join_waiting_list`) called `wait()`, which only handled
a command's `message` — a button press did nothing at all.

## AA1 — Game menu, current game, notification buttons, and the rest — **done, `v2.7.106`**

- [x] **Notification buttons.** `api.shared.game_buttons(game_id)` → 📝 Enter orders /
  🗺 Map / 🎮 Game menu as `g|{id}|{action}|n`; `notify_user`/`notify_players` take
  `buttons=`, stored as `payload.buttons`. On turn processed (🗺 Final map when it ended),
  the 10-minute reminder, "you joined", "game is full" (both paths) and the queue's "game
  created". The bot renders DM buttons too (`notifications._inline_keyboard`).
- [x] **Game menu** (`telegram_bot/hub.py`). `/games` lists games as buttons (straight to the
  menu with one game); the menu is `status_text` plus Order all units / One unit / My orders
  (Clear, History) / Map / Messages / Deadline / ready-or-wait (auto-process games) /
  Process turn now (creator only). Every button carries its game id. `|n` answers in a new
  message so the notification stays readable. The old per-game callbacks (`orders_menu_*`,
  `submit_orders_*`, `view_orders_*`, `clear_orders_*`, `order_history_*`, `view_messages_*`,
  `demo_orders_*`) route into it, since they live on under old messages.
- [x] **Current game.** Stored per player in the bot's SQLite (`current_game` table), set
  whenever a game is opened, named, joined or tapped from a notification.
  `resolve_game_and_power` falls back to it for a multi-game player; `/game <id>` switches.
- [x] **Typed replies.** 💬 Messages → tap a power (or 📣 Everyone) → type. A private game's
  power buttons ask for the password as the next message and delete it. `/cancel` stops.
  Plain-text handling is private-chat only (the bot sits in linked channel groups).
- [x] **Commands.** `/orders` = `/order` (game id optional); `/findgame`, `/leavequeue`
  (`/wait`, `/unwait` kept as aliases); deadline votes are buttons (the typed forms still
  work); `/message`, `/broadcast`, `/messages`, `/viewmap`, `/processturn`,
  `/orderhistory` take an optional id. The "/" menu was re-curated.
- [x] **Early processing is the creator's.** `POST /games/{id}/process_turn` with the bot
  secret *and* a `telegram_id` (what the bot now sends) is allowed only for the game's
  creator, 403 otherwise. `/users/{id}/games` gained `is_creator`. A bare bot secret, the
  admin token and seated Bearer users (the web) are unchanged — see the open question below.
- [x] **Onboarding.** `/start` registers silently and shows three keys: 🎮 My games ·
  🎲 Find a game · ℹ️ Help (old labels still answered). Find a game = joinable games (not
  yours, not full, not demos, not finished), the queue, the demo. Joining and queueing
  register too. The queue commands work from buttons.
- [x] **Demo.** The player creates it (so is its creator), the other six are civil-disorder
  seats, auto-process is on, and `map_name="demo"` makes `GameService._demo_ai_orders` give
  every order-less dummy `engine.simple_ai` orders (seeded by game and phase; checked to
  round-trip format → parse over 40 phases) that land in `order_history`.

**Evidence:** `tests/test_telegram_hub.py` (16: current game, menu buttons per role, `|n`,
walk from a button, compose, deadline buttons, Find a game filtering, `/start`, DM buttons),
`tests/test_telegram_flows_api.py` (8: notification payload, creator-only processing,
`is_creator`, demo AI moving and recorded, determinism, non-demo dummies still hold), and a
password-join test in `tests/test_private_games_bot.py`. Full suite 1761 passed, 10 xfailed;
engine coverage 93.97%, total 75.02%.

**Open question for the maintainer:** the web client still let any seated player press
"Process turn". Answered "update the website as well" — AA2.

## AA2 — Early processing is the creator's on the web too — **done, `v2.7.107`**

- [x] `_authorize_process_turn`: a Bearer user must be the game's creator (seated or not);
  a seated non-creator gets the same 403 as a Telegram player. Bot secret and admin token
  unchanged; an ownerless (waiting-list) game is admin-only.
- [x] The view gains `created_by_user_id`; `GameView` shows the Process turn section only
  to the creator and tells other players when turns run instead.

**Evidence:** `tests/test_telegram_flows_api.py::TestEndingATurnEarlyOnTheWeb` (seated
non-creator 403 and the view names the creator; creator without a seat 200; ownerless game
admin-only), `GameView.test.tsx` (non-creator sees the explanation, not the button; the
creator's button still confirms before calling). Every existing web-processing test already
processed as the game's creator, so none changed behaviour.



---

# Track Z — Telegram order entry (maintainer report, 2026-09-24)

## Why this track exists

The maintainer played the demo game (game 1) as Germany through the bot, ordered all three
units, and only one moved. Nothing was wrong with adjudication: the only German order ever
stored was the last one entered.

## Z1 — Orders sent one at a time overwrote each other — **done, `v2.7.104`**

- [x] **Cause.** Every bot path posts to `POST /games/set_orders` — `/selectunit` one order
      per request, `/order` one message's worth — and `GameService.submit_orders` stored
      `pending[power] = <this request's orders>`. Each submission wiped the previous ones,
      while the bot replied "Submit more orders with /selectunit". (The legacy text-command
      `server.py` had merged, `existing + [order]`; the HTTP path never did.)
- [x] **Fix.** `set_orders` takes `merge` (the bot always sends `true`; the web client, which
      sends the full set, keeps replace). Merging keys orders by their unit's province (a
      build by its site): a new valid order replaces that unit's old one, an invalid one
      never displaces a good one, `WAIVE`s append.
- [x] **W10 knock-on.** Auto-processing counted a power as done once it had *any* order, so
      one-at-a-time entry would have run the turn after a player's first unit. It now waits
      until each power has ordered everything that must act (`GameService._orders_complete`:
      every unit / every dislodged unit / as many builds-waives-disbands as owed);
      `orders_status` gains `incomplete`, shown in `/status`. Holding needs an explicit `H`.
- Tests: `tests/test_order_merge.py` (5, incl. the demo scenario end to end); W10's tests now
      order every unit.

## Z2 — Two order-entry flows: all units, or one — **done, `v2.7.105`**

- [x] Maintainer's request: players usually order *all* their units, sometimes only some.
      **`/orderall [game]`** walks every unit that must act this phase (retreats: every
      dislodged unit; adjustments: each build/disband slot, with already-chosen builds taken
      off the list), one screen per unit with its legal orders — supports and convoys
      through the same sub-menus as `/selectunit` — plus ⬅️ Back, ⏭ Skip and ❌ Cancel, then
      a summary to **submit everything in one request** (merged, Z1) or start over. A
      skipped unit keeps any earlier order, else holds. If the turn was processed while the
      player was choosing, nothing is sent and they are told. **`/selectunit`** stays the
      one-order flow (sent at once) and now offers "📋 Order all units, one by one" at the top.
- [x] Mechanics: the walk lives in `user_data["order_walk"][game_id]`; while it exists, an
      `ord|` pick is recorded for the current step instead of submitted
      (`app.button_callback`), which is what lets the existing support/convoy sub-menus
      serve both flows. `/orderall` is in the "/" menu; help, demo help and
      `TELEGRAM_BOT_COMMANDS.md` updated.
- Tests: `tests/test_order_all_flow.py` (7, driven through the real callback router:
      full walk with skip/back, a support from the sub-menu, skipped units, turn moved on,
      cancel, adjustment slots, and `/selectunit` still sending at once).
