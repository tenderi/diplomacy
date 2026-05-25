# Data Model Specification for Diplomacy Python Implementation

## Purpose
Defines the comprehensive data model for the Diplomacy game engine, including game state, units, orders, phases, and all related entities. This specification ensures data integrity and proper handling of all Diplomacy rules.

## Core Data Structures

### 1. Game State Model

```python
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
    status: str          # "active", "paused", "completed"
    created_at: datetime
    updated_at: datetime
    
    # Core game data
    powers: Dict[str, PowerState]
    units: Dict[str, List[Unit]]  # power -> units
    supply_centers: Dict[str, str]  # province -> controlling_power
    orders: Dict[str, List[Order]]  # power -> orders for current phase
    pending_retreats: Dict[str, List[RetreatOrder]]  # power -> retreat orders
    pending_builds: Dict[str, List[BuildOrder]]     # power -> build orders
    pending_destroys: Dict[str, List[DestroyOrder]] # power -> destroy orders
    
    # Game history
    turn_history: List[TurnState]
    order_history: List[Dict[str, List[Order]]]  # Historical orders
    map_snapshots: List[MapSnapshot]
```

### 2. Power State Model

```python
@dataclass
class PowerState:
    """Individual power (player) state"""
    power_name: str
    user_id: Optional[int]  # Telegram user ID if human player
    is_active: bool
    is_eliminated: bool
    home_supply_centers: List[str]
    controlled_supply_centers: List[str]
    units: List[Unit]
    orders_submitted: bool
    last_order_time: Optional[datetime]
    
    # Phase-specific data
    retreat_options: Dict[str, List[str]]  # unit -> valid retreat provinces
    build_options: List[str]  # available build provinces
    destroy_options: List[str]  # units that can be destroyed
```

### 3. Unit Model

```python
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
```

### 4. Order Models

```python
@dataclass
class Order:
    """Base order class"""
    power: str
    unit: Unit
    order_type: str  # "move", "hold", "support", "convoy", "retreat", "build", "destroy"
    phase: str       # Phase when order is valid
    status: str = "pending"  # "pending", "success", "failed", "bounced"
    failure_reason: Optional[str] = None
    
    def validate(self, game_state: GameState) -> Tuple[bool, str]:
        """Validate order against current game state"""
        pass

@dataclass
class MoveOrder(Order):
    """Movement order"""
    target_province: str
    is_convoyed: bool = False
    convoy_route: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.unit} - {self.target_province}"

@dataclass
class HoldOrder(Order):
    """Hold order"""
    def __str__(self) -> str:
        return f"{self.unit} H"

@dataclass
class SupportOrder(Order):
    """Support order"""
    supported_unit: Unit
    supported_action: str  # "move" or "hold"
    supported_target: Optional[str] = None  # For move support
    
    def __str__(self) -> str:
        if self.supported_action == "move":
            return f"{self.unit} S {self.supported_unit} - {self.supported_target}"
        else:
            return f"{self.unit} S {self.supported_unit}"

@dataclass
class ConvoyOrder(Order):
    """Convoy order"""
    convoyed_unit: Unit
    convoyed_target: str
    convoy_chain: List[str] = field(default_factory=list)
    
    def __str__(self) -> str:
        return f"{self.unit} C {self.convoyed_unit} - {self.convoyed_target}"

@dataclass
class RetreatOrder(Order):
    """Retreat order"""
    retreat_province: str
    
    def __str__(self) -> str:
        return f"{self.unit} R {self.retreat_province}"

@dataclass
class BuildOrder(Order):
    """Build order"""
    build_province: str
    build_type: str  # "A" or "F"
    build_coast: Optional[str] = None  # For multi-coast provinces
    
    def __str__(self) -> str:
        coast_suffix = f"/{self.build_coast}" if self.build_coast else ""
        return f"BUILD {self.build_type} {self.build_province}{coast_suffix}"

@dataclass
class DestroyOrder(Order):
    """Destroy order"""
    destroy_unit: Unit
    
    def __str__(self) -> str:
        return f"DESTROY {self.destroy_unit}"
```

### 5. Map and Province Models

```python
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
```

### 6. Turn and Phase Models

```python
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
class OrderResult:
    """Result of order execution"""
    order: Order
    success: bool
    failure_reason: Optional[str] = None
    original_order_string: str  # Store original string for debugging
    parsed_correctly: bool = True
    parsing_error: Optional[str] = None
    dislodged_units: List[Unit] = field(default_factory=list)
    retreat_required: bool = False

@dataclass
class MapSnapshot:
    """Snapshot of map state at specific point"""
    turn_number: int
    phase_code: str
    units: Dict[str, List[Unit]]
    supply_centers: Dict[str, str]
    map_image_path: Optional[str] = None
    created_at: datetime
```

## Database Schema

### Core Tables

```sql
-- Games table
CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(50) UNIQUE NOT NULL,
    map_name VARCHAR(50) NOT NULL DEFAULT 'standard',
    current_turn INTEGER NOT NULL DEFAULT 0,
    current_year INTEGER NOT NULL DEFAULT 1901,
    current_season VARCHAR(10) NOT NULL DEFAULT 'Spring',
    current_phase VARCHAR(20) NOT NULL DEFAULT 'Movement',
    phase_code VARCHAR(10) NOT NULL DEFAULT 'S1901M',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Players/Powers table
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    power_name VARCHAR(20) NOT NULL,
    user_id BIGINT,  -- Telegram user ID
    is_active BOOLEAN DEFAULT true,
    is_eliminated BOOLEAN DEFAULT false,
    home_supply_centers TEXT[],  -- Array of province names
    controlled_supply_centers TEXT[],  -- Array of province names
    orders_submitted BOOLEAN DEFAULT false,
    last_order_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, power_name)
);

-- Units table
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    power_name VARCHAR(20) NOT NULL,
    unit_type CHAR(1) NOT NULL CHECK (unit_type IN ('A', 'F')),
    province VARCHAR(20) NOT NULL,
    is_dislodged BOOLEAN DEFAULT false,
    dislodged_by VARCHAR(20),
    can_retreat BOOLEAN DEFAULT true,
    retreat_options TEXT[],  -- Array of province names
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, province)  -- Only one unit per province
);

-- Orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    power_name VARCHAR(20) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    unit_type CHAR(1) NOT NULL,
    unit_province VARCHAR(20) NOT NULL,
    target_province VARCHAR(20),
    supported_unit_type CHAR(1),
    supported_unit_province VARCHAR(20),
    supported_target VARCHAR(20),
    convoyed_unit_type CHAR(1),
    convoyed_unit_province VARCHAR(20),
    convoyed_target VARCHAR(20),
    convoy_chain TEXT[],  -- Array of sea areas
    build_type CHAR(1),
    build_province VARCHAR(20),
    build_coast VARCHAR(10),
    destroy_unit_type CHAR(1),
    destroy_unit_province VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    failure_reason TEXT,
    original_order_string TEXT,  -- Store original string for debugging
    parsed_correctly BOOLEAN DEFAULT true,
    parsing_error TEXT,
    phase VARCHAR(20) NOT NULL,
    turn_number INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Order history table for complete audit trail
CREATE TABLE order_history (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    phase VARCHAR(20) NOT NULL,
    power_name VARCHAR(20) NOT NULL,
    submitted_string TEXT NOT NULL,  -- Original multi-order string
    parsed_orders JSONB NOT NULL,    -- Array of parsed orders
    parse_success BOOLEAN NOT NULL,
    parse_errors TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Supply centers table
CREATE TABLE supply_centers (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    province VARCHAR(20) NOT NULL,
    controlling_power VARCHAR(20),
    is_home_supply_center BOOLEAN DEFAULT false,
    home_power VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, province)
);

-- Turn history table
CREATE TABLE turn_history (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    year INTEGER NOT NULL,
    season VARCHAR(10) NOT NULL,
    phase VARCHAR(20) NOT NULL,
    phase_code VARCHAR(10) NOT NULL,
    units_before JSONB,  -- Units state before turn
    units_after JSONB,   -- Units state after turn
    supply_centers_before JSONB,
    supply_centers_after JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Map snapshots table
CREATE TABLE map_snapshots (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    phase_code VARCHAR(10) NOT NULL,
    units JSONB NOT NULL,
    supply_centers JSONB NOT NULL,
    map_image_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table (for Telegram integration)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    username VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table (for diplomatic communication)
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
    sender_user_id BIGINT REFERENCES users(telegram_id),
    sender_power VARCHAR(20),
    recipient_user_id BIGINT REFERENCES users(telegram_id),
    recipient_power VARCHAR(20),
    message_type VARCHAR(20) NOT NULL,  -- 'private', 'broadcast', 'system'
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Data Validation Rules

### 1. Unit Validation
- Only one unit per province
- Units must belong to valid powers
- Unit types must be "A" (Army) or "F" (Fleet)
- Provinces must exist in map data
- Units cannot be in invalid provinces for their type

### 2. Order Validation
- Orders must be submitted by the power that owns the unit
- Orders must be valid for the current phase
- Move orders must target adjacent provinces
- Support orders must support valid actions
- Convoy orders must involve fleets and armies
- Retreat orders must target valid retreat provinces
- Build orders must be in unoccupied home supply centers
- Destroy orders must target own units

### 3. Game State Validation
- Supply center count must equal unit count for each power
- No two units in same province
- All units must belong to active powers
- Phase transitions must follow Diplomacy rules
- Turn numbers must be sequential

### 4. Map Validation
- All provinces must have valid adjacencies
- Supply centers must be properly defined
- Home supply centers must be assigned to powers
- Starting positions must be valid

## Data Access Patterns

### 1. Game State Queries
```python
# Get current game state
def get_game_state(game_id: str) -> GameState:
    # Load game, players, units, orders, supply centers
    pass

# Get units for specific power
def get_power_units(game_id: str, power: str) -> List[Unit]:
    pass

# Get orders for current phase
def get_current_orders(game_id: str) -> Dict[str, List[Order]]:
    pass
```

### 2. Order Management
```python
# Submit orders for power
def submit_orders(game_id: str, power: str, orders: List[Order]) -> bool:
    pass

# Validate orders against game state
def validate_orders(game_id: str, orders: List[Order]) -> List[Tuple[bool, str]]:
    pass

# Get order history
def get_order_history(game_id: str, turn: int) -> Dict[str, List[Order]]:
    pass
```

### 3. Turn Processing
```python
# Process movement phase
def process_movement_phase(game_id: str) -> Dict[str, List[OrderResult]]:
    pass

# Process retreat phase
def process_retreat_phase(game_id: str) -> Dict[str, List[OrderResult]]:
    pass

# Process builds phase
def process_builds_phase(game_id: str) -> Dict[str, List[OrderResult]]:
    pass
```

## Error Handling

### 1. Data Integrity Errors
- Duplicate units in same province
- Invalid unit ownership
- Invalid order submission
- Phase mismatch errors

### 2. Validation Errors
- Invalid move targets
- Invalid support targets
- Invalid convoy routes
- Invalid retreat destinations
- Invalid build locations

### 3. State Consistency Errors
- Supply center count mismatch
- Missing required orders
- Invalid phase transitions
- Orphaned units or orders

## Performance Considerations

### 1. Indexing Strategy
- Index on game_id for all tables
- Index on power_name for player-specific queries
- Index on province for unit lookups
- Index on turn_number for historical queries

### 2. Caching Strategy
- Cache current game state in memory
- Cache map data (provinces, adjacencies)
- Cache order validation results
- Cache unit positions for quick lookups

### 3. Query Optimization
- Use batch operations for order submission
- Minimize database round trips
- Use JSONB for complex nested data
- Implement connection pooling

## Migration Strategy

### Phase 1: Core Data Structures
1. Implement basic GameState, Unit, Order classes
2. Create database schema
3. Implement basic CRUD operations
4. Add data validation

### Phase 2: Order Processing
1. Implement order parsing and validation
2. Add order execution logic
3. Implement phase transitions
4. Add order result tracking

### Phase 3: Advanced Features
1. Add turn history and snapshots
2. Implement diplomatic messaging
3. Add user management
4. Implement map rendering integration

### Phase 4: Optimization
1. Add caching layer
2. Optimize database queries
3. Implement batch operations
4. Add performance monitoring

---

This data specification provides a comprehensive foundation for implementing a robust Diplomacy game engine with proper data integrity, validation, and performance characteristics.
