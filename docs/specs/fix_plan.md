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
>   history. Track letters run in sequence; the next free one is **DM**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-14.
- **Open tracks:** DL (code-health findings, 2026-11-14): pick it first, DL1 onward.
  DH (the maintainer's bug reports #404–#408): only DH1 and DH5 are left, and both
  wait on the maintainer's rulings on their issues. Then F (a human playing the game end to end, and host chores, which are
  the maintainer's). Finished tracks are removed; `git log` and the `v3.0.x` commit messages
  carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

# Track DL — Code-health findings (2026-11-14)

From a coverage sweep (3764 passed, 0 skipped, 89.9%): code a player or client depends on
that no test runs. One PR per item.

- [ ] DL1: `GET /games/{id}/map` (`api/routes/maps.py` ~144-158) never runs in a test;
      every bot test stubs `api_get_bytes`. Add `@pytest.mark.map` tests that get a real
      PNG for a movement and a retreat phase. Also delete the dead, unauthenticated
      `GET /games/{id}/debug/unit_locations` (`routes/games.py` ~1820) and any reference
      to it (route-authz matrix, docs).
- [x] DL2: DAIDE retreat/adjustment replies are untested (`daide/session.py` ~377,
      ~581-585, ~615-630): `NOW` with dislodged units and `MRT` lists, `MIS` in retreat and
      adjustment phases, the `RET` note on `ORD`. Also the `SUB` per-power rejection
      (~974-976): a client seated as FRANCE submitting an Austrian unit gets `NYU` and
      nothing is stored. Check each reply against the DAIDE syntax doc.
- [ ] DL3: the void-support explanations (`game_service.py` `_supporter_reaches` fleet
      branch ~2020, the support-hold branch of `_unordered_support_reason` ~2039-2043) and
      the end-of-game texts for `no_winner`/`only_dummies` (`api/shared.py` ~705-709)
      have no tests; include split-coast fleets (STP, SPA, BUL).
- [ ] DL4: the bot's `/queue` listing with queued and finished writes
      (`telegram_bot/notifications.py` ~446-454, `outbox.py` ~165, older-than-today label)
      and the password-reset SMTP send (`routes/auth.py` ~697-706: starttls before login,
      From, recipients) are untested; add a recording fake `SMTP`.

# Track DH — Maintainer bug reports from differential fuzzing and race review

Each item is one GitHub issue carrying the failing test; the issue has the root cause and
the suggested direction.

- [ ] DH1 (#404): a convoyed army dislodged by the unit leaving its destination still
      stands a third unit off there (rulebook IX.7). Prevent strength must be 0 whenever
      the unit at the destination moves into the origin and the move fails, convoyed or
      not; `adjudication.md` §5 and the `contested` rule updated.
- [x] DH2 (#408): `@cached_response` stores a response read before a write but put after
      its `invalidate_cache`. Generation counter (one, process-wide); exact-path invalidation; note
      that the cache is per process.
- [x] DH3 (#406): the deadline scheduler can process the phase after the one whose
      deadline fell due, because the phase change and spending the deadline are two
      commits. Make them one write.
- [x] DH4 (#407): auto-process ignores a wait flag raised between its readiness check and
      the turn's write. Re-check the flags on the locked row, from the auto-process caller
      only.
- [ ] DH5 (#405): an adjacent move with only a partial chain of convoy orders fails
      `NO_CONVOY` instead of walking. **Waiting for the maintainer's ruling** on the issue.

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
- [x] A turn followed by a phase nobody orders in (a trapped retreat, a dummy-only winter)
      posts the group once, not once per phase (issue #414): one text naming the phase that
      needs orders, carrying the folded phase's news (a trapped unit's disband), then the
      ordered turn's orders map and the board after the folded phase.
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
