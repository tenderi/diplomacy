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
>   history. Track letters run in sequence; the next free one is **DX**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-22.
- **Open tracks:** DW (phone-width web UI findings; DW4 and DW5 remain), DV (only DV4, which awaits the maintainer decision), then F (a human playing the game end to end — the first play-throughs are
  under way — which is the maintainer's). Finished tracks are removed;
  `git log` and the versioned commit messages carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

# Track DW — Phone-width web UI findings (2026-11-22 play-through, 390x844)

- [x] DW1: logging in after a redirect from a protected page (`/games/1`) lands on `/games`
      instead of the page the player was going to; a game link from a notification loses
      its target. Return to the original route after login.
- [x] DW2: `/games/999` shows "Game not found" but keeps polling state, players and
      messages, a stream of 404s; stop polling once the game is known not to exist.
- [x] DW3: choosing "Support" without a target disables Submit and shows "Choose a target
      for A BUD before submitting." *below* the button, while the order helper still says
      "A BUD has no order, so it will hold". Put the warning where a player sees it and
      make the helper agree with the half-filled row.
- [ ] DW4: at 390px the game page's order form sits ~2.5 screens down, behind the status
      card, results, previous turns and the map; the sandbox's Resolve buttons sit above
      the map, far from the order rows, and aren't sticky. Bring the controls closer.
- [ ] DW5: small polish: the "Previous turn" `<select>` is 32px tall (other controls 40–44px);
      the map's legend and title are unreadable at phone width until zoomed
      (`src/rendering/legend.py`); `/nonexistent` silently redirects to Home.

# Track DV — Smaller bot-text findings (2026-11-21 play-through)

- [x] DV1: draw-vote DMs end "Use /draw to agree or /nodraw to withdraw" even for a player
      who has already voted; tailor the line to the recipient's vote.
- [x] DV2: the deadline-set DM names neither who set it nor how long is left, and the hub
      says a deadline "applies when a majority of players agree" while any one player's
      `/deadline` sets it at once. Make the hub text match the behaviour and add the
      setter's power and the time left to the DM.
- [x] DV3: one wording for a waived build: an explicit WAIVE says "1 build waived.", a
      missed one "Your 1 build was waived: no orders came in."; the caller's reply says
      "Austria owes 1 build." where everything else says "AUSTRIA"; the `/order A ROM -
      PAR` note "PAR is inland, so no fleet can convoy it there" is odd advice for an army.
- [ ] DV4 (needs a decision first, ask the maintainer): `/message` in a finished game is
      accepted and delivered; results DMs list orders alphabetically, without outcomes;
      a `/newgame` creator who hasn't joined can't `/unlinkgroup`.

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
