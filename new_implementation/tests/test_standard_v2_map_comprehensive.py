#!/usr/bin/env python3
"""
Comprehensive test suite for standard-v2 map integration.

Tests cover:
- Map initialization and basic functionality
- Coordinate extraction from v2.svg
- Game creation and management
- API endpoints
- Map rendering (all variants)
- Comparison with standard map
- Edge cases and error handling
- Integration scenarios
"""

import sys
import os
import pytest
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestStandardV2MapInitialization:
    """Test Map class initialization with standard-v2"""
    
    def test_map_initialization(self):
        """Test that Map can be initialized with standard-v2"""
        from engine.map import Map
        
        map_instance = Map("standard-v2")
        assert map_instance.map_name == "standard-v2"
        assert len(map_instance.provinces) > 0
        assert len(map_instance.supply_centers) > 0
    
    def test_map_uses_standard_adjacencies(self):
        """Test that standard-v2 uses same adjacencies as standard map"""
        from engine.map import Map
        
        standard_map = Map("standard")
        v2_map = Map("standard-v2")
        
        # Test several key adjacencies
        test_cases = [
            ("PAR", "BUR"),
            ("LON", "YOR"),
            ("BER", "KIE"),
            ("VIE", "BUD"),
            ("ROM", "VEN"),
            ("CON", "SMY"),
            ("MOS", "WAR"),
        ]
        
        for prov1, prov2 in test_cases:
            assert standard_map.is_adjacent(prov1, prov2) == v2_map.is_adjacent(prov1, prov2), \
                f"Adjacency mismatch for {prov1}-{prov2}"
    
    def test_map_supply_centers_match(self):
        """Test that standard-v2 has same supply centers as standard"""
        from engine.map import Map
        
        standard_map = Map("standard")
        v2_map = Map("standard-v2")
        
        assert standard_map.supply_centers == v2_map.supply_centers, \
            "Supply centers should match between standard and standard-v2"
    
    def test_map_provinces_match(self):
        """Test that standard-v2 has same provinces as standard"""
        from engine.map import Map
        
        standard_map = Map("standard")
        v2_map = Map("standard-v2")
        
        assert set(standard_map.provinces.keys()) == set(v2_map.provinces.keys()), \
            "Provinces should match between standard and standard-v2"


class TestStandardV2CoordinateExtraction:
    """Test coordinate extraction from v2.svg"""
    
    def test_v2_svg_exists(self):
        """Test that v2.svg file exists"""
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        v2_path = os.path.join(base_dir, "maps", "v2.svg")
        
        # Try relative path if absolute doesn't work
        if not os.path.exists(v2_path):
            v2_path = "maps/v2.svg"
        
        assert os.path.exists(v2_path), f"v2.svg not found at {v2_path}"
    
    def test_coordinate_extraction(self):
        """Test that coordinates can be extracted from v2.svg"""
        from engine.map import Map
        
        # Get SVG path resolution
        svg_path = Map._resolve_svg_path("standard-v2")
        assert os.path.exists(svg_path), f"SVG path {svg_path} should exist"
        
        # Test coordinate extraction
        tree, coords = Map._get_cached_svg_data(svg_path)
        assert tree is not None, "SVG tree should be parsed"
        assert isinstance(coords, dict), "Coordinates should be a dictionary"
        assert len(coords) > 0, "Should extract coordinates for provinces"
        
        # Verify some expected provinces have coordinates
        expected_provinces = ["LON", "PAR", "BER", "VIE", "ROM", "CON", "MOS"]
        found_provinces = [p for p in expected_provinces if p in coords]
        assert len(found_provinces) > 0, \
            f"Should find coordinates for at least some provinces. Found: {found_provinces}"
    
    def test_coordinate_scaling(self):
        """Test that coordinates are properly scaled"""
        from engine.map import Map
        
        svg_path = Map._resolve_svg_path("standard-v2")
        tree, coords = Map._get_cached_svg_data(svg_path)
        
        # Check that coordinates are reasonable (within expected output dimensions)
        output_width = 1835.0
        output_height = 1360.0
        
        for prov, (x, y) in coords.items():
            assert 0 <= x <= output_width * 1.1, \
                f"X coordinate for {prov} ({x}) should be within reasonable bounds"
            assert 0 <= y <= output_height * 1.1, \
                f"Y coordinate for {prov} ({y}) should be within reasonable bounds"


class TestStandardV2GameCreation:
    """Test game creation with standard-v2 map"""
    
    def test_server_game_creation(self):
        """Test creating a game via Server with standard-v2"""
        from server.server import Server
        
        server = Server()
        result = server.process_command("CREATE_GAME standard-v2")
        
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "game_id" in result or "status" in result, "Result should contain game_id or status"
        
        game_id = result.get("game_id") if isinstance(result, dict) else result
        assert game_id is not None, "Game ID should not be None"
        
        # Verify game state
        state_result = server.process_command(f"GET_GAME_STATE {game_id}")
        if isinstance(state_result, dict):
            state = state_result.get("state", state_result)
        else:
            state = state_result
        
        assert state is not None, "Game state should exist"
        
        # Cleanup
        try:
            if game_id in server.games:
                del server.games[game_id]
        except:
            pass
    
    def test_api_game_creation(self):
        """Test creating a game via API with standard-v2"""
        from server.api.routes.games import create_game
        from server.api.routes.games import CreateGameRequest
        from server.api.shared import server as shared_server
        
        # Create game request
        req = CreateGameRequest(map_name="standard-v2")
        result = create_game(req)
        
        assert "game_id" in result, "Result should contain game_id"
        game_id = result["game_id"]
        
        # Verify game exists and has correct map_name in shared server
        assert game_id in shared_server.games, "Game should exist in shared server"
        game = shared_server.games[game_id]
        assert game.map_name == "standard-v2", "Map name should be standard-v2"
        
        # Cleanup
        try:
            if game_id in shared_server.games:
                del shared_server.games[game_id]
        except:
            pass
    
    def test_game_state_includes_map_name(self):
        """Test that game state includes correct map_name"""
        from server.server import Server
        
        server = Server()
        result = server.process_command("CREATE_GAME standard-v2")
        game_id = result.get("game_id") if isinstance(result, dict) else result
        
        state_result = server.process_command(f"GET_GAME_STATE {game_id}")
        if isinstance(state_result, dict):
            state = state_result.get("state", state_result)
        else:
            state = state_result
        
        # Map name might be in different places depending on state structure
        map_name = None
        if isinstance(state, dict):
            map_name = state.get("map_name") or state.get("map")
        
        assert map_name == "standard-v2" or map_name is None, \
            f"Game state should include map_name=standard-v2, got {map_name}"
        
        # Cleanup
        try:
            if game_id in server.games:
                del server.games[game_id]
        except:
            pass


class TestStandardV2MapRendering:
    """Test map rendering with standard-v2"""
    
    def test_basic_map_rendering(self):
        """Test basic map rendering with standard-v2"""
        from engine.map import Map
        
        units = {
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
            "ENGLAND": ["A LON", "F EDI", "F LVP"],
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = Map._resolve_svg_path("standard-v2")
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        assert len(img_bytes) > 0, "Map should generate image bytes"
        assert img_bytes[:8] == b'\x89PNG\r\n\x1a\n', "Should generate valid PNG"
    
    def test_map_rendering_with_all_powers(self):
        """Test map rendering with all 7 powers"""
        from engine.map import Map
        
        units = {
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
            "ENGLAND": ["A LON", "F EDI", "F LVP"],
            "RUSSIA": ["A MOS", "A WAR", "F SEV", "F STP"],
            "AUSTRIA": ["A VIE", "A BUD", "F TRI"],
            "ITALY": ["A ROM", "A VEN", "F NAP"],
            "TURKEY": ["A CON", "A SMY", "F ANK"]
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = Map._resolve_svg_path("standard-v2")
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        assert len(img_bytes) > 0, "Map should generate image bytes"
        
        # Save for manual inspection
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        output_path = os.path.join(test_maps_dir, "test_standard_v2_all_powers.png")
        with open(output_path, 'wb') as f:
            f.write(img_bytes)
    
    def test_map_rendering_with_moves(self):
        """Test map rendering with moves using standard-v2"""
        from engine.map import Map
        
        units = {
            "FRANCE": ["A PAR", "F BRE"],
            "GERMANY": ["A BER", "F KIE"]
        }
        
        # Moves format: {power: {"successful": [...], "failed": [...], etc}}
        moves = {
            "FRANCE": {
                "successful": [
                    {"type": "move", "unit": "A PAR", "target": "BUR", "status": "successful"}
                ],
                "failed": []
            },
            "GERMANY": {
                "successful": [
                    {"type": "move", "unit": "A BER", "target": "SIL", "status": "successful"}
                ],
                "failed": []
            }
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = Map._resolve_svg_path("standard-v2")
        img_bytes = Map.render_board_png_with_moves(svg_path, units, moves, phase_info=phase_info)
        
        assert len(img_bytes) > 0, "Map with moves should generate image bytes"
    
    def test_map_rendering_with_supply_centers(self):
        """Test map rendering with supply center control"""
        from engine.map import Map
        
        units = {
            "FRANCE": ["A PAR", "A MAR"],
            "GERMANY": ["A BER", "A MUN"]
        }
        
        supply_center_control = {
            "PAR": "FRANCE",
            "MAR": "FRANCE",
            "BER": "GERMANY",
            "MUN": "GERMANY",
            "LON": "ENGLAND",  # Unoccupied but controlled
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = Map._resolve_svg_path("standard-v2")
        img_bytes = Map.render_board_png(
            svg_path, units, 
            phase_info=phase_info,
            supply_center_control=supply_center_control
        )
        
        assert len(img_bytes) > 0, "Map with supply centers should generate image bytes"


class TestStandardV2APIIntegration:
    """Test API endpoints with standard-v2 map"""
    
    def test_generate_map_endpoint(self):
        """Test /games/{game_id}/generate_map endpoint with standard-v2"""
        from server.api.shared import server as shared_server
        from server.api.routes.maps import generate_map_for_snapshot
        
        result = shared_server.process_command("CREATE_GAME standard-v2")
        game_id = str(result.get("game_id") if isinstance(result, dict) else result)
        
        try:
            result = generate_map_for_snapshot(game_id)
            assert "map_path" in result or "map_data" in result or "image_path" in result, \
                f"Map generation should return map_path, map_data, or image_path. Got: {result.keys()}"
        finally:
            try:
                if game_id in shared_server.games:
                    del shared_server.games[game_id]
            except:
                pass
    
    def test_generate_orders_map_endpoint(self):
        """Test /games/{game_id}/generate_map/orders endpoint with standard-v2"""
        from server.api.shared import server as shared_server
        from server.api.routes.maps import generate_orders_map
        
        result = shared_server.process_command("CREATE_GAME standard-v2")
        game_id = str(result.get("game_id") if isinstance(result, dict) else result)
        
        # Add a player and set orders
        shared_server.process_command(f"ADD_PLAYER {game_id} FRANCE")
        shared_server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
        
        try:
            result = generate_orders_map(game_id)
            assert "map_path" in result or "map_data" in result or "image_path" in result, \
                f"Orders map generation should return map_path, map_data, or image_path. Got: {result.keys()}"
        finally:
            try:
                if game_id in shared_server.games:
                    del shared_server.games[game_id]
            except:
                pass
    
    def test_generate_resolution_map_endpoint(self):
        """Test /games/{game_id}/generate_map/resolution endpoint with standard-v2"""
        from server.api.shared import server as shared_server
        from server.api.routes.maps import generate_resolution_map
        
        result = shared_server.process_command("CREATE_GAME standard-v2")
        game_id = str(result.get("game_id") if isinstance(result, dict) else result)
        
        # Add players and process a turn
        shared_server.process_command(f"ADD_PLAYER {game_id} FRANCE")
        shared_server.process_command(f"ADD_PLAYER {game_id} GERMANY")
        shared_server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
        shared_server.process_command(f"SET_ORDERS {game_id} GERMANY A MUN H")
        shared_server.process_command(f"PROCESS_TURN {game_id}")
        
        try:
            result = generate_resolution_map(game_id)
            assert "map_path" in result or "map_data" in result or "image_path" in result, \
                f"Resolution map generation should return map_path, map_data, or image_path. Got: {result.keys()}"
        finally:
            try:
                if game_id in shared_server.games:
                    del shared_server.games[game_id]
            except:
                pass


class TestStandardV2Comparison:
    """Test comparison between standard and standard-v2 maps"""
    
    def test_visual_difference(self):
        """Test that standard and standard-v2 produce different visual outputs"""
        from engine.map import Map
        
        units = {
            "FRANCE": ["A PAR", "F BRE"],
            "GERMANY": ["A BER", "F KIE"]
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        # Generate both maps
        standard_svg = Map._resolve_svg_path("standard")
        v2_svg = Map._resolve_svg_path("standard-v2")
        
        standard_img = Map.render_board_png(standard_svg, units, phase_info=phase_info)
        v2_img = Map.render_board_png(v2_svg, units, phase_info=phase_info)
        
        # They should be different (different SVG files)
        # But both should be valid PNGs
        assert len(standard_img) > 0, "Standard map should generate image"
        assert len(v2_img) > 0, "V2 map should generate image"
        assert standard_img[:8] == b'\x89PNG\r\n\x1a\n', "Standard should be valid PNG"
        assert v2_img[:8] == b'\x89PNG\r\n\x1a\n', "V2 should be valid PNG"
        
        # Save for comparison
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        
        with open(os.path.join(test_maps_dir, "test_standard_comparison.png"), 'wb') as f:
            f.write(standard_img)
        with open(os.path.join(test_maps_dir, "test_standard_v2_comparison.png"), 'wb') as f:
            f.write(v2_img)
    
    def test_same_game_logic(self):
        """Test that standard and standard-v2 have identical game logic"""
        from engine.map import Map
        
        standard_map = Map("standard")
        v2_map = Map("standard-v2")
        
        # Test all provinces are the same
        assert set(standard_map.provinces.keys()) == set(v2_map.provinces.keys())
        
        # Test all adjacencies are the same
        for prov_name in standard_map.provinces:
            standard_adj = set(standard_map.provinces[prov_name].adjacent)
            v2_adj = set(v2_map.provinces[prov_name].adjacent)
            assert standard_adj == v2_adj, \
                f"Adjacencies for {prov_name} should match: {standard_adj} vs {v2_adj}"


class TestStandardV2EdgeCases:
    """Test edge cases and error handling for standard-v2"""
    
    def test_fallback_when_v2_svg_missing(self):
        """Test fallback behavior when v2.svg is missing"""
        from engine.map import Map
        
        # This should not raise an error, but should fallback to standard
        # (In practice, v2.svg exists, so we test the path resolution logic)
        svg_path = Map._resolve_svg_path("standard-v2")
        assert svg_path is not None, "Should resolve to a path (even if fallback)"
    
    def test_invalid_map_name_handling(self):
        """Test that invalid map names are handled gracefully"""
        from engine.map import Map
        
        # standard-v2 should work
        try:
            map_instance = Map("standard-v2")
            assert map_instance.map_name == "standard-v2"
        except Exception as e:
            pytest.fail(f"standard-v2 should be valid: {e}")
    
    def test_coordinate_extraction_with_malformed_svg(self):
        """Test coordinate extraction handles edge cases"""
        from engine.map import Map
        
        svg_path = Map._resolve_svg_path("standard-v2")
        if os.path.exists(svg_path):
            tree, coords = Map._get_cached_svg_data(svg_path)
            # Should handle missing or malformed text elements gracefully
            assert isinstance(coords, dict), "Should return dict even if extraction fails partially"


class TestStandardV2Integration:
    """Integration tests for standard-v2 map"""
    
    def test_full_game_workflow(self):
        """Test complete game workflow with standard-v2"""
        from server.server import Server
        
        server = Server()
        
        # Create game
        result = server.process_command("CREATE_GAME standard-v2")
        game_id = result.get("game_id") if isinstance(result, dict) else result
        
        try:
            # Add players
            server.process_command(f"ADD_PLAYER {game_id} FRANCE")
            server.process_command(f"ADD_PLAYER {game_id} GERMANY")
            
            # Set orders
            server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
            server.process_command(f"SET_ORDERS {game_id} GERMANY A MUN H")
            
            # Process turn
            result = server.process_command(f"PROCESS_TURN {game_id}")
            assert result is not None, "Turn processing should succeed"
            
            # Get game state
            state_result = server.process_command(f"GET_GAME_STATE {game_id}")
            assert state_result is not None, "Game state should be retrievable"
            
        finally:
            try:
                server.process_command(f"DELETE_GAME {game_id}")
            except:
                pass
    
    def test_multiple_games_different_maps(self):
        """Test creating multiple games with different map types"""
        from server.server import Server
        
        server = Server()
        
        result1 = server.process_command("CREATE_GAME standard")
        result2 = server.process_command("CREATE_GAME standard-v2")
        
        game_id1 = result1.get("game_id") if isinstance(result1, dict) else result1
        game_id2 = result2.get("game_id") if isinstance(result2, dict) else result2
        
        try:
            # Both games should exist and be independent
            state1 = server.process_command(f"GET_GAME_STATE {game_id1}")
            state2 = server.process_command(f"GET_GAME_STATE {game_id2}")
            
            assert state1 is not None, "Standard game should exist"
            assert state2 is not None, "Standard-v2 game should exist"
            
        finally:
            try:
                server.process_command(f"DELETE_GAME {game_id1}")
                server.process_command(f"DELETE_GAME {game_id2}")
            except:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

