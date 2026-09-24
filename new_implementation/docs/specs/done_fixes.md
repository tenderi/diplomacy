

---

# Track Z — Telegram order entry (maintainer report, 2026-09-24)

## Why this track exists

The maintainer played the demo game (game 1) as Germany through the bot, ordered all three
units, and only one moved. Nothing was wrong with adjudication: the only German order ever
stored was the last one entered.

## Z1 — Orders sent one at a time overwrote each other — **done, `v2.7.104`**

- [x] **Cause.** Every bot path posts to `POST /games/set_orders` — `/selectunit` one order
      per request, `/order` one message's worth — and `GameService.submit_orders` stored
      `pending[power] = <this request's orders>`. Each submission wiped the previous ones,
      while the bot replied "Submit more orders with /selectunit". (The legacy text-command
      `server.py` had merged, `existing + [order]`; the HTTP path never did.)
- [x] **Fix.** `set_orders` takes `merge` (the bot always sends `true`; the web client, which
      sends the full set, keeps replace). Merging keys orders by their unit's province (a
      build by its site): a new valid order replaces that unit's old one, an invalid one
      never displaces a good one, `WAIVE`s append.
- [x] **W10 knock-on.** Auto-processing counted a power as done once it had *any* order, so
      one-at-a-time entry would have run the turn after a player's first unit. It now waits
      until each power has ordered everything that must act (`GameService._orders_complete`:
      every unit / every dislodged unit / as many builds-waives-disbands as owed);
      `orders_status` gains `incomplete`, shown in `/status`. Holding needs an explicit `H`.
- Tests: `tests/test_order_merge.py` (5, incl. the demo scenario end to end); W10's tests now
      order every unit.

## Z2 — Two order-entry flows: all units, or one — **done, `v2.7.105`**

- [x] Maintainer's request: players usually order *all* their units, sometimes only some.
      **`/orderall [game]`** walks every unit that must act this phase (retreats: every
      dislodged unit; adjustments: each build/disband slot, with already-chosen builds taken
      off the list), one screen per unit with its legal orders — supports and convoys
      through the same sub-menus as `/selectunit` — plus ⬅️ Back, ⏭ Skip and ❌ Cancel, then
      a summary to **submit everything in one request** (merged, Z1) or start over. A
      skipped unit keeps any earlier order, else holds. If the turn was processed while the
      player was choosing, nothing is sent and they are told. **`/selectunit`** stays the
      one-order flow (sent at once) and now offers "📋 Order all units, one by one" at the top.
- [x] Mechanics: the walk lives in `user_data["order_walk"][game_id]`; while it exists, an
      `ord|` pick is recorded for the current step instead of submitted
      (`app.button_callback`), which is what lets the existing support/convoy sub-menus
      serve both flows. `/orderall` is in the "/" menu; help, demo help and
      `TELEGRAM_BOT_COMMANDS.md` updated.
- Tests: `tests/test_order_all_flow.py` (7, driven through the real callback router:
      full walk with skip/back, a support from the sub-menu, skipped units, turn moved on,
      cancel, adjustment slots, and `/selectunit` still sending at once).
