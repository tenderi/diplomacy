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
>   history. Track letters run in sequence; the next free one is **DQ**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-17.
- **Open tracks:** F (a human playing the game end to end — the first play-throughs are
  under way — and host chores, which are the maintainer's). Finished tracks are removed;
  `git log` and the `v3.0.x` commit messages carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

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

- [x] Exercise the bot's queue for real (maintainer, 2026-11-17: works): `docker compose stop diplomacy_api`, send `/order`
      and `/message` from Telegram, check `/queue`, `docker compose start diplomacy_api`,
      confirm the delivered reports arrive and the message shows its original time.
- [ ] Stop the old game stack on the home server (`kattotuuletin.local`:
      `cd ~/diplomacy/new_implementation && docker compose down`; keep its `pg_data` volume
      until sure — it held no games). The tunnel and p2p's stack there are not ours.
- [x] After the `v3.0.118` deploy (issue #225), count the API's access-log lines over an
      idle hour (2026-10-21: 0 lines in the idle hour) (`docker compose logs --since 1h diplomacy_api | wc -l`). Before: 1,315
      lines/hour, 1,195 of them `/bot/outbox` polls; the issue's target is at least 90% fewer.
- [x] Delete the unused `DIPLOMACY_BOT_SECRET` repository secret (gone, 2026-11-17)
      (`gh secret delete DIPLOMACY_BOT_SECRET -R tenderi/diplomacy`); nothing reads it.


---

## Out of scope

- Tournaments, Discord, observer/spectator mode, AI-powered analysis. 4.0.0 removed the
  old tournament, Discord and spectator code and tables (#461).
- An interactive map component, animation, or a new layout engine.
- Map variants beyond `standard`.
- An admin web page: the host is administered over SSH (`docs/DEPLOYMENT.md`).
- Game options beyond the standard rules: engine rule switches (`BUILD_ANY`, `HOLD_WIN`,
  `SHARED_VICTORY`, …), no-press or public-press games, several powers per player (dummies
  cover small tables), custom starting positions (snapshot restore and saved-game import
  suffice).
- **DAIDE press-content parsing** (`ALY`/`XDO`/`PRP` beyond syntax-checked opaque
  forwarding) — a permanent design decision (`architecture.md`), not a gap.
