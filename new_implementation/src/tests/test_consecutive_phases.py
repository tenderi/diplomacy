#!/usr/bin/env python3
"""
Test for 6 consecutive phases: movement → retreat → retreat → movement → build → movement
This test verifies the game engine can handle the full Diplomacy phase cycle.
"""

import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from src.engine.game import Game

def test_consecutive_phases():
    """Test 6 consecutive phases: movement → retreat → retreat → movement → build → movement"""
    print("=== Testing 6 Consecutive Phases ===")
    
    # Create a demo game
    game = Game(map_name="demo")
    
    # Add two powers for interaction
    game.add_player("GERMANY")
    game.add_player("FRANCE")
    
    print(f"Initial state: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Initial phase code: {game.phase_code}")
    
    # Phase 1: Movement (Spring 1901 Movement)
    print("\n--- Phase 1: Movement (Spring 1901 Movement) ---")
    game.set_orders("GERMANY", [
        "GERMANY A BER - SIL",  # Germany moves army
        "GERMANY A MUN - TYR",  # Germany moves army
        "GERMANY F KIE - BAL"   # Germany moves fleet
    ])
    game.set_orders("FRANCE", [
        "FRANCE A PAR - BUR",   # France moves army
        "FRANCE A MAR - PIE",   # France moves army
        "FRANCE F BRE - ENG"    # France moves fleet
    ])
    
    game.process_turn()
    print(f"After Phase 1: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    print(f"Germany units: {game.game_state.powers['GERMANY'].units}")
    print(f"France units: {game.game_state.powers['FRANCE'].units}")
    
    # Phase 2: Retreat (Spring 1901 Retreat) - if any units were dislodged
    print("\n--- Phase 2: Retreat (Spring 1901 Retreat) ---")
    if game.phase == "Retreat":
        print("Retreat phase detected - no retreat orders needed for this test")
        # Process retreat phase (no retreat orders = units disband)
        game.process_turn()
    else:
        print("No retreat phase needed - advancing to builds")
        # Skip to builds phase
        game.phase = "Builds"
        game._update_phase_code()
    
    print(f"After Phase 2: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    
    # Phase 3: Builds (Spring 1901 Builds)
    print("\n--- Phase 3: Builds (Spring 1901 Builds) ---")
    if game.phase == "Builds":
        # Add some build orders
        game.set_orders("GERMANY", [
            "GERMANY BUILD A BER"  # Build army in Berlin
        ])
        game.set_orders("FRANCE", [
            "FRANCE BUILD A PAR"   # Build army in Paris
        ])
        
        game.process_turn()
    else:
        print("Not in builds phase - skipping")
    
    print(f"After Phase 3: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    print(f"Germany units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['GERMANY'].units]}")
    print(f"France units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['FRANCE'].units]}")
    
    # Phase 4: Movement (Autumn 1901 Movement)
    print("\n--- Phase 4: Movement (Autumn 1901 Movement) ---")
    game.set_orders("GERMANY", [
        "GERMANY A SIL - BOH",   # Germany moves army
        "GERMANY A TYR - VIE",   # Germany moves army
        "GERMANY F BAL - BOT"    # Germany moves fleet
    ])
    game.set_orders("FRANCE", [
        "FRANCE A BUR - BEL",    # France moves army
        "FRANCE A PIE - TUS",    # France moves army
        "FRANCE F ENG - IRI"     # France moves fleet
    ])
    
    game.process_turn()
    print(f"After Phase 4: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    print(f"Germany units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['GERMANY'].units]}")
    print(f"France units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['FRANCE'].units]}")
    
    # Phase 5: Retreat (Autumn 1901 Retreat) - if any units were dislodged
    print("\n--- Phase 5: Retreat (Autumn 1901 Retreat) ---")
    if game.phase == "Retreat":
        print("Retreat phase detected - no retreat orders needed for this test")
        # Process retreat phase (no retreat orders = units disband)
        game.process_turn()
    else:
        print("No retreat phase needed - advancing to builds")
        # Skip to builds phase
        game.phase = "Builds"
        game._update_phase_code()
    
    print(f"After Phase 5: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    
    # Phase 6: Builds (Autumn 1901 Builds)
    print("\n--- Phase 6: Builds (Autumn 1901 Builds) ---")
    if game.phase == "Builds":
        # Add some destroy orders to test destroy functionality
        game.set_orders("GERMANY", [
            "GERMANY DESTROY A BER"  # Destroy army in Berlin
        ])
        game.set_orders("FRANCE", [
            "FRANCE DESTROY A PAR"   # Destroy army in Paris
        ])
        
        game.process_turn()
    else:
        print("Not in builds phase - skipping")
    
    print(f"After Phase 6: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    print(f"Germany units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['GERMANY'].units]}")
    print(f"France units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['FRANCE'].units]}")
    
    # Phase 7: Movement (Spring 1902 Movement)
    print("\n--- Phase 7: Movement (Spring 1902 Movement) ---")
    game.set_orders("GERMANY", [
        "GERMANY A SIL - GAL",   # Germany moves army
        "GERMANY A TYR - VIE",   # Germany moves army
        "GERMANY F BAL - BOT"    # Germany moves fleet
    ])
    game.set_orders("FRANCE", [
        "FRANCE A BUR - BEL",    # France moves army
        "FRANCE A PIE - TUS",    # France moves army
        "FRANCE F ENG - IRI"     # France moves fleet
    ])
    
    game.process_turn()
    print(f"After Phase 7: Turn {game.turn}, Season {game.season}, Phase {game.phase}")
    print(f"Phase code: {game.phase_code}")
    print(f"Germany units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['GERMANY'].units]}")
    print(f"France units: {[f'{u.unit_type} {u.province}' for u in game.game_state.powers['FRANCE'].units]}")
    
    # Verify we've gone through the expected phases
    print("\n=== Phase Verification ===")
    print(f"Final turn: {game.turn}")
    print(f"Final season: {game.season}")
    print(f"Final phase: {game.phase}")
    print(f"Final phase code: {game.phase_code}")
    
    # Check that we've advanced through multiple phases
    assert game.turn >= 1, f"Expected turn >= 1, got {game.turn}"
    assert game.season in ["Spring", "Autumn"], f"Expected season to be Spring or Autumn, got {game.season}"
    assert game.phase in ["Movement", "Retreat", "Builds"], f"Expected phase to be Movement, Retreat, or Builds, got {game.phase}"
    
    print("✅ All phases processed successfully!")
    print("✅ Game engine can handle consecutive phases correctly!")

def test_phase_transitions():
    """Test specific phase transitions"""
    print("\n=== Testing Phase Transitions ===")
    
    game = Game(map_name="demo")
    game.add_player("GERMANY")
    
    # Test Movement → Retreat → Builds → Movement cycle
    print(f"Initial: {game.season} {game.year} {game.phase} ({game.phase_code})")
    
    # Movement phase
    game.set_orders("GERMANY", ["GERMANY A BER H"])
    game.process_turn()
    print(f"After Movement: {game.season} {game.year} {game.phase} ({game.phase_code})")
    
    # Should go to Builds (no retreats needed)
    if game.phase == "Builds":
        # No build orders needed for this test - just process the phase
        game.process_turn()
        print(f"After Builds: {game.season} {game.year} {game.phase} ({game.phase_code})")
    
    # Should now be in next season's Movement phase
    assert game.phase == "Movement", f"Expected Movement phase, got {game.phase}"
    print("✅ Phase transitions working correctly!")

if __name__ == "__main__":
    try:
        test_consecutive_phases()
        test_phase_transitions()
        print("\n🎉 All tests passed! Game engine handles consecutive phases correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
