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
>   history. Track letters run in sequence; the next free one is **BE**.
> - Other sessions may be working in parallel: fetch and rebase on `origin/main` before
>   opening a PR, and take the next free version tag and track letter from `origin/main`.

## Status

- **Last updated:** 2026-10-08. `v3.0.82` did BD5 (a civil-disorder disband is announced
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
  **Track BC** (the DATC hard tail) is open agent work, BC5 next.
  **Track BD** (play-through wording fixes) is open agent work, BD8 next.
  **Track F** (a human playing the game end to end, and host chores) is the maintainer's.

---

# Track BC — DATC hard tail

Five DATC cases are `xfail`: 6.F.16, 6.F.17, 6.F.18, 6.F.23, 6.F.24
(`tests/datc/`). This track makes them pass, one small PR per milestone,
with the targeted fixes first and the paradox resolver after. The expected outcomes are
the DATC's preferred ones (1982/2000 rulebook, Szykman paradox rule) and already sit in
the tests. `git show v2.7.68:old_implementation/diplomacy/tests/test_datc.py` holds the
old engine's version of each case, result codes included.

To see what the engine does on one case, run it with `--runxfail`:
`PYTHONPATH=src python -m pytest tests/datc -q --runxfail -k 6f16`.

**Root causes** (found 2026-10-06 by running each case; prototypes of BC1 to BC4 each
turned their cases green, with the rest of `tests/datc` and `tests/engine` green too):

- **6.G.11: convoy intent is inferred only for a swap.** Without `VIA`, `_uses_convoy` treats
  an adjacent army move as convoyed only if its own power ordered the convoy *and* the
  move is a swap (`_is_swap`). The 1982/2000 rule (choice d of DATC 4.A.3) needs only the
  own-power convoy order. The swap condition was a stand-in for 6.G.7 and is not needed
  once BC2 voids impossible convoy orders. With the condition dropped, the existing
  backup rule already gets 6.G.11 right.
- **6.F.16, 6.F.17, 6.F.18: first-order paradoxes the resolver detects wrongly.** The
  xfail reasons call them second-order; they are not. Three defects in `_resolve` and
  `_backup_rule`, which all matter:
  1. *A dependency is lost.* On re-entering a `GUESSING` order, `_resolve` appends it to
     `_deps` only if it is not already there, and a computation counts as guess-free when
     `_deps` did not grow. So an order whose result reads an already-listed guess is
     marked `RESOLVED` on that guess. In 6.F.16, `F BEL - ENG` is frozen as succeeding on
     the guess that London's support is cut.
  2. *Convoys sit outside the dependency graph.* `_convoy_path_works` asks
     `_is_dislodged` directly instead of resolving the Convoy order through `_resolve`.
     The convoying fleet and the convoyed army therefore never appear in a cycle, and
     `_backup_rule` can classify a convoy paradox as circular movement.
  3. *Szykman fixes too little.* `_backup_rule` sets the convoyed move to `False`, but
     (a) it keeps the guess-pass value for every other move in the cycle, and (b) it does
     not record the convoy as disrupted, so `_convoy_path_works` recomputes it live and
     the re-resolution of the cycle's supports re-enters the same paradox.

  A quick prototype that fixed (1) and (2) and re-resolved the whole cycle after Szykman
  recursed without end on 6.F.14/15/22, or fell into the circular-movement branch. The
  fix is a restructure of `_resolve`/`_backup_rule`, not a patch: BC5.
- **6.F.23, 6.F.24: genuine second-order paradoxes.** Two convoys each decide whether the
  other's support is cut. 6.F.23 has two consistent outcomes and 6.F.24 has none. DATC's
  Szykman rule fails *every* convoyed move in the paradox core, and then nothing that
  depended on them changes. Today both armies already fail, but the fleets attacking the
  convoys keep their guessed success (same root as above). These cases need BC5's
  machinery plus iteration: BC6.

**Every milestone's "done" check:** the cases it names lose their `xfail` and pass; the
rest of `tests/datc` and `tests/engine` stay green, including the order-shuffling
determinism property in `tests/datc/test_properties.py`; `tests/engine/test_purity.py`
passes (stdlib only); `coverage report --include='src/engine/*' --fail-under=95` holds;
and the full local gates in CLAUDE.md pass. Each milestone also updates the DATC counts
and its entry in `docs/specs/adjudication.md` §3/§5/§6/§11,
`docs/specs/testing_and_validation.md`, `CODEBASE_OVERVIEW.md` ("Conformance") and
CLAUDE.md's DATC sentence, and removes its cases from those lists. A milestone that
changes another case's result code says so in its commit, citing v2.7.68's expectation.

- [x] BC1 — **6.E.8, 6.E.10: report a support for an attack on one's own unit as `VOID`
      unless it served other means.** In `src/engine/adjudicator/movement.py`
      `_support_is_void` (the reporting path, `count_own_unit_rule=True`), replace the
      `_destination_contested_by_other` test with "the support was decisive elsewhere":
      the support is given, and the supported move's prevent strength equals the attack
      strength of another move into the same destination, so without it that move would
      have won. Keep the rule reporting-only: `_support_given` must not call it (see
      adjudication.md §5 on why). Drop `_destination_contested_by_other` if it is left
      unused. Cases: 6.E.8, 6.E.10. 6.E.9 and 6.E.12 must stay green.
- [x] BC2 — **6.G.7: a convoy order no route can use is illegal.** In `_Resolver.__init__`,
      a `Convoy` whose fleet is not on a possible route is void: it is reported `VOID`,
      kept out of `items`, and shows no intent. "Possible route" means a chain of fleets
      currently in sea provinces (any power, any order) that starts at a fleet touching
      the army's province, passes through this fleet, and ends at a fleet touching the
      destination. Add one helper (BFS from each end over sea fleets) that BC3 reuses.
      `server/legal_orders.py` already offers convoys only along fleet-held chains
      (`_convoy_shores`), so the two agree. Case: 6.G.7. Add a mechanics test for a
      coastal-province fleet's convoy order (6.F.1's `F CON`) being `VOID`.
- [x] BC3 — **6.D.8: an army move is legal when the board allows a convoy, ordered or not.**
      Replace `_legal_move`'s `(src, dst) in self._convoy_pairs` check with BC2's `_possible_route`
      possible-route helper, and delete `_convoy_pairs`. Add to `_support_is_void`: a
      support of a convoyed move is void when no possible route remains without the
      supporting fleet (6.D.31). Change 6.F.1's `A GRE` assertion to `VOID` and 6.D.31's
      `A RUM` to `NO_CONVOY` (both v2.7.68's codes; fix the docstrings to match).
      6.D.32 must stay green. Leave submission validation (`orders/validation.py`) as it
      is: it already accepts a non-adjacent move between two coasts. Case: 6.D.8.
- [x] BC3b — **`_possible_route` must search simple paths.** Its `through` check accepts a
      dead-end fleet: on the board `A HOL - BEL`, `F NTH C A HOL - BEL`, `F SKA C A HOL - BEL`,
      `F BEL - HOL`, the route NTH → SKA → NTH counts, so SKA's convoy order is not `VOID`
      and shows intent. No current case depends on it, but BC4 makes any own-power convoy
      order show intent, so this has to land before BC4. Require the route through the
      fleet to visit no province twice; add the board above as a mechanics test.
- [x] BC4 — **6.G.11: an own-power convoy order shows intent, swap or not.** In
      `_uses_convoy`, drop `and self._is_swap(m)` from the no-`VIA` branch (and `_is_swap`
      if it is then unused). Do this after BC2, which is what keeps 6.G.7 correct. Update
      adjudication.md §6. Case: 6.G.11. The rest of 6.G must stay green.
- [ ] BC5 — **6.F.16, 6.F.17, 6.F.18: rebuild cycle detection and the Szykman backup.**
      In `movement.py`:
      (1) record every read of a `GUESSING` order as a dependency, so that any result
      computed on a guess is never marked `RESOLVED`;
      (2) decide a convoying fleet's survival through `_resolve` on its Convoy item, so
      convoys join cycles;
      (3) in `_backup_rule`, apply Szykman by adding the cycle's convoyed armies to a
      "convoy disrupted" set that `_convoy_path_works` honours (they fail, cut nothing and
      get `NO_CONVOY`), then reset *every* other cycle member to `UNRESOLVED` and resolve
      it again; a move's guess-pass value is never kept.
      Follow Kruijswijk's published algorithm ("The Math of Adjudication") for the
      `_resolve` skeleton, and add mechanics tests that pin (1) and (2) on their own.
      6.C (circular movement) and 6.F.14, 6.F.15, 6.F.19 to 6.F.22 must stay green. If
      this runs past an hour, land (1) and (2) first as one PR with their mechanics tests
      and the suite green, and (3) as a second.
- [ ] BC6 — **6.F.23, 6.F.24: iterate Szykman over second-order paradoxes.** When
      re-resolution after a Szykman step meets another paradox, fail the convoyed moves
      of that one too, and repeat until no paradox remains. This ends because every round
      fails at least one more convoyed move. A cycle with no convoyed move left falls back
      to the circular-movement rule. Document the loop in adjudication.md §3 and drop the
      "single-pass" paragraph. Cases: 6.F.23, 6.F.24. 6.F.22 must stay green.
- [ ] **Done when:** every box above is checked, `tests/datc` has no `xfail`, and the docs
      and CLAUDE.md say 154/154.

---

# Track BD — play-through wording fixes

A play-through on 2026-10-06 found player-facing wording that is missing, misleading or
wrong. One small PR per task; each pins its exact texts in tests.

- [x] BD1 — **A draw says it is a draw; a withdrawn draw vote is announced.** (a) A game
      ended by an agreed draw told players only "Game N has ended!" and posted
      "🔔 Turn Processed - Game N / Game N has ended." to the group, though no turn was
      processed; neither said it was a draw or among whom (`api/shared.py`
      `notify_turn_processed`'s `game_ended` branch, called from the draw path). (b)
      Withdrawing a draw vote (`vote: false`) notified nobody, so the others kept
      believing "FRANCE has voted … (2/7 agreed)", and the vote notice did not say votes
      lapse when the phase is processed (`routes/games.py` `submit_draw_vote`). (c) Two
      deciding yes votes sent at the same moment could both end the game, so the draw was
      announced twice. Or a vote that loaded the board before the draw committed was recorded
      on the finished game and announced as "(1/7 agreed)". A draw keeps the phase code, so
      the phase check let both through. `modify_draw_votes` and `save_state` now refuse a
      completed row (`refuse_completed`).
- [x] BD2 — **A move written for the wrong unit type names the unit.** `F ROM - TYS` when
      ROM holds an army answers "TYS is not adjacent to ROM", and `F ROM - VEN` is saved
      as `A ROM - VEN`: `engine/orders/validation.py` `_validate_move` checks the real
      unit, not the written type. Say the unit in ROM is an army instead.
- [x] BD3 — **The retreat hint suggests only a legal retreat.** In a retreat phase,
      `A BUR - RUH` answers "to retreat, write A BUR R RUH" even when RUH is not a legal
      retreat (the attacker's origin). Suggest a legal retreat, or list the legal ones.
- [x] BD4 — **A player's own DMs address them as "you".** They talk about the reader in
      the third person ("FRANCE's A BUR was dislodged", "orders are due from FRANCE").
- [x] BD5 — **A civil-disorder disband is announced to its power.** When a power sends no
      disband in an adjustment phase, the engine disbands for it and nobody tells it.
- [x] BD6 — **The bot says which build a new one replaced.** The bot-path `_make_room`
      silently dropped the oldest build when a new one exceeded the allowance; the
      `set_orders` results now carry `replaced`/`note` and the bot shows
      `✅ BUILD A PAR replaced BUILD F BRE (you may build 1)`.
- [x] BD7 — **data_spec.md's `auto_process` mentions incomplete orders.** "Nothing
      missing" omits that it also waits for incomplete orders (`ready_to_auto_process`).
- [ ] BD8 — **A draw voted over DAIDE notifies the Telegram players.** `daide/session.py`
      `_cmd_drw` calls `GameService.submit_draw_vote` directly, so a DAIDE vote, its
      withdrawal (`NOT (DRW)`) and a draw it completes reach only the DAIDE sessions
      (`broadcast_draw_completion`), never `notify_players`, `notify_game_drawn` or the
      group. Needs a notification hook the DAIDE layer can call without importing
      `server.api`.
- [ ] BD9 — **The web results list says a civil-disorder disband was not ordered.**
      `OrderEntry.tsx` `ResultList` shows it as "D A MUN — Unit was disbanded.", like an
      ordered one. `last_resolution` now carries `civil_disorder: true` on it
      (`lib/resultText.ts` `describeResult` can say "Disbanded by civil disorder: you
      ordered too few disbands.").

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
