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

- **ACTIVE: Track A — Finish the Port. NEXT TASK: PR5 — `turn-lifecycle`,** which is
  independent of everything landed so far. PR1–PR4 are merged; PR6 and the manual
  end-to-end check remain. **The manual end-to-end check is now runnable** — it was
  gated on PR4.
- **UNBLOCKED: Track B — Post-rewrite cleanup.** V0 done 2026-07-28 (`v2.7.19`); V1 was
  absorbed into PR4 and is complete. **V2 done 2026-07-28 (`v2.7.24`, branch
  `renderer-topology-v2`, pushed not merged)** — see the V2 section below for details.
  **V3–V4 are now startable.** V5 is independent filler. Track B may be run in parallel
  with PR5/PR6 — they touch disjoint files.
- **Suite baseline (post-V2, `renderer-topology-v2`):** 840 passed, 15 skipped, 10
  xfailed; ruff clean; engine coverage 92.86%, overall 61.73%. (Was 890/15/10 before
  V2 — the 50-test drop is entirely deleted dead-module tests: 34 in
  `test_province_mapping.py` plus 16 elsewhere that exercised the retired
  `normalize_province_name`/`normalize_order_provinces`/`Map` topology-query API; see
  the V2 section for the itemized list.) **Frontend baseline unchanged:** 99 passed in
  21 files; `tsc -b --noEmit` and `npm run build` clean (V2 touched no frontend files).
- **Last updated:** 2026-07-28.

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
- **Coverage gates in CI:** engine ≥92% (`--include='src/engine/*'`), overall ≥57%
  (measured ~59). Coverage headroom is the hidden constraint — thin-client bot code drags
  the overall number; deleting dead src code helps it.
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
coverage report --fail-under=57
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

## PR 5 — `turn-lifecycle` (independent of PR3/PR4)

- [ ] **`/status` submission state (carried over from PR4).** Once
      `GET /games/{id}/orders_status` exists, wire the Telegram `/status` command to it.
      PR4 removed the old, already-broken submission-status block rather than fake it;
      `GET /games/{id}/orders` cannot substitute because it only returns the caller's own
      power.

- [ ] `POST /deadline` (`routes/games.py:469-484`) mutates a **detached** ORM object and
      never commits (the session closes at `database_service.py:315-318`, and
      `db_service.commit()` is a documented no-op) — so the deadline is silently
      discarded. Switch to `update_game_deadline`, which the scheduler already uses and
      which commits.
- [ ] Concurrency: `POST /process_turn` **does** correctly acquire its lock (`async with
      lock:` — an earlier survey claim that it only checks `lock.locked()` was wrong),
      but an `asyncio.Lock` is per-process and won't survive a second uvicorn worker. Add
      `expected_phase_code` to `GameRepo.save_state`, raise `StaleGameError` → 409. Drop
      the `lock.locked()` check in `api/shared.py:127-136`, which pretends to guard
      without acquiring.
- [ ] New `GET /games/{id}/orders_status` + `POST /process_turn?require_all=true`.
      **Default stays `false`** so no existing test changes; both clients pass `true`,
      the deadline scheduler never does.
- [ ] `restore/{snapshot_id}` is a stub — snapshots store the *view*, which
      `state_from_dict` can't read. Add `state_json` to the snapshot payload (purely
      additive, so `/history` and `/replay` keep working) and make restore of a
      pre-change snapshot fail loudly with 409.
- [ ] **Un-skip the four scheduler tests** (`test_api_scheduler.py:58,78,106,129`). Their
      stated reason ("session isolation") is stale: `update_game_deadline` opens its own
      session and commits, so once `set_deadline` uses it the value *is* visible
      cross-session. Rewrite the 70-second reminder test to call the reminder branch
      directly instead of `time.sleep`.
- [ ] New `tests/test_persistence_database_service.py` — first direct coverage of the
      1033-LOC DAL. Start narrow: `update_game_deadline` round-trip incl. `None`,
      snapshot create/get, `get_players_by_game_id`, and an explicit test that `commit()`
      is a no-op so nobody reintroduces the detached-mutation pattern.

## PR 6 — `test-hygiene` (last, small)

- [ ] `pytest.ini`: `asyncio_mode = auto`; **remove `--disable-warnings`** — that flag is
      what hid the coroutine-never-awaited warnings. Triage the resulting noise with
      targeted `filterwarnings`, not by restoring the blanket flag.
- [ ] `@pytest.mark.asyncio` on `test_convoy_functions.py:229,235` — the only two
      genuinely silent async skips outside the uncollected files (an earlier claim of ~19
      was wrong).
- [ ] Delete `tests/bot_test_runner.py` (never collected; 5 dead async functions).
- [ ] Ratchet the coverage floors to just under the new measured values; refresh the
      dated comments in `test.yml` / `.coveragerc`.
- [ ] Add `frontend` to required status checks via `gh api`. Precondition met: the job was
      green on PR #13 and on the resulting `main` merge commit (`v2.7.20`).

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

**UNBLOCKED as of `v2.7.22`** — PR4 removed the bot's `rendering.map` import, which was
the last src consumer of the renderer's topology half, so finding 2 below is now spent and
V2–V4 can start. V5 was always independent. Goal: remove the remaining pre-rewrite dead
and duplicated code, and bring `src/rendering/` up to the engine's standard — single
topology source, focused modules, correct overlays.

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
3. **`engine/province_mapping.py` (365 lines) is almost retired.** Remaining consumers:
   `map.py:289` (type lists used only for *warnings* inside the doomed `_parse_map_file`)
   and `telegram_bot/orders.py` (a function-local `normalize_province_name` import on the
   **user-typed-order path only** — PR4 stopped calling it on `legal_orders` strings). It
   also sits inside `src/engine/`, violating "engine = pure rules logic". V2 should fold
   the alias table into `engine/orders/parser.py` and drop the bot's normalization
   entirely, letting the server's single grammar resolve aliases.
4. **`map.py` is a 3,150-line God class**: one `Map` class, ~80 methods (mostly static),
   26 blanket `except Exception`, duplicated primitives (`_draw_checkmark` vs
   `_draw_success_checkmark`, `_draw_status_x` vs `_draw_failure_x`), and a redundant
   public pair (`render_board_png_orders` at `:1382` is a thin alias over
   `render_board_png_with_orders` at `:1320`).
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

### V2 — Delete the renderer's topology half; retire `province_mapping` ✅ DONE 2026-07-28 (`v2.7.24`, branch `renderer-topology-v2`, pushed not merged)

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

### V3 — Split `map.py` into focused modules

3,150 lines / one class is the last pre-rewrite God object. Keep this **mechanical** —
move code, don't redesign rendering (same rule the rewrite used for the M6 split). Note
PR4 already creates `rendering/view_adapter.py`; slot it into this layout.

- [ ] Proposed layout (adjust with rationale here if reality disagrees):
      - `rendering/cache.py` — `MapCache` + module-level `_map_cache`.
      - `rendering/board.py` — SVG load/parse, coordinate extraction, province coloring,
        ocean pattern, `render_board_png`, phase-info banner.
      - `rendering/overlays.py` — `_draw_comprehensive_order_visualization` + every
        arrow/marker primitive (`_draw_arrow`, curved/dashed/dotted variants, standoff,
        conflict, checkmark/X).
      - `rendering/legend.py` — `_draw_legend` (285 lines) + mini-icon helpers.
      - `rendering/icons.py` — army/fleet icon loading & drawing.
      - `rendering/map.py` stays as a thin facade re-exporting `Map` — or update the
        importers (`api/routes/maps.py`, `api/routes/admin.py`, `telegram_bot/maps.py`,
        tests) and delete the facade; pick one, note it here.
- [ ] Deduplicate while moving (pure duplicates, safe to merge):
      `_draw_checkmark`≡`_draw_success_checkmark`, `_draw_status_x`≡`_draw_failure_x`;
      fold `render_board_png_with_orders` into `render_board_png_orders` (one public
      name, the alias dies).
- [ ] Narrow the 26 blanket `except Exception` blocks to what each site actually expects
      (most guard font/icon loading and SVG parsing); let programming errors raise.
- [ ] Type hints on every moved signature (mandatory repo-wide; ruff must stay clean).
- [ ] **Done when:** no module in `rendering/` exceeds ~800 lines, suite + the map E2E
      smoke green, `ruff check src/` clean.

### V4 — Overlay correctness polish

- [ ] **Merged convoy chains:** in `order_overlay.py`, group all `Convoy` orders sharing
      the same (origin, dest) into one viz entry whose `convoy_chain` lists every
      convoying fleet in path order, instead of one single-fleet entry per fleet.
- [ ] **Dislodged styling:** `_STATUS_BY_CODE` maps `DISLODGED → "success"`, which draws
      a green check on a unit that just got thrown out. Give dislodgement its own status
      (the renderer already has dislodged markers + `dislodged_coords` support in
      `_draw_comprehensive_order_visualization`) and draw retreat arrows from the
      dislodged-offset position, not the province center.
- [ ] **Retreat-phase resolution maps:** verify `/games/{id}/generate_map/resolution`
      renders sensibly for retreat and adjustment phases (the `last_resolution` column
      persists whatever phase was adjudicated), not just movement.
- [ ] Keep/extend the E2E smoke: create game → submit orders → orders map → process →
      resolution map; assert non-trivial PNG sizes and no render warnings in the log
      (pattern exists in `tests/test_order_overlay.py` + `test_game_service.py`).
- [ ] **Done when:** a convoyed move with a 2-fleet chain renders one continuous chain,
      dislodged units are visually distinct from successful holds, suite green.

### V5 — Repo hygiene (small; independent — do anytime)

- [ ] Delete tracked backup cruft: `maps/standard_backup.svg`,
      `maps/standard_backup_20250730_145707.svg`, `maps/standard.map.backup`
      (git history is the backup). Check nothing globs `maps/*` for variants first.
- [ ] Decide the fate of the `standard-v2` map variant (`maps/v2.svg`,
      `Map._resolve_svg_path("standard-v2")`, two `test_standard_v2_*` files): it is not
      reachable from any production flow (games are created with `map_name="standard"`).
      Either wire it up as a real selectable variant or delete the SVG + tests. Ask the
      maintainer if unsure — don't silently keep dead product surface.
- [ ] Modernize or prune the pre-rewrite print-style test scripts
      (`test_order_visualization.py`, `test_visualization.py`,
      `test_standard_v2_map.py`): drop `main()` runners, emoji banners, `sys.path`
      hacks; keep the actual assertions as plain pytest tests. (`bot_test_runner.py` is
      already covered by Track A's PR6.)
- [ ] **Done when:** `tests/` contains only pytest-idiomatic files and `maps/` only
      shipping assets.

---

## Definition of done (both tracks)

- [ ] **Track A acceptance:** a game plays end-to-end (movement, retreat, build) from
      both the browser and Telegram — the manual check above completed and each step
      checked off.
- [ ] Frontend CI job green and required.
- [ ] `src/rendering/` has zero topology knowledge beyond what it imports from
      `engine.map_loader`; `engine/province_mapping.py` is gone; no rendering module
      over ~800 lines.
- [ ] Overlays: merged convoy chains, distinct dislodged styling, retreat arrows from
      dislodged positions.
- [ ] Full suite green **with a DB**, ruff clean, coverage gates hold, CI green on
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

- The Telegram bot tests stub deep internals; PR4 will churn them — port assertions to
  the new flow rather than deleting coverage.
- The rendering split (V3) is import-graph surgery over a file with 26 broad excepts —
  breakage may hide at runtime, not test time. Run the E2E smoke (orders + resolution
  PNGs) after every move, not just at the end.
- `visualization_config.json` is live again as of V0 — if arrow styling looks different
  in a diff of rendered PNGs, that's the intended restore, not a regression.
- Renderer output is byte-cached (`/tmp/diplomacy_map_cache` + in-memory); clear it when
  eyeballing visual changes (`Map.clear_map_cache()` or delete the tmp dir).
