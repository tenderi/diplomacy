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
