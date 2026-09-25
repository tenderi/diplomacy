# Testing and Validation Strategy

How this project is tested, what the gates are, and the conventions to follow when adding
tests. For what each test file covers, see
[`CODEBASE_OVERVIEW.md` §9](https://github.com/tenderi/diplomacy/blob/main/CODEBASE_OVERVIEW.md).

## Gates

CI ([`.github/workflows/test.yml`](https://github.com/tenderi/diplomacy/blob/main/.github/workflows/test.yml)) runs three jobs,
all three of which are required status checks on `main`:

| Job | What it runs |
|---|---|
| `test` | `ruff check src/`, the full pytest suite against a fresh `postgres:14`, and two coverage floors. |
| `frontend` | `npx tsc -b --noEmit`, `npm run test:coverage` (Vitest with coverage thresholds), `npm run build`. |
| `security` | `pip-audit` on `requirements.txt` and `bandit` on `src/`. |

Coverage floors: **engine ≥95%** (`coverage report --include='src/engine/*'`), **overall
≥80%**, and the frontend thresholds in `frontend/vite.config.ts` (90% of lines). Each sits
two to three points under the measured number: room to delete covered dead code, not to
stop testing.

Reproduce the gates locally before pushing:

```bash
ruff check src/
bandit -q -r src/ -ll
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=95
coverage report --fail-under=80
cd frontend && npx tsc -b --noEmit && npm run test:coverage && npm run build
```

## The database trap

**Database-dependent tests skip silently without `SQLALCHEMY_DATABASE_URL`** (or
`DIPLOMACY_DATABASE_URL`, or a `.env` in the repository root). A local run without a
database looks green while testing almost nothing. If a test you expect to run is skipped,
the environment is wrong — never treat a no-DB green run as a pass. CI always provides a
fresh Postgres container.

## Markers

Declared in `pytest.ini`; select with `pytest -m <marker>`.

| Marker | Meaning |
|---|---|
| `unit` | Isolated, fast, no external dependencies. |
| `integration` | Multiple components together; may use a real database. |
| `database` | Requires a database connection. |
| `datc` | DATC conformance cases. |
| `map` | Requires map files or CairoSVG rendering. |
| `telegram`, `channels` | Bot commands and group integration (Telegram API mocked). |
| `slow` | Long-running scenarios and simulations. |
| `execution_context` | The bot as production runs it: its image's imports, `python -m server.telegram_bot`. |
| `deployment`, `infrastructure` | Compose file, host scripts, the deploy workflow. |
| `ai`, `performance` | Order-generation heuristics; benchmarks. |

`asyncio_mode = auto`, so async tests need no explicit marker.

**`filterwarnings` is empty on purpose, and must stay that way.** A blanket
`--disable-warnings` or `ignore::DeprecationWarning` hides real bugs (naive-`datetime`
misuse among them). Fix or narrowly silence the individual warning instead.

## Test layers

**Engine (`tests/engine/`, `tests/datc/`)** — the engine is pure, so it needs no fixtures,
no database, and no mocks. This is where correctness actually lives:

- `tests/datc/` — one test per official DATC case (6.A–6.J, plus two extra cases in 6.K).
  144 of 154 pass; 10 are documented `xfail`s with the reason inline. **Do not un-xfail one
  without the corresponding engine work** (see [`adjudication.md`](adjudication.md) §11).
- `tests/datc/harness.py` — `Harness().units(...)`, `.orders(...)`, `.adjudicate()`, the
  retreat and adjustment variants, and `assert_success` / `assert_bounce` /
  `assert_dislodged` / `assert_result`. Use it rather than hand-rolling state.
- `tests/datc/test_properties.py` — Hypothesis properties over random positions *with
  supports*, so dislodgements happen: shuffling the order list never changes the outcome
  (determinism), ≤1 unit per province after resolution, unit conservation, and every retreat
  offered is one the rules allow.
- `tests/engine/test_purity.py` — every engine import is the standard library or `engine`.

**Service and API** — `GameService` scenarios driven through the real public API
(`create_game` → `submit_orders` → `process_turn` → `view`), and route tests asserting the
GameState-native response shape. Prefer driving a real game to hand-building a `GameState`.
`tests/test_concurrent_processing.py` covers the cross-process guard, and
`tests/test_cache_coherence.py` that no cached read shows the world before your own write.

**Clients** — bot tests mock the Telegram API and assert the HTTP contract of each command
and the route of each button (`tests/test_bot_commands.py`, `tests/test_bot_routing.py`);
`tests/test_execution_context.py` rejects any bot import its Docker image lacks. Frontend
tests use Vitest + React Testing Library — see
[`frontend/docs/TESTING.md`](https://github.com/tenderi/diplomacy/blob/main/frontend/docs/TESTING.md).

**Rendering** — render through the real functions and assert on pixels where it matters
(`tests/test_board_render.py`: ownership and a fleet at sea tint their provinces; the render
cache never serves one board for another). For changes that should be behaviour-preserving,
compare **sha256 of the rendered PNG before and after** with the byte cache cleared: a
swallowed exception can hand back a subtly wrong image while every test still passes.

## Conventions

- **Every test must be able to fail.** `tests/test_suite_hygiene.py` rejects a test with no
  assertion. Assert the exact value, message or status code — never "one of these codes", and
  never a list that includes 500. When a test passes suspiciously easily, check that it
  exercises the real path (a frontend test with a bare `MemoryRouter` and no `<Route>` only
  ever sees the loading spinner). A new test should fail without the change it covers.
- **Use real topology.** Build state from `Game.new_standard()` or the DATC harness so
  adjacency comes from `maps/standard.map`, never from hand-written adjacency data.
- **No real sleeps.** Use an injectable or patched clock, or call the function under test
  directly (e.g. `check_and_send_reminders(now)`).
- **Mock only at boundaries** — the Telegram API, SMTP, the filesystem. Do not mock the
  engine, `GameService`, or the database when a real one is available.
- **Don't depend on row order the database doesn't promise.** Compare sorted, or by key.
- **Cover new database code.** `DatabaseService` is large; any new method needs a direct
  test.
