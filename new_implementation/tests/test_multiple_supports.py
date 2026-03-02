"""
Tests for multiple simultaneous support scenarios.

Tests cases where units receive support from multiple units,
and complex support interactions.
"""
import pytest
from engine.game import Game
from engine.data_models import Unit


@pytest.mark.unit
class TestMultipleSupports:
    """Test multiple simultaneous support scenarios."""
    
    def test_unit_receives_multiple_supports(self):
        """Test that a unit can receive support from multiple units."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France: A PAR attacks BUR with support from MAR and PIC
        # Germany: A BUR defends
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='PIC', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",  # Attack
            "FRANCE A MAR S A PAR - BUR",  # Support 1
            "FRANCE A PIC S A PAR - BUR"   # Support 2
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H"  # Defend
        ])
        
        game.process_turn()
        
        # Attack with strength 3 (1 base + 2 supports) should beat defense with strength 1
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["FRANCE"].units), \
            "Supported attack (strength 3) should succeed"
        assert not any(unit.province == 'BUR' for unit in game.game_state.powers["GERMANY"].units), \
            "Defender should be dislodged"
    
    def test_multiple_supports_with_one_cut(self):
        """Test that if one support is cut, others still count."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        game.add_player("ITALY")
        
        # France: A PAR attacks BUR with support from MAR and PIC
        # Germany: A BUR defends, A GAS attacks and cuts support from MAR
        # Italy: A PIE supports Germany's attack on MAR
        # GAS is adjacent to MAR, and PIE is adjacent to MAR
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='PIC', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='GAS', power='GERMANY')  # GAS is adjacent to MAR
        ]
        game.game_state.powers["ITALY"].units = [
            Unit(unit_type='A', province='PIE', power='ITALY')  # PIE is adjacent to MAR
        ]
        
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR",  # Support (will be cut)
            "FRANCE A PIC S A PAR - BUR"   # Support (not cut)
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H",  # Defend
            "GERMANY A GAS - MAR"  # Cut support (GAS is adjacent to MAR)
        ])
        game.set_orders("ITALY", [
            "ITALY A PIE S A GAS - MAR"  # Support the cut (PIE is adjacent to MAR)
        ])
        
        game.process_turn()
        
        # Attack with strength 2 (1 base + 1 support, 1 cut) vs defense 1
        # Should succeed
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["FRANCE"].units), \
            "Attack with one support cut should still succeed (strength 2 vs 1)"
        assert not any(unit.province == 'MAR' for unit in game.game_state.powers["FRANCE"].units), \
            "Supporting unit should be dislodged"
    
    def test_multiple_supports_all_cut(self):
        """Test that if all supports are cut, attack fails."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France: A PAR attacks BUR with support from MAR and PIC
        # Germany: A BUR defends, cuts both supports
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='PIC', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='GAS', power='GERMANY'),  # GAS is adjacent to MAR
            Unit(unit_type='A', province='BEL', power='GERMANY')
        ]
        
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR",  # Support 1
            "FRANCE A PIC S A PAR - BUR"   # Support 2
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H",  # Defend
            "GERMANY A GAS - MAR",  # Cut support 1 (GAS is adjacent to MAR)
            "GERMANY A BEL - PIC"   # Cut support 2 (BEL is adjacent to PIC)
        ])
        
        game.process_turn()
        
        # Attack with strength 1 (all supports cut) vs defense 1 = standoff
        assert any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units), \
            "Attack with all supports cut should fail (standoff)"
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["GERMANY"].units), \
            "Defender should hold"
    
    def test_support_chain(self):
        """Test a chain of supports: A supports B, B supports C."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France: A PAR supports A MAR, A MAR supports A PIC
        # A PIC attacks BUR
        # This tests that supports can chain (though in practice, supports are direct)
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='PIC', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # Note: Supports are direct, not chained
        # A PAR supports A PIC directly, A MAR supports A PIC directly
        game.set_orders("FRANCE", [
            "FRANCE A PAR S A PIC - BUR",  # Support PIC
            "FRANCE A MAR S A PIC - BUR",  # Support PIC
            "FRANCE A PIC - BUR"           # Attack
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H"  # Defend
        ])
        
        game.process_turn()
        
        # Attack with strength 3 (1 base + 2 supports) should succeed
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["FRANCE"].units), \
            "Supported attack should succeed"


@pytest.mark.unit
class TestComplexSupportScenarios:
    """Test complex support interaction scenarios."""
    
    def test_support_vs_support_standoff(self):
        """Test that supported attacks of equal strength result in standoff."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Both sides: attack BUR with one support (PAR and MAR adjacent to BUR; MUN adjacent to BUR)
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY'),
            Unit(unit_type='A', province='MUN', power='GERMANY')
        ]
        
        # France attacks BUR with support from MAR (both PAR and MAR adjacent to BUR)
        # Germany holds BUR with support from MUN (MUN adjacent to BUR) -> 2 vs 2 standoff
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR"
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H",
            "GERMANY A MUN S A BUR"
        ])
        
        game.process_turn()
        
        # Both attacks should bounce (standoff)
        assert any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units), \
            "French unit should bounce"
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["GERMANY"].units), \
            "German unit should bounce"
    
    def test_support_against_holding_unit(self):
        """Test supporting an attack against a holding unit."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France attacks with support, Germany holds
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR"
        ])
        game.set_orders("GERMANY", [
            "GERMANY A BUR H"  # Hold
        ])
        
        game.process_turn()
        
        # Supported attack (strength 2) should beat hold (strength 1)
        assert any(unit.province == 'BUR' for unit in game.game_state.powers["FRANCE"].units), \
            "Supported attack should dislodge holding unit"
    
    def test_support_cut_by_move(self):
        """Test that when a unit has both support and move orders, support is cut (engine allows both; support is cut during adjudication)."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # France: A PAR attacks BUR, A MAR supports but also has move order (support is cut)
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BUR', power='GERMANY')
        ]
        
        # Engine allows support+move for same unit (support is cut during processing)
        game.set_orders("FRANCE", [
            "FRANCE A PAR - BUR",
            "FRANCE A MAR S A PAR - BUR",
            "FRANCE A MAR - PIE"
        ])
        game.set_orders("GERMANY", ["GERMANY A BUR H"])
        game.process_turn()
        # Without MAR's support, PAR's attack on BUR is 1 vs 1 -> standoff; MAR moves to PIE
        assert any(u.province == "PIE" for u in game.game_state.powers["FRANCE"].units)
        assert any(u.province == "BUR" for u in game.game_state.powers["GERMANY"].units)
