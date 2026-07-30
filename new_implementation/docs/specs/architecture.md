# Architecture

> Reflects the post-rewrite layout (`fix_plan.md` M0–M7). For the adjudication algorithm
> itself see [`adjudication.md`](adjudication.md); for the wire/DB shapes see
> [`data_spec.md`](data_spec.md).

## Processes

```
Telegram Bot ──┐
React SPA ─────┼──► FastAPI (port 8000) ──► GameService ──► GameRepo ──► Postgres
DAIDE clients ─┘         │                        │
                         │                        └─ (state_json / pending_orders /
                         │                            last_resolution / order_history)
                         └── engine.Game (pure logic, no I/O) ──► src/rendering (PNG maps)
```

Five things talk to one Postgres database: the FastAPI HTTP server, the Telegram bot (a
thin HTTP client, never touches the engine or DB directly), the React SPA, DAIDE TCP
clients (a real `asyncio` listener, `src/server/daide/`, started alongside the API
process — see "DAIDE protocol support" below; this is no longer aspirational, per
`fix_plan.md` Track D D1-D5), and the deadline scheduler background task inside the API
process.

## Package boundaries (the M6 split)

```
src/engine/          # PURE rules core — stdlib only, no I/O, no DB, no rendering
  types.py            # frozen dataclasses: Location, Unit, Order variants, GameState,
                       #   Resolution, DislodgedUnit; enums (UnitKind, Season, PhaseType,
                       #   OrderType, ResultCode, GameStatus)
  map_loader.py        # .map file -> MapData; coasts first-class; topology only
  orders/parser.py     # order grammar: coasts, VIA convoy, aliases; parse + format
  orders/validation.py # the one validation path: validate(order, state, map)
  adjudicator/movement.py    # Kruijswijk fixed-point resolver — see adjudication.md
  adjudicator/retreats.py    # retreat legality + phase
  adjudicator/adjustments.py # builds/disbands/civil disorder
  game.py               # phase machine over immutable GameState snapshots
  serialization.py      # canonical GameState/Order/Resolution <-> JSON (one place)
  simple_ai.py           # dumb heuristic order generator for demo/AI-filled games

src/persistence/       # SQLAlchemy models + DAL (moved out of engine/ in M6)
  database.py            # ORM models (GameModel, UserModel, PlayerModel, ...)
  database_service.py     # DatabaseService — CRUD for players/users/messages/channels/
                          #   tournaments/etc.; game *state* itself is delegated to...
  game_repo.py             # ...GameRepo: state_json/pending_orders/last_resolution/
                            #   order_history persistence for the new engine

src/rendering/          # SVG -> PNG map rendering (moved out of engine/map.py in M6)
  map.py                  # renderer: board state, order arrows, resolution arrows
  order_overlay.py         # adapts engine Order/Resolution into the renderer's arrow format
  visualization_config.py   # colors/sizes/layout config

src/server/             # FastAPI app, CLI Server, DAIDE, Telegram bot
  game_service.py          # THE single entry point from server code into the engine —
                            # wraps engine.Game + serialization + parser/validation over
                            # GameRepo. Routes/CLI/DAIDE never touch engine internals directly.
  api/routes/               # games, orders, users, auth, messages, maps, channels, admin,
                             # dashboard, health, tournaments
  telegram_bot/              # thin HTTP client over the API — see below
  daide/                      # the DAIDE TCP protocol (Track D D1-D5) — see below
  server.py                    # text-command CLI surface (CREATE_GAME, ADD_PLAYER, ...),
                                # used by tests and DAIDE; independent of the HTTP API
```

Key discipline established in M6: **`src/engine/` imports nothing but stdlib.** Nothing
in it knows about SQLAlchemy, FastAPI, Pillow, or JSON serialization frameworks — a
Hypothesis-checked property enforces this isn't just aspirational. Everything else
(persistence, rendering, the HTTP/bot/DAIDE surfaces) is an *adapter* around
`GameService`, which is the only thing that constructs `engine.game.Game` instances,
calls `adjudicate()`, or reaches into `orders/parser.py` and `orders/validation.py`.

## Engine design decisions (see `adjudication.md` for the algorithm)

- **Immutability.** Every engine type is a frozen, hashable dataclass. Adjudication is a
  pure function `(map, state, orders) -> (Resolution, new_state)`. `Game` wraps the
  current state plus a tuple of past snapshots (`history`); nothing mutates in place.
- **`Location = (province, coast|None)` everywhere.** A fleet in Spain is *at*
  `Location("SPA", "SC")`. Armies never carry a coast. There are no hardcoded
  adjacency/coast tables anywhere in the engine — `map_loader.py` is the only reader of
  `maps/standard.map`, which is the sole topology source.
- **Kruijswijk fixed-point resolver.** Per-order state UNRESOLVED/GUESSING/RESOLVED;
  recursive resolve with dependency-cycle detection; circular movement succeeds,
  convoy-entangled cycles apply the Szykman rule. Full writeup: `adjudication.md`.
- **Phases**: `S{y}M -> [S{y}R] -> F{y}M -> [F{y}R] -> [W{y}A] -> S{y+1}M -> ...`; a
  retreat phase is inserted only when the preceding movement dislodged a unit; an
  adjustment phase only when some power's unit count differs from its supply-center
  count; SC ownership updates once, after the Fall turn settles; victory at 18 centers.

## State persistence (the M6 clean break)

A game row (`games` table) stores the **whole `GameState`** as `state_json`
(`engine.serialization.state_to_dict`), not a normalized relational breakdown of units
and orders. Alongside it: `pending_orders` (`{power: [order_str]}`, submitted but not yet
adjudicated), `last_resolution` (the most recent `Resolution`, kept only so the
resolution-map renderer has something to draw arrows from), and `order_history`
(`{turn: {power: [order_str]}}`, appended on every `process_turn`, powering the
Telegram bot's order-history view). Player-to-power assignments live in the separate
`players` table (unaffected — never engine-coupled). See `data_spec.md` for the exact
column list and the legacy relational tables that predate this and are no longer written.

`GameService` (`src/server/game_service.py`) is the funnel:
`create_game` / `submit_orders` / `process_turn` / `view` / `last_resolution` /
`order_history`. `process_turn` loads `state_json`, parses `pending_orders`, calls
`Game.adjudicate()`, and persists the next `state_json` + `last_resolution` +
appended `order_history`, then clears `pending_orders`. `view` builds the
GameState-native API response shape consumed by the frontend, the bot, and DAIDE (see
`data_spec.md` §API view shape).

## Rendering

`src/rendering/map.py` renders PNGs from a `GameState`-derived unit/ownership view (not
from engine internals) plus, optionally, order or resolution arrows adapted by
`order_overlay.py` from `Order`/`Resolution` objects. Results are cached in-memory and on
disk at `/tmp/diplomacy_map_cache`. This package has no engine-internal coupling beyond
`map_loader` topology and the plain-dict view `GameService.view` already produces.

## DAIDE protocol support

`src/server/daide/` (Track D, D1-D5) is a real implementation of the DAIDE wire protocol
— interoperability with the external DAIDE bot ecosystem (DumbBot, Albert, and other
standalone Diplomacy AIs) — not the text-command stub that used to occupy this slot
(deleted in D4). It is started as an `asyncio.start_server` listener alongside the
deadline scheduler in `_api_module.py`'s `lifespan`, on the same port (8432) the old stub
used.

```
src/server/daide/
  tokens.py    # Token: the DAIDE byte-level vocabulary (powers, provinces+coasts, unit
               #   types, order types, commands, THX/ORD/HLO tokens) as a bidirectional
               #   registry; province coverage is asserted against
               #   engine.map_loader.load_standard_map(), never a second hardcoded list
  wire.py      # DCSP framing: IM/RM/DM/FM/EM message types over asyncio Stream{Reader,
               #   Writer}; async read_message/write_message
  clauses.py   # the encode/decode bridge between DAIDE token clauses and engine.types
               #   (Location, Unit, Order variants); decode reuses
               #   engine.orders.parser.parse_order rather than a second grammar
  session.py   # DaideSession: per-connection protocol state machine — the IM/RM
               #   handshake, then NME/IAM/HLO/MAP/MDF/SCO/NOW/SUB/THX/MIS/TME/HST/DRW/
               #   ADM/SND dispatch, all routed through GameService (never engine
               #   internals directly)
  server.py    # DaideServer: owns the listening socket, the game a connection's NME
               #   resolves against (created lazily on first successful NME, not at
               #   listener startup — see its docstring), the power/passcode registry,
               #   and the notify_game_processed broadcast (NOW/ORD/OUT/SLO) that fires
               #   whenever GameService.process_turn runs for a game with live sessions
```

**Known, permanent limitation: press content is relayed opaquely, not parsed.** DAIDE's
press negotiation grammar (`PRP`/`ALY`/`XDO`/... nested inside `SND`/`FRM`) is the
deepest part of the spec and the least essential for interoperability. This codebase
syntax-checks press messages only (balanced parens, a valid recipient-power list) and
forwards the token payload opaquely between clients — negotiation *content* is the
bots' concern, not the server's. Full press-grammar parsing is out of scope by design
(see `fix_plan.md` Track D's "Ground rules" and "Out of scope"), not a temporary gap to
be closed later.

End-to-end proof this composes correctly over a real socket (not just each layer's own
unit tests) lives in `tests/test_daide_server.py`'s
`TestEndToEndOneFullTurnOverOneSocket` — one continuous `asyncio` TCP connection drives
IM→RM→NME→HLO→MAP→MDF→SCO→NOW→SUB→THX against a real `GameService`/Postgres-backed game,
then `GameService.process_turn` + `DaideServer.notify_game_processed` (the same calls the
HTTP route/deadline scheduler make) push a real `NOW`/`ORD` notification back over that
same socket.

## Notifications: who gets told what, when

There are three delivery surfaces, and they are not interchangeable:

- **Telegram DM** — `notify_players(numeric_game_id, message, exclude_telegram_id=None)` in
  `api/shared.py`. POSTs to `DIPLOMACY_NOTIFY_URL` (default `http://localhost:8081/notify`),
  the small FastAPI server the *bot* runs (`telegram_bot/notifications.py`). Players with a
  non-numeric `telegram_id` (test fixtures like `"u1"`) are skipped, not errored.
- **Linked channel post** — `telegram_bot/channels.py`. Only fires for games that have a
  channel linked, gated by the per-game `should_auto_post_*` settings; a no-op otherwise.
- **Web client** — pull-only. The SPA polls `GET /games/{id}/state`; nothing is pushed. Any row
  below is therefore "visible on next poll" for the browser, and that is not a gap to close
  with websockets unless someone decides it is.

(`DaideServer.notify_game_processed` is a fourth, protocol-level path — `NOW`/`ORD`/`OUT`/`SLO`
to connected DAIDE bots. It is orthogonal to the table below and fires from both `process_turn`
call sites already.)

**The matrix.** This is the deliverable of G3, and it exists because the two `process_turn`
paths had silently drifted: the deadline path notified everyone and posted to the channel, while
the manual route notified nobody unless the game had just ended. The failure case was richly
instrumented and the success case was silent, because nobody owned the question.

| Event | Telegram DM | Channel post | Web client | Where |
|---|---|---|---|---|
| **Turn processed** (deadline) | all players | notification + rendered map | next poll | `notify_turn_processed(trigger="deadline")` |
| **Turn processed** (manual) | all players **except the caller** | notification + rendered map | next poll | `notify_turn_processed(trigger="manual")` |
| **Game ended** (18 centres, draw, last power) | all players except the caller | notification | next poll | `notify_turn_processed(game_ended=True)` |
| Deadline reminder (10 min out) | all players | — | — | `check_and_send_reminders` |
| Player joined | all players | — | next poll | `routes/games.py` join |
| Game full / started | all players | — | next poll | `routes/games.py` join |
| Player quit / replaced | all players | — | next poll | `routes/games.py` quit, admin replace |
| Broadcast message | all players | the broadcast text | next poll | `routes/messages.py` |
| Private message | recipient only | — | next poll | `routes/messages.py` |
| Draw vote cast (not final) | all players except the voter | — | next poll | `routes/games.py` `submit_draw_vote` |
| Draw quorum reached → game ends | all players except the voter | notification | next poll | `notify_turn_processed(game_ended=True)` |
| Power conceded | all players except the conceder | — | next poll | `routes/games.py` `concede_game` |
| Waiting list filled | all seven placed players, each told their own power | — | — | `api/routes/waiting_list.py` |

Those three rows were **`nothing`** until `v2.7.64` (G3a), and the reason is worth keeping:
`submit_draw_vote` finalizes the game inline the moment quorum is reached
(`GameService.submit_draw_vote` calls `Game.draw()` and `save_state` directly) and returns the
outcome to the *voter* only. Because the game is then `COMPLETED`, the deadline scheduler skips it
(`get_games_with_deadlines_and_active_status`), so **no later turn-processed fan-out covered for
it** — a game could end by agreement and six of seven players find out by refreshing. A
concession was likewise invisible until someone looked at the board.

A non-final draw vote is announced too, deliberately: a draw is the one outcome every power holds
a veto over, so discovering that one is being negotiated should not require running `/status`.

**Rules for adding a notification.**

1. **One fan-out per event, shared by every trigger.** `notify_turn_processed` exists so the
   deadline and manual paths cannot diverge again. If an event can be reached two ways, the
   second way calls the same function — do not bolt a `notify_players` call onto the new call
   site.
2. **Never notify the caller of their own action twice.** A player who presses "process turn"
   gets the resolution in their HTTP response; `exclude_telegram_id` skips their DM.
3. **Every send is best-effort.** Wrap and log. A Telegram outage must never fail a turn that
   is already committed to Postgres — the state change is the contract, the notification is not.
4. **Update this table in the same commit.** It is the only place the full picture exists.

`notify_turn_processed` is deliberately **synchronous** so the sync scheduler path
(`process_due_deadlines`) and the `async` HTTP route can share it with no bridge. It therefore
blocks its caller for up to `timeout=2` per player. That is pre-existing on both paths, not
introduced by the shared helper; moving it off the event loop is a legitimate future change, and
`_notify_daide_processed` in the same module shows the sync/async bridge pattern to follow if
anyone does.

## Frontend

React 18 + Vite + TypeScript SPA (`frontend/`), Tailwind + shadcn/ui. Consumes the
GameState-native `GET /games/{id}/state` view directly (`units_by_power`, `ownership`,
`dislodged`, `contested`, `phase_type`, `players`, ...) — there is no `powers`-shaped
legacy view to translate. Proxies API calls to `http://localhost:8000` in dev.

## Out of scope for this document

Route-by-route API reference, Telegram command list, and DB column-level schema live in
`data_spec.md` and the user-facing docs in `docs/`. Map-variant support beyond `standard`
and rendering-pipeline redesign are explicitly out of scope for the engine rewrite (see
`fix_plan.md` "Out of scope").
