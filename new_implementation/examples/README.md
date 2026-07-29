# Examples

## `demo_perfect_game.py`

A scripted two-year game that exercises every order type and mechanic, rendering a map
series for each phase into `test_maps/`. Because the orders are hardcoded it is fully
deterministic, which makes it the project's end-to-end sanity check: any change in
adjudication or rendering shows up as a different result.

```bash
PYTHONPATH=src python examples/demo_perfect_game.py
```

Design and phase-by-phase scenarios:
[`docs/specs/automated_demo_game_spec.md`](../docs/specs/automated_demo_game_spec.md).

## CLI server session

`Server` (`src/server/server.py`) accepts text commands and is the quickest way to drive the
engine without HTTP:

```python
from server.server import Server

server = Server()
game_id = server.process_command("CREATE_GAME standard")["game_id"]
server.process_command(f"ADD_PLAYER {game_id} FRANCE")
server.process_command(f"ADD_PLAYER {game_id} GERMANY")
server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
server.process_command(f"SET_ORDERS {game_id} GERMANY A BER - MUN")
server.process_command(f"PROCESS_TURN {game_id}")
print(server.process_command(f"GET_GAME_STATE {game_id}"))
```

Run it with `PYTHONPATH=src` from `new_implementation/`. `standard` is the only supported
map — `map_name` is recorded on the game row, but the engine always loads
`maps/standard.map`.

---

> `order_visualization_example.py` is **stale** — it imports `engine.map`, which was split
> into `src/rendering/` and no longer exists. Use the map endpoints or
> `demo_perfect_game.py` for order-visualization examples until it is rewritten.
