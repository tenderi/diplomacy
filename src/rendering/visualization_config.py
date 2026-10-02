"""Every size, colour and line style the renderer uses, read from
``visualization_config.json`` beside this module.

``DEFAULT_CONFIG`` is the same data, so a missing or partial file still renders;
``tests/test_visualization.py`` keeps the two identical. What each value *means*
is in ``docs/specs/visualization_spec.md``.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("diplomacy.rendering.visualization_config")


class VisualizationConfig:
    """The renderer's visual constants, file values merged over the defaults."""

    DEFAULT_CONFIG: dict[str, Any] = {
        "colors": {
            "power_colors": {
                "AUSTRIA": "#D32F2F",
                "ENGLAND": "#7B1FA2",
                "FRANCE": "#1E88E5",
                "GERMANY": "#424242",
                "ITALY": "#2E7D32",
                "RUSSIA": "#00897B",
                "TURKEY": "#FBC02D",
            },
            "casing": "#111111",
            "halo": "#FFFFFF",
            "failure": "#E00000",
            "void": "#8A8A8A",
            "standoff": "#FF6F00",
            "build": "#2E7D32",
            "footer_background": "#F4F1EA",
            "footer_text": "#1A1A1A",
        },
        "units": {
            "diameter": 30,
            "outline_width": 2,
            "font_size": 17,
            "light_text_threshold": 500,
            "build_alpha": 150,
        },
        "arrows": {
            "move_width": 5,
            "support_width": 3,
            "retreat_width": 4,
            "casing": 1.5,
            "head_length": 18,
            "head_half_width": 9,
            "head_notch": 5,
            "token_gap": 3,
            "bounce_bar_half_length": 8,
            "bounce_bar_width": 5,
            "opposed_offset": 9,
            "support_dot_radius": 5,
            "convoy_steps_per_leg": 16,
        },
        "line_styles": {
            "dashed": {"dash": 9, "gap": 6},
            "dotted": {"dash": 3, "gap": 5},
        },
        "markers": {
            "hold_gap": 5,
            "hold_width": 3,
            "support_ring_gap": 9,
            "support_ring_width": 3,
            "dislodged_gap": 4,
            "dislodged_width": 4,
            "cross_size": 8,
            "cross_width": 4,
            "standoff_radius": 15,
            "build_badge_radius": 8,
            "faded_alpha": 140,
            "land_tint_alpha": 72,
            "sea_hatch_alpha": 120,
        },
        "footer": {
            "padding": 12,
            "row_height": 30,
            "item_gap": 26,
            "symbol_width": 34,
            "title_font_size": 18,
            "item_font_size": 15,
        },
    }

    def __init__(self, config_path: Optional[str] = None) -> None:
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visualization_config.json")
        self.config: dict[str, Any] = copy.deepcopy(self.DEFAULT_CONFIG)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self._merge_config(self.config, json.load(f))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config from {config_path}: {e}. Using defaults.")
        else:
            logger.info(f"Config file not found at {config_path}. Using defaults.")

    def _merge_config(self, base: dict[str, Any], override: dict[str, Any]) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get_color(self, name: str) -> str:
        """A semantic colour (``failure``, ``standoff``, ...)."""
        colors = self.config["colors"]
        if name in colors and name != "power_colors":
            return str(colors[name])
        raise KeyError(f"unknown colour {name!r}")

    def get_power_color(self, power: str) -> str:
        """``power``'s colour; grey for anything that is not one of the seven."""
        return str(self.config["colors"]["power_colors"].get(power.upper(), "#9E9E9E"))

    def get_power_colors(self) -> dict[str, str]:
        return dict(self.config["colors"]["power_colors"])

    def get_unit_specs(self) -> dict[str, Any]:
        return dict(self.config["units"])

    def get_arrow_specs(self) -> dict[str, Any]:
        return dict(self.config["arrows"])

    def get_line_style(self, style: str) -> dict[str, Any]:
        """Dash pattern for ``dashed``/``dotted``; ``{}`` (unbroken) for anything else."""
        return dict(self.config["line_styles"].get(style, {}))

    def get_marker_specs(self) -> dict[str, Any]:
        return dict(self.config["markers"])

    def get_footer_specs(self) -> dict[str, Any]:
        return dict(self.config["footer"])


_config_instance: Optional[VisualizationConfig] = None


def get_config() -> VisualizationConfig:
    """The process-wide configuration, loaded once."""
    global _config_instance
    if _config_instance is None:
        _config_instance = VisualizationConfig()
    return _config_instance
