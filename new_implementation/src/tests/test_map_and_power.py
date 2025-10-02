"""
Tests for map and power modules in the engine.
"""
from engine.map import Map
from engine.power import Power

def test_map_provinces():
    m = Map()
    assert "PAR" in m.provinces
    assert m.provinces["PAR"].is_supply_center
    assert m.is_adjacent("PAR", "BUR")
    # Updated: PAR and BRE are adjacent in the standard map
    assert m.is_adjacent("PAR", "BRE")

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

def test_get_locations_and_adjacency():
    m = Map()
    locs = m.get_locations()
    assert "PAR" in locs
    adj = m.get_adjacency("PAR")
    assert "BUR" in adj
    assert "PIC" in adj
    assert m.validate_location("PAR")
    assert not m.validate_location("XYZ")

def test_map_edge_cases():
    m = Map()
    # Invalid province adjacency
    assert not m.is_adjacent("PAR", "XYZ")
    # All supply centers are valid locations
    for sc in m.get_supply_centers():
        assert m.validate_location(sc)
    # Adjacency is symmetric (if A->B, then B->A for land provinces)
    for prov in m.get_locations():
        for adj in m.get_adjacency(prov):
            if m.validate_location(adj):
                assert prov in m.get_adjacency(adj)

def test_variant_map_integration():
    """Test integration: create a game with a map variant and process a turn."""
    from .game import Game
    game = Game(map_name='mini_variant')
    game.add_player('FRANCE')
    # Place a unit in PAR (exists in mini_variant)
    game.powers['FRANCE'].units = {'A PAR'}
    # Move to MAR (adjacent in mini_variant)
    game.set_orders('FRANCE', ['A PAR - MAR'])
    game.process_phase()
    # Unit should have moved to MAR
    assert 'A MAR' in game.powers['FRANCE'].units
    assert 'A PAR' not in game.powers['FRANCE'].units
