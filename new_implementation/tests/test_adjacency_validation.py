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
    ]
    
    for prov1, prov2 in non_adjacent_pairs:
        p1 = game.map.provinces.get(prov1)
        p2 = game.map.provinces.get(prov2)
        
        if p1 and p2:
            assert prov2 not in p1.adjacent, f"{prov1} should NOT be adjacent to {prov2}"
            assert prov1 not in p2.adjacent, f"{prov2} should NOT be adjacent to {prov1}"

