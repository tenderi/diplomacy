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
        players = ["GERMANY", "FRANCE", "ENGLAND", "RUSSIA"]
        
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
                "GERMANY A BER - SIL",
                "GERMANY A MUN - TYR", 
                "GERMANY F KIE - BAL"
            ],
            "FRANCE": [
                "FRANCE A PAR - BUR",
                "FRANCE A MAR - PIE",
                "FRANCE F BRE - ENG"
            ],
            "ENGLAND": [
                "ENGLAND A LVP - YOR",
                "ENGLAND F LON - NTH",
                "ENGLAND F EDI - NTH"
            ],
            "RUSSIA": [
                "RUSSIA A WAR - GAL",
                "RUSSIA A MOS - UKR",
                "RUSSIA F STP - BOT",
                "RUSSIA F SEV - BLA"
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
        
        # Generate initial map
        self.generate_and_save_map(game_state, "demo_initial.png")
        
        # Phase 1: Spring 1901 Movement
        self.print_header("PHASE 1: SPRING 1901 MOVEMENT")
        orders = self.get_spring_1901_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
            self.submit_orders(power, power_orders)
            
        time.sleep(1)  # Brief pause
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state and show results
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map after movement
        self.generate_and_save_map(game_state, "demo_spring_1901_movement.png")
        
        # Phase 2: Spring 1901 Builds
        self.print_header("PHASE 2: SPRING 1901 BUILDS")
        build_orders = self.get_build_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in build_orders.items():
            if power_orders:
                print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
                self.submit_orders(power, power_orders)
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
        
        # Generate map after builds
        self.generate_and_save_map(game_state, "demo_spring_1901_builds.png")
        
        # Phase 3: Autumn 1901 Movement
        self.print_header("PHASE 3: AUTUMN 1901 MOVEMENT")
        orders = self.get_autumn_1901_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
            self.submit_orders(power, power_orders)
            
        time.sleep(1)
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map after autumn movement
        self.generate_and_save_map(game_state, "demo_autumn_1901_movement.png")
        
        # Phase 4: Autumn 1901 Builds
        self.print_header("PHASE 4: AUTUMN 1901 BUILDS")
        build_orders = self.get_build_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in build_orders.items():
            if power_orders:
                print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
                self.submit_orders(power, power_orders)
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
        
        # Generate map after autumn builds
        self.generate_and_save_map(game_state, "demo_autumn_1901_builds.png")
        
        # Phase 5: Spring 1902 Movement
        self.print_header("PHASE 5: SPRING 1902 MOVEMENT")
        orders = self.get_spring_1902_orders()
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            print(f"   /orders {self.game_id} {power} {' '.join(power_orders)}")
            self.submit_orders(power, power_orders)
            
        time.sleep(1)
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get final state
        game_state = self.get_game_state()
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate final map
        self.generate_and_save_map(game_state, "demo_spring_1902_movement.png")
        
        # Final summary
        self.print_header("DEMO GAME COMPLETE")
        print(f"🎮 Game ID: {self.game_id}")
        print(f"📊 Final Turn: {game_state.get('turn', 0)}")
        print(f"📅 Final Season: {game_state.get('season', 'Spring')}")
        print(f"🔄 Final Phase: {game_state.get('phase', 'Movement')}")
        print(f"🏷️  Final Phase Code: {game_state.get('phase_code', 'S1902M')}")
        print(f"\n🗺️  Maps generated in: /home/helgejalonen/diplomacy/new_implementation/test_maps/")
        print(f"   - demo_initial.png")
        print(f"   - demo_spring_1901_movement.png")
        print(f"   - demo_spring_1901_builds.png")
        print(f"   - demo_autumn_1901_movement.png")
        print(f"   - demo_autumn_1901_builds.png")
        print(f"   - demo_spring_1902_movement.png")

def main():
    """Main function to run the automated demo game"""
    # Ensure test_maps directory exists
    os.makedirs("/home/helgejalonen/diplomacy/new_implementation/test_maps", exist_ok=True)
    
    # Create and run demo game
    demo = AutomatedDemoGame()
    demo.run_demo_game()

if __name__ == "__main__":
    main()
