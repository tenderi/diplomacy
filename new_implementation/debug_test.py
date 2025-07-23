#!/usr/bin/env python3

from src.engine.game import Game  # noqa

# Load mini variant by name
game = Game(map_name="mini_variant")
game.add_player("RED")
game.add_player("BLUE")
# Place units for both powers in adjacent provinces
game.powers["RED"].units = {"A PAR"}
game.powers["BLUE"].units = {"A BUR"}
print("Before turn:")
print(f"RED units: {game.powers['RED'].units}")
print(f"BLUE units: {game.powers['BLUE'].units}")

# RED attacks, BLUE holds
game.set_orders("RED", ["RED A PAR - BUR"])
game.set_orders("BLUE", ["BLUE A BUR H"])
print("\nOrders set:")
print(f"RED orders: {game.orders['RED']}")
print(f"BLUE orders: {game.orders['BLUE']}")

game.process_phase()

print("\nAfter turn:")
print(f"RED units: {game.powers['RED'].units}")
print(f"BLUE units: {game.powers['BLUE'].units}")

# Check adjacency
print(f"\nAdjacency PAR: {game.map.get_adjacency('PAR')}")
print(f"Is BUR adjacent to PAR? {game.map.is_adjacent('PAR', 'BUR')}")
