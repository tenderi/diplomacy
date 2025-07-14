#!/usr/bin/env python3
"""Debug convoy move parsing and adjudication."""

from src.engine.game import Game
from src.engine.order import OrderParser

def debug_convoy():
    game = Game()
    game.add_player("ENGLAND")
    game.add_player("FRANCE")
    game.powers["ENGLAND"].units = {"A LON", "F NTH", "A YOR"}
    game.powers["FRANCE"].units = {"A BEL"}
    
    # England A LON - BEL via convoy with support, F NTH convoys, A YOR supports
    orders = [
        "ENGLAND A LON - BEL",
        "ENGLAND F NTH C A LON - BEL",
        "ENGLAND A YOR S A LON - BEL"
    ]
    
    print("=== Parsing Orders ===")
    for order_str in orders:
        try:
            order = OrderParser.parse(order_str)
            print(f"Order: {order}")
            print(f"  Power: {order.power}")
            print(f"  Unit: {order.unit}")
            print(f"  Action: {order.action}")
            print(f"  Target: {order.target}")
        except Exception as e:
            print(f"Error parsing '{order_str}': {e}")
        print()
    
    print("=== Game State Before ===")
    for power, p in game.powers.items():
        print(f"{power}: {p.units}")
    
    game.set_orders("ENGLAND", orders)
    game.set_orders("FRANCE", ["FRANCE A BEL H"])
    
    print("\n=== Processing Turn ===")
    game.process_turn()
    
    print("\n=== Game State After ===")
    for power, p in game.powers.items():
        print(f"{power}: {p.units}")

if __name__ == "__main__":
    debug_convoy()
