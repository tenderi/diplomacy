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
            
            # Get units dictionary
            units = game_state.get('units', {})
            
            # Convert orders to visualization format
            orders_vis = {}
            for power, power_orders in orders.items():
                if power_orders:
                    orders_vis[power] = []
                    for order_text in power_orders:
                        # Parse order text to extract order details
                        order_data = self._parse_order_text(order_text)
                        if order_data:
                            orders_vis[power].append(order_data)
            
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
            
            # Get units dictionary
            units = game_state.get('units', {})
            
            # Convert orders to moves format showing resolution
            moves_vis = {}
            for power, power_orders in orders.items():
                if power_orders:
                    moves_vis[power] = {
                        "successful": [],
                        "failed": [],
                        "bounced": [],
                        "holds": [],
                        "supports": [],
                        "convoys": [],
                        "builds": [],
                        "destroys": []
                    }
                    
                    for order_text in power_orders:
                        # For demo purposes, assume most orders succeed
                        # In a real implementation, this would come from the game engine
                        order_data = self._parse_order_text(order_text)
                        if order_data:
                            order_type = order_data.get("type", "move")
                            
                            if order_type == "move":
                                # Simulate some orders failing for demonstration
                                if "BER" in order_text or "MUN" in order_text:
                                    moves_vis[power]["failed"].append(order_text)
                                elif "KIE" in order_text:
                                    moves_vis[power]["bounced"].append(order_text)
                                else:
                                    moves_vis[power]["successful"].append(order_text)
                            elif order_type == "hold":
                                moves_vis[power]["holds"].append(order_text)
                            elif order_type == "support":
                                moves_vis[power]["supports"].append(order_text)
                            elif order_type == "convoy":
                                moves_vis[power]["convoys"].append(order_text)
                            elif order_type == "build":
                                moves_vis[power]["builds"].append(order_text)
                            elif order_type == "destroy":
                                moves_vis[power]["destroys"].append(order_text)
            
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
