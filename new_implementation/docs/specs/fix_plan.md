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

- **Phase:** **M0–M6 COMPLETE.** Ground-up engine rewrite done and integrated: the whole app
  runs on the new immutable engine. **Remaining: M7 (enforcement, docs, ship) + the M6
  follow-ups.** Not yet merged to `main`.

> ### ▶ RESUME HERE (fresh agent, start of session)
> 1. **Read this whole file**, then the M7 section + the "M6 follow-ups" box in the M6 section.
> 2. **Bring up a DB before running tests** — a no-DB run silently skips ~all integration
>    tests and looks falsely green. See the `local-postgres-for-m6` memory for the no-sudo
>    recipe (the scratchpad `PGDATA` is ephemeral and may need re-`initdb` each session).
>    Then: `export SQLALCHEMY_DATABASE_URL=postgresql+psycopg2://diplomacy_user:password@localhost:5432/diplomacy_db`
>    and `alembic upgrade head`.
> 3. **Baseline to confirm before changing anything:**
>    `PYTHONPATH=src python -m pytest tests/ -q` → **800 passed, 15 skipped, 10 xfailed**;
>    `ruff check src/` → clean.
> 4. **Do M7 in order** (below). The single most impactful M6 follow-up is the **frontend TS
>    types** — the React app still speaks the OLD API shape and will break at runtime until
>    ported; it is NOT covered by the Python CI, so it won't show up as a red test.
> 5. Work on `engine-rewrite`; merge to `main` is the LAST M7 step (CI on `main` runs
>    `test` + `security` and rejects red pushes). Do **not** build on `fix-oidc-trust`.

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
- **Branch:** work happens on `engine-rewrite` (off up-to-date `main`). Do **not** build on
  `fix-oidc-trust`; it carries unrelated in-flight infra work.
- **Last updated:** 2026-07-24 (Opus 4.8 — M6 COMPLETE: clean-break engine swap, old engine deleted, 800 green + E2E).

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

> **M6 follow-ups (not blocking; carry into M7/next):**
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

### M7 — Enforcement, docs, ship  ← **NEXT MILESTONE (do these in order)**

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
2. [ ] **CI coverage gates** (`.github/workflows/test.yml`). Today CI runs plain
      `pytest -q` (no coverage gate) + `ruff check src/`. **First measure**
      `pytest --cov=src --cov-report=term-missing` on a DB, then set realistic gates:
      overall `--cov-fail-under=<N>` and an engine gate
      `coverage report --include='src/engine/*' --fail-under=95` (engine is very high from
      tests/engine + tests/datc; server/rendering/bot are lower — pick the overall N from
      the measured number, don't guess 85 blind). Align `pytest.ini` + `.coveragerc`.
      **CI runs on a fresh `postgres:14`, so a green local run on a DB is required first.**
- [x] `ruff check src/` clean (keep it clean; CI enforces it).
3. [ ] **Docs.** `CLAUDE.md` engine/persistence/rendering sections are ALREADY updated
      (M6). Still to do: write `docs/specs/adjudication.md` (Kruijswijk fixed-point
      algorithm, attack/defend/prevent/hold strengths, support-cut exemptions, cycle +
      Szykman backup rule, retreat legality, civil-disorder distance rule — mine
      `adjudicator/movement.py`, `retreats.py`, `adjustments.py` docstrings); update
      `docs/specs/architecture.md`, `data_spec.md`, `CODEBASE_OVERVIEW.md` to the new
      layout + the new API view shape.
4. [ ] **Merge `engine-rewrite` → `main`** per CLAUDE.md branch workflow (version bump +
      tag). `main` is protected and rejects red pushes; `test` + `security` must pass on
      CI's fresh DB. The deploy migration `a1b2c3d4e5f7` **wipes all game rows** in prod —
      intended (game data disposable), but call it out in the merge/commit message. After
      merge verify deploy + `/health`, delete the branch.
5. [ ] Final update of this file: everything checked, Status → complete.

**Environment reminder for whoever runs this:** DB-dependent tests skip silently without
`SQLALCHEMY_DATABASE_URL`; bring up Postgres first (see `local-postgres-for-m6` memory) and
`alembic upgrade head`. Don't trust a local green run without a DB.

---

## Definition of done

- [x] DATC cases green (144/154 + 10 documented hard-tail xfails). **Not yet enforced via a
      dedicated CI gate** — runs as part of the normal suite; a hard `datc`-marker gate can
      be added in M7 CI if desired.
- [ ] Coverage gates enforced in CI: engine ≥95% (achievable now); overall N TBD from
      measurement (M7 step 2). **Not yet enforced.**
- [x] Hypothesis property tests green (determinism, invariants, serialization round-trips).
- [x] 7-power AI self-play smoke green (`tests/engine/test_game.py::TestSelfPlaySmoke`,
      runs to ≥1911 or an 18-center win; invariants asserted every phase).
- [x] Live E2E through the HTTP API incl. coasted fleet move (create → `F STP/SC - BOT` +
      moves → advance → state + PNG map). Convoy adjudication covered by tests/datc 6.F/6.G.
- [x] Old engine + dead code deleted; specs updated (fix_plan + CLAUDE.md; adjudication.md /
      architecture.md / CODEBASE_OVERVIEW.md still pending in M7).
- [ ] **CI green on `main`** (merge is the last M7 step; still on `engine-rewrite`).

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
