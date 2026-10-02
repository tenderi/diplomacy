"""The renderer's configuration: the JSON file and the built-in defaults agree, and
a partial file overrides only what it names."""
import json
import os
import tempfile

from PIL import ImageColor

from rendering.visualization_config import VisualizationConfig, get_config


def test_the_file_and_the_defaults_are_the_same() -> None:
    """The defaults exist so a missing file still renders; they must not drift from it."""
    path = os.path.join(os.path.dirname(__file__), "..", "src", "rendering", "visualization_config.json")
    with open(path, encoding="utf-8") as f:
        assert json.load(f) == VisualizationConfig.DEFAULT_CONFIG


def test_a_partial_file_overrides_only_what_it_names() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"arrows": {"move_width": 9}, "colors": {"power_colors": {"FRANCE": "#000001"}}}, f)
    try:
        config = VisualizationConfig(config_path=f.name)
        assert config.get_arrow_specs()["move_width"] == 9
        assert config.get_arrow_specs()["support_width"] == VisualizationConfig.DEFAULT_CONFIG["arrows"]["support_width"]
        assert config.get_power_color("FRANCE") == "#000001"
        assert config.get_power_color("ITALY") == VisualizationConfig.DEFAULT_CONFIG["colors"]["power_colors"]["ITALY"]
        # Loading a file must not leak into the class-level defaults.
        assert VisualizationConfig.DEFAULT_CONFIG["arrows"]["move_width"] != 9
    finally:
        os.unlink(f.name)


def test_the_singleton() -> None:
    assert get_config() is get_config()


def _distance(a: str, b: str) -> float:
    (r1, g1, b1), (r2, g2, b2) = ImageColor.getrgb(a)[:3], ImageColor.getrgb(b)[:3]
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def test_the_seven_powers_are_told_apart() -> None:
    """The old palette had Austria, Germany and Russia as three muddy browns and
    greys (closest pair 40 apart in RGB)."""
    colours = list(get_config().get_power_colors().values())
    assert len(colours) == 7
    closest = min(_distance(a, b) for i, a in enumerate(colours) for b in colours[i + 1:])
    assert closest > 60


def test_no_power_wears_the_outcome_colours() -> None:
    config = get_config()
    for name in ("void", "standoff", "casing"):
        assert min(_distance(config.get_color(name), c) for c in config.get_power_colors().values()) > 60
