#!/usr/bin/env python3
"""
Test enhanced order resolution with conflicts, supports, and convoys.
"""

import pytest
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.engine.game import Game
from src.engine.data_models import Unit, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, OrderStatus


class TestOrderResolution:
    """Test enhanced order resolution functionality."""

    def test_simple_move_conflict(self):
        """Test resolution of simple move conflicts."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        # Set up conflicting moves
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_munich = Unit(unit_type='A', province='MUN', power='GERMANY')
        
        game.game_state.powers['FRANCE'].units.append(army_paris)
        game.game_state.powers['GERMANY'].units.append(army_munich)
        
        # Both armies try to move to Burgundy
        move_france = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        move_germany = MoveOrder(
            power='GERMANY',
            unit=army_munich,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        game.game_state.orders['FRANCE'] = [move_france]
        game.game_state.orders['GERMANY'] = [move_germany]
        
        # Process the movement phase
        results = game._process_movement_phase()
        
        # Should have a conflict
        assert len(results["conflicts"]) == 1
        assert results["conflicts"][0]["target"] == "BUR"
        assert results["conflicts"][0]["winner"] is None  # Tie results in bounce
        
        # Both units should bounce (no dislodgement)
        assert len(results["dislodged_units"]) == 0
        
        # Both moves should have failed due to bounce
        burgundy_moves = [m for m in results["moves"] if m["to"] == "BUR"]
        assert len(burgundy_moves) == 2
        for move in burgundy_moves:
            assert move["success"] == False
            assert move["failure_reason"] == "bounced"

    def test_supported_move(self):
        """Test resolution of supported moves."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        
        # Set up units
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_marseille = Unit(unit_type='A', province='MAR', power='FRANCE')
        army_munich = Unit(unit_type='A', province='MUN', power='GERMANY')
        
        game.game_state.powers['FRANCE'].units.extend([army_paris, army_marseille])
        game.game_state.powers['GERMANY'].units.append(army_munich)
        
        # French army moves to Burgundy with support
        move_france = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        support_france = SupportOrder(
            power='FRANCE',
            unit=army_marseille,
            supported_unit=army_paris,
            supported_action='-',
            supported_target='BUR',
            status=OrderStatus.PENDING
        )
        
        # German army also tries to move to Burgundy
        move_germany = MoveOrder(
            power='GERMANY',
            unit=army_munich,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        game.game_state.orders['FRANCE'] = [move_france, support_france]
        game.game_state.orders['GERMANY'] = [move_germany]
        
        # Process the movement phase
        results = game._process_movement_phase()
        
        # French move should win due to support (strength 2 vs 1)
        successful_moves = [m for m in results["moves"] if m["success"] == True]
        assert len(successful_moves) == 1
        assert successful_moves[0]["unit"] == "A PAR"
        assert successful_moves[0]["to"] == "BUR"
        assert successful_moves[0]["strength"] == 2
        
        # German move should fail
        failed_moves = [m for m in results["moves"] if m["success"] == False]
        assert len(failed_moves) == 1
        assert failed_moves[0]["unit"] == "A MUN"
        assert failed_moves[0]["to"] == "BUR"
        
        # German unit should be dislodged
        assert len(results["dislodged_units"]) == 1
        assert results["dislodged_units"][0]["unit"] == "A MUN"

    def test_convoy_move(self):
        """Test convoy moves."""
        game = Game('standard')
        game.add_player('ENGLAND')
        game.add_player('FRANCE')
        
        # Set up units
        army_london = Unit(unit_type='A', province='LON', power='ENGLAND')
        fleet_english_channel = Unit(unit_type='F', province='ENG', power='ENGLAND')
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        
        game.game_state.powers['ENGLAND'].units.extend([army_london, fleet_english_channel])
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # English army convoyed to Belgium
        move_england = MoveOrder(
            power='ENGLAND',
            unit=army_london,
            target_province='BEL',
            is_convoyed=True,
            status=OrderStatus.PENDING
        )
        
        convoy_england = ConvoyOrder(
            power='ENGLAND',
            unit=fleet_english_channel,
            convoyed_unit=army_london,
            convoyed_target='BEL',
            status=OrderStatus.PENDING
        )
        
        game.game_state.orders['ENGLAND'] = [move_england, convoy_england]
        game.game_state.orders['FRANCE'] = []  # No French orders
        
        # Process the movement phase
        results = game._process_movement_phase()
        
        # English convoy should succeed
        assert len(results["moves"]) == 1
        assert results["moves"][0]["unit"] == "A LON"
        assert results["moves"][0]["success"] == True
        assert results["moves"][0]["to"] == "BEL"

    def test_support_cut_by_dislodgement(self):
        """Test that support is cut when supporting unit is attacked, causing a bounce."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('GERMANY')
        game.add_player('ITALY')
        
        # Set up units
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        army_marseille = Unit(unit_type='A', province='MAR', power='FRANCE')
        army_munich = Unit(unit_type='A', province='MUN', power='GERMANY')
        army_rome = Unit(unit_type='A', province='ROM', power='ITALY')
        
        game.game_state.powers['FRANCE'].units.extend([army_paris, army_marseille])
        game.game_state.powers['GERMANY'].units.append(army_munich)
        game.game_state.powers['ITALY'].units.append(army_rome)
        
        # French army moves to Burgundy with support from Marseille
        move_france = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        support_france = SupportOrder(
            power='FRANCE',
            unit=army_marseille,
            supported_unit=army_paris,
            supported_action='-',
            supported_target='BUR',
            status=OrderStatus.PENDING
        )
        
        # German army moves to Burgundy
        move_germany = MoveOrder(
            power='GERMANY',
            unit=army_munich,
            target_province='BUR',
            status=OrderStatus.PENDING
        )
        
        # Italian army attacks Marseille (cutting support)
        move_italy = MoveOrder(
            power='ITALY',
            unit=army_rome,
            target_province='MAR',
            status=OrderStatus.PENDING
        )
        
        game.game_state.orders['FRANCE'] = [move_france, support_france]
        game.game_state.orders['GERMANY'] = [move_germany]
        game.game_state.orders['ITALY'] = [move_italy]
        
        # Process the movement phase
        results = game._process_movement_phase()
        
        # Italian move to Marseille should succeed (cutting support)
        marseille_moves = [m for m in results["moves"] if m["to"] == "MAR"]
        assert len(marseille_moves) == 1
        assert marseille_moves[0]["unit"] == "A ROM"
        
        # German move to Burgundy should succeed (French support was cut)
        burgundy_moves = [m for m in results["moves"] if m["to"] == "BUR"]
        assert len(burgundy_moves) == 2  # Both armies bounced
        # Both moves should have failed due to bounce
        for move in burgundy_moves:
            assert move["success"] == False
            assert move["failure_reason"] == "bounced"
        
        # French army should not be dislodged (bounced instead)
        french_dislodged = [d for d in results["dislodged_units"] if d["unit"] == "A PAR"]
        assert len(french_dislodged) == 0

    def test_hold_order_processing(self):
        """Test that hold orders are processed correctly."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Set up unit
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units.append(army_paris)
        
        # Hold order
        hold_order = HoldOrder(
            power='FRANCE',
            unit=army_paris,
            status=OrderStatus.PENDING
        )
        
        game.game_state.orders['FRANCE'] = [hold_order]
        
        # Process the movement phase
        results = game._process_movement_phase()
        
        # Should have one hold result
        assert len(results["moves"]) == 1
        assert results["moves"][0]["unit"] == "A PAR"
        assert results["moves"][0]["from"] == "PAR"
        assert results["moves"][0]["to"] == "PAR"
        assert results["moves"][0]["success"] == True
        assert results["moves"][0]["action"] == "hold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
