#!/usr/bin/env python3
"""
Automated Demo Game - Plays a full Diplomacy game automatically
Shows bot commands, processes phases, and generates maps between phases.
"""

import sys
import os
import time
import requests
import json
from typing import Dict, List, Any

# Add the project path
sys.path.append('/home/helgejalonen/diplomacy/new_implementation')

from src.engine.game import Game
from src.engine.map import Map
from src.server.server import Server

class AutomatedDemoGame:
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.game_id = None
        self.phase_count = 0
        self.server = Server()
        
    def print_header(self, title: str):
        """Print a formatted header"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)
        
    def print_phase_info(self, game_state: Dict[str, Any]):
        """Print current phase information"""
        turn = game_state.get('turn', 0)
        season = game_state.get('season', 'Spring')
        phase = game_state.get('phase', 'Movement')
        phase_code = game_state.get('phase_code', 'S1901M')
        
        print(f"\n📊 PHASE INFO:")
        print(f"   Turn: {turn}")
        print(f"   Season: {season}")
        print(f"   Phase: {phase}")
        print(f"   Phase Code: {phase_code}")
        
    def print_units(self, game_state: Dict[str, Any]):
        """Print current unit positions"""
        powers = game_state.get('powers', [])
        units = game_state.get('units', {})
        print(f"\n🏰 UNIT POSITIONS:")
        
        if isinstance(powers, list):
            for power_name in powers:
                power_units = units.get(power_name, [])
                if power_units:
                    print(f"   {power_name}: {', '.join(sorted(power_units))}")
                else:
                    print(f"   {power_name}: No units")
        elif isinstance(powers, dict):
            for power, power_data in powers.items():
                power_units = power_data.get('units', [])
                if power_units:
                    print(f"   {power}: {', '.join(sorted(power_units))}")
                else:
                    print(f"   {power}: No units")
                
    def print_orders(self, game_state: Dict[str, Any]):
        """Print current orders"""
        orders = game_state.get('orders', {})
        print(f"\n📋 CURRENT ORDERS:")
        for power, power_orders in orders.items():
            if power_orders:
                print(f"   {power}: {', '.join(power_orders)}")
            else:
                print(f"   {power}: No orders")
                
    def generate_and_save_map(self, game_state: Dict[str, Any], filename: str):
        """Generate and save a map for the current game state"""
        try:
            # Get units dictionary directly from game state
            # The game state already has units in the correct format: {power_name: [unit_list]}
            units = game_state.get('units', {})
            
            # Create phase info
            phase_info = {
                'turn': game_state.get('turn', 0),
                'season': game_state.get('season', 'Spring'),
                'phase': game_state.get('phase', 'Movement'),
                'phase_code': game_state.get('phase_code', 'S1901M')
            }
            
            # Generate map using Map.render_board_png
            svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
            map_path = f"/home/helgejalonen/diplomacy/new_implementation/test_maps/{filename}"
            
            img_bytes = Map.render_board_png(svg_path, units, output_path=map_path, phase_info=phase_info)
            print(f"🗺️  Map saved: {map_path}")
            
        except Exception as e:
            print(f"❌ Error generating map: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_orders_map(self, game_state: dict, orders: dict, filename: str):
        """Generate map showing submitted orders (before processing)"""
        try:
            from src.engine.map import Map
            from src.engine.order_visualization import OrderVisualizationService
            from src.engine.data_models import GameState, PowerState, Unit, OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, MapData, Province
            
            # Get units dictionary
            units = game_state.get('units', {})
            
            # Convert old game state to new data model
            new_game_state = self._convert_to_new_data_model(game_state, orders)
            
            # Use new order visualization service
            viz_service = OrderVisualizationService()
            orders_vis = viz_service.create_visualization_data(new_game_state)
            
            # Create phase info
            phase_info = {
                'turn': game_state.get('turn', 0),
                'season': game_state.get('season', 'Spring'),
                'phase': game_state.get('phase', 'Movement'),
                'phase_code': game_state.get('phase_code', 'S1901M')
            }
            
            # Generate map with order visualization
            svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
            map_path = f"/home/helgejalonen/diplomacy/new_implementation/test_maps/{filename}"
            
            img_bytes = Map.render_board_png_with_orders(
                svg_path=svg_path,
                units=units,
                orders=orders_vis,
                phase_info=phase_info,
                output_path=map_path
            )
            print(f"🗺️  Orders map saved: {map_path}")
            
        except Exception as e:
            print(f"❌ Error generating orders map: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_resolution_map(self, game_state: dict, orders: dict, filename: str):
        """Generate map showing movement resolution (after processing)"""
        try:
            from src.engine.map import Map
            from src.engine.order_visualization import OrderVisualizationService
            
            # Get units dictionary
            units = game_state.get('units', {})
            
            # Convert old game state to new data model
            new_game_state = self._convert_to_new_data_model(game_state, orders)
            
            # Use new order visualization service for moves format
            viz_service = OrderVisualizationService()
            moves_vis = viz_service.create_moves_visualization_data(new_game_state)
            
            # Create phase info
            phase_info = {
                'turn': game_state.get('turn', 0),
                'season': game_state.get('season', 'Spring'),
                'phase': game_state.get('phase', 'Movement'),
                'phase_code': game_state.get('phase_code', 'S1901M')
            }
            
            # Generate map with moves visualization
            svg_path = "/home/helgejalonen/diplomacy/new_implementation/maps/standard.svg"
            map_path = f"/home/helgejalonen/diplomacy/new_implementation/test_maps/{filename}"
            
            img_bytes = Map.render_board_png_with_moves(
                svg_path=svg_path,
                units=units,
                moves=moves_vis,
                phase_info=phase_info,
                output_path=map_path
            )
            print(f"🗺️  Resolution map saved: {map_path}")
            
        except Exception as e:
            print(f"❌ Error generating resolution map: {e}")
            import traceback
            traceback.print_exc()
    
    def _convert_to_new_data_model(self, game_state: dict, orders: dict):
        """Convert old game state format to new data model"""
        from src.engine.data_models import GameState, PowerState, Unit, OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, MapData, Province
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
                for unit_item in game_state.get('units', {}).get(power_name, []):
                    if isinstance(unit_item, str) and ' ' in unit_item:
                        unit_type, province = unit_item.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
                    elif hasattr(unit_item, 'unit_type') and hasattr(unit_item, 'province'):
                        # Already a Unit object
                        power_units.append(unit_item)
                
                powers_dict[power_name] = {
                    'units': power_units,
                    'supply_centers': game_state.get('supply_centers', {}).get(power_name, [])
                }
            powers_data = powers_dict
        
        for power_name, power_data in powers_data.items():
            # Create units
            power_units = []
            if isinstance(power_data, dict):
                for unit_item in power_data.get('units', []):
                    if isinstance(unit_item, str) and ' ' in unit_item:
                        unit_type, province = unit_item.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
                    elif hasattr(unit_item, 'unit_type') and hasattr(unit_item, 'province'):
                        # Already a Unit object
                        power_units.append(unit_item)
            elif isinstance(power_data, list):
                for unit_item in power_data:
                    if isinstance(unit_item, str) and ' ' in unit_item:
                        unit_type, province = unit_item.split(' ', 1)
                        unit = Unit(unit_type=unit_type, province=province, power=power_name)
                        power_units.append(unit)
                    elif hasattr(unit_item, 'unit_type') and hasattr(unit_item, 'province'):
                        # Already a Unit object
                        power_units.append(unit_item)
            
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
                    order = self._parse_order_to_new_model(order_text, power_name, power_units)
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
    
    def _parse_order_to_new_model(self, order_text: str, power_name: str, power_units: list):
        """Parse order text to new order model"""
        from src.engine.data_models import OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder
        
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
            
            # Support order (A PAR S A BUR - MUN)
            elif len(parts) >= 5 and parts[2] == "S":
                # Find supported unit
                supported_unit_str = f"{parts[3]} {parts[4]}"
                supported_unit = None
                for u in power_units:
                    if hasattr(u, 'unit_type') and hasattr(u, 'province'):
                        if f"{u.unit_type} {u.province}" == supported_unit_str:
                            supported_unit = u
                            break
                    elif isinstance(u, str) and u == supported_unit_str:
                        # Handle case where power_units contains strings
                        supported_unit = Unit(unit_type=parts[3], province=parts[4], power=power_name)
                        break
                
                if supported_unit:
                    supported_target = parts[6] if len(parts) > 6 and parts[5] == "-" else None
                    return SupportOrder(
                        power=power_name,
                        unit=unit,
                        order_type=OrderType.SUPPORT,
                        phase="Movement",
                        supported_unit=supported_unit,
                        supported_action="move" if supported_target else "hold",
                        supported_target=supported_target,
                        status=OrderStatus.SUCCESS
                    )
            
            # Convoy order (F ENG C A PAR - HOL)
            elif len(parts) >= 6 and parts[2] == "C":
                # Find convoyed unit
                convoyed_unit_str = f"{parts[3]} {parts[4]}"
                convoyed_unit = None
                for u in power_units:
                    if hasattr(u, 'unit_type') and hasattr(u, 'province'):
                        if f"{u.unit_type} {u.province}" == convoyed_unit_str:
                            convoyed_unit = u
                            break
                    elif isinstance(u, str) and u == convoyed_unit_str:
                        # Handle case where power_units contains strings
                        convoyed_unit = Unit(unit_type=parts[3], province=parts[4], power=power_name)
                        break
                
                if convoyed_unit:
                    convoyed_target = parts[6] if len(parts) > 6 and parts[5] == "-" else None
                    return ConvoyOrder(
                        power=power_name,
                        unit=unit,
                        order_type=OrderType.CONVOY,
                        phase="Movement",
                        convoyed_unit=convoyed_unit,
                        convoyed_target=convoyed_target,
                        convoy_chain=[],
                        status=OrderStatus.SUCCESS
                    )
            
            return None
            
        except Exception as e:
            print(f"Error parsing order '{order_text}': {e}")
            return None

    def _parse_order_text(self, order_text: str) -> dict:
        """Parse order text into order dictionary format"""
        try:
            parts = order_text.split()
            if len(parts) < 3:
                return None
            
            # Skip the power name if present (e.g., "GERMANY A BER - HOL" -> "A BER - HOL")
            if len(parts) > 3 and parts[1] in ['A', 'F']:
                # Power name is first, skip it
                parts = parts[1:]
            elif len(parts) > 2 and parts[0] in ['A', 'F']:
                # No power name, use as is
                pass
            else:
                return None
                
            unit = f"{parts[0]} {parts[1]}"  # e.g., "A PAR"
            
            # Move order (A PAR - BUR)
            if len(parts) >= 4 and parts[2] == "-":
                return {
                    "type": "move",
                    "unit": unit,
                    "target": parts[3],
                    "status": "success"
                }
            
            # Hold order (A PAR H or A PAR)
            elif len(parts) == 2 or (len(parts) == 3 and parts[2] == "H"):
                return {
                    "type": "hold",
                    "unit": unit,
                    "status": "success"
                }
            
            # Support order (A PAR S A BUR - MUN)
            elif len(parts) >= 5 and parts[2] == "S":
                if len(parts) >= 6 and parts[4] == "-":
                    return {
                        "type": "support",
                        "unit": unit,
                        "supporting": f"{parts[3]} {parts[4]} {parts[5]}",
                        "status": "success"
                    }
                else:
                    return {
                        "type": "support",
                        "unit": unit,
                        "supporting": parts[3],
                        "status": "success"
                    }
            
            # Convoy order (F ENG C A PAR - HOL)
            elif len(parts) >= 6 and parts[2] == "C":
                return {
                    "type": "convoy",
                    "unit": unit,
                    "target": parts[5],
                    "via": [],
                    "status": "success"
                }
            
            # Build order (BUILD A PAR)
            elif parts[0] == "BUILD":
                return {
                    "type": "build",
                    "unit": "",
                    "target": parts[2],
                    "status": "success"
                }
            
            # Destroy order (DESTROY A PAR)
            elif parts[0] == "DESTROY":
                return {
                    "type": "destroy",
                    "unit": f"{parts[1]} {parts[2]}",
                    "status": "success"
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error parsing order '{order_text}': {e}")
            return None
            
    def create_demo_game(self) -> bool:
        """Create a new demo game"""
        try:
            result = self.server.process_command("CREATE_GAME standard")
            if result.get("status") == "ok":
                self.game_id = result.get("game_id")
                print(f"✅ Created demo game: {self.game_id}")
                return True
            else:
                print(f"❌ Failed to create game: {result.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error creating game: {e}")
            return False
            
    def add_players(self) -> bool:
        """Add players to the demo game"""
        players = ["GERMANY", "FRANCE", "ENGLAND", "RUSSIA", "ITALY", "AUSTRIA", "TURKEY"]
        
        for player in players:
            try:
                result = self.server.process_command(f"ADD_PLAYER {self.game_id} {player}")
                if result.get("status") == "ok":
                    print(f"✅ Added player: {player}")
                else:
                    print(f"❌ Failed to add player {player}: {result.get('message', 'Unknown error')}")
                    return False
            except Exception as e:
                print(f"❌ Error adding player {player}: {e}")
                return False
                
        return True
        
    def get_game_state(self) -> Dict[str, Any]:
        """Get current game state"""
        try:
            result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
            if result.get("status") == "ok":
                return result.get("state", {})
            else:
                print(f"❌ Failed to get game state: {result.get('message', 'Unknown error')}")
                return {}
        except Exception as e:
            print(f"❌ Error getting game state: {e}")
            return {}
            
    def submit_orders(self, power: str, orders: List[str]) -> bool:
        """Submit orders for a power"""
        try:
            # Submit each order separately
            for order in orders:
                result = self.server.process_command(f"SET_ORDERS {self.game_id} {power} {order}")
                if result.get("status") != "ok":
                    print(f"❌ Failed to submit order '{order}' for {power}: {result.get('message', 'Unknown error')}")
                    return False
            print(f"✅ {power} orders submitted: {', '.join(orders)}")
            return True
        except Exception as e:
            print(f"❌ Error submitting orders for {power}: {e}")
            return False
            
    def process_turn(self) -> bool:
        """Process the current turn/phase"""
        try:
            result = self.server.process_command(f"PROCESS_TURN {self.game_id}")
            if result.get("status") == "ok":
                print(f"✅ Turn processed successfully")
                return True
            else:
                print(f"❌ Failed to process turn: {result.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"❌ Error processing turn: {e}")
            return False
            
    def get_spring_1901_orders(self) -> Dict[str, List[str]]:
        """Get orders for Spring 1901 Movement phase"""
        return {
            "GERMANY": [
                "GERMANY A BER - HOL",
                "GERMANY A MUN - BUR", 
                "GERMANY F KIE - DEN"
            ],
            "FRANCE": [
                "FRANCE A PAR - BEL",
                "FRANCE A MAR - SPA",
                "FRANCE F BRE - MAO"
            ],
            "ENGLAND": [
                "ENGLAND A LVP H",
                "ENGLAND F LON H",
                "ENGLAND F EDI - NTH"
            ],
            "RUSSIA": [
                "RUSSIA A WAR H",
                "RUSSIA A MOS H",
                "RUSSIA F STP H",
                "RUSSIA F SEV - RUM"
            ],
            "ITALY": [
                "ITALY A ROM - TUS",
                "ITALY A VEN H",
                "ITALY F NAP - ION"
            ],
            "AUSTRIA": [
                "AUSTRIA A VIE - GAL",
                "AUSTRIA A BUD - SER",
                "AUSTRIA F TRI - ADR"
            ],
            "TURKEY": [
                "TURKEY A CON - BUL",
                "TURKEY A SMY H",
                "TURKEY F ANK - BLA"
            ]
        }
        
    def get_autumn_1901_orders(self) -> Dict[str, List[str]]:
        """Get orders for Autumn 1901 Movement phase"""
        return {
            "GERMANY": [
                "GERMANY A SIL - BOH",
                "GERMANY A TYR - VIE",
                "GERMANY F BAL - BOT"
            ],
            "FRANCE": [
                "FRANCE A BUR - BEL",
                "FRANCE A PIE - TUS",
                "FRANCE F ENG - IRI"
            ],
            "ENGLAND": [
                "ENGLAND A YOR - LON",
                "ENGLAND F NTH - HEL",
                "ENGLAND F NTH - DEN"
            ],
            "RUSSIA": [
                "RUSSIA A GAL - BUD",
                "RUSSIA A UKR - RUM",
                "RUSSIA F BOT - SWE",
                "RUSSIA F BLA - CON"
            ],
            "ITALY": [
                "ITALY A TUS - ROM",
                "ITALY A VEN H",
                "ITALY F ION - TUN"
            ],
            "AUSTRIA": [
                "AUSTRIA A GAL - BUD",
                "AUSTRIA A SER - GRE",
                "AUSTRIA F ADR - ION"
            ],
            "TURKEY": [
                "TURKEY A BUL - CON",
                "TURKEY A SMY H",
                "TURKEY F BLA - RUM"
            ]
        }
        
    def get_spring_1902_orders(self) -> Dict[str, List[str]]:
        """Get orders for Spring 1902 Movement phase"""
        return {
            "GERMANY": [
                "GERMANY A BOH - GAL",
                "GERMANY A VIE - BUD",
                "GERMANY F BOT - STP"
            ],
            "FRANCE": [
                "FRANCE A BEL - HOL",
                "FRANCE A TUS - ROM",
                "FRANCE F IRI - NAO"
            ],
            "ENGLAND": [
                "ENGLAND A LON - WAL",
                "ENGLAND F HEL - DEN",
                "ENGLAND F DEN - BAL"
            ],
            "RUSSIA": [
                "RUSSIA A BUD - SER",
                "RUSSIA A RUM - BUL",
                "RUSSIA F SWE - DEN",
                "RUSSIA F CON - AEG"
            ],
            "ITALY": [
                "ITALY A ROM - NAP",
                "ITALY A VEN H",
                "ITALY F TUN - TYS"
            ],
            "AUSTRIA": [
                "AUSTRIA A BUD - SER",
                "AUSTRIA A GRE - ALB",
                "AUSTRIA F ION - ADR"
            ],
            "TURKEY": [
                "TURKEY A CON - SMY",
                "TURKEY A SMY H",
                "TURKEY F RUM - BLA"
            ]
        }
        
    def get_build_orders(self, game_state: Dict[str, Any]) -> Dict[str, List[str]]:
        """Get build orders based on current game state"""
        # Simple build logic - add units in home supply centers
        builds = {
            "GERMANY": ["BUILD A BER"],
            "FRANCE": ["BUILD A PAR"],
            "ENGLAND": ["BUILD A LON"],
            "RUSSIA": ["BUILD A MOS"]
        }
        
        # Remove builds for powers that don't have supply center advantage
        powers = game_state.get('powers', [])
        units = game_state.get('units', {})
        
        if isinstance(powers, list):
            for power_name in powers:
                power_units = len(units.get(power_name, []))
                # For demo purposes, assume each power has 3 supply centers initially
                supply_centers = 3
                
                if power_units >= supply_centers:
                    builds[power_name] = []  # No builds needed
        elif isinstance(powers, dict):
            for power, power_data in powers.items():
                power_units = len(power_data.get('units', []))
                supply_centers = len(power_data.get('supply_centers', []))
                
                if power_units >= supply_centers:
                    builds[power] = []  # No builds needed
                
        return builds
        
    def run_demo_game(self):
        """Run the complete automated demo game"""
        self.print_header("AUTOMATED DIPLOMACY DEMO GAME")
        
        # Create game
        if not self.create_demo_game():
            return
            
        # Add players
        if not self.add_players():
            return
            
        # Initial state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate initial map (stable situation)
        self.generate_and_save_map(game_state, "demo_1901_01_initial.png")
        
        # Phase 1: Spring 1901 Movement
        self.print_header("PHASE 1: SPRING 1901 MOVEMENT")
        orders = self.get_spring_1901_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
            self.submit_orders(power, power_orders)
            
        time.sleep(1)  # Brief pause
        
        # Generate map showing submitted orders (before processing)
        self.generate_orders_map(game_state, orders, "demo_1901_02_spring_orders.png")
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state and show results
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map showing movement resolution (after processing)
        self.generate_resolution_map(game_state, orders, "demo_1901_03_spring_resolution.png")
        
        # Generate map after movement (stable situation)
        self.generate_and_save_map(game_state, "demo_1901_04_spring_movement.png")
        
        # Phase 2: Autumn 1901 Movement
        self.print_header("PHASE 2: AUTUMN 1901 MOVEMENT")
        orders = self.get_autumn_1901_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            if power_orders:
                print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
                self.submit_orders(power, power_orders)
            else:
                print(f"   {power}: No orders")
                
        time.sleep(1)
        
        # Generate map showing submitted orders (before processing)
        self.generate_orders_map(game_state, orders, "demo_1901_05_autumn_orders.png")
        
        # Process movement
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map showing movement resolution (after processing)
        self.generate_resolution_map(game_state, orders, "demo_1901_06_autumn_resolution.png")
        
        # Generate map after movement
        self.generate_and_save_map(game_state, "demo_1901_07_autumn_movement.png")
        
        # Phase 3: Autumn 1901 Builds
        self.print_header("PHASE 3: AUTUMN 1901 BUILDS")
        build_orders = self.get_build_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in build_orders.items():
            if power_orders:
                print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
                self.submit_orders(power, power_orders)
            else:
                print(f"   {power}: No builds needed")
            
        time.sleep(1)
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map after builds
        self.generate_and_save_map(game_state, "demo_1901_08_autumn_builds.png")
        
        # Phase 4: Spring 1902 Movement
        self.print_header("PHASE 4: SPRING 1902 MOVEMENT")
        orders = self.get_spring_1902_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
            self.submit_orders(power, power_orders)
            
        time.sleep(1)
        
        # Generate map showing submitted orders (before processing)
        self.generate_orders_map(game_state, orders, "demo_1902_09_spring_orders.png")
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get final state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map showing movement resolution (after processing)
        self.generate_resolution_map(game_state, orders, "demo_1902_10_spring_resolution.png")
        
        # Generate final map
        self.generate_and_save_map(game_state, "demo_1902_11_spring_movement.png")
        
        # Final summary
        self.print_header("DEMO GAME COMPLETE")
        print(f"🎮 Game ID: {self.game_id}")
        print(f"📊 Final Turn: {game_state.get('turn', 0)}")
        print(f"📅 Final Season: {game_state.get('season', 'Spring')}")
        print(f"🔄 Final Phase: {game_state.get('phase', 'Movement')}")
        print(f"🏷️  Final Phase Code: {game_state.get('phase_code', 'S1902M')}")
        print(f"\n🗺️  Maps generated in: /home/helgejalonen/diplomacy/new_implementation/test_maps/")
        print(f"   📊 Game Sequence (chronological order):")
        print(f"      01 - demo_1901_01_initial.png")
        print(f"      02 - demo_1901_02_spring_orders.png")
        print(f"      03 - demo_1901_03_spring_resolution.png")
        print(f"      04 - demo_1901_04_spring_movement.png")
        print(f"      05 - demo_1901_05_autumn_orders.png")
        print(f"      06 - demo_1901_06_autumn_resolution.png")
        print(f"      07 - demo_1901_07_autumn_movement.png")
        print(f"      08 - demo_1901_08_autumn_builds.png")
        print(f"      09 - demo_1902_09_spring_orders.png")
        print(f"      10 - demo_1902_10_spring_resolution.png")
        print(f"      11 - demo_1902_11_spring_movement.png")

def main():
    """Main function to run the automated demo game"""
    # Ensure test_maps directory exists
    os.makedirs("/home/helgejalonen/diplomacy/new_implementation/test_maps", exist_ok=True)
    
    # Create and run demo game
    demo = AutomatedDemoGame()
    demo.run_demo_game()

if __name__ == "__main__":
    main()
