"""
Core data models for Diplomacy game engine.

This module implements the comprehensive data structures defined in data_spec.md
to ensure proper data integrity and validation throughout the game.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum


class OrderType(Enum):
    """Order types in Diplomacy"""
    MOVE = "move"
    HOLD = "hold"
    SUPPORT = "support"
    CONVOY = "convoy"
    RETREAT = "retreat"
    BUILD = "build"
    DESTROY = "destroy"


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    BOUNCED = "bounced"


class GameStatus(Enum):
    """Game status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class Unit:
    """Individual unit representation"""
    unit_type: str  # "A" (Army) or "F" (Fleet)
    province: str
    power: str
    is_dislodged: bool = False
    dislodged_by: Optional[str] = None  # province of attacking unit
    can_retreat: bool = True
    retreat_options: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.unit_type} {self.province}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_type": self.unit_type,
            "province": self.province,
            "power": self.power,
            "is_dislodged": self.is_dislodged,
            "dislodged_by": self.dislodged_by,
            "can_retreat": self.can_retreat,
            "retreat_options": self.retreat_options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Unit':
        return cls(
            unit_type=data["unit_type"],
            province=data["province"],
            power=data["power"],
            is_dislodged=data.get("is_dislodged", False),
            dislodged_by=data.get("dislodged_by"),
            can_retreat=data.get("can_retreat", True),
            retreat_options=data.get("retreat_options", [])
        )


@dataclass
class Province:
    """Individual province representation"""
    name: str
    province_type: str  # "land", "sea", "coastal"
    is_supply_center: bool
    is_home_supply_center: bool
    home_power: Optional[str] = None
    adjacent_provinces: List[str] = field(default_factory=list)
    coastal_provinces: List[str] = field(default_factory=list)  # For fleets
    coordinates: Tuple[int, int] = (0, 0)  # For map rendering
    
    def is_adjacent_to(self, other_province: str) -> bool:
        return other_province in self.adjacent_provinces
    
    def can_fleet_move_to(self, other_province: str) -> bool:
        """Check if fleet can move to another province"""
        if other_province in self.adjacent_provinces:
            return True
        # Check coastal adjacency for fleets
        return other_province in self.coastal_provinces


@dataclass
class MapData:
    """Complete map representation"""
    map_name: str
    provinces: Dict[str, Province]
    supply_centers: List[str]
    home_supply_centers: Dict[str, List[str]]  # power -> provinces
    starting_positions: Dict[str, List[Unit]]  # power -> starting units


@dataclass
class Order:
    """Base order class"""
    power: str
    unit: Unit
    order_type: OrderType
    phase: str  # Phase when order is valid
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate order against current game state"""
        # Basic validation - to be implemented by subclasses
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        return True, ""


@dataclass
class MoveOrder:
    """Movement order"""
    power: str
    unit: Unit
    order_type: OrderType = OrderType.MOVE
    phase: str = "Movement"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    target_province: str = ""
    is_convoyed: bool = False
    convoy_route: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.unit} - {self.target_province}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate move order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Check if target province exists
        if self.target_province not in game_state.map_data.provinces:
            return False, f"Target province {self.target_province} does not exist"
        
        # Check adjacency (skip if no adjacencies defined)
        # Note: Non-adjacent moves are allowed as they might be convoyed
        # Adjacency will be validated during order processing when convoy status is determined
        current_province = game_state.map_data.provinces[self.unit.province]
        target_province_obj = game_state.map_data.provinces[self.target_province]
        
        # Allow non-adjacent moves for armies to sea/coast provinces (likely convoyed)
        # or if there are no adjacencies defined
        if (current_province.adjacent_provinces and 
            not current_province.is_adjacent_to(self.target_province) and
            not (self.unit.unit_type == 'A' and target_province_obj.province_type in ['water', 'coast'])):
            return False, f"{self.unit.province} is not adjacent to {self.target_province}"
        
        return True, ""
    
    def _is_potentially_convoyed(self, game_state: 'GameState') -> bool:
        """Check if this move might be convoyed by looking for convoy orders."""
        # Look for convoy orders that could convoy this unit
        for power_name, orders in game_state.orders.items():
            for order in orders:
                if hasattr(order, 'convoyed_unit') and hasattr(order, 'convoyed_target'):
                    if (order.convoyed_unit == self.unit and 
                        order.convoyed_target == self.target_province):
                        return True
        return False


@dataclass
class HoldOrder:
    """Hold order"""
    power: str
    unit: Unit
    order_type: OrderType = OrderType.HOLD
    phase: str = "Movement"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.unit} H"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate hold order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        return True, ""


@dataclass
class SupportOrder:
    """Support order"""
    power: str
    unit: Unit
    supported_unit: Unit
    supported_action: str  # "move" or "hold"
    order_type: OrderType = OrderType.SUPPORT
    phase: str = "Movement"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    supported_target: Optional[str] = None  # For move support
    
    def __str__(self) -> str:
        if self.supported_action == "move":
            return f"{self.unit} S {self.supported_unit} - {self.supported_target}"
        else:
            return f"{self.unit} S {self.supported_unit}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate support order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Check if supported unit exists
        if not any(u.province == self.supported_unit.province and u.power == self.supported_unit.power 
                  for u in game_state.get_all_units()):
            return False, f"Supported unit {self.supported_unit} does not exist"
        
        return True, ""


@dataclass
class ConvoyOrder:
    """Convoy order"""
    power: str
    unit: Unit
    convoyed_unit: Unit
    convoyed_target: str
    order_type: OrderType = OrderType.CONVOY
    phase: str = "Movement"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    convoy_chain: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.unit} C {self.convoyed_unit} - {self.convoyed_target}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate convoy order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Only fleets can convoy
        if self.unit.unit_type != "F":
            return False, f"Only fleets can convoy, not {self.unit.unit_type}"
        
        # Check if convoyed unit exists
        if not any(u.province == self.convoyed_unit.province and u.power == self.convoyed_unit.power 
                  for u in game_state.get_all_units()):
            return False, f"Convoyed unit {self.convoyed_unit} does not exist"
        
        return True, ""


@dataclass
class RetreatOrder:
    """Retreat order"""
    power: str
    unit: Unit
    retreat_province: str
    order_type: OrderType = OrderType.RETREAT
    phase: str = "Retreat"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    
    def __str__(self) -> str:
        return f"{self.unit} R {self.retreat_province}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate retreat order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Unit must be dislodged
        if not self.unit.is_dislodged:
            return False, f"Unit {self.unit} is not dislodged"
        
        # Retreat province must be valid
        if self.retreat_province not in self.unit.retreat_options:
            return False, f"Invalid retreat destination {self.retreat_province}"
        
        return True, ""


@dataclass
class BuildOrder:
    """Build order"""
    power: str
    unit: Unit
    build_province: str
    build_type: str  # "A" or "F"
    order_type: OrderType = OrderType.BUILD
    phase: str = "Builds"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    build_coast: Optional[str] = None  # For multi-coast provinces
    
    def __str__(self) -> str:
        coast_suffix = f"/{self.build_coast}" if self.build_coast else ""
        return f"BUILD {self.build_type} {self.build_province}{coast_suffix}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate build order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Check if build province is home supply center
        if self.build_province not in game_state.map_data.home_supply_centers.get(self.power, []):
            return False, f"{self.build_province} is not a home supply center for {self.power}"
        
        # Check if province is unoccupied
        if any(u.province == self.build_province for u in game_state.get_all_units()):
            return False, f"{self.build_province} is occupied"
        
        return True, ""


@dataclass
class DestroyOrder:
    """Destroy order"""
    power: str
    unit: Unit
    destroy_unit: Unit
    order_type: OrderType = OrderType.DESTROY
    phase: str = "Builds"
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    
    def __str__(self) -> str:
        return f"DESTROY {self.destroy_unit}"
    
    def validate(self, game_state: 'GameState') -> Tuple[bool, str]:
        """Validate destroy order"""
        if self.unit.power != self.power:
            return False, f"Unit {self.unit} does not belong to power {self.power}"
        
        # Check if destroy unit belongs to power
        if self.destroy_unit.power != self.power:
            return False, f"Cannot destroy unit {self.destroy_unit} belonging to {self.destroy_unit.power}"
        
        return True, ""


@dataclass
class PowerState:
    """Individual power (player) state"""
    power_name: str
    user_id: Optional[int] = None  # Telegram user ID if human player
    is_active: bool = True
    is_eliminated: bool = False
    home_supply_centers: List[str] = field(default_factory=list)
    controlled_supply_centers: List[str] = field(default_factory=list)
    units: List[Unit] = field(default_factory=list)
    orders_submitted: bool = False
    last_order_time: Optional[datetime] = None
    
    # Phase-specific data
    retreat_options: Dict[str, List[str]] = field(default_factory=dict)  # unit -> valid retreat provinces
    build_options: List[str] = field(default_factory=list)  # available build provinces
    destroy_options: List[str] = field(default_factory=list)  # units that can be destroyed
    
    def get_unit_count(self) -> int:
        return len(self.units)
    
    def get_supply_center_count(self) -> int:
        return len(self.controlled_supply_centers)
    
    def needs_builds(self) -> bool:
        return self.get_supply_center_count() > self.get_unit_count()
    
    def needs_destroys(self) -> bool:
        return self.get_unit_count() > self.get_supply_center_count()


@dataclass
class OrderResult:
    """Result of order execution"""
    order: Order
    success: bool
    failure_reason: Optional[str] = None
    dislodged_units: List[Unit] = field(default_factory=list)
    retreat_required: bool = False


@dataclass
class TurnState:
    """State of a single turn"""
    turn_number: int
    year: int
    season: str
    phase: str
    phase_code: str
    orders: Dict[str, List[Order]]
    results: Dict[str, List[OrderResult]]
    units_before: Dict[str, List[Unit]]
    units_after: Dict[str, List[Unit]]
    supply_centers_before: Dict[str, str]
    supply_centers_after: Dict[str, str]
    timestamp: datetime


@dataclass
class MapSnapshot:
    """Snapshot of map state at specific point"""
    turn_number: int
    phase_code: str
    units: Dict[str, List[Unit]]
    supply_centers: Dict[str, str]
    map_image_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GameState:
    """Complete game state representation"""
    game_id: str
    map_name: str
    current_turn: int
    current_year: int
    current_season: str  # "Spring" or "Autumn"
    current_phase: str   # "Movement", "Retreat", "Builds"
    phase_code: str      # e.g., "S1901M", "A1901R", "A1901B"
    status: GameStatus
    created_at: datetime
    updated_at: datetime
    
    # Core game data
    powers: Dict[str, PowerState]
    map_data: MapData
    orders: Dict[str, List[Order]]  # power -> orders for current phase
    pending_retreats: Dict[str, List[RetreatOrder]] = field(default_factory=dict)  # power -> retreat orders
    pending_builds: Dict[str, List[BuildOrder]] = field(default_factory=dict)     # power -> build orders
    pending_destroys: Dict[str, List[DestroyOrder]] = field(default_factory=dict) # power -> destroy orders
    
    # Game history
    turn_history: List[TurnState] = field(default_factory=list)
    order_history: List[Dict[str, List[Order]]] = field(default_factory=list)  # Historical orders
    map_snapshots: List[MapSnapshot] = field(default_factory=list)
    
    def get_all_units(self) -> List[Unit]:
        """Get all units from all powers"""
        all_units = []
        for power_state in self.powers.values():
            all_units.extend(power_state.units)
        return all_units
    
    def get_unit_at_province(self, province: str) -> Optional[Unit]:
        """Get unit at specific province"""
        for unit in self.get_all_units():
            if unit.province == province:
                return unit
        return None
    
    def get_power_units(self, power: str) -> List[Unit]:
        """Get units for specific power"""
        return self.powers.get(power, PowerState(power_name=power)).units
    
    def get_supply_centers(self) -> Dict[str, str]:
        """Get supply center ownership"""
        supply_centers = {}
        for power_state in self.powers.values():
            for province in power_state.controlled_supply_centers:
                supply_centers[province] = power_state.power_name
        return supply_centers
    
    def is_valid_phase_for_order_type(self, order_type: OrderType) -> bool:
        """Check if order type is valid for current phase"""
        if self.current_phase == "Movement":
            return order_type in [OrderType.MOVE, OrderType.HOLD, OrderType.SUPPORT, OrderType.CONVOY]
        elif self.current_phase == "Retreat":
            return order_type in [OrderType.RETREAT, OrderType.DESTROY]
        elif self.current_phase == "Builds":
            return order_type in [OrderType.BUILD, OrderType.DESTROY]
        return False
    
    def validate_game_state(self) -> Tuple[bool, List[str]]:
        """Validate entire game state for consistency"""
        errors = []
        
        # Check unit positions
        occupied_provinces = set()
        for unit in self.get_all_units():
            if unit.province in occupied_provinces:
                errors.append(f"Multiple units in province {unit.province}")
            occupied_provinces.add(unit.province)
        
        # Check supply center counts
        for power_name, power_state in self.powers.items():
            if not power_state.is_eliminated:
                unit_count = power_state.get_unit_count()
                supply_count = power_state.get_supply_center_count()
                if unit_count != supply_count and self.current_phase != "Builds":
                    errors.append(f"{power_name} has {unit_count} units but {supply_count} supply centers")
        
        # Check unit ownership consistency
        for power_name, power_state in self.powers.items():
            for unit in power_state.units:
                if unit.power != power_name:
                    errors.append(f"Unit {unit} belongs to {unit.power} but is in {power_name}'s units list")
        
        # Check supply center ownership consistency
        supply_centers = self.get_supply_centers()
        for power_name, power_state in self.powers.items():
            for province in power_state.controlled_supply_centers:
                if supply_centers.get(province) != power_name:
                    errors.append(f"Supply center {province} controlled by {power_name} but ownership shows {supply_centers.get(province)}")
        
        # Check phase consistency
        if self.current_phase not in ["Movement", "Retreat", "Builds"]:
            errors.append(f"Invalid phase: {self.current_phase}")
        
        # Check season consistency
        if self.current_season not in ["Spring", "Autumn"]:
            errors.append(f"Invalid season: {self.current_season}")
        
        # Check phase code format
        expected_phase_code = self._generate_phase_code()
        if self.phase_code != expected_phase_code:
            errors.append(f"Phase code mismatch: expected {expected_phase_code}, got {self.phase_code}")
        
        # Check orders consistency
        for power_name, orders in self.orders.items():
            if power_name not in self.powers:
                errors.append(f"Orders for non-existent power: {power_name}")
            
            for order in orders:
                if order.power != power_name:
                    errors.append(f"Order {order} belongs to {order.power} but is in {power_name}'s orders")
                
                # Check if order is valid for current phase
                if not self.is_valid_phase_for_order_type(order.order_type):
                    errors.append(f"Order {order} type {order.order_type.value} not valid for phase {self.current_phase}")
        
        return len(errors) == 0, errors
    
    def _generate_phase_code(self) -> str:
        """Generate expected phase code based on current state"""
        season_code = "S" if self.current_season == "Spring" else "A"
        year_code = str(self.current_year)  # Use full year
        
        if self.current_phase == "Movement":
            phase_code = "M"
        elif self.current_phase == "Retreat":
            phase_code = "R"
        elif self.current_phase == "Builds":
            phase_code = "B"
        else:
            phase_code = "?"
        
        return f"{season_code}{year_code}{phase_code}"
    
    def validate_orders_for_phase(self) -> Tuple[bool, List[str]]:
        """Validate all orders for current phase"""
        errors = []
        
        for power_name, orders in self.orders.items():
            if power_name not in self.powers:
                errors.append(f"Orders for non-existent power: {power_name}")
                continue
            
            power_state = self.powers[power_name]
            
            for order in orders:
                # Validate order against game state
                valid, reason = order.validate(self)
                if not valid:
                    errors.append(f"{power_name} order {order}: {reason}")
                
                # Check if order type is valid for current phase
                if not self.is_valid_phase_for_order_type(order.order_type):
                    errors.append(f"{power_name} order {order}: type {order.order_type.value} not valid for phase {self.current_phase}")
        
        return len(errors) == 0, errors
    
    def validate_unit_positions(self) -> Tuple[bool, List[str]]:
        """Validate unit positions and adjacencies"""
        errors = []
        
        for unit in self.get_all_units():
            # Check if unit province exists in map
            if unit.province not in self.map_data.provinces:
                errors.append(f"Unit {unit} in non-existent province {unit.province}")
                continue
            
            province = self.map_data.provinces[unit.province]
            
            # Check if unit type is valid for province
            if unit.unit_type == "F" and province.province_type == "land":
                errors.append(f"Fleet {unit} in land province {unit.province}")
            elif unit.unit_type == "A" and province.province_type == "sea":
                errors.append(f"Army {unit} in sea province {unit.province}")
        
        return len(errors) == 0, errors
    
    def validate_supply_centers(self) -> Tuple[bool, List[str]]:
        """Validate supply center ownership"""
        errors = []
        
        # Check that all supply centers are owned by someone
        for province_name, province in self.map_data.provinces.items():
            if province.is_supply_center:
                supply_centers = self.get_supply_centers()
                if province_name not in supply_centers:
                    errors.append(f"Supply center {province_name} is not owned by any power")
        
        # Check that all claimed supply centers are actual supply centers
        for power_name, power_state in self.powers.items():
            for province in power_state.controlled_supply_centers:
                if province not in self.map_data.provinces:
                    errors.append(f"{power_name} claims non-existent province {province}")
                elif not self.map_data.provinces[province].is_supply_center:
                    errors.append(f"{power_name} claims non-supply center {province}")
        
        return len(errors) == 0, errors
    
    def validate_power_states(self) -> Tuple[bool, List[str]]:
        """Validate power states"""
        errors = []
        
        for power_name, power_state in self.powers.items():
            # Check unit count vs supply center count
            unit_count = power_state.get_unit_count()
            supply_count = power_state.get_supply_center_count()
            
            if self.current_phase == "Builds":
                # During builds phase, counts can be different
                if unit_count > supply_count:
                    errors.append(f"{power_name} has {unit_count} units but only {supply_count} supply centers (needs destroys)")
                elif unit_count < supply_count:
                    errors.append(f"{power_name} has {supply_count} supply centers but only {unit_count} units (can build)")
            else:
                # During other phases, counts must match
                if unit_count != supply_count:
                    errors.append(f"{power_name} has {unit_count} units but {supply_count} supply centers")
            
            # Check that all units belong to this power
            for unit in power_state.units:
                if unit.power != power_name:
                    errors.append(f"Unit {unit} in {power_name}'s units but belongs to {unit.power}")
            
            # Check that all claimed supply centers are actually controlled
            supply_centers = self.get_supply_centers()
            for province in power_state.controlled_supply_centers:
                if supply_centers.get(province) != power_name:
                    errors.append(f"{power_name} claims {province} but it's controlled by {supply_centers.get(province)}")
        
        return len(errors) == 0, errors
    
    def get_validation_report(self) -> str:
        """Get comprehensive validation report"""
        report = []
        report.append(f"Game State Validation Report for {self.game_id}")
        report.append(f"Turn: {self.current_turn}, Year: {self.current_year}, Season: {self.current_season}, Phase: {self.current_phase}")
        report.append("=" * 60)
        
        # Overall game state validation
        valid, errors = self.validate_game_state()
        if valid:
            report.append("✅ Overall game state: VALID")
        else:
            report.append("❌ Overall game state: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        report.append("")
        
        # Unit positions validation
        valid, errors = self.validate_unit_positions()
        if valid:
            report.append("✅ Unit positions: VALID")
        else:
            report.append("❌ Unit positions: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        report.append("")
        
        # Supply centers validation
        valid, errors = self.validate_supply_centers()
        if valid:
            report.append("✅ Supply centers: VALID")
        else:
            report.append("❌ Supply centers: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        report.append("")
        
        # Power states validation
        valid, errors = self.validate_power_states()
        if valid:
            report.append("✅ Power states: VALID")
        else:
            report.append("❌ Power states: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        report.append("")
        
        # Orders validation
        valid, errors = self.validate_orders_for_phase()
        if valid:
            report.append("✅ Orders: VALID")
        else:
            report.append("❌ Orders: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        return "\n".join(report)
