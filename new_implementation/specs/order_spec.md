?????# Order Module Specification

## Purpose
Handles order representation, parsing, validation, and execution for all Diplomacy order types including movement, support, convoy, retreat, build, and destroy orders.

## API
- `Order`: Class representing a single order (move, support, hold, convoy, retreat, build, destroy)
  - Methods:
    - `__init__(self, order_str: str)`
    - `is_valid(self, game_state: dict) -> bool`
    - `execute(self, game_state: dict) -> dict`
- `OrderParser`: Parses and validates orders
  - Methods:
    - `parse(self, order_str: str) -> Order`
    - `validate(self, order: Order, game_state: dict) -> bool`

## Order Format Grammar

### Formal Grammar Definition

```
UNIT_TYPE := "A" | "F"
PROVINCE := [A-Z]{3}  # Three uppercase letters
UNIT := UNIT_TYPE PROVINCE

ORDER_TYPES:
1. HOLD:    UNIT "H"
2. MOVE:    UNIT "-" PROVINCE
3. SUPPORT: UNIT "S" UNIT ("-" PROVINCE)? ("H")?
4. CONVOY:  UNIT "C" UNIT "-" PROVINCE
5. RETREAT: UNIT "R" PROVINCE
6. BUILD:   "BUILD" UNIT_TYPE PROVINCE ("/" COAST)?
7. DESTROY: "DESTROY" UNIT

ORDER_BOUNDARY:
- Each order starts with either:
  a) UNIT_TYPE followed by PROVINCE (for standard orders)
  b) "BUILD" keyword (for build orders)
  c) "DESTROY" keyword (for destroy orders)
- Multiple orders separated by identifying next order start
```

### Order Boundary Detection

**Key Principle**: Order boundaries are determined by identifying the start of each order, not by splitting on unit types.

**Order Start Patterns**:
1. **Standard Orders**: `(A|F) PROVINCE` - Unit type followed by 3-letter province
2. **Build Orders**: `BUILD` keyword
3. **Destroy Orders**: `DESTROY` keyword

**Critical Rule**: Support orders contain multiple units but are **single orders**:
- `A ROM S A VEN H` is ONE order (support hold)
- `F NAP S A ROM - TUS` is ONE order (support move)
- `A ROM S A VEN H A TUS - PIE` is TWO orders (support + move)

**Regex Pattern for Order Boundaries**:
```regex
\b([AF])\s+([A-Z]{3})\b|(?:^|\s)(BUILD|DESTROY)\b
```

This pattern matches:
- `A ROM`, `F NAP` (unit + province)
- `BUILD`, `DESTROY` (special keywords)

### Multi-Order String Format

**Concatenation Rules**:
- Multiple orders separated by spaces
- No special delimiters between orders
- Order boundaries detected by parsing logic

**Examples**:
```
"A ROM - TUS A VEN H"                    # 2 orders: move + hold
"A ROM S A VEN H A TUS - PIE"            # 2 orders: support + move  
"F NAP S A ROM - TUS A VEN H"           # 2 orders: support + hold
"BUILD A PAR DESTROY A ROM"              # 2 orders: build + destroy
"A ROM - TUS F NAP - ROM A VEN S A ROM H" # 3 orders: move + move + support
```

**Parsing Algorithm**:
1. Find all order start positions using regex
2. Extract text between start positions
3. Clean whitespace and validate format
4. Return list of individual order strings

## Order Types

### 1. Movement Orders
- **Format**: `UNIT PROVINCE - DESTINATION`
- **Examples**: `A PAR - BUR`, `F LON - NTH`
- **Rules**: Unit moves to adjacent province/sea area

**Legal Examples**:
- `A PAR - BUR` (Army Paris to Burgundy)
- `F LON - NTH` (Fleet London to North Sea)
- `A MOS - UKR` (Army Moscow to Ukraine)
- `F KIE - DEN` (Fleet Kiel to Denmark)

**Illegal Examples**:
- `A PAR - LON` (Non-adjacent move)
- `F LON - MOS` (Fleet cannot move to inland province)
- `A PAR - PAR` (Cannot move to same province)
- `A PAR - BUR` when Paris is occupied by another unit
- `A PAR - BUR` when Burgundy is occupied by another unit

### 2. Support Orders
- **Format**: `UNIT PROVINCE S TARGET_UNIT - DESTINATION` or `UNIT PROVINCE S TARGET_UNIT`
- **Examples**: `A BUR S A PAR - MAR`, `F NTH S F LON`
- **Rules**: Unit supports another unit's move or hold

**Legal Examples**:
- `A BUR S A PAR - MAR` (Burgundy supports Paris to Marseilles)
- `F NTH S F LON` (North Sea supports London hold)
- `A SIL S RUSSIAN A WAR - PRU` (Support foreign unit)
- `F BAL S A BER - KIE` (Fleet supports army move)

**Illegal Examples**:
- `A BUR S A PAR - LON` (Supporting non-adjacent move)
- `F NTH S A PAR - MAR` (Fleet cannot support inland move)
- `A BUR S F LON - NTH` (Army cannot support sea move)
- `A BUR S A PAR - MAR` when Burgundy is occupied
- `A BUR S A PAR - MAR` when Paris is not adjacent to Marseilles

### 3. Convoy Orders
- **Format**: `F SEA_AREA C ARMY_UNIT - DESTINATION`
- **Examples**: `F NTH C A LON - BEL`
- **Rules**: 
  - Fleet convoys army across sea areas
  - Fleet can only convoy armies from provinces adjacent to that sea area
  - Army must be ordered to move to the same destination as convoy order
  - Multiple fleets can convoy through adjacent sea areas (convoy chains)
  - If any fleet in convoy chain is dislodged, entire convoy fails
  - Fleet cannot convoy more than one army per turn

**Legal Examples**:
- `F NTH C A LON - BEL` (North Sea convoys London to Belgium - both adjacent to NTH)
- `F ENG C A LON - BEL` (English Channel convoys London to Belgium - both adjacent to ENG)
- `F NTH C ENGLISH A LON - BEL` (Convoy foreign army)
- `F MED C A ROM - TUN` (Mediterranean convoys Rome to Tunisia - both adjacent to MED)
- Multi-fleet convoy: `F ENG C A LON - TUN`, `F MED C A LON - TUN` (convoy chain through ENG and MED)

**Illegal Examples**:
- `A PAR C A LON - BEL` (Only fleets can convoy)
- `F NTH C F LON - BEL` (Cannot convoy fleets)
- `F NTH C A LON - MOS` (Cannot convoy to inland province)
- `F NTH C A LON - BEL` when London is not adjacent to North Sea
- `F NTH C A PAR - BEL` when Paris is not adjacent to North Sea
- `F NTH C A LON - BEL` when army order is `A LON - HOL` (destination mismatch)

### 4. Hold Orders
- **Format**: `UNIT PROVINCE H` or `UNIT PROVINCE`
- **Examples**: `A PAR H`, `F LON`
- **Rules**: Unit remains in current position

**Legal Examples**:
- `A PAR H` (Army Paris holds)
- `F LON` (Fleet London holds - implicit)
- `A MOS H` (Army Moscow holds)
- `F STP H` (Fleet St. Petersburg holds)

**Illegal Examples**:
- `A PAR H MOS` (Hold with destination)
- `A PAR H` when Paris is occupied by another unit
- `A PAR H` when Paris doesn't belong to the power

### 5. Retreat Orders (NEW)
- **Format**: `UNIT PROVINCE - RETREAT_DESTINATION`
- **Examples**: `A PAR - GAS`, `F LON - ENG`
- **Rules**: 
  - Only available during Retreat phase
  - Unit must have been dislodged in previous movement phase
  - Retreat destination must be:
    - Adjacent to current province
    - Unoccupied
    - Not the province the attacker came from
    - Not a province left vacant due to standoff
  - If no valid retreat available, unit is automatically destroyed

**Legal Examples**:
- `A PAR - GAS` (Paris retreats to Gascony)
- `F LON - ENG` (London retreats to English Channel)
- `A MOS - STP` (Moscow retreats to St. Petersburg)
- `F SEV - BLA` (Sevastopol retreats to Black Sea)

**Illegal Examples**:
- `A PAR - BUR` (Retreat to occupied province)
- `A PAR - LON` (Non-adjacent retreat)
- `A PAR - GAS` when Paris wasn't dislodged
- `A PAR - GAS` when Gascony is the attacker's origin
- `A PAR - GAS` when Gascony was left vacant by standoff
- `A PAR - GAS` during Movement phase (wrong phase)

### 6. Build Orders (NEW)
- **Format**: `BUILD_TYPE PROVINCE` (for armies) or `BUILD_TYPE PROVINCE COAST` (for fleets)
- **Examples**: `BUILD A PAR`, `BUILD F STP/NC`, `BUILD F STP/SC`
- **Rules**:
  - Only available during Builds phase (after Fall moves)
  - Player must have more supply centers than units
  - Can only build in unoccupied home supply centers
  - For fleets in multi-coast provinces (St. Petersburg), must specify coast
  - Builds are written and exposed simultaneously

**Legal Examples**:
- `BUILD A PAR` (Build army in Paris)
- `BUILD F LON` (Build fleet in London)
- `BUILD F STP/NC` (Build fleet in St. Petersburg North Coast)
- `BUILD F STP/SC` (Build fleet in St. Petersburg South Coast)
- `BUILD A MOS` (Build army in Moscow)

**Illegal Examples**:
- `BUILD A PAR` when Paris is occupied
- `BUILD A PAR` when player has no excess supply centers
- `BUILD A PAR` during Movement phase (wrong phase)
- `BUILD F STP` (Must specify coast for St. Petersburg)
- `BUILD A WAR` when Warsaw is not a home supply center
- `BUILD A PAR` when Paris is owned by another power

### 7. Destroy Orders (NEW)
- **Format**: `DESTROY UNIT PROVINCE`
- **Examples**: `DESTROY A PAR`, `DESTROY F LON`
- **Rules**:
  - Only available during Builds phase (after Fall moves)
  - Player must have more units than supply centers
  - Player chooses which units to destroy
  - Can destroy any of their units
  - Destroys are written and exposed simultaneously

**Legal Examples**:
- `DESTROY A PAR` (Destroy army in Paris)
- `DESTROY F LON` (Destroy fleet in London)
- `DESTROY A MOS` (Destroy army in Moscow)
- `DESTROY F SEV` (Destroy fleet in Sevastopol)

**Illegal Examples**:
- `DESTROY A PAR` when Paris is occupied by another power
- `DESTROY A PAR` when player has no excess units
- `DESTROY A PAR` during Movement phase (wrong phase)
- `DESTROY A WAR` when Warsaw is not occupied by the player
- `DESTROY A PAR` when Paris is not occupied by any unit

## Phase-Specific Order Rules

### Movement Phase (Spring/Autumn)
- All order types except retreats, builds, and destroys
- Orders processed simultaneously
- Conflicts resolved after all orders are read

### Retreat Phase (After Movement if dislodged units exist)
- Only retreat orders and destroy orders allowed
- Players may choose to destroy unit instead of retreating
- If multiple units retreat to same space, all are destroyed
- If player fails to order retreat, unit is automatically destroyed
- Retreats may not be convoyed or supported

### Builds Phase (After Fall moves and retreats)
- Only build and destroy orders allowed
- Unit count must equal supply center count
- Builds and destroys processed simultaneously
- No diplomacy period before builds/destroys

## Expected Behavior
- Parses order strings into objects with proper validation
- Validates orders against current game state and phase
- Executes orders to update game state appropriately
- Handles phase transitions correctly

## Example Usage
```python
from orders.order import Order
from orders.order_parser import OrderParser

# Movement order
order = Order('A PAR - BUR')
parser = OrderParser()
parsed_order = parser.parse('A PAR - BUR')
valid = parser.validate(parsed_order, game_state)

# Retreat order
retreat_order = parser.parse('A PAR - GAS')  # During retreat phase

# Build order
build_order = parser.parse('BUILD A PAR')  # During builds phase

# Destroy order
destroy_order = parser.parse('DESTROY A PAR')  # During builds phase
```

## Validation Details (Updated October 2025)
- Validation now checks:
  - Power existence
  - Unit ownership (unit must belong to power)
  - Action validity (must be one of '-', 'H', 'S', 'C', 'BUILD', 'DESTROY')
  - Phase appropriateness (retreats only in retreat phase, builds/destroys only in builds phase)
  - For moves: target must be present, valid, and adjacent (if map is provided)
  - For supports: target must be present
  - For convoys: only fleets can convoy, target must be present
  - For holds: must not have a target
  - For retreats: unit must be dislodged, destination must be valid retreat space
  - For builds: player must have excess supply centers, province must be unoccupied home supply center
  - For destroys: player must have excess units, unit must belong to player
- Validation returns a tuple (bool, str): pass/fail and error message
- Tests cover valid, invalid, and edge-case orders, and check error messages

## Special Rules

### Retreat Conflicts
- If two or more units retreat to the same space, all are destroyed
- Exception: If only one unit is ordered to retreat and others are ordered to be destroyed, the retreating unit succeeds

### Build Restrictions
- Can only build in home supply centers
- Must specify coast for fleets in multi-coast provinces (St. Petersburg)
- Cannot build if all home supply centers are occupied or owned by others

### Destroy Priority (Civil Disorder)
- When player fails to submit orders, units are destroyed automatically
- Priority: farthest from home first, fleet before army, alphabetical by province name

---

Update this spec as the module evolves.
