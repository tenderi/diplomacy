"""
Configuration loader for visualization settings.

This module provides a centralized way to manage all visualization parameters
as specified in the visualization specification. All visual elements should
use this configuration to ensure consistency and easy customization.
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("diplomacy.engine.visualization_config")


class VisualizationConfig:
    """
    Configuration class for visualization parameters.
    
    Loads configuration from JSON file with fallback to defaults.
    Provides methods to access all visualization parameters.
    """
    
    # Default configuration matching spec section 3.4
    DEFAULT_CONFIG = {
        "arrows": {
            "arrowhead_size": 12,
            "arrowhead_base_width": 15,
            "line_width_primary": 3,
            "line_width_secondary": 2,
            "shape": "triangular"
        },
        "colors": {
            "success": "#00FF00",
            "failure": "#FF0000",
            "convoy": "#FFD700",
            "support_defensive": "#90EE90",
            "support_offensive": "#FFB6C1",
            "power_colors": {
                "AUSTRIA": "#c48f85",
                "ENGLAND": "darkviolet",
                "FRANCE": "royalblue",
                "GERMANY": "#a08a75",
                "ITALY": "forestgreen",
                "RUSSIA": "#757d91",
                "TURKEY": "#b9a61c"
            }
        },
        "units": {
            "diameter": 22,
            "border_width": 2,
            "dislodged_border_width": 3,
            "dislodged_offset": [20, 20],
            "label_font_size": 11,
            "dislodged_indicator_size": 9,
            "dislodged_indicator_offset": [6, 6]
        },
        "line_styles": {
            "solid": {},
            "dashed": {"dash": 4, "gap": 2},
            "dotted": {"dot": 2, "gap": 2}
        },
        "markers": {
            "hold_indicator_diameter": 32,
            "hold_indicator_border_width": 2,
            "support_circle_diameter": 32,
            "support_circle_border_width": 3,
            "convoy_fleet_marker_diameter": 30,
            "convoy_fleet_marker_border_width": 2,
            "build_marker_diameter": 18,
            "build_marker_border_width": 2,
            "destroy_marker_diameter": 18,
            "destroy_marker_border_width": 2,
            "battle_indicator_size": 22,
            "battle_indicator_border_width": 2,
            "standoff_indicator_size": 20,
            "standoff_indicator_border_width": 2,
            "status_indicator_size": 13,
            "status_indicator_line_width": 2
        },
        "fonts": {
            "unit_label_size": 11,
            "hold_label_size": 9,
            "phase_overlay_size": 16,
            "conflict_label_size": 11,
            "standoff_label_size": 9
        }
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration from file or use defaults.
        
        Args:
            config_path: Path to JSON configuration file. If None, uses default
                        location relative to this module.
        """
        if config_path is None:
            # Default location: same directory as this module
            module_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(module_dir, "visualization_config.json")
        
        self.config = self.DEFAULT_CONFIG.copy()
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Deep merge with defaults
                    self._merge_config(self.config, file_config)
                logger.info(f"Loaded visualization config from {config_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config from {config_path}: {e}. Using defaults.")
        else:
            logger.info(f"Config file not found at {config_path}. Using defaults.")
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override config into base config."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get_arrow_specs(self) -> Dict[str, Any]:
        """Return arrow configuration."""
        return self.config["arrows"].copy()
    
    def get_color(self, name: str) -> str:
        """
        Get color by semantic name.
        
        Args:
            name: Color name (e.g., "success", "failure", "convoy", 
                  "support_defensive", "support_offensive")
        
        Returns:
            Color string (hex or named color)
        """
        colors = self.config["colors"]
        if name in colors and name != "power_colors":
            return colors[name]
        logger.warning(f"Unknown color name: {name}. Returning black.")
        return "#000000"
    
    def get_power_color(self, power: str) -> str:
        """
        Get power-specific color.
        
        Args:
            power: Power name (e.g., "AUSTRIA", "ENGLAND")
        
        Returns:
            Color string (hex or named color)
        """
        power_colors = self.config["colors"]["power_colors"]
        if power in power_colors:
            return power_colors[power]
        logger.warning(f"Unknown power: {power}. Returning black.")
        return "#000000"
    
    def get_unit_specs(self) -> Dict[str, Any]:
        """Return unit marker configuration."""
        return self.config["units"].copy()
    
    def get_line_style(self, style: str) -> Dict[str, Any]:
        """
        Get line style pattern.
        
        Args:
            style: Style name ("solid", "dashed", "dotted")
        
        Returns:
            Dictionary with style parameters
        """
        line_styles = self.config["line_styles"]
        if style in line_styles:
            return line_styles[style].copy()
        logger.warning(f"Unknown line style: {style}. Returning solid.")
        return {}
    
    def get_marker_specs(self) -> Dict[str, Any]:
        """Return marker configuration."""
        return self.config["markers"].copy()
    
    def get_font_specs(self) -> Dict[str, Any]:
        """Return font configuration."""
        return self.config["fonts"].copy()


# Global singleton instance
_config_instance: Optional[VisualizationConfig] = None


def get_config() -> VisualizationConfig:
    """
    Get the global configuration instance (singleton pattern).
    
    Returns:
        VisualizationConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = VisualizationConfig()
    return _config_instance

