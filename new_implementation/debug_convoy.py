#!/usr/bin/env python3

import sys
import os
sys.path.append('/home/helgejalonen/diplomacy/new_implementation')

from src.engine.game import Game
from src.engine.data_models import Unit

def debug_convoy_test():
    print("=== Debug Convoy Test ===")
    game = Game('standard')
    game.add_player("ENGLAND")
    game.add_player("GERMANY")
    
    # Add units to the new data model
    game.game_state.powers["ENGLAND"].units = [
        Unit(unit_type='A', province='LON', power='ENGLAND'),
        Unit(unit_type='F', province='NTH', power='ENGLAND'),
        Unit(unit_type='A', province='YOR', power='ENGLAND')
    ]
    game.game_state.powers["GERMANY"].units = [
        Unit(unit_type='A', province='HOL', power='GERMANY')
    ]
    
    print("Before orders:")
    print(f"ENGLAND units: {[str(unit) for unit in game.game_state.powers['ENGLAND'].units]}")
    print(f"GERMANY units: {[str(unit) for unit in game.game_state.powers['GERMANY'].units]}")
    
    game.set_orders("ENGLAND", [
        "ENGLAND A LON - HOL",
        "ENGLAND F NTH C A LON - HOL",
        "ENGLAND A YOR S A LON - HOL"
    ])
    game.set_orders("GERMANY", [
        "GERMANY A HOL H"
    ])
    
    print("\nAfter setting orders:")
    print(f"ENGLAND orders: {game.game_state.orders.get('ENGLAND', [])}")
    print(f"GERMANY orders: {game.game_state.orders.get('GERMANY', [])}")
    
    result = game.process_turn()
    print(f"\nProcess turn result: {result}")
    
    print("\nAfter processing turn:")
    print(f"ENGLAND units: {[str(unit) for unit in game.game_state.powers['ENGLAND'].units]}")
    print(f"GERMANY units: {[str(unit) for unit in game.game_state.powers['GERMANY'].units]}")
    
    # Check if convoy worked
    england_hol = any(unit.province == 'HOL' for unit in game.game_state.powers["ENGLAND"].units)
    germany_hol = any(unit.province == 'HOL' for unit in game.game_state.powers["GERMANY"].units)
    
    print(f"\nResults:")
    print(f"ENGLAND has unit in HOL: {england_hol}")
    print(f"GERMANY has unit in HOL: {germany_hol}")

if __name__ == "__main__":
    debug_convoy_test()
