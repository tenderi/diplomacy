#!/usr/bin/env python3
"""
Test script to isolate the TypeError issue in the demo game.
"""

import os
import sys
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from engine.data_models import (
    GameState, PowerState, Unit, OrderType, OrderStatus, GameStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder,
    MapData, Province
)
from engine.order_visualization import OrderVisualizationService


def test_demo_conversion():
    """Test the demo game data conversion"""
    print("🧪 Testing demo game data conversion...")
    
    # Simulate the demo game data structure
    game_state = {
        'powers': ['GERMANY', 'FRANCE', 'ENGLAND'],
        'units': {
            'GERMANY': ['A BER', 'A MUN', 'F KIE'],
            'FRANCE': ['A PAR', 'A MAR', 'F BRE'],
            'ENGLAND': ['A LVP', 'F LON', 'F EDI']
        },
        'supply_centers': {
            'GERMANY': ['BER', 'MUN', 'KIE'],
            'FRANCE': ['PAR', 'MAR', 'BRE'],
            'ENGLAND': ['LVP', 'LON', 'EDI']
        },
        'turn': 1,
        'year': 1901,
        'season': 'Spring',
        'phase': 'Movement',
        'phase_code': 'S1901M'
    }
    
    orders = {
        'GERMANY': ['GERMANY A BER - HOL', 'GERMANY A MUN - BUR', 'GERMANY F KIE - DEN'],
        'FRANCE': ['FRANCE A PAR - BEL', 'FRANCE A MAR - SPA', 'FRANCE F BRE - MAO'],
        'ENGLAND': ['ENGLAND A LVP H', 'ENGLAND F LON H', 'ENGLAND F EDI - NTH']
    }
    
    # Create the conversion method (copied from demo game)
    def _convert_to_new_data_model(game_state, orders):
        from engine.data_models import GameState, PowerState, Unit, OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, MapData, Province
        from datetime import datetime
        
        # Create basic map data (simplified for demo)
        provinces = {}
        for province_name in ["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "LON", "NTH", "ENG", "BUR", "BEL", "HOL", "LVN", "BOT", "SWE", "DEN", "HEL", "IRI", "NTF"]:
            provinces[province_name] = Province(
                name=province_name,
                province_type="land" if province_name in ["PAR", "MAR", "BER", "MUN", "LON", "BUR", "BEL", "HOL", "LVN", "BOT", "SWE", "DEN", "IRI"] else "sea",
                is_supply_center=province_name in ["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "LON", "NTH", "ENG"],
                is_home_supply_center=False,
                adjacent_provinces=[]
            )
        
        map_data = MapData(
            map_name="standard",
            provinces=provinces,
            supply_centers=["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "LON", "NTH", "ENG"],
            home_supply_centers={},
            starting_positions={}
        )
        
        # Convert powers and units
        powers = {}
        new_orders = {}
        
        # Handle both list and dict formats for powers
        powers_data = game_state.get('powers', {})
        if isinstance(powers_data, list):
            # Convert list to dict format
            powers_dict = {}
            for power_name in powers_data:
                # Get power data from game state
                power_units = []
                for unit_str in game_state.get('units', {}).get(power_name, []):
                    if ' ' in unit_str:
                        unit_type, province = unit_str.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
                
                powers_dict[power_name] = {
                    'units': power_units,
                    'supply_centers': game_state.get('supply_centers', {}).get(power_name, [])
                }
            powers_data = powers_dict
        
        for power_name, power_data in powers_data.items():
            # Create units
            power_units = []
            if isinstance(power_data, dict):
                for unit_str in power_data.get('units', []):
                    if ' ' in unit_str:
                        unit_type, province = unit_str.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
            elif isinstance(power_data, list):
                for unit_str in power_data:
                    if ' ' in unit_str:
                        unit_type, province = unit_str.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
            
            # Create power state
            power_state = PowerState(
                power_name=power_name,
                units=power_units,
                controlled_supply_centers=power_data.get('supply_centers', []) if isinstance(power_data, dict) else []
            )
            powers[power_name] = power_state
            
            # Convert orders
            power_orders = []
            for order_text in orders.get(power_name, []):
                try:
                    print(f"DEBUG: Parsing order '{order_text}' for power '{power_name}' with {len(power_units)} units")
                    order = _parse_order_to_new_model(order_text, power_name, power_units)
                    if order:
                        power_orders.append(order)
                except Exception as e:
                    print(f"Error parsing order '{order_text}': {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            new_orders[power_name] = power_orders
        
        # Create new game state
        new_game_state = GameState(
            game_id=str(game_state.get('game_id', 'demo')),
            map_name="standard",
            current_turn=game_state.get('turn', 1),
            current_year=game_state.get('year', 1901),
            current_season=game_state.get('season', 'Spring'),
            current_phase=game_state.get('phase', 'Movement'),
            phase_code=game_state.get('phase_code', 'S1901M'),
            status="active",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers=powers,
            map_data=map_data,
            orders=new_orders
        )
        
        return new_game_state
    
    def _parse_order_to_new_model(order_text: str, power_name: str, power_units: list):
        """Parse order text to new order model"""
        from engine.data_models import OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder
        
        try:
            parts = order_text.split()
            if len(parts) < 2:
                return None
            
            # Skip the power name if present (e.g., "GERMANY A BER - HOL" -> "A BER - HOL")
            if len(parts) > 2 and parts[1] in ['A', 'F']:
                # Power name is first, skip it
                parts = parts[1:]
            elif len(parts) > 1 and parts[0] in ['A', 'F']:
                # No power name, use as is
                pass
            else:
                return None
            
            unit_str = f"{parts[0]} {parts[1]}"  # e.g., "A PAR"
            
            # Find the unit in power_units
            unit = None
            for u in power_units:
                if hasattr(u, 'unit_type') and hasattr(u, 'province'):
                    if f"{u.unit_type} {u.province}" == unit_str:
                        unit = u
                        break
                elif isinstance(u, str) and u == unit_str:
                    # Handle case where power_units contains strings
                    unit = Unit(unit_type=parts[0], province=parts[1], power=power_name)
                    break
            
            if not unit:
                print(f"Warning: Unit {unit_str} not found for power {power_name}")
                return None
            
            # Move order (A PAR - BUR)
            if len(parts) >= 4 and parts[2] == "-":
                return MoveOrder(
                    power=power_name,
                    unit=unit,
                    order_type=OrderType.MOVE,
                    phase="Movement",
                    target_province=parts[3],
                    status=OrderStatus.SUCCESS
                )
            
            # Hold order (A PAR H or A PAR)
            elif len(parts) == 2 or (len(parts) == 3 and parts[2] == "H"):
                return HoldOrder(
                    power=power_name,
                    unit=unit,
                    order_type=OrderType.HOLD,
                    phase="Movement",
                    status=OrderStatus.SUCCESS
                )
            
            return None
            
        except Exception as e:
            print(f"Error parsing order '{order_text}': {e}")
            return None
    
    # Test the conversion
    try:
        new_game_state = _convert_to_new_data_model(game_state, orders)
        print("✅ Data conversion successful!")
        
        # Test order visualization service
        viz_service = OrderVisualizationService()
        viz_data = viz_service.create_visualization_data(new_game_state)
        print("✅ Order visualization successful!")
        
        print(f"Generated visualization data for {len(viz_data)} powers")
        for power, orders_list in viz_data.items():
            print(f"  {power}: {len(orders_list)} orders")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run the test"""
    print("🚀 Testing demo game data conversion...\n")
    test_demo_conversion()


if __name__ == "__main__":
    main()
