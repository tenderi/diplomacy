# Testing and Validation Strategy

How this project is tested, what the gates are, and the conventions to follow when adding
tests. For what each test file covers, see
[`CODEBASE_OVERVIEW.md` §9](../../../CODEBASE_OVERVIEW.md).

## Gates

CI ([`.github/workflows/test.yml`](../../../.github/workflows/test.yml)) runs three jobs,
all three of which are required status checks on `main`:

| Job | What it runs |
|---|---|
| `test` | `ruff check src/`, the full pytest suite against a fresh `postgres:14`, and two coverage floors. |
| `frontend` | `npx tsc -b --noEmit`, `npm run test:run`, `npm run build`. |
| `security` | `safety` and `bandit` scans. |

Coverage floors: **engine ≥92%** (`coverage report --include='src/engine/*'`) and
**overall ≥60%**. The engine floor has under a point of headroom and is deliberately not
ratcheted tighter — a tighter floor would make ordinary dead-code deletion fail CI.

Reproduce the gates locally before pushing:

```bash
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

## The database trap

**Database-dependent tests skip silently without `SQLALCHEMY_DATABASE_URL`** (or
`DIPLOMACY_DATABASE_URL`, or a `.env` in `new_implementation/`). A local run without a
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
| `telegram`, `channels` | Bot commands and channel integration (Telegram API mocked). |
| `slow` | Long-running scenarios and simulations. |
| `execution_context` | Code run as a script / under a production `PYTHONPATH`, not just imported. |
| `deployment`, `infrastructure` | Deployment scripts, systemd/nginx config validation. |
| `ai`, `performance` | Order-generation heuristics; benchmarks. |

`asyncio_mode = auto`, so async tests need no explicit marker.

**`filterwarnings` is empty on purpose, and must stay that way.** The blanket
`--disable-warnings` and `ignore::DeprecationWarning` entries that used to live there were
concealing 22 real naive-`datetime` bugs. Do not add blanket entries; fix or narrowly
silence the individual warning instead.

## Test layers

**Engine (`tests/engine/`, `tests/datc/`)** — the engine is pure, so it needs no fixtures,
no database, and no mocks. This is where correctness actually lives:

- `tests/datc/` — one test per official DATC case (6.A–6.J, ~154 cases). 144 pass; 10 are
  documented `xfail`s with the reason inline. **Do not un-xfail one without the
  corresponding engine work** (see [`adjudication.md`](adjudication.md) §11).
- `tests/datc/harness.py` — `place_units` / `give_orders` / `adjudicate` / `assert_result` /
  `assert_dislodged`. Use it rather than hand-rolling state.
- `tests/datc/test_properties.py` — Hypothesis properties: shuffling the order list never
  changes the outcome (determinism), ≤1 unit per province after resolution, unit
  conservation, every dislodged unit has a computed legal retreat set, and the engine
  imports nothing outside the standard library.

**Service and API** — `GameService` scenarios driven through the real public API
(`create_game` → `submit_orders` → `process_turn` → `view`), and route tests asserting the
GameState-native response shape. Prefer driving a real game to hand-building a `GameState`.

**Clients** — bot tests mock the Telegram API and assert against the HTTP layer; the bot
must never call the engine or renderer directly, and there is a test asserting exactly that.
Frontend tests use Vitest + React Testing Library — see
[`frontend/docs/TESTING.md`](../../frontend/docs/TESTING.md).

**Rendering** — render through the real API-route functions and assert on PNG magic bytes
and non-trivial size. For changes that should be behaviour-preserving (module splits,
exception narrowing), compare **sha256 of the rendered PNG before and after** with the byte
cache cleared. That check catches what the suite cannot: a swallowed exception handing back
a subtly wrong image while every test still passes.

## Conventions

- **Use real topology.** Build state from `Game.new_standard()` or the DATC harness so
  adjacency comes from `maps/standard.map`, never from hand-written adjacency data.
- **Assert something.** Several historical test files collected zero tests or asserted
  nothing at all (a `MemoryRouter` with no `<Route>` leaves `useParams()` unresolved and
  tests only the spinner; `*Tester` classes don't match `python_classes = Test*`). When a
  test passes suspiciously easily, verify it is exercising the real path.
- **No real sleeps.** Use an injectable clock or call the function under test directly
  (e.g. `check_and_send_reminders(now)`).
- **Mock only at boundaries** — the Telegram API, SMTP, the filesystem. Do not mock the
  engine, `GameService`, or the database when a real one is available.
- **Cover new database code.** `DatabaseService` is large; any new method needs a direct
  test, including one asserting that detached-object mutation patterns do not creep back in.
