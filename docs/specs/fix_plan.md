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
>   history. Track letters run in sequence; the next free one is **BG**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-10. `v3.0.97` did BF2 (`routes/games.py`: the 500-wrapping
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

# Track F — Manual acceptance and host chores (maintainer)

No automated test spans a real human playing a real game: it needs a live bot token and a
human at a Telegram client, so this cannot be delegated to an agent. Every phase has
automated coverage; what is unverified is whether the whole thing is *pleasant and
coherent* to use.

## Track BF — No blind excepts

`CLAUDE.md` forbids a blanket `except Exception`; `ruff check src/ --select BLE001` found
155. Policy: a blanket catch may remain only at a true **boundary** (a background loop
that must survive one bad iteration; a side effect after an already-committed write, such
as a notification; a bot command's last-resort reply to the user), and then it logs with
`logger.exception(...)` (a traceback, not a one-liner) and carries
`# noqa: BLE001 -- <why this is a boundary>`. Everywhere else, narrow to what can actually
occur (`SQLAlchemyError`, `requests.RequestException`, `telegram.error.TelegramError`,
`ValueError`, ...) or remove the `try`. In a route, a remaining generic `except` is
preceded by `except HTTPException: raise`. `discord_bot` and `routes/tournaments.py` stay
under a permanent per-file ignore (out of scope, kept for back-compat). Each step removes
its files from `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml`; the track is done
when that list holds only the out-of-scope files.

- [x] **BF1** Enable BLE001; fix `api/shared.py` and `_api_module.py`.
- [x] **BF2** `api/routes/games.py`.
- [ ] **BF3** The other API routes, `persistence/database.py`, `api/idempotency.py`,
  `response_cache.py`.
- [ ] **BF4** `telegram_bot/orders.py`.
- [ ] **BF5** The rest of `telegram_bot/`.

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
