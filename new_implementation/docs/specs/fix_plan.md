# Fix Plan — Game Engine Rewrite (Living Tracker)

> **This file is the single source of truth for engine-rewrite progress.** Any agent or
> model picking up this project: read this file top to bottom, then continue at the first
> unchecked task of the current milestone.
>
> **Maintenance contract (non-negotiable):**
> - Check off tasks (`[x]`) in the same commit as the work that completes them.
> - Keep the **Status** block below current: milestone, next action, date.
> - Newly discovered work becomes a new unchecked task under the right milestone — never
>   done silently.
> - If a design decision here is changed, edit this file to say what changed and why.

## Status

> ### ⚠️ A SECOND PROJECT IS NOW IN PROGRESS IN THIS FILE
> The engine rewrite (M0–M7) below is **complete and closed**. A follow-on track,
> **"Finish the Port" (PR1–PR6)**, is **IN PROGRESS** — see
> [Finish the Port](#finish-the-port--make-a-game-playable-end-to-end-again) at the
> bottom of this file. **PR1 and PR2 are merged; PR3 is the next task.** Do not resume
> anything in M0–M7.

- **Phase: COMPLETE.** M0–M7 all done. `engine-rewrite` merged to `main` via PR #5
  (commit `f0e7ae2`), tagged `v2.7.15`, pushed. `engine-rewrite` branch deleted
  (local + remote) — its full history lives on in `main`'s merge commit. This file's
  job as an active tracker is done; it remains as the historical record of the rewrite
  and the reference for anyone touching `src/engine/adjudicator/` later (see
  `adjudication.md` for the algorithm itself).
- **How the merge actually went (2026-07-27):** a direct `git push origin main` of the
  merge commit was **rejected by branch protection** (`2 of 2 required status checks are
  expected`) — a brand-new merge-commit SHA has never had CI run against it, so it can
  never satisfy "required status checks" via a bare push, regardless of how green the
  underlying code is. This is a correction to this file's own prior guidance ("direct
  push is allowed... GitHub rejects any push that fails CI" reads as if a passing push
  either succeeds or fails on content — in practice a *new* SHA is rejected outright,
  content aside). The fix: push to a temp branch, open a PR into `main` (`gh pr create`,
  making sure `-R tenderi/diplomacy` is explicit — `gh` was silently resolving the
  `upstream` remote, the unrelated original `diplomacy/diplomacy` repo, instead of
  `origin`), wait for `test`+`security` to go green on the PR, `gh pr merge --merge`.
  That merge-commit-through-GitHub is what satisfies protection. Tag *after* the PR
  merges, on the resulting `main` commit — not on the pre-merge local commit.
- **Deploy verification was explicitly skipped**: the maintainer confirmed nothing is
  currently deployed anywhere, so the `a1b2c3d4e5f7` game-data-wiping migration has no
  live data to affect and there is no running `/health` endpoint to check. Whoever
  deploys this for the first time should expect that migration to run as part of the
  normal `alembic upgrade head` deploy step (see CLAUDE.md's deploy-from-CI section) —
  it is not destructive in a fresh environment, just worth knowing about.

- **M6 COMPLETE (engine swapped, old engine deleted).** Server routes / CLI `Server` / DAIDE
  / persistence / rendering all go through `GameService` + the GameState-native API view;
  game state persists as `games.state_json` (migration `a1b2c3d4e5f7`). Old adjudication
  engine + `data_models` deleted; `engine/` is pure rules-logic, `persistence/` + `rendering/`
  are separate packages; `engine/game.py` is the phase machine (was `orchestrator.py`). Full
  suite **800 passed, 15 skipped, 10 xfailed**; ruff clean on `src/`; HTTP E2E verified
  (create → coasted fleet move → advance → state + PNG map).
- **M4 COMPLETE.** `DislodgedUnit` data model; `retreats.py::compute_retreat_options`
  authoritative legality; `retreats.py` + `adjustments.py`; DATC 6.H/6.I/6.J all green.
- **M3 COMPLETE** — resolver + full DATC 6.A–6.G + properties green.
  Passing: 6.A (8), 6.B (14/14), 6.C (7/7), 6.D (33/34), 6.E (13/15), 6.F (19/24),
  6.G (16/18) + mechanics (6). Resolver fixes driver-owned throughout.
- **10 xfail'd hard-tail cases** (documented inline in the test files):
  - second-order convoy paradoxes 6.F.16/17/18/23/24 — need iterative Szykman
    re-resolution; the single-pass backup rule handles first-order paradoxes only;
  - issue-4.A.7 convoy-to-adjacent variants 6.G.7/11;
  - beleaguered-garrison self-dislodgement variants 6.E.8/6.E.10 — not distinguished
    from the used-for-other-means case 6.E.12 by the current support-void rule;
  - 6.D.8 — competing DATC reading of a no-fleet convoy move (this engine treats it as
    illegal/ignored, consistent with 6.D.28/29/31/32).
- **M3 Hypothesis properties: DONE** (`tests/datc/test_properties.py`) — determinism
  under order-shuffling (200 examples), ≤1 unit/province, unit conservation, retreat
  sets. 249 passed, 10 xfailed, ruff clean.
- **Execution:** pipeline with mixed models — driver (Fable/Opus) owns M1, M3 core, M6;
  Sonnet/Haiku subagents take M2, M4, M5, M7 and DATC test batches. Milestones are
  sequential; each gated green before the next starts.
- **Branch:** all work happened on `engine-rewrite` (off up-to-date `main`); merged and
  deleted (local + remote) 2026-07-27 — see the Status block above. Everything now lives
  on `main`.
- **Last updated:** 2026-07-27 (Sonnet 5 — M7 steps 3–5 DONE: `adjudication.md` written;
  `architecture.md`/`data_spec.md`/`CODEBASE_OVERVIEW.md` rewritten from stale
  pre-rewrite drafts to the actual post-M6 layout; `engine-rewrite` merged to `main` via
  PR #5 and tagged `v2.7.15`; branch deleted. **Project complete — nothing left to
  resume.**).

## Goal

Perfect the game engine: correct Diplomacy adjudication (DATC-conformant), full enforced
test coverage, no buggy features. The maintainer has authorized a **ground-up rewrite of
the rules core** — nothing needs to be preserved, no backwards compatibility. Server, bot,
DB, and rendering are *adapted*, not rewritten.

## Why a rewrite (confirmed defects in the current engine)

All paths relative to `new_implementation/`. Line refs are pre-rewrite `main`. These are
verified by direct reads, not guesses. Do not trust the old engine as a rules reference.

1. **Order-dependent adjudication** — `_process_movement_phase` (`src/engine/game.py:433-1205`)
   is one ~770-line pass that mutates `unit.province` mid-loop in dict order. Only 2-unit
   swaps get cycle detection (`:679-693`). No fixed point → interdependent support/dislodge
   cases resolve wrong or nondeterministically.
2. **Convoy adds attack strength** (`game.py:558-560` + `_calculate_convoy_strength:1207`) —
   a convoyed army attacks at strength ≥2. Flat rules violation.
3. **No convoy paradox handling** (no Szykman rule anywhere); multi-route convoys fail if
   *any* fleet dies (`game.py:1140-1163`); multi-fleet chains fail validation because each
   fleet must be adjacent to both endpoints (`src/engine/data_models.py:409-414`).
4. **Support-cut rules wrong** (`game.py:611-619`): no exemption for attack from the
   province the support targets; own units cut own support; cuts computed once up front,
   never revisited.
5. **Coasts dead on arrival**: parser captures `/SC` but passes `"SPA/SC"` through as a
   province name (`src/engine/order_parser.py:328-334`) → map lookup fails; `Unit.coast`
   never populated. Coast adjacency hardcoded wrong in three places (`data_models.py:120-142`,
   `allowed_moves.py:26-39`, `province_mapping.py`) while `maps/standard.map` is correct
   and ignored.
6. **Builds unvalidated** (`game.py:1520-1551`): any BuildOrder creates a unit — no home-SC/
   vacancy/ownership check, no build cap, no civil disorder, no waives, built fleets lose
   coast.
7. **Retreat conflicts order-dependent** (`game.py:1304-1393`): two retreats to one
   province → first wins, second disbands. Rule: both disband.
8. **Structural rot**: dislodgement as `"DISLODGED_<prov>"` string prefix; two different
   `Province` classes duck-typed via `getattr(..., [])` (silent empty adjacency); engine
   logic bent to satisfy wrong tests (`game.py:1401-1405`).
9. **Package boundaries**: `src/engine/` contains the persistence layer (`database.py`,
   `database_service.py`, ~2,300 lines) and `map.py` is 3,488 lines (~3,200 = PNG/SVG
   rendering tangled with topology).
10. **Testing**: ~1,180 tests but zero DATC / paradox / coast-adjudication / civil-disorder
    coverage; `.coveragerc` sets `fail_under=85` but CI runs plain `pytest -q` — no
    coverage enforced anywhere; some tests enshrine bugs and must die with the old engine.

## Reference material (use these, in this order)

- **DATC** (Kruijswijk's Diplomacy Adjudicator Test Cases, public document) — the
  conformance standard. ~160 cases, sections 6.A–6.J.
- `old_implementation/diplomacy/tests/test_datc.py` — battle-tested encoding of all 160
  cases (6.F.14–6.F.24 = convoy paradoxes). **AGPL (Paquette's package): use to cross-check
  expected outcomes; do not copy code.**
- `old_implementation/diplomacy/engine/game.py` — reference resolver semantics
  (`_detect_paradox:3650`, `_check_disruptions:3680`, convoy paths `:1898-2100`,
  resolution `:3523-4550`). Same AGPL caveat.
- `new_implementation/maps/standard.map` — **the only topology truth**, coasts included
  (e.g. `BUL/EC ABUTS BLA CON RUM`). Already correct.
- `docs/specs/diplomacy_rules.md` — rulebook prose (authoritative on rules, silent on
  algorithm). `old_implementation/rules.pdf` — official rulebook.
- Algorithm: Kruijswijk, *The Math of Adjudication* — the fixed-point resolver this
  rewrite implements.

## Target design (decided — change only with written rationale here)

```
src/engine/                  # PURE rules core — no I/O, no DB, no rendering
  types.py                   # frozen dataclasses: Location(province, coast), Unit,
                             #   Order variants (Hold/Move/SupportHold/SupportMove/
                             #   Convoy/Retreat/Disband/Build/Waive), GameState,
                             #   Resolution + result enums (OK/BOUNCE/CUT/VOID/
                             #   NO_CONVOY/DISLODGED/DISBAND)
  map_loader.py              # .map parser → MapData; coasts first-class; topology only
  orders/parser.py           # ONE grammar: coasts, VIA convoy, aliases; parse + format
  orders/validation.py       # ONE validation path
  adjudicator/movement.py    # Kruijswijk fixed-point resolver (see below)
  adjudicator/retreats.py    # retreat resolution
  adjudicator/adjustments.py # builds/disbands, civil disorder, waives
  game.py                    # phase machine over immutable GameState snapshots
  serialization.py           # canonical GameState/Order/Resolution ⇄ JSON (one place)

src/persistence/             # database.py + database_service.py move here (adapted)
src/rendering/               # SVG/PNG pipeline + order_visualization move here
```

Key decisions:
- **Immutability**: `Unit` frozen+hashable; adjudication is a pure function
  `(map, state, orders) -> (Resolution, new_state)`; history = list of snapshots.
- **`Location = (province, coast|None)`** everywhere; a fleet in Spain is *at* `SPA/SC`.
  All hardcoded adjacency/coast tables deleted; `.map` file is the sole source.
- **Adjudicator = Kruijswijk fixed-point**: per-order state UNRESOLVED/GUESSING/RESOLVED,
  recursive resolve with dependency tracking; attack/prevent/defend/hold strengths;
  support cuts with proper exemptions; convoy paths over *surviving* fleets with
  multi-route support; dependency cycles: all-moves → circular movement succeeds,
  through-convoy → **Szykman** (convoyed moves in cycle fail, re-resolve).
- **Civil disorder**: unordered dislodged units disband; owed disbands auto-resolve by
  rulebook distance rule (farthest from home, fleets before armies, alphabetical);
  missing builds → waived.
- **Phases**: `S1901M → [S1901R] → F1901M → [F1901R] → W1901A → S1902M…`; retreat phase
  only when dislodgements exist; SC ownership updates after Fall retreats; victory 18 SCs.
- Deleted outright: `power.py`, `order_parser_utils.py`, `allowed_moves.py`,
  `strategic_ai.OrderGenerator`, all duplicate coast/home-center tables.

---

## Task lists

### M0 — Setup

- [x] `git checkout main && git pull --rebase && git checkout -b engine-rewrite`
- [x] Add `hypothesis` to `requirements.txt` (test dep)
- [x] Add `datc` marker to `pytest.ini`
- [x] Update this file's Status block; commit

### M1 — Core types & map topology

- [x] `src/engine/types.py`: enums (`UnitKind`, `Season`, `PhaseType`, result codes) +
      frozen dataclasses (`Location`, `Unit`, all order variants, `GameState`,
      `Resolution`). Armies never carry coasts; fleets in split-coast provinces always do.
- [x] `src/engine/map_loader.py`: parse `maps/standard.map` into `MapData` — provinces,
      types (land/coast/water), adjacency with coast nodes first-class, supply centers,
      home centers, 1901 starting units. Query API: `adjacent(loc)`, `is_adjacent(a, b)`,
      `army_moves(province)`, `fleet_moves(location)`.
- [x] Tests: province/SC counts (75/34), adjacency symmetry, coast adjacency exactly
      matching the `.map` file (BUL/EC↔{BLA,CON,RUM}, BUL/SC↔{AEG,CON,GRE}, SPA/NC,
      SPA/SC, STP/NC, STP/SC), correct 1901 starting position.
- [x] **Done when:** zero hardcoded topology in new code; map tests green.

### M2 — Order grammar & parser

- [x] `src/engine/orders/parser.py`: all order types; coast syntax (`F SPA/SC`,
      `A LON - BEL VIA`, `F STP/NC - BAR`); build/disband/waive; optional power prefix;
      alias normalization folded in from `province_mapping.py` (one table); consistent
      province-token handling (kill the 3-char vs 3–10-char regex split).
- [x] Canonical `format(order)` for round-trip and display. NOTE: non-Build orders store
      only `Location`s (not the A/F letter), so `format_order` infers kind from coast
      presence — round-trip-safe, but display of a fleet at a non-coast province prints
      `A`. Revisit for human-facing display in M5/M6 (pass unit kind from state).
- [x] `src/engine/orders/validation.py`: the single validation path
      `validate(order, state, map)` — used by server, adjudicator precheck, everything.
      Convoying fleet must be in a WATER space (tightened from the subagent's draft).
- [x] Tests: grammar matrix (order type × coast × alias × malformed), Hypothesis
      round-trip `parse(format(o)) == o`, DATC 6.A/6.B validity subset.
- [x] **Done when:** coasted orders produce proper `Location`s; round-trip property green.

### M3 — Movement adjudicator  ← the heart, budget the most time

- [x] `tests/datc/harness.py`: helpers `place_units / give_orders / adjudicate /
      assert_result / assert_dislodged` against the new engine API.
- [x] Write DATC cases from the DATC document (cross-check outcomes vs
      `old_implementation/diplomacy/tests/test_datc.py`; do not copy code), one test per
      case, named/tagged by DATC number, marker `datc`:
  - [x] 6.A basic checks (12)
  - [x] 6.B coastal issues (14)
  - [x] 6.C circular movement (7)
  - [x] 6.D supports & dislodges (34)
  - [x] 6.E head-to-head & beleaguered garrison (15)
  - [x] 6.F convoys incl. all paradoxes (24)
  - [x] 6.G convoy + move combinations (18)
- [x] `src/engine/adjudicator/movement.py`: fixed-point resolver per the design above.
- [x] Hypothesis properties: shuffling order submission never changes results; ≤1 unit
      per province post-resolution; unit conservation; every dislodged unit has a
      computed legal retreat set.
- [x] **Done when:** DATC 6.A–6.G all green (~124 cases) + properties green.

### M4 — Retreats & adjustments

> **Design decisions — RESOLVED (2026-07-24, driver):**
> 1. **DONE.** Added `DislodgedUnit(unit, attacker_origin, retreats)` frozen dataclass in
>    `types.py`; `GameState.dislodged` is now `tuple[DislodgedUnit, ...]` (was
>    `frozenset[Unit]`). Each record carries its attacker-origin province and the
>    precomputed legal retreat set. `movement.run()` builds these; `GameState.dislodged_at`
>    looks one up. `attacker_origin` is `None` when the dislodging attack was convoyed (a
>    convoyed attacker crosses no shared border, so its origin does not block the retreat).
> 2. **DONE.** `retreats.py::compute_retreat_options` is the single authoritative legality
>    path: it computes against *post-resolution* occupancy, excludes the `contested`
>    standoff set and the (non-convoyed) attacker origin. `movement.run()` calls it to fill
>    both `DislodgedUnit.retreats` and each `OrderResult.retreat_options`; the old
>    `movement._retreat_options` is deleted. `orders/validation.py` validates a Retreat by
>    exact membership in the precomputed set.

- [x] `adjudicator/retreats.py`: legal destinations exclude attacker's origin, standoff
      provinces, occupied provinces; **all** units retreating to the same province
      disband; unordered dislodged units disband. (`compute_retreat_options` +
      `adjudicate_retreats`.)
- [x] `adjudicator/adjustments.py`: entitlement = owned SCs − units; build validation
      (owned home SC, vacant, fleet coast required where split); explicit + implicit
      waives; civil-disorder auto-disband (distance rule above).
- [x] DATC cases: 6.H retreating (16), 6.I building (7), 6.J civil disorder (11) — all
      34 green, authored by 3 parallel Sonnet subagents (distinct files, no adjudicator
      edits), outcomes cross-checked vs the AGPL reference. No resolver fixes were needed:
      the retreat/adjustment adjudicators conformed on first integration.
- [x] **Done when:** full DATC suite green. **154 DATC cases authored; 144 green + the 10
      documented M3 hard-tail xfails** (second-order convoy paradoxes 6.F.16/17/18/23/24,
      convoy-adjacent 6.G.7/11, beleaguered self-dislodge 6.E.8/10, no-fleet-convoy 6.D.8).
      Those 10 need the iterative-Szykman resolver upgrade and are explicitly out of M4
      scope — do NOT un-xfail without it. 285 passed, 10 xfailed, ruff clean.

### M5 — Orchestration & serialization

> **Naming decision (2026-07-24, driver):** the new phase machine is
> `src/engine/orchestrator.py`, NOT `game.py` — the legacy `engine/game.py` still exists
> and is imported by the server until M6 deletes it. Likewise the new dumb AI is
> `src/engine/simple_ai.py` (not a rewrite of the old `strategic_ai.py`). **M6 renames
> `orchestrator.py` → `game.py` and replaces `strategic_ai.py` with `simple_ai.py`** once
> the old engine is gone.

- [x] `src/engine/orchestrator.py` (→ `game.py` in M6): `Game` frozen snapshot + phase
      machine — conditional retreat phase (only on dislodgement) & adjustment phase (only
      when a power's unit/center counts differ), SC-ownership update after Fall, victory at
      18, elimination query, snapshot history.
- [x] `src/engine/serialization.py`: canonical JSON for `GameState`/`Order`/`Resolution`
      (+ `DislodgedUnit`, `OrderResult`); Hypothesis order round-trip (300 ex) + explicit
      state/resolution round-trips.
- [x] Port the AI to the new types → `src/engine/simple_ai.py` (dumb heuristic generator
      for all three phases). Old `strategic_ai.OrderGenerator` deletion deferred to M6.
- [x] Self-play smoke test: 7 AI powers, runs to ≥1911 or an earlier 18-center win;
      invariants (≤1 unit/province, unit cap, state+resolution round-trip) asserted every
      phase; no crash. (`tests/engine/test_game.py::TestSelfPlaySmoke` — file renamed from
      `test_orchestrator.py` when `orchestrator.py`→`game.py` in M6.)
- [x] **Done when:** smoke + round-trip green; engine package imports nothing but stdlib.
      Verified: new modules import only `json`/`random`/`re` + engine internals. 308
      passed, 10 xfailed, ruff clean.

### M6 — Integration (riskiest milestone — server reaches into engine internals today)

> **M6 progress (2026-07-24, Opus 4.8):** local Postgres up (see local-postgres memory);
> pre-M6 baseline **1358 passed, 16 skipped, 10 xfailed**.
> - **Slice 1 (done, green):** moved `engine.database*` → `src/persistence/` (mechanical).
> - **Slice 2 (done, green):** deleted genuinely-dead `power.py` + `strategic_ai.py` (zero
>   src usage) and their old-engine-only tests (`test_power`, `test_strategic_ai`,
>   `test_map_and_power`, `test_integration`). Suite now **1275 passed**.
>
> **The remaining M6 is the ENGINE SWAP — an all-or-nothing chunk, NOT incrementally
> green-able.** Rewiring the server onto the immutable new engine changes the API JSON
> contract (`_state_to_spec_dict`'s `powers`/`units`/`supply_centers`/order shapes), which
> ~50 test files + the React frontend + the bot all assert. Code + every asserting test
> must land together or the suite is red. Do it as ONE focused branch, server-first, then
> delete. Concrete target design:
>
> **Persistence (new).** A game row stores `state_json = serialization.state_to_dict(game.state)`
> (the new `GameState`) + `map_name` + `status` + `deadline`; drop the relational
> unit/order/power tables' state role and the `unit_to_dict/order_to_dict/dict_to_order`
> helpers. Player→power assignments stay in `players` (not engine-coupled). Pending orders:
> `{power: [order_dict]}` JSON per game, cleared on process-turn. Alembic migration wipes
> all game rows (auth/users/channels kept).
> **Adjudication flow.** CREATE→`Game.new_standard()`; SET_ORDERS→new `parser` + `validation`,
> store per-power; PROCESS_TURN→load state, gather orders, `game.adjudicate(orders)`, store
> next `state_json` + resolution, advance phase (retreat/adjustment auto-inserted by the
> orchestrator); GET→new API serializer over `GameState`.
> **New API serializer** (replaces `_state_to_spec_dict`): build the response from
> `GameState` — `units` (by power), `ownership`/`supply_centers`, `dislodged` w/ retreats,
> `contested`, `phase_name`, `status`, plus `players` (power→user). Pick the shape ONCE and
> update `frontend/src` types, bot `api_client.py`, and all asserting tests in the same PR.
> **Deletes** (after the swap compiles + tests ported): `engine/game.py`, `data_models.py`,
> `order_parser.py`, `order_parser_utils.py`, `allowed_moves.py`, `province_mapping.py`
> (fold any needed aliases into the new parser), old `map.py` topology half. Rename
> `orchestrator.py`→`game.py`.
> **Map/rendering.** `map.py` tangles topology (used only by the old engine) with the
> SVG→PNG render pipeline (used by `maps.py`/bot). Split: move rendering → `src/rendering/`
> keyed off `map_loader` topology + `GameState`; delete the old topology half. `maps.py`,
> `admin.py`, bot `maps.py`/`orders.py` adapt to the new render entry point.

- [~] Move `src/engine/database.py` + `database_service.py` → `src/persistence/`; fix
      imports; drop `unit_to_dict`/`order_to_dict`/`dict_to_order` in favor of
      `engine/serialization.py`. **Package MOVE done** (mechanical: 18 import sites +
      alembic env + one mock-patch target repointed; the two modules' internal
      `.data_models`/`.map` imports absolutised to `engine.*`; full suite green). The
      **drop-helpers-for-serialization** half is part of the engine-swap chunk below.
- [x] **Slice 2:** delete genuinely-dead `power.py`/`strategic_ai.py` + old-engine-only
      tests (superseded by tests/engine + tests/datc). Suite 1275 green.
- [x] **Checkpoint A (additive, green):** new-engine game service over state_json.
      `games.state_json`/`pending_orders` columns + migration `a1b2c3d4e5f7` (wipes legacy
      game data); `persistence/game_repo.py`; `server/game_service.py` (GameService:
      create/submit/process/view over `orchestrator.Game` + serialization + parser/
      validation); `tests/test_game_service.py` (5 passing incl. coasted fleet move). Suite
      1280 green. **Decision: clean-break new API shape** (GameState-native — see the view
      dict in `game_service.view`), not the legacy `powers` shape.
- [x] **Checkpoint B (RED cutover):** rewired `Server` CLI, `api/shared.py`,
      `api/routes/games.py` + `orders.py` onto `GameService` returning the new view shape;
      also DAIDE, `maps.py`, `channels.py`.
- [x] **Checkpoint C:** deleted the old engine (`game.py`(old), `data_models.py`,
      `order_parser.py`, `order_parser_utils.py`, `allowed_moves.py`, `order_visualization.py`,
      dead `power.py`/`strategic_ai.py`, dead `server/api.py`). `province_mapping.py` KEPT
      (rendering aliases). Removed the data_models-based methods from persistence. Deleted
      43 old-engine test files (superseded by tests/engine + tests/datc); ported the
      surviving API/server/daide/client tests to the new view shape; trimmed obsolete
      Server-CLI tests (SAVE/LOAD/REMOVE_PLAYER/ADVANCE_PHASE).
- [x] **Checkpoint D (rendering split):** `src/engine/map.py` + `visualization_config.py`
      → `src/rendering/`; importers repointed; renderer fed from the `GameState` view (text
      units). Order/resolution **arrow overlays are stubbed to plain-board renders** — the
      overlay rework is deferred (see follow-ups). Also renamed `orchestrator.py`→`game.py`.
- [x] Alembic migration `a1b2c3d4e5f7`: added `state_json`/`pending_orders`; wipes stored
      game data (users/auth kept). Inspector-guarded TRUNCATE (safe on CI's fresh DB).
- [x] **Done when:** full suite green with a DB (**800 passed, 15 skipped, 10 xfailed**),
      server boots, HTTP E2E verified: create → coasted `F STP/SC - BOT` + moves → advance
      (S1901M→F1901M) → fetch state + PNG map (722 KB). Convoy adjudication covered by
      tests/datc 6.F/6.G. ruff clean on `src/`.

> **M6 follow-ups — ALL DONE in M7 step 1 (2026-07-27).** The four bullets below are
> resolved; see the checked items under "M7 → 1." for the implementation details. Kept here
> for context.
> - **Frontend TS types** (`frontend/src`) still describe the OLD `powers`-shaped state and
>   have NOT been updated to the new view (`units`/`ownership`/`phase`/`phase_type`/
>   `players`/`dislodged`/`contested`). The React app will break at runtime until ported;
>   the Python suite + CI don't cover it. This is the main remaining consumer to adapt.
> - **Order/resolution map overlays**: `maps.py` `generate_map/orders` & `/resolution` now
>   render a plain board (no move arrows). Rework the overlay layer against `Resolution`.
> - **`format_order` A/F display**: pending orders echo the unit letter inferred from coast
>   (a fleet at a non-split province prints `A`). Cosmetic only — adjudication uses the
>   board unit, not the letter. Pass unit kind through for human display.
> - **Order history** is no longer retained per-turn (state is a single snapshot); the
>   `/orders/history` endpoint returns empty. Add snapshot-derived history if needed.

### M7 — Enforcement, docs, ship  ← **COMPLETE (2026-07-27)**

Ordered so the suite/branch stays green at each commit; **merge to `main` is LAST.**

1. **M6 follow-ups first** (they change code; land + green before docs/CI polish):
   - [x] **Frontend TS types & API calls → new view shape** (highest priority; the only
         unported consumer). DONE (2026-07-27): `GameView.tsx` now consumes the GameState-
         native view (`phase`/`phase_type`/`year`/`season`/`status`/`units_by_power`/
         `ownership`/`dislodged`/`contested`/`players`), adapting units into the internal
         `UnitOut` shape; Pregame/lobby/start removed (engine has no lobby — a created game
         is at S1901M); join UI kept for claiming an unclaimed power. `GameView.test.tsx`
         updated to the new shape. Also fixed 8 pre-existing unused-import `tsc` errors in
         test files that had left `npm run build` red on this branch. Verified with a
         scratchpad Node 22: `npm run build` green, `npm run test:run` 88/88 green.
         (Old checklist text retained below for reference.)
         The new `/games/{id}/state` returns: `game_id, map_name, phase` (e.g. `"S1901M"`),
         `year, season, phase_type` (`MOVEMENT|RETREAT|ADJUSTMENT`), `status`
         (`ACTIVE|COMPLETED`), `units` (list of `{kind:"A"|"F", power, location:"PAR"|"SPA/SC"}`),
         `units_by_power` (power→that list), `ownership` (prov→power), `supply_centers`
         (== ownership), `dislodged` (`[{unit, attacker_origin, retreats:[...]}]`),
         `contested` ([prov]), `players` (power→`{user_id, is_active}`), `orders`
         (power→[order string]). Update TS interfaces + any `.powers`/`.current_*` access;
         `cd frontend && npm run build` + `npm run test:run` must pass. NOTE: the Python CI
         job does not build the frontend, so this won't surface as a red pytest.
   - [x] **Order/resolution map overlays.** DONE (2026-07-27). New adapter
         `src/rendering/order_overlay.py` translates engine `Order`/`Resolution` data into
         the renderer's order-dict format (the arrow primitives in `rendering/map.py` —
         `render_board_png_orders`/`render_board_png_resolution` — survived M6 intact; only
         the wiring was missing). `maps.py` `/generate_map/orders` now draws arrows from the
         current pending orders; `/generate_map/resolution` draws each adjudicated order's
         arrow coloured by its result plus standoff markers. Resolution is otherwise lost at
         `process_turn` (pending cleared, state is a single snapshot), so it is now persisted
         in a new nullable `games.last_resolution` JSON column (migration `b2c3d4e5f6a8`),
         written by `GameService.process_turn`. Tests: `tests/test_order_overlay.py` (12
         adapter unit tests) + `TestResolutionPersistence` in `tests/test_game_service.py`;
         E2E-smoked (orders map 724 KB, resolution map 735 KB, no render warnings). Full
         suite 812 passed / 15 skipped / 10 xfailed, ruff clean.
   - [x] **`format_order` human display** DONE (2026-07-27). Threaded an optional
         `kind_by_province` (province → `A`/`F`) through `format_order`/`_unit_str`/
         `_kind_letter`; when given, unit letters come from the board instead of the
         coast-presence inference. `GameService.view` now reparses+reformats echoed pending
         orders against the current units (`_humanize_orders`), so a fleet at a non-split
         province reads `F BRE H`, not `A BRE H`. Adjudication is unaffected (still uses the
         board unit). Tests: `TestOrderDisplay` in `tests/test_game_service.py`.
   - [x] **Per-turn order history** DONE (2026-07-27). `process_turn` now appends the
         submitted orders (truthful A/F letters) to a new nullable `games.order_history`
         JSON column (migration `c3d4e5f6a7b9`), keyed by turn: `{turn: {power: [order_str]}}`
         — the exact shape the Telegram bot's Order-History button expects. `/orders/history`
         returns it (empty until the first processed turn). Tests: `TestOrderHistory` in
         `tests/test_game_service.py`.
2. [x] **CI coverage gates** DONE (2026-07-27). CI now runs `pytest --cov=src
      --cov-report=term-missing` then two `coverage report` gates. **Measured** (local, on
      a DB): engine **92.91%**, overall **58.66%** — the plan's aspirational 95% engine was
      not real (dragged by `simple_ai` 79.76% — AI quality is out of scope — and
      `adjustments` 84.44% + defensive branches). Enforced floors, set just under measured
      with CI-variance margin: **engine `--include='src/engine/*' --fail-under=92`** (engine
      tests are env-independent, so the tight floor is safe) and **overall `--fail-under=57`**
      (lower because the Telegram/Discord bot modules are thin clients, intentionally lightly
      unit-tested). `.coveragerc` (`source = src`, `fail_under = 57`) and `pytest.ini` aligned
      and documented. Both gates verified green locally against a fresh-DB run.
- [x] `ruff check src/` clean (keep it clean; CI enforces it).
3. [x] **Docs.** DONE (2026-07-27). `CLAUDE.md` engine/persistence/rendering sections were
      already updated (M6). This step: wrote `docs/specs/adjudication.md` (Kruijswijk
      fixed-point algorithm, attack/defend/prevent/hold strengths, support-cut exemptions,
      cycle + Szykman backup rule, convoy path/intent rules, retreat legality,
      civil-disorder distance rule, and the 10 documented DATC `xfail` gaps — mined from
      `adjudicator/movement.py`/`retreats.py`/`adjustments.py` docstrings); rewrote
      `docs/specs/architecture.md` and `data_spec.md` (both were stale pre-rewrite
      drafts — `data_spec.md` still described `data_models.py`/relational
      units-orders-supply_centers tables that no longer back game state) to the actual
      `engine`/`persistence`/`rendering`/`server` package layout, the `state_json`-based
      persistence columns, and the `GameService.view` API shape; updated root
      `CODEBASE_OVERVIEW.md` (engine/server/rendering/persistence/tests sections, the
      architecture diagram, data-flow walkthrough, order examples) to match.
4. [x] **Merge `engine-rewrite` → `main`** DONE (2026-07-27). Direct push to `main` was
      rejected by branch protection (`2 of 2 required status checks are expected` — a
      brand-new merge commit SHA has no prior CI run, so a direct `git push` can never
      satisfy "required status checks" on a protected branch; this contradicts the literal
      reading of CLAUDE.md's "direct push is allowed" — in practice, for a merge this
      size, it has to go through a PR so GitHub associates the check runs with the merge
      commit). Routed through PR #5 (`merge-engine-rewrite` → `main`) instead: local
      `git merge engine-rewrite --no-ff` on `main`, pushed to a temp branch, opened the
      PR, both `test` and `security` checks passed (`test` 2m6s, `security` 27s), merged
      via `gh pr merge --merge`. Tagged `v2.7.15` on the resulting `main` commit
      (`f0e7ae2`) and pushed the tag. Temp branch `merge-engine-rewrite` deleted
      (local + remote). The merge migration `a1b2c3d4e5f7` (wipes all game rows) was
      called out in both the merge commit message and the PR description — moot in
      practice, since the maintainer confirmed **nothing is currently deployed anywhere**,
      so there is no live data to lose and no `/health` endpoint to verify against.
      `engine-rewrite` itself (the long-lived feature branch, distinct from the deleted
      `merge-engine-rewrite` temp branch) is scheduled for deletion in step 5.
5. [x] Final update of this file DONE (2026-07-27): everything checked, Status → complete.
      Deploy/`/health` verification skipped per the maintainer (nothing deployed yet —
      see step 4). `engine-rewrite` branch deleted (local + remote) now that `main`
      carries its full history via the merge commit.

**Environment reminder for whoever runs this:** DB-dependent tests skip silently without
`SQLALCHEMY_DATABASE_URL`; bring up Postgres first (see `local-postgres-for-m6` memory) and
`alembic upgrade head`. Don't trust a local green run without a DB.

---

## Definition of done

- [x] DATC cases green (144/154 + 10 documented hard-tail xfails). **Not yet enforced via a
      dedicated CI gate** — runs as part of the normal suite; a hard `datc`-marker gate can
      be added in M7 CI if desired.
- [x] Coverage gates enforced in CI (M7 step 2): engine **≥92%** (measured 92.91%; the
      aspirational 95% was not real — `simple_ai`/`adjustments`/defensive branches) and
      overall **≥57%** (measured 58.66%). Both in `.github/workflows/test.yml`.
- [x] Hypothesis property tests green (determinism, invariants, serialization round-trips).
- [x] 7-power AI self-play smoke green (`tests/engine/test_game.py::TestSelfPlaySmoke`,
      runs to ≥1911 or an 18-center win; invariants asserted every phase).
- [x] Live E2E through the HTTP API incl. coasted fleet move (create → `F STP/SC - BOT` +
      moves → advance → state + PNG map). Convoy adjudication covered by tests/datc 6.F/6.G.
- [x] Old engine + dead code deleted; specs updated (fix_plan, CLAUDE.md, adjudication.md,
      architecture.md, data_spec.md, CODEBASE_OVERVIEW.md).
- [x] **CI green on `main`** — merged via PR #5 (`test` + `security` both passed), tagged
      `v2.7.15`, `engine-rewrite` branch deleted.

## Out of scope

- Rewriting the rendering pipeline or DB layer (they move packages; call sites adapt).
- Map variants beyond `standard` (the 13 old `.map` variants are compatible — later).
- StrategicAI quality (stays a heuristic bot).
- Tournaments, Discord, observer/spectator mode, AI-powered analysis (long-standing
  out-of-scope list — kept here because CLAUDE.md points at this file for it).

## Risks / notes for whoever continues

- M6 has the widest blast radius: routes import engine internals and `database.py`
  helpers directly today. Funnel everything through `engine/serialization.py` once.
- A few DATC cases have rule-variant answers; follow DATC's stated preferred choice and
  note the choice in the test docstring.
- The rendering split must stay mechanical — resist redesigning it.
- DB-dependent tests silently skip without `SQLALCHEMY_DATABASE_URL` (see `conftest.py`);
  CI provides postgres:14, so don't trust a local green run without a DB.

---
---

# Finish the Port — make a game playable end-to-end again

> **Status: IN PROGRESS.** Started 2026-07-27. This is a *separate project* from the
> engine rewrite above, which is closed. Same maintenance contract applies: check tasks
> off in the same commit as the work, keep this Status block current, never drop
> discovered work silently.
>
> - **Done:** PR1 (merged, `v2.7.17`, PR #8) · PR2 (merged, `v2.7.18`, PR #10)
> - **NEXT TASK: PR3 — `frontend-phase-ui` + the frontend CI job.**
> - **Remaining after that:** PR4, PR5, PR6, then the manual end-to-end check.
> - **Last updated:** 2026-07-27 (Opus 5 driver + Sonnet implementation subagents).

## Why this project exists

The engine rewrite landed a correct adjudicator, but it **changed the shape of the game
state view and only some callers were ported**. The engine is fine; the layers that expose
it are not. Concretely, before this work a game could not be played past the first
dislodgement or the first build phase, and the Telegram bot could not start at all.

**Acceptance criterion for the whole project:** a game can be played end-to-end — movement,
retreat, and build phases — from *both* the browser and Telegram. No automated test spans
this; it is the manual check at the end.

## Execution model

One **Sonnet** subagent per PR, run one at a time in dependency order. The driver (Opus)
verifies every agent claim by direct read and by re-running the gates locally before
opening a PR — this has already caught several incorrect subagent claims, so **do not skip
it**. Agents push a branch and stop; they do not open or merge PRs.

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
3. `gh pr create -R tenderi/diplomacy` (the `-R` is mandatory; `gh` otherwise resolves the
   unrelated `upstream` remote).
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
  After a rebase changed the head SHA, `gh pr reopen` failed with
  `GraphQL: Could not open the pull request` — recovery required a brand-new PR (#9 → #10).
- Tagging the branch commit before the rebase left `v2.7.18` pointing at an **orphaned**
  SHA. Fixed with `git tag -f` + `git push -f origin v2.7.18`. Verify with
  `git merge-base --is-ancestor <tag> main`.

## Local gates (run before every push)

A local Postgres **is** configured and running for this repo, so DB tests really execute —
a skip means something is wrong, not that it is unavailable.

```bash
cd new_implementation && source venv/bin/activate
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=57
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

Coverage headroom is the hidden constraint: overall floor **57** against ~59.2 measured.
Test-count baseline as of PR2 merged: **844 passed, 15 skipped, 10 xfailed**.

---

## PR 1 — `bot-entrypoint` ✅ MERGED (`v2.7.17`, PR #8)

- [x] **The Telegram bot could not start at all.** `src/server/telegram_bot.py` (620 LOC,
      where every `CommandHandler` is registered) was **shadowed** by the same-named
      package `src/server/telegram_bot/`. `PYTHONPATH=src python -m server.telegram_bot`
      — verbatim the production systemd `ExecStart` at `infra/terraform/user_data.sh:159`
      — died with `'server.telegram_bot' is a package and cannot be directly executed`.
- [x] `git mv` → `src/server/telegram_bot/app.py` (contents unchanged; its imports were
      already absolute `server.telegram_bot.X`). Added `telegram_bot/__main__.py`.
- [x] `run_telegram_bot.py`: ~60 lines of hand-rolled `importlib` package forgery replaced
      with one `runpy.run_module` call.
- [x] `infra/scripts/run_bot_with_logs.sh` ran `python3 -m src.server.telegram_bot` (wrong
      `src.` prefix) — fixed. `user_data.sh` needed no change (`PYTHONPATH` already comes
      from `EnvironmentFile`).
- [x] **Why nothing caught it:** the three tests referencing the module loaded it via
      `spec_from_file_location` with a hand-forged `__package__`, which works fine on a
      shadowed file — they tested the workaround, not the real import path. Repointed them
      at `app.py` and switched to plain imports; they would otherwise have started
      **silently skipping**. Added `test_no_shadowing_telegram_bot_module` so the shadowing
      cannot come back, plus a subprocess smoke asserting the module now fails on the
      *missing token* rather than on import.
- [x] Gates: ruff clean, `822 passed`, `test_execution_context.py` 0 skips (was 3).

## PR 2 — `legal-orders-phase-aware` ✅ MERGED (`v2.7.18`, PR #10)

- [x] **`GET /legal_orders/{power}/{unit}` enumerated orders from map topology alone,
      ignoring the phase** — it never read `state.units`, `state.dislodged`, or
      `phase_type`. Consequences:
      1. Retreat phases unusable (movement orders offered for dislodged units).
      2. Build phases unusable **and silently destructive**: with no unit to key on, the
         browser asked about `myUnits[0]`, got movement orders that *passed* `validate()`
         and persisted — then `adjudicate_adjustments` (`adjustments.py:114`) dropped any
         non-Build/Disband/Waive order **without error**, silently waiving the builds.
      3. Split-coast bug: destinations unioned over *all* coasts, so a fleet at `STP/SC`
         was offered `STP/NC`-only destinations, and the coast was dropped from the output.
- [x] New **pure** `src/server/legal_orders.py` — `legal_orders_for_power(map, state,
      power)`. No FastAPI / DB / `game_service` import, so it is unit-testable without a
      database (this is also what protects the coverage floor). Returns `phase`,
      `phase_type`, `power`, `units`, `orders_by_unit`, flat `orders`, and an `adjustment`
      block (`delta`/`action`/`slots`) on Adjustment phases.
- [x] Reuse, not reimplementation: RETREAT reads the already-computed
      `DislodgedUnit.retreats`; ADJUSTMENT computes `delta` exactly as
      `adjudicate_adjustments` does and filters candidates through the **unmodified**
      `_validate_build` via a new public `legal_builds()` in `engine/orders/validation.py`.
- [x] New primary route `GET /games/{id}/legal_orders/{power}`; the per-unit route is now a
      lookup into `orders_by_unit`, preserving 404 (bad game) / 400 (malformed unit), and
      returning `{"orders": []}` **with 200** for a foreign or unknown unit — a 404 trips
      the frontend's fallback path. Province-only fallback so a bare `F STP` finds a unit
      standing on `STP/SC`.
- [x] `tests/test_legal_orders.py` (18 tests, no DB). The one that carries the PR: for
      movement, retreat, build and disband states, **every emitted string** for **every
      power** must satisfy `validate(parse_order(s), state, map).ok`.
- [x] Tightened `TestLegalOrders` in `test_api_routes_games.py` (3 → 7): it asserted
      `status_code in [200, 404]` and `isinstance(orders, list)`, so it could only fail on
      a crash, never on a wrong answer.
- [x] Gates: ruff clean, `844 passed`, engine 92.97%, overall 59.16%.

### Two findings from PR2 that later PRs must respect

- **`format_order` renders fleets as `A`.** It infers the unit letter from *coast presence*
  unless passed `kind_by_province` — so a fleet at any non-split province prints `A`. Any
  code emitting order strings must pass an explicit kind map. (Noted as a cosmetic M7
  follow-up above; it is not cosmetic once clients parse the strings back.)
- **`orders_by_unit` keys name their unit but do not always prefix it.** Keys are
  `f"{kind} {location}"` **with coast** (`"F STP/SC"`). Hold/move/support/convoy/retreat
  strings start with the key, but the engine's grammar is **verb-first** for builds and
  disbands (`D A PAR`, `BUILD F BRE`), so for those the key matches as a *suffix*.
  `WAIVE` has no unit and appears only in the flat `orders` list. Clients must not assume
  a prefix match.

---

## PR 3 — `frontend-phase-ui` + the frontend CI job  ← **NEXT TASK**

Ships together, because this is the first frontend change and **there is currently no
frontend job in CI at all** — nothing gates `tsc`, Vitest, or the build.

All three bug sites below were re-verified by direct read on 2026-07-27:

- [ ] `frontend/src/lib/orderParsing.ts` — add a `waive` type and a **leading-verb** branch
      *before* the null-guard. Verified dead today: for `D A PAR`, `parts[length-2]` is
      `"A"`, not `"D"`, so the destroy branch never fires and the function returns `null`;
      `WAIVE` returns `null` at the null-guard (`parts[i+1]` undefined). Moving the
      `' S '`/`' C '` checks above the `endsWith(' H')` check is worth doing defensively,
      **but is not an active bug** — `format_order` renders support-hold as `A PAR S A BUR`
      with no trailing `H`, so engine-emitted strings never collide.
- [ ] `frontend/src/pages/GameView.tsx` — one fetch of the new
      `/legal_orders/{power}` replaces the N+1 per-unit loop. Delete the `_build` bucket and
      all `myUnits[0]` indexing (`:376` — on an empty `myUnits`, `unit.unit_type` at `:384`
      **throws**; that is a power with zero units in an Adjustment phase, which PR2 now
      serves correctly). Unit keys must become `${kind} ${location}` carrying the coast —
      today `:365` builds them from `u.province`, so they can never match PR2's keys.
- [ ] `BuildOrdersSection` (`:202`, `:213-215`) — drop the **removed**
      `powerState.controlled_supply_centers`; take `slots`/`action` from the new
      `adjustment` block. This also removes the `Math.max(slotCount, ..., 1)` floor that
      renders a phantom build slot when `delta == 0`.
- [ ] **CI:** add a third `frontend` job to `.github/workflows/test.yml` — `npm ci`,
      `npx tsc -b --noEmit`, `npm run test:run`, `npm run build`, with
      `cache-dependency-path: new_implementation/frontend/package-lock.json` (the 97-byte
      root lockfile is an unrelated stub). **Add `frontend` to required status checks only
      after it has been green on `main` once**, or `main` bricks.
- [ ] Tests: `orderParsing.test.ts` for each new verb form; `GameView.test.tsx` blocks
      stubbing RETREAT and ADJUSTMENT states — assert exactly `slots` slots render, that
      options are build strings, and that **a power with zero units in an Adjustment phase
      renders without throwing** (today's crash).

## PR 4 — `bot-phase-aware` (largest)

API prerequisites, same PR: `routes/orders.py` `get_orders_for_power`/`get_orders` must
accept `telegram_id` + bot secret (Bearer-only today, so the bot gets **403** even after
the session fix); new `GET /games/{id}/map/history/{turn}`; promote
`_units_for_render`/`_phase_info`/`_svg_path_for_map_name` from `routes/maps.py` into a new
pure `src/rendering/view_adapter.py`.

- [ ] New `telegram_bot/game_context.py` with `resolve_game_and_power(user_id, game_id=None)`
      wrapping `api_get(f"/users/{id}/games")["games"]` — note that endpoint returns a
      **dict**, not a list. Replaces every dead `api_get(f"/users/{id}")` call (that route
      reads `user_sessions`, an in-memory dict populated only by `POST /users/register`,
      which the bot never calls → 404) and four copy-pasted resolution blocks.
- [ ] `orders.py`: fix `/myorders`, `/clearorders` (must also post `telegram_id` so
      `api_client.py:74` injects the bot secret — it 401s today), `/clear`,
      `/orderhistory`; make `/selectunit` read the units **list** and branch on
      `phase_type`; drive `show_possible_moves`/`show_convoy_*` from `legal_orders` and
      **delete `from rendering.map import Map`** (the bot must not import the engine or
      renderer — CLAUDE.md: it is a thin client over the HTTP API).
- [ ] Cache the fetched order list in `context.user_data` and put `ord|{game_id}|{idx}` in
      `callback_data` — the current scheme embeds order text and **overflows Telegram's
      64-byte cap** on convoys and coasted orders.
- [ ] `maps.py`: `/map`, `/viewmap`, `/replay` fetch PNG bytes via a new `api_get_bytes()`
      in `api_client.py`. `/replay` currently dies with `'list' object has no attribute
      'items'` — `rendering/map.py:1155` expects `{power: ["A BER"]}` but the new view's
      `units` is a **list of dicts**. Delete `send_demo_map` (broken twice over: it also
      calls the `@staticmethod` `render_board_png` with shifted args) and repoint
      `admin.py:69`.
- [ ] `games.py`: `/players` reads the bare list (`:355`, `:432`); `/status` reads
      `phase`/`phase_type`, deadline from `GET /games/{id}/deadline`, submission state from
      the new `/orders_status` (PR5).
- [ ] `ui.py:281`: `DESTROY A Munich` → `D A Munich` (the parser accepts only `D`/`DISBAND`);
      add retreat and `WAIVE` examples.
- [ ] **Check `normalize_order_provinces`** (`telegram_bot/orders.py:16-48`) against
      `WAIVE`/`BUILD`/`D` — it maps any `.isalpha()` token through `province_mapping` and
      will mangle verbs. Right fix is to stop calling it on strings that came from
      `legal_orders`.
- [ ] Also fix `infra/scripts/diagnose_bot.sh`: it references
      `/opt/diplomacy/src/server/run_telegram_bot.py`, missing the `new_implementation/`
      segment (prod path per `user_data.sh`'s `WorkingDirectory`). Found during PR1,
      deliberately deferred here.
- [ ] **Resurrect the 755 dead LOC of bot tests here, not in PR6.** `test_bot_functions.py`,
      `test_selectunit_fix.py`, `test_telegram_bot.py` collect **zero tests** because their
      classes are named `*Tester`, which does not match `python_classes = Test*`. Renaming
      alone would make them collect and instantly fail — they assert pre-rewrite shapes.
      Rename `*Tester` → `Test*` (leave `MockUser`/`MockUpdate`), add
      `@pytest.mark.asyncio`, rewrite fixtures to the new view shape, and add
      `test_selectunit_retreat_phase`, `test_selectunit_adjustment_phase`, and a test
      asserting `render_board_png` is **never** called from the bot for a game map.

## PR 5 — `turn-lifecycle` (independent of PR3/PR4)

- [ ] `POST /deadline` (`routes/games.py:469-484`) mutates a **detached** ORM object and
      never commits (the session closes at `database_service.py:315-318`, and
      `db_service.commit()` is a documented no-op) — so the deadline is silently discarded.
      Switch to `update_game_deadline`, which the scheduler already uses and which commits.
- [ ] Concurrency: `POST /process_turn` **does** correctly acquire its lock (`async with
      lock:` — an earlier survey claim that it only checks `lock.locked()` was wrong), but
      an `asyncio.Lock` is per-process and won't survive a second uvicorn worker. Add
      `expected_phase_code` to `GameRepo.save_state`, raise `StaleGameError` → 409. Drop the
      `lock.locked()` check in `api/shared.py:127-136`, which pretends to guard without
      acquiring.
- [ ] New `GET /games/{id}/orders_status` + `POST /process_turn?require_all=true`. **Default
      stays `false`** so no existing test changes; both clients pass `true`, the deadline
      scheduler never does.
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
      1033-LOC DAL. Start narrow: `update_game_deadline` round-trip incl. `None`, snapshot
      create/get, `get_players_by_game_id`, and an explicit test that `commit()` is a no-op
      so nobody reintroduces the detached-mutation pattern.

## PR 6 — `test-hygiene` (last, small)

- [ ] `pytest.ini`: `asyncio_mode = auto`; **remove `--disable-warnings`** — that flag is
      what hid the coroutine-never-awaited warnings. Triage the resulting noise with
      targeted `filterwarnings`, not by restoring the blanket flag.
- [ ] `@pytest.mark.asyncio` on `test_convoy_functions.py:229,235` — the only two genuinely
      silent async skips outside the uncollected files (an earlier claim of ~19 was wrong).
- [ ] Delete `tests/bot_test_runner.py` (never collected; 5 dead async functions).
- [ ] Ratchet the coverage floors to just under the new measured values; refresh the dated
      comments in `test.yml` / `.coveragerc`.
- [ ] Add `frontend` to required status checks via `gh api` (only once green on `main`).

## Final acceptance — manual end-to-end check

No automated test spans this. Run it after PR4.

- [ ] `PYTHONPATH=src python -m server.telegram_bot` starts (already true since PR1).
- [ ] Start the API; create a game, fill 7 powers; `/map` returns a PNG in Telegram.
- [ ] Order a deliberate dislodgement (A PAR–BUR supported, vs. A MUN–BUR); process.
- [ ] Phase `S1901R`: browser shows retreat options for the dislodged unit only; Telegram
      `/selectunit` offers retreats. Submit one, process — it takes effect.
- [ ] Play to `W1901A` with a captured centre. Both clients show exactly `delta` build
      slots with real home-centre options, and a power at `delta == 0` shows none. Submit a
      build, process — the unit appears on the map.
- [ ] `POST /games/{id}/deadline`, then `GET` it back — the value persists (it does not
      today; PR5).

## Out of scope for this project

The 10 DATC hard-tail xfails; the aspirational spec docs (`dashboard.md`,
`visualization_spec.md` §10); and everything in CLAUDE.md's standing out-of-scope list
(tournaments, Discord, observer/spectator mode, AI-powered analysis).
