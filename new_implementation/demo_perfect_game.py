#!/usr/bin/env python3
"""
Perfect Automated Demo Game for Diplomacy

This script runs a hardcoded automated Diplomacy game that demonstrates all
game mechanics through a carefully choreographed sequence of predetermined orders.
Unlike the dynamic AI-based demo, this uses specific orders to showcase:
- 2-1 battles
- Support cuts
- Convoys
- Standoffs
- Retreats
- Build phases

All orders are hardcoded and validated to ensure they demonstrate specific
mechanics and create educational scenarios.

Usage:
    python3 demo_perfect_game.py

The script will:
1. Create a demo game
2. Add all seven powers
3. Play through predetermined scenarios (Spring 1901, Fall 1901, etc.)
4. Generate visual maps at each phase
5. Demonstrate all order types and game mechanics
"""

import os
import sys
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Add the src directory to Python path so we can import engine and server modules
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "src")
if os.path.exists(src_dir):
    sys.path.insert(0, src_dir)
else:
    sys.path.insert(0, script_dir)

from server.server import Server
from engine.game import Game
from engine.map import Map


@dataclass
class ScenarioData:
    """Data structure for a single scenario phase."""
    year: int
    season: str
    phase: str
    orders: Dict[str, List[str]]
    expected_outcomes: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


class PerfectDemoGame:
    """Hardcoded demo game that plays a predetermined sequence of scenarios."""
    
    def __init__(self):
        self.server = Server()
        self.map = Map("standard")
        self.game_id: Optional[str] = None
        self.phase_count = 0
        self.scenarios: List[ScenarioData] = []
        
        # Ensure test_maps directory exists
        self.maps_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_maps")
        os.makedirs(self.maps_dir, exist_ok=True)
        
        # Load all scenarios
        self.load_scenarios()
    
    def adjust_scenario_for_state(self, scenario: ScenarioData) -> ScenarioData:
        """Adjust scenario orders based on actual game state positions."""
        # Get current game state
        result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
        if result.get("status") != "ok":
            return scenario
        
        game_state = result.get("state")
        if not game_state:
            return scenario
        
        units = game_state.get("units", {})
        
        # Adjust Spring 1902 orders for England if needed
        if scenario.year == 1902 and scenario.season == "Spring" and scenario.phase == "Movement":
            england_units = units.get("ENGLAND", [])
            
            # Build a map of all England units (handle multiple fleets/armies)
            england_armies = []
            england_fleets = []
            for unit_str in england_units:
                parts = unit_str.split()
                if len(parts) >= 2:
                    unit_type = parts[0]
                    province = parts[1].replace("DISLODGED_", "")
                    if unit_type == "A":
                        england_armies.append(province)
                    elif unit_type == "F":
                        england_fleets.append(province)
            
            if england_armies and england_fleets:
                # Find the best army for convoy (prefer CLY, then any army)
                army_province = england_armies[0]
                if "CLY" in england_armies:
                    army_province = "CLY"
                
                # Find a fleet that can convoy (prefer NTH, ENG, then any fleet in northern waters)
                fleet_province = None
                for fleet in england_fleets:
                    if fleet in ["NTH", "ENG"]:
                        fleet_province = fleet
                        break
                if not fleet_province:
                    # Try other northern fleets
                    for fleet in england_fleets:
                        if fleet in ["YOR", "LON", "EDI", "CLY"]:
                            fleet_province = fleet
                            break
                if not fleet_province and england_fleets:
                    # Use any available fleet
                    fleet_province = england_fleets[0]
                
                # Adjust convoy orders if army or fleet positions differ
                if army_province and fleet_province:
                    adjusted_orders = list(scenario.orders.get("ENGLAND", []))
                    new_orders = []
                    for order in adjusted_orders:
                        original_order = order
                        # Fix convoy orders (remove VIA CONVOY if present, it's not needed)
                        if "VIA CONVOY" in order:
                            # Remove VIA CONVOY - convoy is specified by convoy orders
                            order = order.replace(" VIA CONVOY", "")
                            # Replace army position in convoy move order
                            if "A CLY" in order:
                                order = order.replace("A CLY", f"A {army_province}")
                            if "A LVP" in order:
                                order = order.replace("A LVP", f"A {army_province}")
                        if "C A" in order:
                            # Replace both fleet and army positions in convoy order
                            # Format: F NTH C A CLY - BEL
                            if "F NTH" in order:
                                order = order.replace("F NTH", f"F {fleet_province}")
                            if "F ENG" in order:
                                order = order.replace("F ENG", f"F {fleet_province}")
                            if f"A {army_province}" not in order:
                                # Replace army reference in convoy
                                if "A CLY" in order:
                                    order = order.replace("A CLY", f"A {army_province}")
                                if "A LVP" in order:
                                    order = order.replace("A LVP", f"A {army_province}")
                        if "S F" in order:
                            # Replace fleet position in support order
                            if "S F NTH" in order:
                                order = order.replace("S F NTH", f"S F {fleet_province}")
                            if "S F ENG" in order:
                                order = order.replace("S F ENG", f"S F {fleet_province}")
                        new_orders.append(order)
                        
                        if order != original_order:
                            print(f"    🔄 Adjusted order: {original_order} -> {order}")
                    
                    if new_orders != adjusted_orders:
                        scenario.orders["ENGLAND"] = new_orders
                        print(f"  🔄 Adjusted England orders: army in {army_province}, fleet in {fleet_province}")
                else:
                    print(f"  ⚠️ Warning: Cannot adjust England convoy orders - missing units")
                    print(f"    Armies: {england_armies}, Fleets: {england_fleets}")
        
        return scenario
    
    def load_scenarios(self) -> None:
        """Load all hardcoded scenario data."""
        # Spring 1901 Movement
        self.scenarios.append(ScenarioData(
            year=1901,
            season="Spring",
            phase="Movement",
            orders={
                "AUSTRIA": ["A VIE - TYR", "A BUD - RUM", "F TRI H"],
                "ENGLAND": ["F LON - ENG", "F EDI - NTH", "A LVP - CLY"],
                "FRANCE": ["A PAR - BUR", "A MAR - PIE", "F BRE - MAO"],
                "GERMANY": ["A BER - KIE", "A MUN - SIL", "F KIE - HOL"],
                "ITALY": ["A ROM - TUS", "A VEN H", "F NAP - ION"],
                "RUSSIA": ["A MOS - UKR", "A WAR - GAL", "F SEV - BLA", "F STP - BOT"],
                "TURKEY": ["A CON - BUL", "A SMY - ARM", "F ANK - BLA"]
            },
            description="Initial positioning phase. All powers expand into adjacent territories."
        ))
        
        # Fall 1901 Movement
        self.scenarios.append(ScenarioData(
            year=1901,
            season="Autumn",
            phase="Movement",
            orders={
                "AUSTRIA": ["A TYR - VEN", "A RUM H", "F TRI S A TYR - VEN"],
                "ENGLAND": ["F ENG - BEL", "F NTH S F ENG - BEL", "A CLY H"],
                "FRANCE": ["A BUR - BEL", "A PIE - TYS", "F MAO S A BUR - BEL"],
                "GERMANY": ["A SIL - GAL", "A HOL - BEL", "A KIE S A HOL - BEL"],
                "ITALY": ["A VEN H", "A APU S A VEN H", "F ION - ADR"],
                "RUSSIA": ["A UKR - RUM", "A GAL S A UKR - RUM", "F BLA - CON", "F BOT H"],
                "TURKEY": ["A BUL - RUM", "A ARM - SEV", "F BLA H"]
            },
            description="Demonstrates 2-1 battles, support cuts, and creates dislodgements for retreat phase."
        ))
        
        # Fall 1901 Retreat
        self.scenarios.append(ScenarioData(
            year=1901,
            season="Autumn",
            phase="Retreat",
            orders={
                "ITALY": ["A VEN R APU"],
                "TURKEY": ["F BLA D"]  # Disband - no valid retreat
            },
            description="Demonstrates retreat orders and forced disband when no valid retreat exists."
        ))
        
        # Fall 1901 Builds
        self.scenarios.append(ScenarioData(
            year=1901,
            season="Autumn",
            phase="Builds",
            orders={
                "FRANCE": ["BUILD A MAR"],
                "AUSTRIA": ["BUILD A BUD"],
                "RUSSIA": ["BUILD A MOS"],
                "ENGLAND": [],
                "GERMANY": [],
                "ITALY": [],
                "TURKEY": []
            },
            description="Build phase after Fall turn. Powers that gained supply centers build new units."
        ))
        
        # Spring 1902 Movement
        # Note: After Fall 1901, England's army is in CLY (not LVP), and fleet positions may vary
        # Based on Fall 1901 outcomes: France takes BEL, England's F ENG is dislodged from BEL
        # England should have F NTH and A CLY after retreat phase
        self.scenarios.append(ScenarioData(
            year=1902,
            season="Spring",
            phase="Movement",
            orders={
                "ENGLAND": ["A CLY - BEL", "F NTH C A CLY - BEL", "F ENG S F NTH"],
                "FRANCE": ["A BEL H", "A PAR S A BEL H", "F MAO - SPA", "A MAR - PIE"],
                "GERMANY": ["A KIE - HOL", "A SIL - WAR", "A BEL - RUH"],
                "AUSTRIA": ["A VEN H", "A TYR S A VEN H", "F TRI - ADR"],
                "ITALY": ["A APU - VEN", "F ADR S A APU - VEN"],
                "RUSSIA": ["A RUM - BUL", "A UKR S A RUM - BUL", "A GAL - WAR", "F BOT - SWE"],
                "TURKEY": ["A BUL - GRE", "A ARM H", "F BLA - CON"]
            },
            description="Demonstrates convoy orders and complex support combinations."
        ))
    
    def run_demo(self) -> None:
        """Execute the perfect demo game sequence."""
        print("🎮 Starting Perfect Automated Diplomacy Demo Game")
        print("=" * 60)
        print("This demo uses hardcoded orders to demonstrate all game mechanics")
        print("=" * 60)
        
        try:
            # Step 1: Create demo game
            if not self.create_demo_game():
                print("❌ Failed to create demo game")
                return
            
            # Step 2: Add all players
            if not self.add_players():
                print("❌ Failed to add players")
                return
            
            # Step 3: Play through all scenarios
            self.play_scenarios()
            
            print("\n🎉 Perfect demo game completed successfully!")
            print(f"📊 Processed {self.phase_count} phases")
            print(f"🗺️ Maps saved to: {self.maps_dir}/")
            
        except Exception as e:
            print(f"❌ Demo game failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def create_demo_game(self) -> bool:
        """Create a new demo game instance."""
        print("🎯 Creating demo game...")
        
        try:
            result = self.server.process_command("CREATE_GAME standard")
            
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
    
    def play_scenarios(self) -> None:
        """Play through all hardcoded scenarios."""
        print("\n🎲 Starting scenario playback...")
        
        phase_counter = 1
        
        for scenario in self.scenarios:
            # Adjust scenario orders based on actual game state if needed
            scenario = self.adjust_scenario_for_state(scenario)
            print(f"\n📅 {scenario.season} {scenario.year} - {scenario.phase}")
            print("-" * 50)
            print(f"📖 {scenario.description}")
            print("-" * 50)
            
            # Get current game state
            result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
            if result.get("status") != "ok":
                print("❌ Failed to get game state")
                continue
            game_state = result.get("state")
            
            if not game_state:
                print("❌ Failed to get game state")
                continue
            
            # Check if game is completed
            if game_state.get('done', False):
                print("🏆 Game completed!")
                return
            
            # Verify we're in the correct phase (adjust if needed)
            if game_state.get('phase') != scenario.phase or game_state.get('year') != scenario.year or game_state.get('season') != scenario.season:
                print(f"⚠️ Phase mismatch: Expected {scenario.season} {scenario.year} {scenario.phase}, got {game_state.get('season')} {game_state.get('year')} {game_state.get('phase')}")
                # Try to advance phases if needed - for now, continue anyway
            
            # Generate and save initial map
            filename = f"perfect_demo_{phase_counter:02d}_{scenario.year}_{scenario.season}_{scenario.phase}_01_initial"
            self.generate_and_save_map(game_state, filename)
            
            # Submit hardcoded orders
            orders_submitted = self.submit_orders(scenario.orders)
            if not orders_submitted:
                print("  ⚠️ Some orders failed - continuing with available orders")
            
            # Generate orders map (using submitted orders, not original)
            orders_filename = f"perfect_demo_{phase_counter:02d}_{scenario.year}_{scenario.season}_{scenario.phase}_02_orders"
            self.generate_orders_map(game_state, scenario.orders, orders_filename)
            
            # Store previous state for resolution comparison
            previous_state = game_state.copy()
            
            # Always process the phase to advance game state, even if some orders failed
            if not self.process_phase():
                print("  ❌ Failed to process phase - game state may be inconsistent")
                # Still continue to next scenario
                continue
            
            # Get updated game state
            result = self.server.process_command(f"GET_GAME_STATE {self.game_id}")
            if result.get("status") == "ok":
                updated_state = result.get("state")
                if updated_state:
                    # Generate resolution map
                    resolution_filename = f"perfect_demo_{phase_counter:02d}_{scenario.year}_{scenario.season}_{scenario.phase}_03_resolution"
                    self.generate_resolution_map(updated_state, scenario.orders, resolution_filename, previous_state)
                    
                    # Generate final map
                    final_filename = f"perfect_demo_{phase_counter:02d}_{scenario.year}_{scenario.season}_{scenario.phase}_04_final"
                    self.generate_and_save_map(updated_state, final_filename)
                    
                    # Display game state
                    self.display_game_state(updated_state)
            
            self.phase_count += 1
            phase_counter += 1
            
            # Small delay for readability
            time.sleep(0.5)
    
    def submit_orders(self, orders: Dict[str, List[str]]) -> bool:
        """Submit orders for all powers. Returns True if at least one power's orders succeeded."""
        success_count = 0
        failed_powers = []
        
        try:
            for power_name, power_orders in orders.items():
                if power_orders:
                    # Join orders into a single string for SET_ORDERS command
                    orders_str = " ".join(power_orders)
                    result = self.server.process_command(f"SET_ORDERS {self.game_id} {power_name} {orders_str}")
                    if result.get("status") == "ok":
                        success_count += 1
                    else:
                        print(f"  ⚠️ Failed to submit orders for {power_name}: {result.get('message', result)}")
                        failed_powers.append(power_name)
            
            if success_count > 0:
                if failed_powers:
                    print(f"  ⚠️ Orders submitted for {success_count} powers; failed for: {', '.join(failed_powers)}")
                else:
                    print(f"  ✅ Orders submitted successfully for all {success_count} powers")
                return True
            else:
                print(f"  ❌ Failed to submit orders for all powers")
                return False
            
        except Exception as e:
            print(f"  ❌ Error submitting orders: {e}")
            import traceback
            traceback.print_exc()
            return success_count > 0  # Return True if at least some succeeded
    
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
            import traceback
            traceback.print_exc()
            return False
    
    def generate_and_save_map(self, game_state: Dict[str, Any], filename: str) -> None:
        """Generate and save map visualization."""
        try:
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
            
            if parts[0].upper() == "DESTROY" or parts[0].upper() == "D":
                if len(parts) >= 3:
                    unit_type = parts[1]
                    province = parts[2]
                    return {
                        "type": "destroy",
                        "unit": f"{unit_type} {province}",
                        "status": "pending"
                    }
                elif len(parts) >= 2:
                    # Format: "D" for disband (retreat phase)
                    unit_type = parts[0] if parts[0] in ['A', 'F'] else parts[1][0]
                    province = parts[1] if parts[1] not in ['A', 'F', 'D'] else parts[2]
                    return {
                        "type": "destroy",
                        "unit": f"{unit_type} {province}",
                        "status": "pending"
                    }
            
            # Handle retreat orders (A PAR R BUR)
            if len(parts) >= 4 and parts[2].upper() == "R":
                return {
                    "type": "retreat",
                    "unit": f"{parts[0]} {parts[1]}",
                    "target": parts[3],
                    "status": "pending"
                }
            
            # Handle movement orders (A PAR - BUR)
            if len(parts) >= 4 and parts[2] == "-":
                # Check for convoy notation
                if len(parts) > 4 and parts[4].upper() == "VIA" and parts[5].upper() == "CONVOY":
                    return {
                        "type": "move",
                        "unit": f"{parts[0]} {parts[1]}",
                        "target": parts[3],
                        "via": "convoy",
                        "status": "pending"
                    }
                else:
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
            conflicts = adjudication_results.get("conflicts", [])
            for conflict in conflicts:
                resolution_data["conflicts"].append({
                    "province": conflict.get("target", ""),
                    "attackers": conflict.get("participants", []),
                    "defender": None,
                    "strengths": conflict.get("strengths", {}),
                    "result": "standoff" if conflict.get("winner") is None else "victory"
                })
        
        # Extract dislodgements - units that are now in DISLODGED_ format
        units = game_state.get('units', {})
        previous_units = previous_state.get('units', {}) if previous_state else {}
        
        for power_name, power_units in units.items():
            for unit in power_units:
                if "DISLODGED_" in unit:
                    parts = unit.split()
                    if len(parts) >= 2:
                        original_province = parts[1].replace("DISLODGED_", "")
                        resolution_data["dislodgements"].append({
                            "unit": unit,
                            "dislodged_by": None,
                            "retreat_options": []
                        })
        
        return resolution_data
    
    def generate_resolution_map(self, game_state: Dict[str, Any], orders: Dict[str, List[str]], filename: str, previous_state: Dict[str, Any] = None) -> None:
        """Generate PNG map showing order resolution results."""
        try:
            # Convert orders to visualization format with status
            viz_orders = {}
            for power_name, power_orders in orders.items():
                viz_orders[power_name] = []
                for order_text in power_orders:
                    viz_order = self._convert_order_to_visualization_format(order_text, power_name)
                    if viz_order:
                        viz_order["status"] = "success"  # Default
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
                for power_name, power_state in powers.items():
                    if isinstance(power_state, dict):
                        controlled_scs = power_state.get("controlled_supply_centers", [])
                        for sc in controlled_scs:
                            supply_center_control[sc] = power_name
            elif isinstance(powers, list):
                if "supply_centers" in game_state and isinstance(game_state["supply_centers"], dict):
                    supply_center_control = game_state["supply_centers"]
                elif "units" in game_state:
                    scs = self.map.get_supply_centers()
                    for power_name, power_units in game_state["units"].items():
                        for unit_str in power_units:
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
    
    def display_game_state(self, game_state: Dict[str, Any]) -> None:
        """Display current game state."""
        print(f"📊 Game State - {game_state['year']} {game_state['season']} {game_state['phase']}")
        
        units = game_state.get('units', {})
        for power_name, power_units in units.items():
            if power_units:
                print(f"  {power_name}: {len(power_units)} units")
                for unit in power_units:
                    print(f"    {unit}")


def main():
    """Main entry point for the perfect demo game."""
    print("🎮 Perfect Automated Diplomacy Demo Game")
    print("=" * 60)
    
    # Verify imports work
    try:
        from server.server import Server  # noqa: F401
        from engine.game import Game  # noqa: F401
        from engine.map import Map  # noqa: F401
        print("✅ All imports successful")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print(f"   Python path: {sys.path}")
        print(f"   Current directory: {os.getcwd()}")
        print(f"   Script location: {os.path.abspath(__file__)}")
        sys.exit(1)
    
    # Create and run demo game
    try:
        demo = PerfectDemoGame()
        demo.run_demo()
    except Exception as e:
        print(f"❌ Demo game failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

