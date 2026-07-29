"""DAIDE protocol support (Track D, `docs/specs/fix_plan.md`).

- `tokens` -- the fixed 2-byte token vocabulary and signed-integer/ASCII
  escape encodings.
- `wire` -- the DCSP framing layer (message headers, handshake, payload
  envelopes) built on `asyncio.StreamReader`/`StreamWriter`.

Later Track D milestones add `clauses` (order/location encode-decode against
`engine.types`), `session` (per-connection protocol state machine), and
`server` (the `asyncio.start_server` listener).
"""
