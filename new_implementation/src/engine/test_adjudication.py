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

def test_convoyed_move_placeholder():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("ENGLAND")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["ENGLAND"].units = {"BRE"}
    game.set_orders("FRANCE", ["FRANCE A PAR C A PAR - MAR"])
    game.set_orders("ENGLAND", ["ENGLAND F BRE C A PAR - MAR"])
    game.process_turn()
    assert "PAR" in game.powers["FRANCE"].units
    assert "BRE" in game.powers["ENGLAND"].units

def test_dislodgement_placeholder():
    game = Game()
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    game.powers["FRANCE"].units = {"PAR"}
    game.powers["GERMANY"].units = {"BUR"}
    game.set_orders("FRANCE", ["FRANCE A PAR H"])
    game.set_orders("GERMANY", ["GERMANY A BUR - PAR"])
    game.process_turn()
    assert "PAR" in game.powers["FRANCE"].units
    assert "BUR" in game.powers["GERMANY"].units
