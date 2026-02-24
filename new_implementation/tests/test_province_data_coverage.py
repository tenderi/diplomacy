"""
Test province data coverage and validation.

Ensures:
1. All provinces in map have complete adjacency data
2. All provinces in mapping exist in map
3. No illegal moves can be executed
4. Province name normalization works correctly
"""

import pytest
from engine.map import Map
from engine.province_mapping import PROVINCE_MAPPING, normalize_province_name
from engine.data_models import GameState, MapData, Province, Unit, MoveOrder
from engine.game import Game


class TestProvinceDataCoverage:
    """Test that all province data is complete and consistent."""
    
    def test_all_map_provinces_have_adjacencies(self):
        """Verify every province in the map has at least one adjacency."""
        map_instance = Map('standard')
        provinces_without_adj = []
        
        for name, province in map_instance.provinces.items():
            if len(province.adjacent) == 0:
                provinces_without_adj.append(name)
        
        assert len(provinces_without_adj) == 0, \
            f"Provinces without adjacencies: {provinces_without_adj}"
    
    def test_province_mapping_matches_map(self):
        """Verify all provinces in mapping exist in map and vice versa."""
        map_instance = Map('standard')
        mapping_provinces = set(PROVINCE_MAPPING.keys())
        map_provinces = set(map_instance.provinces.keys())
        
        missing_in_map = mapping_provinces - map_provinces
        missing_in_mapping = map_provinces - mapping_provinces
        
        assert len(missing_in_map) == 0, \
            f"Provinces in mapping but not in map: {missing_in_map}"
        assert len(missing_in_mapping) == 0, \
            f"Provinces in map but not in mapping: {missing_in_mapping}"
    
    def test_province_name_normalization(self):
        """Test that province name normalization works correctly."""
        # Test canonical names
        assert normalize_province_name("LYO") == "LYO"
        assert normalize_province_name("ROM") == "ROM"
        assert normalize_province_name("MAR") == "MAR"
        
        # Test alternative names map correctly
        assert normalize_province_name("gol") == "LYO"  # GOL should map to LYO
        assert normalize_province_name("lyo") == "LYO"
        assert normalize_province_name("mars") == "MAR"
    
    def test_rom_not_adjacent_to_mar(self):
        """Verify ROM and MAR are correctly not adjacent (standard Diplomacy)."""
        map_instance = Map('standard')
        rom = map_instance.provinces.get('ROM')
        mar = map_instance.provinces.get('MAR')
        
        assert rom is not None, "ROM province not found"
        assert mar is not None, "MAR province not found"
        assert 'MAR' not in rom.adjacent, \
            "ROM should NOT be adjacent to MAR in standard Diplomacy (they are separated by the Alps)"
    
    def test_lyo_exists_in_map(self):
        """Verify LYO (Gulf of Lyon) exists in map."""
        map_instance = Map('standard')
        lyo = map_instance.provinces.get('LYO')
        
        assert lyo is not None, "LYO province not found in map"
        assert lyo.type == 'sea', "LYO should be a sea province"


class TestIllegalMovePrevention:
    """Test that illegal moves are properly rejected."""
    
    def test_non_adjacent_move_rejected(self):
        """Verify that moves to non-adjacent provinces are rejected."""
        game = Game('standard')
        game.add_player('FRANCE')
        
        # Get a unit
        france_units = game.game_state.powers['FRANCE'].units
        if not france_units:
            pytest.skip("No French units available")
        
        unit = france_units[0]
        current_province = unit.province
        
        # Find a province that is NOT adjacent
        map_instance = game.map
        current_prov_obj = map_instance.provinces.get(current_province)
        
        if not current_prov_obj:
            pytest.skip(f"Province {current_province} not found in map")
        
        # Find a non-adjacent province
        all_provinces = set(map_instance.provinces.keys())
        adjacent_provinces = set(current_prov_obj.adjacent)
        non_adjacent = all_provinces - adjacent_provinces - {current_province}
        
        if not non_adjacent:
            pytest.skip(f"All provinces are adjacent to {current_province}")
        
        non_adjacent_province = list(non_adjacent)[0]
        
        # Try to create a move order to non-adjacent province
        move_order = MoveOrder(
            power='FRANCE',
            unit=unit,
            target_province=non_adjacent_province,
            is_convoyed=False
        )
        
        # Validate should fail
        valid, reason = move_order.validate(game.game_state)
        assert not valid, \
            f"Move from {current_province} to {non_adjacent_province} should be rejected: {reason}"
        assert "non-adjacent" in reason.lower() or "cannot move" in reason.lower(), \
            f"Error message should mention non-adjacent: {reason}"
    
    def test_illegal_move_rejected_in_processing(self):
        """Verify that even if validation passes, illegal moves are rejected during processing."""
        game = Game('standard')
        game.add_player('FRANCE')
        game.add_player('ITALY')
        
        # Create units in non-adjacent provinces
        army_paris = Unit(unit_type='A', province='PAR', power='FRANCE')
        game.game_state.powers['FRANCE'].units = [army_paris]
        
        # Try to move to a non-adjacent province (PAR to ROM is not adjacent)
        # PAR is adjacent to: BUR, BRE, GAS, PIC
        # ROM is not in that list
        move_order = MoveOrder(
            power='FRANCE',
            unit=army_paris,
            target_province='ROM',  # Not adjacent to PAR
            is_convoyed=False
        )
        
        game.game_state.orders['FRANCE'] = [move_order]
        
        # Process movement phase - should reject the move
        results = game._process_movement_phase()
        
        # The move should not appear in successful moves
        successful_moves = [m for m in results["moves"] if m.get("success") and m.get("to") == "ROM"]
        assert len(successful_moves) == 0, \
            "Illegal move to non-adjacent province should be rejected"
        
        # Check that a warning was logged (move was rejected)
        # The move should either not appear, or appear as failed
        all_rom_moves = [m for m in results["moves"] if m.get("to") == "ROM"]
        assert len(all_rom_moves) == 0, \
            "Illegal move should not appear in results at all"
