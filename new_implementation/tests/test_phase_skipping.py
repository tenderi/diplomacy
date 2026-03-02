"""
Tests for phase skipping edge cases in Diplomacy.

These tests verify that the game correctly skips phases when appropriate:
- Skip Retreat phase when no units are dislodged
- Skip Retreat phase when all dislodged units disband
- Correct phase transitions in all scenarios
"""
import pytest
from engine.game import Game
from engine.data_models import Unit


@pytest.mark.unit
class TestPhaseSkipping:
    """Test phase skipping scenarios."""
    
    def test_skip_retreat_no_dislodgements(self):
        """Test that Retreat phase is skipped when no units are dislodged."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Place units that won't conflict
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BER', power='GERMANY')
        ]
        
        # Spring Movement phase - no conflicts
        assert game.phase == "Movement"
        assert game.season == "Spring"
        
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", ["GERMANY A BER H"])
        game.process_turn()
        
        # Should skip Retreat phase and go directly to Autumn Movement
        # (or Builds if it's Autumn, but for Spring it should go to Autumn Movement)
        assert game.phase == "Movement", f"Expected Movement phase, got {game.phase}"
        assert game.season == "Autumn", f"Expected Autumn season, got {game.season}"
        assert "A1901M" in game.phase_code or game.phase_code == "A1901M", \
            f"Expected A1901M phase code, got {game.phase_code}"
    
    def test_skip_retreat_all_disband(self):
        """Test that Retreat phase is skipped when all dislodged units disband."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Place units that will conflict
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')
        ]
        
        # Spring Movement - Germany attacks and dislodges France
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", [
            "GERMANY A BUR - PAR",
            "GERMANY A PIC S A BUR - PAR"
        ])
        game.process_turn()
        
        # Should be in Retreat phase
        assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"
        
        # Process retreat phase with no retreat orders (all units disband)
        game.process_turn()
        
        # Should skip to next phase (Autumn Movement or Builds)
        assert game.phase in ["Movement", "Builds"], \
            f"Expected Movement or Builds phase, got {game.phase}"
    
    def test_spring_with_dislodgements_retreat_phase(self):
        """Test Spring Movement → Retreat → Autumn Movement transition."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Place units
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')
        ]
        
        # Spring Movement - create dislodgement
        assert game.phase == "Movement"
        assert game.season == "Spring"
        
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", [
            "GERMANY A BUR - PAR",
            "GERMANY A PIC S A BUR - PAR"
        ])
        game.process_turn()
        
        # Should be in Retreat phase
        assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"
        assert "R" in game.phase_code, f"Expected R in phase code, got {game.phase_code}"
        
        # Process retreat (no orders = disband)
        game.process_turn()
        
        # Should go to Autumn Movement
        assert game.phase == "Movement", f"Expected Movement phase, got {game.phase}"
        assert game.season == "Autumn", f"Expected Autumn season, got {game.season}"
    
    def test_autumn_with_dislodgements_retreat_then_builds(self):
        """Test Autumn Movement → Retreat → Builds transition."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Start in Autumn (manually set after Spring)
        game.season = "Autumn"
        game.year = 1901
        game.phase = "Movement"
        game._update_phase_code()
        
        # Place units
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')
        ]
        
        # Autumn Movement - create dislodgement
        assert game.phase == "Movement"
        assert game.season == "Autumn"
        
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", [
            "GERMANY A BUR - PAR",
            "GERMANY A PIC S A BUR - PAR"
        ])
        game.process_turn()
        
        # Should be in Retreat phase
        assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"
        
        # Process retreat
        game.process_turn()
        
        # Should go to Builds phase
        assert game.phase == "Builds", f"Expected Builds phase, got {game.phase}"
        assert "B" in game.phase_code, f"Expected B in phase code, got {game.phase_code}"
    
    def test_autumn_without_dislodgements_skip_retreat(self):
        """Test Autumn Movement → Builds (skip Retreat) when no dislodgements."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Start in Autumn
        game.season = "Autumn"
        game.year = 1901
        game.phase = "Movement"
        game._update_phase_code()
        
        # Place units that won't conflict
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BER', power='GERMANY')
        ]
        
        # Autumn Movement - no conflicts
        assert game.phase == "Movement"
        assert game.season == "Autumn"
        
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", ["GERMANY A BER H"])
        game.process_turn()
        
        # Should skip Retreat and go directly to Builds
        assert game.phase == "Builds", f"Expected Builds phase, got {game.phase}"
        assert game.season == "Autumn", f"Expected Autumn season, got {game.season}"
        assert "B" in game.phase_code, f"Expected B in phase code, got {game.phase_code}"


@pytest.mark.unit
class TestBuildsPhaseTransitions:
    """Test transitions from Builds phase."""
    
    def test_builds_to_next_spring_movement(self):
        """Test that Builds phase transitions to next Spring Movement and increments year."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Start in Builds phase (after Autumn)
        game.season = "Autumn"
        game.year = 1901
        game.phase = "Builds"
        game._update_phase_code()
        
        # Process builds phase (no orders)
        game.process_turn()
        
        # Should go to Spring Movement of next year
        assert game.phase == "Movement", f"Expected Movement phase, got {game.phase}"
        assert game.season == "Spring", f"Expected Spring season, got {game.season}"
        assert game.year == 1902, f"Expected year 1902, got {game.year}"
        assert "S1902M" in game.phase_code or game.phase_code == "S1902M", \
            f"Expected S1902M phase code, got {game.phase_code}"
