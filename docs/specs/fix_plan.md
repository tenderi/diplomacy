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
>   history. Track letters run in sequence; the next free one is **DK**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-11-13.
- **Open tracks:** DJ (the web UI on a phone; next: DJ1). DH (the maintainer's bug reports #404–#408): only DH1 and DH5 are left, and both
  wait on the maintainer's rulings on their issues. Then F (a human playing the game end to end, and host chores, which are
  the maintainer's). Finished tracks are removed; `git log` and the `v3.0.x` commit messages
  carry what each one did.
- Keep this block to the current state: what is open and what to pick next. A finished
  task's write-up goes in its commit message, not here.

# Track DJ — The web UI on a phone

A Playwright walkthrough at 390×844 (2026-11-13) found these, each seen in a screenshot.
Done = each fixed, with a Vitest test that fails without the fix where one can.

- [x] DJ1: zoom-bar buttons (−, +, Fit, 1:1, ↗, ×) are now 44 px on touch. The 55% opening
      zoom of the enlarged map on phones is kept on purpose (v3.0.276: Fit is ~21% there, no
      bigger than the inline map); the walkthrough's crop is the intended pan.
- [x] DJ2: the login error ("Invalid email or password", `Login.tsx`; check
      `Register.tsx` and the password pages) renders grey in a bordered box like an input.
      Use the destructive alert style used elsewhere, with `role="alert"`.
- [ ] DJ7: the shadcn components in `frontend/src/components/ui/` were written for
      Tailwind v4, but the project builds with Tailwind v3, which silently drops classes
      it can't generate. DJ2 found the destructive Alert colour missing for this reason.
      Still suspect: `focus-visible:ring-ring/50` and `aria-invalid:ring-destructive/20`
      (an opacity modifier on a bare `var()` colour), `outline-hidden`, `shadow-xs` and
      `field-sizing-content` in `button`, `select`, `textarea`, `card` and `alert-dialog`.
      Check each against the built CSS and rewrite in v3 terms. Focus rings matter most.
- [ ] DJ3: tap targets under 44 px: the "Back to games" / sandbox / "Home" / login and
      register text links, the orange "You still need to submit orders" button (20 px),
      the game-creation checkboxes and radios.
- [ ] DJ4: on `GameView.tsx` the orders form sits below the map on a ~2,700 px page, the
      "You still need to submit orders" button doesn't say it jumps there, and "Resolve
      orders and advance the game" is a bare red link at the very bottom. Make the status
      button jump to the orders and say so; give the resolve action a real destructive
      button.
- [ ] DJ5: the build phase (`OrderEntry.tsx`) warns "2 builds left unused — they will be
      waived" before the player has chosen anything, and the empty slot's "Build"
      placeholder doesn't read as a picker.
- [ ] DJ6: opening the confirm dialog logs "Function components cannot be given refs …
      AlertDialog"; fix the `alert-dialog` / `Button` ref forwarding.

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
