# Audit findings — `new_implementation/` — 2026-05-13

Triaged bug list from an exhaustive code+test audit of the engine (`src/engine/`) and the HTTP/DAIDE/CLI server (`src/server/`), per the plan at `~/.claude/plans/next-task-read-through-compressed-pony.md`.

## Summary

- **Code audited:** 17,778 lines across `src/engine/` (~11K) and `src/server/` (~7K), plus 21 Alembic migrations.
- **Test baseline:** `pytest tests/` → **145 failed, 828 passed, 63 skipped, 4 errors** (no Postgres available; ~118 of the failures are DB-environment, but **27 are pure-engine adjudication failures**).
- **Ruff:** 111 errors in `src/` (CI claims strict mode — likely red).
- **DATC probes:** 14 probes against new `Game` class, **8 confirmed adjudication bugs**, 5 pass, 1 inconclusive.
- **Findings:** **P0 = 22, P1 = 25, P2 = 12** (total 59).

Out of scope per `specs/fix_plan.md`: tournaments, Discord, observer/spectator beyond existing, AI analysis. The audit only flagged `tournaments.py` where it impacts the rest of the system (it doesn't, beyond unauth-route count).

`specs/fix_plan.md` is dated 2025-03-02 ("All P0/P1/P2 completed, production-ready"). Today is 2026-05-13 — that document is stale; many "fixed" items are reproducibly broken (see e.g. F-001..F-008, F-024..F-033).

---

## Findings

> Each finding has a reproduction. Engine repros use `_process_movement_phase()` against a clean state — start `PYTHONPATH=src python` from `new_implementation/` with a venv that has `pip install -r requirements.txt`. API repros assume `PYTHONPATH=src uvicorn server._api_module:app --port 8000` with a Postgres URL set.

### ENGINE — P0

#### P0-001: SupportOrder validation accepts supports adjacent to origin (not destination)
- **Area:** engine / validation
- **Location:** `new_implementation/src/engine/data_models.py:314-333`
- **Observation:** `SupportOrder.validate()` accepts a move-support whenever the supporter is adjacent to *either* the destination *or* the supported unit's origin: `if not (adjacent_to_dest or adjacent_to_origin): return False`.
- **Why it's a bug:** Per Diplomacy rules ("the supporter must be able to move into the supported province"), the supporter must be adjacent to the **destination**, not the origin. With this code, `A MUN S A BUR - GAS` is accepted because MUN is adjacent to BUR — even though MUN is not adjacent to GAS.
- **Reproduction:** DATC probe `6.A.3-like Support adjacency` — `/tmp/datc_probes.py`. Engine assigns BUR strength = 2 (with MUN's invalid support counted); expected ≤ 1.
- **Blast radius:** Wrong adjudication outcomes anywhere a player adds a support adjacent only to their own unit. Affects every game.

#### P0-002: SupportOrder validation rejects all sea-to-sea supports
- **Area:** engine / validation
- **Location:** `new_implementation/src/engine/data_models.py:324-332`
- **Observation:** When `supporting_province.province_type == "sea"`, the code only accepts the support if the target or origin is "coastal". Sea-to-sea supports (e.g., `F MAO S F WES - GOL`) fall through to `return False`.
- **Why it's a bug:** Sea fleets can support moves to other sea provinces if adjacent. The rule is "supporter must be able to move there", not "target must be coastal".
- **Reproduction:** Set up F MAO and F WES; have F MAO support F WES → GOL (or any sea-to-sea); validate returns False.
- **Blast radius:** Fleet supports in naval theatres (Mediterranean, North Sea ring) silently rejected.

#### P0-003: `_process_movement_phase` does not re-validate support legality
- **Area:** engine / adjudication
- **Location:** `new_implementation/src/engine/game.py:546-604`
- **Observation:** The support pass uses `order.supported_unit` / `order.supported_target` directly without calling `order.validate()`. Any `SupportOrder` placed into `game_state.orders` (whether by `set_orders` or by direct injection) is added to `support_strengths` if not "cut", regardless of legality.
- **Why it's a bug:** Combined with P0-001/2 and the fact that `set_orders` doesn't call `order.validate()` either (see F-031 / P1-014), invalid supports always make it into adjudication.
- **Reproduction:** Same as P0-001 — MUN's support of BUR→GAS is counted in `conflicts.strengths`.
- **Blast radius:** Universal mis-resolution wherever a non-adjacent support is submitted.

#### P0-004: Army can move to sea province
- **Area:** engine / adjudication
- **Location:** `new_implementation/src/engine/game.py:474-544` (no unit-type vs. province-type check in the move-execution path); `data_models.py` MoveOrder.validate exists but is never called from `set_orders`.
- **Observation:** `A LON - NTH` is accepted and executed. The move-phase adjacency check (line 491) treats LON and NTH as adjacent (they are, for the fleet) and proceeds.
- **Why it's a bug:** Per Diplomacy rules, armies cannot enter sea spaces.
- **Reproduction:** DATC probe `6.A.1 Army to sea` — engine reports `{'unit': 'A LON', 'to': 'NTH', 'success': True}`.
- **Blast radius:** A player can move an army to any adjacent sea province and have it accepted. Cascading consequences: holds in seas, fleet/army identity confusion, supply-center logic.

#### P0-005: Fleet can move to inland province
- **Area:** engine / adjudication
- **Location:** Same as P0-004.
- **Observation:** A fleet placed at PAR (inland) can move to BUR (inland). The engine accepts both placement and movement.
- **Reproduction:** DATC probe `6.A.2 Fleet to inland`.
- **Blast radius:** Same as P0-004 but mirrored.

#### P0-006: Multi-coast adjacency check skipped when general adjacency returns True
- **Area:** engine / adjudication (multi-coast)
- **Location:** `new_implementation/src/engine/game.py:489-497`
- **Observation:**
  ```
  is_adjacent = current_province_obj.is_adjacent_to(order.target_province)
  if not is_adjacent and current_province_obj.is_multi_coast_province():
      ...
  ```
  The coast-specific check only runs when the general adjacency check is False. Since `SPA.is_adjacent_to('WES')` returns True (some coast of SPA reaches WES), the coast-specific guard never runs for a fleet at SPA/NC trying to move to WES.
- **Why it's a bug:** A fleet at SPA/NC's only valid sea moves are POR/GAS/MAO. Allowing it to reach WES (only via /SC) bypasses the multi-coast rule.
- **Reproduction:** Clarification probe — `F SPA/NC -> WES` executed with `success=True`.
- **Blast radius:** Multi-coast fleet movement (SPA, STP, BUL).

#### P0-007: Retreat options include attacker's origin province
- **Area:** engine / retreat
- **Location:** `new_implementation/src/engine/game.py:1217-1246`
- **Observation:** `_calculate_retreat_options` iterates `province_data.adjacent_provinces` and skips only occupied provinces. It does not exclude (a) the attacker's origin or (b) standoff provinces.
- **Why it's a bug:** DATC 6.H — a dislodged unit cannot retreat to the province its attacker came from, nor to any province that had a standoff this turn.
- **Reproduction:** Clarification probe — A WAR dislodged by A SIL has `retreat_options` containing `'SIL'`.
- **Blast radius:** Wrong retreat choices, wrong forced disbands, possible illegal moves accepted at retreat phase.

#### P0-008: Supply-center ownership flips immediately on Spring movement
- **Area:** engine / supply centers
- **Location:** `new_implementation/src/engine/game.py:862-873` (single-move branch), `:1007-1018` (multi-move branch). `_update_supply_center_ownership` at `:1428-1466` only runs in Autumn build.
- **Observation:** Whenever a unit moves into a supply center, `controlled_supply_centers` is updated immediately (in both Spring and Fall). Combined with the "empty SCs maintain previous control" persistence rule in `_update_supply_center_ownership`, an SC briefly visited in Spring is reassigned to the visitor and stays reassigned even if the visitor leaves before Fall.
- **Why it's a bug:** Per Diplomacy rules, supply-center ownership is only checked at the end of Fall (after retreats). Spring movement is purely positional.
- **Reproduction:** DATC probe `Custom: Spring SC ownership flip` — Russia → loses WAR after Germany passes through in Spring with no Fall presence.
- **Blast radius:** Wrong build counts in Winter; wrong "first to 18 SCs wins" timing; wrong elimination logic.

#### P0-009: Every `/admin/*` endpoint is unauthenticated
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/admin.py` — all 12 endpoints
- **Observation:** `ADMIN_TOKEN` is imported (line 11) but no route checks it. `POST /admin/delete_all_games` (line 17), `POST /admin/clear_response_cache` (line 164), `POST /admin/invalidate_cache/{game_id}` (line 176), etc. all have no `Depends` and no token check.
- **Reproduction:** `curl -X POST http://localhost:8000/admin/delete_all_games` deletes everything.
- **Blast radius:** Anyone with network access to the API can wipe the database.

#### P0-010: `/dashboard/api/services/restart` is unauthenticated and runs `sudo systemctl`
- **Area:** api / auth / infra
- **Location:** `new_implementation/src/server/api/routes/dashboard.py:98-135`
- **Observation:** No auth dependency. Runs `sudo /usr/bin/systemctl restart <service>` where `<service>` is taken from request body. Service name is allowlisted to `["diplomacy", "diplomacy-bot"]`, which limits to those two — but still constitutes an unauthenticated DoS.
- **Reproduction:** `curl -X POST http://host:8000/dashboard/api/services/restart -d '{"service":"diplomacy"}'`.
- **Blast radius:** Unauth attacker can take production services offline at will.

#### P0-011: `resolve_user_or_telegram` accepts unauthenticated `telegram_id` body
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/auth.py:174-188`
- **Observation:** If Bearer token is absent or invalid, the function falls back to `db_service.get_user_by_telegram_id(telegram_id)`. The telegram_id is a public identifier; possessing it is not a credential. Used by `POST /games/{id}/join`, `quit`, `replace`, `spectate`, `/games/set_orders`, `POST /games/{id}/message`, `POST /games/{id}/broadcast`, `POST /games/{id}/orders/{power}/clear`, `POST /games/{id}/spectate` (DELETE too).
- **Why it's a bug:** Any HTTP client that learns a victim's `telegram_id` (visible in many places — Telegram public profiles, broadcasts) can act as them: submit orders, send private messages, quit games, etc.
- **Reproduction:**
  ```
  curl -X POST http://host:8000/games/set_orders \
    -d '{"game_id":"1","power":"FRANCE","orders":["A PAR - BUR"],"telegram_id":"<victim_id>"}'
  ```
- **Blast radius:** Universal account impersonation across all bot-facing endpoints.

#### P0-012: `/games/{id}/process_turn` is unauthenticated
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/games.py:109-160`
- **Observation:** No `Depends`. Anyone can force any game's turn to process.
- **Blast radius:** Griefing — turn processed before players submit; orders for unsubmitted powers default to holds (and inactive marks).

#### P0-013: `/games/{id}/deadline` POST is unauthenticated
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/games.py:753-764`
- **Observation:** No auth. Anyone can set any game's deadline to any value (including past).
- **Blast radius:** Combine with the deadline scheduler — set deadline to past, and on next scheduler tick the turn is auto-processed regardless of player readiness.

#### P0-014: `/games/{id}/channel/link` is unauthenticated
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/channels.py:53-89`
- **Observation:** No auth. Body takes `channel_id` and binds it to the game; the rest of the system uses that channel for auto-posting maps/broadcasts.
- **Reproduction:** `curl -X POST http://host:8000/games/1/channel/link -d '{"channel_id":"-100<attacker_channel>"}'`.
- **Blast radius:** Hijack game notifications to attacker's channel; possibly leak game data; use for phishing other players.

#### P0-015: `GET /games/{id}/messages` returns all private messages when unauthenticated
- **Area:** api / auth / info leak
- **Location:** `new_implementation/src/server/api/routes/messages.py:120-150`
- **Observation:**
  ```
  user = get_current_user_optional(credentials)
  if user is None and telegram_id:
      user = db_service.get_user_by_telegram_id(telegram_id)
  ...
  if user:
      ... filter by recipient_power or sender_user_id ...
  ```
  When user is None (no Bearer, no telegram_id), the filter block is skipped. The query returns all messages including private ones (recipient_power is not null).
- **Reproduction:** `curl http://host:8000/games/1/messages` returns full message log.
- **Blast radius:** Total diplomatic information leak. Any spectator/non-participant can read every alliance negotiation.

#### P0-016: Pending orders are readable without auth
- **Area:** api / auth / info leak
- **Location:** `new_implementation/src/server/api/routes/orders.py:168-195` (`GET /games/{id}/orders`), `:216-229` (`GET /games/{id}/orders/{power}`)
- **Observation:** No auth on either endpoint. Returns pending orders for current turn from `db_service.get_orders_by_player_id`.
- **Why it's a bug:** Orders in Diplomacy are SECRET until adjudication. Reading another power's pending orders breaks the entire negotiation/bluffing dynamic.
- **Reproduction:** `curl http://host:8000/games/1/orders/FRANCE`.
- **Blast radius:** Game-breaking. Any participant can read every other power's pending orders.

#### P0-017: Telegram link code is 6 numeric digits with no rate limit
- **Area:** auth
- **Location:** `new_implementation/src/engine/database_service.py:695-707` (creation); `src/server/api/routes/auth.py:399-411` (`POST /auth/telegram/link`)
- **Observation:** `code = "".join(secrets.choice("0123456789") for _ in range(6))` — 10^6 codes, 10-minute TTL. The link endpoint has no rate limiting.
- **Why it's a bug:** Attacker who knows a victim's telegram_id can race-attempt link codes after the victim requests a link. At 1k req/s × 600 s = 600k attempts ≈ 60% hit rate before code expires. Successful link binds victim's telegram to attacker's account, granting persistent control.
- **Reproduction:** Hit `POST /auth/telegram/link` with `{"telegram_id": "<victim>", "code": "000000"}` repeatedly with random codes.
- **Blast radius:** Targeted account takeover via Telegram linking.

#### P0-018: `/games/add_player` has no auth and no user binding
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/games.py:88-107`
- **Observation:** Body takes only `game_id` and `power`. No user identifier. Creates player slot in DB via `db_service.add_player(game_id=..., power_name=...)` with no `user_id`.
- **Why it's a bug:** Anyone can occupy any power slot in any game. Combined with `/games/{id}/join` (which requires auth but checks "if taken → 409"), an attacker can spam-claim powers preemptively to deny them to legit users.
- **Reproduction:** `curl -X POST http://host:8000/games/add_player -d '{"game_id":"1","power":"FRANCE"}'`.
- **Blast radius:** Power-slot squatting/denial.

#### P0-019: `/games/create` is unauthenticated
- **Area:** api / auth / DoS
- **Location:** `new_implementation/src/server/api/routes/games.py:62-86`
- **Observation:** No auth. Anyone can create unlimited games.
- **Blast radius:** Resource exhaustion (DB rows, in-memory `server.games` dict).

#### P0-020: `/users/persistent_register` is unauthenticated
- **Area:** api / auth
- **Location:** `new_implementation/src/server/api/routes/users.py:59-86`
- **Observation:** Body takes `telegram_id` and `full_name` and creates a DB row. If an attacker registers a victim's `telegram_id` first, the attacker now owns that user record; later, when the victim's Telegram bot does `persistent_register`, the endpoint returns "already_registered" with the *attacker's* user_id. The victim transparently uses the attacker's user.
- **Reproduction:** `curl -X POST http://host:8000/users/persistent_register -d '{"telegram_id":"<victim>","full_name":"X"}'` before the victim ever uses the bot.
- **Blast radius:** Pre-claim account hijack — works against any new Telegram user.

#### P0-021: JWT default secret is the hardcoded literal `dev-secret-change-in-production-32b`
- **Area:** auth
- **Location:** `new_implementation/src/server/api/routes/auth.py:33`
- **Observation:** `JWT_SECRET = os.environ.get("DIPLOMACY_JWT_SECRET", "dev-secret-change-in-production-32b")`. If the env var is not set in production, the secret is in plaintext in the public repo. Any attacker can mint Bearer tokens for any user_id.
- **Reproduction:** `python -c "import jwt; print(jwt.encode({'sub':'1','exp':9999999999,'type':'access'}, 'dev-secret-change-in-production-32b'))"` → use as Bearer.
- **Blast radius:** Total auth bypass if the deployment forgets the env var. There's no startup-time check to refuse to boot with the default.

#### P0-022: Deadline scheduler runs `PROCESS_TURN` without lock vs. concurrent HTTP `/process_turn`
- **Area:** scheduler / concurrency
- **Location:** `new_implementation/src/server/api/shared.py:195` (scheduler) and `src/server/api/routes/games.py:109-160` (HTTP)
- **Observation:** Both paths call `server.process_command(f"PROCESS_TURN {game_id_str}")` against the shared `server.games[game_id]` `Game` object. No lock, no transaction. Concurrent calls mutate the same `game_state` dict and the same DB rows.
- **Reproduction:** With a game deadline expiring, race `curl -X POST .../process_turn` against the scheduler's 30-second tick.
- **Blast radius:** Turn processed twice (units moved twice, builds doubled), or state torn (some powers' orders cleared, others not).

---

### ENGINE — P1

#### P1-001: Retreat options don't filter by unit type
- **Location:** `src/engine/game.py:1227-1244`
- **Observation:** `_calculate_retreat_options` adds every adjacent unoccupied province to `retreat_options`, regardless of whether `province_type` is compatible with the unit's `unit_type`.
- **Impact:** Dislodged army can be assigned a retreat to a sea province; dislodged fleet to inland.

#### P1-002: Retreat options for multi-coast fleets ignore coast-specific adjacency
- **Location:** `src/engine/game.py:1217-1246`
- **Observation:** Uses `province_data.adjacent_provinces` (general), not the coast-specific list from `get_coast_specific_adjacencies(unit.coast)`. Fleet at SPA/SC could retreat to provinces reachable only from SPA/NC.

#### P1-003: Two units retreating to the same province don't both disband
- **Location:** `src/engine/game.py:1248-1318`
- **Observation:** `_process_retreat_phase` processes retreats sequentially. The first retreat succeeds (target empty); the second sees target occupied (`_is_valid_retreat` returns False) and the *second* unit disbands. Per DATC 6.H.10 ("Two retreats to same province"), both must disband.

#### P1-004: Build phase has zero validation
- **Location:** `src/engine/game.py:1462-1510`
- **Observation:** `BuildOrder` and `DestroyOrder` are executed without checking: home SC ownership, target province occupancy, total build count vs. excess SCs, or destroy ownership.
- **Impact:** A power can issue arbitrary builds in non-home SCs, or exceed its allowed build count, if the order reaches process_builds_phase without earlier validation (which validation methods exist but aren't wired into `set_orders`).

#### P1-005: `_is_valid_move` rejects all moves to occupied provinces (dead code)
- **Location:** `src/engine/game.py:1357-1358`
- **Observation:** `if any(u.province == order.target_province for u in self.game_state.get_all_units()): return False`. Comment literally admits "In actual Diplomacy, moves to occupied provinces are valid and cause battles but this test expects them to be invalid in initial validation."
- **Impact:** Dead in production (`set_orders` doesn't call this), but `test_enhanced_validation.py` uses it. The presence of this code suggests the validation architecture is held together by test-driven hacks.

#### P1-006: Validation methods `_validate_order_comprehensive` / `_is_valid_*` are dead in `set_orders`
- **Location:** `src/engine/game.py:176-330` (set_orders) vs. `:1397-1426` (validators)
- **Observation:** `set_orders` calls `parser.create_order_from_parsed()` and does ad-hoc checks (self-support, duplicates, self-occupied target), then returns. It never calls `_validate_order_comprehensive`, and `create_order_from_parsed` never calls `order.validate()`.
- **Impact:** All `Order.validate()` logic — including adjacency checks for SupportOrder, ConvoyOrder, BuildOrder, RetreatOrder — is bypassed in the production submission path. Invalid orders are stored verbatim.

#### P1-007: Support cut logic missing DATC 6.D exception
- **Location:** `src/engine/game.py:574-583`
- **Observation:** Any unit moving to the supporter's province cuts support. Per Calhamer/DATC, an attack from the very destination of the supported attack does NOT cut support (the "circular support" exception). Engine doesn't model this.

#### P1-008: `moves[].strength` inconsistent (base for losers, total for winners)
- **Location:** `src/engine/game.py:858, 1003, 1059`
- **Observation:** In the single-move branch, success path uses local `strength` post-support-add. In multi-move, winner uses `max_strength` (total), losers use `strength` from `remaining_moves` (base). Standoff branch (line 1066-1083) uses base. Clients/tests cannot rely on the field.

#### P1-009: SC ownership "persistence" cements wrongly flipped centers
- **Location:** `src/engine/game.py:1442-1460`
- **Observation:** `_update_supply_center_ownership` keeps "previous control" for empty SCs. Combined with P0-008 (in-Spring flipping), a Spring transit through an SC re-attributes ownership permanently even though no unit is there in Fall.

#### P1-010: `PROCESS_TURN` clears all orders for all powers after phase
- **Location:** `src/server/server.py:194-195`
- **Observation:** After every phase, all powers' orders are cleared. Including retreat-phase orders that may have already been parsed for the retreat phase. Subtle, but causes state churn.

#### P1-011: `REMOVE_PLAYER` orphans units
- **Location:** `src/server/server.py:243-260`
- **Observation:** Deletes power from `powers` dict but leaves unit instances dangling (unit.power still references the gone power).

#### P1-012: 27 engine adjudication tests fail (pure-engine, no DB needed)
- **Location:** `tests/test_battle_resolution.py`, `tests/test_standoff_detection.py`, `tests/test_order_resolution.py`, `tests/test_demo_game_battles.py`, `tests/test_province_data_coverage.py`
- **Observation:** All these tests use the pattern `game.add_player("FRANCE"); game.game_state.powers["FRANCE"].units.append(Unit(...))` — `add_player` already adds the canonical starting units, so the append creates *duplicate* units in the same province. The engine's support-cut check (line 574-583) then treats one duplicate as an attacker of the other, cutting support.
- **Impact:** The test suite is structurally broken — 27 supposedly-passing tests fail on a clean run. Clean-state probes (`/tmp/datc_probes.py`) confirm the engine resolves standoffs correctly for some cases, so these are mostly test-setup bugs masking the absence of real coverage.

#### P1-013: `set_orders` does not invalidate response cache for state/orders
- **Location:** `src/server/api/routes/orders.py:57-166`
- **Observation:** After persisting orders, no call to `invalidate_cache(f"games/{game_id}")`. The cached `GET /games/{id}/state`, `/orders`, `/players` (TTL 30/60 s) serve stale data.

#### P1-014: `clear_orders` does not invalidate cache
- **Location:** `src/server/api/routes/orders.py:234-263`

#### P1-015: `GET /games/{id}/orders/history` is unauthenticated
- **Location:** `src/server/api/routes/orders.py:197-214`
- **Observation:** Returns past orders for all powers. Even post-adjudication orders are sensitive (reveal who was bluffing). No auth.

#### P1-016: `GET /users/{telegram_id}` and `/users/{telegram_id}/games` are unauthenticated
- **Location:** `src/server/api/routes/users.py:51-57, 111-123`
- **Observation:** No auth. Returns user session and list of games. Anyone with a known telegram_id can enumerate a user's games.

#### P1-017: `POST /users/register` accepts arbitrary in-memory sessions
- **Location:** `src/server/api/routes/users.py:43-49`
- **Observation:** Stores user_sessions[telegram_id] = UserSession(...). No auth. Anyone can register or overwrite anyone's in-memory session.

#### P1-018: `GET /games/{id}/spectators` is unauthenticated
- **Location:** `src/server/api/routes/games.py:469-477`

#### P1-019: `GET /dashboard/api/logs/{service}` is unauthenticated
- **Location:** `src/server/api/routes/dashboard.py:137+`
- **Observation:** Returns systemd logs unauthenticated — potentially leaks request bodies, stack traces, or other sensitive info.

#### P1-020: Scheduler exception-handling wraps the full loop
- **Location:** `src/server/api/shared.py:163-242`
- **Observation:** `try: for game in games: ... except Exception:` — if one game's processing raises, all subsequent games in the same tick are skipped. The reminder/dashboard loop at lines 260-340 has the same shape.

#### P1-021: Deadline-null ordering creates stuck-game window
- **Location:** `src/server/api/shared.py:193-198`
- **Observation:**
  ```
  server.process_command(f"PROCESS_TURN {game_id_str}")   # mutates state in-memory; may or may not persist
  db_service.update_game_deadline(game_id_val, None)       # nulls deadline
  db_service.commit()
  ```
  `process_command(PROCESS_TURN)` updates `server.games[id]` but persistence to DB via `update_game_state` happens only on the HTTP `/process_turn` path (games.py:127-148), not from the scheduler. If the process crashes between the in-memory mutation and `update_game_deadline`, on restart the in-memory state is gone, the deadline is still set, and the cycle repeats. If it crashes between `update_game_deadline` and `commit`, deadline is in the SQLAlchemy session but not flushed.

#### P1-022: `ADMIN_TOKEN` defaults to `"changeme"`
- **Location:** `src/server/api/shared.py:47`
- **Observation:** Used only by `mark_player_inactive` (games.py:720). Anywhere that env var is not overridden, the literal "changeme" is a valid admin token.

#### P1-023: DAIDE `submit_orders` uses `int(game_id)` against string game IDs
- **Location:** `src/server/daide_protocol.py:161`
- **Observation:** `db_service.create_game` returns a `game_id` that may be a string (game_id_str of a UUID or numeric). `int(game_id)` raises if non-numeric. Surrounding try/except swallows it and continues to the in-memory `SET_ORDERS` (line 163), creating DB/in-memory divergence.

#### P1-024: DAIDE `for/else` discards partial order_objects on first failure
- **Location:** `src/server/daide_protocol.py:150-163`
- **Observation:** The `for parsed in parsed_orders: ... except: response = ...; break` followed by `else: db_service.submit_orders(...)`. If any single order fails to create, submit is skipped — but the in-memory SET_ORDERS below the `else` runs *regardless* (it's outside the for/else), creating DB/in-memory state divergence.

#### P1-025: DAIDE has its own `DatabaseService` instance
- **Location:** `src/server/daide_protocol.py:14`
- **Observation:** `db_service = DatabaseService(SQLALCHEMY_DATABASE_URL)` — separate session factory from the HTTP API. Concurrent writes against the same game from DAIDE and HTTP are not coordinated; no row-level locking (no `SELECT … FOR UPDATE`). Lost-update race possible.

---

### P2 (latent, dead code, cosmetic, info-tier)

#### P2-001: 111 Ruff errors in `src/`
- **Files:** 14 in `src/engine/map.py`, 12 in `src/server/api/shared.py`, plus 85 across other files. Mostly unused imports (F401) and unused variables (F841). CI workflow at `.github/workflows/test.yml:38-40` claims `ruff check src/ --output-format=github` — either CI is red, or it's not enforced on push.

#### P2-002: `_check_victory_condition` doesn't handle ties
- **Location:** `src/engine/game.py:1511-1520`
- **Observation:** Iterates `powers.items()` and picks first ≥18 — Python dict iteration is insertion order, so the result is deterministic but arbitrary if two powers tie.

#### P2-003: `SAVE_GAME`/`LOAD_GAME` use `pickle` with no integrity check
- **Location:** `src/server/server.py:219-242`
- **Observation:** Not exposed in HTTP or DAIDE today, but any future path that forwards these CLI commands → RCE on `LOAD_GAME`.

#### P2-004: Cache key uses MD5
- **Location:** `src/server/response_cache.py:54`
- **Observation:** MD5 collision probability is academic at cache-key scale; flagged for completeness.

#### P2-005: Self-dislodgement loser reported as "defeated"
- **Location:** `src/engine/game.py:1051-1062`
- **Observation:** When self-dislodgement prevents a winning move, the holder's hold is appended to `results["moves"]` with `failure_reason: "defeated"`. The holder was the defender, not defeated — label is misleading. Same hold also appears as a separate success entry.

#### P2-006: No rate limiting on `/auth/login`
- **Location:** `src/server/api/routes/auth.py:229-246`. Brute-force password guessing has no in-app limiter. (Bcrypt is slow, partially mitigates.)

#### P2-007: `mark_player_inactive` admin_token in body
- **Location:** `src/server/api/routes/games.py:717-739`
- **Observation:** Should be a header (e.g., `X-Admin-Token`) to avoid body logging.

#### P2-008: Bare `except Exception: raise HTTPException(500, str(e))` leaks internals
- **Files:** Every route module. Internal exception messages (SQL errors, stack contents) returned to clients.

#### P2-009: DAIDE 100-message-per-connection limit drops clients silently
- **Location:** `src/server/daide_protocol.py:66-68`. Intended for tests; production effect is silent client kick.

#### P2-010: No JWT revocation
- **Location:** `src/server/api/routes/auth.py`. Logout / password change does not invalidate outstanding access (30 min) or refresh (7 days) tokens. No blacklist.

#### P2-011: `forgot_password` timing leak
- **Location:** `src/server/api/routes/auth.py:365-383`. Existing users take measurably longer (token creation, SMTP); attacker can enumerate emails by timing the response.

#### P2-012: `users/register` and `users/persistent_register` overlap and confuse model
- **Location:** `src/server/api/routes/users.py:18-86`. Two parallel "register" endpoints (in-memory vs DB), neither auth-gated, both writable by anyone. Code-smell that obscures the auth contract — easy place for a future P0.

---

## What was NOT investigated

- Full read of `map.py` (3,617 lines) — only spot-checked. Adjacency tables not exhaustively diffed against `old_implementation/diplomacy/maps/standard.map`. Worth a follow-up if any province is suspected wrong.
- Channel routes (`channels.py`, 838 lines) beyond the link/unlink endpoints. Likely more unauth endpoints; budget exhausted.
- Tournament routes (`tournaments.py`, 190 lines) — flagged as no-auth but out of scope per `specs/fix_plan.md`.
- Alembic migrations beyond the raw-SQL spot check (no SQL injection observed; not all reversibility checked).
- Convoy paradoxes (DATC 6.F, 6.G) — only smoke tested.

## Recommendations (not implementation — for triage planning)

The P0 list combines into two themes that should be addressed first:

1. **Adjudication correctness** (P0-001..P0-008): The validation architecture is broken — `Order.validate()` exists, is buggy where wired in, and isn't wired in for `set_orders`. Fix order: (a) wire `_validate_order_comprehensive` into `set_orders`, (b) fix `SupportOrder.validate` (drop the `adjacent_to_origin` clause; expand sea support rule), (c) make the move-phase adjacency check coast-aware-first not coast-aware-on-fail, (d) add unit-type-vs-province-type checks at submission and adjudication, (e) defer SC ownership update to end-of-Fall only, (f) exclude attacker origin from retreat options.

2. **Authorization** (P0-009..P0-022): The API trusts unauthenticated `telegram_id`, ships zero auth on `/admin/*`, `/dashboard/*` write endpoints, `/games/create`, `/games/add_player`, `/games/{id}/process_turn`, `/games/{id}/deadline` (POST), `/games/{id}/channel/link`, `/users/persistent_register`, and `GET /games/{id}/messages`/`/orders`/`/orders/{power}`/`/orders/history`. The default JWT secret and "changeme" admin token compound this. Treat as a single deploy-blocker.

The P1/P2 lists are accumulated tech debt — work them after P0 is closed.
