# Data Model Specification

> Reflects the post-rewrite (M0–M7) engine and persistence layout. Two layers, kept
> deliberately separate — see [`architecture.md`](architecture.md):
>
> 1. **Engine value types** (`src/engine/types.py`) — pure, immutable, no persistence
>    concerns. This is what adjudication actually operates on.
> 2. **Persistence** (`src/persistence/`) — a game row stores the *serialized* engine
>    `GameState` wholesale (`state_json`), not a normalized relational breakdown. A few
>    peripheral tables (players, users, messages, channels, tournaments, ...) remain
>    relational because they aren't engine-coupled.
>
> For the algorithm that produces these values, see [`adjudication.md`](adjudication.md).

## 1. Engine value types (`src/engine/types.py`)

All frozen, hashable dataclasses; no dict-of-dicts, no mutation. Full definitions live in
the source — this is the field-level reference.

### `Location`

```python
Location(province: str, coast: Optional[str] = None)
```

`province` is always uppercased on construction. `coast` is one of `NC`/`SC`/`EC`/`WC`
(also uppercased) or `None`. Armies always have `coast=None`; fleets in split-coast
provinces (`BUL`, `SPA`, `STP`) always name one. `str(loc)` renders the canonical text
form: `"PAR"` or `"SPA/SC"` — this is also the JSON encoding (§4).

### `Unit`

```python
Unit(kind: UnitKind, power: str, location: Location)
```

`kind` is `UnitKind.ARMY` (`"A"`) or `UnitKind.FLEET` (`"F"`). Raises if an army carries
a coast. `.province` is a convenience property (`location.province`).

### `DislodgedUnit`

```python
DislodgedUnit(unit: Unit, attacker_origin: Optional[str] = None,
              retreats: tuple[Location, ...] = ())
```

Carries everything the retreat phase needs precomputed: the province the dislodging
attack came from (`None` if that attack was convoyed — no shared-border block applies),
and the full legal retreat set already computed against post-resolution occupancy (see
`adjudication.md` §8). Empty `retreats` means the unit is trapped and must disband.

### Orders

All orders share a `power: str` field and an `order_type: OrderType` property. One class
per order kind (movement-phase: `Hold`, `Move`, `SupportHold`, `SupportMove`, `Convoy`;
retreat-phase: `Retreat`, `Disband`; adjustment-phase: `Build`, `Disband` (shared),
`Waive`):

| Class | Fields | Example order text |
|---|---|---|
| `Hold` | `unit` | `A PAR H` |
| `Move` | `unit`, `dest`, `via_convoy` | `A PAR - BUR`, `A LON - BEL VIA` |
| `SupportHold` | `unit`, `target` | `F BRE S A PAR` |
| `SupportMove` | `unit`, `origin`, `dest` | `F BRE S A PIC - BEL` |
| `Convoy` | `unit`, `origin`, `dest` | `F NTH C A LON - BEL` |
| `Retreat` | `unit`, `dest` | `A PAR R BUR` |
| `Disband` | `unit` | `D A PAR` |
| `Build` | `location`, `kind` | `BUILD A PAR`, `BUILD F STP/SC` |
| `Waive` | — | `WAIVE` |

All `Location`-typed fields, not strings — there is no separate "target province name"
field to keep in sync with a `Location`. Grammar/parsing lives in `orders/parser.py`;
legality (not just grammar) in `orders/validation.py`; adjudication semantics for each
type in `adjudication.md`.

### `OrderResult` / `Resolution`

```python
OrderResult(order: Order, result: ResultCode, dislodged: bool = False,
            retreat_options: tuple[Location, ...] = ())
Resolution(results: tuple[OrderResult, ...] = ())
```

`ResultCode`: `OK`, `BOUNCE`, `CUT`, `VOID`, `NO_CONVOY`, `DISLODGED`, `DISBAND`,
`BUILD`, `WAIVE` — see `types.py`'s enum docstring for the precise meaning of each; the
convoy-specific distinction between `VOID`/`DISLODGED`/`NO_CONVOY`/`OK` is covered in
`adjudication.md` §6. `Resolution.for_unit(loc)` looks up the result for whichever order
acted on the unit at `loc`.

### `GameState`

```python
GameState(
    year: int, season: Season, phase_type: PhaseType,
    units: frozenset[Unit] = frozenset(),
    ownership: dict[str, str] = {},       # supply-center province -> owning power
    dislodged: tuple[DislodgedUnit, ...] = (),
    contested: frozenset[str] = frozenset(),  # standoff provinces (retreat phase only)
    status: GameStatus = GameStatus.ACTIVE,
)
```

An **immutable snapshot** of the whole game between phases — not a mutable "current
state" object. `phase_name` derives the canonical code (`"S1901M"`, `"F1901R"`,
`"W1901A"`) from `season`/`year`/`phase_type`. Helper queries: `units_of(power)`,
`unit_at(province)`, `centers_of(power)`, `dislodged_at(province)`.

`Game` (`src/engine/game.py`) wraps a `GameState` with its `map: MapData` and a `history`
tuple of past snapshots; `Game.adjudicate(orders)` is the only way to advance it, and it
returns a **new** `Game` plus the phase's `Resolution` — nothing mutates.

## 2. Serialization (`src/engine/serialization.py`)

The **one** place `GameState`/`Order`/`Resolution` cross the pure-engine boundary into
JSON. Round-trips exactly (`state_from_dict(state_to_dict(s)) == s`, Hypothesis-checked).

- `Location` -> its canonical string (`location_to_str`/`location_from_str`): `"PAR"` or
  `"SPA/SC"`.
- Every enum -> its `.value` string.
- `frozenset`/`tuple` fields (`units`, `contested`) -> JSON arrays (order doesn't matter
  for round-trip equality — they decode back into sets).
- `state_to_dict(state)` -> `{year, season, phase_type, units: [unit_dict...],
  ownership: {province: power}, dislodged: [dislodged_dict...], contested: [province...],
  status}`.
- `order_to_dict(order)` -> `{type, power, ...order-specific Location strings...}` (see
  the field table above — each order type serializes exactly its own fields).
- `resolution_to_dict(resolution)` -> `{results: [{order, result, dislodged,
  retreat_options}, ...]}`.

`to_json()`/`state_from_json()`/`order_from_json()`/`resolution_from_json()` are thin
`json.dumps`/`json.loads` wrappers around the dict functions.

## 3. Persistence (`src/persistence/`)

### `games` table (`GameModel`, `src/persistence/database.py`)

The columns that matter for the new engine (M6 additions, all nullable so they layer
onto the pre-existing row shape without a destructive migration for *these* columns —
though the `state_json`/`pending_orders` migration `a1b2c3d4e5f7` itself **does** wipe
stored game rows; see `fix_plan.md` M6):

| Column | Type | Written by | Meaning |
|---|---|---|---|
| `state_json` | JSON | `GameRepo.create` / `.save_state` | The serialized `GameState` — the authoritative source of truth for a game's board. |
| `pending_orders` | JSON | `GameRepo.set_pending_orders` | `{power: [order_str, ...]}`, submitted but not yet adjudicated; cleared after `process_turn`. |
| `last_resolution` | JSON | `GameRepo.save_state` | The most recent `resolution_to_dict()` output — kept only so `/generate_map/resolution` can draw arrows for the turn just processed; not otherwise authoritative (superseded on the next `process_turn`). |
| `order_history` | JSON | `GameRepo.save_state` | `{turn_number_str: {power: [order_str, ...]}}`, appended (never overwritten) each `process_turn`, using the *truthful* A/F-lettered order text. Powers `/orders/history`. |

Plus denormalized convenience columns kept in sync for code that doesn't want to parse
`state_json` (deadline scheduler, game listings, channel posts): `map_name`,
`current_turn`, `current_year`, `current_season`, `current_phase`, `phase_code`,
`status`, `deadline`, `channel_id`, `channel_settings`, `observer_mode`, `created_at`,
`updated_at`.

**Legacy relational columns/tables** — `units`, `orders`, `supply_centers` (as separate
tables, still present in the schema) and the old per-game relational fields — predate the
engine rewrite and are **no longer written or read** for game state; `state_json` fully
supersedes them. They exist only because dropping them would be a separate, disruptive
migration outside the rewrite's scope (`fix_plan.md` M6 explicitly deleted the *code*
paths that wrote them — `unit_to_dict`/`order_to_dict`/`dict_to_order` — but left the
tables themselves alone). Do not add new code that reads/writes them.

### `players` table (`PlayerModel`)

Unaffected by the engine rewrite — player-to-power assignment is not an engine concern.
Key columns: `game_id` (FK), `power_name`, `user_id` (FK to `users`), `is_active`,
`is_eliminated`. `GameRepo.players(game_id)` reads this into `{power: {user_id,
is_active}}` for the API view (§4).

### Other tables

`users`, `link_codes`, `password_reset_tokens`, `messages`, `turn_history`,
`map_snapshots`, tournament tables, channel-analytics tables — all unchanged by the
engine rewrite; see `database.py` for the full model list. `DatabaseService`
(`database_service.py`) remains the DAL for all of these; only game *state* itself was
carved out into `GameRepo` + `GameService`.

## 4. The HTTP API view shape

`GameService.view(game_id)` (`src/server/game_service.py`) is the **single** place that
builds the JSON a client sees for `GET /games/{id}/state` (and equivalent DAIDE/bot
paths) — built directly from `GameState`, not from any legacy relational shape:

```jsonc
{
  "game_id": "1",
  "map_name": "standard",
  "phase": "S1901M",                    // GameState.phase_name
  "year": 1901,
  "season": "SPRING",
  "phase_type": "MOVEMENT",             // MOVEMENT | RETREAT | ADJUSTMENT
  "status": "ACTIVE",                   // ACTIVE | COMPLETED
  "units": [ {"kind": "F", "power": "FRANCE", "location": "BRE"}, ... ],
  "units_by_power": { "FRANCE": [ ... ], ... },
  "ownership": { "PAR": "FRANCE", ... },
  "supply_centers": { "PAR": "FRANCE", ... },  // == ownership; kept as an alias for callers
  "dislodged": [
    {"unit": {...}, "attacker_origin": "BUR", "retreats": ["PIC", "GAS"]}
  ],
  "contested": ["BUR"],
  "players": { "FRANCE": {"user_id": 42, "is_active": true}, ... },
  "orders": { "FRANCE": ["F BRE H", "A PAR - BUR"], ... }  // pending, truthfully re-lettered
}
```

`orders` is re-derived every call via `_humanize_orders`: stored pending-order strings
are reparsed and reformatted against the *current* board so the A/F unit letter is always
correct (a fleet at a non-split-coast province displays `F`, not the coast-inferred
guess `format_order` would otherwise produce — see `orders/parser.py`'s `format_order`
docstring). This is a display-only correction; adjudication always uses the actual board
unit, never the letter in the order string.

Consumers of this exact shape: `frontend/src` (React SPA — `GameView.tsx` and friends),
the Telegram bot's `api_client.py`, and `src/server/daide/session.py`. There is no legacy
`powers`-keyed view left to support.

## 5. Validation

Order legality (not grammar — grammar is `orders/parser.py`'s job) is centralized in
`orders/validation.py`'s `validate(order, state, map) -> ValidationResult`, the **one**
path used by `GameService.submit_orders` (pre-check before an order is accepted into
`pending_orders`) and by `adjudicator/adjustments.py` (build legality). There is no
second, divergent validation path anywhere in the codebase.

## 6. Out of scope here

Full DB migration history: `alembic/versions/`. Route-by-route request/response models: the
route modules themselves, or the generated OpenAPI schema at `/docs`. The adjudication
algorithm that produces `Resolution`/next-`GameState`: `adjudication.md`.
