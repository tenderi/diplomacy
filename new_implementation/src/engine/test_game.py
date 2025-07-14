import importlib.util
import os
spec = importlib.util.spec_from_file_location("game", os.path.join(os.path.dirname(__file__), "game.py"))
if spec is None or spec.loader is None:
    raise ImportError("Could not load game module for testing.")
game_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game_module)
Game = game_module.Game

def test_game_instantiation():
    game = Game()
    assert game is not None
