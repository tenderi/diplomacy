"""
Tests for map and power modules in the engine.
"""
import pytest
from engine.map import Map, Province
from engine.power import Power

def test_map_provinces():
    m = Map()
    assert "PAR" in m.provinces
    assert m.provinces["PAR"].is_supply_center
    assert m.is_adjacent("PAR", "BUR")
    assert not m.is_adjacent("PAR", "MAR")  # Not adjacent in stub

def test_supply_centers():
    m = Map()
    scs = m.get_supply_centers()
    assert "PAR" in scs
    assert "MAR" in scs

def test_power_init():
    p = Power("FRANCE", ["PAR", "MAR"])
    assert p.name == "FRANCE"
    assert "PAR" in p.home_centers
    assert p.is_alive

def test_power_gain_lose_center():
    p = Power("FRANCE", ["PAR"])
    p.lose_center("PAR")
    assert not p.is_alive
    p.gain_center("PAR")
    assert p.is_alive
