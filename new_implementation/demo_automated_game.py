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

# Add the src directory to Python path so we can import engine and server modules
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "src")
# Add src directory if it exists, otherwise add parent directory (for local development)
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)
else:
    # For local development, add project root
    sys.path.insert(0, script_dir)

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
                
                # Generate and save initial map (with ordering prefix)
                filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_01_initial"
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
                
                # Generate orders map (with ordering prefix)
                orders_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_02_orders"
                self.generate_orders_map(game_state, orders, orders_filename)
                
                # Store previous state for resolution comparison
                previous_state = game_state.copy()
                
                # Process the phase
                if not self.process_phase():
                    print("❌ Failed to process phase")
                    continue
                
                # Get updated game state
                result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
                if result.get("status") == "ok":
                    updated_state = result.get("state")
                    if updated_state:
                        # Generate resolution map (with ordering prefix, pass previous_state for comparison)
                        resolution_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_03_resolution"
                        self.generate_resolution_map(updated_state, orders, resolution_filename, previous_state)
                        
                        # Generate final map (with ordering prefix)
                        final_filename = f"demo_{phase_counter:02d}_{year}_{phase_name}_04_final"
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
            # Priority: Use phase_name parameter (we know what phase we're generating orders for)
            # The game state phase may still be the previous phase
            actual_phase = game_state.get('phase', '').lower()
            
            if "Movement" in phase_name or "Retreat" in phase_name:
                is_movement_phase = True
                is_builds_phase = False
            elif "Builds" in phase_name or "Build" in phase_name:
                is_movement_phase = False
                is_builds_phase = True
            else:
                # Fallback to actual game state phase
                phase_code = game_state.get('phase_code', '').upper()
                
                if phase_code and ('M' in phase_code or 'R' in phase_code):
                    is_movement_phase = True
                    is_builds_phase = False
                elif phase_code and ('B' in phase_code or 'A' in phase_code):
                    is_movement_phase = False
                    is_builds_phase = True
                elif 'movement' in actual_phase or 'retreat' in actual_phase:
                    is_movement_phase = True
                    is_builds_phase = False
                elif 'build' in actual_phase or 'adjustment' in actual_phase:
                    is_movement_phase = False
                    is_builds_phase = True
                else:
                    # Default: assume movement if unclear
                    is_movement_phase = True
                    is_builds_phase = False
            
            print(f"    Phase detection: {phase_name} -> Movement: {is_movement_phase}, Builds: {is_builds_phase}, Actual: {actual_phase}")
            
            if is_movement_phase:
                # Generate movement orders with support orders
                power_orders = self.generate_movement_phase_orders(power_name, power_units, game_state)
            
            elif is_builds_phase:
                # Generate build/disband orders ONLY - no movement in build phase
                power_orders = self.generate_build_orders(power_name, game_state)
            
            orders[power_name] = power_orders
            
            if power_orders:
                print(f"  {power_name}: {len(power_orders)} orders")
        
        return orders
    
    def generate_movement_phase_orders(self, power_name: str, power_units: List[str], game_state: Dict[str, Any]) -> List[str]:
        """Generate movement phase orders including moves and supports."""
        orders = []
        unit_orders = {}  # Track what each unit is doing
        
        # First pass: generate move/hold orders for each unit
        # Skip dislodged units (they should be handled in retreat phase)
        for unit_str in power_units:
            # Skip dislodged units - they shouldn't have movement orders
            if "DISLODGED_" in unit_str:
                continue
                
            parts = unit_str.split()
            if len(parts) >= 2:
                unit_type = parts[0]
                province = parts[1]
                
                order = self.generate_movement_order(unit_type, province, power_name, game_state)
                if order:
                    orders.append(order)
                    unit_orders[unit_str] = order
        
        # Second pass: generate support orders
        # Look for opportunities where one unit can support another unit's move
        # Skip dislodged units for support generation too
        for supporter_str in power_units:
            # Skip dislodged units
            if "DISLODGED_" in supporter_str:
                continue
                
            parts = supporter_str.split()
            if len(parts) >= 2:
                supporter_type = parts[0]
                supporter_province = parts[1]
                
                # Check if this unit can support another unit's move
                support_order = self.generate_support_order(supporter_str, unit_orders, power_name, game_state)
                if support_order:
                    # Replace the supporter's order with support order
                    # Find and replace the supporter's original order
                    for i, order in enumerate(orders):
                        if order.startswith(f"{supporter_type} {supporter_province}"):
                            orders[i] = support_order
                            unit_orders[supporter_str] = support_order
                            break
                    else:
                        # If not found, add support order (replaces a hold)
                        orders.append(support_order)
        
        return orders
    
    def generate_support_order(self, supporter_str: str, unit_orders: Dict[str, str], power_name: str, game_state: Dict[str, Any]) -> Optional[str]:
        """Generate a support order if there's an opportunity to support an adjacent unit's move.
        
        Priority: Support moves to provinces that have enemy units (to create 2-1 battles).
        """
        try:
            parts = supporter_str.split()
            if len(parts) < 2:
                return None
            
            supporter_type = parts[0]
            supporter_province = parts[1]
            
            # Get adjacent provinces for supporter
            supporter_adjacent = self.map.get_adjacency(supporter_province)
            if not supporter_adjacent:
                return None
            
            # Look for units of the same power that are moving to provinces adjacent to the supporter
            units = game_state.get('units', {}).get(power_name, [])
            
            # Priority 1: Support moves to provinces with enemy units (creates 2-1 battles)
            best_support = None
            best_target = None
            
            for unit_str, order in unit_orders.items():
                # Skip if this is the supporter itself
                if unit_str == supporter_str:
                    continue
                
                # Parse the order to see if it's a move order
                order_parts = order.split()
                if len(order_parts) >= 4 and order_parts[2] == "-":
                    # This is a move order: "A PAR - BUR"
                    moving_unit_type = order_parts[0]
                    moving_from = order_parts[1]
                    moving_to = order_parts[3]
                    
                    # Check if the move target is adjacent to the supporter
                    if moving_to in supporter_adjacent:
                        # Check if the supported unit's origin is also adjacent (support rule)
                        supported_adjacent = self.map.get_adjacency(moving_from)
                        if supporter_province in supported_adjacent or moving_from == supporter_province:
                            # Check if target has enemy unit (higher priority)
                            has_enemy = self.has_enemy_unit_dict(moving_to, supporter_province, game_state)
                            if has_enemy:
                                # Prioritize this - generates 2-1 battle
                                best_support = f"{supporter_type} {supporter_province} S {moving_unit_type} {moving_from} - {moving_to}"
                                best_target = moving_to
                                break
                            elif best_support is None:
                                # Keep as backup if no enemy found
                                best_support = f"{supporter_type} {supporter_province} S {moving_unit_type} {moving_from} - {moving_to}"
                                best_target = moving_to
            
            if best_support:
                return best_support
            
            # Priority 2: Support hold orders (less interesting visually, but valid)
            for unit_str in units:
                if unit_str == supporter_str:
                    continue
                
                unit_parts = unit_str.split()
                if len(unit_parts) >= 2:
                    held_province = unit_parts[1]
                    
                    # Check if held province is adjacent to supporter
                    if held_province in supporter_adjacent:
                        # Check if this unit has a hold order (or default hold)
                        unit_order = unit_orders.get(unit_str, f"{unit_parts[0]} {held_province} H")
                        if "H" in unit_order or len(unit_order.split()) == 2:
                            # Only generate support hold if the held province is under threat
                            if self.has_enemy_unit_dict(held_province, supporter_province, game_state):
                                # Support hold format: "A BUR S A PAR" (no H at end)
                                return f"{supporter_type} {supporter_province} S {unit_str}"
            
            return None
            
        except Exception as e:
            print(f"    ⚠️ Error generating support order for {supporter_str}: {e}")
            return None
    
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
        """Generate build/disband orders for a power. NO MOVEMENT ORDERS IN BUILD PHASE."""
        orders = []
        
        try:
            # Get power state - handle both dict and list formats
            powers = game_state.get('powers', {})
            power_state = None
            
            if isinstance(powers, dict) and power_name in powers:
                power_state = powers[power_name]
            elif isinstance(powers, list):
                # Powers is a list of power names, need to get state differently
                # Try to get from units to determine if we need builds/destroys
                units = game_state.get('units', {}).get(power_name, [])
                supply_centers_count = len([u for u in units if u.split()[1] in self.map.get_supply_centers()])
                unit_count = len(units)
                
                # Generate build orders if we have more supply centers than units
                if unit_count < supply_centers_count:
                    # Determine what to build based on available home centers
                    # For demo purposes, just build armies
                    num_builds = min(supply_centers_count - unit_count, 2)  # Limit to 2 builds
                    for i in range(num_builds):
                        # Find a home supply center without a unit
                        units_provinces = [u.split()[1] for u in units]
                        home_centers = self._get_home_centers(power_name)
                        for home_center in home_centers:
                            if home_center not in units_provinces:
                                orders.append(f"BUILD A {home_center}")
                                units_provinces.append(home_center)
                                break
                
                return orders
            
            if isinstance(power_state, dict):
                # Get build options
                build_options = power_state.get('builds', [])
                build_options = power_state.get('build_options', build_options)
                
                # Simple AI: build units if we have build options
                if build_options:
                    # Take first few build options
                    for i, build_option in enumerate(build_options[:2]):  # Limit to 2 builds per phase
                        if build_option:
                            # Handle different formats
                            if isinstance(build_option, str):
                                if build_option.startswith("A ") or build_option.startswith("F "):
                                    orders.append(f"BUILD {build_option}")
                                else:
                                    orders.append(f"BUILD A {build_option}")
                            else:
                                orders.append(f"BUILD A {build_option}")
                
                # Check if we need to disband (more units than supply centers)
                units = game_state.get('units', {}).get(power_name, [])
                controlled_scs = power_state.get('controlled_supply_centers', [])
                if len(units) > len(controlled_scs):
                    num_destroys = len(units) - len(controlled_scs)
                    # For demo, destroy excess units (prefer fleets if available)
                    for unit_str in units[:num_destroys]:
                        parts = unit_str.split()
                        if len(parts) >= 2:
                            orders.append(f"DESTROY {parts[0]} {parts[1]}")
                            break
                
                if not orders:
                    print(f"    {power_name}: No build orders (no build options, {len(units)} units, {len(controlled_scs)} SCs)")
            else:
                print(f"    {power_name}: Power state is not a dict: {type(power_state)}")
            
        except Exception as e:
            print(f"    ⚠️ Error generating build orders for {power_name}: {e}")
            import traceback
            traceback.print_exc()
        
        return orders
    
    def _get_home_centers(self, power_name: str) -> List[str]:
        """Get home supply centers for a power."""
        home_centers = {
            "AUSTRIA": ["VIE", "BUD", "TRI"],
            "ENGLAND": ["LON", "EDI", "LVP"],
            "FRANCE": ["PAR", "MAR", "BRE"],
            "GERMANY": ["BER", "MUN", "KIE"],
            "ITALY": ["ROM", "VEN", "NAP"],
            "RUSSIA": ["MOS", "WAR", "STP", "SEV"],
            "TURKEY": ["CON", "SMY", "ANK"]
        }
        return home_centers.get(power_name.upper(), [])
    
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
            
            # Ensure maps directory exists
            os.makedirs(self.maps_dir, exist_ok=True)
            filepath = os.path.join(self.maps_dir, f"{filename}.png")
            
            # Verify SVG path exists
            if not os.path.exists(svg_path):
                raise FileNotFoundError(f"SVG map not found at {svg_path}")
            
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
            
            # Verify file was created
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"PNG file was not created at {filepath}")
            
            print(f"  🗺️ Map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate map {filename}: {e}")
            import traceback
            traceback.print_exc()
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
    
    def _convert_order_to_visualization_format(self, order_text: str, power_name: str) -> Optional[Dict[str, Any]]:
        """Convert order text string to visualization dictionary format."""
        try:
            parts = order_text.split()
            if len(parts) < 2:
                return None
            
            # Handle BUILD and DESTROY orders
            if parts[0].upper() == "BUILD":
                if len(parts) >= 2:
                    unit_type = parts[1][0]  # A or F
                    province = parts[1][1:] if len(parts[1]) > 1 else parts[2] if len(parts) > 2 else None
                    if province:
                        return {
                            "type": "build",
                            "unit": f"{unit_type} {province}",
                            "target": province,
                            "status": "pending"
                        }
            
            if parts[0].upper() == "DESTROY":
                if len(parts) >= 2:
                    # Format: "DESTROY A PAR" or "DESTROY A PAR - BUR"
                    unit_type = parts[1][0]
                    province = parts[1][1:] if len(parts[1]) > 1 else parts[2] if len(parts) > 2 else None
                    if province:
                        return {
                            "type": "destroy",
                            "unit": f"{unit_type} {province}",
                            "status": "pending"
                        }
            
            # Handle movement orders (A PAR - BUR)
            if len(parts) >= 4 and parts[2] == "-":
                return {
                    "type": "move",
                    "unit": f"{parts[0]} {parts[1]}",
                    "target": parts[3],
                    "status": "pending"
                }
            
            # Handle hold orders (A PAR H or just A PAR)
            if len(parts) == 2 or (len(parts) == 3 and parts[2].upper() == "H"):
                return {
                    "type": "hold",
                    "unit": f"{parts[0]} {parts[1]}",
                    "status": "pending"
                }
            
            # Handle support orders (A PAR S A BUR - MUN or A PAR S A BUR)
            if len(parts) >= 4 and parts[2].upper() == "S":
                supporting = " ".join(parts[3:])
                return {
                    "type": "support",
                    "unit": f"{parts[0]} {parts[1]}",
                    "supporting": supporting,
                    "status": "pending"
                }
            
            # Handle convoy orders (F ENG C A PAR - BUR)
            if len(parts) >= 6 and parts[2].upper() == "C":
                return {
                    "type": "convoy",
                    "unit": f"{parts[0]} {parts[1]}",
                    "target": parts[-1] if len(parts) > 3 else None,
                    "via": [],  # Would need to parse convoy chain
                    "status": "pending"
                }
            
            return None
            
        except Exception as e:
            print(f"    ⚠️ Error converting order '{order_text}': {e}")
            return None
    
    def generate_orders_map(self, game_state: Dict[str, Any], orders: Dict[str, List[str]], filename: str) -> None:
        """Generate PNG map showing submitted orders."""
        if not self.config.SAVE_MAPS:
            return
            
        try:
            # Convert orders to visualization format
            viz_orders = {}
            for power_name, power_orders in orders.items():
                viz_orders[power_name] = []
                for order_text in power_orders:
                    viz_order = self._convert_order_to_visualization_format(order_text, power_name)
                    if viz_order:
                        viz_orders[power_name].append(viz_order)
            
            # Generate PNG map
            svg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps", "standard.svg")
            
            # Ensure maps directory exists
            os.makedirs(self.maps_dir, exist_ok=True)
            filepath = os.path.join(self.maps_dir, f"{filename}.png")
            
            # Verify SVG path exists
            if not os.path.exists(svg_path):
                raise FileNotFoundError(f"SVG map not found at {svg_path}")
            
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
            
            # Generate PNG map with orders
            img_bytes = Map.render_board_png_orders(
                svg_path=svg_path,
                units=units,
                orders=viz_orders,
                phase_info=phase_info,
                output_path=filepath
            )
            
            # Verify file was created
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"PNG file was not created at {filepath}")
            
            print(f"  📋 Orders map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate orders map {filename}: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to text file
            try:
                filepath = os.path.join(self.maps_dir, f"{filename}.txt")
                with open(filepath, 'w') as f:
                    f.write(f"Orders for {filename}\n")
                    f.write(f"Year: {game_state['year']}\n")
                    f.write(f"Phase: {game_state['phase']}\n\n")
                    
                    for power_name, power_orders in orders.items():
                        f.write(f"{power_name}:\n")
                        for order in power_orders:
                            f.write(f"  {order}\n")
                        f.write("\n")
                print(f"  📄 Fallback text map saved: {filepath}")
            except Exception:
                pass
    
    def _extract_resolution_data(self, game_state: Dict[str, Any], previous_state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract resolution data from game state changes."""
        resolution_data = {
            "conflicts": [],
            "dislodgements": [],
            "order_results": {}
        }
        
        # Extract conflicts from adjudication results if available
        adjudication_results = game_state.get("adjudication_results", {})
        if adjudication_results:
            # Check for conflicts in results
            conflicts = adjudication_results.get("conflicts", [])
            for conflict in conflicts:
                resolution_data["conflicts"].append({
                    "province": conflict.get("target", ""),
                    "attackers": conflict.get("participants", []),
                    "defender": None,  # Would need to determine from context
                    "strengths": conflict.get("strengths", {}),
                    "result": "standoff" if conflict.get("winner") is None else "victory"
                })
        
        # Extract dislodgements - units that are now in DISLODGED_ format
        units = game_state.get('units', {})
        previous_units = previous_state.get('units', {}) if previous_state else {}
        
        for power_name, power_units in units.items():
            for unit in power_units:
                if "DISLODGED_" in unit:
                    # Extract original province
                    parts = unit.split()
                    if len(parts) >= 2:
                        original_province = parts[1].replace("DISLODGED_", "")
                        resolution_data["dislodgements"].append({
                            "unit": unit,
                            "dislodged_by": None,  # Would need to determine from context
                            "retreat_options": []
                        })
        
        # Extract order results - compare previous orders with current state
        # For now, mark all orders as success (would need more sophisticated analysis)
        resolution_data["order_results"] = {}
        
        return resolution_data
    
    def generate_resolution_map(self, game_state: Dict[str, Any], orders: Dict[str, List[str]], filename: str, previous_state: Dict[str, Any] = None) -> None:
        """Generate PNG map showing order resolution results."""
        if not self.config.SAVE_MAPS:
            return
            
        try:
            # Convert orders to visualization format with status
            viz_orders = {}
            for power_name, power_orders in orders.items():
                viz_orders[power_name] = []
                for order_text in power_orders:
                    viz_order = self._convert_order_to_visualization_format(order_text, power_name)
                    if viz_order:
                        # Try to determine status from game state changes
                        # For now, default to "success" (would need more sophisticated analysis)
                        viz_order["status"] = "success"
                        viz_orders[power_name].append(viz_order)
            
            # Extract resolution data
            resolution_data = self._extract_resolution_data(game_state, previous_state or {})
            
            # Generate PNG map
            svg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "maps", "standard.svg")
            
            # Ensure maps directory exists
            os.makedirs(self.maps_dir, exist_ok=True)
            filepath = os.path.join(self.maps_dir, f"{filename}.png")
            
            # Verify SVG path exists
            if not os.path.exists(svg_path):
                raise FileNotFoundError(f"SVG map not found at {svg_path}")
            
            # Create units dictionary from game state (includes dislodged units)
            units = {}
            if "units" in game_state:
                units = game_state["units"]
            
            # Get supply center control
            supply_center_control = {}
            powers = game_state.get("powers", {})
            
            # Handle both dict and list formats
            if isinstance(powers, dict):
                # Full game state format with power state objects
                for power_name, power_state in powers.items():
                    if isinstance(power_state, dict):
                        controlled_scs = power_state.get("controlled_supply_centers", [])
                        for sc in controlled_scs:
                            supply_center_control[sc] = power_name
            elif isinstance(powers, list):
                # Simplified state format - try to get from supply_centers field if available
                if "supply_centers" in game_state and isinstance(game_state["supply_centers"], dict):
                    supply_center_control = game_state["supply_centers"]
                # Otherwise, derive from units (units on supply centers control them)
                elif "units" in game_state:
                    from engine.map import Map
                    map_obj = Map("standard")
                    scs = map_obj.get_supply_centers()
                    for power_name, power_units in game_state["units"].items():
                        for unit_str in power_units:
                            # Parse unit like "A PAR" or "F BRE"
                            parts = unit_str.split()
                            if len(parts) >= 2:
                                province = parts[1]
                                if province in scs:
                                    supply_center_control[province] = power_name
            
            # Get phase information
            phase_info = {
                "year": str(game_state.get("year", 1901)),
                "season": game_state.get("season", "Spring"),
                "phase": game_state.get("phase", "Movement"),
                "phase_code": game_state.get("phase_code", "S1901M")
            }
            
            # Generate PNG resolution map
            img_bytes = Map.render_board_png_resolution(
                svg_path=svg_path,
                units=units,
                orders=viz_orders,
                resolution_data=resolution_data,
                phase_info=phase_info,
                output_path=filepath,
                supply_center_control=supply_center_control
            )
            
            # Verify file was created
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"PNG file was not created at {filepath}")
            
            print(f"  ⚔️ Resolution map saved: {filepath}")
            
        except Exception as e:
            print(f"  ⚠️ Could not generate resolution map {filename}: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to text file
            try:
                filepath = os.path.join(self.maps_dir, f"{filename}.txt")
                with open(filepath, 'w') as f:
                    f.write(f"Resolution for {filename}\n")
                    f.write(f"Year: {game_state['year']}\n")
                    f.write(f"Phase: {game_state['phase']}\n")
                    f.write(f"Turn: {game_state.get('turn', 1)}\n\n")
                    
                    f.write("Current Units:\n")
                    units = game_state.get('units', {})
                    for power_name, power_units in units.items():
                        if power_units:
                            f.write(f"{power_name}:\n")
                            for unit in power_units:
                                f.write(f"  {unit}\n")
                            f.write("\n")
                print(f"  📄 Fallback text map saved: {filepath}")
            except Exception:
                pass
    
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
    
    # Verify imports work (imports are already done at top of file, but verify)
    try:
        # Re-import to verify they work
        from server.server import Server  # noqa: F401
        from engine.game import Game  # noqa: F401
        from engine.map import Map  # noqa: F401
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(f"   Python path: {sys.path}")
        print(f"   Current directory: {os.getcwd()}")
        print(f"   Script location: {os.path.abspath(__file__)}")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir_check = os.path.join(script_dir, "src")
        print(f"   src directory exists: {os.path.exists(src_dir_check)}")
        if os.path.exists(src_dir_check):
            print(f"   src directory: {src_dir_check}")
        sys.exit(1)
    
    # Create and run demo game
    try:
        demo = AutomatedDemoGame()
        demo.run_demo_game()
    except Exception as e:
        print(f"❌ Demo game failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
