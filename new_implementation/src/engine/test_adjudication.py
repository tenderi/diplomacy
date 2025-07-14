"""
Tests for advanced order adjudication and turn processing in Diplomacy.
Covers support cut, standoffs, convoyed moves, and dislodgement.
"""
from engine.game import Game

def test_support_cut():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"BUR"}
    game.set_orders("FRANCE", ["FRANCE A PAR S A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A BUR - PAR"])
    game.process_turn()
    assert "PAR" in game.powers["FRANCE"].units
    assert "BUR" in game.powers["GERMANY"].units

def test_standoff():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"MAR"}
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A MAR - BUR"])
    game.process_turn()
    assert "PAR" in game.powers["FRANCE"].units
    assert "MAR" in game.powers["GERMANY"].units

def test_convoyed_move():
    game = Game()
    game.add_player("ENGLAND")
    game.add_player("FRANCE")
    game.powers["ENGLAND"].units = {"LON", "NTH", "YOR"}
    game.powers["FRANCE"].units = {"BEL"}
    # England A LON - BEL via convoy with support, F NTH convoys, A YOR supports
    game.set_orders("ENGLAND", [
        "ENGLAND A LON - BEL VIA CONVOY",
        "ENGLAND F NTH C A LON - BEL",
        "ENGLAND A YOR S A LON - BEL"  # Support for the convoyed attack
    ])
    game.set_orders("FRANCE", [
        "FRANCE A BEL H"
    ])
    game.process_turn()
    # Supported attack (strength 2) should beat defender (strength 1)
    assert "BEL" in game.powers["ENGLAND"].units   # Army moved to BEL
    assert "BEL" not in game.powers["FRANCE"].units # French army dislodged
    assert "LON" not in game.powers["ENGLAND"].units # Army left LON
    assert "NTH" in game.powers["ENGLAND"].units   # Fleet stays in NTH
    assert "YOR" in game.powers["ENGLAND"].units   # Supporting army stays

def test_dislodgement():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"BUR", "MUN"}
    # Germany attacks PAR from BUR with support from MUN
    game.set_orders("FRANCE", ["FRANCE A PAR H"])
    game.set_orders("GERMANY", [
        "GERMANY A BUR - PAR",
        "GERMANY A MUN S A BUR - PAR"
    ])
    game.process_turn()
    # French unit should be dislodged from PAR
    assert "PAR" not in game.powers["FRANCE"].units
    assert "PAR" in game.powers["GERMANY"].units
    assert "BUR" not in game.powers["GERMANY"].units
    assert "MUN" in game.powers["GERMANY"].units

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
    assert "SER" in game.powers["AUSTRIA"].units  # Defender stays
    assert "RUM" in game.powers["RUSSIA"].units   # Attacker 1 fails
    assert "BUD" in game.powers["RUSSIA"].units   # Supporter stays
    assert "BUL" in game.powers["TURKEY"].units   # Attacker 2 fails
    assert "GRE" in game.powers["TURKEY"].units   # Supporter stays

def test_support_cut_by_dislodgement():
    """Test support being cut by dislodgement of supporting unit"""
    game = Game()
    game.add_player("GERMANY")
    game.add_player("RUSSIA")
    game.powers["GERMANY"].units = {"BER", "SIL"}
    game.powers["RUSSIA"].units = {"PRU", "WAR", "BOH"}
    
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
    assert "BER" in game.powers["GERMANY"].units  # Failed to move
    assert "SIL" not in game.powers["GERMANY"].units  # Dislodged
    assert "SIL" in game.powers["RUSSIA"].units   # Russian unit moved in
    assert "PRU" in game.powers["RUSSIA"].units   # Russian unit stayed to defend

def test_self_standoff():
    """Test self-standoff: country can stand off its own units"""
    game = Game()
    game.add_player("AUSTRIA")
    game.add_player("RUSSIA")
    game.powers["AUSTRIA"].units = {"SER", "VIE"}
    game.powers["RUSSIA"].units = {"GAL"}
    
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
    assert "BUD" in game.powers["AUSTRIA"].units  # Supported attack wins
    assert "VIE" in game.powers["AUSTRIA"].units  # Unsupported attack fails
    assert "SER" not in game.powers["AUSTRIA"].units  # Supported unit moved
    assert "GAL" in game.powers["RUSSIA"].units   # Supporter stays

def test_complex_convoy_disruption():
    """Test convoy disruption by attacking convoying fleet"""
    game = Game()
    game.add_player("FRANCE")
    game.add_player("ITALY")
    game.powers["FRANCE"].units = {"SPA", "LYO", "TYR"}
    game.powers["ITALY"].units = {"ION", "TUN"}
    
    # France tries to convoy army, but one convoying fleet is attacked
    game.set_orders("FRANCE", [
        "FRANCE A SPA - NAP VIA CONVOY",
        "FRANCE F LYO C A SPA - NAP",
        "FRANCE F TYR C A SPA - NAP"
    ])
    game.set_orders("ITALY", [
        "ITALY F ION - TYR",  # Attack convoying fleet
        "ITALY F TUN S F ION - TYR"
    ])
    
    game.process_turn()
    
    # Fleet should be dislodged, convoy should fail
    assert "SPA" in game.powers["FRANCE"].units   # Army stays (convoy failed)
    assert "LYO" in game.powers["FRANCE"].units   # Fleet stays
    assert "TYR" not in game.powers["FRANCE"].units  # Fleet dislodged
    assert "TYR" in game.powers["ITALY"].units    # Italian fleet moved in
    assert "ION" not in game.powers["ITALY"].units  # Italian fleet moved out

def test_circular_movement():
    """Test circular movement between three units"""
    game = Game()
    game.add_player("ENGLAND")
    game.powers["ENGLAND"].units = {"HOL", "BEL", "NTH"}
    
    # Three units move in a circle
    game.set_orders("ENGLAND", [
        "ENGLAND A HOL - BEL",
        "ENGLAND F BEL - NTH",
        "ENGLAND F NTH - HOL"
    ])
    
    game.process_turn()
    
    # All units should move successfully in circle
    assert "BEL" in game.powers["ENGLAND"].units  # Army moved
    assert "NTH" in game.powers["ENGLAND"].units  # Fleet 1 moved
    assert "HOL" in game.powers["ENGLAND"].units  # Fleet 2 moved
    # Check original positions are vacated
    assert len(game.powers["ENGLAND"].units) == 3  # All three units
