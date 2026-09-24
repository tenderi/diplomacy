"""Rendering layer: the SVG→PNG board pipeline (``map``) and its style config
(``visualization_config``). Moved out of ``engine`` in M6 so the engine package
stays pure rules-logic; rendering consumes the new engine's ``GameState`` view.
"""
