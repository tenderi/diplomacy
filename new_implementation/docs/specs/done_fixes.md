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

**Open question for the maintainer (not done):** the web client still lets any seated player
press "Process turn". Making it creator-only too would be consistent, but changes web
behaviour and needs the view to say who the creator is.



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
