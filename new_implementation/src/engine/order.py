"""
Order parsing and validation for Diplomacy.
- Defines order types and basic parsing/validation stubs.
"""
from typing import Optional, Dict, Any

class Order:
    """Represents a Diplomacy order (move, hold, support, convoy, etc.)."""
    def __init__(self, power: str, unit: str, action: str, target: Optional[str] = None) -> None:
        self.power: str = power
        self.unit: str = unit  # e.g., 'A PAR' or 'F BRE'
        self.action: str = action  # e.g., 'H', '-', 'S', 'C'
        self.target: Optional[str] = target  # e.g., 'BUR' for move, or 'A MAR' for support

    def __repr__(self) -> str:
        return f"Order({self.power}, {self.unit}, {self.action}, {self.target})"

class OrderParser:
    """Order parsing and validation for Diplomacy orders."""
    @staticmethod
    def parse(order_str: str) -> 'Order':
        # Parse order string: e.g. 'FRANCE A PAR - BUR' or 'FRANCE BUILD A PAR'
        tokens = order_str.strip().split()
        if len(tokens) < 3:
            raise ValueError("Invalid order format. Expected: <POWER> <ACTION> <TARGET?>")
        
        power: str = tokens[0]
        action: str = tokens[1]
        
        # Handle BUILD and DESTROY orders (different format)
        if action in {'BUILD', 'DESTROY'}:
            if len(tokens) < 3:
                raise ValueError(f"Invalid {action} order format. Expected: <POWER> {action} <UNIT_TYPE> <UNIT_LOC> [COAST?]")
            
            # For BUILD/DESTROY, the "unit" is actually the target specification
            # e.g., "FRANCE BUILD A PAR" -> unit="BUILD", target="A PAR"
            unit: str = action  # Use action as unit for BUILD/DESTROY
            target: Optional[str] = ' '.join(tokens[2:]) if len(tokens) > 2 else None
            return Order(power, unit, action, target)
        
        # Handle traditional orders: 'FRANCE A PAR - BUR' or 'FRANCE F BRE H'
        if len(tokens) < 4:
            # Check if this is an implicit hold order (e.g., "FRANCE F BRE")
            if len(tokens) == 3 and tokens[1] in {'A', 'F'}:
                unit_type: str = tokens[1]  # 'A' or 'F'
                unit_loc: str = tokens[2]   # e.g. 'BRE'
                action = "H"               # Implicit hold
                target = None
                unit: str = f"{unit_type} {unit_loc}"
                return Order(power, unit, action, target)
            else:
                raise ValueError("Invalid order format. Expected: <POWER> <UNIT_TYPE> <UNIT_LOC> <ACTION> <TARGET?>")
        
        unit_type: str = tokens[1]  # 'A' or 'F'
        unit_loc: str = tokens[2]   # e.g. 'PAR'
        action = tokens[3]          # '-', 'H', 'S', 'C', etc.

        # Handle multi-word targets (e.g., convoy, support)
        if len(tokens) > 4:
            target: Optional[str] = ' '.join(tokens[4:])
        else:
            target = None

        unit: str = f"{unit_type} {unit_loc}"
        return Order(power, unit, action, target)

    @staticmethod
    def validate(order: 'Order', game_state: Dict[str, Any]) -> tuple[bool, str]:
        # Enhanced validation with detailed error messages
        powers = game_state.get("powers", [])
        units = game_state.get("units", {})

        if order.power not in powers:
            return False, f"Power '{order.power}' does not exist."
        
        # Skip unit ownership check for BUILD/DESTROY orders
        if order.action not in {'BUILD', 'DESTROY'}:
            if order.power not in units or order.unit not in units[order.power]:
                return False, f"Unit '{order.unit}' does not belong to power '{order.power}'."
        valid_actions = {'-', 'H', 'S', 'C', 'BUILD', 'DESTROY'}
        if order.action not in valid_actions:
            return False, f"Invalid action '{order.action}'. Must be one of {valid_actions}."
        
        # Extract unit type for traditional orders
        if order.action not in {'BUILD', 'DESTROY'}:
            unit_type, _ = order.unit.split()
        else:
            unit_type = None  # Will be extracted from target for BUILD/DESTROY
        # Move validation
        if order.action == '-':
            if not order.target:
                return False, "Move order missing target."

            # Check adjacency for move orders
            unit_location = order.unit.split()[-1]  # Get the province from unit
            target_location = order.target.replace(' VIA CONVOY', '')  # Remove convoy marker

            # Get the map object from game state
            map_obj = game_state.get("map_obj")
            if map_obj:
                # Check if the move is to an adjacent province
                adjacent_provinces = map_obj.get_adjacency(unit_location)
                if target_location not in adjacent_provinces:
                    # Check if this could be a convoy move
                    if 'VIA CONVOY' in order.target:
                        # Allow convoy moves (they will be validated during processing)
                        pass
                    else:
                        # Check if there are any convoy orders that could support this move
                        # We need to check current orders for convoy orders
                        current_orders = game_state.get("orders", {})
                        power_orders = current_orders.get(order.power, [])

                        # Look for a convoy order that matches this move
                        has_convoy_support = False
                        for order_str in power_orders:
                            if ' C ' in order_str:
                                # This is a convoy order, check if it supports our move
                                convoy_target = order_str.split(' C ')[-1]
                                expected_convoy_target = f"{order.unit} - {target_location}"
                                if convoy_target == expected_convoy_target:
                                    has_convoy_support = True
                                    break

                        if not has_convoy_support:
                            return False, f"Cannot move from '{unit_location}' to '{target_location}' - not adjacent and no convoy support."
                # --- NEW: Check unit type vs province type ---
                target_prov = map_obj.get_province(target_location)
                if target_prov:
                    if unit_type == 'A' and target_prov.type == 'water':
                        return False, f"Army cannot move to water province '{target_location}'."
                    if unit_type == 'F' and target_prov.type == 'land':
                        return False, f"Fleet cannot move to land province '{target_location}'."
                # Fleets can move to 'water' or 'coast', armies to 'land' or 'coast'.
        # Support validation
        if order.action == 'S':
            if not order.target:
                return False, "Support order missing target."
            # Optionally, parse and check supported order
        # Convoy validation
        if order.action == 'C':
            if unit_type != 'F':
                return False, "Only fleets can perform convoy orders."
            if not order.target:
                return False, "Convoy order missing target."
        # Hold validation
        if order.action == 'H' and order.target:
            return False, "Hold order should not have a target."
        
        # Phase-aware validation
        current_phase = game_state.get("phase", "Movement")
        if order.action in {'BUILD', 'DESTROY'} and current_phase != "Builds":
            return False, f"{order.action} orders are only allowed during Builds phase, current phase is {current_phase}."
        
        # Retreat validation (movement orders during retreat phase)
        if order.action == '-' and current_phase == "Retreat":
            return OrderParser._validate_retreat_order(order, game_state)
        
        # Build order validation
        if order.action == 'BUILD':
            if not order.target:
                return False, "Build order missing target."
            # Parse build target (e.g., "A PAR" or "F STP/NC")
            build_parts = order.target.split()
            if len(build_parts) < 2:
                return False, "Build order must specify unit type and province (e.g., 'A PAR' or 'F STP/NC')."
            
            build_unit_type = build_parts[0]
            build_province = build_parts[1]
            
            if build_unit_type not in {'A', 'F'}:
                return False, f"Invalid build unit type '{build_unit_type}'. Must be 'A' or 'F'."
            
            # Check if player has excess supply centers (simplified check)
            supply_centers = game_state.get("supply_centers", {}).get(order.power, [])
            current_units = len(units.get(order.power, []))
            if len(supply_centers) <= current_units:
                return False, f"Cannot build - no excess supply centers. Have {len(supply_centers)} centers and {current_units} units."
            
            # Check if province is unoccupied
            all_units = []
            for power_units in units.values():
                all_units.extend(power_units)
            
            for unit in all_units:
                unit_province = unit.split()[-1]
                if unit_province == build_province:
                    return False, f"Cannot build in '{build_province}' - province is occupied."
            
            # Check if it's a home supply center (simplified - would need proper home center list)
            home_centers = game_state.get("home_centers", {}).get(order.power, [])
            if build_province not in home_centers:
                return False, f"Cannot build in '{build_province}' - not a home supply center."
            
            # Check multi-coast provinces (St. Petersburg)
            if build_province == "STP" and build_unit_type == 'F':
                if len(build_parts) < 3 or build_parts[2] not in {'NC', 'SC'}:
                    return False, "Fleet builds in St. Petersburg must specify coast (NC or SC)."
        
        # Destroy order validation
        if order.action == 'DESTROY':
            if not order.target:
                return False, "Destroy order missing target."
            
            # Parse destroy target (e.g., "A PAR")
            destroy_parts = order.target.split()
            if len(destroy_parts) < 2:
                return False, "Destroy order must specify unit type and province (e.g., 'A PAR')."
            
            destroy_unit_type = destroy_parts[0]
            destroy_province = destroy_parts[1]
            
            if destroy_unit_type not in {'A', 'F'}:
                return False, f"Invalid destroy unit type '{destroy_unit_type}'. Must be 'A' or 'F'."
            
            # Check if player has excess units (simplified check)
            supply_centers = game_state.get("supply_centers", {}).get(order.power, [])
            current_units = len(units.get(order.power, []))
            if len(supply_centers) >= current_units:
                return False, f"Cannot destroy - no excess units. Have {len(supply_centers)} centers and {current_units} units."
            
            # Check if unit exists and belongs to player
            target_unit = f"{destroy_unit_type} {destroy_province}"
            if target_unit not in units.get(order.power, []):
                return False, f"Cannot destroy '{target_unit}' - unit does not belong to {order.power}."
        
        return True, ""

    @staticmethod
    def generate_legal_orders(power: str, unit: str, game_state: dict) -> list[str]:
        """
        Generate all legal order strings for the given unit and power in the current game state.
        Args:
            power: The power (player) issuing the order (e.g., 'FRANCE').
            unit: The unit identifier (e.g., 'A PAR', 'F BRE').
            game_state: The current game state dict, must include 'units' and 'map_obj'.
        Returns:
            List of valid order strings for this unit (e.g., 'FRANCE A PAR - BUR', 'FRANCE A PAR H', ...).
        Logic:
            - Hold: Always legal for any unit.
            - Move: To any adjacent province (type-checked for army/fleet).
            - Support: Support hold or move for any adjacent unit (if adjacency allows).
            - Convoy: For fleets in water, convoy any adjacent army to any adjacent province.
        """
        orders = []
        units = game_state.get("units", {}).get(power, [])
        map_obj = game_state.get("map_obj")
        if unit not in units or map_obj is None:
            return []
        unit_type, unit_loc = unit.split()
        # Hold is always legal
        orders.append(f"{power} {unit} H")  # Hold order
        # Move orders
        for adj in map_obj.get_adjacency(unit_loc):
            target_prov = map_obj.get_province(adj)
            if not target_prov:
                continue
            if unit_type == 'A' and target_prov.type == 'water':
                continue  # Armies can't move to water
            if unit_type == 'F' and target_prov.type == 'land':
                continue  # Fleets can't move to land
            orders.append(f"{power} {unit} - {adj}")  # Move order
        # Support orders (support hold and support move for adjacent units)
        for other_power, other_units in game_state.get("units", {}).items():
            for other_unit in other_units:
                if other_unit == unit:
                    continue
                other_type, other_loc = other_unit.split()
                # Support hold (if adjacent)
                if map_obj.is_adjacent(unit_loc, other_loc):
                    orders.append(f"{power} {unit} S {other_unit} H")  # Support hold
                # Support move (if adjacent to both)
                for move_target in map_obj.get_adjacency(other_loc):
                    if map_obj.is_adjacent(unit_loc, other_loc):
                        orders.append(f"{power} {unit} S {other_unit} - {move_target}")  # Support move
        # Convoy orders (only for fleets in water)
        if unit_type == 'F' and map_obj.get_province(unit_loc).type == 'water':
            # Find all armies that could be convoyed
            for other_power, other_units in game_state.get("units", {}).items():
                for other_unit in other_units:
                    if other_unit == unit:
                        continue
                    o_type, o_loc = other_unit.split()
                    if o_type != 'A':
                        continue
                    # If this fleet is adjacent to the army, allow convoy
                    if map_obj.is_adjacent(unit_loc, o_loc):
                        # Try all possible destinations for the army
                        for dest in map_obj.get_adjacency(unit_loc):
                            orders.append(f"{power} {unit} C {other_unit} - {dest}")  # Convoy order
        return orders
    
    @staticmethod
    def _validate_retreat_order(order: 'Order', game_state: Dict[str, Any]) -> tuple[bool, str]:
        """Validate retreat orders with specific retreat rules."""
        if not order.target:
            return False, "Retreat order missing target."
        
        unit_location = order.unit.split()[-1]  # Get the province from unit
        retreat_destination = order.target
        
        # Check if unit was dislodged (simplified check)
        dislodged_units = game_state.get("dislodged_units", {}).get(order.power, [])
        if order.unit not in dislodged_units:
            return False, f"Unit '{order.unit}' was not dislodged and cannot retreat."
        
        # Get the map object from game state
        map_obj = game_state.get("map_obj")
        if not map_obj:
            return False, "Map object required for retreat validation."
        
        # Check if retreat destination is adjacent
        adjacent_provinces = map_obj.get_adjacency(unit_location)
        if retreat_destination not in adjacent_provinces:
            return False, f"Cannot retreat to '{retreat_destination}' - not adjacent to '{unit_location}'."
        
        # Check if retreat destination is occupied
        all_units = []
        for power_units in game_state.get("units", {}).values():
            all_units.extend(power_units)
        
        for unit in all_units:
            unit_province = unit.split()[-1]
            if unit_province == retreat_destination:
                return False, f"Cannot retreat to '{retreat_destination}' - province is occupied."
        
        # Check if retreat destination is the attacker's origin province
        attacker_origins = game_state.get("attacker_origins", {}).get(order.unit, [])
        if retreat_destination in attacker_origins:
            return False, f"Cannot retreat to '{retreat_destination}' - attacker came from this province."
        
        # Check if retreat destination was left vacant by standoff
        standoff_vacated = game_state.get("standoff_vacated", [])
        if retreat_destination in standoff_vacated:
            return False, f"Cannot retreat to '{retreat_destination}' - province was left vacant by standoff."
        
        # Check unit type vs province type
        unit_type, _ = order.unit.split()
        target_prov = map_obj.get_province(retreat_destination)
        if target_prov:
            if unit_type == 'A' and target_prov.type == 'water':
                return False, f"Army cannot retreat to water province '{retreat_destination}'."
            if unit_type == 'F' and target_prov.type == 'land':
                return False, f"Fleet cannot retreat to land province '{retreat_destination}'."
        
        return True, ""
