#!/usr/bin/env python3
"""
Test script to specifically check Italy's orders in the demo game.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engine.game import Game
from engine.map import Map
from engine.order_visualization import OrderVisualizationService

def test_italy_orders_specifically():
    """Test Italy's orders specifically to see if they're visible."""
    
    print("🔍 TESTING ITALY ORDERS SPECIFICALLY")
    print("=" * 50)
    
    # Create the exact same scenario as the demo game
    game = Game(map_name='standard')
    
    # Add all players
    powers = ['GERMANY', 'FRANCE', 'ENGLAND', 'RUSSIA', 'ITALY', 'AUSTRIA', 'TURKEY']
    for power in powers:
        game.add_player(power)
    
    print(f"✅ Created game with all powers")
    
    # Submit the exact same orders as in the demo game Autumn 1901
    print(f"\n📋 Submitting Autumn 1901 orders (same as demo game):")
    
    # Germany orders
    game.set_orders('GERMANY', ['A BER - PRU', 'A MUN S A BER'])
    print(f"  GERMANY: A BER - PRU, A MUN S A BER")
    
    # France orders  
    game.set_orders('FRANCE', ['A PAR - BUR', 'A MAR - PIE', 'F BRE - MAO'])
    print(f"  FRANCE: A PAR - BUR, A MAR - PIE, F BRE - MAO")
    
    # England orders
    game.set_orders('ENGLAND', ['F LON H', 'F EDI - CLY', 'A LVP - WAL'])
    print(f"  ENGLAND: F LON H, F EDI - CLY, A LVP - WAL")
    
    # Russia orders
    game.set_orders('RUSSIA', ['A MOS S F SEV', 'A WAR - PRU', 'F SEV S A MOS - UKR', 'F STP H'])
    print(f"  RUSSIA: A MOS S F SEV, A WAR - PRU, F SEV S A MOS - UKR, F STP H")
    
    # Italy orders (THE KEY ONES)
    game.set_orders('ITALY', ['A ROM S A VEN', 'A VEN S A ROM', 'F NAP - ROM'])
    print(f"  ITALY: A ROM S A VEN, A VEN S A ROM, F NAP - ROM")
    
    # Austria orders
    game.set_orders('AUSTRIA', ['A VIE H', 'A BUD S A VIE - GAL', 'F TRI - SER'])
    print(f"  AUSTRIA: A VIE H, A BUD S A VIE - GAL, F TRI - SER")
    
    # Turkey orders
    game.set_orders('TURKEY', ['A CON - BUL', 'A SMY - ARM', 'F ANK - SMY'])
    print(f"  TURKEY: A CON - BUL, A SMY - ARM, F ANK - SMY")
    
    # Check stored orders
    print(f"\n📊 Checking stored orders:")
    for power in powers:
        orders = game.game_state.orders.get(power, [])
        print(f"  {power}: {len(orders)} orders")
        for i, order in enumerate(orders):
            print(f"    {i+1}. {order}")
    
    # Create visualization
    print(f"\n📋 Creating order visualization:")
    vis_service = OrderVisualizationService()
    orders_vis = vis_service.create_visualization_data(game.game_state)
    
    print(f"📊 Visualization results:")
    for power in powers:
        vis_orders = orders_vis.get(power, [])
        print(f"  {power}: {len(vis_orders)} visualized orders")
        for i, vis_order in enumerate(vis_orders):
            print(f"    {i+1}. {vis_order}")
    
    # Generate units for map
    units = {}
    for power_name, power_state in game.game_state.powers.items():
        units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
    
    print(f"\n📊 Units for map:")
    for power, unit_list in units.items():
        print(f"  {power}: {unit_list}")
    
    # Generate the orders map
    print(f"\n🗺️  Generating orders map...")
    svg_path = os.path.join(os.path.dirname(__file__), "maps", "standard.svg")
    output_path = os.path.join(os.path.dirname(__file__), "test_maps", "italy_orders_test.png")
    
    phase_info = {
        'turn': game.game_state.current_turn,
        'year': game.game_state.current_year,
        'season': game.game_state.current_season,
        'phase': game.game_state.current_phase,
        'phase_code': game.game_state.phase_code
    }
    
    try:
        img_bytes = Map.render_board_png_with_orders(
            svg_path, 
            units, 
            orders_vis,
            phase_info=phase_info,
            output_path=output_path
        )
        print(f"✅ Orders map generated: {output_path}")
        print(f"   Image size: {len(img_bytes)} bytes")
        print(f"   Check this map to see if Italy's orders are visible!")
    except Exception as e:
        print(f"❌ Map generation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Process the turn to see what happens
    print(f"\n🤖 Processing turn...")
    results = game.process_turn()
    
    print(f"📊 Movement results:")
    for move in results.get('moves', []):
        print(f"  {move}")
    
    print(f"\n📊 Unit positions after movement:")
    for power_name, power_state in game.game_state.powers.items():
        print(f"  {power_name}:")
        for unit in power_state.units:
            print(f"    {unit.unit_type} {unit.province} (dislodged: {unit.is_dislodged})")
    
    print("\n" + "=" * 50)
    print("🔍 ITALY ORDERS TEST COMPLETE")

if __name__ == "__main__":
    test_italy_orders_specifically()
