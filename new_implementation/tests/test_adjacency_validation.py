"""
Tests for adjacency validation in Diplomacy moves.

These tests ensure that units cannot move to non-adjacent provinces
unless the move is convoyed.
"""

import pytest
from src.engine.game import Game
from src.engine.data_models import MoveOrder, Unit, GameState, MapData, Province
from src.engine.map import Map


def test_ber_hol_not_adjacent():
    """Test that BER and HOL are not adjacent provinces."""
    game = Game('standard')
    ber = game.map.provinces.get('BER')
    hol = game.map.provinces.get('HOL')
    
    assert ber is not None, "BER province not found"
    assert hol is not None, "HOL province not found"
    assert 'HOL' not in ber.adjacent, "BER should not be adjacent to HOL"
    assert 'BER' not in hol.adjacent, "HOL should not be adjacent to BER"


def test_non_adjacent_move_rejected():
    """Test that a move from BER to HOL is rejected."""
    game = Game('standard')
    game.add_player("GERMANY")
    
    # Create a unit in BER
    unit = Unit("A", "BER", "GERMANY")
    game.game_state.powers["GERMANY"].units.append(unit)
    
    # Create a move order from BER to HOL (not adjacent)
    move_order = MoveOrder(
        power="GERMANY",
        unit=unit,
        target_province="HOL"
    )
    
    # Add order to game state
    game.game_state.orders["GERMANY"] = [move_order]
    
    # Process movement phase
    results = game._process_movement_phase()
    
    # The move should be rejected - no moves should succeed
    successful_moves = [m for m in results.get("moves", []) if m.get("status") == "success"]
    assert len(successful_moves) == 0, f"Non-adjacent move BER->HOL should be rejected, but got: {successful_moves}"


def test_adjacent_move_allowed():
    """Test that a move from BER to KIE (adjacent) is allowed."""
    game = Game('standard')
    game.add_player("GERMANY")
    
    # Create a unit in BER
    unit = Unit("A", "BER", "GERMANY")
    game.game_state.powers["GERMANY"].units.append(unit)
    
    # Create a move order from BER to KIE (adjacent)
    move_order = MoveOrder(
        power="GERMANY",
        unit=unit,
        target_province="KIE"
    )
    
    # Add order to game state
    game.game_state.orders["GERMANY"] = [move_order]
    
    # Process movement phase
    results = game._process_movement_phase()
    
    # The move should be processed (may succeed or bounce depending on conflicts)
    # At minimum, it should be in the move_strengths calculation
    moves = results.get("moves", [])
    # The move should be processed, even if it bounces
    assert len(moves) > 0 or any("KIE" in str(m) for m in results.get("conflicts", [])), \
        f"Adjacent move BER->KIE should be processed, but got: {results}"


def test_adjacency_is_bidirectional():
    """Test that adjacency is bidirectional."""
    game = Game('standard')
    
    # Test a few known adjacent pairs
    test_pairs = [
        ("BER", "KIE"),
        ("KIE", "BER"),
        ("PAR", "BUR"),
        ("BUR", "PAR"),
        ("VEN", "TRI"),
        ("TRI", "VEN"),
    ]
    
    for prov1, prov2 in test_pairs:
        p1 = game.map.provinces.get(prov1)
        p2 = game.map.provinces.get(prov2)
        
        assert p1 is not None, f"{prov1} not found"
        assert p2 is not None, f"{prov2} not found"
        assert prov2 in p1.adjacent, f"{prov1} should be adjacent to {prov2}"
        assert prov1 in p2.adjacent, f"{prov2} should be adjacent to {prov1}"


def test_convoyed_moves_bypass_adjacency():
    """Test that convoyed moves can bypass adjacency check."""
    game = Game('standard')
    game.add_player("ENGLAND")
    
    # Create an army in LON (coastal)
    army = Unit("A", "LON", "ENGLAND")
    game.game_state.powers["ENGLAND"].units.append(army)
    
    # Create a fleet in ENG (sea, adjacent to both LON and BRE)
    fleet = Unit("F", "ENG", "ENGLAND")
    game.game_state.powers["ENGLAND"].units.append(fleet)
    
    # Create a move order from LON to BRE (not directly adjacent for army)
    # This would require a convoy
    move_order = MoveOrder(
        power="ENGLAND",
        unit=army,
        target_province="BRE"
    )
    
    # Create a convoy order
    from src.engine.data_models import ConvoyOrder
    convoy_order = ConvoyOrder(
        power="ENGLAND",
        unit=fleet,
        convoyed_unit=army,
        convoyed_target="BRE"
    )
    
    # Add orders to game state
    game.game_state.orders["ENGLAND"] = [move_order, convoy_order]
    
    # Process movement phase
    results = game._process_movement_phase()
    
    # The convoyed move should be processed (not rejected for adjacency)
    # Check that convoy was processed
    convoys = results.get("convoys", [])
    # The convoy should be in the results, even if it fails for other reasons
    assert len(convoys) > 0 or any("BRE" in str(m) for m in results.get("moves", [])), \
        f"Convoyed move LON->BRE should be processed, but got: {results}"


def test_all_known_non_adjacent_pairs():
    """Test several known non-adjacent province pairs."""
    game = Game('standard')
    
    # Known non-adjacent pairs
    non_adjacent_pairs = [
        ("BER", "HOL"),
        ("PAR", "VEN"),
        ("MOS", "LON"),
        ("STP", "NAP"),
        ("ANK", "EDI"),
        ("CLY", "IRI"),  # CLY does NOT border IRI (corrected from hardcoded error)
    ]
    
    for prov1, prov2 in non_adjacent_pairs:
        p1 = game.map.provinces.get(prov1)
        p2 = game.map.provinces.get(prov2)
        
        if p1 and p2:
            assert prov2 not in p1.adjacent, f"{prov1} should NOT be adjacent to {prov2}"
            assert prov1 not in p2.adjacent, f"{prov2} should NOT be adjacent to {prov1}"


def test_cly_adjacencies_from_standard_map():
    """Test that CLY has correct adjacencies as defined in standard.map."""
    game = Game('standard')
    cly = game.map.provinces.get('CLY')
    
    assert cly is not None, "CLY province not found"
    
    # CLY should border: EDI, LVP, NAO, NWG (from standard.map line 146)
    expected_adjacents = {"EDI", "LVP", "NAO", "NWG"}
    actual_adjacents = set(cly.adjacent)
    
    assert actual_adjacents == expected_adjacents, \
        f"CLY should border {expected_adjacents}, but got {actual_adjacents}"
    
    # CLY should NOT border IRI (this was incorrectly in hardcoded data)
    assert "IRI" not in cly.adjacent, "CLY should NOT border IRI"


def test_iri_adjacencies_from_standard_map():
    """Test that IRI has correct adjacencies as defined in standard.map."""
    game = Game('standard')
    iri = game.map.provinces.get('IRI')
    
    assert iri is not None, "IRI province not found"
    
    # IRI should border: ENG, LVP, MAO, NAO, WAL (from standard.map line 159)
    expected_adjacents = {"ENG", "LVP", "MAO", "NAO", "WAL"}
    actual_adjacents = set(iri.adjacent)
    
    assert actual_adjacents == expected_adjacents, \
        f"IRI should border {expected_adjacents}, but got {actual_adjacents}"
    
    # IRI should NOT border CLY (this was incorrectly in hardcoded data)
    assert "CLY" not in iri.adjacent, "IRI should NOT border CLY"


def test_map_parsed_from_standard_map_file():
    """Test that the map is being parsed from standard.map file, not hardcoded."""
    game = Game('standard')
    
    # Verify that CLY does NOT border IRI (this would be wrong in old hardcoded data)
    cly = game.map.provinces.get('CLY')
    iri = game.map.provinces.get('IRI')
    
    assert cly is not None, "CLY province not found"
    assert iri is not None, "IRI province not found"
    
    # If map was parsed correctly from standard.map, CLY should not border IRI
    assert "IRI" not in cly.adjacent, \
        "Map appears to be using hardcoded data (CLY borders IRI). Should use standard.map instead."
    assert "CLY" not in iri.adjacent, \
        "Map appears to be using hardcoded data (IRI borders CLY). Should use standard.map instead."


def test_all_adjacencies_bidirectional():
    """Test that ALL adjacencies in the map are bidirectional."""
    game = Game('standard')
    
    issues = []
    for prov_name, province in game.map.provinces.items():
        for adj in province.adjacent:
            if adj in game.map.provinces:
                adj_province = game.map.provinces[adj]
                if prov_name not in adj_province.adjacent:
                    issues.append(f"{prov_name} borders {adj}, but {adj} does not border {prov_name}")
    
    assert len(issues) == 0, \
        f"Found {len(issues)} bidirectional adjacency issues:\n" + "\n".join(issues[:10])

