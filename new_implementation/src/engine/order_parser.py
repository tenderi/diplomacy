"""
Enhanced order parser for Diplomacy game engine.

This module implements proper order parsing and validation using the new data models
to ensure correct order-to-unit mapping and power ownership validation.
"""

import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from .data_models import (
    Order, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, 
    RetreatOrder, BuildOrder, DestroyOrder, OrderType, OrderStatus,
    Unit, GameState, PowerState
)


class OrderParseError(Exception):
    """Exception raised when order parsing fails"""
    pass


class OrderValidationError(Exception):
    """Exception raised when order validation fails"""
    pass


@dataclass
class ParsedOrder:
    """Result of order parsing"""
    order_type: OrderType
    power: str
    unit_type: str
    unit_province: str
    target_province: Optional[str] = None
    supported_unit_type: Optional[str] = None
    supported_unit_province: Optional[str] = None
    supported_target: Optional[str] = None
    convoyed_unit_type: Optional[str] = None
    convoyed_unit_province: Optional[str] = None
    convoyed_target: Optional[str] = None
    convoy_chain: List[str] = None
    retreat_province: Optional[str] = None
    build_type: Optional[str] = None
    build_province: Optional[str] = None
    build_coast: Optional[str] = None
    destroy_unit_type: Optional[str] = None
    destroy_unit_province: Optional[str] = None
    raw_text: str = ""


class OrderParser:
    """Enhanced order parser with proper validation"""
    
    def __init__(self):
        # Order patterns
        self.move_pattern = re.compile(r'^([AF])\s+([A-Z]{3})\s*-\s*([A-Z]{3})$', re.IGNORECASE)
        self.hold_pattern = re.compile(r'^([AF])\s+([A-Z]{3})\s*(?:H)?$', re.IGNORECASE)
        self.support_pattern = re.compile(r'^([AF])\s+([A-Z]{3})\s+S\s+([AF])\s+([A-Z]{3})(?:\s*-\s*([A-Z]{3}))?$', re.IGNORECASE)
        self.convoy_pattern = re.compile(r'^([AF])\s+([A-Z]{3})\s+C\s+([AF])\s+([A-Z]{3})\s*-\s*([A-Z]{3})$', re.IGNORECASE)
        self.retreat_pattern = re.compile(r'^([AF])\s+([A-Z]{3})\s+R\s+([A-Z]{3})$', re.IGNORECASE)
        self.build_pattern = re.compile(r'^BUILD\s+([AF])\s+([A-Z]{3})(?:/([A-Z]{2}))?$', re.IGNORECASE)
        self.destroy_pattern = re.compile(r'^DESTROY\s+([AF])\s+([A-Z]{3})$', re.IGNORECASE)
        
        # Power names for validation
        self.valid_powers = {
            'ENGLAND', 'FRANCE', 'GERMANY', 'RUSSIA', 
            'TURKEY', 'AUSTRIA', 'ITALY'
        }
    
    def parse_order_text(self, order_text: str, power: str) -> ParsedOrder:
        """
        Parse order text into structured data.
        
        Args:
            order_text: Raw order text (e.g., "A PAR - BUR" or "GERMANY A PAR - BUR")
            power: Power name submitting the order
            
        Returns:
            ParsedOrder object with parsed data
            
        Raises:
            OrderParseError: If order cannot be parsed
        """
        # Clean and normalize input
        order_text = order_text.strip()
        
        # Remove power name if present (e.g., "GERMANY A PAR - BUR" -> "A PAR - BUR")
        parts = order_text.split()
        if len(parts) > 3 and parts[0].upper() in self.valid_powers:
            # Power name is first, remove it
            order_text = ' '.join(parts[1:])
        
        # Try each order type pattern
        parsed = self._try_move_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_hold_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_support_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_convoy_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_retreat_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_build_order(order_text, power)
        if parsed:
            return parsed
            
        parsed = self._try_destroy_order(order_text, power)
        if parsed:
            return parsed
        
        raise OrderParseError(f"Unable to parse order: '{order_text}'")
    
    def _try_move_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as move order"""
        match = self.move_pattern.match(order_text)
        if match:
            unit_type, unit_province, target_province = match.groups()
            return ParsedOrder(
                order_type=OrderType.MOVE,
                power=power,
                unit_type=unit_type.upper(),
                unit_province=unit_province.upper(),
                target_province=target_province.upper(),
                raw_text=order_text
            )
        return None
    
    def _try_hold_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as hold order"""
        match = self.hold_pattern.match(order_text)
        if match:
            unit_type, unit_province = match.groups()
            return ParsedOrder(
                order_type=OrderType.HOLD,
                power=power,
                unit_type=unit_type.upper(),
                unit_province=unit_province.upper(),
                raw_text=order_text
            )
        return None
    
    def _try_support_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as support order"""
        match = self.support_pattern.match(order_text)
        if match:
            unit_type, unit_province, supported_unit_type, supported_unit_province, supported_target = match.groups()
            return ParsedOrder(
                order_type=OrderType.SUPPORT,
                power=power,
                unit_type=unit_type.upper(),
                unit_province=unit_province.upper(),
                supported_unit_type=supported_unit_type.upper(),
                supported_unit_province=supported_unit_province.upper(),
                supported_target=supported_target.upper() if supported_target else None,
                raw_text=order_text
            )
        return None
    
    def _try_convoy_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as convoy order"""
        match = self.convoy_pattern.match(order_text)
        if match:
            unit_type, unit_province, convoyed_unit_type, convoyed_unit_province, convoyed_target = match.groups()
            return ParsedOrder(
                order_type=OrderType.CONVOY,
                power=power,
                unit_type=unit_type.upper(),
                unit_province=unit_province.upper(),
                convoyed_unit_type=convoyed_unit_type.upper(),
                convoyed_unit_province=convoyed_unit_province.upper(),
                convoyed_target=convoyed_target.upper(),
                raw_text=order_text
            )
        return None
    
    def _try_retreat_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as retreat order"""
        match = self.retreat_pattern.match(order_text)
        if match:
            unit_type, unit_province, retreat_province = match.groups()
            return ParsedOrder(
                order_type=OrderType.RETREAT,
                power=power,
                unit_type=unit_type.upper(),
                unit_province=unit_province.upper(),
                retreat_province=retreat_province.upper(),
                raw_text=order_text
            )
        return None
    
    def _try_build_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as build order"""
        match = self.build_pattern.match(order_text)
        if match:
            build_type, build_province, build_coast = match.groups()
            return ParsedOrder(
                order_type=OrderType.BUILD,
                power=power,
                unit_type="",  # Build orders don't have existing units
                unit_province="",  # Build orders don't have existing units
                build_type=build_type.upper(),
                build_province=build_province.upper(),
                build_coast=build_coast.upper() if build_coast else None,
                raw_text=order_text
            )
        return None
    
    def _try_destroy_order(self, order_text: str, power: str) -> Optional[ParsedOrder]:
        """Try to parse as destroy order"""
        match = self.destroy_pattern.match(order_text)
        if match:
            destroy_unit_type, destroy_unit_province = match.groups()
            return ParsedOrder(
                order_type=OrderType.DESTROY,
                power=power,
                unit_type="",  # Destroy orders don't have existing units
                unit_province="",  # Destroy orders don't have existing units
                destroy_unit_type=destroy_unit_type.upper(),
                destroy_unit_province=destroy_unit_province.upper(),
                raw_text=order_text
            )
        return None
    
    def create_order_from_parsed(self, parsed: ParsedOrder, game_state: GameState) -> Order:
        """
        Create Order object from parsed data.
        
        Args:
            parsed: ParsedOrder object
            game_state: Current game state for validation
            
        Returns:
            Order object
            
        Raises:
            OrderValidationError: If order cannot be created or validated
        """
        # Validate power exists
        if parsed.power not in game_state.powers:
            raise OrderValidationError(f"Power {parsed.power} does not exist in game")
        
        power_state = game_state.powers[parsed.power]
        
        # Create appropriate order type
        if parsed.order_type == OrderType.MOVE:
            return self._create_move_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.HOLD:
            return self._create_hold_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.SUPPORT:
            return self._create_support_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.CONVOY:
            return self._create_convoy_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.RETREAT:
            return self._create_retreat_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.BUILD:
            return self._create_build_order(parsed, power_state, game_state)
        elif parsed.order_type == OrderType.DESTROY:
            return self._create_destroy_order(parsed, power_state, game_state)
        else:
            raise OrderValidationError(f"Unknown order type: {parsed.order_type}")
    
    def _create_move_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> MoveOrder:
        """Create MoveOrder from parsed data"""
        # Find the unit
        unit = self._find_unit(parsed.unit_type, parsed.unit_province, power_state)
        
        return MoveOrder(
            power=parsed.power,
            unit=unit,
            order_type=OrderType.MOVE,
            phase=game_state.current_phase,
            target_province=parsed.target_province
        )
    
    def _create_hold_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> HoldOrder:
        """Create HoldOrder from parsed data"""
        unit = self._find_unit(parsed.unit_type, parsed.unit_province, power_state)
        
        return HoldOrder(
            power=parsed.power,
            unit=unit,
            order_type=OrderType.HOLD,
            phase=game_state.current_phase
        )
    
    def _create_support_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> SupportOrder:
        """Create SupportOrder from parsed data"""
        unit = self._find_unit(parsed.unit_type, parsed.unit_province, power_state)
        
        # Find supported unit
        supported_unit = self._find_unit_in_game(
            parsed.supported_unit_type, 
            parsed.supported_unit_province, 
            game_state
        )
        
        return SupportOrder(
            power=parsed.power,
            unit=unit,
            order_type=OrderType.SUPPORT,
            phase=game_state.current_phase,
            supported_unit=supported_unit,
            supported_action="move" if parsed.supported_target else "hold",
            supported_target=parsed.supported_target
        )
    
    def _create_convoy_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> ConvoyOrder:
        """Create ConvoyOrder from parsed data"""
        unit = self._find_unit(parsed.unit_type, parsed.unit_province, power_state)
        
        # Find convoyed unit
        convoyed_unit = self._find_unit_in_game(
            parsed.convoyed_unit_type,
            parsed.convoyed_unit_province,
            game_state
        )
        
        return ConvoyOrder(
            power=parsed.power,
            unit=unit,
            order_type=OrderType.CONVOY,
            phase=game_state.current_phase,
            convoyed_unit=convoyed_unit,
            convoyed_target=parsed.convoyed_target
        )
    
    def _create_retreat_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> RetreatOrder:
        """Create RetreatOrder from parsed data"""
        unit = self._find_unit(parsed.unit_type, parsed.unit_province, power_state)
        
        return RetreatOrder(
            power=parsed.power,
            unit=unit,
            order_type=OrderType.RETREAT,
            phase=game_state.current_phase,
            retreat_province=parsed.retreat_province
        )
    
    def _create_build_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> BuildOrder:
        """Create BuildOrder from parsed data"""
        # Build orders don't have existing units
        dummy_unit = Unit(
            unit_type="",
            province="",
            power=parsed.power
        )
        
        return BuildOrder(
            power=parsed.power,
            unit=dummy_unit,
            order_type=OrderType.BUILD,
            phase=game_state.current_phase,
            build_province=parsed.build_province,
            build_type=parsed.build_type,
            build_coast=parsed.build_coast
        )
    
    def _create_destroy_order(self, parsed: ParsedOrder, power_state: PowerState, game_state: GameState) -> DestroyOrder:
        """Create DestroyOrder from parsed data"""
        # Find the unit to destroy
        destroy_unit = self._find_unit(parsed.destroy_unit_type, parsed.destroy_unit_province, power_state)
        
        # Destroy orders don't have existing units
        dummy_unit = Unit(
            unit_type="",
            province="",
            power=parsed.power
        )
        
        return DestroyOrder(
            power=parsed.power,
            unit=dummy_unit,
            order_type=OrderType.DESTROY,
            phase=game_state.current_phase,
            destroy_unit=destroy_unit
        )
    
    def _find_unit(self, unit_type: str, province: str, power_state: PowerState) -> Unit:
        """Find unit in power's units"""
        for unit in power_state.units:
            if unit.unit_type == unit_type and unit.province == province:
                return unit
        
        raise OrderValidationError(f"Unit {unit_type} {province} not found for power {power_state.power_name}")
    
    def _find_unit_in_game(self, unit_type: str, province: str, game_state: GameState) -> Unit:
        """Find unit anywhere in game"""
        for unit in game_state.get_all_units():
            if unit.unit_type == unit_type and unit.province == province:
                return unit
        
        raise OrderValidationError(f"Unit {unit_type} {province} not found in game")
    
    def parse_orders(self, orders_text: str, power: str) -> List[ParsedOrder]:
        """
        Parse multiple orders from text.
        
        Args:
            orders_text: Orders separated by semicolons or newlines
            power: Power name submitting the orders
            
        Returns:
            List of ParsedOrder objects
        """
        # Split by semicolons or newlines
        order_lines = re.split(r'[;\n]', orders_text)
        
        parsed_orders = []
        for line in order_lines:
            line = line.strip()
            if line:
                try:
                    parsed = self.parse_order_text(line, power)
                    parsed_orders.append(parsed)
                except OrderParseError as e:
                    # Log error but continue with other orders
                    print(f"Warning: Failed to parse order '{line}': {e}")
        
        return parsed_orders
    
    def validate_orders(self, orders: List[Order], game_state: GameState) -> List[Tuple[bool, str]]:
        """
        Validate list of orders against game state.
        
        Args:
            orders: List of Order objects
            game_state: Current game state
            
        Returns:
            List of (success, error_message) tuples
        """
        results = []
        
        for order in orders:
            try:
                # Check if order type is valid for current phase
                if not game_state.is_valid_phase_for_order_type(order.order_type):
                    results.append((False, f"Order type {order.order_type.value} not valid for phase {game_state.current_phase}"))
                    continue
                
                # Validate the order
                valid, reason = order.validate(game_state)
                results.append((valid, reason))
                
            except Exception as e:
                results.append((False, f"Validation error: {str(e)}"))
        
        return results
