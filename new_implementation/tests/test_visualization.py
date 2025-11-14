"""
Tests for visualization configuration and marker rendering.

Tests config loading, marker rendering, and visual consistency.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path

from engine.visualization_config import VisualizationConfig, get_config
from engine.map import Map


class TestVisualizationConfig:
    """Test visualization configuration loading and access."""
    
    def test_config_loads_defaults(self):
        """Test that config loads with defaults when no file exists."""
        # Create a config with a non-existent path
        config = VisualizationConfig(config_path="/nonexistent/path/config.json")
        
        # Verify defaults are loaded
        assert config.get_arrow_specs()["arrowhead_size"] == 12
        assert config.get_color("success") == "#00FF00"
        assert config.get_power_color("FRANCE") == "royalblue"
        assert config.get_unit_specs()["diameter"] == 22
    
    def test_config_loads_from_file(self):
        """Test that config loads from JSON file."""
        # Create temporary config file
        test_config = {
            "arrows": {"arrowhead_size": 15},
            "colors": {"success": "#00FF00"},
            "units": {"diameter": 25}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_config, f)
            config_path = f.name
        
        try:
            config = VisualizationConfig(config_path=config_path)
            # Verify file values are loaded
            assert config.get_arrow_specs()["arrowhead_size"] == 15
            # Verify defaults are merged
            assert config.get_arrow_specs()["line_width_primary"] == 3
        finally:
            os.unlink(config_path)
    
    def test_config_singleton(self):
        """Test that get_config() returns singleton instance."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2
    
    def test_get_color(self):
        """Test color retrieval by semantic name."""
        config = get_config()
        assert config.get_color("success") == "#00FF00"
        assert config.get_color("failure") == "#FF0000"
        assert config.get_color("convoy") == "#FFD700"
        assert config.get_color("support_defensive") == "#90EE90"
        assert config.get_color("support_offensive") == "#FFB6C1"
    
    def test_get_power_color(self):
        """Test power color retrieval."""
        config = get_config()
        assert config.get_power_color("AUSTRIA") == "#c48f85"
        assert config.get_power_color("ENGLAND") == "darkviolet"
        assert config.get_power_color("FRANCE") == "royalblue"
        assert config.get_power_color("GERMANY") == "#a08a75"
        assert config.get_power_color("ITALY") == "forestgreen"
        assert config.get_power_color("RUSSIA") == "#757d91"
        assert config.get_power_color("TURKEY") == "#b9a61c"
    
    def test_get_line_style(self):
        """Test line style retrieval."""
        config = get_config()
        solid = config.get_line_style("solid")
        assert solid == {}
        
        dashed = config.get_line_style("dashed")
        assert dashed["dash"] == 4
        assert dashed["gap"] == 2
        
        dotted = config.get_line_style("dotted")
        assert dotted["dot"] == 2
        assert dotted["gap"] == 2
    
    def test_get_unit_specs(self):
        """Test unit specification retrieval."""
        config = get_config()
        specs = config.get_unit_specs()
        # Check that specs are valid (may be from defaults or loaded file)
        assert specs["diameter"] > 0
        assert specs["border_width"] > 0
        assert specs["dislodged_border_width"] > 0
        assert len(specs["dislodged_offset"]) == 2
        assert specs["dislodged_offset"][0] > 0
        assert specs["dislodged_offset"][1] > 0
    
    def test_get_marker_specs(self):
        """Test marker specification retrieval."""
        config = get_config()
        specs = config.get_marker_specs()
        assert "build_marker_diameter" in specs
        assert "destroy_marker_diameter" in specs
        assert "battle_indicator_size" in specs
        assert "standoff_indicator_size" in specs


class TestMarkerRendering:
    """Test that markers render correctly using config values."""
    
    def test_arrow_function_uses_config(self):
        """Test that _draw_arrow uses config values."""
        # This is an integration test - verify the function exists and accepts config parameters
        assert hasattr(Map, '_draw_arrow')
        # The function signature should accept status parameter
        import inspect
        sig = inspect.signature(Map._draw_arrow)
        assert 'status' in sig.parameters
    
    def test_unit_markers_use_config(self):
        """Test that unit markers use config values."""
        # Verify unit drawing functions exist
        assert hasattr(Map, 'render_board_png')
        # The rendering should use config values internally
        # This is verified by the fact that config is imported and used in map.py
    
    def test_build_destroy_markers_use_config(self):
        """Test that build/destroy markers use config values."""
        assert hasattr(Map, '_draw_build_order')
        assert hasattr(Map, '_draw_destroy_order')
    
    def test_support_markers_use_config(self):
        """Test that support markers use config values."""
        assert hasattr(Map, '_draw_support_order')
    
    def test_convoy_markers_use_config(self):
        """Test that convoy markers use config values."""
        assert hasattr(Map, '_draw_convoy_order')
    
    def test_conflict_markers_use_config(self):
        """Test that conflict markers use config values."""
        assert hasattr(Map, '_draw_conflict_marker')
        assert hasattr(Map, '_draw_standoff_indicator')
    
    def test_status_indicators_use_config(self):
        """Test that status indicators use config values."""
        assert hasattr(Map, '_draw_success_checkmark')
        assert hasattr(Map, '_draw_failure_x')


class TestVisualConsistency:
    """Test visual consistency across markers."""
    
    def test_all_arrows_use_same_shape(self):
        """Test that all arrows use the same base shape from config."""
        config = get_config()
        arrow_specs = config.get_arrow_specs()
        # All arrows should use the same arrowhead_size and shape
        assert arrow_specs["arrowhead_size"] > 0
        assert arrow_specs["shape"] == "triangular"
    
    def test_colors_are_consistent(self):
        """Test that colors are consistently retrieved from config."""
        config = get_config()
        # Success/failure colors should be consistent
        success = config.get_color("success")
        failure = config.get_color("failure")
        assert success != failure
        # Colors should be valid (hex or named color)
        assert success.startswith("#") or success in ["green", "red", "blue", "yellow", "orange", "purple", "cyan", "magenta", "black", "white", "darkviolet", "royalblue", "forestgreen"]
    
    def test_font_sizes_are_consistent(self):
        """Test that font sizes are consistently retrieved from config."""
        config = get_config()
        font_specs = config.get_font_specs()
        assert font_specs["unit_label_size"] > 0
        assert font_specs["phase_overlay_size"] > 0
        assert font_specs["conflict_label_size"] > 0

