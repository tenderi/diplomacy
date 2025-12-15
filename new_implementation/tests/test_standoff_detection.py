"""
Tests for standoff/stalemate detection in Diplomacy battles.

These tests ensure that equal strength battles result in standoffs
where no units move.
"""

import pytest
from src.engine.game import Game
from src.engine.data_models import MoveOrder, HoldOrder, SupportOrder, Unit


def test_1v1_battle_standoff():
    """Test 1-1 battle results in standoff."""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("FRANCE")

    
    # Create two units attacking the same province
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BUR", "GERMANY")
    
    game.game_state.powers["FRANCE"].units.append(unit1)
    game.game_state.powers["GERMANY"].units.append(unit2)
    
    # Both units move to GAS
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="GAS")
    move2 = MoveOrder(power="GERMANY", unit=unit2, target_province="GAS")
    
    game.game_state.orders["FRANCE"] = [move1]
    game.game_state.orders["GERMANY"] = [move2]
    
    results = game._process_movement_phase()
    
    # Both moves should bounce
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) == 2, f"Expected 2 bounced moves, got {len(bounced_moves)}: {moves}"
    
    # No units should have moved
    assert unit1.province == "PAR", "Unit1 should still be in PAR"
    assert unit2.province == "BUR", "Unit2 should still be in BUR"


def test_2v2_battle_standoff():
    """Test 2-2 battle with support results in standoff."""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    
    # Create units
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BRE", "FRANCE")
    unit3 = Unit("A", "BUR", "GERMANY")
    unit4 = Unit("A", "MUN", "GERMANY")
    
    game.game_state.powers["FRANCE"].units.append(unit1)
    game.game_state.powers["FRANCE"].units.append(unit2)
    game.game_state.powers["GERMANY"].units.append(unit3)
    game.game_state.powers["GERMANY"].units.append(unit4)
    
    # France: A PAR -> GAS, A BRE S A PAR -> GAS
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="GAS")
    support1 = SupportOrder(
        power="FRANCE",
        unit=unit2,
        supported_unit=unit1,
        supported_action="move",
        supported_target="GAS"
    )
    
    # Germany: A BUR -> GAS, A MUN S A BUR -> GAS
    move2 = MoveOrder(power="GERMANY", unit=unit3, target_province="GAS")
    support2 = SupportOrder(
        power="GERMANY",
        unit=unit4,
        supported_unit=unit3,
        supported_action="move",
        supported_target="GAS"
    )
    
    game.game_state.orders["FRANCE"] = [move1, support1]
    game.game_state.orders["GERMANY"] = [move2, support2]
    
    results = game._process_movement_phase()
    
    # Both moves should bounce (2-2 standoff)
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) == 2, f"Expected 2 bounced moves, got {len(bounced_moves)}: {moves}"
    
    # Check conflicts
    conflicts = results.get("conflicts", [])
    assert len(conflicts) > 0, "Should have conflicts"
    conflict = conflicts[0]
    assert conflict.get("winner") is None, "Should have no winner (standoff)"


def test_3v3_battle_standoff():
    """Test 3-3 battle results in standoff."""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("FRANCE")

    # Create units with multiple supports
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BRE", "FRANCE")
    unit3 = Unit("A", "PIC", "FRANCE")
    unit4 = Unit("A", "BUR", "GERMANY")
    unit5 = Unit("A", "MUN", "GERMANY")
    unit6 = Unit("A", "RUH", "GERMANY")
    
    game.game_state.powers["FRANCE"].units.append(unit1)

    
    game.game_state.powers["FRANCE"].units.append(unit2)

    
    game.game_state.powers["FRANCE"].units.append(unit3)
    game.game_state.powers["GERMANY"].units.append(unit4)

    game.game_state.powers["GERMANY"].units.append(unit5)

    game.game_state.powers["GERMANY"].units.append(unit6)
    
    # France: A PAR -> GAS with 2 supports
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="GAS")
    support1 = SupportOrder(power="FRANCE", unit=unit2, supported_unit=unit1, supported_action="move", supported_target="GAS")
    support2 = SupportOrder(power="FRANCE", unit=unit3, supported_unit=unit1, supported_action="move", supported_target="GAS")
    
    # Germany: A BUR -> GAS with 2 supports
    move2 = MoveOrder(power="GERMANY", unit=unit4, target_province="GAS")
    support3 = SupportOrder(power="GERMANY", unit=unit5, supported_unit=unit4, supported_action="move", supported_target="GAS")
    support4 = SupportOrder(power="GERMANY", unit=unit6, supported_unit=unit4, supported_action="move", supported_target="GAS")
    
    game.game_state.orders["FRANCE"] = [move1, support1, support2]
    game.game_state.orders["GERMANY"] = [move2, support3, support4]
    
    results = game._process_movement_phase()
    
    # Both moves should bounce (3-3 standoff)
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) == 2, f"Expected 2 bounced moves, got {len(bounced_moves)}: {moves}"


def test_hold_with_support_vs_move_with_support_standoff():
    """Test hold with support vs move with support results in standoff if equal."""
    game = Game('standard')
    game.add_player("ITALY")
    game.add_player("AUSTRIA")

    # Create units
    unit1 = Unit("A", "VEN", "ITALY")
    unit2 = Unit("A", "TUS", "ITALY")
    unit3 = Unit("A", "TYR", "AUSTRIA")
    unit4 = Unit("A", "TRI", "AUSTRIA")
    
    game.game_state.powers["ITALY"].units.append(unit1)

    
    game.game_state.powers["ITALY"].units.append(unit2)
    game.game_state.powers["AUSTRIA"].units.append(unit3)

    game.game_state.powers["AUSTRIA"].units.append(unit4)
    
    # Italy: A VEN H, A TUS S A VEN H
    hold1 = HoldOrder(power="ITALY", unit=unit1)
    support1 = SupportOrder(power="ITALY", unit=unit2, supported_unit=unit1, supported_action="hold")
    
    # Austria: A TYR -> VEN, A TRI S A TYR -> VEN
    move1 = MoveOrder(power="AUSTRIA", unit=unit3, target_province="VEN")
    support2 = SupportOrder(power="AUSTRIA", unit=unit4, supported_unit=unit3, supported_action="move", supported_target="VEN")
    
    game.game_state.orders["ITALY"] = [hold1, support1]
    game.game_state.orders["AUSTRIA"] = [move1, support2]
    
    results = game._process_movement_phase()
    
    # Should be standoff (2-2)
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) >= 1, f"Expected at least 1 bounced move, got {len(bounced_moves)}: {moves}"
    
    # Unit should still be in VEN
    assert unit1.province == "VEN", "Unit1 should still be in VEN"


def test_multiple_units_equal_strength_standoff():
    """Test multiple units attacking with equal strength results in standoff."""
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.add_player("ENGLAND")

    # Create 3 units all attacking the same province
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BUR", "GERMANY")
    unit3 = Unit("A", "BEL", "ENGLAND")
    
    game.game_state.powers["FRANCE"].units.append(unit1)
    game.game_state.powers["GERMANY"].units.append(unit2)
    game.game_state.powers["ENGLAND"].units.append(unit3)
    
    # All move to PIC
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="PIC")
    move2 = MoveOrder(power="GERMANY", unit=unit2, target_province="PIC")
    move3 = MoveOrder(power="ENGLAND", unit=unit3, target_province="PIC")
    
    game.game_state.orders["FRANCE"] = [move1]
    game.game_state.orders["GERMANY"] = [move2]
    game.game_state.orders["ENGLAND"] = [move3]
    
    results = game._process_movement_phase()
    
    # All moves should bounce (3-way standoff)
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) == 3, f"Expected 3 bounced moves, got {len(bounced_moves)}: {moves}"


def test_2_units_with_2_support_each_standoff():
    """Test 2 units with 2 support each attacking = standoff (3-3)."""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("FRANCE")

    # Create units
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BRE", "FRANCE")
    unit3 = Unit("A", "GAS", "FRANCE")
    unit4 = Unit("A", "BUR", "GERMANY")
    unit5 = Unit("A", "MUN", "GERMANY")
    unit6 = Unit("A", "RUH", "GERMANY")
    
    game.game_state.powers["FRANCE"].units.append(unit1)

    
    game.game_state.powers["FRANCE"].units.append(unit2)

    
    game.game_state.powers["FRANCE"].units.append(unit3)
    game.game_state.powers["GERMANY"].units.append(unit4)

    game.game_state.powers["GERMANY"].units.append(unit5)

    game.game_state.powers["GERMANY"].units.append(unit6)
    
    # France: A PAR -> PIC with 2 supports (strength 3)
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="PIC")
    support1 = SupportOrder(power="FRANCE", unit=unit2, supported_unit=unit1, supported_action="move", supported_target="PIC")
    support2 = SupportOrder(power="FRANCE", unit=unit3, supported_unit=unit1, supported_action="move", supported_target="PIC")
    
    # Germany: A BUR -> PIC with 2 supports (strength 3)
    move2 = MoveOrder(power="GERMANY", unit=unit4, target_province="PIC")
    support3 = SupportOrder(power="GERMANY", unit=unit5, supported_unit=unit4, supported_action="move", supported_target="PIC")
    support4 = SupportOrder(power="GERMANY", unit=unit6, supported_unit=unit4, supported_action="move", supported_target="PIC")
    
    game.game_state.orders["FRANCE"] = [move1, support1, support2]
    game.game_state.orders["GERMANY"] = [move2, support3, support4]
    
    results = game._process_movement_phase()
    
    # Both moves should bounce (3-3 standoff)
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) == 2, f"Expected 2 bounced moves, got {len(bounced_moves)}: {moves}"


def test_standoff_with_mixed_hold_and_move_orders():
    """Test standoff with mixed hold and move orders = all bounce."""
    game = Game('standard')
    game.add_player("ITALY")
    game.add_player("AUSTRIA")

    # Create units
    unit1 = Unit("A", "VEN", "ITALY")
    unit2 = Unit("A", "TUS", "ITALY")
    unit3 = Unit("A", "TYR", "AUSTRIA")
    unit4 = Unit("A", "TRI", "AUSTRIA")
    
    game.game_state.powers["ITALY"].units.append(unit1)

    
    game.game_state.powers["ITALY"].units.append(unit2)
    game.game_state.powers["AUSTRIA"].units.append(unit3)

    game.game_state.powers["AUSTRIA"].units.append(unit4)
    
    # Italy: A VEN H with support (strength 2)
    hold1 = HoldOrder(power="ITALY", unit=unit1)
    support1 = SupportOrder(power="ITALY", unit=unit2, supported_unit=unit1, supported_action="hold")
    
    # Austria: A TYR -> VEN with support (strength 2)
    move1 = MoveOrder(power="AUSTRIA", unit=unit3, target_province="VEN")
    support2 = SupportOrder(power="AUSTRIA", unit=unit4, supported_unit=unit3, supported_action="move", supported_target="VEN")
    
    game.game_state.orders["ITALY"] = [hold1, support1]
    game.game_state.orders["AUSTRIA"] = [move1, support2]
    
    results = game._process_movement_phase()
    
    # Should be standoff - move bounces, hold remains
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_moves) >= 1, f"Expected at least 1 bounced move, got {len(bounced_moves)}: {moves}"
    
    # Unit should still be in VEN
    assert unit1.province == "VEN", "Unit1 should still be in VEN"


def test_standoff_after_support_cut():
    """Test standoff after support cut: 3-2 becomes 2-2 = standoff."""
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.add_player("ENGLAND")

    # Create units
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BRE", "FRANCE")
    unit3 = Unit("A", "GAS", "FRANCE")
    unit4 = Unit("A", "BUR", "GERMANY")
    unit5 = Unit("A", "MUN", "GERMANY")
    unit6 = Unit("A", "PIC", "ENGLAND")  # Will cut support (PIC is adjacent to BRE)
    
    game.game_state.powers["FRANCE"].units.append(unit1)

    
    game.game_state.powers["FRANCE"].units.append(unit2)

    
    game.game_state.powers["FRANCE"].units.append(unit3)
    game.game_state.powers["GERMANY"].units.append(unit4)

    game.game_state.powers["GERMANY"].units.append(unit5)
    game.game_state.powers["ENGLAND"].units.append(unit6)
    
    # France: A PAR -> PIC with 2 supports (strength 3)
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="PIC")
    support1 = SupportOrder(power="FRANCE", unit=unit2, supported_unit=unit1, supported_action="move", supported_target="PIC")
    support2 = SupportOrder(power="FRANCE", unit=unit3, supported_unit=unit1, supported_action="move", supported_target="PIC")
    
    # Germany: A BUR -> PIC with 1 support (strength 2)
    move2 = MoveOrder(power="GERMANY", unit=unit4, target_province="PIC")
    support3 = SupportOrder(power="GERMANY", unit=unit5, supported_unit=unit4, supported_action="move", supported_target="PIC")
    
    # England: A PIC -> BRE (cuts support1) - PIC is adjacent to BRE
    move3 = MoveOrder(power="ENGLAND", unit=unit6, target_province="BRE")
    
    game.game_state.orders["FRANCE"] = [move1, support1, support2]
    game.game_state.orders["GERMANY"] = [move2, support3]
    game.game_state.orders["ENGLAND"] = [move3]
    
    results = game._process_movement_phase()
    
    # After support cut: 2-2 standoff
    moves = results.get("moves", [])
    bounced_moves = [m for m in moves if m.get("failure_reason") == "bounced"]
    # Both moves to PIC should bounce
    pic_moves = [m for m in moves if m.get("to") == "PIC"]
    bounced_pic = [m for m in pic_moves if m.get("failure_reason") == "bounced"]
    assert len(bounced_pic) == 2, f"Expected 2 bounced moves to PIC, got {len(bounced_pic)}: {pic_moves}"


def test_standoff_verification_no_units_move():
    """Test standoff verification: NO units move, all orders marked as bounced."""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("FRANCE")

    # Create units
    unit1 = Unit("A", "PAR", "FRANCE")
    unit2 = Unit("A", "BUR", "GERMANY")
    
    original_province1 = unit1.province
    original_province2 = unit2.province
    
    game.game_state.powers["FRANCE"].units.append(unit1)
    game.game_state.powers["GERMANY"].units.append(unit2)
    
    # Both move to GAS
    move1 = MoveOrder(power="FRANCE", unit=unit1, target_province="GAS")
    move2 = MoveOrder(power="GERMANY", unit=unit2, target_province="GAS")
    
    game.game_state.orders["FRANCE"] = [move1]
    game.game_state.orders["GERMANY"] = [move2]
    
    results = game._process_movement_phase()
    
    # Verify no units moved
    assert unit1.province == original_province1, f"Unit1 should not have moved from {original_province1}"
    assert unit2.province == original_province2, f"Unit2 should not have moved from {original_province2}"
    
    # Verify all moves are marked as bounced
    moves = results.get("moves", [])
    for move in moves:
        if move.get("to") == "GAS":
            assert move.get("success") == False, f"Move should fail: {move}"
            assert move.get("failure_reason") == "bounced", f"Move should be bounced: {move}"

