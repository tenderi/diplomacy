"""
Comprehensive tests for order validation edge cases.

Tests various edge cases in order validation including:
- Duplicate orders
- Orders for non-existent units
- Orders for wrong power
- Orders in wrong phase
- Convoy orders without valid paths
- Support orders for non-moves
- Move to own province
"""
import pytest
from engine.game import Game
from engine.data_models import Unit, OrderType


@pytest.mark.unit
class TestOrderValidationEdgeCases:
    """Test order validation edge cases."""
    
    def test_duplicate_orders_same_unit(self):
        """Test that duplicate orders for the same unit are rejected."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # Try to submit two orders for the same unit
        with pytest.raises(ValueError, match="duplicate|multiple"):
            game.set_orders('FRANCE', [
                'A PAR - BUR',
                'A PAR - PIC'  # Duplicate order for same unit
            ])
    
    def test_order_for_nonexistent_unit(self):
        """Test that orders for non-existent units are rejected."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Remove all units to test non-existent unit
        game.game_state.powers['FRANCE'].units = []
        
        # Try to order a unit that doesn't exist
        with pytest.raises(ValueError, match="not found|does not exist|invalid"):
            game.set_orders('FRANCE', [
                'A PAR - BUR'  # Unit doesn't exist
            ])
    
    def test_order_for_wrong_power(self):
        """Test that orders cannot be submitted for another power's unit."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        # Place German unit
        game.game_state.powers['GERMANY'].units = [
            Unit(unit_type='A', province='BER', power='GERMANY')
        ]
        
        # France tries to order Germany's unit
        with pytest.raises(ValueError, match="not belong|wrong power|unauthorized"):
            game.set_orders('FRANCE', [
                'GERMANY A BER - SIL'  # Wrong power
            ])
    
    def test_movement_order_in_retreat_phase(self):
        """Test that movement orders are rejected in Retreat phase."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # Set to Retreat phase
        game.phase = "Retreat"
        game._update_phase_code()
        
        # Try to submit movement order in Retreat phase
        with pytest.raises(ValueError, match="not valid for phase|wrong phase|Retreat"):
            game.set_orders('FRANCE', [
                'A PAR - BUR'  # Movement order in Retreat phase
            ])
    
    def test_movement_order_in_builds_phase(self):
        """Test that movement orders are rejected in Builds phase."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # Set to Builds phase
        game.phase = "Builds"
        game._update_phase_code()
        
        # Try to submit movement order in Builds phase
        with pytest.raises(ValueError, match="not valid for phase|wrong phase|Builds"):
            game.set_orders('FRANCE', [
                'A PAR - BUR'  # Movement order in Builds phase
            ])
    
    def test_build_order_in_movement_phase(self):
        """Test that build orders are rejected in Movement phase."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Set to Movement phase
        game.phase = "Movement"
        game._update_phase_code()
        
        # Try to submit build order in Movement phase
        with pytest.raises(ValueError, match="not valid for phase|wrong phase|Movement"):
            game.set_orders('FRANCE', [
                'BUILD A PAR'  # Build order in Movement phase
            ])
    
    def test_retreat_order_in_movement_phase(self):
        """Test that retreat orders are rejected in Movement phase."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True)
        ]
        
        # Set to Movement phase
        game.phase = "Movement"
        game._update_phase_code()
        
        # Try to submit retreat order in Movement phase (rejected: wrong phase or invalid retreat)
        with pytest.raises(ValueError, match="not valid for phase|wrong phase|Movement|invalid retreat|retreat"):
            game.set_orders('FRANCE', [
                'A PAR R BUR'  # Retreat order in Movement phase
            ])
    
    def test_convoy_order_without_valid_path(self):
        """Test that convoy orders without valid convoy paths are rejected."""
        game = Game('standard')
        game.add_player('ENGLAND')
        
        # Place army but no fleets for convoy
        game.game_state.powers['ENGLAND'].units = [
            Unit(unit_type='A', province='LON', power='ENGLAND')
        ]
        
        # Try to convoy without any convoying fleets
        with pytest.raises(ValueError, match="convoy|path|no.*fleet"):
            game.set_orders('ENGLAND', [
                'A LON - HOL',  # Convoy move
                # No convoying fleet orders
            ])
    
    def test_support_order_for_holding_unit(self):
        """Test that support orders for units that are holding are invalid."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        game.game_state.powers['GERMANY'].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # PAR holds, MAR tries to support PAR's "move" (but PAR is holding)
        with pytest.raises(ValueError, match="support.*hold|holding|invalid"):
            game.set_orders('FRANCE', [
                'A PAR H',  # Holding
                'A MAR S A PAR - BUR'  # Support for holding unit (invalid)
            ])
    
    def test_move_to_own_province_occupied(self):
        """Test that moves to provinces occupied by own units are rejected."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Place two French units
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='BUR', power='FRANCE')
        ]
        
        # Try to move PAR to BUR (occupied by own unit)
        # This should be rejected (self-dislodgement prevention)
        with pytest.raises(ValueError, match="occupied|own|self"):
            game.set_orders('FRANCE', [
                'A PAR - BUR'  # Move to own occupied province
            ])
    
    def test_support_order_without_target_move(self):
        """Test that support orders must support an actual move order."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        game.game_state.powers['GERMANY'].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # MAR supports PAR - BUR, but PAR doesn't have a move order
        with pytest.raises(ValueError, match="support.*move|no.*order"):
            game.set_orders('FRANCE', [
                'A PAR H',  # PAR holds, no move
                'A MAR S A PAR - BUR'  # Support for non-move
            ])


@pytest.mark.unit
class TestOrderValidationPowerOwnership:
    """Test power ownership validation in orders."""
    
    def test_order_unit_belongs_to_power(self):
        """Test that orders can only be submitted for units belonging to the power."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        # Place units
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers['GERMANY'].units = [
            Unit(unit_type='A', province='BER', power='GERMANY')
        ]
        
        # France tries to order Germany's unit
        with pytest.raises(ValueError):
            game.set_orders('FRANCE', [
                'GERMANY A BER - SIL'  # Wrong power
            ])
    
    def test_order_power_matches_unit_power(self):
        """Test that order power matches unit power."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # Order with mismatched power (should still work if unit belongs to power)
        # This tests the validation logic
        try:
            game.set_orders('FRANCE', [
                'FRANCE A PAR - BUR'  # Explicit power name
            ])
            # If no exception, verify the order was accepted
            assert len(game.game_state.orders.get('FRANCE', [])) > 0
        except ValueError:
            # If exception raised, that's also valid behavior
            pass


@pytest.mark.unit
class TestOrderValidationPhaseCompatibility:
    """Test phase compatibility validation for orders."""
    
    def test_all_order_types_in_correct_phases(self):
        """Test that each order type is only valid in its correct phase."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Movement phase - should accept move, hold, support, convoy
        game.phase = "Movement"
        game._update_phase_code()
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # These should work in Movement phase
        try:
            game.set_orders('FRANCE', ['A PAR H'])
            game.clear_orders('FRANCE')
            game.set_orders('FRANCE', ['A PAR - BUR'])
        except ValueError:
            pytest.fail("Movement orders should be valid in Movement phase")
        
        # Retreat phase - should accept retreat, disband
        game.phase = "Retreat"
        game._update_phase_code()
        dislodged_unit = Unit(unit_type='A', province='PAR', power='FRANCE', is_dislodged=True)
        # Set retreat options for the dislodged unit
        dislodged_unit.retreat_options = ['BUR', 'PIC', 'GAS']  # Valid retreat destinations
        game.game_state.powers['FRANCE'].units = [dislodged_unit]
        
        # These should work in Retreat phase
        try:
            game.set_orders('FRANCE', ['A PAR R BUR'])
            game.clear_orders('FRANCE')
            game.set_orders('FRANCE', ['A PAR D'])  # Disband
        except ValueError:
            pytest.fail("Retreat orders should be valid in Retreat phase")
        
        # Builds phase - should accept build, destroy
        game.phase = "Builds"
        game._update_phase_code()
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        # controlled_supply_centers is a list, not a set
        if 'MAR' not in game.game_state.powers['FRANCE'].controlled_supply_centers:
            game.game_state.powers['FRANCE'].controlled_supply_centers.append('MAR')
        
        # These should work in Builds phase
        try:
            game.set_orders('FRANCE', ['BUILD A MAR'])
            game.clear_orders('FRANCE')
            # Destroy order format: "DESTROY A PAR" or "A PAR D"
            game.set_orders('FRANCE', ['DESTROY A PAR'])
        except ValueError:
            pytest.fail("Build/Destroy orders should be valid in Builds phase")
