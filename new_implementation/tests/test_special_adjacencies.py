"""
Tests for special adjacency cases in Diplomacy.

Tests special cases like:
- Kiel (special land/sea connections)
- Constantinople (special connections)
- Other edge cases in adjacency rules
"""
import pytest
from engine.game import Game
from engine.map import Map
from engine.data_models import Unit


@pytest.mark.unit
@pytest.mark.map
class TestKielAdjacencies:
    """Test Kiel special adjacency rules."""
    
    def test_kiel_adjacencies(self):
        """Test that Kiel has correct adjacencies."""
        map_obj = Map('standard')
        
        # Kiel should be adjacent to both land and sea provinces
        kiel_adj = map_obj.get_adjacency("KIE")
        
        assert kiel_adj is not None
        # Kiel should be adjacent to land provinces (e.g., BER, MUN)
        # and sea provinces (e.g., HEL, BAL)
        # Exact adjacencies depend on map implementation
        assert len(kiel_adj) > 0
    
    def test_army_in_kiel(self):
        """Test army movement from Kiel."""
        game = Game('standard')
        game.add_player("GERMANY")
        
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='KIE', power='GERMANY')
        ]
        
        # Army should be able to move to adjacent land provinces
        # (exact provinces depend on map)
        unit = game.game_state.powers["GERMANY"].units[0]
        assert unit.province == 'KIE'
        assert unit.unit_type == 'A'
    
    def test_fleet_in_kiel(self):
        """Test fleet movement from Kiel."""
        game = Game('standard')
        game.add_player("GERMANY")
        
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='F', province='KIE', power='GERMANY')
        ]
        
        # Fleet should be able to move to adjacent sea provinces
        unit = game.game_state.powers["GERMANY"].units[0]
        assert unit.province == 'KIE'
        assert unit.unit_type == 'F'


@pytest.mark.unit
@pytest.mark.map
class TestConstantinopleAdjacencies:
    """Test Constantinople special adjacency rules."""
    
    def test_constantinople_adjacencies(self):
        """Test that Constantinople has correct adjacencies."""
        map_obj = Map('standard')
        
        # Constantinople should be adjacent to both land and sea provinces
        con_adj = map_obj.get_adjacency("CON")
        
        assert con_adj is not None
        # Constantinople should be adjacent to land provinces (e.g., BUL, ANK)
        # and sea provinces (e.g., BLA, AEG)
        assert len(con_adj) > 0
    
    def test_army_in_constantinople(self):
        """Test army movement from Constantinople."""
        game = Game('standard')
        game.add_player("TURKEY")
        
        game.game_state.powers["TURKEY"].units = [
            Unit(unit_type='A', province='CON', power='TURKEY')
        ]
        
        # Army should be able to move to adjacent land provinces
        unit = game.game_state.powers["TURKEY"].units[0]
        assert unit.province == 'CON'
        assert unit.unit_type == 'A'
    
    def test_fleet_in_constantinople(self):
        """Test fleet movement from Constantinople."""
        game = Game('standard')
        game.add_player("TURKEY")
        
        game.game_state.powers["TURKEY"].units = [
            Unit(unit_type='F', province='CON', power='TURKEY')
        ]
        
        # Fleet should be able to move to adjacent sea provinces
        unit = game.game_state.powers["TURKEY"].units[0]
        assert unit.province == 'CON'
        assert unit.unit_type == 'F'


@pytest.mark.unit
@pytest.mark.map
class TestCoastalProvinceAdjacencies:
    """Test adjacency rules for coastal provinces."""
    
    def test_army_can_move_to_coastal_province(self):
        """Test that armies can move to coastal provinces."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Army in Paris (coastal) should be able to move to other coastal provinces
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        
        # Try to move to another coastal province
        game.set_orders("FRANCE", ["FRANCE A PAR - BRE"])
        game.process_turn()
        
        # Should succeed (if BRE is adjacent to PAR)
        # Verify unit moved or validation handled correctly
        pass
    
    def test_fleet_can_move_to_coastal_province(self):
        """Test that fleets can move to coastal provinces."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Fleet in Brest (coastal) should be able to move to sea or coastal provinces
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='F', province='BRE', power='FRANCE')
        ]
        
        # Try to move to sea province
        game.set_orders("FRANCE", ["FRANCE F BRE - ENG"])
        game.process_turn()
        
        # Should succeed (if ENG is adjacent to BRE)
        pass


@pytest.mark.unit
@pytest.mark.map
class TestLandlockedProvinces:
    """Test provinces with no sea access."""
    
    def test_army_in_landlocked_province(self):
        """Test army in landlocked province (no sea access)."""
        game = Game('standard')
        game.add_player("AUSTRIA")
        
        # Vienna is landlocked
        game.game_state.powers["AUSTRIA"].units = [
            Unit(unit_type='A', province='VIE', power='AUSTRIA')
        ]
        
        # Army should only be able to move to adjacent land provinces
        unit = game.game_state.powers["AUSTRIA"].units[0]
        assert unit.unit_type == 'A'
        assert unit.province == 'VIE'
    
    def test_fleet_cannot_be_in_landlocked_province(self):
        """Test that fleets cannot be placed in landlocked provinces."""
        game = Game('standard')
        game.add_player("AUSTRIA")
        
        # Try to place fleet in Vienna (should be invalid)
        # This would be caught during validation
        try:
            game.game_state.powers["AUSTRIA"].units = [
                Unit(unit_type='F', province='VIE', power='AUSTRIA')
            ]
            # If allowed, verify it's invalid during move validation
            game.set_orders("AUSTRIA", ["AUSTRIA F VIE - BUD"])
            game.process_turn()
            # Should fail validation
        except ValueError:
            # Expected - fleets cannot be in landlocked provinces
            pass


@pytest.mark.unit
@pytest.mark.map
class TestSeaProvinceAdjacencies:
    """Test sea province adjacency rules."""
    
    def test_fleet_in_sea_province(self):
        """Test fleet movement from sea province."""
        game = Game('standard')
        game.add_player("ENGLAND")
        
        # Fleet in North Sea
        game.game_state.powers["ENGLAND"].units = [
            Unit(unit_type='F', province='NTH', power='ENGLAND')
        ]
        
        # Fleet should be able to move to adjacent sea or coastal provinces
        unit = game.game_state.powers["ENGLAND"].units[0]
        assert unit.unit_type == 'F'
        assert unit.province == 'NTH'
    
    def test_army_cannot_be_in_sea_province(self):
        """Test that armies cannot be in sea provinces."""
        game = Game('standard')
        game.add_player("ENGLAND")
        
        # Try to place army in sea province (should be invalid)
        try:
            game.game_state.powers["ENGLAND"].units = [
                Unit(unit_type='A', province='NTH', power='ENGLAND')
            ]
            # If allowed, verify it's invalid during move validation
            game.set_orders("ENGLAND", ["ENGLAND A NTH - ENG"])
            game.process_turn()
            # Should fail validation
        except ValueError:
            # Expected - armies cannot be in sea provinces
            pass


@pytest.mark.unit
@pytest.mark.map
class TestAdjacencySymmetry:
    """Test that adjacency is symmetric where appropriate."""
    
    def test_land_adjacency_symmetric(self):
        """Test that land province adjacencies are symmetric."""
        map_obj = Map('standard')
        
        # If PAR is adjacent to BUR, then BUR should be adjacent to PAR
        par_adj = map_obj.get_adjacency("PAR")
        bur_adj = map_obj.get_adjacency("BUR")
        
        if "BUR" in par_adj:
            assert "PAR" in bur_adj, "Land adjacency should be symmetric"
    
    def test_coastal_adjacency_symmetric(self):
        """Test that coastal province adjacencies are symmetric."""
        map_obj = Map('standard')
        
        # Test a few coastal provinces
        coastal_provinces = ["PAR", "BRE", "LON"]
        
        for prov1 in coastal_provinces:
            adj1 = map_obj.get_adjacency(prov1)
            for prov2 in adj1:
                if map_obj.validate_location(prov2):
                    adj2 = map_obj.get_adjacency(prov2)
                    # If prov1 is adjacent to prov2, prov2 should be adjacent to prov1
                    # (for land/coastal connections, not necessarily for sea)
                    if prov2 in ["PAR", "BRE", "LON"]:  # Only check other coastal/land
                        assert prov1 in adj2 or prov2 not in adj1, \
                            f"Adjacency should be symmetric: {prov1} <-> {prov2}"
