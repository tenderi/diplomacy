from typing import Dict, List, Any, Optional, Tuple
from .map import Map
from .order_parser import OrderParser
from .data_models import (
    Order, GameState, PowerState, Unit, MapData, Province, OrderType, OrderStatus, GameStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder
)
import logging
from collections import deque
from datetime import datetime

class Game:
    """
    Main game class using new data models exclusively.
    
    This class manages the complete Diplomacy game state, including turn processing,
    order validation, and game phase management. It uses the comprehensive data
    models defined in data_models.py for proper type safety and validation.
    
    Attributes:
        map_name: Name of the map variant being used
        map: Map object containing province and adjacency data
        turn: Current turn number
        year: Current game year
        season: Current season (Spring, Fall, Winter)
        phase: Current phase (Movement, Retreat, Builds)
        phase_code: Short code for current phase (e.g., "S1901M")
        done: Whether the game is completed
        game_state: Complete GameState object containing all game data
    """
    
    def __init__(self, map_name: str = 'standard') -> None:
        self.map_name: str = map_name
        # Use standard map for demo mode
        actual_map_name = 'standard' if map_name == 'demo' else map_name
        self.map: Map = Map(actual_map_name)
        
        # Game state tracking
        self.turn: int = 0
        self.year: int = 1901
        self.season: str = "Spring"
        self.phase: str = "Movement"
        self.phase_code: str = "S1901M"
        self.done: bool = False
        
        # Initialize new data model
        self.game_state = self._initialize_game_state()

    def _initialize_game_state(self) -> GameState:
        """Initialize the new GameState data model"""
        # Create map data using the Map's Province objects directly
        provinces = {}
        for province_name in self.map.get_locations():
            map_province = self.map.get_province(province_name)
            if map_province:
                # Convert Map Province to data_models Province
                provinces[province_name] = Province(
                    name=province_name,
                    province_type=map_province.type,
                    is_supply_center=province_name in self.map.get_supply_centers(),
                    is_home_supply_center=False,  # Will be set when powers are added
                    adjacent_provinces=list(map_province.adjacent) if map_province.adjacent else []
                )
        
        map_data = MapData(
            map_name=self.map_name,
            provinces=provinces,
            supply_centers=list(self.map.get_supply_centers()),
            home_supply_centers={},  # Will be populated when powers are added
            starting_positions={}  # Will be populated when powers are added
        )
        
        return GameState(
            game_id="demo",
            map_name=self.map_name,
            map_data=map_data,
            current_turn=0,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            powers={},
            orders={},
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def add_player(self, power_name: str) -> None:
        """
        Add a player to the game.
        
        Args:
            power_name: Name of the power to add (e.g., "FRANCE", "GERMANY")
            
        Note:
            This method initializes the power with their home supply centers
            and starting units according to the standard Diplomacy rules.
            If the power already exists, this method does nothing.
        """
        if power_name not in self.game_state.powers:
            # Define home supply centers for each power
            home_centers = {
                'ENGLAND': ['LON', 'EDI', 'LVP'],
                'FRANCE': ['PAR', 'MAR', 'BRE'],
                'GERMANY': ['BER', 'KIE', 'MUN'],
                'ITALY': ['ROM', 'VEN', 'NAP'],
                'AUSTRIA': ['VIE', 'BUD', 'TRI'],
                'RUSSIA': ['MOS', 'WAR', 'SEV', 'STP'],
                'TURKEY': ['CON', 'SMY', 'ANK'],
            }
            
            # Add to new data model
            self.game_state.powers[power_name] = PowerState(
                power_name=power_name,
                units=[],
                controlled_supply_centers=home_centers.get(power_name.upper(), []),
                home_supply_centers=home_centers.get(power_name.upper(), [])
            )
            
            # Update map data with home supply centers
            if power_name.upper() in home_centers:
                self.game_state.map_data.home_supply_centers[power_name] = home_centers[power_name.upper()]
            
            # Assign standard starting units if using the standard map or demo mode
            if self.map_name in ['standard', 'demo']:
                starting_units = {
                    'ENGLAND': ['F LON', 'F EDI', 'A LVP'],
                    'FRANCE': ['A PAR', 'A MAR', 'F BRE'],
                    'GERMANY': ['A BER', 'A MUN', 'F KIE'],
                    'ITALY': ['A ROM', 'A VEN', 'F NAP'],
                    'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],
                    'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'],
                    'TURKEY': ['A CON', 'A SMY', 'F ANK'],
                }
                pname = power_name.upper()
                if pname in starting_units:
                    # Add units to new data model
                    for unit_str in starting_units[pname]:
                        unit_type, province = unit_str.split()
                        unit = Unit(
                            unit_type=unit_type,
                            province=province,
                            power=power_name,
                            is_dislodged=False,
                            dislodged_by=None,
                            can_retreat=True,
                            retreat_options=[]
                        )
                        self.game_state.powers[power_name].units.append(unit)
        
        # Initialize orders list for this power
        if power_name not in self.game_state.orders:
            self.game_state.orders[power_name] = []

    def clear_orders(self, power_name: str) -> None:
        """
        Clear all orders for a power.
        
        Args:
            power_name: Name of the power to clear orders for
            
        Note:
            This removes all pending orders for the specified power,
            effectively resetting their order submission for the current phase.
        """
        if power_name in self.game_state.powers:
            self.game_state.orders[power_name] = []

    def set_orders(self, power_name: str, orders: List[str]) -> None:
        """
        Set orders for a power. Orders are parsed, validated, and stored.
        
        Args:
            power_name: Name of the power submitting orders
            orders: List of order strings (e.g., ["A PAR - BUR", "F BRE H"])
            
        Raises:
            ValueError: If the power is not found in the game
            OrderValidationError: If any order fails validation
            
        Note:
            Orders are parsed using the OrderParser and validated against
            the current game state before being stored.
        """
        if power_name not in self.game_state.powers:
            raise ValueError(f"Power {power_name} not found in game")
        
        # Convert string orders to new order objects
        parser = OrderParser()
        parsed_orders = parser.parse_orders(";".join(orders), power_name)
        # Build concrete Order objects from parsed forms
        power_state = self.game_state.powers[power_name]
        new_orders = []
        for parsed in parsed_orders:
            order_obj = parser.create_order_from_parsed(parsed, self.game_state)
            new_orders.append(order_obj)
        
        # Ensure game state phase is up to date
        self.game_state.current_phase = self.phase
        
        # Store orders temporarily for convoy validation
        self.game_state.orders[power_name] = new_orders
        
        # Validate each order
        validation_errors = []
        for order in new_orders:
            if order:
                # Validate order against game state
                valid, reason = OrderParser().validate_orders([order], self.game_state)[0]
                if not valid:
                    validation_errors.append(f"Order {order}: {reason}")
                
                # Check if order type is valid for current phase
                if not self.game_state.is_valid_phase_for_order_type(order.order_type):
                    validation_errors.append(f"Order {order}: type {order.order_type.value} not valid for phase {self.game_state.current_phase}")
        
        # Cross-order validation: Check convoy restrictions
        convoy_validation_errors = self.game_state._validate_convoy_restrictions()
        validation_errors.extend(convoy_validation_errors)
        
        # If there are validation errors, raise an exception
        if validation_errors:
            raise ValueError(f"Invalid orders for {power_name}: {'; '.join(validation_errors)}")

    def process_turn(self) -> Dict[str, Any]:
        """
        Process a complete turn and return results.
        
        Returns:
            Dictionary containing:
                - moves: List of successful moves
                - dislodgements: List of units that were dislodged
                - status: "completed" if turn processed successfully
                
        Note:
            This method processes the current phase (Movement, Retreat, or Builds)
            and then advances to the next phase. The game state is updated
            with the results of order resolution.
        """
        results = {
            "moves": [],
            "dislodgements": [],
            "status": "completed"
        }
        
        # Process current phase
        if self.phase == "Movement":
            results.update(self._process_movement_phase())
        elif self.phase == "Retreat":
            results.update(self._process_retreat_phase())
        elif self.phase == "Builds":
            results.update(self._process_builds_phase())
        
        # Advance to next phase
        self._advance_phase()
        
        return results

    def _process_movement_phase(self) -> Dict[str, Any]:
        """Process movement phase with full Diplomacy rules."""
        results: Dict[str, List[Any]] = {
            "moves": [],
            "dislodgements": [],
            "supports": [],
            "convoys": [],
            "conflicts": [],
            "dislodged_units": []
        }
        
        # First pass: Detect convoyed moves and convoy orders
        convoy_orders = {}  # (convoyed_unit_type, convoyed_unit_province, convoyed_target) -> convoy_order
        convoyed_moves = {}  # (unit_type, unit_province, target) -> convoy_order
        
        for power_name, orders in self.game_state.orders.items():
            for order in orders:
                if isinstance(order, ConvoyOrder):
                    convoy_key = (order.convoyed_unit.unit_type, order.convoyed_unit.province, order.convoyed_target)
                    convoy_orders[convoy_key] = order
                    
                    # Mark the corresponding move order as convoyed
                    move_key = (order.convoyed_unit.unit_type, order.convoyed_unit.province, order.convoyed_target)
                    convoyed_moves[move_key] = order
        
        # Calculate move strengths and identify conflicts
        move_strengths: Dict[str, List[Tuple[Unit, int, Order]]] = {}  # target_province -> list of (unit, strength, order)
        support_strengths: Dict[str, List[Tuple[Unit, int]]] = {}  # target_province -> list of (supporting_unit, strength)
        
        # First pass: Process all moves and holds to determine conflicts and dislodgements
        for power_name, orders in self.game_state.orders.items():
            for order in orders:
                if isinstance(order, MoveOrder):
                    target = order.target_province
                    if target not in move_strengths:
                        move_strengths[target] = []
                    
                    # Calculate base strength (1 for move)
                    strength = 1
                    
                    # Check if this move is convoyed
                    move_key = (order.unit.unit_type, order.unit.province, order.target_province)
                    if move_key in convoyed_moves:
                        order.is_convoyed = True
                        # Collect all convoy orders for this move
                        convoy_route: List[str] = []
                        for power_name_check, orders_check in self.game_state.orders.items():
                            for convoy_order in orders_check:
                                if isinstance(convoy_order, ConvoyOrder):
                                    if (convoy_order.convoyed_unit.unit_type == order.unit.unit_type and
                                        convoy_order.convoyed_unit.province == order.unit.province and
                                        convoy_order.convoyed_target == order.target_province):
                                        convoy_route.append(convoy_order.unit.province)
                        order.convoy_route = convoy_route
                        
                        # Calculate convoy strength
                        convoy_strength = self._calculate_convoy_strength(order)
                        if convoy_strength > 0:
                            strength += convoy_strength
                    
                    move_strengths[target].append((order.unit, strength, order))
                    
                elif isinstance(order, HoldOrder):
                    # Hold orders don't move, but they can be dislodged
                    target = order.unit.province
                    if target not in move_strengths:
                        move_strengths[target] = []
                    move_strengths[target].append((order.unit, 1, order))
        
        # Second pass: Process support orders
        for power_name, orders in self.game_state.orders.items():
            for order in orders:
                if isinstance(order, SupportOrder):
                    # Check if supporting unit is dislodged
                    supporting_unit = order.unit
                    is_support_cut = False

                    # Check if any unit is moving to the supporting unit's province
                    for target_province, moves in move_strengths.items():
                        if target_province == supporting_unit.province:
                            for unit, strength, move_order in moves:
                                if unit != supporting_unit:  # Not supporting itself
                                    is_support_cut = True
                                    break
                            if is_support_cut:
                                break

                    if not is_support_cut:
                        # Support is not cut, add support strength
                        if order.supported_target not in support_strengths:
                            support_strengths[order.supported_target] = []
                        support_strengths[order.supported_target].append((supporting_unit, 1))
        
        # Check for mutual moves (units trying to swap positions)
        mutual_moves = []
        for target_province, moves in move_strengths.items():
            if len(moves) == 1:
                unit, strength, order = moves[0]
                # Check if there's a unit in the target province that's also moving
                for other_target, other_moves in move_strengths.items():
                    if other_target != target_province:
                        for other_unit, other_strength, other_order in other_moves:
                            if isinstance(other_order, MoveOrder) and other_order.target_province == unit.province:
                                # This is a mutual move (swap)
                                mutual_moves.append((unit, strength, order, other_unit, other_strength, other_order))
        
        # Process mutual moves first
        for unit1, strength1, order1, unit2, strength2, order2 in mutual_moves:
            # Both units bounce (standoff)
            results["moves"].append({
                "unit": f"{unit1.unit_type} {unit1.province}",
                "from": unit1.province,
                "to": order1.target_province,
                "strength": strength1,
                "success": False,
                "failure_reason": "bounced"
            })
            results["moves"].append({
                "unit": f"{unit2.unit_type} {unit2.province}",
                "from": unit2.province,
                "to": order2.target_province,
                "strength": strength2,
                "success": False,
                "failure_reason": "bounced"
            })
        
        # Process remaining moves (excluding mutual moves)
        processed_units = set()
        for unit1, strength1, order1, unit2, strength2, order2 in mutual_moves:
            processed_units.add(f"{unit1.unit_type} {unit1.province}")
            processed_units.add(f"{unit2.unit_type} {unit2.province}")
        
        # Resolve conflicts
        for target_province, moves in move_strengths.items():
            # Skip if this target province is involved in mutual moves
            skip_target = False
            for unit1, strength1, order1, unit2, strength2, order2 in mutual_moves:
                if target_province == order1.target_province or target_province == order2.target_province:
                    skip_target = True
                    break
            if skip_target:
                continue
            
            # Filter out processed units
            remaining_moves = [(unit, strength, order) for unit, strength, order in moves if f"{unit.unit_type} {unit.province}" not in processed_units]
            if not remaining_moves:
                continue
            if len(remaining_moves) == 1:
                # Single move - succeeds
                unit, strength, order = remaining_moves[0]
                old_province = unit.province
                
                # Add support strength
                if target_province in support_strengths:
                    for supporting_unit, support_strength in support_strengths[target_province]:
                        # Check if this support is for this specific move
                        if isinstance(order, MoveOrder):
                            # The support is for the target province, so it applies to any move to that province
                            strength += support_strength
                            break
                
                if isinstance(order, MoveOrder):
                    # Check for self-dislodgement
                    self_dislodgement = False
                    for power_name, power in self.game_state.powers.items():
                        for target_unit in power.units:
                            if target_unit.province == target_province and target_unit != unit and target_unit.power == unit.power:
                                # Self-dislodgement prohibited
                                self_dislodgement = True
                                break
                        if self_dislodgement:
                            break
                    
                    if self_dislodgement:
                        # Self-dislodgement prohibited - move fails
                        results["moves"].append({
                            "unit": f"{unit.unit_type} {old_province}",
                            "from": old_province,
                            "to": target_province,
                            "strength": strength,
                            "success": False,
                            "failure_reason": "self_dislodgement_prohibited"
                        })
                    else:
                        # Execute move
                        unit.province = target_province
                        results["moves"].append({
                            "unit": f"{unit.unit_type} {old_province}",
                            "from": old_province,
                            "to": target_province,
                            "strength": strength,
                            "success": True
                        })
                        
                        # Check if there's an enemy unit in the target province that needs to be dislodged
                        for power_name, power in self.game_state.powers.items():
                            for target_unit in power.units:
                                if target_unit.province == target_province and target_unit != unit:
                                    # This unit is being dislodged
                                    dislodged_from = target_unit.province
                                    target_unit.is_dislodged = True
                                    target_unit.province = f"DISLODGED_{dislodged_from}"
                                    target_unit.retreat_options = self._calculate_retreat_options(target_unit)
                                    
                                    results["dislodgements"].append({
                                        "unit": f"{target_unit.unit_type} {dislodged_from}",
                                        "dislodged_by": f"{unit.unit_type} {old_province}",
                                        "retreat_options": target_unit.retreat_options
                                    })
                                    results["dislodged_units"].append({
                                        "unit": f"{target_unit.unit_type} {dislodged_from}",
                                        "dislodged_by": f"{unit.unit_type} {old_province}",
                                        "retreat_options": target_unit.retreat_options
                                    })
                                    break
            else:
                # Multiple moves - resolve conflict
                # Add support strengths
                total_strengths = {}
                for unit, strength, order in remaining_moves:
                    unit_key = f"{unit.unit_type} {unit.province}"
                    if unit_key not in total_strengths:
                        total_strengths[unit_key] = 0
                    total_strengths[unit_key] += strength
                
                # Add support from support orders
                if target_province in support_strengths:
                    for supporting_unit, support_strength in support_strengths[target_province]:
                        # Find which unit this support is for by looking at the support order
                        for power_name, orders in self.game_state.orders.items():
                            for support_order in orders:
                                if isinstance(support_order, SupportOrder):
                                    if (support_order.unit == supporting_unit and 
                                        support_order.supported_target == target_province):
                                        # This support order is for this target province
                                        # Find the unit that this support is targeting
                                        supported_unit = support_order.supported_unit
                                        unit_key = f"{supported_unit.unit_type} {supported_unit.province}"
                                        if unit_key in total_strengths:
                                            total_strengths[unit_key] += support_strength
                                        break
                
                # Find winner
                max_strength = max(total_strengths.values())
                winners = [unit_key for unit_key, strength in total_strengths.items() if strength == max_strength]
                
                # Add conflict information
                conflict_info = {
                    "target": target_province,
                    "participants": list(total_strengths.keys()),
                    "strengths": total_strengths,
                    "winner": winners[0] if len(winners) == 1 else None
                }
                results["conflicts"].append(conflict_info)
                
                if len(winners) == 1:
                    # Single winner
                    winner_key = winners[0]
                    # Store original provinces before any modifications
                    unit_original_provinces = {}
                    for unit, strength, order in remaining_moves:
                        unit_original_provinces[id(unit)] = unit.province
                    
                    # Find the actual unit object
                    winner_unit = None
                    for unit, strength, order in remaining_moves:
                        if f"{unit.unit_type} {unit.province}" == winner_key:
                            winner_unit = unit
                            break
                    
                    if winner_unit:
                        old_province = winner_unit.province
                        
                        # Check for self-dislodgement
                        self_dislodgement = False
                        for power_name, power in self.game_state.powers.items():
                            for target_unit in power.units:
                                if (target_unit.province == target_province and 
                                    target_unit != winner_unit and 
                                    target_unit.power == winner_unit.power):
                                    # Self-dislodgement prohibited
                                    self_dislodgement = True
                                    break
                            if self_dislodgement:
                                break
                        
                        if self_dislodgement:
                            # Self-dislodgement prohibited - move fails
                            results["moves"].append({
                                "unit": f"{winner_unit.unit_type} {old_province}",
                                "from": old_province,
                                "to": target_province,
                                "strength": max_strength,
                                "success": False,
                                "failure_reason": "self_dislodgement_prohibited"
                            })
                        else:
                            # Execute winning move
                            winner_unit.province = target_province
                            results["moves"].append({
                                "unit": f"{winner_unit.unit_type} {old_province}",
                                "from": old_province,
                                "to": target_province,
                                "strength": max_strength,
                                "success": True
                            })
                            
                            # Dislodge other units that are currently in the target province
                            for power_name, power in self.game_state.powers.items():
                                for target_unit in power.units:
                                    if target_unit.province == target_province and target_unit != winner_unit:
                                        # This unit is being dislodged
                                        dislodged_from = target_unit.province
                                        target_unit.is_dislodged = True
                                        target_unit.province = f"DISLODGED_{dislodged_from}"
                                        target_unit.retreat_options = self._calculate_retreat_options(target_unit)
                                        
                                        results["dislodgements"].append({
                                            "unit": f"{target_unit.unit_type} {dislodged_from}",
                                            "dislodged_by": f"{winner_unit.unit_type} {old_province}",
                                            "retreat_options": target_unit.retreat_options
                                        })
                                        results["dislodged_units"].append({
                                            "unit": f"{target_unit.unit_type} {dislodged_from}",
                                            "dislodged_by": f"{winner_unit.unit_type} {old_province}",
                                            "retreat_options": target_unit.retreat_options
                                        })
                    
                    # Add failed moves for all non-winning units
                    for unit, strength, order in remaining_moves:
                        original_province = unit_original_provinces[id(unit)]
                        unit_key = f"{unit.unit_type} {original_province}"
                        if unit_key != winner_key:
                            results["moves"].append({
                                "unit": f"{unit.unit_type} {original_province}",
                                "from": original_province,
                                "to": target_province,
                                "strength": strength,
                                "success": False,
                                "failure_reason": "defeated"
                            })
                else:
                    # Multiple winners - standoff, no move
                    for unit, strength, order in remaining_moves:
                        if isinstance(order, MoveOrder):
                            results["moves"].append({
                                "unit": f"{unit.unit_type} {unit.province}",
                                "from": unit.province,
                                "to": target_province,
                                "strength": strength,
                                "success": False,
                                "failure_reason": "bounced"
                            })
        
        # Final convoy disruption check: Mark convoyed moves as failed if convoying fleets were dislodged
        convoy_disrupted_moves = []
        for move_result in results["moves"]:
            if move_result["success"]:
                # Find the original order for this move
                unit_str = move_result["unit"]
                target_province = move_result["to"]
                
                # Look for convoyed orders that match this move
                for power_name, orders in self.game_state.orders.items():
                    for order in orders:
                        if (isinstance(order, MoveOrder) and 
                            order.is_convoyed and
                            f"{order.unit.unit_type} {move_result['from']}" == unit_str and
                            order.target_province == target_province):
                            
                            # Check if any convoying fleet was dislodged
                            convoy_disrupted = False
                            for convoy_province in order.convoy_route:
                                # Find the convoying fleet at this province
                                convoying_fleet = None
                                for power_name_check, power in self.game_state.powers.items():
                                    for unit in power.units:
                                        if unit.province == convoy_province and unit.unit_type == "F":
                                            convoying_fleet = unit
                                            break
                                    if convoying_fleet:
                                        break
                                
                                if convoying_fleet:
                                    # Check if this convoying fleet was dislodged
                                    for power_name_check, power in self.game_state.powers.items():
                                        for convoy_unit in power.units:
                                            if (convoy_unit.province.startswith("DISLODGED_") and
                                                convoy_unit.unit_type == convoying_fleet.unit_type and
                                                convoy_unit.province.replace("DISLODGED_", "") == convoying_fleet.province.replace("DISLODGED_", "")):
                                                convoy_disrupted = True
                                                break
                                    if convoy_disrupted:
                                        break
                                if convoy_disrupted:
                                    break
                            
                            if convoy_disrupted:
                                convoy_disrupted_moves.append(move_result)
                                break
                    if convoy_disrupted_moves and convoy_disrupted_moves[-1] == move_result:
                        break
        
        # Mark convoy disrupted moves as failed and move units back
        for move_result in convoy_disrupted_moves:
            move_result["success"] = False
            move_result["failure_reason"] = "convoy_disrupted"
            
            # Move the unit back to its original province
            unit_str = move_result["unit"]
            from_province = move_result["from"]
            for power_name, power in self.game_state.powers.items():
                for unit in power.units:
                    # Check if this is the unit that moved (by matching unit type and current province)
                    if (f"{unit.unit_type} {unit.province}" == unit_str or
                        (unit.unit_type == unit_str.split()[0] and unit.province == move_result["to"])):
                        unit.province = from_province
                        break
        
        # Add hold orders to results
        for power_name, orders in self.game_state.orders.items():
            for order in orders:
                if isinstance(order, HoldOrder):
                    # Hold orders succeed unless the unit was dislodged
                    was_dislodged = any(d["unit"] == f"{order.unit.unit_type} {order.unit.province}" 
                                       for d in results["dislodged_units"])
                    
                    if not was_dislodged:
                        results["moves"].append({
                            "unit": f"{order.unit.unit_type} {order.unit.province}",
                            "from": order.unit.province,
                            "to": order.unit.province,
                            "strength": 1,
                            "success": True,
                            "action": "hold"
                        })
        
        return results

    def _calculate_convoy_strength(self, order: MoveOrder) -> int:
        """Calculate convoy strength for a convoyed move."""
        convoy_strength = 0
        convoyed_unit = order.unit
        
        for power_name, orders in self.game_state.orders.items():
            for convoy_order in orders:
                if isinstance(convoy_order, ConvoyOrder):
                    if (convoy_order.convoyed_unit == convoyed_unit and 
                        convoy_order.convoyed_target == order.target_province):
                        # Check if convoy path is valid
                        if self._is_valid_convoy_path(convoy_order, order):
                            convoy_strength += 1
        
        return convoy_strength

    def _is_valid_convoy_path(self, convoy_order: ConvoyOrder, move_order: MoveOrder) -> bool:
        """Check if a convoy path is valid."""
        # Use the comprehensive convoy route validation from ConvoyOrder
        convoy_validation_error = convoy_order._validate_convoy_route(self.game_state)
        return convoy_validation_error is None

    def _calculate_retreat_options(self, unit: Unit) -> List[str]:
        """Calculate valid retreat options for a dislodged unit."""
        retreat_options: List[str] = []
        current_province = unit.province.replace("DISLODGED_", "")
        
        # Get adjacent provinces
        province_data = self.game_state.map_data.provinces.get(current_province)
        if not province_data:
            return retreat_options
        
        for province_name in province_data.adjacent_provinces:
            # Check if province is valid for this unit type
            target_province = self.game_state.map_data.provinces.get(province_name)
            if not target_province:
                continue
            
            # Check if province is occupied
            occupied = False
            for power_name, power in self.game_state.powers.items():
                for other_unit in power.units:
                    if other_unit.province == province_name:
                        occupied = True
                        break
                if occupied:
                    break
            
            if not occupied:
                retreat_options.append(province_name)
        
        return retreat_options

    def _process_retreat_phase(self) -> Dict[str, Any]:
        """Process retreat phase."""
        results: Dict[str, List[Any]] = {
            "retreats": [],
            "disbands": []
        }
        
        # Process retreat orders
        for power_name, orders in self.game_state.orders.items():
            for order in orders:
                if isinstance(order, RetreatOrder):
                    # Validate retreat
                    if self._is_valid_retreat(order):
                        # Execute retreat
                        old_province = order.unit.province.replace("DISLODGED_", "")
                        order.unit.province = order.retreat_province
                        order.unit.is_dislodged = False
                        order.unit.retreat_options = []
                        
                        results["retreats"].append({
                            "unit": f"{order.unit.unit_type} {old_province}",
                            "to": order.retreat_province,
                            "success": True
                        })
                    else:
                        # Invalid retreat - unit is disbanded
                        results["disbands"].append({
                            "unit": f"{order.unit.unit_type} {order.unit.province.replace('DISLODGED_', '')}",
                            "reason": "invalid_retreat"
                        })
                        
                        # Remove unit from game
                        power = self.game_state.powers[power_name]
                        power.units = [u for u in power.units if u != order.unit]
        
        return results

    def _is_valid_retreat(self, order: RetreatOrder) -> bool:
        """Check if a retreat order is valid."""
        # Check if retreat province is adjacent
        current_province = order.unit.province.replace("DISLODGED_", "")
        province_data = self.game_state.map_data.provinces.get(current_province)
        if not province_data:
            return False
        
        if order.retreat_province not in province_data.adjacent_provinces:
            return False
        
        # Check if retreat province is occupied
        for power_name, power in self.game_state.powers.items():
            for unit in power.units:
                if unit.province == order.retreat_province:
                    return False
        
        return True

    def _update_supply_center_ownership(self) -> None:
        """Update supply center ownership based on unit occupation at end of Fall."""
        # Clear all current supply center ownership
        for power_state in self.game_state.powers.values():
            power_state.controlled_supply_centers.clear()
        
        # Determine ownership based on unit occupation
        for province_name, province in self.game_state.map_data.provinces.items():
            if province.is_supply_center:
                # Find unit occupying this supply center
                occupying_unit = self.game_state.get_unit_at_province(province_name)
                
                if occupying_unit:
                    # Unit occupies the supply center - power controls it
                    power_state = self.game_state.powers[occupying_unit.power]
                    power_state.controlled_supply_centers.append(province_name)
                else:
                    # No unit occupying - check if it was previously controlled
                    # For now, we'll leave it unowned (in a full implementation,
                    # we'd track the last occupier)
                    pass

    def _process_builds_phase(self) -> Dict[str, Any]:
        """Process builds phase with unit adjustments."""
        # First, update supply center ownership based on current unit positions
        if self.season == "Autumn":
            self._update_supply_center_ownership()
        
        results: Dict[str, List[Any]] = {
            "builds": [],
            "destroys": []
        }
        
        for power_name, orders in self.game_state.orders.items():
            power = self.game_state.powers[power_name]
            
            for order in orders:
                if isinstance(order, BuildOrder):
                    # Execute build
                    new_unit = Unit(
                        unit_type=order.build_type,
                        province=order.build_province,
                        power=power_name,
                        is_dislodged=False,
                        dislodged_by=None,
                        can_retreat=True,
                        retreat_options=[]
                    )
                    power.units.append(new_unit)
                    
                    results["builds"].append({
                        "unit": f"{order.build_type} {order.build_province}",
                        "power": power_name,
                        "success": True
                    })
                
                elif isinstance(order, DestroyOrder):
                    # Execute destroy
                    power.units = [u for u in power.units if u != order.destroy_unit]
                    
                    results["destroys"].append({
                        "unit": f"{order.destroy_unit.unit_type} {order.destroy_unit.province}",
                        "power": power_name,
                        "success": True
                    })
        
        # Check for victory condition after builds
        self._check_victory_condition()
        
        return results

    def _check_victory_condition(self) -> None:
        """Check if any power has achieved victory."""
        for power_name, power_state in self.game_state.powers.items():
            if len(power_state.controlled_supply_centers) >= 18:
                self.done = True
                self.game_state.status = GameStatus.COMPLETED
                # Store winner information
                if not hasattr(self, 'winner'):
                    self.winner = power_name
                break

    def _advance_phase(self) -> None:
        """Advance to the next phase."""
        if self.phase == "Movement":
            # Check if retreats are needed
            retreats_needed = False
            for power in self.game_state.powers.values():
                for unit in power.units:
                    if unit.is_dislodged:
                        retreats_needed = True
                        break
                if retreats_needed:
                    break
            
            if retreats_needed:
                self.phase = "Retreat"
            else:
                # After Spring Movement -> Autumn Movement
                # After Autumn Movement -> Builds
                if self.season == "Spring":
                    self.phase = "Movement"  # Go to Autumn Movement
                    self.season = "Autumn"
                else:  # Autumn
                    self.phase = "Builds"
        elif self.phase == "Retreat":
            # After Spring Retreat -> Autumn Movement
            # After Autumn Retreat -> Builds
            if self.season == "Spring":
                self.phase = "Movement"  # Go to Autumn Movement
                self.season = "Autumn"
            else:  # Autumn
                self.phase = "Builds"
        elif self.phase == "Builds":
            self.phase = "Movement"
            self.turn += 1
            if self.season == "Autumn":
                self.season = "Spring"
                self.year += 1
        
        self._update_phase_code()

    def _update_phase_code(self) -> None:
        """Update the phase code based on current year, season, and phase."""
        season_prefix = "S" if self.season == "Spring" else "A"
        phase_suffix = "M" if self.phase == "Movement" else "R" if self.phase == "Retreat" else "B"
        self.phase_code = f"{season_prefix}{self.year}{phase_suffix}"
        
        # Update new data model
        self.game_state.phase_code = self.phase_code
        self.game_state.current_turn = self.turn
        self.game_state.current_year = self.year
        self.game_state.current_season = self.season
        self.game_state.current_phase = self.phase
        self.game_state.updated_at = datetime.now()

    def get_state(self) -> Dict[str, Any]:
        """
        Get current game state for compatibility.
        
        Returns:
            Dictionary containing:
                - turn: Current turn number
                - year: Current game year
                - season: Current season (Spring/Autumn)
                - phase: Current phase (Movement/Retreat/Builds)
                - phase_code: Short phase code (e.g., "S1901M")
                - powers: List of power names in the game
                - units: Dictionary mapping powers to their unit lists
                - orders: Dictionary mapping powers to their order lists
                
        Note:
            This method provides a legacy-compatible interface for accessing
            game state information.
        """
        result = {
            "game_id": getattr(self, 'game_id', 'unknown'),
            "map_name": self.map_name,
            "turn": self.turn,
            "year": self.year,
            "season": self.season,
            "phase": self.phase,
            "phase_code": self.phase_code,
            "done": self.done,
            "powers": list(self.game_state.powers.keys()),
            "units": {power_name: [f"{u.unit_type} {u.province}" for u in power.units] 
                     for power_name, power in self.game_state.powers.items()},
            "orders": {power_name: [str(order) for order in orders] 
                      for power_name, orders in self.game_state.orders.items()}
        }
        
        # Add winner information if game is done
        if self.done and hasattr(self, 'winner'):
            result["winner"] = self.winner
            
        return result
    
    def get_game_state(self) -> 'GameState':
        """
        Get the game state using the new data model directly.
        
        Returns:
            GameState object containing the complete current game state
            
        Note:
            This method returns the full GameState object with all detailed
            information including units, orders, map data, and power states.
            Use this for applications that need access to the complete data model.
        """
        return self.game_state

    def is_game_done(self) -> bool:
        """
        Check if the game is done.
        
        Returns:
            True if the game has ended, False otherwise
            
        Note:
            A game is considered done when a power controls 18 or more
            supply centers, or when all other powers have been eliminated.
        """
        return self.done