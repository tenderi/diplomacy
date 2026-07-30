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

- **Last updated:** 2026-07-30, at `v2.7.63`. `main` green.
- **Next action: G3a** — the only automated work left in this file. Everything else open is
  Track F, which is the maintainer's to run by hand.
- **G1–G6 and Track H are complete** (`v2.7.58`–`v2.7.63`); **Track H has been moved to
  [`done_fixes.md`](done_fixes.md)**. G1 and G3 each turned up a defect bigger than the one
  recorded:
  - G1's help text also claimed `ARMY`/`FLEET` were valid unit spellings (they are rejected
    outright) and marked a *working* order with ❌ — wrong in all three copies of a copy-pasted
    block.
  - **G3 found that `notify_players` had never sent a single notification in this project's
    history**, because it read `telegram_id` off `PlayerModel`, which has no such column. Every
    Telegram DM for every event — turn processed, reminders, joins, broadcasts, game end — was
    dead code. Evidence in G3's section.
  - New task **G3a** filed: draw-vote quorum and concession still notify nobody.
- **The port itself is finished.** Tracks A–E are merged (`v2.7.17`–`v2.7.55`) and Track H is
  archived: the engine conforms to DATC, every phase is playable from both clients, a game can
  end by agreement, a real DAIDE bot can play a turn over the wire, and a player can see what
  happened to their orders. See [`done_fixes.md`](done_fixes.md).
- **Two tracks remain:**
  - **Track F — manual acceptance.** Maintainer-only: needs a live bot token and a human at a
    Telegram client. This is the last thing standing between the project and "the port is
    finished". **Not delegable to an agent.**
  - **Track G — client & lifecycle gaps.** Originally six findings (G1–G6), each verified
    against the code on 2026-07-30 with file/line evidence below; five came from Track E's
    audits, G1 was found while verifying them, and G3a was found while fixing G3. **All six
    original findings are done** (`v2.7.58`–`v2.7.63`); **only G3a remains.**
- **Suggested order:** **G3a**, then Track F whenever the maintainer has a Telegram client to
  hand (it gates nothing else). Completed this session, in order:
  ~~G1~~ → ~~G3~~ → ~~G4~~ → ~~G5~~ → ~~G2~~ → ~~G6~~ → ~~H1~~ → ~~H2~~.
- **Suite baseline to hold (re-measured 2026-07-30 on `main` at `v2.7.62`, against a real
  local Postgres):** **1435 passed, 11 skipped, 10 xfailed**, 2 warnings; ruff clean; engine
  coverage **93.44%** (floor 92), overall **68.79%** (floor 60). Added since `v2.7.56`'s 1333:
  G1's 60 (`test_bot_help_text.py`), G3's 4 (`test_turn_notifications.py`), G4's 10
  (`test_support_order_menu.py`), G5's 12 (`test_waiting_list.py`) plus a rewritten
  `test_telegram_waiting_list.py` (4 → 11) and two removed from
  `test_telegram_bot_enhanced.py`, and G2's 11 (`test_province_display_names.py`).
- **Frontend baseline (re-measured for real at `v2.7.62`, with a local Node 22):** **23 test
  files / 137 tests**, `tsc -b --noEmit` clean, `npm run build` green. G2 added
  `provinceNames.test.ts` (16 tests). Everything before G2 touched no frontend files.

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
  is being honest, not lazy — install the toolchain and re-run them yourself. This works and
  needs no root (G2 used it to run the frontend gates for real):

  ```bash
  curl -fsSLO https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz
  tar xf node-v22.14.0-linux-x64.tar.xz
  export PATH="$PWD/node-v22.14.0-linux-x64/bin:$PATH"
  cd new_implementation/frontend && npm ci
  ```
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
- **After adding an Alembic revision, check `alembic heads` returns exactly one head.** G5's
  first revision id collided with the existing `a1b2c3d4e5f7` (M6's state_json migration).
  Alembic does not fail on the duplicate — it emits a `UserWarning: Revision … is present more
  than once` and then `upgrade head` dies with "Multiple head revisions are present", which
  reads like a branching problem rather than a copy-pasted id. Also verify the migration
  round-trips (`upgrade` → `downgrade -1` → `upgrade`) against a real Postgres; CI runs against a
  fresh `postgres:14`, so a broken `downgrade` is invisible there.
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

- [x] Add `display_names: dict[str, str]` (canonical code → full name) to `MapData`, populated
      in the existing `=`-line parse. Done — a plain field beside `aliases`, no new I/O, and the
      `.map` file stays the sole source. All 75 provinces are covered.
      **The one real subtlety:** split-coast provinces have *three* `=` lines each
      (`Bulgaria (east coast)`, `Bulgaria (south coast)`, `Bulgaria`) and all three resolve to
      the same canonical `BUL`, so taking whichever came first would render a plain `BUL` unit
      as "Bulgaria (east coast)". The display name is therefore only taken from the line whose
      matched spelling has **no coast**; a test asserts no name contains "coast".
- [x] Expose it once, server-side, rather than shipping a copy per client. Done as
      **`GET /maps/{map_name}/provinces`** (code → name, type, supply-centre flag, coasts),
      read once and cached by both clients.
      **Deviation, recorded:** this task said to extend the existing map/metadata endpoint
      rather than invent a route — but **there is no such endpoint.** Every other `/maps/*`
      route returns a PNG. The alternative was adding the table to the per-game state view,
      which would ship 75 entries on every poll, so a new static route is the cheaper choice.
- [x] Use it where a name helps and a code does not, and **never** in the order strings the
      clients post back. Done, with a deliberate limit on *where*:
      - **Web** (`frontend/src/lib/provinceNames.ts`): the resolution panel keeps the canonical
        order string and adds a **second, muted line** glossing it — `A BER - KIE` with
        "Army Berlin → Kiel" beneath. Retreat options render as `Silesia (SIL)`. Nothing
        rewrites an order.
      - **Bot** (`telegram_bot/orders.py`): names go on **single-province** buttons only — unit
        selection, support targets, convoy origins, support destinations.
      - **Not** on full order-string buttons. `_order_label` clamps at Telegram's 60-character
        limit, and "Army Marseilles supports Army Paris → Burgundy" does not fit while
        `A MAR S A PAR - BUR` does. A truncated order label is worse than a terse one. This is
        the one place the task's letter (`_order_label`) and its intent diverge, so it is
        written down rather than quietly skipped.
      Both surfaces show **name *and* code** (`Berlin (BER)`), never one alone: a player needs
      the code to type an order, and needs the name to know what they are looking at.
- [x] **Done when:** a new player can read the board and the order menus without a province
      lookup table, no client hardcodes a name table of its own, and the strings posted to the
      API are byte-identical to today's. ✅ Met at `v2.7.62`.
      Neither client hardcodes a name: both read `/maps/standard/provinces`, whose source is the
      `.map` file. Wire format is unchanged — asserted by
      `test_display_names_are_not_registered_as_parseable_aliases` (`aliases['berlin']` is still
      `None` and `A Berlin - Kiel` still raises), by `test_bot_order_labels_stay_in_codes`, and
      by a frontend test that the gloss contains no province code a player could paste.

      **Tests:** `tests/test_province_display_names.py` (11 — engine field, coast subtlety,
      endpoint shape, bot label fallback, fetch-once caching) and
      `frontend/src/lib/provinceNames.test.ts` (16 — pure functions).

      **A test-isolation bug this surfaced, worth keeping:** the bot caches the name table in a
      module global, so whichever test ran first paid the HTTP call and every later test saw a
      warm cache — making the `api_get` call count observed by a bot test depend on test
      *order*. `test_convoy_functions.py`'s `assert_called_once_with` failed for exactly this
      reason. Fixed with an autouse `conftest.py` fixture that resets the cache around every
      test, plus `assert_any_call` at the four sites that counted calls.

      Frontend gates run for real this time (local Node 22 fetched): **23 test files /
      137 tests**, `tsc` clean, `npm run build` green.

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

- [x] Split supports out of `direct_orders` the same way convoys already are, behind a
      "🤝 Support options" button, grouped first by the province being supported. Done —
      `show_support_options` (`orders.py`). The button shows the count
      (`🤝 Support options (24)`) so the player knows the sub-menu is worth opening.
- [x] Give it its own callback namespace (`supopt|`, `suporig|`) alongside `cvopt|`/`cvorig|`,
      and register the handlers where the convoy ones are registered. Done, in `app.py`'s
      `button_callback` immediately above the convoy branches. Payloads carry only
      `game_id`/`unit_key`/province — asserted to stay inside Telegram's 64-byte
      `callback_data` cap by `test_support_submenu_callbacks_carry_provinces_not_order_text`.
      Convenient accident worth recording: the support grammar puts the *other* unit's
      location at token index 4, exactly where the convoy grammar puts the convoyed army's
      origin, so `_support_target` and the convoy helpers index identically.
- [x] Handle `SupportHold` and `SupportMove` distinctly in the second level. Done via
      `_support_label`: once the supported province is fixed, buttons read
      `🛡️ supports holding` vs `➡️ supports move to DEN` rather than repeating the full order
      text. **No third level is needed** and this is not a fudge — level two is bounded by the
      *target's* own adjacency (one hold plus one move per province it can reach, ~6 worst
      case), so it cannot rebuild the problem. What would have rebuilt it is rendering the two
      kinds identically, which the test pins.
- [x] **Done when:** the worst-case unit in a mid-game position offers a first-level menu of
      bounded size (hold/move/support-submenu/convoy-submenu/cancel), tested with a
      hand-built bucket containing many supports; existing convoy tests still pass.
      ✅ Met at `v2.7.60`. `tests/test_support_order_menu.py` (10 tests) builds a bucket of 27
      legal orders (24 of them supports across six neighbours) and asserts the first level is
      **5 buttons**, plus the sharper property that *8× the supports adds zero buttons* —
      which a "just cap the list at 20" fix would fail. Existing convoy tests
      (`test_convoy_functions.py`, `test_interactive_orders.py`) unchanged and green.
      **Mutation-verified:** putting supports back in `direct_orders` fails 2 of 10, removing
      `show_support_choices`' sort fails 2, and labelling hold/move identically fails 2.
      One test-quality note worth keeping: the sort mutation initially **passed**, because the
      first fixture emitted supports already hold-first and destination-sorted, making the
      cache/label alignment assertion vacuous. The fixture now emits them deliberately
      unsorted (destinations descending, hold last) — `legal_orders` promises no ordering, so
      that is also the more honest input.

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

- [x] **Fix the notification stub first** — done. All seven players are DM'd through the same
      `NOTIFY_URL` path `api/shared.notify_players` uses, each told their own power. Note this
      only became a *real* fix once G3 was in: `notify_players` itself was a no-op until
      `v2.7.59`, so routing the stub "through the existing notification path" a day earlier
      would have swapped one silent path for another.
      **Also worth recording:** the old tests for this *looked* like proof it worked. They
      injected a fake `notify_callback` and asserted `len(notified) == 7`, while the production
      callback only wrote a log line — the injected fake was the only implementation that ever
      behaved. The new tests assert against the actual HTTP payloads instead.
- [x] **Make `process_waiting_list` recoverable.** Done, and the recorded decision is the
      second option — **no delete path was added.** The order is now: (1) atomically *claim*
      exactly `WAITING_LIST_SIZE` entries, removing them from the queue in one transaction with
      `FOR UPDATE`; (2) resolve all seven `telegram_id`s to real users, which is the one
      realistic failure mode; (3) only then create the game and assign powers. Any failure
      re-queues precisely the entries it claimed, at the front of the queue.
      **Claiming first is what actually kills the compounding bug.** The old code's failure left
      an orphan game *and* an uncleared queue, so the next `/wait` tripped the threshold again
      and minted another orphan — unbounded. Now a failure can produce at most one partially
      populated game, and never a second from the same players.
      **Honest residual:** there is no single-game delete in `DatabaseService` (only
      `delete_all_games`), so a failure that happens *after* `create_game` leaves that one game
      behind. Validating users before creating anything makes that path very unlikely rather
      than impossible. Adding a `delete_game` was rejected as scope creep for a
      now-non-compounding cosmetic leftover; the test asserts the count does not grow on retry.
      Also fixed: taking exactly seven instead of `clear()`ing means an 8th queued player is
      held for the next game rather than silently dropped.
- [x] **Persistence decision: a `waiting_list` table in Postgres.** Taken 2026-07-30,
      maintainer-confirmed. The queue must survive `systemctl restart diplomacy-bot`, and the
      deciding argument is the boundary one rather than the durability one: this module global
      is one of the last places the bot holds game state, and the bot is meant to be a thin
      client over the HTTP API. The cheaper "warn on startup" option was rejected because it
      cannot actually work — the Telegram IDs to warn *are* the state that died with the
      process. Implementation per `CLAUDE.md`: `persistence/database.py` model + a hand-written
      Alembic revision + `DatabaseService` methods, exposed through the API so the bot posts
      to an endpoint instead of appending to a list.
- [x] Original framing of that decision, kept for the reasoning it records: A `waiting_list`
      table is the obvious answer and makes
      the queue survive deploys, but it is a schema change (`persistence/database.py` +
      Alembic + a `DatabaseService` method, per `CLAUDE.md`) and it moves queue state from the
      bot to the server, which is the right side of the boundary — the bot is meant to be a
      thin client and this global is one of the last places it holds game state. Cheaper
      interim option if the maintainer prefers: keep it in memory but tell everyone in the
      queue on startup that it was dropped.
- [x] **Done when:** all seven players are notified when a queue fills; a mid-loop failure
      leaves no orphan game and no lost queue entries (tested by making the join call raise on
      the fourth player); and the persistence decision is recorded here either way.
      ✅ Met at `v2.7.61`, with one documented caveat on "no orphan game" — see the recoverability
      task above: no *compounding* orphan, and at most one from a post-creation failure, because
      there is no single-game delete path to roll back with.

      **Shipped:**
      - `WaitingListModel` + Alembic revision `g5a1c2d3e4f5`, verified `upgrade`/`downgrade`/
        `upgrade` against the real local Postgres (the table is created, dropped and recreated).
        *Trap hit while writing it:* the first revision id collided with the existing
        `a1b2c3d4e5f7` (M6's state_json migration), which alembic reports only as
        "Revision … is present more than once" plus a **multiple heads** error on
        `upgrade head`. Check `alembic heads` returns exactly one head after adding a revision.
      - `DatabaseService`: `add_to_waiting_list`, `remove_from_waiting_list`, `get_waiting_list`,
        `count_waiting_list`, `claim_waiting_list_entries`, `requeue_waiting_list_entries`,
        `clear_waiting_list`.
      - `api/routes/waiting_list.py`: `POST /waiting_list/join`, `POST /waiting_list/leave`,
        `GET /waiting_list`. The server owns the queue and creates the game, so the bot no
        longer orchestrates game creation at all.
      - The bot's `WAITING_LIST` global and `process_waiting_list` are **gone**; `wait()` is a
        thin `api_post` call, and `/unwait` was added — once the queue is durable, a player who
        changes their mind needs an exit that isn't "wait for the next deploy".
      - `GET /waiting_list` returns counts only, not who is queued: nobody needs that list and
        it is not public information.

      **Tests:** `tests/test_waiting_list.py` (12, server-side, incl. the mandated mid-fill
      failure — `create_player` raises on the 4th player, then the queue is asserted intact and
      a retry succeeds) and a rewritten `tests/test_telegram_waiting_list.py` (11, the bot as a
      thin client), including a guard that `WAITING_LIST`/`process_waiting_list` cannot come
      back. `TestProcessWaitingList` was removed from `test_telegram_bot_enhanced.py`.
      **Test-harness trap worth keeping:** `api/shared.py` and `routes/waiting_list.py` both do
      `import requests`, so they share one module object — patching
      `server.api.shared.requests.post` *and*
      `server.api.routes.waiting_list.requests.post` in the same `with` block rebinds the same
      attribute twice and only the inner mock sees any call. One patch covers both.

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

- [x] Make `JoinGameRequest.game_id` optional, with the path as the single source of truth, and
      **400 on a mismatch**. Done — both halves, because they fix different bugs: omitting it used
      to be a 422, and supplying a *different* value than the path was accepted silently.
      The field is kept in the model (not deleted) purely because ~45 call sites send it — the
      bot's `join`, `admin.py`'s demo seeder, `app.py`, the frontend, and about forty tests — and
      Pydantic would reject them all if the key vanished. All were checked; none regressed,
      since every one already sends a value matching the path.
- [x] **Decision: `/games/create` stays authenticated.** Taken 2026-07-30. An unauthenticated
      game-creation endpoint is an obvious spam vector — each call writes a `games` row with a
      full serialized `GameState` — and C2 added per-IP rate limiting for exactly that class of
      abuse. Requiring a Bearer token or `X-Bot-Secret` is the safe default for a public HTTP
      surface, and every real caller already has one.
      The recommendation's diagnosis was right: what made it *feel* like a wart was the error.
      `require_bot_or_user` returned a bare `"Not authenticated"` with no hint that a header was
      missing, so seeding a game by hand looked like a broken endpoint. It now names both
      accepted credentials, and the decision is recorded in the route's docstring so the next
      person to hit the 401 does not re-litigate it.
- [x] **Done when:** joining a game needs the id in exactly one place, no caller regressed,
      and the `/games/create` decision is written down with its reasoning. ✅ Met at `v2.7.63`.
      `tests/test_join_game_id_source_of_truth.py` (5 tests): join with no body `game_id`
      succeeds, join with a matching one still succeeds (the no-regression case), a **mismatch
      is a 400 and joins nothing in either game**, the 401 names both credentials, and the
      bot-secret path still creates games.

---

## Definition of done (open tracks)

- [ ] **Track F:** a game plays end-to-end (movement, retreat, build) from both the browser
      and Telegram, run by a human, with F1's five steps checked off and F2's judgement
      recorded.
- [x] **Track G's six original findings:** every order string the bot shows a player parses
      (G1 ✅); full province names reach client output without contaminating the wire format
      (G2 ✅); manual and deadline-triggered turns notify identically, with the matrix documented
      (G3 ✅); no interactive-order menu is unbounded (G4 ✅); the waiting list notifies everyone
      in it and cannot orphan a game (G5 ✅); joining needs the game id in one place (G6 ✅).
- [ ] **Track G's follow-up (G3a):** a draw vote that ends the game, and a concession, notify
      all players rather than only the actor. The last automated task in this file.
- [x] **Track H:** `CLAUDE.md` describes only infrastructure that exists, and `main` stops
      producing an expected-red workflow on every merge. ✅ `v2.7.63`; section archived in
      `done_fixes.md`.
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
- **`maps/standard.map` and `engine/map_loader.py` are the sole topology, alias *and* display-name
  source.** Two agents editing them in parallel will conflict; sequence such tasks or share one
  worktree. (G1 and G2 were the scheduled pair here; both landed, G2 adding `display_names` from
  the `=` lines' left-hand side.)
- **Display names are not parseable aliases, deliberately.** `MapData.display_names` exists for
  client output only; `aliases` is what `parse_order` consults. Adding a full name to `aliases`
  would half-implement the full-name input G1 explicitly decided against — it would work for
  single-word provinces and fail for the 26 multi-word ones. `tests/test_province_display_names.py`
  asserts `aliases['berlin']` is still `None`.
