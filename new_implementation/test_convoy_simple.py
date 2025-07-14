#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

try:
    from src.engine.game import Game
    print("Game import successful")
    
    game = Game()
    print("Game created")
    
    game.add_player('ENGLAND')
    game.add_player('FRANCE')
    print("Players added")
    
    game.powers['ENGLAND'].units = {'A LON', 'F NTH', 'A YOR'}
    game.powers['FRANCE'].units = {'A BEL'}
    print("Units set")
    
    game.set_orders('ENGLAND', ['ENGLAND A LON - BEL', 'ENGLAND F NTH C A LON - BEL', 'ENGLAND A YOR S A LON - BEL'])
    game.set_orders('FRANCE', ['FRANCE A BEL H'])
    print("Orders set")
    
    print("Processing turn...")
    game.process_turn()
    print("Turn processed")
    
    print('ENGLAND units:', game.powers['ENGLAND'].units)
    print('FRANCE units:', game.powers['FRANCE'].units)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
