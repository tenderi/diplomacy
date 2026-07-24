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

- **Phase:** M3 nearly complete — resolver + full DATC 6.A–6.G authored (all 3 Sonnet
  subagents integrated) + hard-tail fixes. **245 passed, 10 xfailed, ruff clean.**
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
- **Next action:** M4 (retreats & adjustments — delegable to Sonnet). Optionally revisit
  the 10 xfail'd movement cases with a second-order-paradox resolver upgrade first.
- **Execution:** pipeline with mixed models — driver (Fable/Opus) owns M1, M3 core, M6;
  Sonnet/Haiku subagents take M2, M4, M5, M7 and DATC test batches. Milestones are
  sequential; each gated green before the next starts.
- **Branch:** work happens on `engine-rewrite` (off up-to-date `main`). Do **not** build on
  `fix-oidc-trust`; it carries unrelated in-flight infra work.
- **Last updated:** 2026-07-23 (Claude Fable 5 — M0 setup).

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
- [ ] **Done when:** DATC 6.A–6.G all green (~124 cases) + properties green.

### M4 — Retreats & adjustments

- [ ] `adjudicator/retreats.py`: legal destinations exclude attacker's origin, standoff
      provinces, occupied provinces; **all** units retreating to the same province
      disband; unordered dislodged units disband.
- [ ] `adjudicator/adjustments.py`: entitlement = owned SCs − units; build validation
      (owned home SC, vacant, fleet coast required where split); explicit + implicit
      waives; civil-disorder auto-disband (distance rule above).
- [ ] DATC cases: 6.H retreating (16), 6.I building (7), 6.J civil disorder (11).
- [ ] **Done when:** full DATC suite 160/160 green.

### M5 — Orchestration & serialization

- [ ] `src/engine/game.py`: phase machine, conditional retreat/adjustment phases, SC
      ownership updates, victory at 18, elimination, snapshot history.
- [ ] `src/engine/serialization.py`: canonical JSON for `GameState`/`Order`/`Resolution`;
      Hypothesis round-trip test.
- [ ] Port `strategic_ai.py` to the new types (keep it dumb; delete `OrderGenerator`).
- [ ] Self-play smoke test: 7 AI powers × 10+ game-years; invariants asserted every
      phase; no crash.
- [ ] **Done when:** smoke + round-trip green; engine package imports nothing but stdlib.

### M6 — Integration (riskiest milestone — server reaches into engine internals today)

- [ ] Move `src/engine/database.py` + `database_service.py` → `src/persistence/`; fix
      imports; drop `unit_to_dict`/`order_to_dict`/`dict_to_order` in favor of
      `engine/serialization.py`.
- [ ] Split rendering out of `src/engine/map.py` → `src/rendering/` (mechanical move,
      keep the render API); move `order_visualization.py` + `visualization_config.*` too.
- [ ] Adapt server: `src/server/api/shared.py` (`_state_to_spec_dict`), all routes in
      `src/server/api/routes/` (esp. `games.py`, `orders.py`), `server.py` CLI surface —
      public engine API only, no reaching into internals.
- [ ] Adapt DAIDE (`daide_protocol.py`) and bot `api_client.py`/frontend types to any
      changed JSON field names — change consumers, no compat shims.
- [ ] Alembic migration: wipe stored game rows (users/auth kept — game data is
      explicitly disposable per maintainer).
- [ ] Delete old engine: `game.py`, `data_models.py`, `order_parser.py`,
      `order_parser_utils.py`, `allowed_moves.py`, `power.py`, old `map.py` (topology
      half), hardcoded tables — plus bug-enshrining tests. Port keeper tests
      (`test_battle_resolution.py`, `test_standoff_detection.py`,
      `test_multi_coast_provinces.py`, parser/map tests…) to the new API in the same
      commits so the suite never lies.
- [ ] **Done when:** full suite green with a DB; server boots; API E2E: create game →
      submit orders (incl. coasted fleet move + convoy) → advance phase → fetch state+map.

### M7 — Enforcement, docs, ship

- [ ] CI (`.github/workflows/test.yml`): `pytest --cov=src --cov-fail-under=85` + engine
      gate `coverage report --include='src/engine/*' --fail-under=95`; align `pytest.ini`
      and `.coveragerc` (uncomment/fix).
- [ ] `ruff check src/` clean.
- [ ] Write `docs/specs/adjudication.md`: the algorithm, strength definitions, cycle and
      Szykman rules, civil-disorder rules. (No spec covers this today.)
- [ ] Update `docs/specs/architecture.md`, `data_spec.md`, `CODEBASE_OVERVIEW.md`, and
      `CLAUDE.md` (new `engine/persistence/rendering` layout).
- [ ] Merge `engine-rewrite` → `main` per CLAUDE.md branch workflow (version bump + tag),
      delete branch, verify deploy + `/health`.
- [ ] Final update of this file: everything checked, Status → complete.

---

## Definition of done

- [ ] 160/160 DATC cases green, enforced in CI.
- [ ] Coverage gates enforced in CI: ≥85% overall, ≥95% `src/engine/`.
- [ ] Hypothesis property tests green (determinism, invariants, round-trips).
- [ ] 7-power AI self-play, 10+ years, zero invariant violations.
- [ ] Live E2E through the HTTP API incl. coasted move + convoy.
- [ ] Old engine + dead code deleted; specs updated; CI green on `main`.

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
