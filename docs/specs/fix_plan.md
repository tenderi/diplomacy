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
>   history. Track letters run in sequence; the next free one is **DV**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-21.
- **Open tracks:** DU (bot message texts that are wrong for the phase, from the 2026-11-21
  play-through), then F (a human playing the game end to end — the first play-throughs are
  under way — which is the maintainer's). Finished tracks are removed;
  `git log` and the versioned commit messages carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

# Track DU — Bot texts that are wrong for the phase

Found by the 2026-11-21 bot play-through: these texts tell players something false, or
leave them at a dead end.

- [ ] DU1: the "process now" warnings say "Their units will hold" / "treat their units as
      holding" in every phase (`hub.py` `_process_turn`, `orders.py` `processturn`). In a
      retreat phase an unordered dislodged unit is disbanded; in an adjustment phase a
      missing build is waived and a missing disband follows the civil-disorder rule. Make
      the warning phase-aware.
- [ ] DU2: the hub of a finished game (a draw, a solo) still ends with "You have nothing
      to order this phase; wait for the other powers." (`hub.py` `show_hub`,
      `orders.py` ~655). Say the game is over, and offer nothing to wait for.
- [ ] DU3: `/newgame` in a group whose game is still in progress silently relinks the
      group to the new game ("It replaces Game 1…"). The old game's players are not told
      and its maps and reminders stop reaching the group. Ask for confirmation before
      replacing a game that is still in progress, and tell the old game's players when it
      happens (`channel_commands.py` `newgame`).
- [ ] DU4: wording nits. A private `/map` with no argument asks for a game id instead of
      using the current game; a bare `/orders` never mentions `/myorders`; the order echo
      shows `VIA` where help teaches `VIA CONVOY`; "No order yet (disbanded): A BUR" in a
      retreat phase; raw parser errors ("parse error: expected unit kind 'A' or 'F', got
      …") reach players; `/replay` captions omit the phase and `/replay` is missing from
      help.

# Track F — Manual acceptance (maintainer)

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
