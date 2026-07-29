"""DAIDE protocol support (Track D, `docs/specs/fix_plan.md`).

- `tokens` -- the fixed 2-byte token vocabulary and signed-integer/ASCII
  escape encodings.
- `wire` -- the DCSP framing layer (message headers, handshake, payload
  envelopes) built on `asyncio.StreamReader`/`StreamWriter`.
- `clauses` -- the encode/decode bridge between DAIDE token-stream clauses
  (locations, units, turns, and all 9 order-clause shapes) and `engine.types`.

Later Track D milestones add `session` (per-connection protocol state
machine) and `server` (the `asyncio.start_server` listener).
"""
