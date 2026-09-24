# Adjudication — the Kruijswijk Fixed-Point Resolver

> Companion to [`fix_plan.md`](fix_plan.md) (the M0–M7 engine-rewrite tracker) and
> [`diplomacy_rules.md`](diplomacy_rules.md) (rulebook prose). This document covers the
> **algorithm**: how `src/engine/adjudicator/` turns a `(map, state, orders)` triple into a
> `(Resolution, next_state)` pair. It is mined from the source docstrings in
> `movement.py`, `retreats.py`, `adjustments.py` — those files are the ground truth; this
> doc explains *why* they're shaped the way they are and ties the pieces together.
>
> Conformance: 144/154 DATC cases green (`tests/datc/`), 10 documented hard-tail `xfail`s
> (listed at the end). Everything below is implemented, not aspirational.

## 1. Why fixed-point, not a single pass

Diplomacy orders are **simultaneous and interdependent**: whether move A succeeds can
depend on whether support B holds, which depends on whether move C cuts it, which depends
on whether A succeeds. A single linear pass over orders (the pre-rewrite engine's
approach) cannot get this right — see `fix_plan.md` §"Why a rewrite", defect 1.

The fix is Kruijswijk's algorithm ("The Math of Adjudication"): treat the outcome of
every move, support, and convoy order as a boolean **predicate** and resolve them by
mutual recursion with memoization, exactly as you'd resolve a system of mutually
recursive functions. Three predicates:

- `move_succeeds(m)` — does move `m` advance its unit?
- `support_given(s)` — is support `s` effective (valid and not cut)?
- `convoy_survives(c)` — does convoying fleet `c` avoid dislodgement?

`src/engine/adjudicator/movement.py`'s `_Resolver` class implements all three as methods
(`_move_succeeds`, `_support_given`, `_convoy_survives`) dispatched through one entry
point, `_resolve(province)`, keyed by the province of the ordering unit.

## 2. The resolve loop: UNRESOLVED / GUESSING / RESOLVED

Each order's resolvable item (`_Item`) carries a three-valued state:

- **UNRESOLVED** — not yet computed.
- **GUESSING** — computation is in progress; the current `value` is a provisional guess.
- **RESOLVED** — final; `value` is authoritative and memoized.

`_resolve(prov)`:

1. If already `RESOLVED`, return the memoized value.
2. If already `GUESSING`, we've re-entered an order that's still being computed — that's
   a **dependency cycle**. Record `prov` in `self._deps` (the current recursion's
   dependency trail) and return the current guess.
3. Otherwise: mark `GUESSING` with a provisional guess of `False`, then compute via
   `_adjudicate(prov)` (dispatches to `_move_succeeds` / `_support_given` /
   `_convoy_survives`).
4. If no cycle was hit (`self._deps` didn't grow), the computed value is definitive:
   mark `RESOLVED` and return it. This is the common case — most orders have no cyclic
   dependency and resolve in one pass.
5. If a cycle was hit but `prov` isn't its head (some earlier order re-entered before we
   did), propagate the guess upward and let the head handle it.
6. If `prov` **is** the cycle's head: this is where the interesting cases live (§3).

## 3. Breaking cycles: circular movement vs. the Szykman rule

When the head of a cycle is reached, the resolver **tries both truth values** for that
order and re-evaluates the whole cycle each time:

- Reset every other member of the cycle to `UNRESOLVED`, guess the head is `True`, and
  re-run `_adjudicate`. Compare against the first pass (head guessed `False`).
- **If both guesses produce the same outcome** (guess-independent), that shared value is
  correct — take it and move on. This resolves most cycles: the truth value simply
  doesn't depend on the guess.
- **If the two guesses disagree**, the cycle is a genuine paradox and the **backup rule**
  (`_backup_rule`) breaks it:
  - A cycle containing **only moves** (no convoy, no support) is *circular movement* —
    DATC 6.C's army-swap-via-convoy and multi-unit rotation cases. **Every move in the
    cycle succeeds.** This is the classic "three armies chase each other around a
    triangle" case; simultaneity means they all get where they're going.
  - A cycle that touches **both a convoy and a support** is a *convoy paradox* (DATC
    6.F.14–6.F.24, the Szykman-rule cases). The **Szykman rule** applies: every convoyed
    move in the cycle **fails**, as if its convoy had never been ordered. Everything else
    in the cycle (holds, other supports) is then re-resolved against that fixed outcome.

  The distinction is deliberate: a cycle of pure moves (even one routed through a
  convoy, as in a same-power army swap) is not a paradox — nothing about it is
  self-referential once you fix "everyone moves." A paradox only arises when a support's
  cut-or-not status and a convoy's survival-or-not status depend on each other in a loop
  that has no consistent resolution without a tiebreaker.

This is a **single-pass** backup rule: once a cycle is broken, its members are marked
`RESOLVED` and not revisited. The engine does not implement iterative re-resolution for
*second-order* paradoxes (a paradox whose break exposes a second, dependent paradox) —
see §8, the documented `xfail`s (6.F.16/17/18/23/24).

## 4. Strength model

Every strength number folds in "supports that count," with several **exemptions** that
are the actual substance of DATC §6.D:

- **Hold strength** of a province (`_hold_strength`): `0` if empty; `0` if its occupant
  is ordered to move and that move actually happens (it vacated); otherwise
  `1 + valid uncut hold-supports`. A unit ordered to move that *fails* still holds at
  strength 1 with **no** hold support (a unit can't get both — DATC 6.D.7/8/25: a legally
  moving unit cannot receive hold support even if the move later bounces).
- **Attack strength** of a move (`_attack_strength`): `0` if its convoy path is required
  and broken; `0` if it would dislodge a unit of its **own power** (a unit never
  dislodges its own side, even head-to-head); otherwise `1 + supports`, where a support
  from the **defender's own power** does not count toward dislodging that defender
  (`fix_plan.md` defect 4 — the old engine got this backwards).
- **Defend strength** (`_defend_strength`, used in head-to-head battles) and **prevent
  strength** (`_prevent_strength`, used for standoffs against a third unit's move into
  the same empty province): both `1 + supports`, with the same support-source exemptions
  as attack strength. A move that itself loses a head-to-head battle prevents nothing
  against third parties (`_prevent_strength`'s head-to-head short-circuit).

A move succeeds (`_move_succeeds`) when: its convoy path (if any) works; its attack
strength beats every competing move's prevent strength into the same destination
(standoff check); and, if the destination is occupied, either the occupant vacates, or
(in a head-to-head) the attacker's strength beats the occupant's defend strength, or (a
stationary occupant) the attacker's strength beats the occupant's hold strength — and
never against a unit of the attacker's own power.

## 5. Support cuts

A support is **void** (illegal, reported `VOID`, contributes nothing) — computed once,
geometrically, before the cut question is even asked — when (`_support_is_void`):

- it's not a legally reachable support for the supporting unit (`_support_valid`), or
- it names no real order to support (`_support_has_target`) — e.g. a hold-support for an
  empty province, or a move-support whose named mover isn't actually moving there, or
- (`SupportMove`) it would help dislodge a **holding unit of the supporter's own power**
  at the destination — *unless* that unit is itself moving away and the destination is
  independently contested by another attacker (DATC 6.E.12: the support "serves other
  means" rather than self-dislodgement; a unit that vacates via circular movement,
  6.C.2, was never being dislodged at all), or
- (`SupportHold`) it targets a unit that is itself **legally ordered to move** (DATC
  6.D.7/8/25 again — an illegal/ignored move leaves the unit holding, so support for it
  is fine, 6.D.28/29).

Given a non-void support, `_support_given` checks every other order for a move that (a)
targets the supporting unit's own province, (b) isn't the very unit being supported
(a supported unit never cuts its own support), (c) isn't from the **same power** as the
supporter (DATC 6.D.20 — you cannot cut your own country's support), and (d) isn't a
convoyed move whose convoy path is itself broken (a disrupted convoy attack cuts
nothing). One exception inside that: an attack from the province the support is
targeting *against a move* only cuts by actually **dislodging** the supporter — this is
the "attack from the supported-against province" exemption in the rulebook (a unit can
attack a move it's the target of without automatically cutting the support of that
move, unless it wins).

## 6. Convoys

A convoyed move is only *recognized as convoyed* — as opposed to illegal or a plain land
move — under specific conditions (`_uses_convoy`):

- Non-adjacent army moves are always convoyed (there's no other way to make the trip).
- For an **adjacent** move: an explicit `VIA` forces convoy semantics whenever *some*
  fleet (any power) has actually been ordered to carry it (DATC 6.G.10/6.G.14) — with no
  matching Convoy order, `VIA` is ignored and the army walks (6.G.8). Without `VIA`,
  convoy intent is inferred **only** for a two-unit swap riding the army's **own power's**
  convoy chain — a foreign fleet cannot "kidnap" a friendly army onto a convoy it never
  asked for (DATC 6.G.2/6.G.4/6.G.7; the corresponding legitimate case is 6.G.1/5/6, and
  a *valid* such convoy that also creates a cycle is the 6.G.11 paradox).

The convoy **path** itself (`_convoy_path_works`) is a breadth-first search over
currently-surviving convoying fleets (`Convoy` orders whose origin/dest match the move,
filtered to fleets not dislodged this phase), starting from fleets adjacent to the
army's source coast and searching for one adjacent to the destination. This directly
supports **multi-route convoys**: if any surviving subset of the ordered fleets forms an
unbroken chain, the move works — losing one fleet in a multi-fleet, multi-route convoy
order no longer fails the whole move (`fix_plan.md` defect 3).

Three convoy-order result codes reflect fine distinctions DATC cares about:
`VOID` (no matching army move exists to convoy — 6.D.27), `DISLODGED` (the fleet itself
was dislodged this phase), and `NO_CONVOY` (the fleet survived but the chain is broken
elsewhere, e.g. a sibling fleet died) vs. plain `OK` (chain intact, even if the convoyed
army merely bounced at the far end — the convoy did its job).

Critically, **a convoyed army's attack strength is never boosted by the number of
convoying fleets** — it's still `1 + supports`, same as any other move
(`fix_plan.md` defect 2; the old engine wrongly counted convoy legs as strength).

## 7. Assembling the phase result

After every order resolves (`run()`), the resolver derives, in order:

1. **Standoff provinces** (`contested`): an *empty* province targeted by ≥2 moves, none
   of which succeeded. Only empty-province standoffs are recorded here — a contested
   *occupied* province is instead reflected in the occupant's hold/dislodge outcome.
2. **Surviving units**: for each pre-phase unit, if its move succeeded it lands at the
   destination (coast-resolved via `_move_dest_location` — an explicit coast is kept,
   otherwise inferred when the reachable set is unambiguous); otherwise it's dislodged
   (`_is_dislodged`) or stays put.
3. **Dislodged unit records**: for each dislodged unit, its `attacker_origin` (the
   province the successful attacker moved from — `None` if that attack was convoyed,
   since a convoyed attacker crosses no shared border and so imposes no "can't retreat
   the way you came" block) and its precomputed legal `retreats`, via
   `retreats.compute_retreat_options` (§8 below) — computed once, here, against
   **post-resolution** occupancy, so the retreat phase never has to recompute legality
   from stale pre-move board state.
4. **Per-order `OrderResult`s** with the appropriate `ResultCode` (`OK` / `BOUNCE` /
   `CUT` / `VOID` / `NO_CONVOY` / `DISLODGED`), each carrying its `retreat_options` when
   applicable.

The returned `GameState` has `units`, `dislodged`, and `contested` populated; `game.py`
(the phase machine, §9) then decides whether the next phase is a retreat phase, the next
movement phase, or an adjustment phase.

## 8. Retreats

`src/engine/adjudicator/retreats.py` is deliberately split into a pure legality function,
`compute_retreat_options`, and the phase adjudicator, `adjudicate_retreats`, because the
legality function is needed **twice**: once by the movement resolver (to populate
`DislodgedUnit.retreats` and each order's `retreat_options`, both surfaced to players
before they choose), and once by the retreat phase itself to validate submitted orders.
Computing it once and reusing it (rather than recomputing from possibly-stale state) is
the whole point — see the module docstring's framing as "the single source of truth."

A destination is legal iff: the unit could reach it by ordinary adjacency (land for
armies, sea/coast for fleets — coasts are first-class, so a fleet retreating into a
split-coast province gets one candidate per reachable coast); it is **not**
`attacker_origin` (you can't retreat the way the attack came, unless that attack was
convoyed); no **surviving** unit already occupies it; and it isn't in `contested` (a
province that stood off this same movement phase admits no retreats either — too much
traffic).

The retreat phase itself (`adjudicate_retreats`) resolves each dislodged unit's
attempted destination (a legal `Retreat` order, or `None` for an explicit `Disband` or no
order at all), then applies one more collision rule that only bites here: **if two or
more units attempt to retreat into the same province, all of them fail and disband** —
not "first submitted wins" (the old engine's defect 7), and not decided by strength
(retreats don't have supports). An unordered or illegally-ordered dislodged unit disbands
outright.

## 9. Adjustments (builds, disbands, civil disorder)

`src/engine/adjudicator/adjustments.py` reconciles each power's **unit count** against
its **supply-center count** independently, power by power:

- **`centers > units`** (`_resolve_builds`): entitlement is `centers - units`, further
  capped in practice by how many *valid* builds exist (a power can be entitled to 3
  builds but have only 1 vacant home center). Each `Build` order is validated
  (`orders/validation.py` — must be a currently-owned **home** supply center, must be
  vacant, a fleet build at a split-coast province must name a coast) up to the
  entitlement; excess or invalid `Build`s are `VOID`. Explicit `Waive` orders consume a
  build slot without producing a unit; any entitlement left over after processing all
  submitted orders — whether from explicit waives or simply unordered — is implicitly
  waived (silently, no unit appears, reported as a synthetic `WAIVE` result). A `Disband`
  submitted while a power is owed builds is meaningless and `VOID` (you can't shrink
  when you're entitled to grow).
- **`centers < units`** (`_resolve_disbands`): the power must remove `units - centers`.
  Valid submitted `Disband` orders are honoured first, up to the required count; any
  shortfall is made up by **civil disorder** — automatic removal, unordered, following
  the rulebook's distance rule (`_civil_disorder_order`): farthest from the power's
  nearest home supply center first (by shortest route — for armies this traverses land
  *and* sea steps, since a convoy could in principle carry them home, so
  `_distance_to_home`'s BFS for armies is not restricted to land adjacency; fleets are
  restricted to fleet adjacency), fleets removed before armies on a distance tie, and
  alphabetical by province as the final tiebreak. A `Build` or `Waive` submitted while a
  power owes disbands is `VOID` (you can't grow while shrinking).
- **`centers == units`**: no adjustment is owed; any `Build`/`Disband`/`Waive` submitted
  is `VOID`.

## 10. The phase machine

`src/engine/game.py`'s `Game.adjudicate()` dispatches to whichever of the three
adjudicators matches `state.phase_type`, then computes the next phase
(`_transition`):

```
S{y}M → [S{y}R if dislodgements] → F{y}M → [F{y}R if dislodgements]
      → [W{y}A if any power's units ≠ centers] → S{y+1}M → …
```

Supply-center ownership is recomputed once, after the **Fall** turn fully settles
(movement plus any retreats) — whoever occupies a center at that instant claims it;
unoccupied centers keep their previous owner. Victory (`VICTORY_CENTERS = 18`) is
checked at that same point, before deciding whether an adjustment phase is needed. `Game`
itself is a frozen dataclass (`map`, current `state`, `history` of past snapshots) — every
call to `adjudicate()` returns a *new* `Game`, never mutates the old one.

## 11. Documented deviations / known gaps

Ten DATC cases are `xfail` with the reason recorded in the test file docstrings — not
silently skipped, and not to be un-xfailed without the corresponding engine work:

- **6.F.16/17/18/23/24** — second-order convoy paradoxes. The single-pass backup rule
  (§3) resolves first-order paradoxes correctly but does not iterate: breaking one
  paradox can, in principle, expose a second, dependent paradox that this resolver
  doesn't re-detect. Needs an iterative Szykman re-resolution loop.
- **6.G.7/11** — convoy-to-adjacent-province intent-inference edge cases at the boundary
  of the "own-power swap only" rule in §6.
- **6.E.8/6.E.10** — beleaguered-garrison self-dislodgement variants that the current
  support-void rule (§5) does not distinguish from the legitimate "serves other means"
  case, 6.E.12.
- **6.D.8** — a DATC case with a stated rule-variant answer; this engine treats a
  no-fleet convoy move as illegal/ignored, which is the reading consistent with how it
  already handles 6.D.28/29/31/32.

## 12. Where to look

- `src/engine/adjudicator/movement.py` — the resolver (§2–7).
- `src/engine/adjudicator/retreats.py` — retreat legality + phase (§8).
- `src/engine/adjudicator/adjustments.py` — builds/disbands/civil disorder (§9).
- `src/engine/game.py` — phase machine (§10).
- `tests/datc/` — one test per DATC case, tagged with the `datc` pytest marker, organized
  by section (`6.A`–`6.J`); `tests/datc/harness.py` has the `place_units` /
  `give_orders` / `adjudicate` / `assert_result` / `assert_dislodged` helpers used
  throughout.
- `tests/datc/test_properties.py` — Hypothesis properties: order-shuffling never changes
  the outcome (determinism), ≤1 unit per province post-resolution, unit conservation,
  every dislodged unit has a computed legal retreat set.
