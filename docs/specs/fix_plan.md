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
>   history. Track letters run in sequence; the next free one is **BB**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-03, at `v3.0.40` (frontend toolchain on vite 7, vitest 4 and
  plugin-react 5, which clears the vite, esbuild and vitest audit findings: AZ1).
  `v3.0.38` made the turn-processed DM name the new phase (BA4).
- **Track BA** (play-through defects) is the open agent work, top-down. **Track AZ**
  (frontend major dependency upgrades) is in progress: AZ1 done, AZ2 and AZ3 open.
  **Track F** (a human playing the game end to end, and host chores) is the maintainer's.

---

# Track BA — Play-through defects (orders, notifications, privacy)

Found by an agent playing four games against a local API as several powers (2026-10-02).
Adjudication itself was correct in every case checked; these are the paths around it.

- [x] BA1 — **A convoy the menu offers returns a 500 and loses the whole order batch.**
      `F ION C A ALB - APU` with a *fleet* in ALB: `_check_orders` accepts it, re-formats it
      as `F ION C F ALB - APU`, and `submit_orders` re-parses that outside any try block.
      `engine/orders/validation.py` `_validate_convoy` must reject a convoy whose origin
      holds no army, with a 400-class error, and no stored order may fail to re-parse.
      Also `server/legal_orders.py` `_movement_orders`: the `ProvinceType.WATER` loop offers
      `C A X - Y` for every coastal pair next to the fleet whatever is on the board (≈40
      bogus entries for F NTH in F1901, shown by the bot's convoy menu). Offer only convoys
      of armies that exist (the chain-based block already does).
- [x] BA2 — **Every player's Telegram ID is public.** `GET /games/{id}/players` (no auth)
      returns `telegram_id` per seat (`routes/games.py` `get_players`). Drop it from the
      public response (check the bot and frontend for readers first).
- [x] BA3 — **Adjustment orders accepted, then VOID.** Validation never checks the counts
      `legal_orders` already reports in `adjustment.slots`: a build at delta 0, two builds
      with one slot, a disband when builds are owed, two waives for one slot are all
      `success: true`. And the bot's merge path stores `BUILD F KIE` then `WAIVE` as both
      (build happens, waive VOID): waive-after-build must replace like build-after-waive.
- [x] BA4 — **The turn notification is generic and wrong for retreat/adjustment phases.**
      `api/shared.py` `notify_turn_processed` tells every player "Your next orders are due"
      without naming the phase; in a retreat phase only the dislodged powers have orders,
      and they are not told which unit was dislodged or where it may go. Name the new phase,
      tell powers with nothing to do that they wait, tell dislodged powers their units and
      retreat options, and powers with builds/disbands their count.
- [x] BA5 — **An army's convoyed move without `VIA` is rejected.** `A NWY - YOR` (F NTH in
      place) → "YOR is not adjacent to NWY". `docs/specs/adjudication.md` §6 says
      non-adjacent army moves are always convoyed and the rulebook writes `A Lon-Bel`.
      Accept a non-adjacent army move to a coastal province as a convoyed move.
- [ ] BA6 — **Turns can be processed before the game is full** (creator, 1 of 7 seated →
      advances). Decide with the maintainer whether the creator's manual process should
      require a full table (the demo game's AI seats must keep working).
- [ ] BA7 — Smaller issues:
  - [x] The joining player also gets "A player has joined game N as X" (`join_game` passes
        no `exclude_telegram_id`); the power is lower-case there and in `GET /orders/france`.
  - [ ] `orders_status.submitted` counts powers with nothing to do or an empty list
        (`/status` shows "✅ Submitted").
  - [ ] Retreat-phase errors: `A BUR - RUH` should hint at `A BUR R RUH`; an illegal retreat
        should say why (attacker's origin, contested, occupied).
  - [ ] `F ANK - BUL` says "must name a coast" though ANK touches no BUL coast.
  - [x] A private message to your own power is accepted.
  - [ ] `/orderhistory` labels turns "Turn 0/1/3" instead of phase codes.
  - [ ] No history snapshot of the starting board: `/games/{id}/history/0` → 404.
  - [x] `POST /channel/battle_results` is unused and wrong (current phase label, no moves,
        tie numbering) — delete it.
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
- [ ] AZ2 — react-router 7 (follow its v6→v7 migration guide; the future flags first).
- [ ] AZ3 — **`braces` (high, every version: stack-exhaustion DoS on deeply nested
      patterns)**, advisory published after AZ was written, with no fixed release yet. It
      reaches us through `tailwindcss` 3 (via `chokidar`, `fast-glob`, `micromatch`) and the
      `shadcn` CLI (via `fast-glob`, `ts-morph`): 8 of the 10 findings left after AZ1. Both
      are build/dev tooling and parse only our own globs. `npm audit` proposes tailwindcss 4
      (a config rewrite) and a shadcn downgrade to 1.0.0; neither removes `braces` until
      `braces` itself ships a fix. Recheck then, before taking on tailwind 4.
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
