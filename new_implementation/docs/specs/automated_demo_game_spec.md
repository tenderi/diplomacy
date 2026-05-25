# Perfect Demo Game Specification

## Purpose
The Perfect Demo Game is a comprehensive demonstration system that showcases all Diplomacy game mechanics, order types, and phases through a carefully choreographed sequence of hardcoded orders. It serves as both a testing tool and an educational resource, demonstrating the complete functionality of the Diplomacy engine.

## Overview
The perfect demo game plays a complete Diplomacy game automatically using predetermined orders for all seven powers, processing all phases (Movement, Retreat, Build/Destroy), and creating visual documentation of the game progression through map generation. Unlike the previous automated demo which used AI-generated orders, this uses hardcoded scenarios to demonstrate specific mechanics.

## Core Features

### 1. **Complete Game Simulation**
- **Full Game Lifecycle**: Plays from Spring 1901 through multiple years
- **All Seven Powers**: Automatically manages Austria, England, France, Germany, Italy, Russia, and Turkey
- **Dynamic Order Generation**: Creates realistic, legal orders based on current game state
- **Phase Progression**: Handles Movement → Retreat → Build/Destroy phases automatically
- **Victory Conditions**: Continues until a power reaches 18 supply centers or game reaches reasonable conclusion

### 2. **Comprehensive Order Demonstration**
- **Movement Orders**: Basic moves, attacks, and positional changes
- **Support Orders**: Defensive holds, offensive support, and support cuts
- **Convoy Orders**: Army transportation across sea areas
- **Retreat Orders**: Dislodged unit retreats and forced disbands
- **Build Orders**: New unit construction in home supply centers
- **Destroy Orders**: Unit disbandment due to supply center loss
- **Hold Orders**: Defensive positioning and strategic holds

### 3. **Advanced Diplomacy Mechanics**
- **Conflict Resolution**: Demonstrates standoffs, bounces, and successful attacks
- **Support Cut Logic**: Shows how support can be disrupted
- **Convoy Disruption**: Illustrates convoy failure when fleets are dislodged
- **Self-Dislodgement Prevention**: Enforces rule that powers cannot dislodge their own units
- **Beleaguered Garrison**: Multiple equal attacks result in all units staying in place
- **Complex Adjudication**: Multi-way conflicts with proper strength calculation

### 4. **Visual Documentation System**
- **Map Generation**: Creates PNG maps at each phase showing unit positions
- **Order Visualization**: Maps showing submitted orders with movement arrows
- **Resolution Visualization**: Maps showing order results and conflicts
- **Phase Documentation**: Complete visual record of game progression
- **Strategic Analysis**: Maps highlight key strategic developments

## Technical Architecture

### 1. **Core Components**

#### `PerfectDemoGame` Class
```python
class PerfectDemoGame:
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.game_id = None
        self.phase_count = 0
        self.server = Server()
        
    def run_demo_game(self) -> None:
        """Run the complete automated demo game"""
        
    def create_demo_game(self) -> bool:
        """Create a new demo game instance"""
        
    def add_players(self) -> bool:
        """Add all seven powers to the game"""
        
    def generate_dynamic_orders(self, game_state: GameState) -> Dict[str, List[str]]:
        """Generate realistic orders based on current game state"""
        
    def process_phase(self) -> bool:
        """Process current phase and advance to next"""
        
    def generate_and_save_map(self, game_state: GameState, filename: str) -> None:
        """Generate and save map visualization"""
```

#### Order Generation Engine
```python
def generate_movement_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate movement orders based on strategic analysis"""
    
def generate_support_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate support orders for defensive and offensive purposes"""
    
def generate_convoy_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate convoy orders for army transportation"""
    
def generate_retreat_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate retreat orders for dislodged units"""
    
def generate_build_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate build orders based on supply center control"""
    
def generate_destroy_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate destroy orders when units exceed supply centers"""
```

### 2. **Strategic AI Logic**

#### Phase-Aware Order Generation
- **Early Game (1901-1902)**: Focus on expansion and positioning
- **Mid Game (1903-1905)**: Complex alliances and conflicts
- **Late Game (1906+)**: Victory pursuit and elimination strategies

#### Power-Specific Strategies
- **Austria**: Central positioning, alliance management
- **England**: Naval dominance, continental intervention
- **France**: Western expansion, defensive positioning
- **Germany**: Central power, flexible strategy
- **Italy**: Mediterranean control, opportunistic expansion
- **Russia**: Eastern dominance, western pressure
- **Turkey**: Eastern Mediterranean, Black Sea control

#### Dynamic Decision Making
- **Adjacency Validation**: All orders use real game engine adjacency data
- **Supply Center Analysis**: Orders consider supply center control and growth
- **Conflict Avoidance**: Strategic positioning to avoid unnecessary conflicts
- **Opportunistic Attacks**: Capitalize on enemy weaknesses
- **Defensive Positioning**: Protect vulnerable positions

### 3. **Map Visualization System**

#### Map Generation Pipeline
```python
def generate_and_save_map(self, game_state: GameState, filename: str) -> None:
    """Generate map showing current unit positions"""
    
def generate_orders_map(self, game_state: GameState, orders: Dict, filename: str) -> None:
    """Generate map showing submitted orders with arrows"""
    
def generate_resolution_map(self, game_state: GameState, orders: Dict, filename: str) -> None:
    """Generate map showing order resolution results"""
```

#### Visual Elements
- **Unit Positions**: Current location of all units
- **Movement Arrows**: Visual representation of moves
- **Support Indicators**: Circles around supporting units
- **Convoy Routes**: Curved arrows showing convoy paths
- **Conflict Markers**: Visual indicators of battles and standoffs
- **Supply Centers**: Highlighted supply center ownership
- **Phase Information**: Turn, season, and phase details

## Game Flow Specification

### 1. **Initialization Phase**
```
1. Create demo game with standard map
2. Add all seven powers (Austria, England, France, Germany, Italy, Russia, Turkey)
3. Initialize starting positions per Diplomacy rules
4. Generate initial map (demo_1901_01_initial.png)
5. Display game state and unit positions
```

### 2. **Movement Phase Processing**
```
1. Generate dynamic orders for all powers
2. Display bot commands (/orders game_id power order_list)
3. Submit orders to game engine
4. Generate orders map showing submitted moves (demo_1901_02_spring_orders.png)
5. Process turn through game engine
6. Generate resolution map showing results (demo_1901_03_spring_resolution.png)
7. Generate final map after movement (demo_1901_04_spring_movement.png)
8. Display updated game state
```

### 3. **Retreat Phase Processing** (if needed)
```
1. Identify dislodged units
2. Generate retreat orders for affected powers
3. Process retreat phase
4. Generate retreat resolution map
5. Update game state
```

### 4. **Build/Destroy Phase Processing** (after Fall turns)
```
1. Calculate supply center control
2. Generate build orders for powers with excess supply centers
3. Generate destroy orders for powers with excess units
4. Process builds/destroys phase
5. Generate builds map showing new units (demo_1901_08_autumn_builds.png)
6. Update game state and advance to next year
```

### 5. **Multi-Year Progression**
```
- Spring 1901: Initial expansion and positioning
- Fall 1901: Consolidation and first builds
- Spring 1902: Strategic positioning and early conflicts
- Fall 1902: Major conflicts and supply center changes
- Spring 1903+: Advanced strategies and victory pursuit
- Continue until victory condition or reasonable conclusion
```

## Order Generation Algorithms

### 1. **Movement Order Generation**
```python
def generate_movement_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate movement orders based on strategic analysis"""
    orders = {}
    
    for power_name, power_state in game_state.powers.items():
        power_orders = []
        
        for unit in power_state.units:
            # Analyze adjacent provinces
            adjacent = self.map.get_adjacency(unit.province)
            
            # Strategic decision making
            if self.should_expand(unit, game_state):
                target = self.choose_expansion_target(unit, adjacent, game_state)
                if target:
                    power_orders.append(f"{unit.unit_type} {unit.province} - {target}")
            elif self.should_attack(unit, game_state):
                target = self.choose_attack_target(unit, adjacent, game_state)
                if target:
                    power_orders.append(f"{unit.unit_type} {unit.province} - {target}")
            else:
                # Hold or support
                if self.should_support(unit, game_state):
                    support_order = self.generate_support_order(unit, game_state)
                    if support_order:
                        power_orders.append(support_order)
                else:
                    power_orders.append(f"{unit.unit_type} {unit.province} H")
        
        orders[power_name] = power_orders
    
    return orders
```

### 2. **Support Order Generation**
```python
def generate_support_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate support orders for defensive and offensive purposes"""
    orders = {}
    
    for power_name, power_state in game_state.powers.items():
        power_orders = []
        
        for unit in power_state.units:
            # Look for opportunities to support friendly moves
            if self.can_support_friendly_move(unit, game_state):
                support_order = self.create_support_order(unit, game_state)
                if support_order:
                    power_orders.append(support_order)
            # Look for defensive support opportunities
            elif self.can_provide_defensive_support(unit, game_state):
                support_order = self.create_defensive_support(unit, game_state)
                if support_order:
                    power_orders.append(support_order)
        
        orders[power_name] = power_orders
    
    return orders
```

### 3. **Convoy Order Generation**
```python
def generate_convoy_orders(self, game_state: GameState) -> Dict[str, List[str]]:
    """Generate convoy orders for army transportation"""
    orders = {}
    
    for power_name, power_state in game_state.powers.items():
        power_orders = []
        
        # Find fleets that can convoy
        fleets = [u for u in power_state.units if u.unit_type == 'F']
        
        for fleet in fleets:
            # Look for armies that can be convoyed
            convoyable_armies = self.find_convoyable_armies(fleet, game_state)
            
            for army, destination in convoyable_armies:
                convoy_order = f"{fleet.unit_type} {fleet.province} C {army.unit_type} {army.province} - {destination}"
                power_orders.append(convoy_order)
        
        orders[power_name] = power_orders
    
    return orders
```

## Map Visualization Specifications

### 1. **Map Generation Requirements**
- **Format**: PNG images with high resolution (1920x1080 minimum)
- **File Naming**: Descriptive names indicating turn, season, and phase
- **Location**: Saved to `/test_maps/` directory
- **Content**: Current unit positions, supply center ownership, phase information

### 2. **Order Visualization Features**
- **Movement Arrows**: Solid arrows showing unit movements
- **Support Circles**: Circles around supporting units
- **Convoy Routes**: Curved arrows showing convoy paths
- **Conflict Markers**: Visual indicators of battles and standoffs
- **Color Coding**: Power-specific colors for all visual elements
- **Status Indicators**: Success/failure indicators for orders

### 3. **Map Types Generated**
- **Initial Maps**: Starting positions and game setup
- **Order Maps**: Submitted orders before processing
- **Resolution Maps**: Order results and conflicts
- **Final Maps**: Stable positions after phase completion
- **Build Maps**: New units and supply center changes

## Configuration and Customization

### 1. **Game Parameters**
```python
class DemoGameConfig:
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
```

### 2. **Customization Options**
- **Map Variants**: Support for different map configurations
- **AI Personalities**: Different strategic approaches per power
- **Game Length**: Configurable turn limits and victory conditions
- **Visual Styles**: Customizable map appearance and colors
- **Output Formats**: Multiple export options for maps and data

## Integration Points

### 1. **Server Integration**
- **API Endpoints**: Uses standard server API for game management
- **Database Integration**: Saves game state and progression
- **Real-time Processing**: Integrates with live server infrastructure

### 2. **Telegram Bot Integration**
- **Demo Commands**: Bot commands for starting and managing demo games
- **Map Sharing**: Automatic map generation and sharing
- **Progress Updates**: Real-time updates on demo game progression

### 3. **Testing Integration**
- **Unit Tests**: Comprehensive test coverage for all demo components
- **Integration Tests**: End-to-end testing of complete demo flow
- **Performance Tests**: Load testing for demo game performance

## Usage Examples

### 1. **Basic Demo Game**
```python
from demo_perfect_game import PerfectDemoGame

# Create and run demo game
demo = PerfectDemoGame()
demo.run_demo()
```

### 2. **Custom Configuration**
```python
from demo_perfect_game import PerfectDemoGame

# Create perfect demo game (hardcoded scenarios)
demo = PerfectDemoGame()
demo.run_demo()
```

### 3. **Telegram Bot Integration**
```python
# Bot command to start demo game
async def run_automated_demo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Runs demo_perfect_game.py via subprocess
    # See telegram_bot.py for implementation
```

## Testing and Validation

### 1. **Test Coverage Requirements**
- **Unit Tests**: All order generation algorithms
- **Integration Tests**: Complete demo game flow
- **Visual Tests**: Map generation and visualization
- **Performance Tests**: Large game simulation performance

### 2. **Validation Criteria**
- **Order Validity**: All generated orders must be legal
- **Game Progression**: Proper phase transitions and state updates
- **Map Accuracy**: Generated maps must reflect actual game state
- **Strategic Coherence**: Orders must demonstrate logical strategic thinking

### 3. **Quality Assurance**
- **Automated Testing**: Continuous integration testing
- **Manual Review**: Strategic analysis of generated games
- **Performance Monitoring**: Resource usage and execution time
- **Error Handling**: Robust error handling and recovery

## Future Enhancements

### 1. **Advanced AI Features**
- **Machine Learning**: AI that learns from successful strategies
- **Personality Systems**: Distinct AI personalities for each power
- **Adaptive Strategies**: AI that adapts to opponent behavior
- **Historical Analysis**: AI that learns from historical games

### 2. **Enhanced Visualization**
- **Interactive Maps**: Clickable maps with detailed information
- **Animation Support**: Animated order resolution sequences
- **3D Visualization**: Three-dimensional map representations
- **VR Integration**: Virtual reality game visualization

### 3. **Educational Features**
- **Tutorial Mode**: Step-by-step explanation of game mechanics
- **Analysis Tools**: Strategic analysis and commentary
- **Replay System**: Ability to replay and analyze games
- **Learning Resources**: Integration with educational materials

## Success Metrics

### 1. **Functional Requirements**
- ✅ **Complete Game Simulation**: Plays full games from start to finish
- ✅ **All Order Types**: Demonstrates all seven order types
- ✅ **Phase Progression**: Handles all three phases correctly
- ✅ **Visual Documentation**: Generates comprehensive map series

### 2. **Quality Requirements**
- ✅ **Order Validity**: All generated orders are legal and executable
- ✅ **Strategic Coherence**: Orders demonstrate logical strategic thinking
- ✅ **Map Accuracy**: Generated maps accurately reflect game state
- ✅ **Performance**: Efficient execution and resource usage

### 3. **Educational Value**
- ✅ **Mechanics Demonstration**: Clearly shows all game mechanics
- ✅ **Strategic Examples**: Provides examples of good strategic play
- ✅ **Visual Learning**: Maps enhance understanding of game flow
- ✅ **Comprehensive Coverage**: Covers all aspects of Diplomacy gameplay

---

**CURRENT STATUS**: The automated demo game is fully implemented and production-ready. It successfully demonstrates all Diplomacy mechanics, generates comprehensive visual documentation, and provides an excellent educational resource for understanding the game. The system is integrated with the main server infrastructure and can be run via both command-line and Telegram bot interfaces.

**NEXT PRIORITIES**: Performance optimization, enhanced AI strategies, and expanded educational features.

---

## Perfect Automated Demo Game Design

### Overview

The Perfect Automated Demo Game uses hardcoded orders to demonstrate all Diplomacy mechanics through a carefully choreographed sequence. Unlike the dynamic AI-based demo, this uses predetermined orders to showcase specific scenarios: 2-1 battles, support cuts, convoys, standoffs, retreats, and build phases.

### Core Design Principles

1. **Hardcoded Orders**: All orders pre-written in a scenario sequence, no AI generation
2. **Strategic Logic**: Every move makes strategic sense; no self-attacks or illogical orders
3. **Complete Coverage**: Demonstrates all 7 order types (Move, Hold, Support, Convoy, Retreat, Build, Destroy)
4. **Educational Focus**: Each phase teaches specific mechanics
5. **Visual Storytelling**: Maps show clear cause-and-effect relationships
6. **Deterministic Execution**: The game is absolutely deterministic - given the same initial state and hardcoded orders, it will always produce the same results. This makes it a final test that every feature is working correctly.

### Game Structure

**Duration: 2 Years (1901-1902)**

- Spring 1901: Initial expansion and first conflicts
- Fall 1901: Consolidation, supply center changes, builds
- Spring 1902: Advanced tactics, support combinations, convoys
- Fall 1902: Complex conflicts, retreats, final builds

**Phase Sequence:**
1. Spring 1901 Movement
2. Spring 1901 Retreat (if dislodgements occur)
3. Fall 1901 Movement
4. Fall 1901 Retreat (if dislodgements occur)
5. Fall 1901 Builds
6. Spring 1902 Movement
7. Spring 1902 Retreat (if dislodgements occur)
8. Fall 1902 Movement
9. Fall 1902 Retreat (if dislodgements occur)
10. Fall 1902 Builds

### Scenario Designs

#### Spring 1901 Movement

**Objectives:**
- Demonstrate basic moves and holds
- Show first 2-1 battle with support
- Create one dislodgement for retreat phase

**Hardcoded Orders:**
- **AUSTRIA**: `A VIE - TYR`, `A BUD - RUM`, `F TRI H`
- **ENGLAND**: `F LON - ENG`, `F EDI - NTH`, `A LVP - CLY`
- **FRANCE**: `A PAR - BUR`, `A MAR - PIE`, `F BRE - MAO`
- **GERMANY**: `A BER - KIE`, `A MUN - SIL`, `F KIE - HOL`
- **ITALY**: `A ROM - TUS`, `A VEN H`, `F NAP - ION`
- **RUSSIA**: `A MOS - UKR`, `A WAR - GAL`, `F SEV - BLA`, `F STP - BOT`
- **TURKEY**: `A CON - BUL`, `A SMY - ARM`, `F ANK - BLA`

**Expected Outcomes:**
- Basic positioning established
- No major conflicts in first turn
- Units in position for Fall conflicts

#### Fall 1901 Movement

**Objectives:**
- Demonstrate 2-1 battle (supported attack succeeds)
- Show standoff (equal strength bounce)
- Demonstrate support cut mechanics
- Create dislodgement for retreat phase

**Hardcoded Orders:**
- **AUSTRIA**: `A TYR - VEN`, `A RUM H`, `F TRI S A TYR - VEN`
- **ENGLAND**: `F ENG H`, `F NTH H`, `A CLY H`
- **FRANCE**: `A BUR - BEL`, `A PIE H`, `F MAO S A BUR - BEL`
- **GERMANY**: `A SIL - GAL`, `A BER H`, `F KIE S A SIL - GAL`
- **ITALY**: `A VEN H`, `A TUS S A VEN`, `F ION - ADR`
- **RUSSIA**: `A UKR - RUM`, `A GAL S A UKR - RUM`, `F SEV H`, `F BOT H`
- **TURKEY**: `A BUL - RUM`, `A ARM - SEV`, `F ANK H`

**Expected Outcomes:**
- France takes Belgium with 2-1 support
- Austria takes Venice with 2-1
- Russia takes Romania with 2-1
- Turkey's fleet in Black Sea dislodged (if controlled by Turkey)
- Italy's army in Venice dislodged

#### Fall 1901 Retreat

**Objectives:**
- Demonstrate retreat orders
- Show forced disband (no valid retreat)

**Hardcoded Retreat Orders:**
- **ITALY**: `A VEN R APU` (retreat to Apulia)
- **TURKEY**: `F BLA D` (disband - no valid retreat, Black Sea surrounded)

#### Fall 1901 Builds

**Objectives:**
- Demonstrate build orders
- Show supply center control changes

**Hardcoded Build Orders:**
- **FRANCE**: `BUILD A MAR` (gained Belgium)
- **AUSTRIA**: `BUILD A BUD` (gained Venice)
- **RUSSIA**: `BUILD A MOS` (gained Romania)
- Others: No builds

#### Spring 1902 Movement

**Objectives:**
- Demonstrate convoy orders
- Show complex support combinations
- Create multiple conflicts

**Hardcoded Orders:**
- **ENGLAND**: Convoy orders (dynamically adjusted based on unit positions)
- **FRANCE**: `A BEL H`, `A PAR S A BEL H`, `F MAO - SPA`, `A MAR - PIE`
- **GERMANY**: `A KIE - HOL`, `A SIL - WAR`, `A BEL - RUH`
- Other powers: Dynamic adjustment based on actual positions

### Implementation Details

**File**: `demo_perfect_game.py`

**Key Components:**
1. **ScenarioData Class**: Stores year, season, phase, orders, expected outcomes, description
2. **PerfectDemoGame Class**: Manages scenario playback and map generation
3. **Dynamic Order Adjustment**: Adjusts orders based on actual game state positions

**Map Generation:**
- Generate 4 maps per phase: initial, orders, resolution, final
- **IMPORTANT**: Maps are ONLY generated for scenarios that are actually processed. Scenarios that are skipped (e.g., retreat phases with no dislodgements, or scenarios that don't match the current game state) do not generate maps. This ensures the output only contains maps for turns that actually took place.
- Naming convention: `perfect_demo_{year}_{season_num}_{phase_num}_{season}_{phase}_{type}.png`
- Uses existing `Map.render_board_png_orders()` and `Map.render_board_png_resolution()`

**Deterministic Behavior:**
- All orders are hardcoded in the scenario definitions. The game is fully deterministic - running it multiple times with the same inputs will produce identical results.
- The only exception is retreat orders, which are generated based on actual dislodged units. However, this is still deterministic because the dislodged units are determined by the hardcoded orders and game engine logic.
- Order adjustments (e.g., adjusting unit positions based on actual game state) are deterministic transformations of the hardcoded orders.
- The game stops deterministically when:
  1. The game reaches a `done` state (victory condition met)
  2. All scenarios in the hardcoded list have been processed or skipped
  3. A maximum phase limit (50) is reached (safety limit)
- This deterministic behavior makes the perfect demo game a final test that every feature is working correctly. Any changes to game logic will be immediately visible in the demo game results.

**State Verification:**
- After each phase, verify expected outcomes
- Check supply center control changes
- Verify unit positions match expectations
