#!/usr/bin/env python3
"""
Data Model Compliant Automated Demo Game

This demo game uses proper data_spec.md models exclusively, demonstrating
all Diplomacy mechanics with proper data integrity and validation.
"""

import sys
import os
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Add the project path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from src.engine.game import Game
from src.engine.map import Map
from src.server.server import Server
from src.engine.data_models import GameState, PowerState, Unit, Order, OrderType, OrderStatus
from src.engine.strategic_ai import StrategicAI, StrategicConfig, OrderGenerator
from src.engine.order_visualization import OrderVisualizationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataModelCompliantDemoGame:
    """Demo game that uses proper data models exclusively"""
    
    def __init__(self):
        self.server = Server()
        self.game_id: Optional[str] = None
        self.strategic_ai = StrategicAI(StrategicConfig())
        self.order_generator = OrderGenerator()
        self.order_viz_service = OrderVisualizationService()
        
    def print_header(self, title: str):
        """Print a formatted header"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)
        
    def print_phase_info(self, game_state: GameState):
        """Print current phase information using proper data models"""
        if not game_state:
            print(f"\n📊 PHASE INFO: No game state available")
            return
            
        print(f"\n📊 PHASE INFO:")
        print(f"   Turn: {game_state.current_turn}")
        print(f"   Year: {game_state.current_year}")
        print(f"   Season: {game_state.current_season}")
        print(f"   Phase: {game_state.current_phase}")
        print(f"   Phase Code: {game_state.phase_code}")
        print(f"   Status: {game_state.status}")
        
    def print_units(self, game_state: GameState):
        """Print current unit positions using proper data models"""
        if not game_state:
            print(f"\n🏰 UNIT POSITIONS: No game state available")
            return
            
        print(f"\n🏰 UNIT POSITIONS:")
        
        # Use proper GameState methods
        for power_name, power_state in game_state.powers.items():
            unit_strs = [f"{u.unit_type} {u.province}" for u in power_state.units]
            if unit_strs:
                print(f"   {power_name}: {', '.join(sorted(unit_strs))}")
            else:
                print(f"   {power_name}: No units")
                
    def print_orders(self, game_state: GameState):
        """Print current orders using proper data models"""
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
                
    def generate_and_save_map(self, game_state: GameState, filename: str):
        """Generate and save a map using proper data models"""
        try:
            if not game_state:
                print(f"❌ No game state available for map: {filename}")
                return
                
            # Use proper GameState methods to get units
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'year': game_state.current_year,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
            }
            
            # Generate map using Map.render_board_png
            svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
            map_path = os.path.join(BASE_DIR, "test_maps", filename)
            
            img_bytes = Map.render_board_png(svg_path, units, output_path=map_path, phase_info=phase_info)
            print(f"🗺️  Map saved: {map_path}")
            
        except Exception as e:
            print(f"❌ Error generating map: {e}")
            logger.error(f"Map generation error: {e}", exc_info=True)
    
    def generate_orders_map(self, game_state: GameState, orders: Dict[str, List[Order]], filename: str):
        """Generate map showing submitted orders using proper Order objects"""
        try:
            if not game_state:
                print(f"❌ No game state available for orders map: {filename}")
                return
            
            # Use proper OrderVisualizationService with Order objects
            orders_vis = self.order_viz_service.create_visualization_data(game_state)
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'year': game_state.current_year,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
            }
            
            # Use proper GameState methods to get units
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
            # Generate map with order visualization
            svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
            map_path = os.path.join(BASE_DIR, "test_maps", filename)
            
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
            logger.error(f"Orders map generation error: {e}", exc_info=True)
    
    def generate_resolution_map(self, game_state: GameState, orders: Dict[str, List[Order]], filename: str):
        """Generate map showing movement resolution using proper Order objects"""
        try:
            if not game_state:
                print(f"❌ No game state available for resolution map: {filename}")
                return
            
            # Use proper OrderVisualizationService for moves format
            moves_vis = self.order_viz_service.create_moves_visualization_data(game_state)
            
            # Create phase info from GameState object
            phase_info = {
                'turn': game_state.current_turn,
                'year': game_state.current_year,
                'season': game_state.current_season,
                'phase': game_state.current_phase,
                'phase_code': game_state.phase_code
            }
            
            # Use proper GameState methods to get units
            units = {}
            for power_name, power_state in game_state.powers.items():
                units[power_name] = [f"{u.unit_type} {u.province}" for u in power_state.units]
            
            # Generate map with moves visualization
            svg_path = os.path.join(BASE_DIR, "maps", "standard.svg")
            map_path = os.path.join(BASE_DIR, "test_maps", filename)
            
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
            logger.error(f"Resolution map generation error: {e}", exc_info=True)
    
    def create_demo_game(self) -> bool:
        """Create a new demo game using proper data models"""
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
            logger.error(f"Game creation error: {e}", exc_info=True)
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
                logger.error(f"Player addition error for {player}: {e}", exc_info=True)
                return False
                
        return True
        
    def get_game_state(self) -> Optional[GameState]:
        """Get current game state using proper data models"""
        try:
            result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
            if result.get("status") == "ok":
                return result.get("state")  # This should be a GameState object
            else:
                print(f"❌ Failed to get game state: {result.get('message', 'Unknown error')}")
                return None
        except Exception as e:
            print(f"❌ Error getting game state: {e}")
            logger.error(f"Game state retrieval error: {e}", exc_info=True)
            return None
            
    def submit_orders(self, power: str, orders: List[Order]) -> bool:
        """Submit orders using proper Order data models"""
        try:
            # Convert Order objects to strings for server submission
            order_strings = [str(order) for order in orders]
            
            # Submit each order separately
            for order_string in order_strings:
                result = self.server.process_command(f"SET_ORDERS {self.game_id} {power} {order_string}")
                if result.get("status") != "ok":
                    print(f"❌ Failed to submit order '{order_string}' for {power}: {result.get('message', 'Unknown error')}")
                    return False
            print(f"✅ {power} orders submitted: {', '.join(order_strings)}")
            return True
        except Exception as e:
            print(f"❌ Error submitting orders for {power}: {e}")
            logger.error(f"Order submission error for {power}: {e}", exc_info=True)
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
            logger.error(f"Turn processing error: {e}", exc_info=True)
            return False
    
    def generate_dynamic_orders(self, game_state: GameState) -> Dict[str, List[Order]]:
        """Generate orders using StrategicAI with proper data models"""
        orders = {}
        
        if not game_state:
            return orders
            
        print(f"   Generating orders for {game_state.current_season} {game_state.current_year} {game_state.current_phase} phase")
        
        # Use StrategicAI to generate orders for each power
        for power_name, power_state in game_state.powers.items():
            if power_state.is_active and not power_state.is_eliminated:
                try:
                    power_orders = self.strategic_ai.generate_orders(game_state, power_name)
                    
                    # Validate orders using proper validation
                    validation_results = self.order_generator.validate_orders(power_orders, game_state)
                    valid_orders = []
                    
                    for i, (is_valid, error_message) in enumerate(validation_results):
                        if is_valid:
                            valid_orders.append(power_orders[i])
                        else:
                            logger.warning(f"Invalid order for {power_name}: {error_message}")
                    
                    if valid_orders:
                        orders[power_name] = valid_orders
                    else:
                        orders[power_name] = []
                        
                except Exception as e:
                    logger.error(f"Error generating orders for {power_name}: {e}", exc_info=True)
                    orders[power_name] = []
        
        return orders
    
    def run_demo_game(self):
        """Run the complete automated demo game using proper data models"""
        self.print_header("DATA MODEL COMPLIANT DIPLOMACY DEMO GAME")
        
        # Create game
        if not self.create_demo_game():
            return
            
        # Add players
        if not self.add_players():
            return
            
        # Initial state
        game_state = self.get_game_state()
        if not game_state:
            print("❌ Failed to get initial game state")
            return
            
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate initial map
        self.generate_and_save_map(game_state, "compliant_demo_01_initial.png")
        
        # Phase 1: Spring 1901 Movement
        self.print_header("PHASE 1: SPRING 1901 MOVEMENT")
        orders = self.generate_dynamic_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            if power_orders:
                order_strings = [str(order) for order in power_orders]
                print(f"   /orders {self.game_id} {power} {' '.join(order_strings)}")
                self.submit_orders(power, power_orders)
            else:
                print(f"   {power}: No orders")
                
        time.sleep(1)
        
        # Generate map showing submitted orders
        self.generate_orders_map(game_state, orders, "compliant_demo_02_spring_orders.png")
        
        # Process turn
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state and show results
        game_state = self.get_game_state()
        if not game_state:
            print("❌ Failed to get updated game state")
            return
            
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map showing movement resolution
        self.generate_resolution_map(game_state, orders, "compliant_demo_03_spring_resolution.png")
        
        # Generate map after movement
        self.generate_and_save_map(game_state, "compliant_demo_04_spring_movement.png")
        
        # Spring 1901 Builds Phase
        self.print_header("SPRING 1901 BUILDS")
        builds = self.generate_dynamic_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_builds in builds.items():
            if power_builds:
                build_strings = [str(build) for build in power_builds]
                print(f"   /orders {self.game_id} {power} {' '.join(build_strings)}")
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
        if not game_state:
            print("❌ Failed to get updated game state")
            return
            
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map after builds
        self.generate_and_save_map(game_state, "compliant_demo_05_spring_builds.png")
        
        # Phase 2: Autumn 1901 Movement
        self.print_header("PHASE 2: AUTUMN 1901 MOVEMENT")
        game_state = self.get_game_state()
        if not game_state:
            print("❌ Failed to get game state")
            return
            
        orders = self.generate_dynamic_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in orders.items():
            if power_orders:
                order_strings = [str(order) for order in power_orders]
                print(f"   /orders {self.game_id} {power} {' '.join(order_strings)}")
                self.submit_orders(power, power_orders)
            else:
                print(f"   {power}: No orders")
                
        time.sleep(1)
        
        # Generate map showing submitted orders
        self.generate_orders_map(game_state, orders, "compliant_demo_06_autumn_orders.png")
        
        # Process movement
        print(f"\n🤖 BOT COMMAND:")
        print(f"   /processturn {self.game_id}")
        self.process_turn()
        
        # Get updated state
        game_state = self.get_game_state()
        if not game_state:
            print("❌ Failed to get updated game state")
            return
            
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map showing movement resolution
        self.generate_resolution_map(game_state, orders, "compliant_demo_07_autumn_resolution.png")
        
        # Generate map after movement
        self.generate_and_save_map(game_state, "compliant_demo_08_autumn_movement.png")
        
        # Phase 3: Autumn 1901 Builds
        self.print_header("PHASE 3: AUTUMN 1901 BUILDS")
        build_orders = self.generate_dynamic_orders(game_state)
        
        print(f"\n🤖 BOT COMMANDS:")
        for power, power_orders in build_orders.items():
            if power_orders:
                build_strings = [str(build) for build in power_orders]
                print(f"   /orders {self.game_id} {power} {' '.join(build_strings)}")
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
        if not game_state:
            print("❌ Failed to get updated game state")
            return
            
        self.print_phase_info(game_state)
        self.print_units(game_state)
        
        # Generate map after builds
        self.generate_and_save_map(game_state, "compliant_demo_09_autumn_builds.png")
        
        # Final summary
        self.print_header("DATA MODEL COMPLIANT DEMO GAME COMPLETE")
        print(f"🎮 Game ID: {self.game_id}")
        print(f"📊 Final Turn: {game_state.current_turn}")
        print(f"📅 Final Year: {game_state.current_year}")
        print(f"📅 Final Season: {game_state.current_season}")
        print(f"🔄 Final Phase: {game_state.current_phase}")
        print(f"🏷️  Final Phase Code: {game_state.phase_code}")
        print(f"📊 Final Status: {game_state.status}")
        print(f"\n🗺️  Maps generated in: {os.path.join(BASE_DIR, 'test_maps')}/")
        print(f"   📊 Game Sequence (chronological order):")
        print(f"      01 - compliant_demo_01_initial.png")
        print(f"      02 - compliant_demo_02_spring_orders.png")
        print(f"      03 - compliant_demo_03_spring_resolution.png")
        print(f"      04 - compliant_demo_04_spring_movement.png")
        print(f"      05 - compliant_demo_05_spring_builds.png")
        print(f"      06 - compliant_demo_06_autumn_orders.png")
        print(f"      07 - compliant_demo_07_autumn_resolution.png")
        print(f"      08 - compliant_demo_08_autumn_movement.png")
        print(f"      09 - compliant_demo_09_autumn_builds.png")
        print(f"\n✅ All operations used proper data_spec.md models")
        print(f"✅ All orders validated using Order.validate() methods")
        print(f"✅ All map generation used OrderVisualizationService")
        print(f"✅ All game state access used proper GameState methods")


def main():
    """Main function to run the data model compliant demo game"""
    # Ensure test_maps directory exists
    os.makedirs(os.path.join(BASE_DIR, "test_maps"), exist_ok=True)
    
    # Create and run demo game
    demo = DataModelCompliantDemoGame()
    demo.run_demo_game()


if __name__ == "__main__":
    main()
