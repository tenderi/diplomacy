# Fix Plan — Open Work

> **This file is the single source of truth for what to work on next, and it holds open
> work only.** Read it top to bottom, then continue at the first unchecked task of the
> highest-priority track.
>
> - Check off tasks (`[x]`) in the same commit as the work that completes them.
> - Keep **Status** below current.
> - Newly discovered work becomes a new unchecked task (or a new track) here — never done
>   silently.
> - **When a track completes, delete its section.** The commit message and the pull request
>   carry the write-up (what was wrong, what changed, the evidence); `git log` is the
>   history. Track letters run in sequence; the next free one is **BR**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-23. `v3.0.145` did BQ3: the game page refreshes the turn status right after a submission and re-fetches the game and order status every 30 s while the tab is visible (paused when hidden, refreshed on becoming visible, never overlapping, state replaced only when it changed). `v3.0.144` planned Track BQ (a phone-sized sweep of the web UI). `v3.0.143` did BP2: the scheduler spends a deadline that passed at a table with empty seats only if it is still the deadline (and phase) it saw, so a deadline armed by the last seat filling meanwhile is kept and no "waits for a full table" notice goes out. Track BP is done and removed. `v3.0.142` did BP1: a power that orders fewer builds than it is owed is told (DM and group post) how many were waived, unless it waived them itself. `v3.0.141` planned Track BP (two review notes: the implicit waive of a partial build, and the empty-seat deadline skip writing over a freshly armed deadline) and checked off F3's access-log count. `v3.0.140` did BO3: an order naming a fleet on a split coast without its coast (`F STP - BOT`) is stored, resolved and shown with the coast the fleet stands on (`F STP/SC - BOT`); Track BO is done and removed. `v3.0.139` did BO2 and BO4: builds waived for want of orders are told to the power and the group, the adjustment DM names the free home centres, and an unordered retreat disband no longer says "civil disorder". `v3.0.138` did BO1: a replace submission refused in full leaves the power's earlier orders in place (Track BO holds the other play-through findings). `v3.0.137` did BN6: the deadline scheduler re-checks a game's phase and deadline before processing it and passes the phase it saw to `process_turn`, so a game advanced (or a deadline extended) after the scheduler's read is no longer adjudicated with no orders. `v3.0.136` did BN2: the 10-minute deadline reminder is remembered in `games.reminded_deadline`, so a restart or a second worker no longer re-sends it. `v3.0.135` did BN4: an anonymous game's public `/state` no longer carries `created_by_user_id` (the web reads `is_creator` from `/users/me/games`). `v3.0.134` planned Track BN (spec-vs-code audit) and did BN1 (a deadline scheduler that loses the processing race to another worker no longer overwrites the deadline that worker armed for the new phase) and BN3 (the notification matrix lists the group post for a deadline change); Track BL is done and removed. `v3.0.132` did BL5: `POST /games/{id}/deadline` refuses a deadline at or before now with a 422, and a processed movement turn tells players (DM and group) which vacant seats' units held. `v3.0.131` did BM1: Pillow 13 (`pip-audit` reported 8 CVEs against 12.3.0, all fixed in 13.0.0); rendered boards are byte-identical. `v3.0.130`: a button that redraws its message unchanged (Telegram "message is not modified") no longer logs an error, alerts the maintainer and apologises to the player. `v3.0.129` did BL7: a game that ends with no winners sends
  DAIDE clients a bare `DRW`. `v3.0.128` did issue #242: the web header shows the nickname
  (or "Set a nickname"), the game view offers the form to a seated player without one, and the
  bot's private `/players` tells the caller how to set one. `v3.0.127` did BL6: a processed turn that leaves one power
  (or none) ends the game, as a concession already did, and the last powers conceding together
  end it with no winners; a turn that ends a game refreshes every player's cached game list
  (BL5's cache point). `v3.0.126` did BL3: a vacant seat's draw vote stays required but
  the quit announcement and draw tallies name it and how to fill it, and quit on a finished game
  is a 409. `v3.0.125` did BL1 and BL2: orders, draw votes and
  concessions are a 409 `seats_unfilled` until the game starts, an eliminated power can't
  concede again, vote, send press or have its seat retaken, and a concession that leaves one
  power ends the game with it as the winner. `v3.0.124` did BK1 (Track BK, now removed): profiling showed the
  cold-render cost was the footer's and overlays' full-canvas 3x LANCZOS downscale, not the
  tinting; it now resizes only the drawn window (a cold start-board render 0.93 s -> 0.52 s,
  pixel-identical). `v3.0.122` did BL4 (bot `/concede`). `v3.0.120` did part 2 of issue #227: the bot sends a turn
  map it already uploaded by Telegram `file_id`. Part 1 (rasterise the base once) was measured
  and not worth it. `v3.0.119` made the
  container healthchecks cheap (issue #226). `v3.0.118` did issue #225: the bot long-polls
  `GET /bot/outbox?wait=25` instead of polling every 3 s, and healthy health checks and
  empty polls are dropped from the API's access log (F3 has the production check). Track BJ (retreat/adjustment play-through findings) is
  done and removed: `v3.0.113` did BJ1 (bounced and unordered retreat disbands are marked and
  announced), `v3.0.115` BJ2 (a unit with no retreat needs no order), `v3.0.114` BJ3 and BJ4.
  Track BI (concurrency follow-ups from BH3) is done and
  removed: `v3.0.111` made a concession a locked read-modify-write of the board (two powers
  conceding at once both leave it) and replaced `tests/test_idempotency.py`'s 5xx test, which
  never reached the middleware's 5xx check, with an honest raised-exception test. Track BH (tests for untested guards in risky code) is
  done and removed. `v3.0.110` did BH3 (process-turn lock, draw vote and concession on a
  game that ended meanwhile, adjudication retries exhausted, idempotency's no-store rules,
  join of a finished game; a concession loaded before a draw committed no longer overwrites
  the finished game with an active board, it is the game-over 409). `v3.0.109` did BH4
  (`require_bot_or_user` loads the token's user and refuses an inactive or deleted one with
  401 "User not found or inactive"). `v3.0.107` did BH2 (scheduler, deadline-proposal and replace-power guards; a
  withdraw on a game gone under the lock is now a proposal error, not a bare `ValueError`).
  `v3.0.106` did BH1 (snapshot restore and inactive users are pinned; `/auth/token`
  no longer issues tokens to an inactive account, and a snapshot whose `state_json` is not
  an object is the deliberate "Corrupt snapshot" 500, not a traceback). Track BG (play-through findings in the orders API) is done and
  removed (`v3.0.104` did BG3: a superseded order in one request is `success: true` with
  `superseded_by`; `v3.0.103` did BG4: a retreat-phase move with the wrong unit letter names the real kind;
  `v3.0.102` did BG1: a future `client_timestamp` is refused with 422; BG2: order writes on a
  missing game are 404 "Game N not found"); Track BF is done and removed. `v3.0.100` did BF5 (the rest of `telegram_bot/`: command handlers
  catch `requests.RequestException` / `TelegramError` / `sqlite3.Error`; the channel-post formatters
  no longer turn a bug into an error post; the notification and replay loops and `alerting` are the
  logged boundaries; in the outbox poll a Telegram error that is not about one chat retries, and a
  malformed row is acked failed instead of wedging the batch). `v3.0.99` did BF3 (the other API routes, `persistence/database.py`, the
  idempotency middleware and the response cache: the 500-wrapping catches are gone, storage
  catches are `SQLAlchemyError`, notification catches are logged boundaries). `v3.0.98` did
  BF4 (the bot's order commands catch `requests.RequestException` / `TelegramError`, not
  `Exception`; `_on_handler_error` apologises). `v3.0.97` did BF2 (`routes/games.py`: the 500-wrapping
  catches are gone, so a bug is a plain 500 with a traceback; notification catches are
  logged boundaries). `v3.0.96` did BF1 (ruff's BLE001 is on, with a
  per-file ignore list that Track BF empties; the scheduler, housekeeping, notification and
  startup boundaries in `shared.py` and `_api_module.py` now log tracebacks). `v3.0.95` did
  BD11 (DAIDE `SUB` / `NOT (SUB)` invalidate the cached game reads), completing Track BD.
  `v3.0.94` did BD10 (a draw completed over HTTP sends `DRW` to the connected DAIDE
  sessions, once). `v3.0.93` did BE3 (a retreat written as a move names the
  single legal option and says why; "has no build to make: 3 supply centres, 3 units" no
  longer says it twice). `v3.0.92` did BE4 (API edge cases), completing Track BE.
  `v3.0.91` did #199 (`/status` in a group also lists each power's seat, as `/players`
  does). `v3.0.90` did BE2 (a finished game offers no legal
  orders, `draw_vote_status` reports the draw that ended it, and the 409 text is
  capitalized and fitted to the action). `v3.0.88` did BC5 and, with it, BC6, completing Track
  BC: the resolver records every read of a guess, convoys join dependency cycles, and
  the Szykman backup disrupts the cycle's convoys and resolves the cycle again, so
  6.F.16/17/18/23/24 pass (154/154 DATC green) and every case gives one result under
  any submission order. `v3.0.84` did BD8 (a draw vote cast over DAIDE, its
  withdrawal and a draw it completes notify the Telegram players and the group exactly as
  an HTTP vote does: both run `api.shared.after_draw_vote`). `v3.0.83` did BD9 (the web results list says a
  civil-disorder disband was not ordered). `v3.0.85` (merged before `v3.0.83`) fixed a
  test that hardcoded a date and broke `main` once it aged past 30 days. `v3.0.82` did BD5 (a civil-disorder disband is announced
  to its power and the group: the engine marks those results `civil_disorder`).
  `v3.0.81` did BD6 (a merged build or disband past the
  count names the stored one it replaced, in the bot's reply and in a queued order's
  delivery DM). `v3.0.80` did BD4 (a player's own DMs say "you": the
  turn-processed DM, the solo winner, a draw's sharers, a deadline proposal's proposer).
  `v3.0.78` removed the finished Track BB. `v3.0.77` did BC4 (an own-power convoy order shows
  intent, swap or not: 6.G.11 passes, 149/154 DATC green). `v3.0.76` did BD2, BD3 and BD7;
  `v3.0.75` did BC3b. `v3.0.74` did BC3 (a non-adjacent army move is legal
  when the board allows a convoy, ordered or not, and a fleet's support of a convoyed
  move every route needs is `VOID`: 6.D.8 passes, 148/154 DATC green). `v3.0.73` planned
  Track BD (play-through wording fixes) and did BD1 (a draw-ended game says it was a draw
  and names who shares it; withdrawing a draw vote is announced; the vote notice says
  votes last for the phase). `v3.0.71` fixed a rules bug found in a play-through: a
  unit could retreat into a province that was left empty by a standoff, as long as that
  province had a unit in it when the turn began. `v3.0.70` did BC2 (a convoy order whose
  fleet is on no possible route of sea fleets is `VOID` and shows no intent: 6.G.7 passes,
  147/154 DATC green). `v3.0.69` did BB6b (a rumour's DM reaches its sender
  too, byte-identical to everyone else's, as the maintainer chose in #173). `v3.0.68` did
  BC1 (a support for an attack on one's own unit is `VOID` unless it was decisive against
  another attacker: 6.E.8 and 6.E.10 pass, 146/154 DATC green). `v3.0.67` planned Track BC
  (the DATC `xfail`s, six milestones). `v3.0.64` (merged after `v3.0.65` and `v3.0.66`) did BB2b
  (the web game page shows a player the game's Telegram group with an Unlink button, or a
  "Link a Telegram group" link to `t.me/<bot>?startgroup=link_<id>`; `GET /games/{id}/channel`
  names the bot; Unlink asks first, and a web unlink tells the group). `v3.0.66` moved `source-map-js` past a high advisory. `v3.0.65` did BB6a
  (an unknown power in a private message is named as such, `/messages` shows short UTC
  times, the group's orders map reads "orders and results").
  `v3.0.63` did BA6 (the maintainer chose a full table
  in #145, so no turn is processed, by hand, by auto-process or at a deadline, while a
  power is neither seated nor a dummy; Track BA is complete). `v3.0.62` did BB9 and BB2a (a
  game is linked to a group only from inside it -- the link endpoint is bot or admin only,
  `/link_channel` no longer takes a chat id, `/newgame` creates and links in one call or
  creates nothing, and `/start link_<id>` in a group links the game for a player of it).
  `v3.0.61` did BB7 (`/viewmap`, `/map` and `/players`
  typed in a group answer for the group's game, and an id for another game is refused
  there). `v3.0.59` did BB1 (a Telegram group has at most one
  game, only a player of the game it replaces may move the link, and `/status` in a group
  answers for the group's game without naming the caller's power). `v3.0.58` did BB8 (a
  long message log is trimmed to fit one Telegram message); `v3.0.56` did BB3 and BB4 (the
  bot's `/messages` shows private messages again; blank or oversized messages are a 400);
  `v3.0.55` did BB5 (the group guard leaves other bots' commands alone). `v3.0.49`
  finished BA7; `v3.0.47` moved the frontend to react-router 7 (AZ2).
- `v3.0.51`/`v3.0.52` added rumours (anonymous broadcasts, #157) to the API, the bot and
  the web composer.
- **Track AZ** (frontend major dependency upgrades) is in progress: AZ1 and AZ2 done, AZ3 open.
  **Track F** (a human playing the game end to end, and host chores) is the maintainer's.

---

# Track BN — spec-vs-code audit (2026-10-21)

- [x] **BN1** Scheduler race: in `process_due_deadlines` (`server/api/shared.py`) the
  `except StaleGameError` branch fell through to the "processing failed: the deadline is
  still spent" write, so when another worker's processing committed inside
  `process_turn`'s own read-to-save window, the scheduler overwrote the deadline already
  armed for the new phase (with the next weekly slot, or None). It now skips the game.
  (A commit *before* `process_turn` loaded the game raised nothing: that is BN6.)
- [x] **BN2** The 10-minute deadline reminder was tracked in the in-memory `reminder_sent`
  dict (`shared.py`), so an API restart or deploy inside the window re-sent it to every
  player. It is now `games.reminded_deadline`, claimed by one conditional update.
- [x] **BN3** architecture.md's notification matrix said "Deadline set or cleared" has no
  channel post, but `routes/games.py` `set_deadline` posts `⏰ {text}` to the game group.
  The row now says so.
- [x] **BN4** `GameService.view()` returns `created_by_user_id` on the unauthenticated
  `GET /games/{id}/state`, also for anonymous games, and data_spec's view shape doesn't
  list it. Null it for anonymous games (check how the frontend uses it first) and document it.
- [x] **BN6** The deadline scheduler could adjudicate a phase nobody had had a chance to
  order for. `process_due_deadlines` reads every active game once, then processes them one
  by one, seconds apart; a game processed meanwhile by another path (manual, auto-process)
  was then processed again from the stale row, and `process_turn` adjudicated the phase it
  freshly loaded, so the new phase ran with every unit holding. The same went for a
  deadline pushed back within the phase. The scheduler now re-reads the game and skips it
  unless it is still in the phase it saw with a deadline still due, and passes that phase
  to `GameService.process_turn(expected_phase_code=...)`, which raises `StaleGameError`
  if the stored phase differs.
- [ ] **BN5** (maintainer decision) After quit and replace, the new holder of a power reads
  every earlier private message sent to that power (`routes/messages.py` filters by
  `recipient_power`, not by user). Decide whether that is intended.

---

# Track BQ — Web UI on a phone (sweep at 390x844, 2026-10-23)

- [ ] **BQ1** Choosing an order type silently picks the first target (`OrderEntry.tsx`
  `onValueChange` sets `opts[0]`): "Move" for F EDI is already `CLY`, "Support" is already
  some support, and nothing shows it is unconfirmed, so a player can submit an order they
  never chose. Start with no target ("Choose target") and refuse Submit while a row has a
  type but no target.
- [ ] **BQ2** A unit with no order shows a blank "Order type" and nothing says it holds.
  Label it "No order (holds)" (or default to Hold) in `OrderEntry.tsx`.
- [x] **BQ3** The turn status goes stale: after "Orders submitted" the card still says
  "You still need to submit orders" and "0/1 powers have submitted" until a reload, and
  another player's submission or a processed turn never appears (`GameView.tsx`:
  `orders_status` is fetched only on `[gameId, status, phase]`, nothing polls). Refresh it
  after a submission and poll the game while the page is visible.
- [ ] **BQ4** The map on a phone: "Click to enlarge" shows only on hover, so touch users
  never see it; the viewer opens at 21% with no fit-to-width start, its toolbar wraps
  with Open PNG and × on a second row, and page text shows through behind the toolbar
  (`MapViewer.tsx`).
- [ ] **BQ5** Order targets are bare codes (`CLY`, `NTH`); support options don't say whose
  unit. Show "NTH – North Sea" (`OrderEntry.tsx` `targetLabel`).
- [ ] **BQ6** Order entry sits about five screens below the map on a phone (turn status,
  players, Telegram group, draw vote, leave, process all come first). Move orders up or
  add a sticky shortcut (`GameView.tsx`).
- [ ] **BQ7** Small things: tap targets of 28 px (nav, tabs) and 13 px checkboxes; toasts
  cover the header; a "Function components cannot be given refs" warning from
  `ui/button.tsx` inside `AlertDialogTrigger` on every game page.

---

# Track F — Manual acceptance and host chores (maintainer)

No automated test spans a real human playing a real game: it needs a live bot token and a
human at a Telegram client, so this cannot be delegated to an agent. Every phase has
automated coverage; what is unverified is whether the whole thing is *pleasant and
coherent* to use.

## F1 — End-to-end play-through, both clients

- [ ] Create a game, fill 7 powers (dummies are fine); `/map` returns a PNG in Telegram.
- [ ] Order a deliberate dislodgement (A PAR–BUR supported, vs. A MUN–BUR); process.
- [ ] Phase `S1901R`: the browser shows retreat options for the dislodged unit only; the
      bot's order walk offers retreats. Submit one, process — it takes effect.
- [ ] Play to `W1901A` with a captured centre. Both clients show exactly the builds owed
      (capped at the free home centres) with real home-centre options, and a power with
      nothing owed shows none. Submit a build, process — the unit appears on the map.
- [ ] In a Telegram group game, each processed turn posts the orders map and the result map.
- [ ] **Done when:** every box above is checked. A defect found becomes a new track here.

## F2 — Judgement pass on the web game screen

- [ ] Play the F1 game in the browser and judge it as a *player*: is the phase state
      unmistakable, does "what happened last turn" answer the question a player asks, is the
      mobile layout usable on a real phone? The automated tests prove the page works, not
      that it is good.
- [ ] **Done when:** the maintainer's opinion is recorded here. Complaints become tasks;
      "it's fine" is a valid outcome.

## F3 — Host chores

- [ ] Exercise the bot's queue for real: `docker compose stop diplomacy_api`, send `/order`
      and `/message` from Telegram, check `/queue`, `docker compose start diplomacy_api`,
      confirm the delivered reports arrive and the message shows its original time.
- [ ] Stop the old game stack on the home server (`kattotuuletin.local`:
      `cd ~/diplomacy/new_implementation && docker compose down`; keep its `pg_data` volume
      until sure — it held no games). The tunnel and p2p's stack there are not ours.
- [x] After the `v3.0.118` deploy (issue #225), count the API's access-log lines over an
      idle hour (2026-10-21: 0 lines in the idle hour) (`docker compose logs --since 1h diplomacy_api | wc -l`). Before: 1,315
      lines/hour, 1,195 of them `/bot/outbox` polls; the issue's target is at least 90% fewer.
- [ ] Delete the unused `DIPLOMACY_BOT_SECRET` repository secret
      (`gh secret delete DIPLOMACY_BOT_SECRET -R tenderi/diplomacy`); nothing reads it.

# Track AZ — Frontend major dependency upgrades (proposed)

After `v3.0.31` (in-range `npm audit fix`), `npm audit` in `frontend/` still reports 8
findings (5 moderate, 1 high, 2 critical), each fixable only by a major upgrade:

- **vite 5 → 6.4.3+** (high; esbuild ≤0.24.2 dev-server request forgery, `.map` path
  traversal, Windows `server.fs.deny` bypass). Dev-server only; the production image ships
  static files built by vite, not vite itself.
- **vitest / @vitest/coverage-v8 2 → 4.1.11+** (critical; Vitest UI server file read,
  `@vitest/mocker` path traversal). Test tooling only; we never run the Vitest UI server.
- **react-router-dom 6 → 7.17.1+** (moderate; open redirect via a backslash in `<Link>` /
  `useNavigate`, SSR `deserializeErrors`). No fix on 6.x. The app navigates only to fixed
  paths and does no SSR, so neither is reachable today.

- [x] AZ1 — vite 6+ with vitest 4+ (`@vitejs/plugin-react` to match); frontend gates and
      coverage thresholds green, `npm run dev` proxy to the API still works.
- [x] AZ2 — react-router 7 (follow its v6→v7 migration guide; the future flags first).
      `react-router-dom` dropped; everything imports from `react-router`.
- [ ] AZ3 — **`braces` (high, every version: stack-exhaustion DoS on deeply nested
      patterns)**, advisory published after AZ was written, with no fixed release yet. It
      reaches us through `tailwindcss` 3 (via `chokidar`, `fast-glob`, `micromatch`) and the
      `shadcn` CLI (via `fast-glob`, `ts-morph`): all 8 findings left after AZ2. Both
      are build/dev tooling and parse only our own globs. `npm audit` proposes tailwindcss 4
      (a config rewrite) and a shadcn downgrade to 1.0.0; neither removes `braces` until
      `braces` itself ships a fix. Recheck then, before taking on tailwind 4. Since
      2026-10-06 tailwindcss 3 also pulls a vulnerable `postcss-selector-parser` (<7.1.6,
      moderate, quadratic selector parsing) through `postcss-nested`: again build tooling
      over our own CSS, fixed only by tailwind 4. That makes 11 findings, all from these two.
- [ ] **Done when:** `npm audit` in `frontend/` reports 0 vulnerabilities.

---

## Out of scope

- Tournaments, Discord, observer/spectator mode, AI-powered analysis. `tournaments.py`,
  `discord_bot/`, `run_discord_bot.py` and the spectator routes are kept for backward
  compatibility: don't extend, don't delete.
- An interactive map component, animation, or a new layout engine.
- Map variants beyond `standard`.
- An admin web page: the host is administered over SSH (`docs/DEPLOYMENT.md`).
- Game options beyond the standard rules: engine rule switches (`BUILD_ANY`, `HOLD_WIN`,
  `SHARED_VICTORY`, …), no-press or public-press games, several powers per player (dummies
  cover small tables), custom starting positions (snapshot restore and saved-game import
  suffice).
- **DAIDE press-content parsing** (`ALY`/`XDO`/`PRP` beyond syntax-checked opaque
  forwarding) — a permanent design decision (`architecture.md`), not a gap.
