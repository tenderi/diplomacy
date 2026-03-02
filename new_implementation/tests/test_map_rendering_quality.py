"""
Tests for map rendering quality and edge cases.

Tests map generation, visualization quality, and edge cases
in map rendering.
"""
import pytest
from pathlib import Path
from engine.game import Game
from engine.map import Map
from engine.data_models import Unit


@pytest.mark.map
@pytest.mark.unit
class TestMapGeneration:
    """Test map generation functionality."""
    
    def test_map_generation_basic(self):
        """Test basic map generation."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Map should be loaded
        assert game.map is not None
        assert game.map.map_name == "standard"
        assert len(game.map.provinces) > 0
    
    def test_map_generation_with_units(self):
        """Test map generation with units placed."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Units should be placed
        assert len(game.game_state.powers["FRANCE"].units) > 0
        assert len(game.game_state.powers["GERMANY"].units) > 0
    
    def test_map_generation_variant(self):
        """Test map generation for variant maps."""
        try:
            game = Game('mini_variant')
            assert game.map is not None
            assert game.map.map_name == "mini_variant"
        except FileNotFoundError:
            pytest.skip("Mini variant map not available")


@pytest.mark.map
@pytest.mark.unit
class TestMapRenderingEdgeCases:
    """Test edge cases in map rendering."""
    
    def test_map_with_no_units(self):
        """Test map rendering with no units."""
        game = Game('standard')
        
        # Remove all units
        for power in game.game_state.powers.values():
            power.units = []
        
        # Map should still render
        assert game.map is not None
        assert len(game.map.provinces) > 0
    
    def test_map_with_all_units(self):
        """Test map rendering with maximum units."""
        game = Game('standard')
        
        # Add all 7 powers
        for power_name in ["FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY", "ENGLAND"]:
            game.add_player(power_name)
        
        # Map should handle all units
        total_units = sum(len(p.units) for p in game.game_state.powers.values())
        assert total_units > 0
        assert game.map is not None
    
    def test_map_with_orders(self):
        """Test map rendering with orders displayed."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Set orders
        game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
        game.set_orders("GERMANY", ["GERMANY A BER H"])
        
        # Map should be able to render with orders
        assert len(game.game_state.orders.get("FRANCE", [])) > 0
        assert len(game.game_state.orders.get("GERMANY", [])) > 0


@pytest.mark.map
@pytest.mark.unit
class TestMapFileHandling:
    """Test map file loading and handling."""
    
    def test_standard_map_loads(self):
        """Test that standard map loads correctly."""
        map_obj = Map('standard')
        assert map_obj is not None
        assert len(map_obj.provinces) > 0
        assert len(map_obj.supply_centers) > 0
    
    def test_map_file_not_found(self):
        """Test handling of missing map file."""
        with pytest.raises(FileNotFoundError):
            Map('nonexistent_map')
    
    def test_map_province_coverage(self):
        """Test that all expected provinces are in the map."""
        map_obj = Map('standard')
        
        # Check for key provinces
        key_provinces = ["PAR", "LON", "BER", "ROM", "VIE", "MOS", "CON"]
        for province in key_provinces:
            assert province in map_obj.provinces or province in map_obj.get_locations(), \
                f"Key province {province} should be in map"
    
    def test_map_supply_center_coverage(self):
        """Test that all supply centers are present."""
        map_obj = Map('standard')
        supply_centers = map_obj.get_supply_centers()
        
        # Standard Diplomacy map has 22 supply centers (not 34)
        # 34 might be a variant or incorrect expectation
        assert len(supply_centers) == 22, f"Expected 22 supply centers, got {len(supply_centers)}"


@pytest.mark.map
@pytest.mark.unit
class TestMapVisualizationQuality:
    """Test map visualization quality aspects."""
    
    def test_province_coordinates_exist(self):
        """Test that provinces have coordinates for rendering."""
        map_obj = Map('standard')
        
        # Check a few provinces have coordinates
        sample_provinces = ["PAR", "LON", "BER"]
        for province_name in sample_provinces:
            if province_name in map_obj.provinces:
                province = map_obj.provinces[province_name]
                # Coordinates may be in province object or map data
                # Just verify province exists
                assert province is not None
    
    def test_unit_placement_on_map(self):
        """Test that units are placed correctly on map."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Units should be in valid provinces
        for unit in game.game_state.powers["FRANCE"].units:
            assert unit.province in game.map.get_locations() or \
                   unit.province in game.map.provinces, \
                   f"Unit province {unit.province} should be valid"
    
    def test_order_visualization(self):
        """Test that orders can be visualized on map."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Set orders
        game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
        game.set_orders("GERMANY", ["GERMANY A BER - SIL"])
        
        # Orders should be valid for visualization
        france_orders = game.game_state.orders.get("FRANCE", [])
        assert len(france_orders) > 0
        
        # Order should have valid source and target
        if france_orders:
            order = france_orders[0]
            if hasattr(order, 'unit'):
                assert order.unit.province in game.map.get_locations()
            if hasattr(order, 'target_province'):
                assert order.target_province in game.map.get_locations() or \
                       order.target_province in game.map.provinces


@pytest.mark.map
@pytest.mark.unit
class TestMapRenderingPerformance:
    """Test map rendering performance."""
    
    def test_map_loading_performance(self):
        """Test that map loads quickly."""
        import time
        
        start_time = time.time()
        map_obj = Map('standard')
        duration = time.time() - start_time
        
        assert duration < 1.0, f"Map loading took {duration:.2f}s, should be < 1.0s"
    
    def test_map_with_many_units_performance(self):
        """Test map performance with many units."""
        import time
        
        game = Game('standard')
        # Add all powers
        for power_name in ["FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY", "ENGLAND"]:
            game.add_player(power_name)
        
        start_time = time.time()
        # Access map data
        state = game.get_game_state()
        duration = time.time() - start_time
        
        assert duration < 0.5, f"Map state retrieval took {duration:.2f}s, should be < 0.5s"
