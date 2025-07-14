# Example Game: France vs Germany (Standard Map)

This example demonstrates a minimal game using the standard map, showing server commands and expected state transitions.

## Example Commands
```
CREATE_GAME standard
ADD_PLAYER 1 FRANCE
ADD_PLAYER 1 GERMANY
SET_ORDERS 1 FRANCE A PAR - BUR
SET_ORDERS 1 GERMANY A BER - MUN
PROCESS_TURN 1
GET_GAME_STATE 1
```

## Expected Output
- Both players are added to the game.
- Orders are set and processed.
- The game state reflects the new unit positions after the turn.

---

# Example Game: Mini Variant

This example uses the custom `mini_variant` map from `/maps/mini_variant.json`.

## Example Commands
```
CREATE_GAME mini_variant
ADD_PLAYER 1 FRANCE
SET_ORDERS 1 FRANCE A PAR - MAR
PROCESS_TURN 1
GET_GAME_STATE 1
```

## Expected Output
- The game uses the custom map.
- France's unit moves from PAR to MAR if the move is valid in the variant.

---

# How to Run Examples
1. Start the server: `python -m server.server`
2. Enter the commands above in the server CLI.
3. Observe the output and game state after each turn.

See the [README.md](../README.md) for more details on running and testing the server.
