# Perfect Demo Game

`examples/demo_perfect_game.py` plays a scripted Diplomacy game end to end and renders a map
series for every phase. It is both an educational artefact and the project's final
end-to-end check: because the orders are hardcoded, any change in adjudication or rendering
shows up immediately as a different result.

```bash
PYTHONPATH=src python examples/demo_perfect_game.py
```

## Design

- **Hardcoded scenarios, not AI.** Orders are pre-written per phase in `load_scenarios()` as
  `ScenarioData` records (year, season, phase, orders, expected outcomes, description). An
  earlier version generated orders heuristically; that made the output non-reproducible and
  was replaced.
- **Deterministic.** The same inputs always produce the same result. The only derived orders
  are retreats, generated from the units the engine actually dislodged — still deterministic,
  since those follow from the hardcoded orders. Scenario adjustment
  (`adjust_scenario_for_state`) is a deterministic transformation against the real board.
- **Strategically coherent.** Every move makes sense; no self-attacks or nonsense orders.
- **Complete coverage.** Two years (1901–1902) exercising all order types — move, hold,
  support (both kinds), convoy, retreat, build, disband — plus the interesting mechanics:
  2-1 supported attacks, standoffs, support cuts, convoy disruption, self-dislodgement
  prevention, and beleaguered garrison.

## Flow

1. Create a game on the standard map and add all seven powers.
2. For each scenario in order: adjust it against the actual board, submit the orders, render
   the phase's maps, process the turn, and verify the expected outcomes.
3. Retreat and adjustment phases run only when the engine actually enters them.
4. Stop when the game is done, all scenarios are exhausted, or a 50-phase safety limit is
   reached.

Phase sequence over the two years:
`S1901M → [S1901R] → F1901M → [F1901R] → W1901A → S1902M → [S1902R] → F1902M → [F1902R] → W1902A`

## Map output

Up to four maps per phase — `initial`, `orders`, `resolution`, `final` — written to
`test_maps/` as
`perfect_demo_{year}_{season_num}_{phase_num}_{season}_{phase}_{type}.png`, using the same
renderer the API uses (see [`visualization_spec.md`](visualization_spec.md)).

**Maps are only generated for phases that actually ran.** Skipped scenarios — a retreat
phase with no dislodgements, or a scenario that no longer matches the board — produce no
files, so the output directory reflects the real game rather than the script.

## Verification

After each processed phase the demo checks supply-center control and unit positions against
the scenario's recorded expected outcomes and reports any divergence.
