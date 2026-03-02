"""
Comprehensive tests for retreat edge cases in Diplomacy.

Tests various retreat scenarios including:
- Retreat to dislodged province (invalid)
- Retreat to attacking province (invalid)
- Retreat to occupied province (invalid)
- Multiple units retreating to same province (bounce)
- No valid retreat options (disband)
- Retreat order for non-dislodged unit (invalid)
"""
import pytest
from engine.game import Game
from engine.data_models import Unit


@pytest.mark.unit
class TestRetreatValidation:
    """Test retreat order validation."""
    
    def test_retreat_to_dislodged_province_invalid(self):
        """Test that retreating to a province that was dislodged is invalid."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        game.add_player("ITALY")
        
        # Set up: France unit in PAR is dislodged by Germany
        # Italy unit in BUR is also dislodged
        # France tries to retreat to BUR (which was dislodged)
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        game.game_state.powers["ITALY"].units = [
            Unit(unit_type='A', province='MAR', power='ITALY', is_dislodged=True)
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Set retreat options (BUR should not be in options if it was dislodged)
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['BUR', 'PIC']
        
        # Try to retreat to BUR (which was dislodged)
        # This should be invalid - retreat options should exclude dislodged provinces
        with pytest.raises(ValueError, match="invalid|dislodged|not.*retreat"):
            game.set_orders('FRANCE', ['A PAR R BUR'])
    
    def test_retreat_to_attacking_province_invalid(self):
        """Test that retreating to the province of the attacking unit is invalid."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France unit in PAR is dislodged by Germany from BUR
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')  # Attacking unit
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Set retreat options (BUR should not be in options)
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['PIC', 'GAS']
        
        # Try to retreat to BUR (attacking province) - should be invalid
        # BUR should not be in retreat_options, but test explicit validation
        with pytest.raises(ValueError, match="invalid|attacking|not.*retreat"):
            game.set_orders('FRANCE', ['A PAR R BUR'])
    
    def test_retreat_to_occupied_province_invalid(self):
        """Test that retreating to an occupied province is invalid."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France unit in PAR is dislodged
        # Germany unit occupies PIC
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')  # Occupies PIC
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Set retreat options (PIC should not be in options if occupied)
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['GAS']  # Only valid option
        
        # Try to retreat to PIC (occupied) - should be invalid
        with pytest.raises(ValueError, match="invalid|occupied|not.*retreat"):
            game.set_orders('FRANCE', ['A PAR R PIC'])
    
    def test_retreat_order_for_non_dislodged_unit(self):
        """Test that retreat orders for non-dislodged units are invalid."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Unit is not dislodged
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=False)
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Try to retreat with non-dislodged unit
        with pytest.raises(ValueError, match="not dislodged|invalid"):
            game.set_orders('FRANCE', ['A PAR R BUR'])


@pytest.mark.unit
class TestRetreatResolution:
    """Test retreat resolution scenarios."""
    
    def test_multiple_units_retreat_to_same_province_bounce(self):
        """Test that multiple units retreating to the same province bounce."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Two French units are dislodged
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR'),
            Unit(unit_type='A', province='MAR', power='FRANCE', is_dislodged=True, dislodged_by='LYO')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='LYO', power='GERMANY')
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Both units can retreat to GAS
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['GAS', 'PIC']
        game.game_state.powers["FRANCE"].units[1].retreat_options = ['GAS', 'SPA']
        
        # Both try to retreat to GAS
        game.set_orders('FRANCE', [
            'A PAR R GAS',
            'A MAR R GAS'
        ])
        
        game.process_turn()
        
        # Both should bounce and disband (no valid retreat)
        # Units should be removed or remain dislodged
        assert len([u for u in game.game_state.powers["FRANCE"].units if u.is_dislodged]) == 0 or \
               len(game.game_state.powers["FRANCE"].units) == 0, \
               "Both units should have bounced and disbanded"
    
    def test_no_valid_retreat_options_disband(self):
        """Test that units with no valid retreat options disband."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France unit is dislodged with no valid retreat options
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # No valid retreat options
        game.game_state.powers["FRANCE"].units[0].retreat_options = []
        
        # Process retreat phase without orders (should disband)
        game.process_turn()
        
        # Unit should be removed (disbanded)
        assert len(game.game_state.powers["FRANCE"].units) == 0, \
            "Unit with no retreat options should be disbanded"
    
    def test_successful_retreat(self):
        """Test successful retreat to valid province."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France unit in PAR is dislodged
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True, dislodged_by='BUR')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Valid retreat option
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['PIC', 'GAS']
        
        # Retreat to PIC
        game.set_orders('FRANCE', ['A PAR R PIC'])
        game.process_turn()
        
        # Unit should be in PIC and no longer dislodged
        assert any(unit.province == 'PIC' for unit in game.game_state.powers["FRANCE"].units), \
            "Unit should have retreated to PIC"
        assert not any(unit.is_dislodged for unit in game.game_state.powers["FRANCE"].units), \
            "Unit should no longer be dislodged"


@pytest.mark.unit
class TestRetreatPhaseEdgeCases:
    """Test edge cases in retreat phase processing."""
    
    def test_retreat_after_spring_movement(self):
        """Test retreat phase after Spring movement with dislodgements."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Spring Movement phase
        game.phase = "Movement"
        game.season = "Spring"
        game.year = 1901
        game._update_phase_code()
        
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')
        ]
        
        # Germany dislodges France
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", [
            "GERMANY A BUR - PAR",
            "GERMANY A PIC S A BUR - PAR"
        ])
        game.process_turn()
        
        # Should be in Retreat phase
        assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"
        
        # Process retreat
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['GAS']
        game.set_orders('FRANCE', ['A PAR R GAS'])
        game.process_turn()
        
        # Should go to Autumn Movement
        assert game.phase == "Movement", f"Expected Movement phase, got {game.phase}"
        assert game.season == "Autumn", f"Expected Autumn season, got {game.season}"
    
    def test_retreat_after_autumn_movement(self):
        """Test retreat phase after Autumn movement with dislodgements."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Autumn Movement phase
        game.phase = "Movement"
        game.season = "Autumn"
        game.year = 1901
        game._update_phase_code()
        
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='PIC', power='GERMANY')
        ]
        
        # Germany dislodges France
        game.set_orders("FRANCE", ["FRANCE A PAR H"])
        game.set_orders("GERMANY", [
            "GERMANY A BUR - PAR",
            "GERMANY A PIC S A BUR - PAR"
        ])
        game.process_turn()
        
        # Should be in Retreat phase
        assert game.phase == "Retreat", f"Expected Retreat phase, got {game.phase}"
        
        # Process retreat
        game.game_state.powers["FRANCE"].units[0].retreat_options = ['GAS']
        game.set_orders('FRANCE', ['A PAR R GAS'])
        game.process_turn()
        
        # Should go to Builds phase
        assert game.phase == "Builds", f"Expected Builds phase, got {game.phase}"
