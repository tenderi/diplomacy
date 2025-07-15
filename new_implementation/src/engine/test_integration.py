"""
Integration tests for Diplomacy Python implementation.
Covers map variants, edge cases, and server/client integration.
"""
from .game import Game


def test_variant_map_loading_and_play():
    # Load mini variant by name
    game = Game(map_name="mini_variant")
    game.add_player("RED")
    game.add_player("BLUE")
    # Place units for both powers in adjacent provinces
    game.powers["RED"].units = {"A PAR", "A MAR"}  # Add supporting unit
    game.powers["BLUE"].units = {"A BUR"}
    # RED attacks with support, BLUE holds
    game.set_orders("RED", [
        "RED A PAR - BUR",
        "RED A MAR S A PAR - BUR"  # Support the attack
    ])
    game.set_orders("BLUE", ["BLUE A BUR H"])
    game.process_phase()
    # RED should succeed in attacking BLUE with support (strength 2 vs 1)
    assert "A BUR" in game.powers["RED"].units  # RED took BUR
    assert "A PAR" not in game.powers["RED"].units  # RED no longer at PAR
    assert "A BUR" not in game.powers["BLUE"].units  # BLUE was dislodged
    assert "A MAR" in game.powers["RED"].units  # Supporting unit stays


def test_self_dislodgement_multi_power():
    # Standard map, two powers, supported attack should succeed
    game = Game(map_name="standard")
    game.add_player("FRANCE")
    game.add_player("ENGLAND")
    game.powers["FRANCE"].units = {"A PAR", "A MAR"}
    game.powers["ENGLAND"].units = {"A BUR"}
    # France attacks with support, England holds
    game.set_orders("FRANCE", [
        "FRANCE A PAR - BUR",
        "FRANCE A MAR S A PAR - BUR"
    ])
    game.set_orders("ENGLAND", ["ENGLAND A BUR H"])
    game.process_phase()
    # France should succeed (strength 2 vs 1)
    assert "A BUR" in game.powers["FRANCE"].units  # France moved to BUR
    assert "A PAR" not in game.powers["FRANCE"].units  # France left PAR
    assert "A BUR" not in game.powers["ENGLAND"].units  # England was dislodged
    assert "A MAR" in game.powers["FRANCE"].units  # Supporting unit stays
    
    # Now, test self-dislodgement: France tries to dislodge its own unit (should fail)
    game.powers["FRANCE"].units = {"A PAR", "A BUR"}
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR", "FRANCE A BUR H"])
    game.set_orders("ENGLAND", [])
    game.process_phase()
    # Self-dislodgement should be prohibited - both units should remain
    assert "A PAR" in game.powers["FRANCE"].units
    assert "A BUR" in game.powers["FRANCE"].units


def test_order_validation_edge_cases():
    game = Game(map_name="standard")
    game.add_player("GERMANY")
    game.powers["GERMANY"].units = {"A MUN"}
    # Invalid order: move to non-adjacent (should be ignored, unit stays in place)
    game.set_orders("GERMANY", ["GERMANY A MUN - PAR"])
    game.process_phase()
    assert "A MUN" in game.powers["GERMANY"].units
    # Valid order
    game.set_orders("GERMANY", ["GERMANY A MUN H"])
    game.process_phase()
    assert "A MUN" in game.powers["GERMANY"].units

# DAIDE protocol and server/client integration tests would go in test_server.py or test_client.py
# For brevity, not included here, but should be expanded in those files.
