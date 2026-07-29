"""Tests for ``rendering.view_adapter`` — pure GameService-view -> renderer adapters.

No DB, no FastAPI, no rendering pipeline: these are dict-in/dict-out unit tests, the
same style as ``tests/test_legal_orders.py``.
"""
from __future__ import annotations

import pytest

from rendering.view_adapter import phase_info, svg_path_for_map_name, units_for_render

pytestmark = pytest.mark.unit


def _view(**overrides: object) -> dict:
    base = {
        "year": 1901,
        "season": "SPRING",
        "phase_type": "MOVEMENT",
        "phase": "S1901M",
        "units_by_power": {
            "FRANCE": [
                {"kind": "A", "power": "FRANCE", "location": "PAR"},
                {"kind": "F", "power": "FRANCE", "location": "BRE"},
            ],
            "ENGLAND": [
                {"kind": "F", "power": "ENGLAND", "location": "STP/SC"},
            ],
        },
    }
    base.update(overrides)
    return base


class TestSvgPathForMapName:
    def test_default_map_uses_env_or_default(self, monkeypatch):
        monkeypatch.delenv("DIPLOMACY_MAP_PATH", raising=False)
        assert svg_path_for_map_name("standard") == "maps/standard.svg"

    def test_default_map_respects_env_override(self, monkeypatch):
        monkeypatch.setenv("DIPLOMACY_MAP_PATH", "/tmp/custom.svg")
        assert svg_path_for_map_name("standard") == "/tmp/custom.svg"


class TestUnitsForRender:
    def test_groups_by_power_and_strips_coast(self):
        result = units_for_render(_view())
        assert result == {
            "FRANCE": ["A PAR", "F BRE"],
            "ENGLAND": ["F STP"],
        }

    def test_missing_units_by_power_is_empty(self):
        assert units_for_render({}) == {}

    def test_empty_power_list_yields_empty_list(self):
        result = units_for_render({"units_by_power": {"GERMANY": []}})
        assert result == {"GERMANY": []}


class TestPhaseInfo:
    def test_builds_expected_keys(self):
        result = phase_info(_view(), turn=3)
        assert result == {
            "turn": 3,
            "year": 1901,
            "season": "SPRING",
            "phase": "MOVEMENT",
            "phase_code": "S1901M",
        }

    def test_missing_required_key_raises(self):
        with pytest.raises(KeyError):
            phase_info({"year": 1901, "season": "SPRING", "phase_type": "MOVEMENT"}, turn=1)
