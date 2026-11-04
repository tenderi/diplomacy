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
>   history. Track letters run in sequence; the next free one is **CP**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-04.
- **Open tracks:** Track CO (DAIDE server defects from a 2026-11-03 client probe; CO3 open), then
  Track F (a human playing the game end to end, and host chores), which is the
  maintainer's. Finished tracks are removed; `git log` and the `v3.0.x` commit messages
  carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

# Track CO — DAIDE server defects (from a client probe)

A raw-TCP DAIDE client played S1901M to S1902M (movement, retreat, adjustment) against the
local listener on :8432 with seven sessions. NOW, SCO, MIS, MDF, IAM, GOF, DRW and most THX
notes were right; these were not.

- [x] **CO1 — a client can crash its session, or another's.** (a) An unknown token in a DM
      (`0xFFFF`), an unknown frame type (9) or an unknown client error code (0x63) raise
      `ValueError` out of `session.run` (it catches only `DaideWireError`): a traceback and
      the socket closed with no ErrorMessage; expected the DCSP error (0x0E for a bad token).
      (b) A second `NME` on one connection seats a second power (`_cmd_nme` never checks
      `self.power`); the first stays registered to the session after it closes, and a later
      `ADM` or press to it raises uvloop's `RuntimeError` (closed transport) in the
      *sender's* session (`server.py` `broadcast_admin`, `relay_press`, and the same
      `suppress(ConnectionError, OSError)` in `notify_game_processed`, where one dead peer
      can cut the NOW/ORD fan-out). (c) No IM timeout: a connection that never sends IM, or
      stalls mid-frame, stays open forever. (d) Wrong DCSP codes: a DM first gets 0x07
      (expected 0x02), a second IM 0x08 (expected 0x06), a client RM 0x08 (expected 0x0D).
- [x] **CO2 — ORD and SUB misreport orders.** Done in v3.0.231; see the commit message.
- [ ] **CO3 — the handshake.** `NME` is answered with `HLO` at once; a client following the
      standard sequence (NME → YES(NME), MAP → MDF → YES(MAP) → HLO, then SCO and NOW) gets
      `HUH (YES ERR (MAP))` for its `YES (MAP ...)` and may stall. Check the DAIDE spec,
      then accept the standard sequence without breaking today's clients.

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
