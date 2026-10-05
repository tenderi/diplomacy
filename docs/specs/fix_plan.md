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
>   history. Track letters run in sequence; the next free one is **BC**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-06. `v3.0.64` (merged after `v3.0.65` and `v3.0.66`) did BB2b
  (the web game page shows a player the game's Telegram group with an Unlink button, or a
  "Link a Telegram group" link to `t.me/<bot>?startgroup=link_<id>`; `GET /games/{id}/channel`
  names the bot). `v3.0.66` moved `source-map-js` past a high advisory. `v3.0.65` did BB6a
  (an unknown power in a private message is named as such, `/messages` shows short UTC
  times, the group's orders map reads "orders and results"; BB6b, the rumour sender's
  missing DM, awaits the maintainer).
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
- **Track BB** (Telegram groups and messaging, #158) is the open agent work, top-down;
  **Track AZ** (frontend major dependency upgrades) is in progress: AZ1 and AZ2 done, AZ3 open.
  **Track F** (a human playing the game end to end, and host chores) is the maintainer's.

---

# Track BB — Telegram groups and messaging (#158, play-through 2026-10-03)

#158 (maintainer): `/status` in a group answered for Game 1 though Game 2 belongs to that
group. Neither production game is linked to a group; a group's commands ignore the group
link anyway and use the caller's current game. Wanted: exactly one game per group, the link
controllable from the web and from Telegram. The rest come from an agent's messaging
play-through in a group game.

- [x] BB1 — **A group resolves to its linked game, and a group has at most one.**
      `/status` (and the menu header it shares) typed in a group uses the game linked to
      that group, and says how to link one (`/linkgroup <id>`) when none is. In a group it
      never prints the caller's own power ("You are: GERMANY" breaks anonymity). Linking a
      game to a group that already has one moves the link (the reply names the game it
      replaced); a partial unique index on `games.channel_id` makes two impossible.
- [x] BB2a — **The bot links a game from `/start link_<game_id>` in a group** (the
      payload Telegram sends after `t.me/<bot>?startgroup=link_<game_id>`), when the sender
      is a player of that game; same rules and reply as `/linkgroup`. In a private chat the
      payload links nothing.
- [x] BB2b — **Link and unlink from the web game page.** Show the linked group (name) with
      an Unlink button; "Link a Telegram group" opens
      `https://t.me/<bot>?startgroup=link_<game_id>` (BB2a does the linking).
- [x] BB3 — **The bot's `/messages` (and the menu's 💬 Messages) never shows private
      messages**, and a rumour's sender doesn't see it marked as theirs:
      `telegram_bot/messages.py` builds `?telegram_id=` into the URL, so `api_get` sends no
      bot secret and the API treats the bot as anonymous. `tests/test_bot_commands.py`
      asserts the bug. Also: an invalid JWT on `GET /games/{id}/messages` returns 200 with
      broadcasts only instead of 401.
- [x] BB4 — **Blank and oversized messages.** Blank or whitespace-only messages and
      broadcasts are accepted and sent (`routes/messages.py`): 400. Anything that would
      exceed Telegram's 4096 characters with its heading is dropped by the bot as a
      permanent error: cap the text with a clear 400.
- [x] BB5 — **The group guard (v3.0.53) deletes other bots' and unknown commands** when the
      bot is an admin (`/weather@OtherBot`): `app.py` drops the `@bot` suffix unchecked.
      Ignore commands addressed to another bot and commands this bot doesn't have. Its
      "🤫 /rumour is private" notice tells the group who is about to spread a rumour: word
      it generically.
- [x] BB6a — **Messaging polish.** A private message to a name that is not a power
      (`FRANC`) is a 400 that lists the powers (an empty seat keeps "no player is
      assigned"); `/messages` shows `5 Oct 14:03` with "(times in UTC)" in its heading
      instead of raw ISO timestamps; the group's first map is captioned and titled "orders
      and results" rather than "the orders" / "Results".
- [ ] BB6b — **A rumour's sender is the only player who gets no DM**, which hints at the
      author. Needs a design call: awaiting the maintainer.
- [x] BB7 — **`/viewmap` and `/players` typed in a group still used the caller's current
      game.** Now they (and `/map`) resolve through `GET /channels/{id}/game` like
      `/status`, and a typed id for another game is refused in the group.
- [x] BB8 — **A long message log is too big for one Telegram message.** Since BB3 the
      bot's `/messages` shows private messages too, and the log (up to 3500 units per
      message) went out in one reply with no limit, so Telegram refused it. Keep the newest
      whole messages that fit, counted in UTF-16 units, and say how many older were left out.
- [x] BB9 — **A game is linked to a group only from inside that group.** `/link_channel
      <game> <chat_id>` in a private chat and `POST /games/{id}/channel/link` with a web
      login accept any chat id: a player who knows a group's id can squat it with their
      game, and then the group's members can't `/newgame`, `/linkgroup` or `/unlinkgroup`.
      Only the bot (with a chat id it saw the command in) or an admin may link. And
      `/newgame` creates the game, then links: a refused link (409) leaves an unlinked
      orphan game in the public list.
- [ ] **Done when:** every box above is checked.

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

- The 10 DATC hard-tail `xfail`s (second-order convoy paradoxes 6.F.16/17/18/23/24,
  convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8):
  they need an iterative-Szykman resolver, a separate engine project if ever.
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
