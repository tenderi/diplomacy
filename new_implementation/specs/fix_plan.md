# Perfect Automated Demo Game Design Plan

## Overview

Create a new hardcoded automated demo game that demonstrates all Diplomacy mechanics through a carefully choreographed sequence. Unlike the current dynamic AI-based demo, this will use predetermined orders to showcase specific scenarios: 2-1 battles, support cuts, convoys, standoffs, retreats, and build phases.

## Core Design Principles

1. **Hardcoded Orders**: All orders pre-written in a scenario sequence, no AI generation
2. **Strategic Logic**: Every move makes strategic sense; no self-attacks or illogical orders
3. **Complete Coverage**: Demonstrates all 7 order types (Move, Hold, Support, Convoy, Retreat, Build, Destroy)
4. **Educational Focus**: Each phase teaches specific mechanics
5. **Visual Storytelling**: Maps show clear cause-and-effect relationships

## Game Structure

### Duration: 2 Years (1901-1902)

- Spring 1901: Initial expansion and first conflicts
- Fall 1901: Consolidation, supply center changes, builds
- Spring 1902: Advanced tactics, support combinations, convoys
- Fall 1902: Complex conflicts, retreats, final builds

### Phase Sequence

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

## Scenario Design: Spring 1901

### Objectives

- Demonstrate basic moves and holds
- Show first 2-1 battle with support
- Create one dislodgement for retreat phase

### Hardcoded Orders

**AUSTRIA:**

- `A VIE - TYR` (expansion move)
- `A BUD - RUM` (expansion move)
- `F TRI H` (defensive hold)

**ENGLAND:**

- `F LON - ENG` (fleet positioning)
- `F EDI - NTH` (fleet expansion)
- `A LVP - CLY` (army positioning)

**FRANCE:**

- `A PAR - BUR` (move to Belgium border)
- `A MAR - PIE` (southern expansion)
- `F BRE - MAO` (fleet expansion)

**GERMANY:**

- `A BER - KIE` (movement)
- `A MUN - SIL` (movement)
- `F KIE - HOL` (move with support from army)

**ITALY:**

- `A ROM - VEN` (movement)
- `A NAP - APU` (movement)
- `F NAP - ION` (fleet expansion)

**RUSSIA:**

- `A MOS - UKR` (movement)
- `A WAR - GAL` (movement toward Austria)
- `F SEV - BLA` (fleet expansion)
- `F STP - BOT` (fleet expansion)

**TURKEY:**

- `A CON - BUL` (movement)
- `A SMY - ARM` (movement)
- `F ANK - BLA` (fleet to Black Sea)

### Expected Outcomes

- Basic positioning established
- No major conflicts in first turn
- Units in position for Fall conflicts

## Scenario Design: Fall 1901

### Objectives

- Demonstrate 2-1 battle (supported attack succeeds)
- Show standoff (equal strength bounce)
- Demonstrate support cut mechanics
- Create dislodgement for retreat phase

### Hardcoded Orders

**AUSTRIA:**

- `A TYR - VEN` (attack Italy)
- `A RUM H` (hold, supported)
- `F TRI S A TYR - VEN` (support attack)

**ENGLAND:**

- `F ENG - BEL` (move to Belgium)
- `F NTH S F ENG - BEL` (support move)
- `A CLY H` (hold)

**FRANCE:**

- `A BUR - BEL` (attack Belgium, creates 2-1 with support)
- `A PIE - TYS` (fleet movement)
- `F MAO S A BUR - BEL` (support attack - creates 2-1)

**GERMANY:**

- `A SIL - GAL` (attack toward Russia)
- `A HOL - BEL` (competing for Belgium - will bounce)
- `A KIE S A HOL - BEL` (support - creates standoff with France)

**ITALY:**

- `A VEN H` (hold, will be dislodged)
- `A APU S A VEN H` (defensive support, will be cut)
- `F ION - ADR` (fleet movement)

**RUSSIA:**

- `A UKR - RUM` (attack Romania)
- `A GAL S A UKR - RUM` (support attack - creates 2-1)
- `F BLA - CON` (attack Constantinople)
- `F BOT S F BLA - CON` (support - invalid support, shows support rules)

**TURKEY:**

- `A BUL - RUM` (competing for Romania - will bounce)
- `A ARM - SEV` (attack Russia)
- `F BLA H` (hold, will be dislodged)

### Expected Outcomes

- France takes Belgium with 2-1 support (A BUR + F MAO support vs F ENG)
- Standoff in Belgium between Germany and France
- Austria takes Venice with 2-1 (A TYR + F TRI support vs A VEN)
- Russia takes Romania with 2-1 (A UKR + A GAL support vs A RUM)
- Turkey's fleet in Black Sea dislodged
- Italy's army in Venice dislodged

## Scenario Design: Fall 1901 Retreat

### Objectives

- Demonstrate retreat orders
- Show forced disband (no valid retreat)

### Hardcoded Retreat Orders

**ITALY:**

- `A VEN R APU` (retreat to Apulia)

**TURKEY:**

- `F BLA D` (disband - no valid retreat, Black Sea surrounded)

### Expected Outcomes

- Italy retreats successfully
- Turkey forced to disband

## Scenario Design: Fall 1901 Builds

### Objectives

- Demonstrate build orders
- Show supply center control changes

### Hardcoded Build Orders

**FRANCE:** (gained Belgium)

- `BUILD A MAR` (build in Marseilles)

**AUSTRIA:** (gained Venice)

- `BUILD A BUD` (build in Budapest)

**RUSSIA:** (gained Romania)

- `BUILD A MOS` (build in Moscow)

**GERMANY, ENGLAND, ITALY, TURKEY:**

- No builds (no net SC gains)

### Expected Outcomes

- France builds army in Marseilles
- Austria builds army in Budapest
- Russia builds army in Moscow
- All other powers hold steady

## Scenario Design: Spring 1902

### Objectives

- Demonstrate convoy orders
- Show complex support combinations
- Create multiple conflicts

### Hardcoded Orders

**ENGLAND:**

- `A LVP - BEL VIA CONVOY` (convoy to Belgium)
- `F NTH C A LVP - BEL` (convoy order)
- `F ENG S F NTH` (support convoy fleet)

**FRANCE:**

- `A BEL H` (hold Belgium)
- `A PAR S A BEL H` (support hold)
- `F MAO - SPA` (fleet to Spain)
- `A MAR - PIE` (army south)

**GERMANY:**

- `A KIE - HOL` (retake Holland)
- `A SIL - WAR` (attack Poland)
- `A BEL - RUH` (retreat from Belgium conflict)

### Expected Outcomes

- England successfully convoys army to Belgium
- Complex 3-way conflict in Belgium
- Various positioning moves

## File Structure

### New File: `demo_perfect_game.py`

Location: `/home/helgejalonen/diplomacy/new_implementation/demo_perfect_game.py`

**Key Components:**

1. **ScenarioData Class**
```python
@dataclass
class ScenarioData:
    year: int
    season: str
    phase: str
    orders: Dict[str, List[str]]
    expected_outcomes: Dict[str, Any]  # For validation
    description: str  # Educational description
```

2. **PerfectDemoGame Class**
```python
class PerfectDemoGame:
    def __init__(self):
        self.scenarios: List[ScenarioData] = []
        self.load_scenarios()
    
    def load_scenarios(self):
        """Load all hardcoded scenario data"""
        
    def run_demo(self):
        """Execute the perfect demo game sequence"""
        
    def process_scenario(self, scenario: ScenarioData):
        """Process a single scenario phase"""
```

3. **Scenario Registry**

All orders stored in a structured format:

```python
SCENARIOS = {
    "1901_Spring_Movement": ScenarioData(
        year=1901,
        season="Spring",
        phase="Movement",
        orders={
            "AUSTRIA": ["A VIE - TYR", "A BUD - RUM", "F TRI H"],
            ...
        },
        description="Initial positioning phase..."
    ),
    ...
}
```

## Implementation Details

### Order Validation

- All hardcoded orders must be legal (validated before game starts)
- No self-attacks or invalid moves
- Support orders must follow adjacency rules
- Convoy routes must be valid

### Map Generation

- Generate 4 maps per phase: initial, orders, resolution, final
- Use existing `Map.render_board_png_orders()` and `Map.render_board_png_resolution()`
- Follow naming convention: `perfect_demo_{counter:02d}_{year}_{season}_{phase}_{type}.png`

### Educational Annotations

- Each scenario includes description text
- Maps can include annotations explaining key mechanics
- Console output explains what's happening and why

### State Verification

- After each phase, verify expected outcomes
- Check supply center control changes
- Verify unit positions match expectations
- Log any discrepancies

## Integration Points

### Server Integration

- Uses existing `Server.process_command()` interface
- No changes needed to server code
- Same game creation and order submission flow

### Map Visualization

- Uses existing `Map.render_board_png_*()` methods
- All visualization features already implemented
- No new visualization code needed

## Success Criteria

1. All 7 order types demonstrated
2. All 3 phases shown (Movement, Retreat, Builds)
3. Strategic coherence (no illogical moves)
4. Clear 2-1 battle scenarios
5. Support cut demonstration
6. Convoy demonstration
7. Standoff demonstration
8. Retreat demonstration
9. Build/Destroy demonstration
10. All maps generate correctly

## Testing Strategy

1. Validate all hardcoded orders are legal
2. Run complete scenario and verify outcomes match expectations
3. Verify all maps generate without errors
4. Check file naming and ordering
5. Validate strategic coherence (no self-attacks, logical moves)

## Future Enhancements (Out of Scope)

- Multiple scenario variants
- Interactive mode to step through phases
- Detailed annotations on maps
- Export to educational formats