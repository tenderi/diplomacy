"""
Strategic AI for automated demo games using proper data models.

This module implements AI strategies that use the data_spec.md models exclusively,
ensuring proper data integrity and demonstrating all Diplomacy mechanics.
"""

from typing import Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass
import random
import logging

from .data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder
)
from .order import OrderParser

logger = logging.getLogger(__name__)


@dataclass
class StrategicConfig:
    """Configuration for AI strategic behavior"""
    aggression_level: float = 0.7  # 0.0 to 1.0
    support_probability: float = 0.3  # Probability of giving support
    convoy_probability: float = 0.2  # Probability of using convoy
    defensive_probability: float = 0.4  # Probability of defensive moves
    expansion_probability: float = 0.6  # Probability of expansion moves


class StrategicAI:
    """AI that generates strategic orders using proper data models"""
    
    def __init__(self, config: Optional[StrategicConfig] = None):
        self.config = config or StrategicConfig()
        self.order_parser = OrderParser()
        
    def generate_orders(self, game_state: GameState, power: str) -> Sequence[Order]:
        """
        Generate orders for a specific power using proper data models.
        
        Args:
            game_state: Current state of the game containing all powers and units
            power: Name of the power to generate orders for (e.g., "FRANCE", "GERMANY")
            
        Returns:
            Sequence of Order objects representing the AI's strategic decisions
            for the current phase (Movement, Retreat, or Builds)
            
        Note:
            The AI will generate different types of orders based on the current
            game phase and strategic configuration settings.
        """
        if power not in game_state.powers:
            logger.warning(f"Power {power} not found in game state")
            return []
            
        power_state = game_state.powers[power]
        
        if game_state.current_phase == "Movement":
            return self._generate_movement_orders(game_state, power_state)
        elif game_state.current_phase == "Retreat":
            return self._generate_retreat_orders(game_state, power_state)
        elif game_state.current_phase == "Builds":
            return self._generate_build_orders(game_state, power_state)
        else:
            logger.warning(f"Unknown phase: {game_state.current_phase}")
            return []
    
    def _generate_movement_orders(self, game_state: GameState, power_state: PowerState) -> Sequence[Order]:
        """Generate movement orders using proper Order data models"""
        orders = []
        
        for unit in power_state.units:
            if unit.is_dislodged:
                continue  # Skip dislodged units in movement phase
                
            # Determine strategic action for this unit
            action = self._determine_unit_action(game_state, unit)
            
            order: Optional[Order] = None
            if action == "move":
                order = self._create_move_order(game_state, unit)
            elif action == "support":
                order = self._create_support_order(game_state, unit)
            elif action == "convoy":
                order = self._create_convoy_order(game_state, unit)
            else:  # hold
                order = self._create_hold_order(unit)
                
            if order:
                orders.append(order)
                
        return orders
    
    def _generate_retreat_orders(self, game_state: GameState, power_state: PowerState) -> Sequence[Order]:
        """Generate retreat orders for dislodged units"""
        orders = []
        
        for unit in power_state.units:
            if unit.is_dislodged and unit.can_retreat:
                if unit.retreat_options:
                    # Choose first available retreat option
                    retreat_province = unit.retreat_options[0]
                    order = RetreatOrder(
                        power=unit.power,
                        unit=unit,
                        order_type=OrderType.RETREAT,
                        phase=game_state.current_phase,
                        retreat_province=retreat_province
                    )
                    orders.append(order)
                else:
                    # No retreat options, unit will be disbanded
                    logger.info(f"Unit {unit} has no retreat options, will be disbanded")
        
        return orders
    
    def _generate_build_orders(self, game_state: GameState, power_state: PowerState) -> Sequence[Order]:
        """Generate build/destroy orders based on supply center control"""
        orders: List[Order] = []
        
        # Check if power needs to build or destroy units
        supply_center_count = len(power_state.controlled_supply_centers)
        unit_count = len(power_state.units)
        
        if unit_count < supply_center_count:
            # Need to build units
            builds_needed = supply_center_count - unit_count
            available_build_provinces = self._get_available_build_provinces(game_state, power_state)
            
            for i in range(min(builds_needed, len(available_build_provinces))):
                build_province = available_build_provinces[i]
                build_type = self._determine_build_type(game_state, build_province)
                
                order = BuildOrder(
                    power=power_state.power_name,
                    order_type=OrderType.BUILD,
                    phase=game_state.current_phase,
                    build_province=build_province,
                    build_type=build_type
                )
                orders.append(order)
                
        elif unit_count > supply_center_count:
            # Need to destroy units
            destroys_needed = unit_count - supply_center_count
            destroyable_units = self._get_destroyable_units(power_state)
            
            for i in range(min(destroys_needed, len(destroyable_units))):
                unit_to_destroy = destroyable_units[i]
                
                destroy_order = DestroyOrder(
                    power=power_state.power_name,
                    order_type=OrderType.DESTROY,
                    phase=game_state.current_phase,
                    destroy_unit=unit_to_destroy
                )
                orders.append(destroy_order)
        
        return orders
    
    def _determine_unit_action(self, game_state: GameState, unit: Unit) -> str:
        """Determine what action a unit should take"""
        # Strategic decision making based on game state
        if random.random() < self.config.aggression_level:
            if random.random() < self.config.support_probability:
                return "support"
            elif random.random() < self.config.convoy_probability and unit.unit_type == "F":
                return "convoy"
            else:
                return "move"
        else:
            if random.random() < self.config.defensive_probability:
                return "hold"
            else:
                return "move"
    
    def _create_move_order(self, game_state: GameState, unit: Unit) -> Optional[MoveOrder]:
        """Create a move order using proper data models"""
        target_province = self._find_move_target(game_state, unit)
        if not target_province:
            return None
            
        return MoveOrder(
            power=unit.power,
            unit=unit,
            order_type=OrderType.MOVE,
            phase=game_state.current_phase,
            target_province=target_province
        )
    
    def _create_hold_order(self, unit: Unit) -> HoldOrder:
        """Create a hold order using proper data models"""
        return HoldOrder(
            power=unit.power,
            unit=unit,
            order_type=OrderType.HOLD,
            phase="Movement"  # Hold orders are always movement phase
        )
    
    def _create_support_order(self, game_state: GameState, unit: Unit) -> Optional[SupportOrder]:
        """Create a support order using proper data models"""
        # Find a unit to support
        supported_unit = self._find_support_target(game_state, unit)
        if not supported_unit:
            return None
            
        # Determine if supporting a move or hold
        if random.random() < 0.5:  # 50% chance to support a move
            supported_target = self._find_move_target(game_state, supported_unit)
            if supported_target:
                return SupportOrder(
                    power=unit.power,
                    unit=unit,
                    order_type=OrderType.SUPPORT,
                    phase=game_state.current_phase,
                    supported_unit=supported_unit,
                    supported_action="move",
                    supported_target=supported_target
                )
        
        # Support hold
        return SupportOrder(
            power=unit.power,
            unit=unit,
            order_type=OrderType.SUPPORT,
            phase=game_state.current_phase,
            supported_unit=supported_unit,
            supported_action="hold"
        )
    
    def _create_convoy_order(self, game_state: GameState, unit: Unit) -> Optional[ConvoyOrder]:
        """Create a convoy order using proper data models"""
        if unit.unit_type != "F":
            return None
            
        # Find an army to convoy
        convoyed_unit = self._find_convoy_target(game_state, unit)
        if not convoyed_unit:
            return None
            
        convoy_target = self._find_convoy_destination(game_state, convoyed_unit)
        if not convoy_target:
            return None
            
        return ConvoyOrder(
            power=unit.power,
            unit=unit,
            order_type=OrderType.CONVOY,
            phase=game_state.current_phase,
            convoyed_unit=convoyed_unit,
            convoyed_target=convoy_target
        )
    
    def _find_move_target(self, game_state: GameState, unit: Unit) -> Optional[str]:
        """Find a valid move target for a unit using map data"""
        if unit.province not in game_state.map_data.provinces:
            return None
            
        province_data = game_state.map_data.provinces[unit.province]
        adjacent_provinces = province_data.adjacent_provinces
        
        # Filter valid targets based on unit type
        valid_targets = []
        for target in adjacent_provinces:
            if target in game_state.map_data.provinces:
                target_data = game_state.map_data.provinces[target]
                
                # Check if move is legal based on unit type and target province type
                if unit.can_move_to_province_type(target_data.province_type):
                    valid_targets.append(target)
        
        # Choose a target (prefer unoccupied provinces)
        unoccupied_targets = [t for t in valid_targets if not game_state.get_unit_at_province(t)]
        if unoccupied_targets:
            return random.choice(unoccupied_targets)
        elif valid_targets:
            return random.choice(valid_targets)
        
        return None
    
    def _find_support_target(self, game_state: GameState, unit: Unit) -> Optional[Unit]:
        """Find a unit to support"""
        # Get all units from the same power
        power_units = game_state.get_power_units(unit.power)
        
        # Filter out the current unit and find adjacent units
        adjacent_units = []
        if unit.province in game_state.map_data.provinces:
            province_data = game_state.map_data.provinces[unit.province]
            for target_province in province_data.adjacent_provinces:
                target_unit = game_state.get_unit_at_province(target_province)
                if target_unit and target_unit.power == unit.power and target_unit != unit:
                    adjacent_units.append(target_unit)
        
        if adjacent_units:
            return random.choice(adjacent_units)
        
        return None
    
    def _find_convoy_target(self, game_state: GameState, unit: Unit) -> Optional[Unit]:
        """Find an army to convoy"""
        # Get all armies from the same power
        power_units = game_state.get_power_units(unit.power)
        armies = [u for u in power_units if u.unit_type == "A" and u != unit]
        
        if armies:
            return random.choice(armies)
        
        return None
    
    def _find_convoy_destination(self, game_state: GameState, army: Unit) -> Optional[str]:
        """Find a convoy destination for an army"""
        # Find coastal provinces that the army can move to via convoy
        coastal_provinces = []
        for province_name, province_data in game_state.map_data.provinces.items():
            if province_data.province_type == "coastal":
                coastal_provinces.append(province_name)
        
        if coastal_provinces:
            return random.choice(coastal_provinces)
        
        return None
    
    def _get_available_build_provinces(self, game_state: GameState, power_state: PowerState) -> List[str]:
        """Get available provinces for building units"""
        available_provinces = []
        
        for province_name in power_state.home_supply_centers:
            # Check if province is unoccupied
            if not game_state.get_unit_at_province(province_name):
                available_provinces.append(province_name)
        
        return available_provinces
    
    def _determine_build_type(self, game_state: GameState, province: str) -> str:
        """Determine whether to build army or fleet"""
        if province in game_state.map_data.provinces:
            province_data = game_state.map_data.provinces[province]
            if province_data.province_type == "coastal":
                # Randomly choose army or fleet for coastal provinces
                return "F" if random.random() < 0.5 else "A"
            else:
                return "A"  # Land provinces get armies
        
        return "A"  # Default to army
    
    def _get_destroyable_units(self, power_state: PowerState) -> List[Unit]:
        """Get units that can be destroyed"""
        # Return all units (simplified - in real game, might have strategic preferences)
        return power_state.units.copy()


class OrderGenerator:
    """Helper class for generating orders using proper data models"""
    
    def __init__(self):
        self.order_parser = OrderParser()
    
    def create_order_from_string(self, order_string: str, power: str, game_state: GameState) -> Optional[Order]:
        """
        Create an Order object from a string representation.
        
        Args:
            order_string: String representation of the order (e.g., "A PAR - BUR")
            power: Name of the power submitting the order
            game_state: Current game state for validation
            
        Returns:
            Order object if parsing and validation succeed, None otherwise
            
        Example:
            >>> generator = OrderGenerator()
            >>> order = generator.create_order_from_string("A PAR - BUR", "FRANCE", game_state)
            >>> print(order.target_province)  # "BUR"
        """
        try:
            # Parse the order string
            parsed_order = self.order_parser.parse_order(order_string)
            if not parsed_order:
                return None
            
            # Find the unit
            unit = game_state.get_unit_at_province(parsed_order['unit_province'])
            if not unit or unit.power != power:
                return None
            
            # Create appropriate Order object based on type
            order_type = parsed_order['order_type']
            
            if order_type == "move":
                return MoveOrder(
                    power=power,
                    unit=unit,
                    order_type=OrderType.MOVE,
                    phase=game_state.current_phase,
                    target_province=parsed_order['target_province']
                )
            elif order_type == "hold":
                return HoldOrder(
                    power=power,
                    unit=unit,
                    order_type=OrderType.HOLD,
                    phase=game_state.current_phase
                )
            elif order_type == "support":
                supported_unit = game_state.get_unit_at_province(parsed_order['supported_unit_province'])
                if not supported_unit:
                    return None
                    
                return SupportOrder(
                    power=power,
                    unit=unit,
                    order_type=OrderType.SUPPORT,
                    phase=game_state.current_phase,
                    supported_unit=supported_unit,
                    supported_action=parsed_order.get('supported_action', 'hold'),
                    supported_target=parsed_order.get('supported_target')
                )
            elif order_type == "convoy":
                convoyed_unit = game_state.get_unit_at_province(parsed_order['convoyed_unit_province'])
                if not convoyed_unit:
                    return None
                    
                return ConvoyOrder(
                    power=power,
                    unit=unit,
                    order_type=OrderType.CONVOY,
                    phase=game_state.current_phase,
                    convoyed_unit=convoyed_unit,
                    convoyed_target=parsed_order['convoyed_target']
                )
            elif order_type == "retreat":
                return RetreatOrder(
                    power=power,
                    unit=unit,
                    order_type=OrderType.RETREAT,
                    phase=game_state.current_phase,
                    retreat_province=parsed_order['retreat_province']
                )
            elif order_type == "build":
                return BuildOrder(
                    power=power,
                    order_type=OrderType.BUILD,
                    phase=game_state.current_phase,
                    build_province=parsed_order['build_province'],
                    build_type=parsed_order['build_type']
                )
            elif order_type == "destroy":
                destroy_unit = game_state.get_unit_at_province(parsed_order['destroy_unit_province'])
                if not destroy_unit:
                    return None
                    
                return DestroyOrder(
                    power=power,
                    order_type=OrderType.DESTROY,
                    phase=game_state.current_phase,
                    destroy_unit=destroy_unit
                )
            
        except Exception as e:
            logger.error(f"Error creating order from string '{order_string}': {e}")
            return None
        
        return None
    
    def validate_orders(self, orders: List[Order], game_state: GameState) -> List[Tuple[bool, str]]:
        """
        Validate a list of orders against the current game state.
        
        Args:
            orders: List of Order objects to validate
            game_state: Current game state for validation context
            
        Returns:
            List of tuples containing (is_valid, error_message) for each order
            
        Note:
            Each order is validated individually. Invalid orders will have
            error messages explaining why they failed validation.
        """
        results = []
        
        for order in orders:
            try:
                is_valid, error_message = order.validate(game_state)
                results.append((is_valid, error_message))
            except Exception as e:
                results.append((False, f"Validation error: {e}"))
        
        return results
