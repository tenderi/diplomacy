#!/usr/bin/env python3
"""
Automated Demo Game for Diplomacy

This script runs a complete automated Diplomacy game simulation, demonstrating
all game mechanics, order types, and phases through a fully automated game.

Features:
- Complete game simulation from Spring 1901 onwards
- All seven powers (Austria, England, France, Germany, Italy, Russia, Turkey)
- Dynamic order generation based on strategic analysis
- Comprehensive map visualization at each phase
- Educational demonstration of all Diplomacy mechanics

Usage:
    python3 demo_automated_game.py

The script will:
1. Create a demo game
2. Add all seven powers
3. Play through multiple turns with strategic AI
4. Generate visual maps at each phase
5. Demonstrate all order types and game mechanics
"""

import os
import sys
import json
import time
import requests
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.server import Server
from engine.game import Game
from engine.data_models import GameState, PowerState, Unit, GameStatus
from engine.map import Map
from engine.order_parser import OrderParser


@dataclass
class DemoGameConfig:
    """Configuration for the automated demo game."""
    # Game settings
    MAP_NAME: str = "standard"
    MAX_TURNS: int = 20
    VICTORY_CONDITION: int = 18  # Supply centers needed for victory
    
    # AI behavior
    AGGRESSION_LEVEL: float = 0.7  # 0.0 = passive, 1.0 = aggressive
    ALLIANCE_TENDENCY: float = 0.5  # Tendency to form alliances
    EXPANSION_PRIORITY: float = 0.8  # Priority for expansion moves
    
    # Map generation
    MAP_RESOLUTION: Tuple[int, int] = (1920, 1080)
    SAVE_MAPS: bool = True
    MAP_FORMAT: str = "PNG"
    
    # Logging and output
    VERBOSE_OUTPUT: bool = True
    SAVE_GAME_STATE: bool = True
    GENERATE_REPORTS: bool = True


class AutomatedDemoGame:
    """Automated demo game that plays a complete Diplomacy game."""
    
    def __init__(self, config: Optional[DemoGameConfig] = None):
        self.config = config or DemoGameConfig()
        self.api_base = "http://localhost:8000"
        self.game_id: Optional[int] = None
        self.phase_count = 0
        self.server = Server()
        self.map = Map(self.config.MAP_NAME)
        self.order_parser = OrderParser()
        
        # Ensure test_maps directory exists
        self.maps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_maps")
        os.makedirs(self.maps_dir, exist_ok=True)
        
    def run_demo_game(self) -> None:
        """Run the complete automated demo game."""
        print("🎮 Starting Automated Diplomacy Demo Game")
        print("=" * 50)
        
        try:
            # Step 1: Create demo game
            if not self.create_demo_game():
                print("❌ Failed to create demo game")
                return
                
            # Step 2: Add all players
            if not self.add_players():
                print("❌ Failed to add players")
                return
                
            # Step 3: Play the game
            self.play_game()
            
            print("\n🎉 Demo game completed successfully!")
            print(f"📊 Generated {self.phase_count} phases")
            print(f"🗺️ Maps saved to: {self.maps_dir}/")
            
        except Exception as e:
            print(f"❌ Demo game failed: {e}")
            raise
    
    def create_demo_game(self) -> bool:
        """Create a new demo game instance."""
        print("🎯 Creating demo game...")
        
        try:
            # Create game using server process_command
            result = self.server.process_command(f"CREATE_GAME {self.config.MAP_NAME}")
            
            if result.get("status") == "ok":
                self.game_id = result["game_id"]
                print(f"✅ Demo game created with ID: {self.game_id}")
                return True
            else:
                print(f"❌ Failed to create game: {result}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to create game: {e}")
            return False
    
    def add_players(self) -> bool:
        """Add all seven powers to the game."""
        print("👥 Adding all seven powers...")
        
        powers = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"]
        
        for power in powers:
            try:
                # Add player to game using process_command
                result = self.server.process_command(f"ADD_PLAYER {self.game_id} {power}")
                if result.get("status") == "ok":
                    print(f"  ✅ Added {power}")
                else:
                    print(f"  ❌ Failed to add {power}: {result}")
                    return False
                    
            except Exception as e:
                print(f"  ❌ Error adding {power}: {e}")
                return False
        
        print("✅ All powers added successfully")
        return True
    
    def play_game(self) -> None:
        """Play the complete game with automated orders for 3 years."""
        print("🎲 Starting automated gameplay...")
        
        target_years = [1901, 1902, 1903]
        phases_per_year = ["Spring_Movement", "Spring_Builds", "Autumn_Movement", "Autumn_Builds"]
        
        phase_counter = 1
        
        for year in target_years:
            print(f"\n📅 Year {year}")
            print("=" * 40)
            
            for phase_name in phases_per_year:
                print(f"\n🎯 {phase_name.replace('_', ' ')} {year}")
                print("-" * 30)
                
                # Get current game state
                result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
                if result.get("status") != "ok":
                    print("❌ Failed to get game state")
                    return
                game_state = result.get("state")
                
                if not game_state:
                    print("❌ Failed to get game state")
                    return
                    
                # Check if game is completed
                if game_state.get('done', False):
                    print("🏆 Game completed!")
                    return
                
                # Generate and save initial map
                filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_initial"
                self.generate_and_save_map(game_state, filename)
                
                # Generate orders for all powers
                orders = self.generate_dynamic_orders(game_state, phase_name)
                
                if not orders:
                    print("❌ Failed to generate orders")
                    continue
                
                # Submit orders
                if not self.submit_orders(orders):
                    print("❌ Failed to submit orders")
                    continue
                
                # Generate orders map
                orders_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_orders"
                self.generate_orders_map(game_state, orders, orders_filename)
                
                # Process the phase
                if not self.process_phase():
                    print("❌ Failed to process phase")
                    continue
                
                # Get updated game state
                result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
                if result.get("status") == "ok":
                    updated_state = result.get("state")
                    if updated_state:
                        # Generate resolution map
                        resolution_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_resolution"
                        self.generate_resolution_map(updated_state, orders, resolution_filename)
                        
                        # Generate final map
                        final_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_final"
                        self.generate_and_save_map(updated_state, final_filename)
                        
                        # Display game state
                        self.display_game_state(updated_state)
                
                self.phase_count += 1
                phase_counter += 1
                
                # Small delay for readability
                time.sleep(0.5)
    
    def generate_dynamic_orders(self, game_state: Dict[str, Any], phase_name: str) -> Dict[str, List[str]]:
        """Generate realistic orders based on current game state and phase."""
        print(f"🧠 Generating orders for {phase_name.replace('_', ' ')} {game_state['year']}...")
        
        orders = {}
        
        # Get units for each power
        units = game_state.get('units', {})
        
        for power_name, power_units in units.items():
            if not power_units:  # Skip if no units
                continue
                
            power_orders = []
            
            # Determine if this is a Movement or Builds phase
            is_movement_phase = "Movement" in phase_name
            is_builds_phase = "Builds" in phase_name
            
            # Also check the actual game state phase to be sure
            actual_phase = game_state.get('phase', '').lower()
            if 'movement' in actual_phase or 'retreat' in actual_phase:
                is_movement_phase = True
                is_builds_phase = False
            elif 'build' in actual_phase or 'adjustment' in actual_phase:
                is_movement_phase = False
                is_builds_phase = True
            
            print(f"    Phase detection: {phase_name} -> Movement: {is_movement_phase}, Builds: {is_builds_phase}, Actual: {actual_phase}")
            
            if is_movement_phase:
                # Generate movement orders
                for unit_str in power_units:
                    # Parse unit string like "A PAR" or "F BRE"
                    parts = unit_str.split()
                    if len(parts) >= 2:
                        unit_type = parts[0]
                        province = parts[1]
                        
                        order = self.generate_movement_order(unit_type, province, power_name, game_state)
                        if order:
                            power_orders.append(order)
            
            elif is_builds_phase:
                # Generate build/disband orders
                power_orders = self.generate_build_orders(power_name, game_state)
            
            orders[power_name] = power_orders
            
            if power_orders:
                print(f"  {power_name}: {len(power_orders)} orders")
        
        return orders
    
    def generate_movement_order(self, unit_type: str, province: str, power_name: str, game_state: Dict[str, Any]) -> Optional[str]:
        """Generate a movement order for a specific unit."""
        try:
            # Get adjacent provinces
            adjacent = self.map.get_adjacency(province)
            
            if not adjacent:
                return f"{unit_type} {province} H"
            
            # Simple strategic AI for movement
            if self.should_expand_dict(unit_type, province, game_state):
                target = self.choose_expansion_target_dict(unit_type, province, adjacent, game_state)
                if target:
                    return f"{unit_type} {province} - {target}"
            
            if self.should_attack_dict(unit_type, province, game_state):
                target = self.choose_attack_target_dict(unit_type, province, adjacent, game_state)
                if target:
                    return f"{unit_type} {province} - {target}"
            
            # Default to hold
            return f"{unit_type} {province} H"
            
        except Exception as e:
            print(f"    ⚠️ Error generating movement order for {unit_type} {province}: {e}")
            return f"{unit_type} {province} H"
    
    def generate_build_orders(self, power_name: str, game_state: Dict[str, Any]) -> List[str]:
        """Generate build/disband orders for a power."""
        orders = []
        
        try:
            # Get power state - the powers data structure is different
            powers = game_state.get('powers', {})
            if isinstance(powers, dict) and power_name in powers:
                power_state = powers[power_name]
                if isinstance(power_state, dict):
                    # Get build options
                    build_options = power_state.get('builds', [])
                    
                    # Simple AI: build units if we have build options
                    if build_options:
                        # Take first few build options
                        for i, build_option in enumerate(build_options[:2]):  # Limit to 2 builds per phase
                            if build_option:
                                orders.append(f"BUILD {build_option}")
                    
                    # If no build options, we might need to disband
                    # For now, skip disbanding in demo
                    if not orders:
                        print(f"    {power_name}: No build orders (no build options)")
                else:
                    print(f"    {power_name}: Power state is not a dict: {type(power_state)}")
            else:
                print(f"    {power_name}: Power not found in powers dict")
            
        except Exception as e:
            print(f"    ⚠️ Error generating build orders for {power_name}: {e}")
        
        return orders
    
    def generate_unit_order_from_dict(self, unit_type: str, province: str, power_name: str, game_state: Dict[str, Any]) -> Optional[str]:
        """Generate an order for a specific unit from dictionary game state."""
        try:
            # Get adjacent provinces
            adjacent = self.map.get_adjacency(province)
            
            if not adjacent:
                return f"{unit_type} {province} H"
            
            # Simple strategic AI
            if self.should_expand_dict(unit_type, province, game_state):
                target = self.choose_expansion_target_dict(unit_type, province, adjacent, game_state)
                if target:
                    return f"{unit_type} {province} - {target}"
            
            if self.should_attack_dict(unit_type, province, game_state):
                target = self.choose_attack_target_dict(unit_type, province, adjacent, game_state)
                if target:
                    return f"{unit_type} {province} - {target}"
            
            # Default to hold
            return f"{unit_type} {province} H"
            
        except Exception as e:
            print(f"    ⚠️ Error generating order for {unit_type} {province}: {e}")
            return f"{unit_type} {province} H"
    
    def should_expand_dict(self, unit_type: str, province: str, game_state: Dict[str, Any]) -> bool:
        """Determine if a unit should try to expand."""
        # Simple heuristic: expand in early game
        return game_state['year'] <= 1902
    
    def should_attack_dict(self, unit_type: str, province: str, game_state: Dict[str, Any]) -> bool:
        """Determine if a unit should attack."""
        # Simple heuristic: attack in mid-late game
        return game_state['year'] >= 1903
    
    def choose_expansion_target_dict(self, unit_type: str, province: str, adjacent: List[str], game_state: Dict[str, Any]) -> Optional[str]:
        """Choose a target for expansion."""
        # Look for empty adjacent provinces
        for target_province in adjacent:
            if self.is_province_empty_dict(target_province, game_state):
                return target_province
        return None
    
    def choose_attack_target_dict(self, unit_type: str, province: str, adjacent: List[str], game_state: Dict[str, Any]) -> Optional[str]:
        """Choose a target for attack."""
        # Look for enemy units to attack
        for target_province in adjacent:
            if self.has_enemy_unit_dict(target_province, province, game_state):
                return target_province
        return None
    
    def is_province_empty_dict(self, province: str, game_state: Dict[str, Any]) -> bool:
        """Check if a province is empty."""
        units = game_state.get('units', {})
        for power_units in units.values():
            for unit_str in power_units:
                if province in unit_str:
                    return False
        return True
    
    def has_enemy_unit_dict(self, province: str, my_province: str, game_state: Dict[str, Any]) -> bool:
        """Check if a province has an enemy unit."""
        units = game_state.get('units', {})
        for power_name, power_units in units.items():
            for unit_str in power_units:
                if province in unit_str:
                    return True
        return False
    
    def submit_orders(self, orders: Dict[str, List[str]]) -> bool:
        """Submit orders for all powers."""
        try:
            for power_name, power_orders in orders.items():
                if power_orders:
                    # Join orders into a single string for SET_ORDERS command
                    orders_str = " ".join(power_orders)
                    result = self.server.process_command(f"SET_ORDERS {self.game_id} {power_name} {orders_str}")
                    if result.get("status") != "ok":
                        print(f"  ❌ Failed to submit orders for {power_name}: {result}")
                        return False
            
            print("  ✅ Orders submitted successfully")
            return True
            
        except Exception as e:
            print(f"  ❌ Error submitting orders: {e}")
            return False
    
    def process_phase(self) -> bool:
        """Process current phase and advance to next."""
        try:
            result = self.server.process_command(f"PROCESS_TURN {self.game_id}")
            if result.get("status") == "ok":
                print("  ✅ Phase processed successfully")
                return True
            else:
                print(f"  ❌ Failed to process phase: {result}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error processing phase: {e}")
            return False
    
    def generate_and_save_map(self, game_state: Dict[str, Any], filename: str) -> None:
        """Generate and save map visualization."""
        if not self.config.SAVE_MAPS:
            return
            
        try:
            # Generate actual PNG map
            from engine.map import Map
            
            svg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps", "standard.svg")
            filepath = os.path.join(self.maps_dir, f"{filename}.png")
            
            # Create units dictionary from game state
            units = {}
            if "units" in game_state:
                units = game_state["units"]
            
            # Get phase information
            phase_info = {
                "year": str(game_state.get("year", 1901)),
                "season": game_state.get("season", "Spring"),
                "phase": game_state.get("phase", "Movement"),
                "phase_code": game_state.get("phase_code", "S1901M")
            }
            
            # Generate PNG map
            img_bytes = Map.render_board_png(svg_path, units, output_path=filepath, phase_info=phase_info)
            
            print(f"  🗺️ Map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate map {filename}: {e}")
            # Fallback to text file
            self.generate_text_map(game_state, filename)
    
    def generate_text_map(self, game_state: Dict[str, Any], filename: str) -> None:
        """Generate fallback text map."""
        try:
            filepath = os.path.join(self.maps_dir, f"{filename}.txt")
            
            with open(filepath, 'w') as f:
                f.write(f"Map for {filename}\n")
                f.write(f"Year: {game_state['year']}\n")
                f.write(f"Phase: {game_state['phase']}\n")
                f.write(f"Turn: {game_state['turn']}\n")
                f.write(f"Season: {game_state['season']}\n\n")
                
                f.write("Units:\n")
                units = game_state.get('units', {})
                for power_name, power_units in units.items():
                    f.write(f"{power_name}:\n")
                    for unit in power_units:
                        f.write(f"  {unit}\n")
                    f.write("\n")
            
            print(f"  📄 Text map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate text map {filename}: {e}")
    
    def generate_orders_map(self, game_state: Dict[str, Any], orders: Dict[str, List[str]], filename: str) -> None:
        """Generate map showing submitted orders."""
        if not self.config.SAVE_MAPS:
            return
            
        try:
            filepath = os.path.join(self.maps_dir, f"{filename}.txt")
            
            # Create orders summary
            with open(filepath, 'w') as f:
                f.write(f"Orders for {filename}\n")
                f.write(f"Year: {game_state['year']}\n")
                f.write(f"Phase: {game_state['phase']}\n\n")
                
                for power_name, power_orders in orders.items():
                    f.write(f"{power_name}:\n")
                    for order in power_orders:
                        f.write(f"  {order}\n")
                    f.write("\n")
            
            print(f"  📋 Orders map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate orders map {filename}: {e}")
    
    def generate_resolution_map(self, game_state: Dict[str, Any], orders: Dict[str, List[str]], filename: str) -> None:
        """Generate map showing order resolution results."""
        if not self.config.SAVE_MAPS:
            return
            
        try:
            filepath = os.path.join(self.maps_dir, f"{filename}.txt")
            
            # Create resolution summary
            with open(filepath, 'w') as f:
                f.write(f"Resolution for {filename}\n")
                f.write(f"Year: {game_state['year']}\n")
                f.write(f"Phase: {game_state['phase']}\n")
                f.write(f"Turn: {game_state['turn']}\n\n")
                
                f.write("Current Units:\n")
                units = game_state.get('units', {})
                for power_name, power_units in units.items():
                    if power_units:
                        f.write(f"{power_name}:\n")
                        for unit in power_units:
                            f.write(f"  {unit}\n")
                        f.write("\n")
            
            print(f"  ⚔️ Resolution map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate resolution map {filename}: {e}")
    
    def display_game_state(self, game_state: Dict[str, Any]) -> None:
        """Display current game state."""
        print(f"📊 Game State - {game_state['year']} {game_state['phase']}")
        
        units = game_state.get('units', {})
        for power_name, power_units in units.items():
            if power_units:
                print(f"  {power_name}: {len(power_units)} units")
                
                # Show units
                for unit in power_units:
                    print(f"    {unit}")
    
    def get_generated_maps(self) -> List[str]:
        """Get list of all generated map files in chronological order."""
        try:
            import glob
            map_files = glob.glob(os.path.join(self.maps_dir, "demo_*.png"))
            # Sort by filename to get chronological order
            map_files.sort()
            return map_files
        except Exception as e:
            print(f"  ⚠️ Could not get generated maps: {e}")
            return []
    
    def cleanup_maps(self) -> None:
        """Clean up generated map files."""
        try:
            import glob
            map_files = glob.glob(os.path.join(self.maps_dir, "demo_*.png"))
            for file_path in map_files:
                os.remove(file_path)
            print(f"  🧹 Cleaned up {len(map_files)} map files")
        except Exception as e:
            print(f"  ⚠️ Could not cleanup maps: {e}")


def main():
    """Main entry point for the automated demo game."""
    print("🎮 Automated Diplomacy Demo Game")
    print("=" * 40)
    
    # Create and run demo game
    demo = AutomatedDemoGame()
    demo.run_demo_game()


if __name__ == "__main__":
    main()
