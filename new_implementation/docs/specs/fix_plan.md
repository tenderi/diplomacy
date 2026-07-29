# Fix Plan — Living Tracker: Finish the Port + Post-Rewrite Cleanup

> **This file is the single source of truth for what to work on next.** Any agent or
> model picking up this project: read this file top to bottom, then continue at the
> first unchecked task of the **active** track.
>
> **Maintenance contract (non-negotiable):**
> - Check off tasks (`[x]`) in the same commit as the work that completes them.
> - Keep the **Status** block below current: track, next action, date.
> - Newly discovered work becomes a new unchecked task under the right track — never
>   done silently.
> - If a design decision here is changed, edit this file to say what changed and why.

## Status

- **Track A — Finish the Port: ALL PRs MERGED (PR1–PR6).** The only thing left is the
  **manual end-to-end check** below, which is the acceptance criterion for the whole
  track. It needs a live bot token and a human at a Telegram client, so **it cannot be
  delegated to an agent** — it is the maintainer's to run.
- **Track B — Post-rewrite cleanup: ALL SUB-TRACKS DONE.** V0 (`v2.7.19`), V2
  (`v2.7.24`), V3 (`v2.7.26` + `v2.7.28`), V4 (`v2.7.31`), and V5 (`v2.7.30`) are all
  merged; V1 was absorbed into PR4. **Track B is complete.**
- **V3 is fully done.** Its one open item — narrowing the 25 blanket
  `except Exception` blocks in `src/rendering/` (`board.py` 8, `svg_paths.py` 7,
  `cache.py` 6, `icons.py` 3, `overlays.py` 1) — landed in `v2.7.28`. Two more
  near-identical `except (AttributeError, Exception)` tuples in `icons.py` (not caught by
  the original grep, which searched literally for `"except Exception"`) were narrowed in
  the same pass, so 27 blocks total were fixed. See the V3 section for the per-block
  exception choices and how they were validated.
- **V5 is done (`v2.7.30`).** `standard-v2` is deleted entirely (SVG assets, routes,
  view-adapter branch, `Map._resolve_svg_path` branch, `health.py` reference, both
  `test_standard_v2_*` files, plus leftover references outside `src`/`tests` in
  `examples/demo_perfect_game.py`, `infra/scripts/compare_environments.py`, and
  `CODEBASE_OVERVIEW.md`), tracked backup cruft under `maps/` is gone, and
  `test_order_visualization.py` was rewritten pytest-idiomatic (no `__main__` runner, no
  prints, `tmp_path` instead of a hardcoded output dir); `test_visualization.py` was
  already clean, no changes needed. See the V5 section for the full file list and
  verification evidence.
- **V4 is done (`v2.7.31`).** Convoy chains merge into one multi-fleet viz entry;
  `DISLODGED` gets its own `"dislodged"` status and marker distinct from success/failure;
  retreat-phase and adjustment-phase resolution maps verified correct with a real
  dislodge→retreat→ownership-flip→disband scenario driven through `GameService`; E2E
  smoke extended. See the V4 section for the full detail and verification evidence.
- **Only remaining item in either track: Track A's manual end-to-end check** (needs a
  live bot token and a human at a Telegram client — see Track A's "Final acceptance"
  section — it cannot be delegated to an agent).
- **Suite baseline (post-V4+V5, on `main`):** 842 passed, 11 skipped, 10 xfailed, 1
  warning (only the pre-existing unrelated `StarletteDeprecationWarning` — V5 removed the
  suite's last `PytestReturnNotNoneWarning`); ruff clean; engine coverage 93.02% (≥92),
  overall 62.43% (≥60). Verified independently by the driver in each subagent's worktree
  after rebasing onto the other's merged `main`, not just taken from the subagents'
  reports.
- **A count that looks alarming but is fine:** V2's suite drop (890 → 840) is *entirely*
  deleted dead-module tests — 34 in `test_province_mapping.py` plus 16 elsewhere
  exercising the retired `normalize_province_name` / `normalize_order_provinces` / `Map`
  topology-query API. No real coverage was lost.
- **Last updated:** 2026-07-29, mid-session. Track A complete except the manual check
  (PR1–PR6, `v2.7.17`–`v2.7.25`); Track B fully complete (`v2.7.19`/`v2.7.24`/`v2.7.26`+
  `v2.7.28`/`v2.7.30`/`v2.7.31`). `main` is green, no open PRs, no stale branches.

### Where the old trackers went

- **Engine rewrite (M0–M7): COMPLETE 2026-07-27.** Merged to `main` via PR #5, tagged
  `v2.7.15`; algorithm documented in `docs/specs/adjudication.md`. Full historical
  tracker: `git show v2.7.18:new_implementation/docs/specs/fix_plan.md`.
- **Track A was drafted on 2026-07-27** (Opus 5 driver + Sonnet subagents) as PR #11
  (`docs-finish-the-port-tracker`); its content was incorporated into this file on
  2026-07-28 and that PR closed. PR1/PR2 are condensed below; PR3–PR6 are verbatim.

### Carried-over facts (do not lose these)

- **10 DATC hard-tail xfails** (documented inline in `tests/datc/`): second-order convoy
  paradoxes 6.F.16/17/18/23/24 (need iterative Szykman re-resolution), convoy-to-adjacent
  6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8. **Do not un-xfail
  without the iterative-Szykman resolver upgrade.** Out of scope for both tracks.
- **DB-dependent tests skip silently** without `SQLALCHEMY_DATABASE_URL`. A local
  Postgres is configured for this repo (see `.env` + the `local-postgres-for-m6` memory);
  a skip means something is wrong, not that the DB is unavailable. Never trust a local
  green run without a DB.
- **Coverage gates in CI:** engine ≥92% (`--include='src/engine/*'`), overall ≥60%
  (measured 2026-07-28: engine 92.86%, overall 62.02%). Coverage headroom is the hidden
  constraint — thin-client bot code drags the overall number; deleting dead src code helps
  it. **The engine floor has only ~0.86 points of headroom** and is deliberately not
  ratcheted tighter: V2 deleted 366 well-tested engine lines without losing a test, and a
  tighter floor would make ordinary dead-code deletion fail CI.
- **Pushing to protected `main`:** required status checks never ran on a brand-new SHA,
  so a bare `git push origin main` is always rejected — even for a clean local commit
  (re-confirmed 2026-07-28). Either go through a PR, or push the commit to a temp branch,
  wait for `test`+`security` to go green on that SHA, then fast-forward `main` to the
  identical SHA.

---

# Track A — Finish the Port (make a game playable end-to-end again)

## Why this track exists

The engine rewrite landed a correct adjudicator, but it **changed the shape of the game
state view and only some callers were ported**. The engine is fine; the layers that
expose it are not. Before this work a game could not be played past the first
dislodgement or the first build phase, and the Telegram bot could not start at all.

**Acceptance criterion for the whole track:** a game can be played end-to-end — movement,
retreat, and build phases — from *both* the browser and Telegram. No automated test spans
this; it is the manual check at the end.

## Execution model

One **Sonnet** subagent per PR, run one at a time in dependency order. The driver
verifies every agent claim by direct read and by re-running the gates locally before
opening a PR — this has already caught several incorrect subagent claims, so **do not
skip it**. Agents push a branch and stop; they do not open or merge PRs.

```
PR1 (entrypoint) ──┐
                   ├──► PR4 (bot) ──┐
PR2 (legal_orders)─┤                ├──► PR6 (hygiene)
                   └──► PR3 (frontend + CI job)
PR5 (lifecycle) ──── independent
```

## Merge procedure (learned the hard way — follow exactly)

`main` is protected with **strict mode** (branches must be up to date) and admin
enforcement on.

1. Agent pushes its feature branch.
2. Driver re-runs the gates locally (below) and reads the diff.
3. `gh pr create -R tenderi/diplomacy` (the `-R` is mandatory; `gh` otherwise resolves
   the unrelated `upstream` remote).
4. Wait for `test` + `security`: `gh pr checks <n> -R tenderi/diplomacy`.
5. **Rebase onto `origin/main` and force-push the branch** — every PR after the first one
   is behind, and strict mode refuses it with `the head branch is not up to date with the
   base branch`. Do this *before* attempting the merge.
6. `gh pr merge <n> -R tenderi/diplomacy --merge`.
7. **Verify `gh pr view <n> --json state --jq .state` reads `MERGED` as its own step.**
8. Only then delete the branch.
9. Tag the **resulting `main` merge commit**, not the pre-rebase branch commit, then
   `git push origin <tag>`.

**Two traps hit on 2026-07-27, both cost a round-trip:**
- Chaining `gh pr merge && git push --delete` in one command: the merge was refused for
  staleness, the delete ran anyway, and deleting the head branch **closed** the open PR.
  After a rebase changed the head SHA, `gh pr reopen` failed — recovery required a
  brand-new PR (#9 → #10).
- Tagging the branch commit before the rebase left `v2.7.18` pointing at an **orphaned**
  SHA. Fixed with `git tag -f` + `git push -f origin v2.7.18`. Verify with
  `git merge-base --is-ancestor <tag> main`.

## Local gates (run before every push)

```bash
cd new_implementation && source venv/bin/activate
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

## PR 1 — `bot-entrypoint` ✅ MERGED (`v2.7.17`, PR #8)

The bot could not start: `src/server/telegram_bot.py` was shadowed by the same-named
package, so the production `python -m server.telegram_bot` died on import. Fixed by
`git mv` → `telegram_bot/app.py` + `__main__.py`; `run_telegram_bot.py` reduced to
`runpy.run_module`; `run_bot_with_logs.sh` path fixed. The tests that should have caught
it were loading the file via `spec_from_file_location` (testing the workaround, not the
import path) — repointed, plus `test_no_shadowing_telegram_bot_module` and a subprocess
smoke so the shadowing cannot come back.

## PR 2 — `legal-orders-phase-aware` ✅ MERGED (`v2.7.18`, PR #10)

`GET /legal_orders` enumerated orders from map topology alone, ignoring phase — retreat
phases were unusable, build phases were unusable **and silently destructive** (movement
orders passed `validate()`, then `adjudicate_adjustments` dropped them without error,
waiving the builds), and split-coast destinations were unioned across coasts. Replaced by
pure `src/server/legal_orders.py` (`legal_orders_for_power(map, state, power)` — no
FastAPI/DB imports, unit-testable without a database) reusing `DislodgedUnit.retreats`
and the unmodified `_validate_build` via `legal_builds()`. New primary route
`GET /games/{id}/legal_orders/{power}`; per-unit route is a lookup into `orders_by_unit`
(200 + empty list for foreign/unknown units — a 404 trips the frontend's fallback).
`tests/test_legal_orders.py` (18 tests, no DB) asserts every emitted string for every
power passes `validate()` in movement/retreat/build/disband states.

### Two findings from PR2 that later PRs must respect

- **`format_order` renders fleets as `A`.** It infers the unit letter from *coast
  presence* unless passed `kind_by_province` — so a fleet at any non-split province
  prints `A`. Any code emitting order strings must pass an explicit kind map. (Not
  cosmetic once clients parse the strings back.)
- **`orders_by_unit` keys name their unit but do not always prefix it.** Keys are
  `f"{kind} {location}"` **with coast** (`"F STP/SC"`). Hold/move/support/convoy/retreat
  strings start with the key, but the engine's grammar is **verb-first** for builds and
  disbands (`D A PAR`, `BUILD F BRE`), so for those the key matches as a *suffix*.
  `WAIVE` has no unit and appears only in the flat `orders` list. Clients must not assume
  a prefix match.

## PR 3 — `frontend-phase-ui` + the frontend CI job ✅ MERGED (`v2.7.20`, PR #13)

- [x] `orderParsing.ts`: added a `waive` type and a **leading-verb** branch *before* the
      null-guard, so the engine's verb-first grammar parses (`D A PAR`, `DISBAND A PAR`,
      `BUILD F BRE`, `BUILD F STP/SC`, `WAIVE`). The old destroy check tested
      `parts[length-2] === 'D'` — which is `"A"` — so it had never fired; deleted. The
      `' S '`/`' C '` checks moved above the `endsWith(' H')` check defensively (not an
      active bug: `format_order` emits `A PAR S A BUR`, no trailing `H`).
- [x] `GameView.tsx`: one fetch of `/legal_orders/{power}` replaced the N+1 per-unit loop;
      `_build` bucket, `myUnits[0]` indexing, `centersOf` and `myPowerState` deleted; unit
      keys now `${kind} ${location}` **with coast** via a `unitKey()` helper.
- [x] `BuildOrdersSection`: `slots`/`action` come from the response's `adjustment` block;
      the `Math.max(slotCount, ..., 1)` phantom-slot floor is gone.
- [x] **CI:** third `frontend` job in `.github/workflows/test.yml` (`npm ci`,
      `npx tsc -b --noEmit`, `npm run test:run`, `npm run build`), with its own
      `defaults.run.working-directory: new_implementation/frontend` overriding the
      top-level one, and `cache-dependency-path:
      new_implementation/frontend/package-lock.json`. **Green on its first run** (PR #13)
      — so PR6's "add to required status checks" precondition is now satisfiable.
- [x] Tests: verb-form + coast regressions in `orderParsing.test.ts`; RETREAT and
      ADJUSTMENT blocks in `GameView.test.tsx` asserting only the dislodged unit is
      offered retreats, exactly `slots` slots render, and a zero-unit power in an
      Adjustment phase renders without throwing.

### Finding from PR3 that later PRs must respect

- **The old `GameView.test.tsx` was asserting nothing.** It rendered `<GameView />` inside
  a bare `MemoryRouter` with no `<Route>`, so `useParams()` never resolved `gameId` and
  the component never left its loading screen. Any frontend test touching a `/games/:id`
  page must wrap it in `<Routes><Route path="/games/:gameId" …>` or it silently tests the
  spinner. (Same class of bug as PR1's `spec_from_file_location` tests — a test that
  exercises the workaround instead of the real path.)

## PR 4 — `bot-phase-aware` ✅ MERGED (`v2.7.22`)

Built by four Sonnet agents in sequence on one branch (API prerequisites → bot core →
bot periphery + tests → sample-map restore).

API prerequisites, same PR: `routes/orders.py` `get_orders_for_power`/`get_orders` now
accept `telegram_id` + bot secret **as query params** (they are GET, so there is no body
to carry them; pattern copied from `GET /games/{id}/messages`); new
`GET /games/{id}/map/history/{turn}`; `_units_for_render`/`_phase_info`/
`_svg_path_for_map_name` promoted out of `routes/maps.py` into the new pure
`src/rendering/view_adapter.py`.

- [x] New `telegram_bot/game_context.py` with `resolve_game_and_power(user_id,
      game_id=None)` + `fetch_user_games` + `GameContextError`, wrapping
      `api_get(f"/users/{id}/games")["games"]` (that endpoint returns a **dict**, not a
      list). Replaced the three dead `api_get(f"/users/{id}")` calls and the resolution
      blocks duplicated across `orders.py`, `games.py`, `ui.py`, `messages.py` and
      `channel_commands.py` — **19 call sites, not the 4 originally counted.**
- [x] `orders.py`: `/myorders`, `/clearorders`, `/clear`, `/orderhistory` fixed;
      `/selectunit` reads the units **list** and branches on `phase_type`;
      `show_possible_moves`/`show_convoy_*` driven by `legal_orders`;
      `from rendering.map import Map` deleted. *(Completes Track B's V1, unblocks V2.)*
- [x] Order list cached in `context.user_data`; `callback_data` is now
      `ord|{game_id}|{idx}` (plus `selunit|`/`cvopt|`/`cvorig|`/`cancelunit|`), so nothing
      can overflow Telegram's 64-byte cap.
- [x] `maps.py`: `/map`, `/viewmap`, `/replay` fetch PNG bytes via the new
      `api_get_bytes()`. `send_demo_map` deleted, `admin.py:69` repointed.
- [x] `games.py`: `/players` reads the bare list; `/status` reads `phase`/`phase_type`
      and the deadline from `GET /games/{id}/deadline`. **Submission state deferred —
      `/orders_status` is PR5's; see the new PR5 task below.**
- [x] `ui.py`: `DESTROY A Munich` → `D A Munich`, plus retreat and `WAIVE` examples.
- [x] `normalize_order_provinces` scoped to user-typed `/order` and `/orders` only, with
      a docstring forbidding its use on server-emitted strings; the interactive flow posts
      `legal_orders` strings verbatim.
- [x] `infra/scripts/diagnose_bot.sh` path fixed (`new_implementation/` segment restored).
- [x] The three zero-collecting bot test files were **deleted, not resurrected** — see the
      decision note below.

### Three decisions taken during PR4 (departures from the plan as written)

1. **`test_bot_functions.py` / `test_selectunit_fix.py` / `test_telegram_bot.py` were
   deleted rather than rewritten.** They collected zero tests (`*Tester` classes vs.
   `python_classes = Test*`), and on inspection they mocked the pre-rewrite response
   shape, patched module paths that never existed (`src.server.telegram_bot.api_get`),
   imported `button_callback` from a location it never lived, and exercised only the
   now-deleted local-render paths. Their intended coverage is carried by the new
   `tests/test_game_context.py`, `tests/test_selectunit_phases.py` (including
   `test_selectunit_retreat_phase` / `test_selectunit_adjustment_phase`) and
   `tests/test_telegram_bot_maps.py` (which holds the "renderer is never called from the
   bot" assertion). Net suite: 841 → 890 passing.
2. **The bot's sample-map feature was removed and then restored differently.** Making the
   bot a strict thin client killed local rendering, which took the "View Sample Map"
   button, `/refresh_map` and the startup map-pregeneration with it. The maintainer chose
   to keep the feature, so it now comes from a new `GET /maps/{map_name}/preview.png`
   (validated against `{standard, standard-v2}` → 404 otherwise; repeat requests hit the
   renderer's existing `MapCache`, no second cache layer added). **`/refresh_map` and the
   startup pregen were not restored** — the command only ever warmed a bot-local byte
   cache that no longer exists, and wiring it to `POST /admin/clear_map_cache` would mean
   plumbing an admin token into the bot for no functional gain.
3. **`engine.province_mapping` is still imported by `telegram_bot/orders.py`** (function-
   local import, user-typed-order path only). This is the last engine import in the bot
   and it is Track B's V2 to remove — V2 folds the alias table into
   `engine/orders/parser.py`, after which the bot should stop normalizing entirely and let
   the server's single grammar handle aliases.

## PR 5 — `turn-lifecycle` ✅ MERGED (`v2.7.23`)

- [x] **`/status` submission state** (carried over from PR4) — the Telegram `/status`
      command now reads `GET /games/{id}/orders_status`.
- [x] `POST /deadline` no longer mutates a **detached** ORM object that never commits;
      it uses `update_game_deadline`, which opens its own session and commits.
- [x] Concurrency: `expected_phase_code` added to `GameRepo.save_state`, raising
      `StaleGameError` → **409**. This is the cross-process guard an `asyncio.Lock`
      cannot be (each uvicorn worker has its own). The non-acquiring `lock.locked()`
      check in `api/shared.py` is deleted.
- [x] New `GET /games/{id}/orders_status` + `POST /process_turn?require_all=true`
      (default stays `false`; the deadline scheduler never passes it).
- [x] `restore/{snapshot_id}` is real: snapshots now also carry `state_json` (the raw
      `state_to_dict`, not the view shape) via Alembic `d1e2f3a4b5c6`. Purely additive —
      `/history` and `/replay` never read the column — and restoring a pre-migration
      snapshot fails loudly with **409** instead of silently doing nothing.
      `GameRepo.restore_state` deliberately has **no** staleness check: a restore is an
      explicit caller-decided rollback, and it clears `pending_orders` (they were
      submitted against the phase being discarded).
- [x] The four scheduler tests are un-skipped (15 → 11 skips). Both long real sleeps are
      gone: the reminder test calls the new `check_and_send_reminders(now)` directly.
- [x] New `tests/test_persistence_database_service.py` — first direct coverage of the
      1033-LOC DAL, including an explicit test that `commit()` is a no-op so nobody
      reintroduces the detached-mutation pattern.

### Two real bugs the un-skipped scheduler tests exposed

The plan assumed those four tests were skipped for a stale reason ("session isolation").
That was true but not the whole story — un-skipping them surfaced two genuine defects:

1. **The tests never sent `Authorization` headers**, so `/games/create` and
   `POST /deadline` 401'd immediately. They would have failed for that reason alone.
2. **`games.deadline` is a naive `TIMESTAMP` column.** Postgres converts a tz-aware
   value to the *connection's session timezone* on write and stores it naive, while every
   reader reinterprets naive as UTC. On any non-UTC session timezone (a local dev
   Postgres defaults to the machine's zone — this one is `Europe/Helsinki`) **every
   deadline was silently shifted by the zone offset.** CI never caught it because its
   Postgres runs UTC. `update_game_deadline` now normalizes to naive UTC before writing.
   **If you add another `datetime` column, either make it `timestamptz` or normalize on
   write — do not assume the session timezone is UTC.**

## PR 6 — `test-hygiene` ✅ MERGED (`v2.7.25`)

- [x] `pytest.ini`: `asyncio_mode = auto`; `--disable-warnings` removed. **The blanket
      `filterwarnings` ignores were removed too** — `ignore::DeprecationWarning` was doing
      the same hiding job more quietly, and between them they concealed the real finding
      below. `filterwarnings` is now empty, with a comment forbidding blanket entries.
- [x] `@pytest.mark.asyncio` on `test_convoy_functions.py` — **already done**; PR4/V2's
      rewrites gave every async test in that file an explicit marker. No action needed.
- [x] Deleted `tests/bot_test_runner.py` (never collected; 5 dead async functions).
- [x] Coverage floors ratcheted — **overall 57 → 60, engine deliberately left at 92.**
      See the reasoning in `.coveragerc`/`test.yml`: V2 deleted 366 well-tested engine
      lines, so the measured engine figure fell 92.97 → 92.86 without losing a test, and a
      tighter floor would make routine dead-code deletion fail CI.
- [x] `frontend` added to required status checks. Verified it had actually run and passed
      on `main` (not just on the PR) before switching it on, since a required check that
      never reports would brick the branch.

### What removing the warning filters actually found

The plan expected the flag to be hiding coroutine-never-awaited warnings. Those were
already fixed. What it was really hiding was **22 uses of `datetime.utcnow()`** — 21
`default=`/`onupdate=` column defaults in `persistence/database.py` plus one direct call
in the DAL. That is the *same naive-datetime class of bug* that silently shifted
`games.deadline` (fixed in `v2.7.23`), sitting on every `created_at`/`updated_at` in the
schema.

All 22 now go through `persistence.database.utcnow_naive()`. **It returns a NAIVE UTC
datetime on purpose** — every timestamp column here is a plain `TIMESTAMP`, and handing
Postgres a tz-aware value makes it convert to the connection's session timezone and store
it naive, shifting the value by the offset. Do not "modernize" this helper to return
`datetime.now(timezone.utc)`; that is the bug, not the fix.

One test also used httpx's deprecated `data=` for a raw body (now `content=`). After
these fixes the suite emits **no warnings at all** except one
`PytestReturnNotNoneWarning` from `test_standard_v2_map.py`, which disappears with V5's
`standard-v2` removal.

## Final acceptance — manual end-to-end check

No automated test spans this. Run it after PR4.

- [ ] `PYTHONPATH=src python -m server.telegram_bot` starts (already true since PR1).
- [ ] Start the API; create a game, fill 7 powers; `/map` returns a PNG in Telegram.
- [ ] Order a deliberate dislodgement (A PAR–BUR supported, vs. A MUN–BUR); process.
- [ ] Phase `S1901R`: browser shows retreat options for the dislodged unit only; Telegram
      `/selectunit` offers retreats. Submit one, process — it takes effect.
- [ ] Play to `W1901A` with a captured centre. Both clients show exactly `delta` build
      slots with real home-centre options, and a power at `delta == 0` shows none.
      Submit a build, process — the unit appears on the map.

---

# Track B — Post-Rewrite Cleanup: dead code & visualization quality

**ACTIVE TRACK as of `v2.7.25`** — Track A is finished, so this is where work continues.
V0, V2, and now V3 are fully merged, V1 was absorbed into PR4. **V4 and V5 remain.** Goal:
remove the remaining pre-rewrite dead and duplicated code, and bring `src/rendering/` up to
the engine's standard — single topology source, focused modules, correct overlays.

## Findings driving this track (verified by direct reads, 2026-07-28)

1. **`rendering/map.py` still contains the pre-rewrite topology half.** The M6 rendering
   split moved the file but never deleted the topology code: a second `Province` class
   (`map.py:24`), a second `.map`-file parser (`_parse_map_file`, `map.py:278`), a
   **hardcoded `WATER_PROVINCES` table** (`map.py:220` — exactly the kind of duplicate
   topology source the rewrite banned; `engine/map_loader.py` is the sole source), and a
   topology query API (`get_province`/`is_adjacent`/`get_adjacency`/…, `map.py:1509-1531`).
2. **~~The only src consumer of that topology half is the Telegram interactive-order
   UI.~~ SPENT as of `v2.7.22`:** PR4 rewired that UI onto `legal_orders` and deleted the
   import. **The topology half of `rendering/map.py` now has zero src consumers** — verify
   with `grep -rn "rendering" src/server/telegram_bot/` (empty) before starting V2.
3. **~~`engine/province_mapping.py` (365 lines) is almost retired.~~ SPENT by V2** — the
   module is deleted and `grep -rn "province_mapping" src/ tests/` is empty. Original note,
   kept for context: remaining consumers were
   `map.py:289` (type lists used only for *warnings* inside the doomed `_parse_map_file`)
   and `telegram_bot/orders.py` (a function-local `normalize_province_name` import on the
   **user-typed-order path only** — PR4 stopped calling it on `legal_orders` strings). It
   also sits inside `src/engine/`, violating "engine = pure rules logic". V2 should fold
   the alias table into `engine/orders/parser.py` and drop the bot's normalization
   entirely, letting the server's single grammar resolve aliases.
4. **~~`map.py` is a 3,150-line God class.~~ SPENT by V3** (`v2.7.26` + `v2.7.28`,
   PR #19 + PR #21): split into 7 modules, none over 687 lines, with `map.py` left as a
   185-line facade. The duplicated primitives and the `render_board_png_with_orders` alias
   are gone. **The 25 (+2 near-identical) blanket `except Exception` blocks are also gone**
   — narrowed to specific exception tuples in `v2.7.28`. V3 is fully done.
5. **Overlay adapter gaps** (`rendering/order_overlay.py` — otherwise clean, keep its
   style): each `Convoy` order emits `convoy_chain=[own fleet]` instead of one merged
   chain per convoyed move; `ResultCode.DISLODGED → "success"` styling is misleading;
   retreat arrows don't use the renderer's dislodged-offset coordinates.
6. **Hygiene:** tracked backup cruft in `maps/` (`standard_backup*.svg`,
   `standard.map.backup`); pre-rewrite print-style test scripts still in `tests/`.

### V0 — Audit + first dead-code batch ✅ DONE 2026-07-28 (`v2.7.19`)

- [x] Deleted the dead `render_board_png_with_moves` render family from `map.py`
      (~330 lines; zero src callers — the live arrow path is
      `_draw_comprehensive_order_visualization`) plus its three test call sites and
      `tests/test_map_consistency.py` (existed only to compare the two paths).
- [x] Deleted `src/server/models.py` (pre-rewrite `powers`-shaped Pydantic models; sole
      reference was a stale unused import in `tests/test_api_spec_shapes.py` — removed).
- [x] Moved `visualization_config.json` from `src/engine/` → `src/rendering/`. The M6
      split moved `visualization_config.py` but left its JSON behind, so the loader
      (which looks next to its own module) silently fell back to code defaults. Moving it
      re-activates the intended overrides (`line_width_primary` 8 vs default 6,
      `outline_width` 2) — a deliberate, visible-but-minor restore of pre-rewrite arrow
      styling. Rendering tests green with it.
- [x] Full suite green (841/15/10), ruff clean.

### V1 — Telegram interactive orders onto the engine → **ABSORBED INTO TRACK A's PR4**

PR4's `orders.py` bullet does exactly this (drive `show_possible_moves`/`show_convoy_*`
from `legal_orders`, delete the `rendering.map` import, stop province-normalizing
server-emitted strings). Nothing to do here; kept as a placeholder so V-numbering in the
`v2.7.19` commit history stays meaningful.

### V2 — Delete the renderer's topology half; retire `province_mapping` ✅ MERGED (`v2.7.24`, PR #16)

- [x] Deleted from `rendering/map.py`: the `Province` class (`:24`), `WATER_PROVINCES`
      (`:220`), `_init_map`/`_init_classic_map`/`_parse_map_file`/`_validate_adjacencies`
      (`:231-424`), and the topology query API (`get_province`, `is_adjacent`,
      `get_supply_centers`, `get_locations`, `get_adjacency`, `validate_location`).
      `map.py`'s ocean-hatching check (`normalized_id in Map.WATER_PROVINCES`) is now
      `_is_water_province(normalized_id)`, a module-level helper backed by a
      module-cached `engine.map_loader.load_standard_map()` (`_engine_map()`) —
      confirmed to agree with the old hardcoded set on all 18 water codes plus a
      negative check on an unknown code. `telegram_bot/maps.py:109/138` had **already**
      been cleaned by PR4 — no `Map("standard")` construction remained there to fix.
- [x] **`Map` constructor decision: removed entirely, not left trivial.** After task 1
      nothing in the class read `self.*` (the last reader, `get_adjacency`'s
      `self.logger`, died with the topology API), so `Map` is now a pure namespace of
      `@staticmethod`s with a docstring saying so — never instantiated anywhere in
      `src/` or `tests/` post-cleanup. This was chosen over "trivial constructor"
      because a trivial `__init__` would just be dead ceremony nobody calls; folding
      into V3's module split (the plan's "better" option) was rejected because V3 is a
      separate, larger mechanical move and blocking V2 on it wasn't warranted — V3 can
      still relocate this namespace class wholesale later.
- [x] Retired `src/engine/province_mapping.py` entirely (365 lines). Diffed its
      `ALTERNATIVE_MAPPING` (66 entries) against the engine parser's alias source
      (`MapData.aliases`, built from `maps/standard.map`'s `=` lines) — **one gap
      found**: `"english"` (bare, no "channel"/"ech" suffix) was in
      `ALTERNATIVE_MAPPING` but not in the `.map` file's `English Channel = eng channel
      ech eng+ch` line. Folded it in by adding `english` to that line (the parser has
      *no* alias table of its own by design — `MapData.aliases` from the `.map` file is
      the only alias source per `engine/orders/parser.py`'s own docstring — so "fold
      into the parser" means editing the `.map` file, not adding a second table).
      Verified: `load_standard_map().aliases["english"] == "ENG"`. Every other
      `ALTERNATIVE_MAPPING` entry already matched the engine's alias exactly (same
      canonical code) — see the "full province names" finding just below.
      `telegram_bot/orders.py`'s `normalize_order_provinces` (and its function-local
      `province_mapping` import) was deleted outright and both call sites (`/order`,
      `/orders`) now post the user's text/split list unmodified — **verified this is
      safe, not just assumed**: `normalize_province_name("Berlin")` returns the
      unchanged string `"BERLIN"` (checked interactively before deleting), because
      `PROVINCE_MAPPING` is keyed by 3-letter codes and `ALTERNATIVE_MAPPING` never
      contained full city names — the old code's docstring example ("Berlin" → BER) was
      aspirational and never actually worked. So the bot's normalizer was already a
      no-op for full names before this change; removing it changes behavior for exactly
      one input class, the alternative abbreviations in `ALTERNATIVE_MAPPING`, all of
      which (bar the folded-in `"english"`) the engine already accepted.
- [x] Test-file decisions (all four itemized in the plan):
      - `tests/test_province_mapping.py` — **deleted** (34 tests, dies with the module,
        as specified).
      - `tests/test_standard_v2_map.py` — **updated**: dropped the two `is_adjacent`
        assertions (the only topology-asserting lines); kept the rendering assertions.
      - `tests/test_standard_v2_map_comprehensive.py` — **updated**: dropped
        `TestStandardV2MapInitialization` (4 tests: all pure `Map(...)` topology
        queries — `map_name`/`.provinces`/`.supply_centers`/`.is_adjacent`, redundant
        with `tests/engine/`) and `test_invalid_map_name_handling` (asserted
        `Map("standard-v2").map_name`, meaningless post-cleanup). Rewrote
        `test_same_game_logic` to assert what's actually true post-cleanup (there is no
        per-variant topology to compare — `standard` and `standard-v2` differ only in
        which SVG they render) instead of deleting it outright.
      - Three test files **not named in the plan** turned out to import
        `normalize_order_provinces` directly and failed collection once it was deleted:
        `tests/test_interactive_orders.py` (dropped 2 of its own tests plus the
        import), `tests/test_telegram_bot_edge_cases.py` (dropped the 3-test
        `TestMalformedOrders` class — each test only asserted "does not necessarily
        raise", i.e. vacuous), `tests/test_telegram_bot_enhanced.py` (dropped 2 tests).
        All other tests in these three files are kept and pass.
      - Net: 890 → 840 passing (50 removed exactly matches 34 + 4 + 5 + 2 + 3 + 2 across
        the six files above; `tests/test_interactive_orders_simple.py` lost 4 more
        dead-module tests not separately itemized in the plan
        (`test_province_mapping`, `test_normalize_order_provinces`,
        `test_map_adjacency`, `test_unit_type_filtering`) but its two real tests
        (`test_callback_data_parsing`, `test_selectunit_command_mock`) are kept).
- [x] **Done when:** `grep -rn "province_mapping" src/ tests/` is empty (confirmed);
      exactly one `.map` parser exists (`engine/map_loader.py`, confirmed via
      `grep -rln "ABUTS" src/`); suite green: 840 passed, 15 skipped, 10 xfailed; ruff
      clean; engine coverage 92.86% (≥92 floor), overall 61.73% (≥57 floor). Rendered a
      real board PNG (722,481 bytes), orders-overlay PNG (724,983 bytes), and a
      post-`PROCESS_TURN` "resolution" PNG (726,342 bytes, phase F1901M) through the
      actual `generate_map_for_snapshot`/`generate_orders_map`/`generate_resolution_map`
      API-route functions with a captured logger — zero warnings logged by
      `diplomacy.rendering.map`.

### V3 — Split `map.py` into focused modules — **MERGED (`v2.7.26` + `v2.7.28`), DONE**

`map.py` went from ~2,850 lines (post-V2) to a **185-line facade**. All gates green and
merged.

- [x] **Layout — 7 modules, not the proposed 5.** Two extra splits, both made purely to
      stay under the ~800-line target and both documented in the modules' own docstrings:
      `rendering/svg_paths.py` (491) was split out of `board.py`, and
      `rendering/arrows.py` (566) out of `overlays.py`. Final sizes: `overlays.py` 687,
      `board.py` 570, `arrows.py` 566, `svg_paths.py` 491, `legend.py` 338, `icons.py`
      306, `cache.py` 196, `map.py` 185. **Nothing exceeds 687.**
- [x] **Facade decision: `map.py` KEPT as a thin facade.** It re-exports `Map` as a
      namespace of 49 `staticmethod(...)` bindings over the new module-level functions, so
      `api/routes/maps.py`, `api/routes/admin.py` and the tests were not touched. Chosen
      over deleting it because the alternative meant editing every importer for no
      behavioural gain, and V4 still has overlay work to do against this surface.
- [x] Deduplicated while moving: `_draw_checkmark` and `_draw_status_x` are gone (only
      `_draw_success_checkmark` / `_draw_failure_x` survive), and the
      `render_board_png_with_orders` alias is deleted — `render_board_png_orders` is the
      single public name. Verified by grep: the old names appear nowhere in `src/`.
- [x] Type hints on every moved signature; `ruff check src/` clean.
- [x] **Narrowed the blanket `except Exception` blocks (`v2.7.28`).** All 25 counted in
      the original audit (`board.py` 8, `svg_paths.py` 7, `cache.py` 6, `icons.py` 3,
      `overlays.py` 1) plus 2 more found in the same pass — `icons.py` had two
      `except (AttributeError, Exception) as e:` blocks (functionally identical to a bare
      `except Exception`, just missed by the original literal-string grep) — are now
      narrowed to specific exception tuples chosen per call site:
      - **Font loading** (`ImageFont.truetype` fallback to `load_default()`, 4 sites
        across `board.py`/`overlays.py`): `OSError` — the only thing PIL raises when a
        font file is missing/unreadable.
      - **Filesystem I/O** (`os.makedirs`, cache reads/writes/removal in `cache.py`, path
        fallback resolution in `board.py`): `OSError`, plus `json.JSONDecodeError` where
        cache metadata is parsed.
      - **Engine topology lookups** (`_engine_map().supply_centers`, 2 sites in
        `board.py`/`svg_paths.py`): `(OSError, ValueError, KeyError)` — covers a missing/
        malformed bundled `.map` file; `MapData.supply_centers` itself is a always-present
        frozen-dataclass field, so an `AttributeError` here would mean a real bug and is
        left to raise.
      - **Hand-rolled SVG path-data parsing** (the 5 `_fill_svg_path*`/
        `_extract_polygon_points_from_path`/`_draw_ocean_pattern` regex parsers in
        `svg_paths.py`, plus the outer `_color_provinces_by_power_with_transparency`
        wrapper): `(ValueError, TypeError, IndexError)`, with `ZeroDivisionError` added
        for `_draw_ocean_pattern` (divides by `spacing`) and `AttributeError` added back
        for the outer wrapper only (it also touches caller-supplied `units`/
        `supply_center_control` dicts, where a non-string power/province name is a
        legitimate malformed-input case, not a code bug).
      - **Icon loading/pasting** (`icons.py`): `(OSError, ValueError, IndexError,
        ZeroDivisionError)` for `_load_and_process_icon` (file I/O + a `size /
        max(canvas_size)` division); `AttributeError` for the inner `draw.im` fallback
        probe (the one place an `AttributeError` *is* the expected outcome, since it's
        deliberately probing for an attribute that may not exist); `(ValueError,
        TypeError, OSError)` for the final icon-paste block (PIL `paste()`'s failure
        modes) — `AttributeError` dropped there since the `isinstance(base_image,
        Image.Image)` check immediately above already guarantees the attribute exists.
      - **Best-effort startup preload** (`preload_common_maps`'s two blocks): `(OSError,
        ValueError, TypeError)` — the render pipeline's own explicit `raise ValueError`s
        plus file/font I/O.
      In every case, `NameError`/`ImportError`/`RecursionError` and (except where noted
      above) `AttributeError` are deliberately left uncaught, so a real programming bug
      introduced later raises instead of being logged-and-swallowed.
- [x] **Validated the narrowing changed no behavior** — re-ran the same byte-identical
      render check V3's split used: a real game created through `GameService`
      (`generate_map_for_snapshot`/`generate_orders_map`/`generate_resolution_map`, the
      actual API-route functions, against a local Postgres), byte cache cleared first.
      Board, orders, and resolution PNG sha256 are **identical before and after** the
      except-narrowing (`5273a039…`/`fa87835d…`/`41f42161…`, 722481/725052/727603 bytes)
      — the board hash also matches the one recorded for the original V3 split, confirming
      the render is still deterministic. Zero warnings logged during any render.
- [x] **Done when:** no module over ~800 lines ✅; all 25(+2) blanket excepts narrowed ✅;
      suite green ✅ 852 passed, 11 skipped, 10 xfailed (identical to the pre-narrowing
      baseline); engine 92.86%, overall 61.74% (both floors pass, unchanged); `ruff check
      src/` clean ✅.

**Evidence the split was genuinely mechanical:** the board and orders PNGs were rendered
before and after and are **byte-identical** (sha256 `5273a039…` / `ac40f03b…`, 722,481 and
725,129 bytes) with the byte cache cleared between runs. That check matters more than the
test suite here — 25 blanket excepts can swallow a broken import and hand back a subtly
wrong image while every test still passes.

**Process note:** the V3 subagent died before committing, reporting, or updating this
file. The work was recovered from its worktree, verified independently (gates + the
byte-identical render comparison above), and committed by the driver. That is why this
section is written from direct inspection rather than from an agent's report — and why the
unfinished except-narrowing was caught rather than assumed done.

### V4 — Overlay correctness polish — ✅ DONE (`v2.7.31`)

- [x] **Merged convoy chains.** `order_overlay.py`'s `orders_by_power_to_viz` and
      `resolution_dict_to_viz` now group all `Convoy` orders sharing the same
      `(origin, dest)` — including across different owning powers (allied convoys) —
      into one viz entry via `_merge_convoy_group`, filed under the first fleet's power.
      `convoy_chain` lists the fleets in input-list order, not a derived route order:
      this module only ever sees `Order` objects, never `MapData`'s sea-adjacency graph,
      so a true topological ordering isn't derivable here without threading the map
      through — documented inline as a deliberate limitation, not an oversight. A
      mixed-status group (e.g. one fleet dislodged, a sibling reporting `NO_CONVOY`)
      collapses to the worst status via a new `_merge_convoy_status` priority order
      (`success < bounced < failed < dislodged`), so a dislodged fleet's marker is never
      hidden by a merely-`"failed"` sibling. Single-fleet convoys still produce a
      one-element chain (regression-tested).
- [x] **Dislodged styling.** `_STATUS_BY_CODE[ResultCode.DISLODGED]` changed from
      `"success"` to a new `"dislodged"` status. Traced through `adjudicator/movement.py`
      to confirm `DISLODGED` can only ever attach to a `Hold` order or a convoying
      `Convoy` order (never `Move`/`Support*`), so only `_draw_hold_order` and
      `_draw_convoy_order` needed a new branch (`overlays.py`). New
      `_draw_dislodged_marker` primitive in `arrows.py` (a heavy hollow ring) is visually
      distinct from both the green success checkmark and the failure X. Every other
      `status ==` site in `overlays.py` was checked so `"dislodged"` can't silently fall
      through to an unhandled branch. **Retreat arrows from the dislodged-offset
      position turned out to already be implemented** (`overlays.py`'s
      `_draw_comprehensive_order_visualization` already computed and passed
      `dislodged_unit_position` into `_draw_retreat_order`, which already preferred it
      over the province center) — verified working rather than rebuilt.
- [x] **Retreat-phase and adjustment-phase resolution maps verified correct.**
      `tests/test_game_service.py::TestResolutionMapAcrossPhases` drives a small
      hand-built `GameState` (via the real, public `GameService.restore_snapshot`)
      through a guaranteed dislodge → retreat → ownership-flip → disband scenario
      spanning `S1901M → S1901R → F1901M → W1901A → S1902M`, rendering and asserting a
      non-trivial resolution PNG at every phase — including genuine retreat-order and
      adjustment-disband (`Disband`) resolution renders, not just movement. No
      adjudication or rendering bugs found in the process.
- [x] **E2E smoke extended.** `tests/test_game_service.py::TestMapRenderingSmoke` and new
      PNG-rendering tests in `tests/test_order_overlay.py`
      (`TestConvoyAndDislodgedRendering`) cover create → submit → orders map → process →
      resolution map, asserting real PNG magic bytes and non-trivial byte sizes.
- [x] **Done when — verified, not just claimed:** rendered a real 2-fleet merged convoy
      chain (LON→HOL via ENG+NTH) and visually confirmed one continuous curved path with
      two distinct fleet markers, not two overlapping one-fleet arrows; rendered
      dislodged-hold vs. successful-hold PNGs for the same unit/province and confirmed
      they differ (424 differing pixels, dislodged case has a visible red ring the
      success case lacks) — both comparisons are now permanent regression tests, not
      one-off manual checks. Suite green: 842 passed, 11 skipped, 10 xfailed, 1 warning
      (only the pre-existing unrelated `StarletteDeprecationWarning`); ruff clean; engine
      coverage 93.02% (≥92), overall 62.43% (≥60) — re-verified independently by the
      driver after rebasing onto V5's `main`, not just taken from the subagent's report.

### V5 — Repo hygiene — ✅ DONE (`v2.7.30`)

- [x] Deleted tracked backup cruft: `maps/standard_backup.svg`,
      `maps/standard_backup_20250730_145707.svg`, `maps/standard.map.backup`. Grepped the
      whole repo first (code/CI/docs) — the only hits were this tracker file itself and a
      `.cursor/rules/agent.md` policy note about *creating* future backups, not referencing
      these specific files.
- [x] **DELETED `standard-v2` entirely.** Removed `maps/v2.svg` (1.2 MB) and `maps/v2/`
      (4 files, including the two `.ai` vector originals); the `_KNOWN_MAP_NAMES` entry in
      `api/routes/maps.py`; the `standard-v2` branch in `view_adapter.svg_path_for_map_name`;
      the `standard-v2` branch in `board._resolve_svg_path` plus the entire v2-specific
      text/transform coordinate-parsing branch in `_get_cached_svg_data` (the jdipNS path is
      now the only parser, and the now-unused `import re` in `board.py` went with it); the
      `v2_svg` entry in `health.py`'s filesystem check; both `test_standard_v2_*` test files;
      the two `standard-v2`-specific cases in `test_view_adapter.py` (its `standard`/general
      tests are untouched). Also cleaned up references the original audit missed because
      they're outside `src`/`tests`: the `-m standard-v2` CLI option and its resolution
      branch in `examples/demo_perfect_game.py`, the `maps/v2.svg` entry in
      `infra/scripts/compare_environments.py`'s file-existence check, and the `v2.svg`/`v2/`
      row plus stale test-file mentions in `CODEBASE_OVERVIEW.md`.
      `grep -rn "standard-v2\|v2\.svg\|maps/v2"` across the whole repo (excluding this
      tracker file) is now empty. Confirmed the still-supported `standard` map still renders
      correctly post-deletion (722,481-byte PNG through the real `GameService`/API-route
      path — matches the V0/V2 baseline byte count exactly) and that `standard-v2` now 404s
      cleanly instead of silently falling back.
- [x] Modernized `test_order_visualization.py`: rewritten from a `__main__`/emoji-banner
      script into two plain `pytest.mark.map` tests using `tmp_path` (not a hardcoded
      `test_maps/` dir) with real assertions (PNG magic bytes + non-zero length + file
      exists) instead of prints. `test_visualization.py` was inspected and found already
      pytest-idiomatic — no changes needed. (`test_standard_v2_map.py` was deleted outright
      per the task above rather than modernized; `bot_test_runner.py` was already covered by
      Track A's PR6.)
- [x] **Done when:** confirmed — `tests/` contains only pytest-idiomatic files (in the
      scope of this task) and `maps/` only ships `standard.svg`/`standard.map`/
      `mini_variant.json`/`svg.dtd`. Suite: 831 passed, 11 skipped, 10 xfailed, 1 warning
      (the last remaining `PytestReturnNotNoneWarning` is gone, leaving only an unrelated
      pre-existing `StarletteDeprecationWarning`); ruff clean; engine coverage 92.86%,
      overall 60.36% (both floors pass) — re-verified independently by the driver in the
      agent's worktree, not just taken from its report.

---

## Definition of done (both tracks)

- [ ] **Track A acceptance:** a game plays end-to-end (movement, retreat, build) from
      both the browser and Telegram — the manual check above completed and each step
      checked off.
- [x] Frontend CI job green and required (`v2.7.25` — verified green on `main` before
      being switched on).
- [x] `src/rendering/` has zero topology knowledge beyond what it imports from
      `engine.map_loader` (V2); `engine/province_mapping.py` is gone (V2); no rendering
      module over ~800 lines — max is `overlays.py` at 687 (V3).
- [x] Overlays: merged convoy chains, distinct dislodged styling, retreat arrows from
      dislodged positions (V4, `v2.7.31`).
- [x] Full suite green **with a DB**, ruff clean, coverage gates hold, CI green on
      `main`, every landed chunk committed + tagged per CLAUDE.md.

## Out of scope

- The 10 DATC hard-tail xfails / iterative-Szykman resolver (separate engine project, if
  ever — see "Carried-over facts").
- Tournaments, Discord, observer/spectator mode, AI-powered analysis (long-standing
  maintainer list — `tournaments.py`, `discord_bot/`, `run_discord_bot.py` are **kept for
  backward compatibility, not dead code**; don't extend, don't delete).
- Rendering redesign (new art, new layout engine, frontend map component). V3 moves
  code; V4 fixes correctness; neither restyles the board.
- The aspirational spec docs (`dashboard.md`, `visualization_spec.md` §10).
- Map variants beyond `standard` (except the V5 keep-or-kill decision on `standard-v2`).

## Risks / notes

- ~~The Telegram bot tests stub deep internals; PR4 will churn them.~~ Done — see PR4's
  decision 1: three files were deleted rather than ported, with the reasoning recorded.
- **The rendering split's broad excepts are narrowed (`v2.7.28`).** All 27 were replaced
  with specific exception tuples (see the V3 section), so a genuine programming bug
  (`AttributeError`/`NameError`/`ImportError`/etc.) now raises instead of being logged and
  swallowed. **Still true and still worth doing when touching rendering: compare rendered
  PNG bytes before and after** — that is how both the V3 split and the except-narrowing
  were validated, and it catches what the suite cannot. A probe script pattern: clear
  `Map.clear_map_cache()` + `/tmp/diplomacy_map_cache`, render board/orders/resolution PNGs
  through the real `GameService`/API-route functions, compare sha256.
- `visualization_config.json` is live again as of V0 — if arrow styling looks different
  in a diff of rendered PNGs, that's the intended restore, not a regression.
- Renderer output is byte-cached (`/tmp/diplomacy_map_cache` + in-memory); clear it when
  eyeballing visual changes (`Map.clear_map_cache()` or delete the tmp dir).
