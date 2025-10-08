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
        
    def print_phase_info(self, game_state):
        """Print current phase information"""
        if not game_state:
            print(f"\n📊 PHASE INFO: No game state available")
            return
            
        print(f"\n📊 PHASE INFO:")
        print(f"   Turn: {game_state.current_turn}")
        print(f"   Season: {game_state.current_season}")
        print(f"   Phase: {game_state.current_phase}")
        print(f"   Phase Code: {game_state.phase_code}")
        
    def print_units(self, game_state):
        """Print current unit positions"""
        if not game_state:
            print(f"\n🏰 UNIT POSITIONS: No game state available")
            return
            
        print(f"\n🏰 UNIT POSITIONS:")
        
        for power_name, power_state in game_state.powers.items():
            unit_strs = [f"{u.unit_type} {u.province}" for u in power_state.units]
            if unit_strs:
                print(f"   {power_name}: {', '.join(sorted(unit_strs))}")
            else:
                print(f"   {power_name}: No units")
                
    def print_orders(self, game_state):
        """Print current orders"""
        if not game_state:
            print(f"\n📋 CURRENT ORDERS: No game state available")
            return
            
        print(f"\n📋 CURRENT ORDERS:")
        for power_name, orders in game_state.orders.items():
            if orders:
                order_strs = [str(order) for order in orders]
                print(f"   {power_name}: {', '.join(order_strs)}")
            else:
                print(f"   {power_name}: No orders")
                
    def generate_and_save_map(self, game_state, filename: str):
        """Generate and save a map for the current game state"""
        try:
            # game_state is now a GameState object directly
            if not game_state:
                print(f"❌ No game state available for map: {filename}")
                return
                
            # Convert units to dictionary format for map rendering
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
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
    
    def generate_orders_map(self, game_state, orders: dict, filename: str):
        """Generate map showing submitted orders (before processing)"""
        try:
            from src.engine.map import Map
            from src.engine.order_visualization import OrderVisualizationService
            
            # game_state is now a GameState object directly
            if not game_state:
                print(f"❌ No game state available for orders map: {filename}")
                return
            
            # Use new order visualization service
            viz_service = OrderVisualizationService()
            orders_vis = viz_service.create_visualization_data(game_state)
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
            }
            
            # Convert units to dictionary format for map rendering
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
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
    
    def generate_resolution_map(self, game_state, orders: dict, filename: str):
        """Generate map showing movement resolution (after processing)"""
        try:
            from src.engine.map import Map
            from src.engine.order_visualization import OrderVisualizationService
            
            # game_state is now a GameState object directly
            if not game_state:
                print(f"❌ No game state available for resolution map: {filename}")
                return
            
            # Use new order visualization service for moves format
            viz_service = OrderVisualizationService()
            moves_vis = viz_service.create_moves_visualization_data(game_state)
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
            }
            
            # Convert units to dictionary format for map rendering
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
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
        
    def get_game_state(self):
        """Get current game state using new data model"""
        try:
            result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
            if result.get("status") == "ok":
                return result.get("state")  # This is now a GameState object
            else:
                print(f"❌ Failed to get game state: {result.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"❌ Error getting game state: {e}")
            return None
            
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
            
    def get_spring_1901_builds(self, game_state) -> Dict[str, List[str]]:
        """Get builds for Spring 1901 Builds phase"""
        builds = {}
        
        # game_state is now a GameState object directly
        if not game_state:
            return builds
        
        for power_name, power_state in game_state.powers.items():
            power_builds = []
            
            # Check if this power needs builds (simplified logic)
            # In a real game, this would check supply centers vs units
            unit_count = len(power_state.units)
            supply_center_count = len(power_state.controlled_supply_centers)
            
            if unit_count < supply_center_count:
                # Need to build units (simplified - just build armies)
                needed_builds = supply_center_count - unit_count
                for i in range(needed_builds):
                    # Find a home supply center to build in
                    home_centers = power_state.home_supply_centers
                    if home_centers:
                        build_province = home_centers[0]  # Use first available home center
                        power_builds.append(f"{power_name} BUILD A {build_province}")
            
            if power_builds:
                builds[power_name] = power_builds
            else:
                builds[power_name] = []  # No builds needed
        
        return builds

    def generate_dynamic_orders(self, game_state) -> Dict[str, List[str]]:
        """Generate comprehensive orders to demonstrate all Diplomacy mechanics"""
        orders = {}
        
        if not game_state:
            return orders
            
        current_phase = game_state.current_phase
        current_year = game_state.current_year
        current_season = game_state.current_season
        
        print(f"   Generating orders for {current_season} {current_year} {current_phase} phase")
        
        if current_phase == 'Movement':
            orders = self._generate_movement_orders(game_state)
        elif current_phase == 'Retreat':
            orders = self._generate_retreat_orders(game_state)
        elif current_phase == 'Builds':
            orders = self._generate_build_orders(game_state)
        else:
            print(f"   Unknown phase: {current_phase}")
        
        return orders
    
    def _generate_movement_orders(self, game_state) -> Dict[str, List[str]]:
        """Generate movement orders to demonstrate various mechanics"""
        orders = {}
        current_year = game_state.current_year
        current_season = game_state.current_season
        
        # Strategic scenarios based on game progression
        if current_year == 1901 and current_season == 'Spring':
            orders = self._spring_1901_scenario(game_state)
        elif current_year == 1901 and current_season == 'Autumn':
            orders = self._autumn_1901_scenario(game_state)
        elif current_year == 1902 and current_season == 'Spring':
            orders = self._spring_1902_scenario(game_state)
        elif current_year == 1902 and current_season == 'Autumn':
            orders = self._autumn_1902_scenario(game_state)
        else:
            # Default strategic orders for later years
            orders = self._default_strategic_orders(game_state)
        
        return orders
    
    def _spring_1901_scenario(self, game_state) -> Dict[str, List[str]]:
        """Spring 1901: Basic expansion moves"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                if power_name == 'FRANCE':
                    if unit.province == 'PAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BUR")
                    elif unit.province == 'MAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - SPA")
                    elif unit.province == 'BRE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - MAO")
                
                elif power_name == 'GERMANY':
                    if unit.province == 'BER':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - SIL")
                    elif unit.province == 'MUN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - TYR")
                    elif unit.province == 'KIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - DEN")
                
                elif power_name == 'ENGLAND':
                    if unit.province == 'LON':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ENG")
                    elif unit.province == 'EDI':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - NTH")
                    elif unit.province == 'LVP':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - WAL")
                
                elif power_name == 'RUSSIA':
                    if unit.province == 'MOS':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - UKR")
                    elif unit.province == 'WAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - GAL")
                    elif unit.province == 'STP':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - FIN")
                    elif unit.province == 'SEV':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - RUM")
                
                elif power_name == 'ITALY':
                    if unit.province == 'ROM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - TUS")
                    elif unit.province == 'VEN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - TYR")
                    elif unit.province == 'NAP':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - TYS")
                
                elif power_name == 'AUSTRIA':
                    if unit.province == 'VIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - TYR")
                    elif unit.province == 'BUD':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - GAL")
                    elif unit.province == 'TRI':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ADR")
                
                elif power_name == 'TURKEY':
                    if unit.province == 'CON':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BUL")
                    elif unit.province == 'SMY':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ARM")
                    elif unit.province == 'ANK':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BLA")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _autumn_1901_scenario(self, game_state) -> Dict[str, List[str]]:
        """Autumn 1901: Demonstrate support orders and conflicts"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                if power_name == 'FRANCE':
                    if unit.province == 'BUR':
                        # Support Paris to attack Belgium
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} S A PAR - BEL")
                    elif unit.province == 'PAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BEL")
                    elif unit.province == 'SPA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'MAO':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - POR")
                
                elif power_name == 'GERMANY':
                    if unit.province == 'SIL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BOH")
                    elif unit.province == 'TYR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - VIE")
                    elif unit.province == 'DEN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - SWE")
                
                elif power_name == 'ENGLAND':
                    if unit.province == 'ENG':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BEL")
                    elif unit.province == 'NTH':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} S F ENG - BEL")
                    elif unit.province == 'WAL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'RUSSIA':
                    if unit.province == 'UKR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - RUM")
                    elif unit.province == 'GAL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BUD")
                    elif unit.province == 'FIN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'RUM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BUL")
                
                elif power_name == 'ITALY':
                    if unit.province == 'TUS':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - PIE")
                    elif unit.province == 'TYR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - VIE")
                    elif unit.province == 'TYS':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ION")
                
                elif power_name == 'AUSTRIA':
                    if unit.province == 'TYR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'GAL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - WAR")
                    elif unit.province == 'ADR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ION")
                
                elif power_name == 'TURKEY':
                    if unit.province == 'BUL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - RUM")
                    elif unit.province == 'ARM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BLA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - RUM")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _spring_1902_scenario(self, game_state) -> Dict[str, List[str]]:
        """Spring 1902: Demonstrate convoy orders"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                if power_name == 'ENGLAND':
                    if unit.province == 'BEL':
                        # Convoy army to Denmark
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - DEN VIA CONVOY")
                    elif unit.province == 'ENG':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} C A BEL - DEN")
                    elif unit.province == 'NTH':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} C A BEL - DEN")
                    elif unit.province == 'WAL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'FRANCE':
                    if unit.province == 'BEL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BUR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - RUE")
                    elif unit.province == 'SPA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'POR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'GERMANY':
                    if unit.province == 'BOH':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - MUN")
                    elif unit.province == 'VIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'SWE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'RUSSIA':
                    if unit.province == 'RUM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BUD':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'FIN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BUL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'ITALY':
                    if unit.province == 'PIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - MAR")
                    elif unit.province == 'VIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ION':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - ADR")
                
                elif power_name == 'AUSTRIA':
                    if unit.province == 'TYR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'WAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ADR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'TURKEY':
                    if unit.province == 'RUM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ARM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BLA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _autumn_1902_scenario(self, game_state) -> Dict[str, List[str]]:
        """Autumn 1902: Demonstrate complex conflicts and support cuts"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                if power_name == 'ENGLAND':
                    if unit.province == 'DEN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ENG':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - BEL")
                    elif unit.province == 'NTH':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} S F ENG - BEL")
                    elif unit.province == 'WAL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'FRANCE':
                    if unit.province == 'BEL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'RUE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} S A BEL")
                    elif unit.province == 'SPA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'POR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'GERMANY':
                    if unit.province == 'MUN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'VIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'SWE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'RUSSIA':
                    if unit.province == 'RUM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BUD':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'FIN':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BUL':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'ITALY':
                    if unit.province == 'MAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'VIE':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ADR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'AUSTRIA':
                    if unit.province == 'TYR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'WAR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ADR':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                
                elif power_name == 'TURKEY':
                    if unit.province == 'RUM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'ARM':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    elif unit.province == 'BLA':
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _default_strategic_orders(self, game_state) -> Dict[str, List[str]]:
        """Default strategic orders for later years"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                # Generate strategic orders based on current positions
                adjacent_province = self._get_adjacent_province(unit.province, unit.unit_type)
                if adjacent_province:
                    # 30% chance to hold, 70% chance to move
                    import random
                    if random.random() < 0.3:
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
                    else:
                        power_orders.append(f"{power_name} {unit.unit_type} {unit.province} - {adjacent_province}")
                else:
                    power_orders.append(f"{power_name} {unit.unit_type} {unit.province} H")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _generate_retreat_orders(self, game_state) -> Dict[str, List[str]]:
        """Generate retreat orders for dislodged units"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            for unit in power_state.units:
                if hasattr(unit, 'retreat_options') and unit.retreat_options:
                    # Choose first available retreat option
                    retreat_province = unit.retreat_options[0]
                    power_orders.append(f"{power_name} {unit.unit_type} {unit.province} R {retreat_province}")
                elif hasattr(unit, 'is_dislodged') and unit.is_dislodged:
                    # If no retreat options, disband
                    power_orders.append(f"{power_name} {unit.unit_type} {unit.province} D")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _generate_build_orders(self, game_state) -> Dict[str, List[str]]:
        """Generate build orders based on supply center control"""
        orders = {}
        
        for power_name, power_state in game_state.powers.items():
            power_orders = []
            
            # Check if power needs to build or destroy units
            supply_centers = power_state.controlled_supply_centers
            unit_count = len(power_state.units)
            
            if unit_count < len(supply_centers):
                # Need to build units
                builds_needed = len(supply_centers) - unit_count
                home_centers = [sc for sc in supply_centers if sc in self._get_home_supply_centers(power_name)]
                
                for i in range(min(builds_needed, len(home_centers))):
                    home_center = home_centers[i]
                    # Determine unit type based on province type
                    if self._is_coastal_province(home_center):
                        # Randomly choose army or fleet for coastal provinces
                        import random
                        unit_type = 'A' if random.random() < 0.5 else 'F'
                    else:
                        unit_type = 'A'  # Land provinces get armies
                    
                    power_orders.append(f"{power_name} BUILD {unit_type} {home_center}")
            
            elif unit_count > len(supply_centers):
                # Need to destroy units
                destroys_needed = unit_count - len(supply_centers)
                for i in range(destroys_needed):
                    if i < len(power_state.units):
                        unit = power_state.units[i]
                        power_orders.append(f"{power_name} DESTROY {unit.unit_type} {unit.province}")
            
            if power_orders:
                orders[power_name] = power_orders
        
        return orders
    
    def _get_home_supply_centers(self, power_name: str) -> List[str]:
        """Get home supply centers for a power"""
        home_centers = {
            'FRANCE': ['PAR', 'MAR', 'BRE'],
            'GERMANY': ['BER', 'MUN', 'KIE'],
            'ENGLAND': ['LON', 'EDI', 'LVP'],
            'RUSSIA': ['MOS', 'WAR', 'STP', 'SEV'],
            'ITALY': ['ROM', 'VEN', 'NAP'],
            'AUSTRIA': ['VIE', 'BUD', 'TRI'],
            'TURKEY': ['CON', 'SMY', 'ANK']
        }
        return home_centers.get(power_name, [])
    
    def _is_coastal_province(self, province: str) -> bool:
        """Check if a province is coastal"""
        coastal_provinces = {
            'BRE', 'BUL', 'CLY', 'CON', 'DEN', 'EDI', 'FIN', 'GAS', 'GRE', 'HOL', 
            'KIE', 'LON', 'LVP', 'LVN', 'MAR', 'NAP', 'NWY', 'PAR', 'PIC', 'PIE', 
            'POR', 'PRU', 'ROM', 'RUH', 'SMY', 'SPA', 'STP', 'SWE', 'TRI', 'TUN', 'VEN', 'YOR'
        }
        return province in coastal_provinces
    
    def _get_adjacent_province(self, province: str, unit_type: str) -> str:
        """Get an adjacent province for movement using the actual game engine's adjacency data"""
        try:
            # Get the actual game state to use real adjacency data
            game_state = self.get_game_state()
            if not game_state:
                return None
                
            # Get map data from game state
            map_data = game_state.map_data
            if not map_data or province not in map_data.provinces:
                return None
                
            # Get the province data
            province_data = map_data.provinces[province]
            adjacent_provinces = province_data.adjacent_provinces
            
            if not adjacent_provinces:
                return None
            
            # Find a legal move from the actual adjacent provinces
            for target_province in adjacent_provinces:
                if target_province in map_data.provinces:
                    target_province_data = map_data.provinces[target_province]
                    
                    # Check if move is legal based on unit type and target province type
                    if unit_type == 'A' and target_province_data.province_type in ['land', 'coastal']:
                        # Army can move to land or coastal provinces
                        return target_province
                    elif unit_type == 'F' and target_province_data.province_type in ['sea', 'coastal']:
                        # Fleet can move to sea or coastal provinces
                        return target_province
            
            # If no legal move found, return None
            return None
            
        except Exception as e:
            print(f"Error getting adjacent province for {province}: {e}")
            return None

    def get_autumn_1901_orders(self) -> Dict[str, List[str]]:
        """Get orders for Autumn 1901 Movement phase - DEPRECATED, use generate_dynamic_orders instead"""
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
        
    def get_build_orders(self, game_state) -> Dict[str, List[str]]:
        """Get build orders based on current game state"""
        # Simple build logic - add units in home supply centers
        builds = {
            "GERMANY": ["BUILD A BER"],
            "FRANCE": ["BUILD A PAR"],
            "ENGLAND": ["BUILD A LON"],
            "RUSSIA": ["BUILD A MOS"]
        }
        
        # game_state is now a GameState object directly
        if not game_state:
            return builds
        
        # Remove builds for powers that don't have supply center advantage
        for power_name, power_state in game_state.powers.items():
            power_units = len(power_state.units)
            supply_centers = len(power_state.controlled_supply_centers)
            
            if power_units >= supply_centers:
                builds[power_name] = []  # No builds needed
                
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
        orders = self.generate_dynamic_orders(game_state)
        
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
        
        # Spring 1901 Builds Phase
        self.print_header("SPRING 1901 BUILDS")
        builds = self.generate_dynamic_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_builds in builds.items():
            if power_builds:
                print(f"   /orders {self.game_id} {power} {' '.join(power_builds)}")
                self.submit_orders(power, power_builds)
            else:
                print(f"   {power}: No builds needed")
        
        time.sleep(1)
        
        # Process builds
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Phase 2: Autumn 1901 Movement
        self.print_header("PHASE 2: AUTUMN 1901 MOVEMENT")
        game_state = self.get_game_state()  # Get fresh game state
        orders = self.generate_dynamic_orders(game_state)
        
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
        build_orders = self.generate_dynamic_orders(game_state)
        
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
        game_state = self.get_game_state()  # Get fresh game state
        orders = self.generate_dynamic_orders(game_state)
        
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
        print(f"📊 Final Turn: {game_state.current_turn}")
        print(f"📅 Final Season: {game_state.current_season}")
        print(f"🔄 Final Phase: {game_state.current_phase}")
        print(f"🏷️  Final Phase Code: {game_state.phase_code}")
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
