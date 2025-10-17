#!/usr/bin/env python3
"""
Test enhanced validation functionality in the game engine.
"""

import pytest
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from engine.game import Game
from engine.data_models import Unit, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder, OrderStatus


class TestEnhancedValidation:
    """Test enhanced validation functionality."""

    def test_move_validation_basic(self):
        """Test basic move validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Valid move: Army from Paris to Burgundy
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        valid_move = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(valid_move) == True
        
        # Invalid move: Army to water province
        invalid_move = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='ENG',  # Water province
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(invalid_move) == False

    def test_move_validation_adjacency(self):
        """Test move validation with adjacency checks."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # Invalid move: Non-adjacent province
        invalid_move = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='MOS',  # Not adjacent to Paris
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(invalid_move) == False

    def test_move_validation_occupation(self):
        """Test move validation with occupation checks."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_burgundy = Unit(unit_type='A', province='BUR', power='GERMANY')
        
        game.game_state.powers['FRANCE'].units.append(army_paris)
        game.game_state.powers['GERMANY'].units.append(army_burgundy)
        
        # Invalid move: Target province occupied
        invalid_move = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',  # Occupied by German army
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(invalid_move) == False

    def test_fleet_move_validation(self):
        """Test fleet move validation."""
        game = Game('standard')
        game.add_player('ENGLAND')
        
        fleet_london = Unit(unit_type='F', province='LON', power='ENGLAND')
        game.game_state.powers['ENGLAND'].units.append(fleet_london)
        
        # Valid move: Fleet from London to English Channel
        valid_move = MoveOrder(
            power='ENGLAND',
            unit=fleet_london,
            target_province='ENG',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(valid_move) == True
        
        # Invalid move: Fleet to land province
        invalid_move = MoveOrder(
            power='ENGLAND',
            unit=fleet_london,
            target_province='PAR',  # Land province
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_move(invalid_move) == False

    def test_retreat_validation(self):
        """Test retreat validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_paris.is_dislodged = True
        army_paris.retreat_options = ['BUR', 'GAS']
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # Valid retreat
        valid_retreat = RetreatOrder(
            power='FRANCE',
            unit=army_paris,
            retreat_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_retreat(valid_retreat) == True
        
        # Invalid retreat: Unit not dislodged
        army_paris.is_dislodged = False
        assert game._is_valid_retreat(valid_retreat) == False
        
        # Invalid retreat: Not in retreat options
        army_paris.is_dislodged = True
        invalid_retreat = RetreatOrder(
            power='FRANCE',
            unit=army_paris,
            retreat_province='MAR',  # Not in retreat options
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_retreat(invalid_retreat) == False

    def test_build_validation(self):
        """Test build validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Set up power with more supply centers than units
        game.game_state.powers['FRANCE'].controlled_supply_centers = ['PAR', 'MAR', 'BRE']
        game.game_state.powers['FRANCE'].units = []  # No units yet
        
        # Valid build
        valid_build = BuildOrder(
            power='FRANCE',
            unit=Unit(unit_type='A', province='PAR', power='FRANCE'),  # Dummy unit for validation
            build_province='PAR',
            build_type='A',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_build(valid_build) == True
        
        # Invalid build: Power doesn't need builds
        game.game_state.powers['FRANCE'].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='F', province='BRE', power='FRANCE')
        ]
        
        assert game._is_valid_build(valid_build) == False

    def test_destroy_validation(self):
        """Test destroy validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_marseille = Unit(unit_type='A', province='MAR', power='FRANCE')
        fleet_brest = Unit(unit_type='F', province='BRE', power='FRANCE')
        
        game.game_state.powers['FRANCE'].units = [army_paris, army_marseille, fleet_brest]
        game.game_state.powers['FRANCE'].controlled_supply_centers = ['PAR', 'MAR']  # Only 2 supply centers
        
        # Valid destroy
        valid_destroy = DestroyOrder(
            power='FRANCE',
            unit=fleet_brest,
            destroy_unit=fleet_brest,
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_destroy(valid_destroy) == True
        
        # Invalid destroy: Power doesn't need destroys
        game.game_state.powers['FRANCE'].controlled_supply_centers = ['PAR', 'MAR', 'BRE']
        
        assert game._is_valid_destroy(valid_destroy) == False

    def test_phase_specific_validation(self):
        """Test phase-specific validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # Test movement phase validation
        game.phase = "Movement"
        move_order = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_for_current_phase(move_order) == True
        
        # Test retreat phase validation
        game.phase = "Retreat"
        retreat_order = RetreatOrder(
            power='FRANCE',
            unit=army_paris,
            retreat_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_for_current_phase(retreat_order) == True
        assert game._is_valid_for_current_phase(move_order) == False  # Move not valid in retreat phase

    def test_power_ownership_validation(self):
        """Test power ownership validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_munich = Unit(unit_type='A', province='MUN', power='GERMANY')
        
        game.game_state.powers['FRANCE'].units.append(army_paris)
        game.game_state.powers['GERMANY'].units.append(army_munich)
        
        # Valid order: French power ordering French unit
        valid_order = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_power_ownership(valid_order) == True
        
        # Invalid order: French power ordering German unit
        invalid_order = MoveOrder(
            power='FRANCE',
            unit=army_munich,  # German unit
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        assert game._is_valid_power_ownership(invalid_order) == False

    def test_comprehensive_order_validation(self):
        """Test comprehensive order validation."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # Valid order
        valid_order = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        is_valid, error_msg = game._validate_order_comprehensive(valid_order)
        assert is_valid == True
        assert error_msg == ""
        
        # Invalid order: Non-adjacent target
        invalid_order = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='MOS',  # Not adjacent
            status=OrderStatus.PENDING
        )
        
        is_valid, error_msg = game._validate_order_comprehensive(invalid_order)
        assert is_valid == False
        assert "invalid move" in error_msg.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
