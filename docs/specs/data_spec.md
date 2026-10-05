# Data Model Specification

> The engine's types and the persistence layout. Two layers, kept
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
`adjudication.md` §6.

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

The columns that matter for game state (all nullable):

| Column | Type | Written by | Meaning |
|---|---|---|---|
| `state_json` | JSON | `GameRepo.create` / `.save_state` | The serialized `GameState` — the authoritative source of truth for a game's board. |
| `pending_orders` | JSON | `GameRepo.modify_pending_orders` (locked read-modify-write) | `{power: [order_str, ...]}`, submitted but not yet adjudicated; cleared after `process_turn`. |
| `last_resolution` | JSON | `GameRepo.save_state` / `.set_histories` (saved-game import) | The most recent `resolution_to_dict()` output — what `/last_resolution` answers and what `/generate_map/resolution` draws arrows from; not otherwise authoritative (superseded on the next `process_turn`). |
| `order_history` | JSON | `GameRepo.save_state` | `{turn_number_str: {power: [order_str, ...]}}`, appended (never overwritten) each `process_turn`, using the *truthful* A/F-lettered order text. Powers `/orders/history`, which also returns `phases` (`{turn_number_str: phase_code}`, from each turn's `map_snapshots` row) so clients label a turn `S1901M`, not by its counter. |
| `resolution_history` | JSON | `GameRepo.save_state` | `{turn_number_str: resolution_dict}` — what each turn's orders did; powers `/resolutions`, `/history/{turn}` and each turn's orders map. |
| `draw_votes` | JSON | `GameRepo.modify_draw_votes` | `{power: true}` for this phase's yes votes; cleared when a turn is processed. |
| `pending_deadline_proposal` | JSON | `GameRepo` (locked read-modify-write) | The one open majority vote on a deadline change, with its yes/no votes and optional expiry. |
| `phase_length_seconds` | Integer | `create_game`, `POST /deadline` | A recurring phase length a caller may arm a deadline from; never armed on its own. |
| `deadline_schedule` | JSON | `create_game`, `POST /deadline/schedule` | The weekly schedule each phase's deadline is armed from: `{"timezone": iana, "slots": [{"day": "MON", "time": "16:00"}]}` (`server.deadline_schedule`). `GET /deadline` returns it with a readable `description`. Null = none. |
| `phase_started_at` | DateTime | `GameRepo` (every phase change) | When the current phase began; order submissions composed earlier are refused (409). |
| `dummy_powers` | JSON | `GameRepo.create` / `.set_dummy_powers` | Sorted list of powers played by civil disorder. Never joinable, never waited on (`orders_status`), excluded from draw quorum and deadline-proposal majorities (`GameService.active_powers`). Null/`[]` = none; at most six. In a game whose `map_name` is `"demo"` (the bot's solo demo), `process_turn` gives each dummy with no orders `engine.simple_ai` orders, seeded by game id and phase, and records them in `order_history` like anyone's. |
| `auto_process` | Boolean | `GameRepo.create` / `.set_auto_process` | Process the turn as soon as `orders_status` has nothing missing and no wait flag is up. Null/false = manual or deadline only. |
| `wait_flags` | JSON | `GameRepo.modify_wait_flags` | `{power: true}` for players who asked the table to wait. Cleared by `finish_processed_turn` on every processed turn; never stops a deadline or `/processturn`. |
| `join_password_hash` | String(100) | `GameRepo.create` / `.set_join_password_hash` | bcrypt hash of a private game's join password; null = open. Never serialized: views and `GET /games` carry only `private`, and the saved-game export leaves it out (an imported game comes back open). |
| `anonymous` | Boolean, not null, default false | `GameRepo.create` | Chosen at creation (`POST /games/create` `anonymous`, the bot's `/newgame anonymous\|public`, the web's create form) and never changed. **True:** players are known only by their power — every announcement and relayed message names the power alone (`api.shared.power_label`), and no API read says who holds a seat (`api.shared.player_rows`: `user_id`, `nickname` are null; `seated` says whether the seat is held). **False (public):** the player's nickname, when they have set one, rides along with the power, `FRANCE (Anna)`. Carried by the saved-game export. |
| `random_powers` | Boolean, not null, default false | `GameRepo.create` | Chosen at creation (`POST /games/create` `random_powers`, the bot's `/newgame … random`, the web's create form) and never changed. **True:** a joining player does not choose a power — `POST /games/{id}/join` must leave `power` out, and the server seats them in an open power (no seat held, not a civil-disorder dummy; a vacated seat counts as open) drawn with `secrets.SystemRandom`, trying the others in turn if it loses a race for one. `POST /games/{id}/replace`, which names a power, is refused (400). **False:** the joiner names the power. Either way the join response carries the `power` taken. Carried by the saved-game export. |
| `channel_id` | String(255), unique when not null (partial index `uq_games_channel_id`) | `DatabaseService.link_game_to_channel` / `.unlink_game_from_channel` | The Telegram group (or channel) chat id the game belongs to; `channel_settings` holds its posting settings and `channel_name`. **A group has at most one game:** linking another game to it unlinks the previous one in the same transaction (`link_game_to_channel` returns that game's id), and only a player of the previous game (`displacer_user_id`) or an admin may (`ChannelTakenError` otherwise; see architecture.md §Notifications). Set only by the bot, with the chat a command was typed in, or by an admin (`POST /games/{id}/channel/link`), or at creation by `POST /games/create` `channel_id` (bot only, `/newgame`), which deletes the new game again if the link is refused. `DatabaseService.get_game_by_channel` is the reverse lookup behind `GET /channels/{chat_id}/game`. Null = no group. |
| `created_by_user_id` | Integer FK `users.id`, `ON DELETE SET NULL` | `GameRepo.create` | Who created the game (Bearer user, or the bot's `telegram_id`). Null for waiting-list games. Only the creator (or `X-Admin-Token`) may change `dummy_powers` or the join password, or end a turn early. |

Plus denormalized convenience columns kept in sync for code that doesn't want to parse
`state_json` (deadline scheduler, game listings, channel posts): `map_name`,
`current_turn`, `current_year`, `current_season`, `current_phase`, `phase_code`,
`status`, `deadline`, `channel_settings`, `observer_mode`, `created_at`,
`updated_at`.

There are no relational unit, order or supply-centre tables: `state_json` holds the
board, and `map_snapshots` one row per turn: the board the turn began on (turn 0, the
opening board, is written by `GameRepo.create`; every later one after the turn before it is
processed). `/history/{turn}` and `/map/history/{turn}` read it; for a game created
before the turn-0 row existed they fall back to the opening board, which every game starts
from.

### `players` table (`PlayerModel`)

Player-to-power assignment is not an engine concern.
Key columns: `game_id` (FK), `power_name`, `user_id` (FK to `users`), `is_active`,
`is_eliminated`. `GameRepo.players(game_id)` reads this into `{power: {user_id,
is_active}}` for the API view (§4); in an anonymous game the view nulls `user_id` and adds
`seated`.

### Other tables

`users` (`email` + `password_hash` for web login, `telegram_id`, and an optional
`nickname` — unique ignoring case, chosen by the player; **no real names are stored**, nothing
is copied from a Telegram profile), `link_codes`, `password_reset_tokens`, `messages`, `map_snapshots` (the board at
the start of each turn, with its `state_json`), `waiting_list`, the tournament and
spectator tables — see `database.py` for the full model list. `DatabaseService`
(`database_service.py`) is the DAL for all of these; only game *state* lives in `GameRepo` +
`GameService`.

| Table / column | Purpose |
|---|---|
| `bot_outbox` | Everything waiting for the bot to send: `kind` (`dm`, `channel_text`, `channel_map`, `channel_create_thread`), `telegram_id` (a user or a group chat), `message`, `payload` (buttons, `parse_mode`, a map's `path`, …), `created_at`, `delivered_at` (NULL = pending), `attempts`, `last_error`. The bot pulls and acks; delivered rows are purged after 7 days. |
| `feedback` | Player reports (`POST /feedback`, the bot's `/feedback`): `user_id` (FK `users`, `SET NULL`), `source` (`telegram`/`web`), `game_id` (the public id as given; not a FK, so a report outlives its game), `phase_code` (that game's phase when reported), `text` (≤ 2000 chars), `created_at`. At most 10 per player per hour. `GET /admin/feedback` lists them. |
| `idempotency_keys` | First response stored per bot-supplied `Idempotency-Key`: `key`, `endpoint`, `status_code`, `response_json`, `created_at`. Purged after 7 days. |
| `messages.timestamp` | The time the message was *composed* when the client sends `client_timestamp`; otherwise now. |
| `messages.anonymous` | A rumour: a broadcast (`recipient_power` NULL) sent with `anonymous: true`. `sender_user_id` is still stored, for the record and the admin export, but no player-facing read or notification names the sender. Default false. |

## 4. The HTTP API view shape

`GameService.view(game_id)` (`src/server/game_service.py`) is the **single** place that
builds the JSON a client sees for `GET /games/{id}/state` (and equivalent DAIDE/bot
paths) — built directly from `GameState`:

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
                                        // anonymous game: {"user_id": null, "is_active": true, "seated": true}
  "dummy_powers": ["TURKEY"],           // played by civil disorder; [] if none
  "auto_process": false,                // turn runs by itself once all orders are in
  "wait_flags": ["ENGLAND"],            // powers that asked the table to wait
  "private": false,                     // joining needs a password (never the hash)
  "anonymous": false,                   // players known only by their power (games.anonymous)
  "random_powers": false                // joiners are dealt an open power (games.random_powers)
}
```

**Who a player is known as.** `GET /games/{id}/players` returns one row per seat:
`power`, `seated`, `is_active`, `user_id`, `nickname` — the last two null in an
anonymous game. It never carries a Telegram id: the route needs no login, and that id
names a real Telegram account. `GET /games` lists each game's `anonymous` and `random_powers` flags and its seats as
`{power, seated, user_id}` (`user_id` null when anonymous). `GET /games/{id}/messages`
gives each message's `sender_power` (the seat its sender holds now; null if they left) and,
in a public game only, `sender_name`; an anonymous game nulls `sender_user_id`. Each message
also carries `anonymous`: for a rumour, `sender_user_id`, `sender_power` and `sender_name`
are null for every reader except the sender themself, who sees their own. Without
credentials the list holds broadcasts only; with them, also the caller's own private
messages; credentials that don't check out are a 401. `POST /games/{id}/message` and
`/broadcast` refuse blank text and text over 3500 UTF-16 units with a 400
(`docs/specs/architecture.md` §Notifications, "Message text"). A client
finds its own seat in an anonymous game from `GET /users/me/games` (or
`/users/{telegram_id}/games`).

**The view carries no pending orders.** It is public (`GET /games/{id}/state` needs no
login, and game ids are sequential), and orders are secret until the turn is processed.
A player reads their own from `GET /games/{id}/orders/{power}` (or `GET
/games/{id}/orders`), which answer only the user holding that power; server code reads
them from `GameService.pending_orders_view` (every power, for trusted callers only).
Those lists are re-derived every call via `_humanize_orders`: stored pending-order
strings are reparsed and reformatted against the *current* board so the A/F unit letter
is always correct (a fleet at a non-split-coast province displays `F`, not the
coast-inferred guess `format_order` would otherwise produce — see `orders/parser.py`'s
`format_order` docstring). This is a display-only correction; adjudication always uses
the actual board unit, never the letter in the order string. Once a turn is processed its
orders are public: `/history/{turn}`, `/orders/history`, `/map/turn/{turn}/orders`.

Consumers of this exact shape: `frontend/src` (React SPA — `GameView.tsx` and friends),
the Telegram bot, and `src/server/daide/session.py`.

### Resolution-result shapes: `POST .../process_turn` and `GET .../last_resolution`

Who may call it: the game's creator (`games.created_by_user_id`) — as a Bearer user, or
as a Telegram player when the bot passes their `telegram_id` in the JSON body — plus the
bare bot secret and the admin token. Anyone else, seated or not, gets 403; a game nobody
created (a waiting-list game) can be ended early only by an admin. The game view carries
`created_by_user_id` so the web shows "Process turn" only to the creator, and
`GET /users/{telegram_id}/games` marks created games with `is_creator: true` for the bot.

`POST /games/{id}/process_turn` (`api/routes/games.py`) returns, additively (the
pre-existing `status: "ok"` key is unchanged so existing clients keep working):

```jsonc
{
  "status": "ok",
  "phase": "F1901M",           // GameState.phase_name of the *new* (post-adjudication) phase
  "game_status": "ACTIVE",     // GameState.status of the new phase -- "status" was already
                                // taken by the pre-existing "ok" key above
  "resolution": { "results": [ ... ] }  // the turn just adjudicated -- see below
}
```

`GET /games/{id}/last_resolution` (added so a client can re-fetch this after a page
reload, since the inline `process_turn` response above isn't persisted client-side)
returns the same `resolution` shape directly, 404 when the game doesn't exist,
`{"results": []}` when it exists but no turn has been processed yet:

```jsonc
{
  "results": [
    {
      "order": {"type": "MOVE", "power": "FRANCE", "unit": "PAR", "dest": "BUR", "via_convoy": false},
      "result": "BOUNCE",       // engine.types.ResultCode -- OK/BOUNCE/CUT/VOID/NO_CONVOY/DISLODGED/DISBAND/BUILD/WAIVE
      "dislodged": false,
      "retreat_options": [],
      "power": "FRANCE",        // convenience: same as order.power, flattened
      "order_str": "A PAR - BUR"  // convenience: format_order(order), best-effort --
                                   // without the pre-adjudication board's kind_by_province
                                   // (not retained), a fleet at a non-split-coast
                                   // province may print as "A"
    },
    ...
  ]
}
```

Both `order` and the bare `result`/`dislodged`/`retreat_options` fields are exactly
`engine.serialization.resolution_to_dict()`'s canonical per-`OrderResult` shape (§2),
passed through unchanged; `power`/`order_str` are the only fields added on top
(`GameService.last_resolution_view`). This is what a client uses to answer "what
happened to my orders?" without re-deriving adjudication itself.

### Order/resolution overlay maps: `GET .../map/orders`, `GET .../map/resolution`

`GET /games/{id}/map` streams the current board as PNG bytes. Two more GET routes
mirror it with overlay arrows drawn on top, so a browser can render them directly
(the older `POST .../generate_map/orders` and `.../generate_map/resolution` return
`{"map_path": "/tmp/diplomacy_maps/..."}` — a server-filesystem path, unreachable
from a browser; both routes are kept for existing server-side callers):

- `GET /games/{id}/map/orders` — the board plus arrows for the **caller's own**
  pending orders (plain board if none submitted yet). Players in the game only (Bearer,
  or `telegram_id` + `bot_secret` query parameters); anyone else gets 403, since pending
  orders are secret. The web client fetches it with its token and shows it from a blob
  URL, as an `<img src>` sends no credentials. `POST .../generate_map/orders` draws every
  power's pending orders and so takes the bot secret only.
- `GET /games/{id}/map/resolution` — the board plus arrows for the *last processed
  turn's* orders, coloured by `ResultCode`, plus standoff markers (plain board if no
  turn has been processed yet).

Both return `image/png` bytes with the same 404-on-missing-game behavior as `GET
.../map`, and lean on `Map.render_board_png*`'s own disk-backed byte cache rather
than a second caching layer (see `get_map_preview_png`'s docstring in `maps.py`).

### The sandbox: `POST /sandbox/*`

The web sandbox (`routes/sandbox.py`) lets a player order every power on a scratch board and
step it through movement, retreat and adjustment phases. **It stores nothing**: the client
holds the board as a serialized `GameState` (`state_to_dict`, §2) and sends it with every
request. Because it is client-supplied, `GameService.sandbox_state` validates it before use
(`400 Invalid sandbox board: ...`): known powers and provinces only, each unit where its kind
can stand (a fleet on a named coast of a split-coast province), one unit per province,
ownership of supply centres only, dislodged units only in a retreat phase. All four routes
need a signed-in caller (`require_bot_or_user`).

| Route | Body | Returns |
|---|---|---|
| `POST /sandbox/start` | `{game_id?}` | `{source_game_id, state, view}`: that game's current board (404 if unknown), or the opening position |
| `POST /sandbox/legal_orders` | `{state, power}` | `legal_orders_for_power`, the shape of `GET /games/{id}/legal_orders/{power}` |
| `POST /sandbox/adjudicate` | `{state, orders: {power: [order_str]}}` | `{order_results: {power: [{order, ok, reason}]}, resolution, state, view}`; 409 once the board's game is over |
| `POST /sandbox/map` | `{state, orders, overlay}` (`board`, `orders` or `resolution`) | `image/png`: the board, the orders as pending arrows, or the orders adjudicated on this board and coloured by result |

`view` is `GameService.sandbox_view`: the board fields of §4 (`phase`, `phase_type`,
`units_by_power`, `ownership`, `dislodged`, `contested`, `status`, `winners`, ...) plus
`powers_to_order` (`powers_with_orders_to_give`). Orders are validated exactly as
`submit_orders` validates them; a refused order is reported and left out, so its unit holds.
`resolution` results carry `power` and a truthful `order_str`, as `last_resolution` does.
At most 40 orders per power are accepted.

## 5. Validation

Order legality (not grammar — grammar is `orders/parser.py`'s job) is centralized in
`orders/validation.py`'s `validate(order, state, map) -> ValidationResult`, the **one**
path used by `GameService.submit_orders` (pre-check before an order is accepted into
`pending_orders`) and by `adjudicator/adjustments.py` (build legality). There is no
second, divergent validation path anywhere in the codebase.

The first check is the **phase**: an order whose kind has no meaning in
`state.phase_type` is refused before any unit or topology check, with a reason that names
the phase (`a move order is not accepted during the retreat phase (S1901R); only retreat and
disband (for dislodged units) orders are`). Movement takes Hold / Move / SupportHold /
SupportMove / Convoy; Retreat takes Retreat / Disband; Adjustment takes Build / Disband /
Waive. The adjudicators already ignore orders from the wrong phase, so without this gate a
build typed during a movement phase, or a move typed during a retreat or build phase, was
accepted with `ok=True`, stored, shown as pending, and then dropped without a word — which
for an adjustment phase meant a player's build was silently waived. Interactive menus never
offered such orders (`legal_orders.py` is phase-aware); the gate covers free-text input
from every client. One case gets a hint instead of the list: a move by a unit that is
dislodged in this retreat phase is a retreat written as a move, so it is refused with the
retreat spelling (`a move order is not accepted during the retreat phase (S1901R); to
retreat, write A BUR R RUH`). It is refused rather than read as a retreat so that each
order string has one meaning in every phase and what is stored is what the player wrote.

Moves and convoys. A non-adjacent **army** move between two coastal provinces is a convoyed
move, written with or without `VIA` (the rulebook writes `A Lon-Bel`); it is accepted like
`A LON - BEL VIA`, and adjudication treats it as convoyed (`adjudication.md` §6). Any other
non-adjacent move is refused (`BEL is not adjacent to MUN`), as is a move to the unit's own
province (`LON cannot move to its own province`). A fleet moving to a split-coast province
(BUL, SPA, STP) without naming a coast is accepted when exactly one coast is reachable from
where it stands (`F BLA - BUL` arrives on BUL/EC; the adjudicator infers it), refused as
ambiguous when both are (`fleet move into split-coast BUL must name a coast (BUL/EC or
BUL/SC)`), and refused as not adjacent when neither is (`BUL is not adjacent to ANK`). A
`Convoy` is refused unless an army
stands at its origin (`no army at ALB to convoy`, `the unit at ALB is a fleet; only an army
can be convoyed`). `submit_orders` stores each accepted order as `format_order` writes it with
the board's real unit letters, and refuses (as one `ok=False` entry, `parse error: ...`) any
order whose stored form would not parse back, so a single bad order can never fail the
batch.

Retreats. A `Retreat` is legal iff its destination is in the dislodged unit's precomputed
`retreats` (`adjudication.md` §8); a fleet naming no coast gets the sole legal coast, as a
move does, and must name one when two are legal. A refusal says why, through
`retreats.retreat_refusal` (the same rules as `compute_retreat_options`): `BUR is not a legal
retreat for A PAR:` followed by `the unit that dislodged it attacked from there`, `another
unit stands there`, `a standoff left it empty this turn, and no unit may retreat there`, or
`it is not adjacent to PAR`.

In an adjustment phase an order must also be on the right side of the power's delta
(centres minus units), checked after the order's own checks: a `Build` or `Waive` needs a
positive delta and a `Disband` a negative one (`FRANCE has no unit to disband (3 supply
centres, 1 unit); it may build 2 units`). The adjudicator voids anything else. The *count*
is a whole-submission rule and lives in `GameService._check_orders`: a submission may hold
at most `adjustments_owed` builds/waives (the delta, capped at the vacant owned home
centres — the `adjustment.slots` of `legal_orders`) or disbands; the later ones beyond it
are refused (`ENGLAND has 1 build; 2 builds/waives submitted`). When orders are merged
(`merge=true`, every bot path) the stored ones are trimmed to make room for the new ones —
stored waives first, then the oldest — so the stored list never exceeds the count: a
`WAIVE` sent after `BUILD F KIE` replaces it, as a build sent after a waive does.

`GameService.orders_status` (and so `GET /games/{id}/orders_status` and
`process_turn?require_all=true`) counts only the powers that have a decision to make this
phase, via `server.legal_orders.powers_with_orders_to_give`: every power with a unit in a
movement phase, only powers with a dislodged unit in a retreat phase, and in an adjustment
phase only powers that must disband or that are owed a build and have a vacant owned home
centre to put it on. A power `legal_orders_for_power` would offer nothing but `WAIVE` is
not waited on.

Those powers (civil-disorder dummies left out) are `active_powers`, and each of them is in
exactly one of `submitted` — it has at least one stored order this phase — and `missing`.
An empty stored list (what a submission whose every order was refused leaves) is
`missing`, not submitted. `incomplete` is the part of `submitted` that has not yet ordered
everything that must act. `nothing_to_do` lists every other non-dummy power still in the
game (a unit or a centre): no order is due from it, so it is neither submitted nor waited
on. The bot's `/status` and the web turn-status card show the three groups separately.

## 6. Out of scope here

Full DB migration history: `alembic/versions/`. Route-by-route request/response models: the
route modules themselves, or the generated OpenAPI schema at `/docs`. The adjudication
algorithm that produces `Resolution`/next-`GameState`: `adjudication.md`.
