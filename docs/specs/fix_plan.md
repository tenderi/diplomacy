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
>   history. Track letters run in sequence; the next free one is **AS**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-09-25, at `v3.0.17`.
- Everything an agent can do is done. **Track F** (a human playing the game end to end,
  and host chores) is the maintainer's.

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

---

## Out of scope

- The 10 DATC hard-tail `xfail`s (second-order convoy paradoxes 6.F.16/17/18/23/24,
  convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8):
  they need an iterative-Szykman resolver, a separate engine project if ever.
- Tournaments, Discord, observer/spectator mode, AI-powered analysis. `tournaments.py`,
  `discord_bot/`, `run_discord_bot.py` and the spectator routes are kept for backward
  compatibility: don't extend, don't delete.
- A rendering redesign (new art, a new layout engine, an interactive map component).
- Map variants beyond `standard`.
- An admin web page: the host is administered over SSH (`docs/DEPLOYMENT.md`).
- Game options beyond the standard rules: engine rule switches (`BUILD_ANY`, `HOLD_WIN`,
  `SHARED_VICTORY`, …), no-press or public-press games, several powers per player (dummies
  cover small tables), custom starting positions (snapshot restore and saved-game import
  suffice).
- **DAIDE press-content parsing** (`ALY`/`XDO`/`PRP` beyond syntax-checked opaque
  forwarding) — a permanent design decision (`architecture.md`), not a gap.
