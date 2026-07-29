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
- **Track C — Security hardening & missing gameplay features: DONE — all of C1-C4.**
  Added 2026-07-29 from a direct old-vs-new comparison requested by the maintainer. Four
  findings (C1-C4), each verified by reading the actual code. **C4** — decision made,
  executed end to end via Track D's D1-D5. **C3** — engine+API layer via Track D's D3
  (`v2.7.35`), client UX via `v2.7.47` (PR #39): Telegram `/draw`+`/nodraw` and a
  `/status` tally, plus a draw-vote control in the React game view, so a human can end a
  game by agreement without a raw API call. **C2** — `v2.7.46` (PR #38): per-email and
  per-IP rate limiting on `/auth/login`/`/auth/token`/`/auth/register`, 429 +
  `Retry-After`, no enumeration side-channel, no unbounded bucket growth. **C1** —
  `v2.7.48` (PR #40): the `security` CI job is a real gate at last, and was *proved* to
  fail on a deliberate finding via throwaway PR #41 before being merged.
- **Track D — Full DAIDE protocol support: DONE — all of D1-D5 merged.** Added
  2026-07-29 at the maintainer's explicit request ("I want the full DAIDE support as
  well") after Track C's C4 flagged the current server as a non-conformant text stub.
  Five PRs (D1-D5) in dependency order — see the Track D section below. **D1 merged
  (`v2.7.34`, PR #27)** — token vocabulary + DCSP wire framing. **D2 merged (`v2.7.37`,
  PR #31)** — clause encode/decode bridge. **D3 merged (`v2.7.35`, PR #29)** — shared
  draw-vote/concede mechanism, also satisfies Track C's C3. **D4 merged (`v2.7.40`,
  fix `v2.7.41`, PR #33)** — message protocol + the first real asyncio TCP listener;
  caught and fixed a real production-safety bug in review (eager game-creation on every
  deploy — see the D4 section). **D5 merged (`v2.7.43`)** — the end-to-end raw-socket
  test proving the whole wire protocol composes correctly over one continuous real
  connection (IM→RM→NME→HLO→MAP→MDF→SCO→NOW→SUB→THX, then
  `process_turn`→`notify_game_processed`→NOW/ORD back on the same socket), plus
  `architecture.md` brought up to date with the real `src/server/daide/` package and its
  permanent press-relay limitation. **Track D is complete**: a real DAIDE bot (or this
  e2e test standing in for one) can connect, negotiate, submit orders, and receive
  results against a `GameService`/Postgres-backed game, and the listener starts with the
  API process.
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
- **Track E — Client UX: ACTIVE. E1, E2, E3 all merged; E4 is the only open task.** Added
  2026-07-30 at the maintainer's request. Two read-only audits (web + Telegram) found the
  same structural gap from opposite directions: **neither client could tell a player what
  happened to their orders**, because the resolution the engine computes was discarded by
  the HTTP layer. **E1** `v2.7.52` (PR #45) — resolution exposed on `process_turn` + a new
  read endpoint, overlay maps made browser-reachable, and a real authorization hole closed
  (any logged-in stranger could end a turn for all seven powers). **E2** `v2.7.51` (PR #44)
  — web game screen restructured. **E3** `v2.7.53` (PR #46) — Telegram, led by
  `api_client.py` discarding every server error message. **E4** (web results panel + the
  fleet-reported-as-army defect E1 shipped) is in flight. Suite at `v2.7.53`: **1332 passed,
  11 skipped, 10 xfailed**, engine 93.42%, overall 68.12%; frontend 21 files / 109 tests.
- **Track A's manual end-to-end check is still outstanding and still cannot be delegated**
  (needs a live bot token and a human at a Telegram client — see Track A's "Final
  acceptance"). Note as of 2026-07-30 the maintainer confirmed **there is no production
  server currently running**, which makes `CLAUDE.md`'s "Production infrastructure (AWS)"
  section describe infrastructure that isn't there; the CI `Deploy` workflow has never
  succeeded (40/40 runs failed on `sts:AssumeRoleWithWebIdentity`) and that is expected,
  not a regression to chase.
- **Suite baseline (post-C1+C2+C3, on `main` at `v2.7.48`):** **1293 passed, 11 skipped,
  10 xfailed**; ruff clean; engine coverage 93.42% (≥92), overall 66.12% (≥60);
  `bandit -r src/ -ll` and `pip-audit -r requirements.txt` both exit 0. Verified
  independently by the driver against a real local Postgres on each branch *after*
  rebasing onto the others' merged `main` — not taken from the subagents' reports. The
  suite now runs under **pytest 9.1.1** (see C1: the `>=8.4.0,<9.0.0` pin carried
  PYSEC-2026-1845).
- **Historical baseline (post-V4+V5):** 842 passed, 11 skipped, 10 xfailed, 1 warning
  (only the pre-existing unrelated `StarletteDeprecationWarning` — V5 removed the suite's
  last `PytestReturnNotNoneWarning`); ruff clean; engine coverage 93.02%, overall 62.43%.
- **A count that looks alarming but is fine:** V2's suite drop (890 → 840) is *entirely*
  deleted dead-module tests — 34 in `test_province_mapping.py` plus 16 elsewhere
  exercising the retired `normalize_province_name` / `normalize_order_provinces` / `Map`
  topology-query API. No real coverage was lost.
- **Last updated:** 2026-07-29, end of session. Track A complete except the manual check
  (PR1–PR6, `v2.7.17`–`v2.7.25`); Track B fully complete (`v2.7.19`/`v2.7.24`/`v2.7.26`+
  `v2.7.28`/`v2.7.30`/`v2.7.31`); **Track C fully complete** (C4 via Track D, C3 via D3 +
  `v2.7.47`, C2 `v2.7.46`, C1 `v2.7.48` — PRs #38/#39/#40 merged, throwaway #41 closed);
  **Track D fully complete (D1-D5, `v2.7.34`-`v2.7.43`, PRs #27/#29/#31/#33/#35 all
  merged)**. `main` is green (`8d70023`), no open PRs, no stale branches.

  Execution note for whoever picks this up next: C1/C2/C3 were built by three Sonnet
  subagents working in parallel git worktrees (one per task, each against its own
  Postgres database), with an Opus driver verifying every claim by re-running the gates
  itself. That caught three things the agents' own reports did not: C2's unbounded bucket
  growth, C3's two failing frontend tests (the sandbox had no Node until the driver
  installed one — the agent correctly flagged the gap instead of claiming a pass), and a
  wrong triage the driver itself had handed to the C1 agent (see C1's `app.py:497` note,
  where the agent's pushback was right and the driver's instruction was wrong). **Re-run
  the gates yourself; do not merge on an agent's say-so.**

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

# Track C — Security Hardening & Missing Gameplay Features

## Why this track exists

The maintainer's stated goal for the rewrite was not just "port the old engine to modern
libraries" but "don't carry over the old implementation's vulnerabilities" and "support
more UI surfaces" (Telegram, done in Track A). A direct comparison of
`old_implementation/` against `new_implementation/src/` on 2026-07-29 found four gaps
that neither Track A nor Track B's findings covered — two are security regressions
relative to what a public-facing service needs (not present in the old codebase either,
but the old one was never deployed as a public HTTP service the way this one is), and two
are gameplay-completeness gaps inherited from an incomplete port. Each was verified by
reading the actual code, not inferred from a docstring or comment.

**This track has no single acceptance criterion** the way Track A does — it's four
independent findings. Execute them in the order below (C1/C2 are cheap and
security-critical; C3 is a real gameplay gap; C4 needs a maintainer scope decision before
any code is written).

## C1 — The CI "security" job cannot fail a build

**Finding:** `.github/workflows/test.yml:139-144` — both actual scan steps in the
`security` job have `continue-on-error: true`:

```yaml
- name: Run safety check (informational)
  run: safety check -r requirements.txt
  continue-on-error: true

- name: Run bandit security check (informational)
  run: bandit -r src/ -f json -o bandit-report.json
  continue-on-error: true
```

`security` is listed in `CLAUDE.md` as one of the two **required status checks** gating
`main`. But a required check that always exits 0 regardless of findings provides zero
protection — it is required in name only. This is the opposite of the maintainer's stated
goal: the whole point of the rewrite was to not silently carry forward vulnerable
dependencies the way the old implementation did, and right now a genuinely vulnerable
dependency bump or a bandit-flagged code pattern (e.g. a new `eval`, a hardcoded secret)
would merge to `main` without so much as a warning in the PR checks UI — only a
downloadable artifact nobody looks at by default.

- [x] Change `bandit` from `continue-on-error: true` to failing the job on medium+
      severity findings (`bandit -r src/ -ll` — `-ll` sets the severity floor to medium,
      which excludes the noisiest low-severity findings that would otherwise need a mass
      triage before this can be turned on). Run it locally first and fix or
      `# nosec`-annotate (with a one-line reason) any findings before flipping the switch,
      so turning on enforcement doesn't itself red the build.
- [x] Change `safety check` similarly, but expect more friction: `safety check` needs a
      free-tier API key or a switch to the newer `safety scan` / `pip-audit` command as of
      2025-era safety versions — confirm which one the CI runner's `pip install safety`
      resolves to and that it can run non-interactively in CI before wiring it to fail the
      build. If `safety` can't run unauthenticated in CI, switch to `pip-audit` (no auth
      required, actively maintained, reads `requirements.txt` directly) rather than leaving
      the step informational.
- [x] Keep the bandit JSON artifact upload (useful even with a hard gate), but the job's
      overall exit code must now reflect real findings.
- [x] **Done when:** deliberately introducing a known-bad pattern (e.g. a branch with
      `subprocess.call(user_input, shell=True)`) makes the `security` check fail on that
      PR, verified with `gh pr checks`, then revert the deliberate finding before merging
      anything. *(Verified locally on branch `security-ci-gate`: adding
      `subprocess.call(user_input, shell=True)` to a file under `src/` makes
      `bandit -r src/ -ll` flag it as `B602 HIGH` and exit 1; the file was fully reverted
      before committing (`git status`/`git diff` clean).* **On-PR demonstration done by the
      driver 2026-07-29:** throwaway branch `ci-gate-proof` off `security-ci-gate` added
      `src/server/_ci_gate_probe.py` containing exactly that call, opened as PR #41 →
      `gh pr checks 41` reported **`security  fail`**, and the failing step in the run log
      is `Run bandit security check` (`bandit -r src/ -ll -f json -o bandit-report.json`),
      not some unrelated step. The `bandit-report` artifact was still uploaded on the
      failing run, confirming `if: always()` survives the hard gate. PR #41 closed and
      branch deleted immediately after; nothing from it reached `main`. The same commit
      minus the probe (PR #40) has `security  pass` — so the check is genuinely
      finding-sensitive, not merely red.

**Implementation notes (branch `security-ci-gate`):**

- **`safety` → `pip-audit` swap.** `safety check` (v3.8.1) exits 0 while printing
  "0 vulnerabilities reported, 29 vulnerabilities ignored" — it only scans pinned
  versions, and `requirements.txt` uses range specifiers throughout, so it silently
  skipped known CVEs in PyJWT, Pillow, requests, python-multipart, cairosvg, etc. A gate
  that skips almost everything is worse than no gate. `pip-audit` (2.10.1) runs
  unauthenticated, reads `requirements.txt` directly, and correctly surfaced one real
  finding (see below). `.github/workflows/test.yml`'s `security` job now installs
  `bandit pip-audit` (not `safety`) and runs
  `pip-audit -r requirements.txt --progress-spinner=off` as a hard gate before bandit.
- **pytest advisory (PYSEC-2026-1845).** `pip-audit` flagged `pytest==8.4.2`, fixed in
  9.0.3. Tried the real fix first: widened the pin to `pytest>=9.0.3,<10.0.0` in
  `requirements.txt` and ran the full suite (`pytest-asyncio>=1.1.0,<2.0.0` already
  covers the resolved 1.4.0, no change needed there). Result: **1275 passed, 11 skipped,
  10 xfailed** — identical to the pre-upgrade baseline, no code or test changes required.
  `pip-audit -r requirements.txt` now reports "No known vulnerabilities found" (exit 0).
- **`# nosec` sites** (all carry a same-line or immediately-above reason comment):
  - `src/rendering/board.py:161` — B314 (`ET.parse`): `svg_path` resolves to the bundled
    repo asset `maps/standard.svg`, never untrusted input.
  - `src/server/api/routes/dashboard.py:230,237` — B608 (f-string SQL): `table_name` is
    checked against `ALLOWED_TABLES` before either query is built; `limit`/`offset` are
    bound parameters, not interpolated. Query left unrewritten per the allowlist.
  - `src/server/_api_module.py:290` — B104 (bind `0.0.0.0`): dev-only `__main__` fallback
    (production starts via `uvicorn ... --host 127.0.0.1` under systemd, see
    `infra/terraform/user_data.sh`); mirrors the documented local-dev command in
    `CLAUDE.md` which binds all interfaces on purpose so other LAN devices can reach it.
  - `src/server/daide/server.py:53` — B104: the DAIDE listener must accept connections
    from external DAIDE clients; binding loopback would break the protocol.
  - `src/rendering/cache.py:27` and `src/server/api/routes/maps.py:189,193` — B108
    (hardcoded `/tmp` path): documented cache/render-scratch locations
    (`CLAUDE.md`: "cached ... at `/tmp/diplomacy_map_cache`"); the app runs on a
    single-tenant EC2 host with no other local users, so there's no multi-user `/tmp`
    collision/symlink risk. *(These 3 sites were not in the original triage list handed
    down for this task — found and triaged independently while clearing the gate.)*
  - **Not suppressed — fixed instead:** `src/server/telegram_bot/app.py`'s notification
    server (port 8081) was flagged B104 too and the original triage called it deliberate
    like the other two binds, but that turned out to be wrong on inspection: its caller
    (`NOTIFY_URL` in `server/api/shared.py`) defaults to `http://localhost:8081/notify`,
    both systemd units (`diplomacy-api`, `diplomacy-bot`) run on the same EC2 host, and
    `/notify` (`telegram_bot/notifications.py`) has **no authentication** — an open relay
    that lets anyone with a `telegram_id` push arbitrary messages through the bot if ever
    reachable. The only thing keeping it safe today is that the AWS security group
    doesn't open port 8081 (incidental, not defense-in-depth). Changed the default bind
    to `127.0.0.1` (overridable via `DIPLOMACY_NOTIFY_HOST` for a future split-host
    deployment) instead of adding a `# nosec`.
  - B324 (`hashlib.md5`, 3 sites — `rendering/cache.py`, `rendering/overlays.py`,
    `server/response_cache.py`) and B113 (`requests.*` without timeout, 4 sites —
    `telegram_bot/api_client.py` x3, `telegram_bot/channel_commands.py`) were fixed in
    code (`usedforsecurity=False`; a shared `DEFAULT_API_TIMEOUT = 10` constant in
    `api_client.py`), not suppressed — see diff.

## C2 — No brute-force protection on password auth

**Finding:** `src/server/api/routes/auth.py` — `/auth/login` (`:278-295`), `/auth/token`
(`:298-312`), and `/auth/register` (`:251-275`) have no rate limiting, lockout, or delay
of any kind. Compare to `/auth/link_telegram`, which *does* have one
(`_check_link_rate_limit`, `:449-470`) — so the codebase already has the pattern, it just
wasn't applied to the password-auth surface, which is the one actually exposed to
credential-stuffing bots on the open internet (production has no HTTPS yet either, per
`CLAUDE.md`'s infra section — a separate, already-tracked deployment gap, but it makes
this worse in the meantime: credentials transit in cleartext to an endpoint anyone can
hammer unlimited times). There is no global rate-limiting middleware in `_api_module.py`
either (`grep -rn "rate.limit\|slowapi\|RateLimit" src/` matches only the telegram-link
helper).

- [x] Add per-IP (and per-email, to stop distributed attacks against one account) rate
      limiting to `/auth/login` and `/auth/token`, reusing or generalizing the existing
      `_check_link_rate_limit` pattern in the same file rather than inventing a second
      mechanism. A sensible starting point: 5 failed attempts per email per 15 minutes,
      plus a coarser per-IP ceiling; return 429 with a `Retry-After` header rather than a
      misleading 401.
- [x] Add a coarser per-IP limit to `/auth/register` (distinct concern: account-creation
      spam, not credential guessing) — no need for per-email keying since there's no
      existing account to target.
- [x] Failed attempts must **not** distinguish "no such user" from "wrong password" in
      timing or counting — the current 401 messages are already unified
      (`"Invalid email or password"`), keep that property when adding limiting logic (an
      early-return on unknown email would create a timing side-channel and should count
      against the same per-IP bucket as a real wrong-password attempt).
- [x] Test: hammer `/auth/login` with a bad password past the threshold in a test using
      `TestClient`, assert 429 + `Retry-After`, assert a *correct* login for a different
      account/IP still succeeds (bucket isolation), assert the limiter resets after the
      window (use a fake clock, not a real `sleep`).
- [x] **Done when:** the new tests pass, `ruff check src/` clean, and manually confirmed
      that 429s stop appearing once the window rolls over (no permanent lockout without an
      unlock path — a permanently locked legitimate user is its own denial-of-service).

**Implementation notes (`v2.7.46`):** `_check_link_rate_limit` was generalized into shared
`_check_rate_limit`/`_record_attempt` helpers over one module-level bucket dict
(`_rate_limit_attempts` in `src/server/api/routes/auth.py`), keyed by namespaced strings
(`login_email:`, `login_ip:`, `register_ip:`, `link_ip:`/`link_tid:`) rather than a second
mechanism. Decisions that go beyond the letter of the spec above:
- **Thresholds:** login/token per-email 5 attempts / 15 min, per-IP 20 attempts / 15 min
  (coarser, since one IP can legitimately serve many users — e.g. NAT/office wifi);
  register per-IP 20 attempts / hour (coarser still — account-creation spam, not
  credential guessing).
- **`/auth/login` and `/auth/token` share the same buckets** (keyed by email, not by which
  endpoint was hit) — they're the same password-guessing surface (JSON body vs. OAuth2
  form), so an attacker switching endpoints must not get a fresh budget.
- **What counts:** only *failed* login/token attempts are recorded (`_record_attempt`
  happens in the failure branch only), so normal repeated successful logins — including
  the existing test suite — never burn the budget. `/auth/register` records every call
  regardless of outcome, since the concern there is creation-attempt volume, not
  correctness.
- **No enumeration timing/counting side-channel:** added `_DUMMY_PASSWORD_HASH`, a
  precomputed bcrypt hash of a fixed constant. `/auth/login` and `/auth/token` always run
  `bcrypt.checkpw` — against the real hash if the user exists, against the dummy hash if
  not — with no early return on unknown email, so both cases take the same code path,
  roughly the same time, and land in the same rate-limit-recording branch.
- New tests in `tests/test_auth_rate_limiting.py` (9 tests); `tests/conftest.py`'s autouse
  reset fixture was renamed `reset_auth_rate_limiters` and now calls a single
  `auth.reset_rate_limits()` covering all four buckets (previously only cleared the
  telegram-link dict).

**Two findings from the driver's review of C2 (both now fixed/verified in `v2.7.46`):**

1. **The bucket store must not be a `defaultdict`.** The first pass read buckets via
   `_rate_limit_attempts[key]`, so *every key that was merely checked* became a permanent
   entry, and expired buckets were only ever reclaimed if that exact key was touched again
   — which an attacker hammering `/auth/login` with random, never-repeated emails never
   does. That is unbounded, attacker-controlled memory growth on an unauthenticated public
   endpoint (production is a 1 GB `t3.micro`), i.e. the task's own threat model. Now a
   plain `dict`: `_check_rate_limit` reads with `.get()` and returns early on a miss, a
   bucket that purges to empty is `del`eted, and `_record_attempt` is the only thing that
   may create a key. Regression test
   `test_rate_limit_dict_does_not_accumulate_dead_keys` asserts on `len()` of the dict
   itself, and was confirmed to **fail** against the pre-fix code (26 permanent empty-list
   entries) — a test that only checked the 429 behavior would have passed either way.
2. **The per-IP buckets depend on uvicorn's proxy-header handling — do not disable it.**
   `request.client.host` is only the real client IP because uvicorn defaults to
   `proxy_headers=True` with `forwarded_allow_ips="127.0.0.1"`, and nginx (which sets
   `X-Forwarded-For`/`X-Real-IP`, see `infra/terraform/user_data.sh`) proxies from
   loopback. If anyone ever passes `--no-proxy-headers` or narrows `forwarded_allow_ips`,
   **every user collapses into a single `127.0.0.1` bucket** and the per-IP limits become
   a self-inflicted denial of service on the whole service rather than a protection.

## C3 — No draw or concede mechanism; a game can only end by 18-center solo win

**Finding:** `src/engine/types.py:99-104` — `GameStatus` has exactly three values
(`FORMING`, `ACTIVE`, `COMPLETED`), and the only place anything sets `COMPLETED` is
`src/engine/game.py:132`, gated on `VICTORY_CENTERS = 18` (`types.py:120`). There is no
engine-level draw, concede, or vote-to-end mechanism at all — contrast with
`old_implementation/diplomacy/engine/game.py:745` (`draw(winners=None)`) and its
`has_draw_vote()`/`count_voted()`/`clear_vote()` companions (`:877-895`), which let a game
finish by agreement among survivors. In real Diplomacy the large majority of games end in
a negotiated draw, not an 18-center solo — **without this, a new-implementation game that
doesn't produce a solo winner has no way to ever finish.**

This is easy to mistake for already-covered ground because
`src/server/api/routes/channels.py:319-374` has `POST /games/{id}/channel/proposal` +
`GET /games/{id}/channel/proposal/{message_id}`. Read closely
(`telegram_bot/channels.py`'s `post_proposal_with_voting`/`get_proposal_results`), that's
a generic Telegram/Discord poll-with-reactions feature for any text a player wants to put
to a vote — it never touches `GameStatus`, is not aware of which powers are eliminated,
and has no server-side quorum rule. It's a social feature sitting next to the actual gap,
not a substitute for it.

- [x] **Engine, vote state, API, and tests — all done, via Track D's D3** (`v2.7.35`,
      PR #29; see the D3 section under Track D for the full detail and verification
      evidence). `GameState.winners: frozenset[str] | None`, `Game.draw(winners=None)`;
      `games.draw_votes` JSON column mirroring `pending_orders`, cleared every processed
      turn, excluding eliminated powers from quorum; `GameService.submit_draw_vote`
      (auto-finalizes on quorum)/`get_draw_votes`/`concede` (distinct from a draw — does
      not end the game); `POST /games/{id}/draw_vote`, `GET .../draw_vote_status`,
      `POST .../concede`. Engine-level and `GameService`-scenario tests both exist and
      pass. D3 implemented this exactly as specified below (kept for reference, not
      because it's still open):
      <details><summary>original spec</summary>

      Engine: add a way to mark a `GameState` as drawn among a set of winners without
      going through `adjudicate_movement`/`adjudicate_adjustments` — mirror the old
      implementation's shape (`draw(winners=None)` defaulting to all surviving,
      non-eliminated powers) but as a pure function. Vote state: per-power draw votes,
      cleared each phase, excluding eliminated powers from quorum (`Game.eliminated_powers`).
      API: `POST /draw_vote`, `GET /draw_vote_status`, auto-finalize on the vote that
      completes quorum, plus a **concede** path distinct from a draw. Tests: engine-level
      draw resolution, API auth checks, one full `GameService`-driven scenario test.
      </details>
- [x] **Clients — done (`v2.7.47`, branch `draw-vote-clients`).** Both are thin --
      they only call D3's existing API, no client-side game logic:
      - Telegram bot: `/draw [game_id]` casts a yes vote, `/nodraw [game_id]` withdraws
        it (`src/server/telegram_bot/games.py::draw`/`nodraw`, shared impl
        `_cast_draw_vote`), both resolving game/power via the same
        `resolve_game_and_power` helper `/status` uses. `/status` grows a "N/M voted
        for draw" line (`GET /draw_vote_status`, wrapped in try/except so a failure
        degrades gracefully rather than breaking `/status`). Registered in `app.py`,
        documented in `ui.py`'s `/help` text and `docs/TELEGRAM_BOT_COMMANDS.md`.
      - Frontend: a "Draw vote" section in `frontend/src/pages/GameView.tsx` (right
        after the Orders section), shown only when the logged-in user has a power in
        the game and the game is still `ACTIVE` (hidden once `COMPLETED`, and shown
        regardless of `phase_type` -- a draw vote is not phase-restricted the way
        order submission is). Shows the live tally from `GET /draw_vote_status`, a
        "Vote for draw" button, and a "Withdraw draw vote" button once this power has
        voted; reaching quorum surfaces a toast and the phase banner already shows
        "— game over" once `load()` refetches state. Tests added to
        `GameView.test.tsx` (tally rendering, casting a vote, control absent for a
        powerless user).
      - Python-side tests: `tests/test_draw_vote_bot.py` (8 new tests, no DB
        dependency, mocks `api_get`/`api_post` the same way
        `test_interactive_orders.py` does).
      - **Departure from the brief:** no bot/frontend concede command was added --
        the C3 checklist text above only calls out draw-vote client UX ("Telegram bot
        command... and a frontend button"), and concede isn't mentioned in it; adding
        one would be scope creep beyond what this checklist item asks for.
      - All gates run and green: `ruff check src/`; full pytest suite (1283 passed,
        11 skipped, 10 xfailed); engine coverage 93.42% (floor 92%); overall coverage
        66.02% (floor 60%); `npx tsc -b --noEmit`; `npm run test:run` (21 files, 102
        tests, 0 failures); `npm run build`.
- [x] **Done when:** a human can actually cast a draw vote from the Telegram bot or the
      frontend (not just via a raw API call) and see the game end without an 18-center
      solo. The mechanism itself (engine coverage floor, scenario test, quorum logic)
      was already done and verified in D3; the client paths above are now wired to it.

## C4 — The "DAIDE" server does not implement the DAIDE protocol — **DECISION MADE: (a), implement it**

**Finding (unchanged):** `src/server/daide_protocol.py` (161 lines) is a hand-rolled
ASCII text protocol reusing a few DAIDE token names as literal string prefixes. The real
DAIDE protocol is binary (4-byte IM/RM/DM message header, then a token stream where every
clause is a 2-byte token). No unmodified real-world DAIDE bot can connect to this server
today.

**Maintainer decision (2026-07-29): (a) — implement the real protocol.** Superseded by
**Track D**, below, which is the full execution plan. This section is kept only as the
historical record of the finding; do not duplicate tasks here — see Track D.

---

# Track D — Full DAIDE Protocol Support

## Why this track exists

The maintainer decided C4 should be a real implementation, not a rename or deletion:
interoperating with the existing DAIDE bot ecosystem (DumbBot, Albert, and other
standalone Diplomacy AIs that speak this protocol) is a first-class goal, not a nice-to-have.

## Ground rules (read before writing any code)

- **Clean-room, not a port.** `old_implementation` (Philip Paquette's `diplomacy` package)
  is **AGPL-3.0 licensed**; `new_implementation` — and the repo root — currently ship with
  **no LICENSE file at all**. Copying its `daide/` source (verbatim or lightly edited)
  into this repo would drag AGPL's copyleft — including its network-source-disclosure
  clause, which matters because this runs as a public API on EC2 — into a codebase that
  has made no such commitment. **Use `old_implementation/diplomacy/daide/` and its
  `tests/` fixtures only as a read-only reference** to check wire-format correctness
  (token byte values, message framing, and expected byte sequences are dictated by the
  external DAIDE specification itself, not by Paquette's creative expression — reproducing
  the *same required values* for protocol compliance is not the same as copying his code).
  Write fresh implementations with this codebase's own conventions (frozen dataclasses,
  type hints, pure functions in the protocol-encoding layer). **Do not `cp`, do not
  paste function bodies, do not carry over his docstrings/comments/file layout.** If a
  subagent's diff looks structurally identical to the old file with names changed, that's
  a sign to rewrite it, not rename it.
- **DAIDE draw negotiation (`DRW`) needs an engine-level draw mechanism that doesn't exist
  yet — this is the same gap Track C's C3 already found.** Rather than building a
  DAIDE-only shadow implementation, **D3 below builds the shared draw/concede mechanism
  once** (engine + `GameRepo`/`GameService` + generic, non-DAIDE API endpoints), and D4's
  DAIDE `DRW`/`SLO` support is a thin adapter over it. This closes C3's engine+API layer as
  a side effect; C3's remaining item after D3 lands is just the Telegram/frontend UX (a
  `/draw` bot command and a frontend button) — update C3's checklist when D3 merges rather
  than duplicating the work under two names.
- **Currently nothing starts a DAIDE server at all** — `daide_protocol.py` has zero
  importers outside its own test file (confirmed via
  `grep -rln "daide_protocol\|DAIDEServer" . --include=*.py` excluding `old_implementation`
  and `tests/test_daide_protocol.py`). This isn't just a wire-format fix; D4 also has to
  wire a listener into the running app for the first time, following the existing
  `asyncio.create_task(deadline_scheduler())` pattern in `_api_module.py`'s `lifespan`
  (`_api_module.py:139`) — use native `asyncio.start_server`, not Tornado (nothing else in
  this codebase depends on Tornado; don't add it as a dependency for this).
- **Press (`SND`/`FRM`, the `PRP`/`ALY`/`XDO`/... negotiation grammar) is the deepest part
  of the real spec and the least essential for interoperability.** Scope it as: syntax-
  validate bracket structure and forward the token payload opaquely between clients
  (peer-to-peer negotiation content is the bots' concern, not the server's) rather than
  deep-parsing the full press grammar. Full press-content parsing is explicitly **out of
  scope** for this track — note it in `architecture.md` as a known limitation, not a silent
  gap.
- **New package location:** `src/server/daide/` (replacing the single
  `src/server/daide_protocol.py` file), mirroring how `telegram_bot/` is already a
  subpackage of `src/server/`. Update every importer.
- Standard map only (matches this codebase's existing "map variants beyond `standard` are
  out of scope" rule) — the token tables only need `maps/standard.map`'s province set.

## Execution model

Same as Track A: **one Sonnet subagent per PR**, in dependency order, driver
(the session running this) verifies locally and reads the diff before opening a PR — with
one addition specific to this track: **the driver must also verify the clean-room rule
above** (diff the new files against the corresponding old-implementation file by eye; if
it's a rename-and-tweak, send it back). D1 and D3 have no file overlap and no dependency
on each other, so they can run **in parallel**; D2 depends on D1; D4 depends on D2 and D3;
D5 depends on D4.

```
D1 (wire+tokens) ──► D2 (clauses) ──┐
                                    ├──► D4 (messages+server) ──► D5 (e2e tests + docs)
D3 (draw/concede engine) ──────────┘
```

## Local gates (run before every push — same as Track A/B)

```bash
cd new_implementation && source venv/bin/activate
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
```

## D1 — `daide-wire-protocol` ✅ MERGED (`v2.7.34`, PR #27)

Pure protocol layer, stdlib only, zero I/O — same discipline as `src/engine/`.

- [x] `src/server/daide/tokens.py`: a `Token` frozen dataclass (`text`/`raw`/`number`,
      `from_str`/`from_int`/`from_bytes` constructors) backing a bidirectional registry —
      powers, provinces+coasts, unit types, order types, commands, THX order-notes, ORD
      order-results, HLO parameters, press tokens. ASCII-escape fallback and signed
      14-bit integer encoding both implemented. Province coverage is asserted against
      `engine.map_loader.load_standard_map()` via `verify_standard_map_coverage()`
      (called by the test suite, not at import — keeps the module I/O-free on import),
      not a second hand-typed list.
- [x] **Real finding not anticipated in this plan:** this engine's internal province
      codes `ENG` (English Channel), `BOT` (Gulf of Bothnia), and `LYO` (Gulf of Lyon)
      collide with DAIDE's own vocabulary — DAIDE reserves `ENG` for the England power
      token and uses `ECH`/`GOB`/`GOL` for those three seas. `daide_province_token()`
      applies the translation; documented inline rather than silently papered over.
- [x] `src/server/daide/wire.py`: `MessageType`/`ErrorCode` `IntEnum`s +
      `InitialMessage`/`RepresentationMessage`/`DiplomacyMessage`/`FinalMessage`/
      `ErrorMessage` frozen dataclasses, async `read_message`/`write_message` over
      `asyncio.StreamReader`/`StreamWriter`. Decode failures raise `DaideWireError`
      carrying the `ErrorCode` a session layer should echo back.
- [x] Tests: `tests/test_daide_tokens.py` + `tests/test_daide_wire.py`, 293 tests —
      token round-trips, integer boundary cases, ASCII escaping, byte-exact IM/RM/DM/FM/EM
      framing, all written fresh (not copied from `old_implementation`'s test file).
- [x] **Done when — verified independently by the driver, not just taken from the
      subagent's report:** checked out the pushed branch into a separate worktree,
      `ruff check src/` clean, `pytest tests/test_daide_tokens.py tests/test_daide_wire.py`
      293/293 passed, full suite 1094 passed/52 skipped (no local DB)/10 xfailed —
      unaffected by the change. Spot-checked all 7 power tokens, ~10 provinces across
      inland/coastal/sea/bicoastal categories including the three renamed seas, and 7
      command tokens against `old_implementation/diplomacy/daide/tokens.py`'s byte values
      by eye — all matched. Diff read in full for the clean-room rule: original docstrings,
      original class design, no structural resemblance to the old file.

## D2 — `daide-clauses` ✅ MERGED (`v2.7.37`, PR #31)

- [x] `src/server/daide/clauses.py`: province+coast ↔ `Location`, power ↔ token, unit ↔
      `Unit`, turn/season ↔ `(Season, PhaseType)` (explicit `SPR/SUM/FAL/AUT/WIN` table
      with the "why" comment this section asked for), and all 9 order clause types.
      **Decode** goes through `engine.orders.parser.parse_order` (reuses the one grammar).
      **Encode does not** go through `format_order` — documented, sound rationale:
      `SupportHold`/`SupportMove`/`Convoy` carry only `Location` for their target/origin
      unit, never a power, but DAIDE's `SUP`/`CVY` clauses need one; encode composes
      tokens directly from `Order` fields, falling back to DAIDE's own `UNO` ("unknown
      power") token when no `power_by_province` lookup is supplied. `Move.via_convoy`'s
      fleet path is validated as well-formed on decode but not threaded into engine state
      (it isn't engine state — the real path comes from separate `Convoy` orders); encode
      takes an optional `via_fleets` for D4 to supply from the matching orders.
      Added reverse lookups (`engine_province_code`, `engine_power_name`,
      `engine_coast_suffix`) to D1's `tokens.py` rather than duplicating them locally —
      D1's file already owns the bidirectional atom registries.
- [x] Tests: `tests/test_daide_clauses.py`, 59 tests (352 total across the whole `daide/`
      package once combined with D1's) — every order type round-tripped against
      `parse_order`'s own output, explicit STP/SC, STP/NC, SPA/NC, SPA/SC, BUL/EC, BUL/SC
      coverage, and decode-error cases (bad/missing coast, coast-on-army, wrong-phase
      DSB/REM, malformed VIA, unknown verb, `UNO`-as-own-power).
- [x] **Done when — verified independently by the driver, not just taken from the
      subagent's report:** checked out into a worktree, rebased onto `main` (post-D1+D3)
      with zero conflicts, `ruff check src/` clean, `pytest tests/test_daide_clauses.py`
      59/59 and the combined `daide/` suite 352/352, full suite post-rebase (against a
      real local Postgres, migration applied) **1216 passed, 11 skipped, 10 xfailed**,
      overall coverage 64.80% (≥60). Diff read in full: no import of `persistence`/`server`
      beyond `server.daide.tokens`/`wire`, clean-room rule held, and the encode-path
      deviation's rationale checked against `engine/types.py` directly — confirmed
      `SupportHold`/`SupportMove`/`Convoy` genuinely carry no power field.

## D3 — `draw-vote` (shared with Track C's C3 — implement once) ✅ MERGED (`v2.7.35`, PR #29)

- [x] `src/engine/types.py`/`game.py`: `GameState.winners: frozenset[str] | None`,
      pure `Game.draw(winners=None)` (defaults to every power with a unit still on the
      board), `Game.winner()` extended to stay backward compatible (checks `winners`
      first, falls back to the old ownership-scan). Solo-win path
      (`_after_moves_settled`) now also populates `winners={solo}`, so solo and draw
      completions share one representation.
- [x] `src/persistence/`: `games.draw_votes` JSON column (Alembic `f3a9c17b6d20`,
      `{power: "yes"}`, mirrors `pending_orders` exactly), cleared every processed turn.
      New narrow `GameRepo.update_state_json` (state_json/phase_code/status only, no
      turn-counter bump, no pending-orders clear) for concede's out-of-band mutation —
      `save_state` would have wrongly disturbed other powers' already-submitted orders.
- [x] `src/server/game_service.py`: `submit_draw_vote`/`get_draw_votes`/`concede`.
      Draw-vote finalization reuses `save_state`'s `expected_phase_code` staleness guard
      (the same cross-process concurrency protection `process_turn` uses) rather than a
      second ad-hoc write path.
- [x] `src/server/api/routes/games.py`: `POST /games/{id}/draw_vote`,
      `GET /games/{id}/draw_vote_status`, `POST /games/{id}/concede`, reusing
      `orders.py`'s existing `_authorize_power` helper by import rather than duplicating
      the auth check.
- [x] Tests: `tests/engine/test_game.py::TestDraw`,
      `tests/test_game_service.py::TestDrawVoteAndConcede`,
      `tests/test_api_routes_draw_vote.py` — unanimous-survivors/holdout/eliminated-
      exclusion at the engine level, a full `GameService`-driven scenario, and API auth
      tests (non-assigned user gets 403).
- [x] **Done when — verified independently by the driver against a real local Postgres,
      not just taken from the subagent's report:** migration applied cleanly to a live
      DB; `ruff check src/` clean; full suite **1157 passed, 11 skipped, 10 xfailed**;
      engine coverage 93.42% (≥92), overall 64.03% (≥60). Diff read in full — the
      concede/draw split (`update_state_json` vs `save_state`) and the
      quorum-excludes-eliminated-powers logic both matched this section's spec exactly.
      **Track C's C3 is satisfied by this** — its remaining open item is purely client UX
      (a Telegram `/draw` command and a frontend button), not the mechanism itself.

## D4 — `daide-messages-and-server` ✅ MERGED (`v2.7.40`, PR #33; fix `v2.7.41`)

- [x] `src/server/daide/session.py`: per-connection state machine covering the
      gameplay-critical command surface — `NME`/`IAM`/`HLO`, `MAP`/`MDF`, `SCO`,
      `NOW`+`MRT`, `SUB`/`THX` (order-note mapping table, `_reason_to_note_token`),
      `NOT(SUB)`/`GOF`/`NOT(GOF)`, `MIS`, `TME`, `DRW`/`NOT(DRW)` (wired to D3's
      `submit_draw_vote`), `ADM`, `SND`/`FRM` (syntax-checked opaque relay, per Ground
      Rules — press grammar itself never parsed), `OUT`, `SLO`, `OFF`,
      `HUH`/`PRN`/`REJ`/`YES`/`NOT`. **Create-or-join decision made and executed:**
      create-on-first-successful-`NME`, exactly as this section specified — see the
      eager-creation finding below for why "first successful NME" (not "first
      connection" or "listener start") is load-bearing, not cosmetic.
      **Documented scope limitations** (not silent gaps): `HST` replays submitted
      order strings only (no historical SCO/NOW reconstruction — `order_history` has
      no per-phase result/state snapshot to rebuild from); `TME` is an immediate query,
      not `old_implementation`'s subscribe-to-future-push model (this codebase's
      `notify_game_processed` push already covers the same need); `GOF`/`NOT(GOF)` are
      acknowledged only (no per-power ready-gate exists — processing stays HTTP-route/
      scheduler-triggered).
- [x] `src/server/daide/server.py`: `asyncio.start_server` listener (`daide_protocol.py`
      deleted along with its test). Connection registry keyed by `game_id → power →
      session`, reusable passcodes for `IAM` reconnection, `notify_game_processed`
      broadcasting `NOW`/`ORD`/`OUT`/`SLO` (diffing `eliminated_powers()` and
      `view()["status"]` since the last broadcast per game to avoid double-firing).
- [x] `src/server/_api_module.py`: DAIDE listener started in `lifespan` alongside
      `deadline_scheduler`; startup failure (port in use, etc.) is logged and swallowed
      rather than crashing the API — DAIDE is one integration among several, not a
      prerequisite for the others. Notification hook called from both real
      `process_turn` call sites (`routes/games.py`'s route, `api/shared.py`'s
      `process_due_deadlines`) via a small sync/async bridge (`_notify_daide_processed`
      — schedules a task if a loop is already running, else `asyncio.run`; no prior
      bridge existed in this codebase to reuse).
- [x] `tests/test_daide_protocol.py` deleted (tested only the old fake stub).
- [x] **Real production-safety finding caught in review, fixed before merge:**
      the first pass had `DaideServer.start()` eagerly call `game_service.create_game()`
      whenever no `game_id` was supplied — and `_api_module.py` wires `DaideServer` with
      no `game_id`. Since `CLAUDE.md` documents that this repo **auto-deploys to
      production on every merge to `main`** (`systemctl restart diplomacy-api`), that
      would have minted one permanent orphan game row on **every future deploy**,
      whether or not a DAIDE client ever connected or the socket even bound. Fixed:
      `start()` now only binds the socket; `DaideServer.ensure_game_id()` (idempotent)
      creates the game on first successful `NME` only; `IAM` never creates one (`REJ`s
      immediately if no game exists yet, nothing to reclaim). Covered by
      `test_start_binds_an_ephemeral_port_and_creates_no_game` and
      `test_first_successful_nme_creates_the_game_lazily`.
- [x] **Done when — verified independently by the driver against a real local
      Postgres, twice (once before, once after the eager-creation fix), not just taken
      from the subagent's report:** `ruff check src/` clean; `test_daide_session.py` +
      `test_daide_server.py` 64/64; full suite **1274 passed, 11 skipped, 10 xfailed**
      (3 consecutive clean reruns, 0 warnings — one run showed 2 GC-timing-related
      warnings on real-socket tests that did not reproduce); engine coverage 93.42%
      (≥92), overall 65.77% (≥60). Confirmed no remaining `daide_protocol` importers.

## D5 — `daide-e2e-tests-and-docs` ✅ MERGED (`v2.7.43`)

Depends on D4.

- [x] End-to-end raw-socket test: a real TCP client (plain `socket`/`asyncio` in the test,
      not a mocked transport) drives one full turn through the real DAIDE byte protocol
      against a `GameService`/Postgres-backed game — connect, IM/RM, NME, HLO, MAP, MDF,
      SCO, NOW, submit a real move via SUB, process the turn through `GameService`
      directly (simulating what the deadline scheduler or another player finishing orders
      would trigger), and assert the byte-correct ORD/NOW notification arrives on the
      socket. This is this track's equivalent of Track B V4's byte-identical-PNG
      verification — proof the wire format actually round-trips end to end, which unit
      tests on individual layers can't prove by themselves.
      **Landed as** `tests/test_daide_server.py::TestEndToEndOneFullTurnOverOneSocket::
      test_full_wire_round_trip_and_post_turn_notification` — one continuous
      `asyncio.open_connection` client, a real `DaideServer` bound to an ephemeral port,
      backed by a real `GameService`/Postgres game (created lazily by the test's own
      `NME`, exactly as a real bot connecting would trigger it). Drives IM→RM, `NME`→`HLO`
      (asserts the assigned power is a real `STANDARD_POWERS` member, decoded via
      `tokens.engine_power_name` rather than assumed), `MAP` (asserts `MAP (standard)`),
      `MDF` (coarse shape + >800-byte/>400-token size sanity, full adjacency decode is
      D1-D4's tested territory), `SCO` (coarse shape: at least one ownership group +
      `UNO` for neutrals), `NOW` (full cross-check: decodes every unit clause via
      `clauses.unit_from_clause` and asserts the assigned power's units equal
      `engine.map_loader.load_standard_map().starting_units` filtered to that power —
      byte-level wire data matches the real starting position, not just "some units"),
      `SUB` of a real legal `Hold` order for one of that power's own starting units
      (`clauses.encode_order`), confirms `THX ... (MBV)` (accepted, not rejected). Then
      calls `GameService.process_turn` directly and `DaideServer.notify_game_processed`
      (the exact two calls `_api_module.py`/the deadline scheduler make) and reads the
      resulting notifications off the *same* socket: `NOW` first, then `ORD` — confirmed
      against the actual `notify_game_processed` send order in `server.py`, not assumed.
      **Observed in a real run:** the test's own connection is always the first, so it
      always gets `AUSTRIA` (confirmed by direct script run, not just inferred from
      `assign_power`'s `STANDARD_POWERS` iteration order); the legal order submitted was
      `A BUD H`; the `SUB` echo's trailing note was `(MBV)`; the two notifications after
      `notify_game_processed` arrived as `NOW` then `ORD`, in that order, on the one
      unbroken connection.
- [x] Update `docs/specs/architecture.md`: the `DAIDE clients` box in the process diagram
      is no longer aspirational; expand the package-boundaries listing to show
      `src/server/daide/` (`tokens.py`, `wire.py`, `clauses.py`, `session.py`, `server.py`)
      the way `telegram_bot/` is already documented; note the press-content-forwarding
      limitation from the Ground Rules section explicitly, not silently.
      **Done:** the "Processes" section's five-things-talk-to-Postgres paragraph no longer
      says "aspirational"; the package-boundaries listing's `src/server/` block now shows
      `daide/` instead of the deleted `daide_protocol.py`; a new "DAIDE protocol support"
      section (mirroring how `telegram_bot/` gets a short prose treatment) lists all five
      files with a one-line purpose each, states the press-relay limitation explicitly as
      a **permanent design limitation**, not a temporary gap, and points at this e2e test
      as the composition proof.
- [x] Update this file: mark Track D done with the verification evidence (suite counts,
      coverage, the byte-level e2e test passing); update the top `Status` block.
      (C3's checklist itself is left untouched here — its prose in the `Status` block and
      D3's own section already say it's satisfied by D3, as of an earlier commit; D5 does
      not duplicate that note a third time.)
- [x] **Done when:** the e2e test passes against a real Postgres (not sqlite/mocked), full
      suite green, `ruff check` clean, coverage floors hold, and `architecture.md` reflects
      what's actually in `src/` (not what's planned) — same bar Track B held itself to.
      **Verified independently by the driver:** real local Postgres (not sqlite),
      `ruff check src/` clean (pinned `ruff==0.15.12`, matching CI), the new e2e test
      passes on its own and as part of the full `daide/` suite (417 passed:
      `tokens`+`wire`+`clauses`+`session`+`server`), full suite **1275 passed, 11 skipped,
      10 xfailed**, engine coverage 93.42% (≥92), overall coverage 65.77% (≥60).

---

# Track E — Client UX

## Why this track exists

**Added 2026-07-30 at the maintainer's explicit request ("Focus on improving the UX"),** and
scoped by two maintainer decisions taken the same day: work **both** client surfaces in
parallel, and treat the web game screen as a **restructure**, not a polish pass.

Tracks A–D made the game *correct and playable*: the adjudicator conforms to DATC, every
phase works from both clients, a game can end by agreement, and a real DAIDE bot can play.
None of that work asked whether a human enjoys using the thing. Two read-only audits (one
per surface, 2026-07-30) found that the answer is often no — and that the most valuable
missing information is already computed server-side and then discarded.

## The finding that shapes this whole track

**Neither client can tell a player what happened to their orders.** `GameService.process_turn`
returns `{"phase", "status", "resolution"}` (`game_service.py:163-167`), but the HTTP route
ends with `return {"status": "ok"}` (`api/routes/games.py`), throwing the resolution away.
`GameService.last_resolution` has exactly one consumer in the entire server — the map
renderer (`api/routes/maps.py:254`) — and the overlay PNGs it produces are returned as a
*server filesystem path* with no `StaticFiles` mount, so a browser can never load them.
`GET /games/{id}/orders/history` returns orders as *submitted*, never their outcomes.

So after a turn resolves, a player gets a new picture and must diff it against memory to
work out that their army bounced. "Did my order work?" is the central question of a
turn-based game, and answering it needs a backend change (E1), not just frontend work.

## Execution model

Same as Tracks A–D: one Sonnet subagent per task in its own git worktree, each against its
own Postgres database, driver verifies every claim by re-running the gates and reading the
whole diff before opening a PR. **One change from earlier tracks: subagents do not edit this
file.** With three-plus agents running in parallel, concurrent edits to `fix_plan.md`
guarantee rebase conflicts, so the driver maintains Track E's checkboxes and Status block on
their behalf. Agents report; the driver records.

E1 and E2/E3 have no file overlap (backend vs. `frontend/` vs. `telegram_bot/`) and ran in
parallel. E4 depends on E1's endpoints existing.

## E1 — `api-resolution-and-authz` (backend enablement)

- [x] `POST /games/{id}/process_turn` returns the resolution it already computes, additively
      (the existing `"status": "ok"` key must survive — the bot and existing tests read it).
- [x] A read endpoint for the last resolution as JSON, so a page reload doesn't lose it.
      Serialized via the engine's existing `serialization.py`, not a hand-rolled shape.
- [x] `GET` routes streaming the **orders** and **resolution** overlay PNGs as bytes,
      mirroring the working `GET /games/{id}/map`. The renderer already exists
      (`rendering/order_overlay.py`) — this is plumbing, explicitly **not** a rendering
      redesign.
- [x] **Authorization hole:** `process_turn` depends only on `require_bot_or_user`, which
      checks that you are *someone*, not that you are *in this game*. With `require_all`
      defaulting to `false`, any logged-in stranger can end a turn early for all seven
      powers, converting everyone's unsubmitted units into holds. Restrict to bot-secret,
      a user holding a power in that game, and the admin path if one already exists; 403
      otherwise.
- [x] **MERGED `v2.7.52` (PR #45). Verified independently by the driver** against a real
      local Postgres on the rebased tip: `ruff check src/` clean, **1305 passed, 11 skipped,
      10 xfailed**, engine 93.42% (≥92), overall 66.33% (≥60). `process_turn` exposes the
      engine's status as `game_status` to avoid colliding with the pre-existing
      `"status": "ok"` key. `_authorize_process_turn` accepts bot-secret / admin-token /
      game-membership.
- [x] **Three existing tests had encoded the authorization bug** and were fixed, not
      weakened: two called `process_turn` with no credential at all (passing only because
      the test fixture bypasses `require_bot_or_user`, which this route no longer depends
      on — so the override had been masking authorization in tests), and one processed a
      turn with the game *creator's* Bearer token while the power belonged to a different
      account. One didn't assert on the response status at all; it does now.
- [x] Confirmed no bot regression: `require_bot_or_user` already required Bearer **or**
      `X-Bot-Secret`, and the bot's `/processturn` posts an empty body with only the
      header, so `DIPLOMACY_BOT_SECRET` was already mandatory for that command. E1d only
      narrows which *Bearer* users pass.

### Defect E1 shipped, caught by the driver, fixed in E4

`last_resolution_view` calls `format_order(order)` with **no `kind_by_province` map**, and
per `format_order`'s own docstring the unit letter is then inferred from coast presence — so
**a fleet at any non-split-coast province is reported as an army.** Confirmed live against
the seeded game: the submitted orders were `F SEV - BLA` and `F ANK - BLA`; the endpoint
returned `"order_str": "A SEV - BLA"` / `"A ANK - BLA"`. This is the same repo-wide gotcha
Track A's PR2 recorded, resurfacing in new code.

The subagent documented the caveat honestly in the docstring rather than hiding it, which is
why it was cheap to find — but documenting is not fixing, and this is the one endpoint where
truthful unit letters matter most, since its entire purpose is telling a player what happened
to *their* orders. Rolled into E4 rather than left as a known wart. **Root cause worth
remembering:** engine `Order` variants reference a `Location` (province + optional coast),
never a `Unit`, so the kind is genuinely absent from the order and from its serialized form
by design — it is only recoverable from the board as it stood *before* adjudication.

## E2 — `game-screen-restructure` (web)

- [x] Gate "Process turn" on `myPower` and require confirmation. Today the block is
      `{state.status === 'ACTIVE' && ...}` while the draw-vote block immediately above it
      correctly uses `{myPower && ...}` — an irreversible seven-power action offered to
      non-members on a single unlabelled click.
- [x] Rebuild the information hierarchy: deadline and per-power submitted/missing state
      (both endpoints exist and were called by **nobody** in `frontend/src`), an
      unmistakable phase indicator, and a clear "you still need to submit" signal.
- [x] Render the player roster — `players` is fetched *with* `full_name` and used only to
      compute `myPower`/`takenPowers`/`availablePowers`, never drawn, so a player cannot
      see who controls the other six powers.
- [x] Fix the mobile layout: order rows wrap to multiple lines each, pushing every action
      below a long scroll.
- [x] Bug: order selections from the previous phase survive a processed turn (the pre-fill
      effect doesn't depend on `state.phase`).
- [x] Bug: `buildOrderSlots` is never restored from the server, so submitted builds vanish
      from the UI on reload while the server still holds them.
- [x] A 409 `StaleGameError` dumps the raw backend string at the user; catch it and reload.
- [x] Add concede/quit (both endpoints exist, neither is called), a "game is full" message
      where the join section currently vanishes silently, accessible names on the order and
      recipient selects, and remove the dead `phase === 'Builds'` branch.
- **Deliberately excluded:** the results panel and overlay map (depend on E1 → that's E4),
  and an interactive/zoomable map component (a rendering redesign, out of scope per the
  Out-of-scope list).
- [x] **MERGED `v2.7.51` (PR #44). Verified independently by the driver** on the rebased
      tip: `npx tsc -b --noEmit` exit 0, **21 test files / 109 tests passed**,
      `npm run build` green. New layout, top to bottom: back link → header with a coloured
      phase badge → error alert → **turn-status card** (deadline countdown, submission tally,
      explicit "your orders are in" / "you still need to submit") → **player roster** → map →
      join (or "game is full") → orders (responsive grid) → draw vote → **leave game**
      (quit vs. concede, distinction spelled out) → **process turn** (gated + confirmed) →
      messages. One new shadcn component (`alert-dialog`); `apiJson` now throws an `ApiError`
      carrying the HTTP status so 409 can be branched on without string-matching.
- [x] The agent also added the `afterEach(cleanup)` this test suite had always lacked —
      latent until tests started reaching into the dialog's portal via `screen.*`.
- **Process note:** this agent could not run the frontend gates at all on its first pass —
      Node is not installed on this machine — and **said so plainly instead of claiming a
      pass**. The driver then installed a local Node 22 toolchain (matching CI), found two
      of the agent's three new tests genuinely failing, and sent it back. See the
      `no-node-toolchain-locally` note: a frontend change cannot be verified here until a
      toolchain is fetched, despite `CLAUDE.md` documenting `npm` commands as normal gates.

## E3 — `bot-ux-improvements` (Telegram)

- [x] **Highest leverage in either audit:** `api_client.py` discards every server error
      message. `resp.raise_for_status()` yields only `"401 Client Error: Unauthorized for
      url: ..."`, so FastAPI's real `{"detail": ...}` — "Power already taken", "Sender not
      in game" — never reaches the player, at dozens of call sites across the package.
      `link_account.py:34-48` already does it correctly and is the template. One file, every
      handler benefits.
- [x] An ordinary Telegram display name breaks registration reporting: `full_name` is taken
      verbatim from the user's profile and interpolated into a `parse_mode='Markdown'`
      message, so a name containing `_` or `*` makes Telegram reject it, and the surrounding
      `except` then reports **"Registration error"** for a registration that already
      succeeded. `/players` has the same bug with *no* try/except at all, so it silently
      dies. `utils.py` has shipped `escape_markdown` all along, unused here.
- [x] `/messages` shows only who a message was addressed *to*, never who sent it — in a game
      that is entirely negotiation. Joinable client-side from `players`; no new endpoint.
- [x] After `/processturn` the player learns nothing: the handler already holds the `state`
      response containing `dislodged` and `contested` and reads only `turn`/`phase`/`done`.
- [x] `/processturn` lets one player force resolution while others haven't moved (no
      `require_all`, no warning), silently converting their units to holds. Check
      `orders_status` first and confirm.
- [x] No `set_my_commands` anywhere, so Telegram's "/" autocomplete is empty for all ~27
      commands.
- [x] `docs/TELEGRAM_BOT_COMMANDS.md` actively lies about `/join` and `/order`; anyone in
      two games who follows the `/order [game_id]` docs is stuck, because `order()` cannot
      accept a game id at all.
- [x] **MERGED `v2.7.53` (PR #46). Verified independently by the driver** against a real
      local Postgres on the rebased tip: `ruff check src/` clean, **1332 passed, 11 skipped,
      10 xfailed** (+27 new tests), engine 93.42% (≥92), overall 68.12% (≥60).
- [x] **`/processturn` also contained live dead code**, found while doing E3d: it read `turn`
      and `done` from `GET /state`, and *neither key exists* in the GameState-native view
      (the keys are `phase`/`status`). So it printed "Turn: Unknown" on every single
      invocation and its "🏁 Game Complete!" branch was unreachable. Fixed in the same pass.
- [x] **E3g decision — code changed to match the docs, not the reverse.** `/order` now
      accepts an optional leading numeric game id and splits on `;` like `/orders` already
      did; `/join <game_id>` without a power shows the power-selection menu the docs already
      promised. The game-id sniff is `args[0].isdigit()`, which is safe because no order in
      this grammar can start with a digit — unit orders begin `A`/`F`, verb-first orders
      begin `BUILD`/`WAIVE`/`D`. `/order 2` with no order text is handled explicitly.
- [x] `ApiError` deliberately subclasses `requests.HTTPError` rather than `Exception`, so
      `link_account.py`'s existing `.response.status_code` / `.json()` handling keeps working
      while every generic `except Exception as e` handler gains the real message for free.
- The agent audited the *remaining* `parse_mode='Markdown'` sites and left the ones carrying
  only system-generated or enum-bounded data (turn numbers, power names from a fixed list)
  rather than escaping indiscriminately — a judgement call the driver agrees with, recorded
  here so a later reader doesn't mistake it for an oversight.

## E4 — results comprehension in the web client (depends on E1)

- [ ] Render "what happened to my orders" from E1's resolution endpoint, leading with the
      player's own power and translating result codes into plain language (a player should
      never be shown the raw enum `BOUNCE`), with `dislodged` + `retreat_options` surfaced
      prominently since a dislodged unit demands action next phase.
- [ ] Show the resolution and pending-orders overlay maps, unreachable from a browser until
      E1 added `GET .../map/resolution` and `GET .../map/orders`.
- [ ] **Fix the fleet-reported-as-army defect E1 shipped** (see the E1 section above) —
      truthful unit letters, working for a resolution fetched long after the turn, without
      changing the canonical `serialization.py` shape.
- In flight as of 2026-07-30 on branch `results-panel`. Deliberately kept out of E2 so two
  agents didn't collide on `GameView.tsx`.

## Known gaps recorded but not yet scheduled

- **A manual `/processturn` notifies only the caller.** The deadline-triggered path calls
  `notify_players` and posts to a linked channel (`api/shared.py`); the manually-triggered
  route does neither. So the *success* case (everyone submits, someone processes) is silent
  while the *failure* case (missed deadline) is richly instrumented. The audit flagged this
  as needing a deliberate design pass over "who gets told what, when" rather than a bolt-on.
- **Support-order keyboards have no size limit** in the interactive flow — a central unit can
  produce 20-30 buttons. Convoys already solved this with a sub-menu; supports need the same
  treatment and its own callback namespace.
- **`WAITING_LIST` is an in-memory global** dropped on every bot restart (i.e. every deploy),
  with no notification to the players in it, and `process_waiting_list` isn't atomic — a
  failure partway can orphan a game and leave the list undrained.
- **No full province names anywhere in the codebase**, so every client shows 3-letter codes
  while `/rules` and `/examples` teach full names. Teaching material and UI disagree.
- **Two API warts** found while seeding a game: `/games/create` requires an authenticated
  user, and `/games/{id}/join` requires `game_id` in the body *and* the path or it 422s.

---

## Definition of done (all tracks)

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
- [x] **Track C acceptance:** C1 — `security` CI job actually fails on a real finding
      (demonstrated on throwaway PR #41: `gh pr checks` reported `security  fail`, failing
      step `Run bandit security check`; PR closed and branch deleted, nothing reached
      `main`), `v2.7.48`. C2 — brute-force test suite passes for
      `/auth/login`/`/auth/token`/`/auth/register` (10 tests, `v2.7.46`). C3 — engine+API
      layer satisfied by Track D's D3; Telegram `/draw`+`/nodraw`+`/status` tally and the
      frontend draw-vote control landed in `v2.7.47`, so a human can now end a game by
      agreement from either client. C4 — decision made and executed via Track D.
- [x] **Track D acceptance:** D1-D5 all merged; a real DAIDE bot (or the raw-socket e2e
      test standing in for one) can complete a full turn — connect, negotiate, submit
      orders, receive results — against a `GameService`/Postgres-backed game; the DAIDE
      listener actually starts with the API process; `architecture.md` reflects the real
      package, not the old text-stub description. **Done** — D1-D4 merged to `main`
      (`v2.7.34`-`v2.7.41`); D5's e2e test
      (`tests/test_daide_server.py::TestEndToEndOneFullTurnOverOneSocket`) drives a full
      turn over one real socket end to end and passes against a real Postgres-backed
      game; `_api_module.py`'s `lifespan` starts `DaideServer`; `architecture.md`'s "DAIDE
      protocol support" section documents the real `src/server/daide/` package.

## Out of scope

- The 10 DATC hard-tail xfails / iterative-Szykman resolver (separate engine project, if
  ever — see "Carried-over facts").
- Tournaments, Discord, observer/spectator mode, AI-powered analysis (long-standing
  maintainer list — `tournaments.py`, `discord_bot/`, `run_discord_bot.py` are **kept for
  backward compatibility, not dead code**; don't extend, don't delete). DAIDE (Track D)
  is not part of this exclusion — it's now an explicit, in-progress feature.
- Rendering redesign (new art, new layout engine, frontend map component). V3 moves
  code; V4 fixes correctness; neither restyles the board.
- The aspirational spec docs (`dashboard.md`, `visualization_spec.md` §10).
- Map variants beyond `standard` (except the V5 keep-or-kill decision on `standard-v2`).
- HTTPS / TLS termination — already tracked as a known infra gap in the root `CLAUDE.md`
  ("No HTTPS yet"), not new work discovered here. C2's brute-force fix reduces the
  in-the-meantime risk; it doesn't replace TLS.
- **Deep DAIDE press-content parsing** (the full `ALY`/`XDO`/`PRP` negotiation grammar
  beyond syntax-checked opaque forwarding) — see Track D's Ground Rules. A future track
  if a maintainer decision opens it up; D4/D5 only need to relay, not understand, press.

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
