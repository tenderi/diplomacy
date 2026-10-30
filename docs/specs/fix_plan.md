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
>   history. Track letters run in sequence; the next free one is **CA**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-30. `v3.0.186` planned Track BZ (findings from an API play-through of game endings); BZ1 and BZ4 are in progress. `v3.0.185` did Track BY (done and removed): restoring a game from the archive in a phase that needs nobody processes it at once (BY2; `POST /games/import` reports `auto_processed`); BY1 was moot -- a seat its player quit keeps its row and counts as seated, so its deadline never stops and retaking it has nothing to re-arm (pinned by a test; the docstring that suggested otherwise now says so). `v3.0.184` did BX2 (Track BX done and removed): when processing a phase that needs nobody raises, the players and the group are told it could not be processed automatically and that the creator's ⚙️ Process turn now moves it (or when its deadline will), and the error alerts the maintainer (`shared.empty_phase_failed`); no fallback deadline is armed. It also planned Track BY. `v3.0.183` planned Track BX (the gaps a review found in BV2) and did BX1: a phase that becomes empty while it stands -- the only power owing a retreat, build or disband made a dummy or conceding, or the seat completing the table taken while only dummies owe -- is processed at once, whatever `auto_process` says (`shared.process_if_phase_needs_nobody`). `v3.0.182` did BV4 (Track BV done and removed): a join is a group post, not a DM to every seated player (the table is DMed when it fills), and an accepted army move to a non-adjacent province carries the note "needs a convoy: ...". `v3.0.180` did BV3: the set-deadline and proposal-passed notices read as the weekly schedule does ("... UTC (Mon 16:00 Europe/Helsinki)"), a deadline-processed movement turn names the seated powers that had not ordered ("their units held"), the disband DM says civil disorder picks the units with no order, and `process_due_deadlines`'s docstring no longer claims players are marked inactive. `v3.0.179` did BV2: a phase nobody has anything to order in (a retreat phase of trapped units only, an adjustment only dummies owe) is processed at once by every trigger (`after_turn_processed`), and its players get one DM, for the next phase, carrying the earlier lines. `v3.0.176` did BW1 (issue #254; Track BW, its only task, done): the turn-processed DM tells each player what the turn did to their own units, one line per unit ("A PAR - BUR bounced.", "F TRI was dislodged by A TYR (ITALY).", "A MUN held (no order).", "No orders, so F BRE, A MAR and A PAR held."), retreats and builds, and after a Fall turn "Centres: +BEL, -TRI (now 5)."; the resolution now marks `unordered` results and carries `centres`; a multi-line DM puts "Next deadline" on its own line; the group post is unchanged. `v3.0.177` closed AZ3 (issue #255): `npm audit` in `frontend/` reports 0 vulnerabilities (the `postcss-selector-parser` advisory no longer matches tailwind 3's copy), so Track AZ is done and removed; tailwind 4 is not needed for it. `v3.0.175` settled BN5 with the maintainer (issue #253): a player who takes a seat reads the power's earlier private press, as before, now documented in architecture.md; Track BN is done and removed. `v3.0.173` did BV1: every deadline the API returns is aware UTC (`+00:00`, via `shared.utc_iso`), the web parses it with `parseUtc` (the countdown was off by the viewer's UTC offset), and the game page's 30 s refresh refetches the deadline. `v3.0.172` planned Track BV (findings from an API play-through, Spring 1901 to Spring 1903; adjudication was correct throughout). `v3.0.171` did BU5: `tests/test_notify_after_commit.py` makes the notification raise in the quit, replace, deadline propose, vote, schedule and set, and restore routes and pins the normal 200 and the stored write, and pins `save_state` and `modify_state_json` on a missing game raising `ValueError("game <id> not found")` (each guard shown to fail when broken; no bug found). Track BU is done and removed. `v3.0.170` did BU3: `tests/test_deadline_scheduler_guards.py` drives single scheduler passes to pin that a naive deadline (and a naive `now`) is read as UTC, due at or after it and not a second before, that a game deleted or whose deadline was cleared after the scheduler's read is skipped while the next is processed, that one game raising spends its deadline without stopping the next, and that auto-processing stops for a game deleted mid-turn; no bug found. `v3.0.169` did BU2: `tests/test_vote_and_proposal_races.py` pins draw votes, concessions and deadline proposals under races (a turn processed meanwhile is the 409 with the repository's message, a game gone meanwhile is 404, a power that is out gets 409 for a draw vote or a second concession and 400 for a deadline proposal or vote, the only active power's proposal passes at once, an empty table decides nothing); no bug found. `v3.0.168` did BU1: `tests/test_route_auth_guards.py` pins the exact 401/403/404 of the group-join, auto-process, dummy-power, token-type and inactive-user guards (each shown to fail with its guard removed; no bug found). `v3.0.167` did BU4: tests pin the bot outbox's at-least-once delivery (a lost ack leaves the rows to be re-sent next poll) and the `channel_create_thread` row; no bug found. `v3.0.166` planned Track BU (tests for untested guards in risky server code, from a coverage sweep). `v3.0.165` did the wording nits from the v3.0.158 and v3.0.161 reviews (Track BT, done): a deadline proposal reads "a deadline of 8h, counted from when the proposal passes" (no article to get wrong), the bot prints proposal hours as "6h" and "1.5h", not "6.0h", and the 10-minute reminder's group post names the missing powers with `power_label` (nickname in a public game). `v3.0.164` did AZ5: vitest and @vitest/coverage-v8 4.1.12 and a regenerated shadcn tree clear every dev-tooling finding but the tailwind 3 chain, so `npm audit` shows 3 (AZ3). `v3.0.163` did AZ4: the unused `zod`, `react-hook-form` and `@hookform/resolvers` are gone from the frontend, so the production dependency audit is clean. Track BS is done and removed (`v3.0.158` did BS2 and BS4: a power that is out gets no turn DM, an elimination is announced once to the power and the group, and the 10-minute reminder goes only to powers still missing orders, with the phase and real minutes left). `v3.0.161` did BS7: a deadline proposal reads "a 48h deadline, counted from when the proposal passes", "No deadline is set" is its own paragraph naming /deadline, /status shows "Deadline: none set", help says Spring/Fall, quit and replace notices title-case the power. `v3.0.160` did BS3 and BS6: for a finished game `/status` leads with "Game ended: won by France" (or the draw's sharers) and drops the phase, order, wait and draw lines, and the order walk, the hub's deadline view and `/ready`/`/notready` answer "Game 1 has ended."; the bot says "Fall 1903 movement (F1903M)" for a phase (status, walk header, stale-walk notice, order history, the 409 for stale queued orders), and the creator's "Process turn" reply says what the caller's power owes next (nothing / orders / retreats / N builds / N disbands). `v3.0.159` did BS1 and BS5: the order walk says a skipped unit "is disbanded" in a retreat and gives the adjustment walk its own note (a skipped build is waived, a missing disband is chosen by the civil-disorder rule), the retreat DM adds "With no order it is disbanded.", and order confirmations read "Orders received:" with a "No order yet (holds): F NWG" line ("(disbanded)" in a retreat; builds/disbands still owed in an adjustment); the single-order button reply ("Order submitted:") and the queued-replay DM keep their own titles and carry no unordered line. `v3.0.158` did BS2 and BS4: a power that is out (eliminated or conceded) gets no turn DM, a power a turn eliminates is announced once to the table (DM and group, from `resolution.eliminated`), and the 10-minute reminder goes only to powers still owing orders, naming the phase and the real minutes left. `v3.0.157` planned Track BS (a play-through of the bot's and notifications' texts). Track BR is done and removed. `v3.0.156` did BR5: each message on the game page shows its phase and local time, messages newer than the viewer last saw (a per-game id in localStorage, set when the log scrolls into view) are marked NEW, a "Messages (N new)" jump link sits under the title, and the log follows order entry instead of closing the page. `v3.0.155` did BR7: a dislodged hold's gloss reads "Army Munich held", a build result keeps its coast ("Build fleet St Petersburg (south coast)"), and a support/convoy target reads "A YOR – Yorkshire (England) → BEL – Belgium". `v3.0.154` did BR8: the phone header is two rows (Logout beside the logo, the links under it), and logging in or registering lands on `/games`. `v3.0.153` did BR4: the adjustment panel says "2 builds: 6 centres, 4 units" (`legal_orders.adjustment` now carries `centers` and `units`), options read "Build fleet – St Petersburg (south coast)" or "Disband A MUN – Munich", and a submission shows every accepted order's server note, one per line. `v3.0.152` did BR3 (after a retreat phase, `/last_resolution` also carries the movement phase's results as `movement`, found by the phase code each stored resolution now carries, and the game page shows them first) and BR6 (a refused join is shown at the Join form, which takes focus). `v3.0.151` did BR1 and BR2: a retreat phase offers Disband (and says an unordered dislodged unit is disbanded), a build slot hides a province another slot chose, and the server's per-order notes are shown after a submission. `v3.0.150` planned Track BR (a web play-through of retreats, builds, convoys and messages on a phone). `v3.0.149` did BQ7: Button forwards refs (no console warning in `AlertDialogTrigger`), toasts sit bottom-centre, and buttons, inputs, selects, checkboxes, radios, the logo and footer links are at least 40 px on phones. Track BQ is done and removed. `v3.0.148` did BQ6: on the game page a seated player's order entry follows the map directly; the players list and Telegram group card come after it. `v3.0.147` did BQ4: the map viewer works on a phone (the enlarge hint shows without hover, the viewer opens fitted to the screen, its toolbar is one row of icon buttons on an opaque backdrop). `v3.0.146` did BQ1, BQ2 and BQ5: choosing an order type in the web UI leaves the target empty ("Choose target") and Submit is refused, with the reason shown, until every row has one; an unordered unit reads "No order (holds)"; targets show "NTH – North Sea" and a support names the supported unit's power. `v3.0.145` did BQ3: the game page refreshes the turn status right after a submission and re-fetches the game and order status every 30 s while the tab is visible (paused when hidden, refreshed on becoming visible, never overlapping, state replaced only when it changed). `v3.0.144` planned Track BQ (a phone-sized sweep of the web UI). `v3.0.143` did BP2: the scheduler spends a deadline that passed at a table with empty seats only if it is still the deadline (and phase) it saw, so a deadline armed by the last seat filling meanwhile is kept and no "waits for a full table" notice goes out. Track BP is done and removed. `v3.0.142` did BP1: a power that orders fewer builds than it is owed is told (DM and group post) how many were waived, unless it waived them itself. `v3.0.141` planned Track BP (two review notes: the implicit waive of a partial build, and the empty-seat deadline skip writing over a freshly armed deadline) and checked off F3's access-log count. `v3.0.140` did BO3: an order naming a fleet on a split coast without its coast (`F STP - BOT`) is stored, resolved and shown with the coast the fleet stands on (`F STP/SC - BOT`); Track BO is done and removed. `v3.0.139` did BO2 and BO4: builds waived for want of orders are told to the power and the group, the adjustment DM names the free home centres, and an unordered retreat disband no longer says "civil disorder". `v3.0.138` did BO1: a replace submission refused in full leaves the power's earlier orders in place (Track BO holds the other play-through findings). `v3.0.137` did BN6: the deadline scheduler re-checks a game's phase and deadline before processing it and passes the phase it saw to `process_turn`, so a game advanced (or a deadline extended) after the scheduler's read is no longer adjudicated with no orders. `v3.0.136` did BN2: the 10-minute deadline reminder is remembered in `games.reminded_deadline`, so a restart or a second worker no longer re-sends it. `v3.0.135` did BN4: an anonymous game's public `/state` no longer carries `created_by_user_id` (the web reads `is_creator` from `/users/me/games`). `v3.0.134` planned Track BN (spec-vs-code audit) and did BN1 (a deadline scheduler that loses the processing race to another worker no longer overwrites the deadline that worker armed for the new phase) and BN3 (the notification matrix lists the group post for a deadline change); Track BL is done and removed. `v3.0.132` did BL5: `POST /games/{id}/deadline` refuses a deadline at or before now with a 422, and a processed movement turn tells players (DM and group) which vacant seats' units held. `v3.0.131` did BM1: Pillow 13 (`pip-audit` reported 8 CVEs against 12.3.0, all fixed in 13.0.0); rendered boards are byte-identical. `v3.0.130`: a button that redraws its message unchanged (Telegram "message is not modified") no longer logs an error, alerts the maintainer and apologises to the player. `v3.0.129` did BL7: a game that ends with no winners sends
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
- **Track F** (a human playing the game end to end, and host chores) is the maintainer's.

---

# Track BZ — Game endings (API play-through)

- [ ] **BZ1** A draw whose quorum is completed by a concession or a dummy toggle
  (`POST /games/{id}/dummies`) never ends the game: `draw_vote_status` shows `missing: []`,
  `quorum_reached: true`, `game_status: ACTIVE` until someone re-casts a vote, and the votes are
  wiped at the next processed phase. Only `GameService.submit_draw_vote` checks the quorum.
  (`/replace` was named too; it fills a seat that is already required, so it cannot complete one.)
- [ ] **BZ2** `/replace` succeeds on a finished game; it should be the same 409 as `/join`
  ("Game N has ended; it cannot be joined.").
- [ ] **BZ3** A pending deadline proposal survives game end (`GET /deadline` shows
  `pending_proposal` on a COMPLETED game), and `deadline/withdraw` still returns 200 on a finished
  game (vote and propose are a 409 via `_refuse_deadline_change_if_over`).
- [ ] **BZ4** When every human-held power has conceded and only dummies remain, the game stays
  ACTIVE forever (no deadline, `draw_vote_status.required == []`, conceders still see it active).
  Decision: it ends with no winners, as when the last powers concede together (BL6), announced
  the same way. A vacated seat is not a dummy (it can be retaken) and keeps the game alive.
- [ ] **BZ5** Press after game end: architecture.md says a COMPLETED game accepts no writes, but
  `/message` and `/broadcast` are accepted. Decision: post-game press stays allowed (post-mortem
  chat); correct the spec.
- [ ] **BZ6** `/replace` does not refuse a seat listed in `dummy_powers` (`/join` does), so a
  replace can leave a power both seated and a dummy. It should be refused the same way.

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
