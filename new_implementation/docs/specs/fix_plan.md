# Fix Plan — Living Tracker: Open Work Only

> **This file is the single source of truth for what to work on next.** Any agent or model
> picking up this project: read this file top to bottom, then continue at the first unchecked
> task of the highest-priority track.
>
> **Completed work is not here.** Tracks A–E (the port, the post-rewrite cleanup, security
> hardening, full DAIDE support, and client UX) are all merged and archived in
> [`done_fixes.md`](done_fixes.md), together with their findings, rejected alternatives, and
> verification evidence. Read that file when you need the *why* behind existing code; read
> this one to decide what to do.
>
> **Maintenance contract (non-negotiable):**
> - Check off tasks (`[x]`) in the same commit as the work that completes them.
> - Keep the **Status** block below current: track, next action, date.
> - Newly discovered work becomes a new unchecked task under the right track — never done
>   silently.
> - If a design decision here is changed, edit this file to say what changed and why.
> - **When a track completes, move its whole section to `done_fixes.md` verbatim** — findings
>   and evidence included — and delete it from this file. This file only ever grows sideways,
>   never downward.

## Status

- **Last updated:** 2026-07-30, at `v2.7.59`. `main` green.
- **Next action: G4** (unbounded support keyboards). **G1 and G3 are complete**, and each turned
  up a defect bigger than the one recorded:
  - G1's help text also claimed `ARMY`/`FLEET` were valid unit spellings (they are rejected
    outright) and marked a *working* order with ❌ — wrong in all three copies of a copy-pasted
    block.
  - **G3 found that `notify_players` had never sent a single notification in this project's
    history**, because it read `telegram_id` off `PlayerModel`, which has no such column. Every
    Telegram DM for every event — turn processed, reminders, joins, broadcasts, game end — was
    dead code. Evidence in G3's section.
  - New task **G3a** filed: draw-vote quorum and concession still notify nobody.
- **Everything automated is done.** Tracks A–E are merged (`v2.7.17`–`v2.7.55`). The engine
  conforms to DATC, every phase is playable from both clients, a game can end by agreement, a
  real DAIDE bot can play a turn over the wire, and a player can see what happened to their
  orders. See [`done_fixes.md`](done_fixes.md).
- **Three tracks remain, none of them large:**
  - **Track F — manual acceptance.** Maintainer-only: needs a live bot token and a human at a
    Telegram client. This is the last thing standing between the project and "the port is
    finished". **Not delegable to an agent.**
  - **Track G — client & lifecycle gaps (G1–G6).** Six findings, each verified against the
    code on 2026-07-30 with file/line evidence below. Five were recorded by Track E's audits
    and left unscheduled; **G1 is new and is the highest-impact item in this file** — the bot's
    own `/rules` and `/examples` teach order syntax the engine rejects outright.
  - **Track H — infrastructure & documentation truth (H1–H2).** `CLAUDE.md` documents
    production infrastructure that is not running, and the `Deploy` workflow has never
    succeeded. Both need a maintainer decision, not code.
- **Suggested order:** F1 is the maintainer's whenever they have a Telegram client to hand and
  gates nothing else. Otherwise: ~~G1~~ → ~~G3~~ → **G4 → G5 → G2 → G6 → G3a → H1 → H2.** H1/H2 are
  decisions that cost nothing to make and stop the docs from lying; all three of their
  decisions were taken on 2026-07-30 and are recorded in their sections.
- **Suite baseline to hold (re-measured 2026-07-30 on `main` at `v2.7.56`, against a real
  local Postgres):** **1333 passed, 11 skipped, 10 xfailed**, 2 warnings; ruff clean; engine
  coverage **93.42%** (floor 92), overall **68.04%** (floor 60). Track E recorded overall as
  68.24% — the small drift is measurement noise between runs, not lost coverage; both are well
  clear of the floor. Frontend at last measurement: **22 test files / 121 tests**, `tsc` clean,
  build green (not re-run here — no Node on this machine by default, see below).

---

## Carried-over facts (do not lose these)

Hard-won, still load-bearing, and each one has already cost somebody a round-trip. Full
reasoning for every item is in [`done_fixes.md`](done_fixes.md).

- **10 DATC hard-tail xfails** (documented inline in `tests/datc/`): second-order convoy
  paradoxes 6.F.16/17/18/23/24, convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge
  6.E.8/10, no-fleet-convoy 6.D.8. **Do not un-xfail without the iterative-Szykman resolver
  upgrade.** Out of scope.
- **DB-dependent tests skip silently** without `SQLALCHEMY_DATABASE_URL`. A local Postgres is
  configured for this repo (see `.env` and the `local-postgres-for-m6` memory). **A skip means
  something is wrong, not that the DB is unavailable — never trust a green local run without
  a DB.**
- **No Node toolchain on this dev machine by default.** Frontend gates (`tsc`, Vitest,
  `npm run build`) cannot run until a local Node 22 is fetched, despite `CLAUDE.md`
  documenting them as normal gates. An agent that reports "could not run the frontend gates"
  is being honest, not lazy — install the toolchain and re-run them yourself.
- **Coverage floors:** engine ≥92% (`--include='src/engine/*'`), overall ≥60%. The engine
  floor has **under a point of headroom** and is deliberately not ratcheted tighter: a tighter
  floor makes ordinary dead-code deletion fail CI.
- **`format_order` renders fleets as `A`** unless passed an explicit `kind_by_province` map —
  it infers the unit letter from coast presence. This has now shipped as a user-visible bug
  **twice** (Track A's PR2 recorded it; Track E's E1 reintroduced it and E4 fixed it). The
  kind is genuinely absent from an engine `Order`, which references a `Location`, never a
  `Unit`, and is only recoverable from the board *before* adjudication. Any new code that
  renders order strings must pass the kind map.
- **`orders_by_unit` keys match builds and disbands as a *suffix*, not a prefix.** Keys are
  `f"{kind} {location}"` with coast (`"F STP/SC"`); the grammar is verb-first for builds and
  disbands (`D A PAR`, `BUILD F BRE`). `WAIVE` has no unit and appears only in the flat
  `orders` list.
- **Every `datetime` column is a naive `TIMESTAMP`.** Use
  `persistence.database.utcnow_naive()`, which returns **naive UTC on purpose** — handing
  Postgres a tz-aware value makes it convert to the session timezone and store it shifted,
  which silently corrupted every deadline on non-UTC dev machines. Do not "modernize" it. New
  `datetime` columns must be `timestamptz` or normalize on write.
- **`Game.history` does not survive a `GameRepo` round-trip.** `GameService.load` builds
  `Game(map=..., state=...)` with no `history` argument, so it is always `()` after a reload.
  Anything that needs the pre-adjudication board must compute it *during* `process_turn` and
  persist it — reconstructing it afterwards is impossible.
- **Any frontend test touching a `/games/:id` page must wrap it in
  `<Routes><Route path="/games/:gameId" …>`.** A bare `MemoryRouter` leaves `useParams()`
  unresolved and silently tests the loading spinner. (The old `GameView.test.tsx` asserted
  nothing at all for this reason.)
- **When touching `src/rendering/`, compare rendered PNG bytes before and after.** Clear
  `Map.clear_map_cache()` and `/tmp/diplomacy_map_cache`, render board/orders/resolution PNGs
  through the real `GameService`/API-route functions, compare sha256. That check caught what
  the test suite could not, twice.
- **Pushing to protected `main`:** a bare `git push origin main` is always rejected — the
  required checks (`test`, `frontend`, `security`) have never run on a brand-new SHA. Go
  through a PR, or push to a temp branch, wait for green on that SHA, then fast-forward.

## Execution model (for any agent-delegated task below)

Unchanged from Tracks A–E, and it earned its keep: **one Sonnet subagent per task, each in its
own git worktree against its own Postgres database; the driver re-runs every gate and reads
the whole diff before opening a PR.** That caught, across five tracks, an unbounded
memory-growth bug, two failing frontend tests an agent could not run, a production-safety bug
that would have minted an orphan game row on every deploy, and one wrong triage the driver
itself had handed down. **Re-run the gates yourself; do not merge on an agent's say-so.**

**Subagents do not edit this file** — with several agents in flight, concurrent edits to
`fix_plan.md` guarantee rebase conflicts. Agents report; the driver records.

```bash
# Local gates — run before every push (mirrors CI)
cd new_implementation && source venv/bin/activate
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

Merge procedure, branch-protection traps, and the `gh -R tenderi/diplomacy` requirement are in
`CLAUDE.md`; the two traps that each cost a round-trip (chaining `gh pr merge` with a branch
delete, and tagging a pre-rebase commit) are written up in `done_fixes.md`'s Track A section.

---

# Track F — Manual acceptance (maintainer-only)

## Why this track exists

No automated test spans a real human playing a real game. This is Track A's original
acceptance criterion, never completed, plus the human judgement pass Track E's restructured
web UI never received. It needs a live bot token and a human at a Telegram client, so **it
cannot be delegated to an agent** — it is the maintainer's to run.

Both clients are believed to work: every phase has automated coverage, and E1–E4 shipped the
results UI. What is genuinely unverified is whether the whole thing is *pleasant and coherent*
to use, which no test asserts.

## F1 — End-to-end play-through, both clients

- [ ] `PYTHONPATH=src python -m server.telegram_bot` starts (true since PR1, but confirm).
- [ ] Start the API; create a game, fill 7 powers; `/map` returns a PNG in Telegram.
- [ ] Order a deliberate dislodgement (A PAR–BUR supported, vs. A MUN–BUR); process.
- [ ] Phase `S1901R`: the browser shows retreat options for the dislodged unit only; Telegram
      `/selectunit` offers retreats. Submit one, process — it takes effect.
- [ ] Play to `W1901A` with a captured centre. Both clients show exactly `delta` build slots
      with real home-centre options, and a power at `delta == 0` shows none. Submit a build,
      process — the unit appears on the map.
- [ ] **Done when:** every box above is checked, and any defect found is filed as a new task
      under Track G rather than fixed silently mid-session.

## F2 — Human judgement pass on the restructured web game screen

- [ ] Play the F1 game through the browser and judge the E2/E4 layout as a *player*: is the
      phase state unmistakable, does "what happened last turn" answer the question a player
      actually asks, is the mobile layout usable on a real phone?
- [ ] **Why this is separate from F1:** E1–E4's gates were automated tests, `tsc`, and a
      build. Nobody has ever rendered the page — the dev machine has no headless browser and
      no Node by default (see `no-node-toolchain-locally`). "The tests pass" is not "the
      screen is good", and Track E explicitly declined to claim the latter.
- [ ] **Done when:** the maintainer has an opinion on record here. Cosmetic complaints become
      Track G tasks; "it's fine" is a valid and useful outcome to write down.

---

# Track G — Client & lifecycle gaps

## Why this track exists

Five of these were recorded by Track E's two read-only audits and left unscheduled because
Track E's scope was resolution comprehension. **All five were re-verified against the code on
2026-07-30** — none had drifted — and a sixth (G1) was found while verifying them. They are
independent of each other; pick any one.

Two of them (G1, G5) are live user-facing defects, not polish.

## G1 — The bot's own help text teaches order syntax the engine rejects

**Finding (new, 2026-07-30, verified interactively).** `src/server/telegram_bot/ui.py`'s
`/rules` and `/examples` text documents full-province-name orders throughout —
`ui.py:206` `A Berlin - Kiel`, `ui.py:209` `A Paris H`, `ui.py:213`
`A Marseilles S A Paris - Burgundy`, `ui.py:222` `BUILD A Paris`, `ui.py:224` `D A Munich`,
and `ui.py:182` even marks `A Berlin H` with a ✅. **Every one of them fails to parse:**

```
parse_order('A Berlin - Kiel', power='GERMANY', map=load_standard_map())
  → OrderParseError: unknown province: 'BERLIN'
parse_order('A BER - KIE', ...)  → OK
```

The cause is not a missing normalizer — it is that `engine/map_loader.py` registers only the
**right-hand side** tokens of `maps/standard.map`'s `=` lines as aliases (`adr`, `adriatic` →
`ADR`), never the left-hand full name. `MapData.aliases` has 192 entries and not one is a full
province name; `aliases.get('berlin')` is `None`. So a new player who follows the bot's own
teaching material gets `unknown province` on every order they type.

This is adjacent to, but distinct from, the V2 finding that the bot's old
`normalize_province_name("Berlin")` was a no-op (it returned `"BERLIN"` unchanged, because
`ALTERNATIVE_MAPPING` never held full names). V2 correctly deleted a normalizer that did
nothing — but the docstring's aspiration lived on in the *user-facing help text*, which nobody
re-checked. The docs have been lying since before the rewrite.

**Second defect found while fixing this (2026-07-30).** The province names were not the only
lie in that block. The same "Order Format" text claimed:

> • Use abbreviations: `A`, `F`, `H`, `S`, `C`
> • Or full names: `ARMY`, `FLEET`, `HOLD`, `SUPPORT`, `CONVOY`
> • **Important:** Don't mix abbreviations and full names in the same order
> • Examples: `A Berlin H` ✅ or `ARMY Berlin HOLD` ✅ or `A Berlin HOLD` ❌

Every clause of that is wrong. `parse_order` accepts long **verbs**
(`_HOLD_WORDS`/`_SUPPORT_WORDS`/`_CONVOY_WORDS`/`_RETREAT_WORDS`/`_DISBAND_WORDS` in
`orders/parser.py:62-67`) but the unit kind is `A`/`F` only — so `ARMY BER HOLD` fails
(`expected unit kind 'A' or 'F', got 'ARMY'`), while `A BER HOLD` — the string the docs marked
❌ — parses fine. The "don't mix" rule was invented and had the truth exactly backwards. Worse,
that whole block was **copy-pasted into three modules** (`ui.py` twice, `admin.py:94-97`,
`app.py:207-210`), which is why all four copies were wrong at once.

**Third defect, same block, found by reading the diff (2026-07-30).** `admin.py`'s demo-start
message built `demo_text` as an implicitly concatenated group where only the *first* fragment
was an f-string, so its last two lines — `"• Use \`/processturn {game_id}\`…"` — rendered the
literal text `{game_id}` to the player instead of the number. Pre-existing and unrelated to the
province names; fixed in the same commit (two `f` prefixes) because it sat inside the text being
rewritten. Worth noting as a pattern: a partially-f-stringed implicit-concatenation block is
invisible to Ruff and to every existing test.

**Fixed at `v2.7.58`.** All user-facing order text now lives in one module,
`telegram_bot/help_text.py`, imported by `ui.py` (`/rules`, `/examples`, `/help`), `admin.py`
(demo start) and `app.py` (demo help). There is no longer a second copy to drift.

- [x] **Immediate fix — make the help text true.** Done. `/rules`, `/examples`, `/help`, and
      both demo-game blocks now use canonical codes with the English gloss kept
      (`` `A BER - KIE` - Army Berlin moves to Kiel ``). The bogus ✅/❌ "don't mix" bullet is
      gone, replaced by what the grammar actually does. `docs/TELEGRAM_BOT_COMMANDS.md` was
      audited and found **already correct** (its `### Order syntax` block used codes); it is
      now covered by the guard test rather than trusted.
- [x] **Decision: codes only. The engine will not accept full province names.** Recorded
      2026-07-30, maintainer-confirmed.
      **Reasoning.** The blocker is real: 26 of the LHS names are multi-word (`Adriatic Sea`,
      `English Channel`, `Gulf of Bothnia`) and `parser._tokenize` splits on whitespace, so
      those can never work without genuine grammar changes. That leaves single-word-only
      support, which is *worse for the beginner it is meant to help*: `A Burgundy - Ruhr` would
      work while `F English Channel - NTH` failed, and nothing on screen tells you which kind
      of province you are looking at. A consistent, teachable rule ("provinces are 3-letter
      codes") beats an inconsistent convenience. The community writes `A BER - KIE`, the
      single-word aliases that *do* exist already cover the common near-misses (`baltic`,
      `burg`, `york` — 90 of the 192 alias entries are longer than three characters), and
      `/selectunit` exists for anyone who does not want to memorise codes.
      **Consequence for G2:** the display half is still worth doing. Showing `Berlin (BER)` in
      client output costs nothing and teaches the code, which is the actual fix for the
      confusion that motivated this. G2's "do not substitute names into the order strings the
      clients post back" instruction is now load-bearing rather than advisory.
- [x] **Guard against a third recurrence.** Done — `tests/test_bot_help_text.py` (60 tests).
      It reflects over every public string constant in `help_text.py`, extracts each
      backtick-quoted span whose first token is a unit kind or order verb (stripping a leading
      `/orders <id>` where present), and parses each one through the real
      `engine.orders.parser`. Plus four targeted assertions: no mixed-case province token in
      any example (a parse check alone would miss `A baltic - BER`, which *does* parse), no
      mention of `ARMY`/`FLEET` anywhere, `DEMO_UNITS`' province codes are real, and a
      **meta-test** that the extractor still flags `A Berlin - Kiel` — without which a broken
      extractor would make every other assertion vacuously green, which is how the original
      bug survived.
      **Mutation-verified**, not just green: reintroducing a full province name fails 2 tests,
      reintroducing the `ARMY`/`FLEET` claim fails 7, and a bad code in `DEMO_UNITS` fails 1.
- [x] **Done when:** every order string shown to a Telegram user parses, asserted by a test
      that would fail if the help text regressed; the full-name decision is written down here
      with its reasoning either way. ✅ All three met at `v2.7.58`.

## G2 — No full province names anywhere in client output

**Finding (Track E audit, re-verified).** `MapData` (`engine/map_loader.py:95-107`) exposes
`provinces`, `province_types`, `supply_centers`, `home_centers`, `aliases`, … and **no
display-name map**, so every surface shows 3-letter codes: the web board, the roster, the
order lists, the resolution panel, and the bot's inline keyboards. The full names exist and
are already being read — they are the left-hand side of `maps/standard.map`'s `=` lines
(`Adriatic Sea = adr adriatic`) — and are simply discarded by the parser.

This is the display half of G1's input half. It is not a defect (codes are unambiguous and
what experienced players use); it is a new-player comprehension cost. Do G1's doc fix first —
it is what actually unblocks a confused beginner.

- [ ] Add `display_names: dict[str, str]` (canonical code → full name) to `MapData`, populated
      in the existing `=`-line parse. Keep it a plain field on the frozen dataclass, mirroring
      `aliases`, so the engine gains no I/O and the `.map` file stays the sole source. Note
      the engine-purity property test may need to see this is stdlib-only data.
- [ ] Expose it once, server-side, rather than shipping a copy per client: extend whatever the
      map/metadata endpoint already returns rather than inventing a new route, and let both
      clients read it.
- [ ] Use it where a name helps and a code does not: web roster/order/resolution rows
      (`Berlin (BER)`, not one or the other), bot inline-keyboard button labels
      (`_order_label` in `telegram_bot/orders.py`). **Do not** substitute names into the order
      *strings* the clients post back — those must stay canonical, and G1's finding is exactly
      what happens when display and wire formats blur.
- [ ] **Done when:** a new player can read the board and the order menus without a province
      lookup table, no client hardcodes a name table of its own, and the strings posted to the
      API are byte-identical to today's. **Size:** small-to-medium, mostly touching two client
      surfaces.

## G3 — A manually processed turn notifies nobody

**Finding (Track E audit, re-verified).** The two `process_turn` paths tell players wildly
different amounts:

- **Deadline-triggered** (`api/shared.py:188`): calls
  `notify_players(game_id, "The turn has been processed … submit your next orders")`, resets
  the reminder flag, then auto-posts a turn-start notification *and* a freshly rendered map to
  any linked channel (`shared.py:192-229`).
- **Manually triggered** (`api/routes/games.py:151-239`): notifies **only** when the game has
  just *ended* (`games.py:229`, `"Game N has ended!"`). The ordinary case — everyone submitted,
  one player pressed the button — sends nothing to the other six players and posts nothing to
  the channel. The caller gets the resolution in their HTTP response (E1) and nobody else
  learns the turn happened.

So the failure case (missed deadline) is richly instrumented and the success case is silent.
The audit flagged this as needing a deliberate design pass over "who gets told what, when"
rather than a bolt-on `notify_players` call, and that judgement still holds: the two paths
have drifted because nobody owns the question.

**The much larger defect underneath, found while doing this (2026-07-30):
`notify_players` had never sent a single notification.** It iterated `PlayerModel` rows and read
`getattr(player, 'telegram_id', None)` — but `telegram_id` is a column on **`UserModel`**;
`PlayerModel` references a user via `user_id` and has no such column. So the value was
unconditionally `None`, the `if telegram_id_val is not None` guard never passed, and the function
returned silently. Empirically:

```python
sorted(c.name for c in PlayerModel.__table__.columns)
# ['controlled_supply_centers', 'created_at', 'game_id', 'home_supply_centers', 'id',
#  'is_active', 'is_eliminated', 'last_order_time', 'orders_submitted', 'power_name', 'user_id']
hasattr(PlayerModel, 'telegram_id')  # False
```

That made **every** Telegram DM in the system dead code — turn processed, deadline reminder,
player joined, game full, game ended, broadcast, quit, admin-replace — all of them. It raised
nothing and logged nothing, so it was invisible: `getattr` with a default swallows the schema
mismatch, and the one test that touches this path (`test_api_scheduler.py`'s
`test_reminder_and_notification`) patches `notify_players` itself and so never executes its body.
The G3 symptom as recorded was real but understated: the two `process_turn` paths did agree — in
that neither notified anybody.

Fixed at `v2.7.59` by moving the join into `DatabaseService.get_player_telegram_ids(game_id)`
(players → users, skipping unlinked users), so no caller has to remember that `telegram_id` is not
on `PlayerModel`. **Lesson worth keeping:** `getattr(obj, 'field', None)` against an ORM model is
a silent-failure generator. Prefer direct attribute access, which raises on a schema mismatch.

- [x] **Write down the notification matrix first** — every event (turn processed, deadline
      reminder, deadline missed, player joined, game full, game ended, draw vote reached
      quorum, player conceded/quit) × every channel (Telegram DM to each player, linked
      channel post, web client on next poll). Put it in `docs/specs/architecture.md`, which
      already documents the notification bridge. This is the deliverable that stops the drift;
      the code change is the easy part.
      Done — `architecture.md` gained a **"Notifications: who gets told what, when"** section:
      the three delivery surfaces (Telegram DM, linked-channel post, web client on next poll —
      pull-only, nothing is pushed), a 12-row event × surface table, and four rules for adding
      a notification. Two rows are honestly marked **nothing**; see the new task below.
- [x] Extract the shared "a turn was processed" fan-out (player DMs + channel notification +
      channel map post) into one function both call sites use, so the two paths cannot drift
      again. Done: `shared.notify_turn_processed(game_id, numeric_game_id, *, trigger,
      game_ended, exclude_telegram_id)`, called by `process_due_deadlines` and by the manual
      route. `trigger` (`"deadline"`/`"manual"`) changes only the *wording* of the DM — a missed
      deadline is worth saying out loud — while which surfaces fire is identical by construction.
      **No sync/async bridge was needed after all:** the helper is plain-sync, which both a sync
      scheduler and an `async` route can call unchanged. `_notify_daide_processed` bridges the
      other direction (async callee, sync caller), so it was not the applicable precedent. The
      blocking cost (`timeout=2` per player) is pre-existing on both paths and is documented in
      `architecture.md` as a legitimate future change rather than silently altered here.
- [x] Don't notify the caller twice: they already have the resolution in their response.
      Done via `exclude_telegram_id`; `_authorize_process_turn` now returns the authorizing
      player's `telegram_id` (or `None` for bot-secret/admin-token callers, who are not players)
      instead of `None` unconditionally.
- [x] Keep every notification best-effort. Unchanged and now centralised: the fan-out wraps the
      DM loop and the channel post separately, so a channel failure cannot suppress DMs.
      Asserted by `test_notification_failure_does_not_fail_the_turn`, which makes every
      `requests.post` raise and checks the phase still advanced.
- [x] **Done when:** processing a turn manually and by deadline produce the same
      notifications for the six players who did not trigger it, asserted by a test that
      exercises both paths against the same fake notifier, and the matrix is in
      `architecture.md`. ✅ All met at `v2.7.59`.
      `tests/test_turn_notifications.py` (4 tests) seeds a real 7-player game and drives both
      triggers against a patched `requests.post`, comparing *recipient sets* rather than just
      "something was sent" — a bolt-on `notify_players` on the manual path would satisfy the
      latter while still drifting on the former. **Mutation-verified:** restoring the
      `player.telegram_id` read fails 2 of 4, and re-adding the `if game_ended:` guard around
      the manual fan-out fails 3 of 4.

## G3a — Draw-vote quorum and concession notify nobody (new, 2026-07-30)

**Finding.** Filling in G3's matrix turned up two events with no notification at all.
`GameService.submit_draw_vote` finalizes the game *inline* the moment quorum is reached (it calls
`Game.draw()` and `save_state` directly, `game_service.py:213-223`) and returns the outcome only
to the power that cast the deciding vote. The other six players are told nothing — and because the
game is now `COMPLETED`, the deadline scheduler skips it
(`get_games_with_deadlines_and_active_status`), so no later turn-processed fan-out covers for it.
A game can therefore end by agreement and six of seven players find out by refreshing. `concede`
(`games.py:344-364`) is the same shape: a power leaves and nobody is told.

Not scheduled as part of G3, whose scope was the `process_turn` drift. Both are one
`notify_turn_processed`-style call each, now that the fan-out and the matrix exist.

- [ ] Notify all players when a draw vote reaches quorum and the game ends. `notify_turn_processed(..., game_ended=True)` already produces the right message and channel post; the call site is `submit_draw_vote`.
- [ ] Notify all players when a power concedes (a plain `notify_players`; the game continues, so this is not a turn-processed event).
- [ ] Consider notifying on a *non-final* draw vote being cast, so players know a vote is in progress rather than discovering the tally via `/status`. Decide and record — this one is a judgement call, not an obvious gap.
- [ ] Update `architecture.md`'s matrix in the same commit; its two **nothing** rows are what this task removes. **Size:** small.

## G4 — Support-order keyboards have no size limit

**Finding (Track E audit, re-verified).** `telegram_bot/orders.py:628-640`
(`show_unit_orders`) splits a unit's legal-order bucket into `convoy_orders` and
`direct_orders`, then renders **one button per row for every direct order**. Convoys got the
sub-menu treatment precisely because "an open-water fleet's bucket can contain a full cross
product of origin/destination convoy pairs, which would otherwise dominate the menu" (that
file's own docstring, `orders.py:596-602`) — but supports are still inline. A central army
supporting several neighbours' moves in every direction produces 20–30 buttons in one message.

The fix is a known-good pattern already in this file: `show_convoy_options`
(`orders.py:649-697`) groups by origin province and hands off to `show_convoy_destinations`
via its own short callback namespace (`cvopt|`, `cvorig|`), carrying province codes and never
order text — which is what keeps callbacks under Telegram's 64-byte cap.

- [ ] Split supports out of `direct_orders` the same way convoys already are, behind a
      "🤝 Support options" button, grouped first by the province being supported.
- [ ] Give it its own callback namespace (`supopt|`, `suporig|`) alongside `cvopt|`/`cvorig|`,
      and register the handlers where the convoy ones are registered. Carry province codes
      only, never order text — the index-into-cache scheme exists for this reason
      (`orders.py:68`).
- [ ] Handle `SupportHold` and `SupportMove` distinctly in the second level: supporting
      `A BER` to hold and supporting `A BER - SIL` are different orders a player chooses
      between, and flattening them into one list rebuilds the problem one level down.
- [ ] **Done when:** the worst-case unit in a mid-game position offers a first-level menu of
      bounded size (hold/move/support-submenu/convoy-submenu/cancel), tested with a
      hand-built bucket containing many supports; existing convoy tests still pass.
      **Size:** small, and mechanical — the pattern is already written.

## G5 — `WAITING_LIST` is an in-memory global, and its notifications never fire

**Finding (Track E audit, re-verified — and worse than recorded).**
`telegram_bot/games.py:19` declares `WAITING_LIST: List[Tuple[str, str]] = []` as a module
global with `WAITING_LIST_SIZE = 7`. Three separate defects:

1. **Dropped on every restart.** The bot is restarted on every deploy
   (`systemctl restart diplomacy-bot`), so a partially filled queue silently vanishes and the
   players in it are never told. They wait forever for a game that will never be created.
2. **The notification is a stub that only logs.** `wait()` passes a `notify_callback` whose
   entire body is `logger.info(f"Would notify {telegram_id}: {message}")`
   (`games.py:662-664`), with the comment "Notification will be handled by the bot's
   notification system" — it is not. So when the 7th player joins, the six who were already
   queued get **nothing**; only the 7th sees the "Game created!" reply, because that reply
   comes from `wait()`'s own `update.message.reply_text` (`games.py:675`). The bot has a real
   notification path (`notifications.py` on port 8081, driven by `notify_players` in
   `api/shared.py:93`) that this code never reaches for.
3. **`process_waiting_list` is not atomic** (`games.py:594-632`). It creates the game
   (`:600`), then joins seven players in a loop (`:608-612`), then clears the list (`:625`).
   Any failure inside the loop is caught at `:630`, logs, and returns `(None, None)` — leaving
   an **orphan game with a partial roster** *and* an uncleared waiting list, so the next
   `/wait` trips the threshold again and mints another orphan. A separate slip in the same
   function: it takes `waiting_list[:required_size]` but then `clear()`s the whole list, so an
   8th queued player is silently dropped rather than held for the next game.

- [ ] **Fix the notification stub first** — it is the smallest change with the most player
      impact, and independent of the persistence question. Route it through the existing
      notification path instead of a logging no-op.
- [ ] **Make `process_waiting_list` recoverable.** Either roll back the created game when a
      join fails, or (better, since it needs no delete path) create the game *after* all
      seven joins are known to be possible, and remove exactly the seven players consumed
      rather than clearing the list. Decide and record which.
- [ ] **Persistence decision: a `waiting_list` table in Postgres.** Taken 2026-07-30,
      maintainer-confirmed. The queue must survive `systemctl restart diplomacy-bot`, and the
      deciding argument is the boundary one rather than the durability one: this module global
      is one of the last places the bot holds game state, and the bot is meant to be a thin
      client over the HTTP API. The cheaper "warn on startup" option was rejected because it
      cannot actually work — the Telegram IDs to warn *are* the state that died with the
      process. Implementation per `CLAUDE.md`: `persistence/database.py` model + a hand-written
      Alembic revision + `DatabaseService` methods, exposed through the API so the bot posts
      to an endpoint instead of appending to a list.
- [ ] Original framing of that decision, kept for the reasoning it records: A `waiting_list`
      table is the obvious answer and makes
      the queue survive deploys, but it is a schema change (`persistence/database.py` +
      Alembic + a `DatabaseService` method, per `CLAUDE.md`) and it moves queue state from the
      bot to the server, which is the right side of the boundary — the bot is meant to be a
      thin client and this global is one of the last places it holds game state. Cheaper
      interim option if the maintainer prefers: keep it in memory but tell everyone in the
      queue on startup that it was dropped.
- [ ] **Done when:** all seven players are notified when a queue fills; a mid-loop failure
      leaves no orphan game and no lost queue entries (tested by making the join call raise on
      the fourth player); and the persistence decision is recorded here either way.
      **Size:** small for the first two, medium if persistence is chosen (schema + migration).

## G6 — Two API ergonomics warts

**Finding (Track E audit, re-verified).** Both were hit while seeding a game by hand:

1. **`/games/{game_id}/join` needs `game_id` in the body *and* the path.** The route already
   binds `game_id: int` from the path (`api/routes/games.py:466-471`), and
   `JoinGameRequest.game_id: int` (`games.py:45`) is a required field, so omitting it from the
   body is a 422 even though the value is right there in the URL — and supplying a *different*
   value than the path is accepted without complaint. `process_waiting_list` dutifully sends
   both (`telegram_bot/games.py:611`).
2. **`/games/create` requires an authenticated user** (`games.py:86-97`,
   `Depends(require_bot_or_user)`). This may well be deliberate — an unauthenticated
   game-creation endpoint is an obvious spam vector, and C2 added rate limiting for exactly
   that class of abuse — but it is recorded as a wart, so it needs a decision rather than a
   quiet assumption.

- [ ] Make `JoinGameRequest.game_id` optional and ignored, with the path as the single source
      of truth; or, if it must stay, validate that body and path agree and 400 when they do
      not. **Silently accepting a mismatch is the one option to rule out.** Check every caller
      before changing the shape: `telegram_bot/games.py:611`, the frontend's join call, and
      the join tests.
- [ ] Decide and record whether `/games/create` should stay authenticated. Recommendation:
      **keep the auth requirement** (it is the safe default for a public HTTP surface and
      matches C2's threat model) and instead fix whatever made this feel like a wart — most
      likely that the error is an opaque 401 with no hint that a token is needed.
- [ ] **Done when:** joining a game needs the id in exactly one place, no caller regressed,
      and the `/games/create` decision is written down with its reasoning. **Size:** small.

---

# Track H — Infrastructure & documentation truth

## Why this track exists

**The maintainer confirmed on 2026-07-30 that there is no production server currently
running.** That single fact makes a substantial section of the root `CLAUDE.md` describe
infrastructure that does not exist, and it explains a CI workflow that has failed 40 times out
of 40. Neither is a regression to chase — but a spec that describes a fiction is worse than no
spec, and `CLAUDE.md` is loaded into context for every session in this repo, so a wrong
statement there misleads every future agent before it reads a line of code.

Both tasks are **maintainer decisions**, not implementation work.

**Decision taken 2026-07-30 (maintainer-confirmed), covering both H1 and H2: option (a) —
the infrastructure is intentionally torn down.** `CLAUDE.md`'s AWS section becomes "how to
stand it up", with the operational detail living in `infra/terraform/README.md` and a one-line
pointer left behind; the security notes that depend on the deployment get marked explicitly
conditional; and `deploy.yml` is gated behind a repository variable rather than deleted, so the
wiring survives for whenever there is something to deploy again. Rationale: nothing is running,
so present-tense prose in a file loaded into every agent's context is actively misleading, and a
workflow that has failed 40/40 times carries no signal. Gating rather than deleting keeps the
OIDC/SSM deploy path recoverable without re-deriving it.

## H1 — `CLAUDE.md` documents production infrastructure that is not running

**Finding.** `CLAUDE.md`'s "Production infrastructure (AWS)" section describes a running
`t3.micro` in `eu-north-1` with nginx + uvicorn + the bot + postgresql-16, live systemd units,
SSM-backed secret rotation, and deploy-on-merge — in the present tense. None of it is running.
Downstream, C1's `# nosec` justifications, C2's per-IP rate-limit reasoning, and D4's
orphan-game analysis all cite that infrastructure as live context.

- [ ] Decide which is true going forward: **(a)** the infrastructure is intentionally torn
      down and `CLAUDE.md` should describe it as "how to stand it up", moving it to the
      Terraform directory's `README.md` and leaving a one-line pointer; or **(b)** it is
      meant to be running and standing it back up is real work that belongs in this tracker
      as its own task.
- [ ] Whichever is chosen, mark the tense explicitly. The security reasoning that cites the
      deployment (single-tenant `/tmp`, loopback-only nginx proxy, port 8081 closed by the
      security group) must stay readable as *conditional on that deployment*, not as a
      standing guarantee — those are the notes a future agent will lean on when deciding
      whether a bind or a temp path is safe.
- [ ] **Done when:** `CLAUDE.md` describes only what is true at the time of writing, and the
      security notes that depend on the deployment say so. **Size:** under an hour once the
      decision is made.

## H2 — The `Deploy` workflow has never succeeded

**Finding.** `.github/workflows/deploy.yml` triggers on every `main` push whose `Test Suite`
goes green, and has failed **40 out of 40 runs** on `sts:AssumeRoleWithWebIdentity` — the
GitHub OIDC role it assumes does not exist (consistent with H1). Every merge therefore
produces a red workflow that is *expected* to be red, which is exactly the condition that
trains a maintainer to ignore CI failures.

- [ ] Decide: disable the workflow (or gate it behind a repository variable) until there is
      something to deploy, or stand up the OIDC role and make it work. Follows H1 — same
      underlying decision.
- [ ] Either way, stop the permanent red. A workflow that always fails carries no
      information; a disabled workflow with a one-line comment saying why carries some.
- [ ] **Done when:** the default state of `main` after a merge is either all-green or
      red-for-a-real-reason. **Size:** minutes, once H1 is decided.

---

## Definition of done (open tracks)

- [ ] **Track F:** a game plays end-to-end (movement, retreat, build) from both the browser
      and Telegram, run by a human, with F1's five steps checked off and F2's judgement
      recorded.
- [ ] **Track G:** every order string the bot shows a player parses (G1); full province names
      reach client output without contaminating the wire format (G2); manual and
      deadline-triggered turns notify identically, with the matrix documented (G3); no
      interactive-order menu is unbounded (G4); the waiting list notifies everyone in it and
      cannot orphan a game (G5); joining needs the game id in one place (G6).
- [ ] **Track H:** `CLAUDE.md` describes only infrastructure that exists, and `main` stops
      producing an expected-red workflow on every merge.
- [ ] Throughout: full suite green **with a DB**, ruff clean, coverage floors hold, CI green
      on `main`, every landed chunk committed and tagged per `CLAUDE.md`.

Tracks A–E's acceptance criteria are recorded in [`done_fixes.md`](done_fixes.md).

## Out of scope

- The 10 DATC hard-tail xfails / iterative-Szykman resolver (a separate engine project, if
  ever — see "Carried-over facts").
- Tournaments, Discord, observer/spectator mode, AI-powered analysis (long-standing maintainer
  list — `tournaments.py`, `discord_bot/`, `run_discord_bot.py` are **kept for backward
  compatibility, not dead code**; don't extend, don't delete).
- Rendering redesign — new art, a new layout engine, or an interactive/zoomable frontend map
  component. G2 adds province *names* to client text; it does not restyle the board.
- The aspirational spec docs (`dashboard.md`, `visualization_spec.md` §10).
- Map variants beyond `standard`.
- HTTPS / TLS termination — a known infra gap, entangled with Track H's "is there a production
  server at all" decision. C2's brute-force limiting reduces the in-the-meantime risk; it does
  not replace TLS.
- **Deep DAIDE press-content parsing** (the full `ALY`/`XDO`/`PRP` negotiation grammar beyond
  syntax-checked opaque forwarding) — a **permanent** design limitation documented in
  `architecture.md`, not a gap awaiting work.

## Risks / notes

- **`src/rendering/`'s exception handling is deliberately narrow.** All 27 formerly blanket
  `except Exception` blocks were replaced with specific tuples (`v2.7.28`) so a genuine
  programming bug raises instead of being logged and handed back as a subtly wrong image.
  **Never widen one back**, and when touching rendering, compare PNG bytes before and after —
  that check caught what the suite could not.
- **Renderer output is byte-cached** (`/tmp/diplomacy_map_cache` plus in-memory). Clear it when
  eyeballing visual changes (`Map.clear_map_cache()` or delete the tmp dir), or you will
  compare two copies of the same stale image.
- **`visualization_config.json` is live** (since V0) — if arrow styling differs from an old
  screenshot, that is the intended restore, not a regression.
- **G2 and G1 both touch `engine/map_loader.py` and `maps/standard.map`.** If both are
  scheduled, do them in one worktree or sequence them; the `.map` file is the sole topology
  *and* alias source, so two agents editing it in parallel will conflict.
