"""
Order parsing and validation for Diplomacy using new data models.
- Defines order parsing/validation using the new Order data models.
"""
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING
from .data_models import (
    OrderType, OrderStatus, Unit, MoveOrder, HoldOrder, SupportOrder, 
    ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder
)

if TYPE_CHECKING:
    from .game import Game
    from .data_models import GameState, Province


class OrderParser:
    """Order parsing and validation for Diplomacy orders using new data models."""

    @staticmethod
    def parse_order_string(order_str: str, power_name: str, game_instance: 'Game') -> Optional[Any]:
        """Parse a single order string into an Order data model object."""
        tokens = order_str.strip().split()
        if not tokens:
            raise ValueError("Empty order string")

        # Find the unit associated with the order
        unit_str_parts = []
        unit_type = None
        unit_province = None

        # Try to find unit in the format "A PAR" or "F BRE"
        # Orders can be like "GERMANY A BER - HOL" or "A BER - HOL"
        start_idx = 0
        if tokens[0].upper() == power_name.upper() and len(tokens) > 1:
            start_idx = 1 # Skip power name if present

        if len(tokens) > start_idx + 1 and tokens[start_idx].upper() in ['A', 'F']:
            unit_type = tokens[start_idx].upper()
            unit_province = tokens[start_idx + 1].upper()
            unit_str_parts = [unit_type, unit_province]

        unit_obj = None
        if unit_type and unit_province:
            # Parse coast specification if present
            coast = None
            if '/' in unit_province:
                unit_province, coast = unit_province.split('/')
            
            # Find the actual Unit object from the game state
            for unit in game_instance.game_state.powers[power_name].units:
                # Handle both normal units and dislodged units
                # Match province and coast (if specified)
                province_match = (unit.province == unit_province or 
                                unit.province == f"DISLODGED_{unit_province}")
                coast_match = (coast is None or unit.coast == coast)
                
                if (unit.unit_type == unit_type and province_match and coast_match):
                    unit_obj = unit
                    break
        
        # Handle BUILD and DESTROY orders (different format)
        if tokens[start_idx].upper() == 'BUILD':
            if len(tokens) < start_idx + 3:
                raise ValueError("Invalid BUILD order: missing unit type and province")
            build_unit_type = tokens[start_idx + 1].upper()
            build_province = tokens[start_idx + 2].upper()
            build_coast = None
            if '/' in build_province:
                build_province, build_coast = build_province.split('/')
            
            # For build orders, unit_obj is not directly applicable, but we need power
            return BuildOrder(
                power=power_name,
                unit=None,  # Build orders don't have a unit initially
                build_province=build_province,
                build_type=build_unit_type,
                build_coast=build_coast,
                status=OrderStatus.PENDING
            )
        elif tokens[start_idx].upper() == 'DESTROY':
            if len(tokens) < start_idx + 3:
                raise ValueError("Invalid DESTROY order: missing unit type and province")
            destroy_unit_type = tokens[start_idx + 1].upper()
            destroy_province = tokens[start_idx + 2].upper()
            
            destroy_unit_obj = None
            for unit in game_instance.game_state.powers[power_name].units:
                if unit.unit_type == destroy_unit_type and unit.province == destroy_province:
                    destroy_unit_obj = unit
                    break
            
            if not destroy_unit_obj:
                raise ValueError(f"Unit to destroy {destroy_unit_type} {destroy_province} not found for power {power_name}")

            return DestroyOrder(
                power=power_name,
                unit=destroy_unit_obj,  # The unit giving the order
                destroy_unit=destroy_unit_obj,  # The unit to be destroyed
                status=OrderStatus.PENDING
            )

        if not unit_obj:
            raise ValueError(f"Unit {unit_type} {unit_province} not found for power {power_name}")

        action_idx = start_idx + 2
        if len(tokens) <= action_idx: # Implicit hold
            return HoldOrder(power=power_name, unit=unit_obj, status=OrderStatus.PENDING)

        action = tokens[action_idx].upper()

        if action == '-': # Move order
            if len(tokens) <= action_idx + 1:
                raise ValueError("Move order missing target province")
            target_province = tokens[action_idx + 1].upper()
            is_convoyed = False
            if len(tokens) > action_idx + 2 and tokens[action_idx + 2].upper() == 'VIA' and \
               len(tokens) > action_idx + 3 and tokens[action_idx + 3].upper() == 'CONVOY':
                is_convoyed = True
            return MoveOrder(
                power=power_name,
                unit=unit_obj,
                target_province=target_province,
                is_convoyed=is_convoyed,
                status=OrderStatus.PENDING
            )
        elif action == 'H': # Hold order
            return HoldOrder(power=power_name, unit=unit_obj, status=OrderStatus.PENDING)
        elif action == 'S': # Support order
            if len(tokens) <= action_idx + 3:
                raise ValueError("Support order missing supported unit/action")
            supported_unit_type = tokens[action_idx + 1].upper()
            supported_unit_province = tokens[action_idx + 2].upper()
            supported_action = tokens[action_idx + 3].upper()
            supported_target = None
            if supported_action == '-' and len(tokens) > action_idx + 4:
                supported_target = tokens[action_idx + 4].upper()

            supported_unit_obj = None
            for unit in game_instance.game_state.get_all_units():
                if unit.unit_type == supported_unit_type and unit.province == supported_unit_province:
                    supported_unit_obj = unit
                    break
            
            if not supported_unit_obj:
                raise ValueError("Supported unit not found")

            return SupportOrder(
                power=power_name,
                unit=unit_obj,
                supported_unit=supported_unit_obj,
                supported_action=supported_action,
                supported_target=supported_target,
                status=OrderStatus.PENDING
            )
        elif action == 'C': # Convoy order
            if len(tokens) <= action_idx + 4:
                raise ValueError("Convoy order missing convoyed unit/target")
            convoyed_unit_type = tokens[action_idx + 1].upper()
            convoyed_unit_province = tokens[action_idx + 2].upper()
            convoyed_action = tokens[action_idx + 3].upper() # Should be '-'
            convoyed_target = tokens[action_idx + 4].upper()

            convoyed_unit_obj = None
            for unit in game_instance.game_state.get_all_units():
                if unit.unit_type == convoyed_unit_type and unit.province == convoyed_unit_province:
                    convoyed_unit_obj = unit
                    break
            
            if not convoyed_unit_obj:
                raise ValueError("Convoyed unit not found")

            return ConvoyOrder(
                power=power_name,
                unit=unit_obj,
                convoyed_unit=convoyed_unit_obj,
                convoyed_target=convoyed_target,
                status=OrderStatus.PENDING
            )
        elif action == 'R': # Retreat order (special case, usually handled by game engine)
            if len(tokens) <= action_idx + 1:
                raise ValueError("Retreat order missing target province")
            target_province = tokens[action_idx + 1].upper()
            return RetreatOrder(
                power=power_name,
                unit=unit_obj,
                retreat_province=target_province,
                status=OrderStatus.PENDING
            )
        
        raise ValueError("Unknown order type")

    @staticmethod
    def parse_orders_list(order_strings: List[str], power_name: str, game_instance: 'Game') -> List[Any]:
        """Parse a list of order strings into a list of Order data model objects."""
        parsed_orders = []
        for order_str in order_strings:
            order = OrderParser.parse_order_string(order_str, power_name, game_instance)
            parsed_orders.append(order)
        return parsed_orders

    @staticmethod
    def validate_order(order: Any, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate an order using its own validate method."""
        if hasattr(order, 'validate'):
            return order.validate(game_state)
        return False, "Invalid order object or missing validation method."

    @staticmethod
    def generate_legal_orders(power_name: str, unit_str: str, game_state: 'GameState') -> List[str]:
        """
        Generate all legal order strings for the given unit and power in the current game state.
        This method will return string representations of orders, not Order objects.
        """
        orders_strings = []
        
        power_state = game_state.powers.get(power_name)
        if not power_state:
            return []

        unit_obj = None
        for u in power_state.units:
            if f"{u.unit_type} {u.province}" == unit_str:
                unit_obj = u
                break
        
        if not unit_obj:
            return []

        unit_type = unit_obj.unit_type
        unit_loc = unit_obj.province
        
        map_data = game_state.map_data
        current_province_data = map_data.provinces.get(unit_loc)

        if not current_province_data:
            return []

        # Hold is always legal
        orders_strings.append(f"{power_name} {unit_str} H")

        # Move orders
        for adj_name in current_province_data.adjacent_provinces:
            target_prov_data = map_data.provinces.get(adj_name)
            if not target_prov_data:
                continue

            is_valid_move = False
            if unit_type == 'A' and target_prov_data.province_type in ['land', 'coastal']:
                is_valid_move = True
            elif unit_type == 'F' and target_prov_data.province_type in ['sea', 'coastal']:
                is_valid_move = True
            
            if is_valid_move:
                orders_strings.append(f"{power_name} {unit_str} - {adj_name}")

        # Support orders
        for other_power_name, other_power_state in game_state.powers.items():
            for other_unit_obj in other_power_state.units:
                if other_unit_obj == unit_obj:
                    continue
                
                other_loc = other_unit_obj.province
                other_province_data = map_data.provinces.get(other_loc)

                if not other_province_data:
                    continue

                # Check if supporting unit can reach the supported unit's location
                if current_province_data.is_adjacent_to(other_loc):
                    # Support Hold
                    orders_strings.append(f"{power_name} {unit_str} S {other_unit_obj.unit_type} {other_unit_obj.province} H")

                    # Support Move
                    for move_target_name in other_province_data.adjacent_provinces:
                        move_target_data = map_data.provinces.get(move_target_name)
                        if not move_target_data:
                            continue
                        
                        is_valid_support_move_target = False
                        if other_unit_obj.unit_type == 'A' and move_target_data.province_type in ['land', 'coastal']:
                            is_valid_support_move_target = True
                        elif other_unit_obj.unit_type == 'F' and move_target_data.province_type in ['sea', 'coastal']:
                            is_valid_support_move_target = True

                        if is_valid_support_move_target:
                            orders_strings.append(f"{power_name} {unit_str} S {other_unit_obj.unit_type} {other_unit_obj.province} - {move_target_name}")

        # Convoy orders (only for fleets in sea areas)
        if unit_type == 'F' and current_province_data.province_type == 'sea':
            # Find all armies that could be convoyed
            for other_power_name, other_power_state in game_state.powers.items():
                for army_unit_obj in other_power_state.units:
                    if army_unit_obj.unit_type != 'A':
                        continue
                    
                    army_loc = army_unit_obj.province
                    army_province_data = map_data.provinces.get(army_loc)

                    if not army_province_data or army_province_data.province_type not in ['land', 'coastal']:
                        continue # Army must be in a land or coastal province

                    # If this fleet is adjacent to the army's province (coastal adjacency)
                    if current_province_data.is_adjacent_to(army_loc):
                        # Try all possible coastal destinations for the army that are adjacent to the fleet's sea area
                        for dest_name in current_province_data.adjacent_provinces:
                            dest_province_data = map_data.provinces.get(dest_name)
                            if dest_province_data and dest_province_data.province_type == 'coastal':
                                orders_strings.append(f"{power_name} {unit_str} C {army_unit_obj.unit_type} {army_unit_obj.province} - {dest_name}")
        
        return orders_strings