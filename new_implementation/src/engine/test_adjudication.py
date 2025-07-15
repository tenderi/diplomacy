"""
Tests for advanced order adjudication and turn processing in Diplomacy.
Covers support cut, standoffs, convoyed moves, and dislodgement.
"""
from .game import Game

def test_support_cut():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"BUR"}
    game.set_orders("FRANCE", ["FRANCE A PAR S A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A BUR - PAR"])
    game.process_turn()
    assert "A PAR" in game.powers["FRANCE"].units
    assert "A BUR" in game.powers["GERMANY"].units

def test_standoff():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"MAR"}
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A MAR - BUR"])
    game.process_turn()
    assert "A PAR" in game.powers["FRANCE"].units
    assert "A MAR" in game.powers["GERMANY"].units

def test_convoyed_move():
    game = Game()
    game.add_player("ENGLAND")
    game.add_player("FRANCE")
    game.powers["ENGLAND"].units = {"A LON", "F NTH", "A YOR"}
    game.powers["FRANCE"].units = {"A BEL"}
    # England A LON - BEL via convoy with support, F NTH convoys, A YOR supports
    game.set_orders("ENGLAND", [
        "ENGLAND A LON - BEL",
        "ENGLAND F NTH C A LON - BEL",
        "ENGLAND A YOR S A LON - BEL"  # Support for the convoyed attack
    ])
    game.set_orders("FRANCE", [
        "FRANCE A BEL H"
    ])
    game.process_turn()
    # Supported attack (strength 2) should beat defender (strength 1)
    assert "A BEL" in game.powers["ENGLAND"].units   # Army moved to BEL
    assert "A BEL" not in game.powers["FRANCE"].units # French army dislodged
    assert "A LON" not in game.powers["ENGLAND"].units # Army left LON
    assert "F NTH" in game.powers["ENGLAND"].units   # Fleet stays in NTH
    assert "A YOR" in game.powers["ENGLAND"].units   # Supporting army stays

def test_dislodgement():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"A PAR"}
    game.powers["GERMANY"].units = {"A BUR", "A MUN"}
    # Germany attacks PAR from BUR with support from MUN
    game.set_orders("FRANCE", ["FRANCE A PAR H"])
    game.set_orders("GERMANY", [
        "GERMANY A BUR - PAR",
        "GERMANY A MUN S A BUR - PAR"
    ])
    game.process_turn()
    # French unit should be dislodged from PAR
    assert "A PAR" not in game.powers["FRANCE"].units
    assert "A PAR" in game.powers["GERMANY"].units
    assert "A BUR" not in game.powers["GERMANY"].units
    assert "A MUN" in game.powers["GERMANY"].units

def test_beleaguered_garrison():
    """Test beleaguered garrison: two equal attacks standoff, defender stays"""
    game = Game()
    game.add_player("AUSTRIA")
    game.add_player("RUSSIA")
    game.add_player("TURKEY")
    game.powers["AUSTRIA"].units = {"SER"}
    game.powers["RUSSIA"].units = {"RUM", "BUD"}
    game.powers["TURKEY"].units = {"BUL", "GRE"}
    
    # Two supported attacks of equal strength against defending unit
    game.set_orders("AUSTRIA", ["AUSTRIA A SER H"])
    game.set_orders("RUSSIA", [
        "RUSSIA A RUM - SER", 
        "RUSSIA A BUD S A RUM - SER"
    ])
    game.set_orders("TURKEY", [
        "TURKEY A BUL - SER",
        "TURKEY A GRE S A BUL - SER"
    ])
    
    game.process_turn()
    
    # All units should stay in place - beleaguered garrison
    assert "A SER" in game.powers["AUSTRIA"].units  # Defender stays
    assert "A RUM" in game.powers["RUSSIA"].units   # Attacker 1 fails
    assert "A BUD" in game.powers["RUSSIA"].units   # Supporter stays
    assert "A BUL" in game.powers["TURKEY"].units   # Attacker 2 fails
    assert "A GRE" in game.powers["TURKEY"].units   # Supporter stays

def test_support_cut_by_dislodgement():
    """Test support being cut by dislodgement of supporting unit"""
    game = Game()
    game.add_player("GERMANY")
    game.add_player("RUSSIA")
    game.powers["GERMANY"].units = {"A BER", "A SIL"}
    game.powers["RUSSIA"].units = {"A PRU", "A WAR", "A BOH"}
    # Germany tries to take Prussia with support, but supporting unit is dislodged
    game.set_orders("GERMANY", [
        "GERMANY A BER - PRU",
        "GERMANY A SIL S A BER - PRU"
    ])
    game.set_orders("RUSSIA", [
        "RUSSIA A PRU H",  # Defends Prussia
        "RUSSIA A WAR - SIL",   # Attacks and dislodges supporting unit
        "RUSSIA A BOH S A WAR - SIL"  # Supports the attack on supporting unit
    ])
    game.process_turn()
    # Support should be cut by dislodgement, attack on Prussia should fail
    assert "A BER" in game.powers["GERMANY"].units  # Failed to move
    assert "A SIL" not in game.powers["GERMANY"].units  # Dislodged
    assert "A SIL" in game.powers["RUSSIA"].units   # Russian unit moved in
    assert "A PRU" in game.powers["RUSSIA"].units   # Russian unit stayed to defend

def test_self_standoff():
    """Test self-standoff: country can stand off its own units"""
    game = Game()
    game.add_player("AUSTRIA")
    game.add_player("RUSSIA")
    game.powers["AUSTRIA"].units = {"A SER", "A VIE"}
    game.powers["RUSSIA"].units = {"A GAL"}
    
    # Austria orders two equally supported attacks on same space
    game.set_orders("AUSTRIA", [
        "AUSTRIA A SER - BUD",
        "AUSTRIA A VIE - BUD"
    ])
    game.set_orders("RUSSIA", [
        "RUSSIA A GAL S A SER - BUD"  # Support one of the attacks
    ])
    
    game.process_turn()
    
    # Supported attack should succeed over unsupported
    assert "A BUD" in game.powers["AUSTRIA"].units  # Supported attack wins
    assert "A VIE" in game.powers["AUSTRIA"].units  # Unsupported attack fails
    assert "A SER" not in game.powers["AUSTRIA"].units  # Supported unit moved
    assert "A GAL" in game.powers["RUSSIA"].units   # Supporter stays

def test_complex_convoy_disruption():
    """Test convoy disruption by attacking convoying fleet"""
    game = Game()
    game.add_player("FRANCE")
    game.add_player("ITALY")
    game.powers["FRANCE"].units = {"A SPA", "F LYO", "F TYS"}
    game.powers["ITALY"].units = {"F ION", "F TUN"}
    # France tries to convoy army, but one convoying fleet is attacked
    game.set_orders("FRANCE", [
        "FRANCE A SPA - NAP",
        "FRANCE F LYO C A SPA - NAP",
        "FRANCE F TYS C A SPA - NAP"
    ])
    game.set_orders("ITALY", [
        "ITALY F ION - TYS",  # Attack convoying fleet
        "ITALY F TUN S F ION - TYS"
    ])
    game.process_turn()
    
    # Fleet should be dislodged, convoy should fail
    assert "A SPA" in game.powers["FRANCE"].units   # Army stays (convoy failed)
    assert "F LYO" in game.powers["FRANCE"].units   # Fleet stays
    assert "F TYS" not in game.powers["FRANCE"].units  # Fleet dislodged
    assert "F TYS" in game.powers["ITALY"].units    # Italian fleet moved in
    assert "F ION" not in game.powers["ITALY"].units  # Italian fleet moved out

def test_circular_movement():
    """Test circular movement between three units"""
    game = Game()
    game.add_player("ENGLAND")
    game.powers["ENGLAND"].units = {"A HOL", "F BEL", "F NTH"}  # Set proper unit types
    
    # Three units move in a circle
    game.set_orders("ENGLAND", [
        "ENGLAND A HOL - BEL",
        "ENGLAND F BEL - NTH",
        "ENGLAND F NTH - HOL"
    ])
    
    game.process_turn()
    
    # All units should move successfully in circle
    assert "A BEL" in game.powers["ENGLAND"].units  # Army moved
    assert "F NTH" in game.powers["ENGLAND"].units  # Fleet 1 moved
    assert "F HOL" in game.powers["ENGLAND"].units  # Fleet 2 moved
    # Check original positions are vacated
    assert len(game.powers["ENGLAND"].units) == 3  # All three units

def test_self_dislodgement_prohibited():
    """Test that a power cannot dislodge its own unit (self-dislodgement prohibited)."""
    from engine.game import Game
    game = Game(map_name='standard')
    game.add_player('FRANCE')
    # Place two French units in adjacent provinces
    game.powers['FRANCE'].units = {'PAR', 'BUR'}
    # Attempt to move A PAR to BUR, which is occupied by own unit
    game.set_orders('FRANCE', ['A PAR - BUR'])
    game.process_turn()
    # Both units should remain in place (no self-dislodgement)
    assert "A PAR" in game.powers["FRANCE"].units
    assert "A BUR" in game.powers["FRANCE"].units
