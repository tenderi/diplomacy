#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/helge/diplomacy/new_implementation/src')

from engine.game import Game
from engine.order import OrderParser

def test_mini_variant():
    print("=== Testing mini_variant map ===")
    game = Game(map_name='mini_variant')
    print("Game created with map:", game.map_name)
    
    game.add_player('FRANCE')
    game.powers['FRANCE'].units = {'A PAR'}
    print("Units before:", game.powers['FRANCE'].units)
    
    # Test order parsing
    order_str = 'A PAR - MAR'
    print(f"Testing order: {order_str}")
    
    try:
        order = OrderParser.parse(order_str)
        print(f"Parsed order: {order}")
        
        # Test validation
        state = game.get_state()
        print(f"Game state units: {state.get('units', {})}")
        
        valid, error = OrderParser.validate(order, state)
        print(f"Order valid: {valid}, error: {error}")
        
        if valid:
            print("Order is valid, processing turn...")
            game.set_orders('FRANCE', [order_str])
            print("Orders set:", game.orders)
            
            game.process_turn()
            print("Units after:", game.powers['FRANCE'].units)
        else:
            print("Order validation failed!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_mini_variant()
