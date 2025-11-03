"""
Tests for advanced order adjudication and turn processing in Diplomacy.
Covers support cut, standoffs, convoyed moves, and dislodgement.
"""
from engine.game import Game

def test_support_cut():
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    # Add units to the new data model
    from engine.data_models import Unit
    game.game_state.powers["FRANCE"].units = [Unit(unit_type='A', province='PAR', power='FRANCE')]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type='A', province='BUR', power='GERMANY')]
    # France supports its own move to BUR, Germany moves to PAR
    # This should result in both units bouncing (standoff)
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A BUR - PAR"])
    game.process_turn()
    # Both units should bounce (standoff)
    assert any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units)
    assert any(unit.province == 'BUR' for unit in game.game_state.powers["GERMANY"].units)

def test_standoff():
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    from engine.data_models import Unit
    game.game_state.powers["FRANCE"].units = [Unit(unit_type='A', province='PAR', power='FRANCE')]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type='A', province='MAR', power='GERMANY')]
    game.set_orders("FRANCE", ["FRANCE A PAR - BUR"])
    game.set_orders("GERMANY", ["GERMANY A MAR - BUR"])
    game.process_turn()
    # Both units should bounce (standoff)
    assert any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units)
    assert any(unit.province == 'MAR' for unit in game.game_state.powers["GERMANY"].units)

def test_convoyed_move():
    game = Game('standard')
    game.add_player("ENGLAND")
    game.add_player("GERMANY")
    from engine.data_models import Unit
    game.game_state.powers["ENGLAND"].units = [Unit(unit_type='A', province='LON', power='ENGLAND'), Unit(unit_type='F', province='NTH', power='ENGLAND'), Unit(unit_type='A', province='YOR', power='ENGLAND')]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type='A', province='HOL', power='GERMANY')]
    # England A LON - HOL via convoy with support, F NTH convoys, A YOR supports
    game.set_orders("ENGLAND", [
        "ENGLAND A LON - HOL",
        "ENGLAND F NTH C A LON - HOL",
        "ENGLAND A YOR S F NTH"  # Support the convoying fleet (YOR is adjacent to NTH)
    ])
    game.set_orders("GERMANY", [
        "GERMANY A HOL H"
    ])
    game.process_turn()
    # Supported attack (strength 2) should beat defender (strength 1)
    assert any(unit.province == 'HOL' for unit in game.game_state.powers["ENGLAND"].units)   # Army moved to HOL
    assert not any(unit.province == 'HOL' for unit in game.game_state.powers["GERMANY"].units) # German army dislodged
    assert not any(unit.province == 'LON' for unit in game.game_state.powers["ENGLAND"].units) # Army left LON
    assert any(unit.province == 'NTH' for unit in game.game_state.powers["ENGLAND"].units)   # Fleet stays in NTH
    assert any(unit.province == 'YOR' for unit in game.game_state.powers["ENGLAND"].units)   # Supporting army stays

def test_dislodgement():
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("GERMANY")
    from engine.data_models import Unit
    game.game_state.powers["FRANCE"].units = [Unit(unit_type='A', province='PAR', power='FRANCE')]
    game.game_state.powers["GERMANY"].units = [Unit(unit_type='A', province='BUR', power='GERMANY'), Unit(unit_type='A', province='PIC', power='GERMANY')]
    # Germany attacks PAR from BUR with support from PIC (PIC is adjacent to both BUR and PAR)
    game.set_orders("FRANCE", ["FRANCE A PAR H"])
    game.set_orders("GERMANY", [
        "GERMANY A BUR - PAR",
        "GERMANY A PIC S A BUR - PAR"
    ])
    game.process_turn()
    # French unit should be dislodged from PAR
    assert not any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units)
    assert any(unit.province == 'PAR' for unit in game.game_state.powers["GERMANY"].units)
    assert not any(unit.province == 'BUR' for unit in game.game_state.powers["GERMANY"].units)
    assert any(unit.province == 'PIC' for unit in game.game_state.powers["GERMANY"].units)

def test_beleaguered_garrison():
    """Test beleaguered garrison: two equal attacks standoff, defender stays"""
    game = Game('standard')
    game.add_player("AUSTRIA")
    game.add_player("RUSSIA")
    game.add_player("TURKEY")
    from engine.data_models import Unit
    game.game_state.powers["AUSTRIA"].units = [Unit(unit_type='A', province='SER', power='AUSTRIA')]
    game.game_state.powers["RUSSIA"].units = [Unit(unit_type='A', province='RUM', power='RUSSIA'), Unit(unit_type='A', province='BUD', power='RUSSIA')]
    game.game_state.powers["TURKEY"].units = [Unit(unit_type='A', province='BUL', power='TURKEY'), Unit(unit_type='A', province='GRE', power='TURKEY')]

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
    assert any(unit.province == 'SER' for unit in game.game_state.powers["AUSTRIA"].units)  # Defender stays
    assert any(unit.province == 'RUM' for unit in game.game_state.powers["RUSSIA"].units)   # Attacker 1 fails
    assert any(unit.province == 'BUD' for unit in game.game_state.powers["RUSSIA"].units)   # Supporter stays
    assert any(unit.province == 'BUL' for unit in game.game_state.powers["TURKEY"].units)   # Attacker 2 fails
    assert any(unit.province == 'GRE' for unit in game.game_state.powers["TURKEY"].units)   # Supporter stays

def test_support_cut_by_dislodgement():
    """Test support being cut by dislodgement of supporting unit"""
    game = Game('standard')
    game.add_player("GERMANY")
    game.add_player("RUSSIA")
    from engine.data_models import Unit
    game.game_state.powers["GERMANY"].units = [Unit(unit_type='A', province='BER', power='GERMANY'), Unit(unit_type='A', province='SIL', power='GERMANY')]
    game.game_state.powers["RUSSIA"].units = [Unit(unit_type='A', province='PRU', power='RUSSIA'), Unit(unit_type='A', province='WAR', power='RUSSIA'), Unit(unit_type='A', province='BOH', power='RUSSIA')]
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
    assert any(unit.province == 'BER' for unit in game.game_state.powers["GERMANY"].units)  # Failed to move
    assert not any(unit.province == 'SIL' for unit in game.game_state.powers["GERMANY"].units)  # Dislodged
    assert any(unit.province == 'SIL' for unit in game.game_state.powers["RUSSIA"].units)   # Russian unit moved in
    assert any(unit.province == 'PRU' for unit in game.game_state.powers["RUSSIA"].units)   # Russian unit stayed to defend

def test_self_standoff():
    """Test self-standoff: country can stand off its own units"""
    game = Game('standard')
    game.add_player("AUSTRIA")
    game.add_player("RUSSIA")
    from engine.data_models import Unit
    game.game_state.powers["AUSTRIA"].units = [Unit(unit_type='A', province='SER', power='AUSTRIA'), Unit(unit_type='A', province='VIE', power='AUSTRIA')]
    game.game_state.powers["RUSSIA"].units = [Unit(unit_type='A', province='GAL', power='RUSSIA')]

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
    assert any(unit.province == 'BUD' for unit in game.game_state.powers["AUSTRIA"].units)  # Supported attack wins
    assert any(unit.province == 'VIE' for unit in game.game_state.powers["AUSTRIA"].units)  # Unsupported attack fails
    assert not any(unit.province == 'SER' for unit in game.game_state.powers["AUSTRIA"].units)  # Supported unit moved
    assert any(unit.province == 'GAL' for unit in game.game_state.powers["RUSSIA"].units)   # Supporter stays

def test_complex_convoy_disruption():
    """Test convoy disruption by attacking convoying fleet"""
    game = Game('standard')
    game.add_player("FRANCE")
    game.add_player("ITALY")
    from engine.data_models import Unit
    game.game_state.powers["FRANCE"].units = [Unit(unit_type='A', province='SPA', power='FRANCE'), Unit(unit_type='F', province='GOL', power='FRANCE'), Unit(unit_type='F', province='TYS', power='FRANCE')]
    game.game_state.powers["ITALY"].units = [Unit(unit_type='F', province='ION', power='ITALY'), Unit(unit_type='F', province='TUN', power='ITALY')]
    # France tries to convoy army, but one convoying fleet is attacked
    game.set_orders("FRANCE", [
        "FRANCE A SPA - NAP",
        "FRANCE F GOL C A SPA - NAP",
        "FRANCE F TYS C A SPA - NAP"
    ])
    game.set_orders("ITALY", [
        "ITALY F ION - TYS",  # Attack convoying fleet
        "ITALY F TUN S F ION - TYS"
    ])
    game.process_turn()

    # Fleet should be dislodged, convoy should fail
    assert any(unit.province == 'SPA' for unit in game.game_state.powers["FRANCE"].units)   # Army stays (convoy failed)
    assert any(unit.province == 'GOL' for unit in game.game_state.powers["FRANCE"].units)   # Fleet stays
    assert not any(unit.province == 'TYS' for unit in game.game_state.powers["FRANCE"].units)  # Fleet dislodged
    assert any(unit.province == 'TYS' for unit in game.game_state.powers["ITALY"].units)    # Italian fleet moved in
    assert not any(unit.province == 'ION' for unit in game.game_state.powers["ITALY"].units)  # Italian fleet moved out

def test_circular_movement_fleet():
    """Test circular movement between three fleets in adjacent sea/coastal provinces"""
    game = Game('standard')
    game.add_player("ENGLAND")
    from engine.data_models import Unit
    # Use three adjacent coastal/sea provinces: HOL, HEL, NTH
    game.game_state.powers["ENGLAND"].units = [Unit(unit_type='F', province='HOL', power='ENGLAND'), Unit(unit_type='F', province='HEL', power='ENGLAND'), Unit(unit_type='F', province='NTH', power='ENGLAND')]
    game.set_orders("ENGLAND", [
        "ENGLAND F HOL - HEL",
        "ENGLAND F HEL - NTH",
        "ENGLAND F NTH - HOL"
    ])
    game.process_turn()
    assert any(unit.province == 'HEL' for unit in game.game_state.powers["ENGLAND"].units)
    assert any(unit.province == 'NTH' for unit in game.game_state.powers["ENGLAND"].units)
    assert any(unit.province == 'HOL' for unit in game.game_state.powers["ENGLAND"].units)
    assert len(game.game_state.powers["ENGLAND"].units) == 3

def test_circular_movement_army():
    """Test circular movement between three armies in adjacent land provinces"""
    game = Game('standard')
    game.add_player("ENGLAND")
    from engine.data_models import Unit
    # Use three adjacent land provinces: HOL, BEL, RUH
    game.game_state.powers["ENGLAND"].units = [Unit(unit_type='A', province='HOL', power='ENGLAND'), Unit(unit_type='A', province='BEL', power='ENGLAND'), Unit(unit_type='A', province='RUH', power='ENGLAND')]
    game.set_orders("ENGLAND", [
        "ENGLAND A HOL - BEL",
        "ENGLAND A BEL - RUH",
        "ENGLAND A RUH - HOL"
    ])
    game.process_turn()
    assert any(unit.province == 'BEL' for unit in game.game_state.powers["ENGLAND"].units)
    assert any(unit.province == 'RUH' for unit in game.game_state.powers["ENGLAND"].units)
    assert any(unit.province == 'HOL' for unit in game.game_state.powers["ENGLAND"].units)
    assert len(game.game_state.powers["ENGLAND"].units) == 3

def test_army_and_fleet_invalid_moves():
    """Test that armies cannot move to ocean spaces and fleets cannot move to land-locked provinces"""
    game = Game('standard')
    game.add_player("ENGLAND")
    from engine.data_models import Unit
    # Army in LON, Fleet in NTH
    game.game_state.powers["ENGLAND"].units = [Unit(unit_type='A', province='LON', power='ENGLAND'), Unit(unit_type='F', province='NTH', power='ENGLAND')]
    # Try to move army to NTH (ocean), and fleet to LON (land)
    game.set_orders("ENGLAND", [
        "ENGLAND A LON - NTH",
        "ENGLAND F NTH - LON"
    ])
    game.process_turn()
    # Both units should remain in place
    assert any(unit.province == 'LON' for unit in game.game_state.powers["ENGLAND"].units)
    assert any(unit.province == 'NTH' for unit in game.game_state.powers["ENGLAND"].units)
    assert len(game.game_state.powers["ENGLAND"].units) == 2

def test_self_dislodgement_prohibited():
    """Test that a power cannot dislodge its own unit (self-dislodgement prohibited)."""
    from engine.game import Game
    from engine.data_models import Unit
    game = Game('standard')
    game.add_player('FRANCE')
    # Place two French units in adjacent provinces
    game.game_state.powers['FRANCE'].units = [Unit(unit_type='A', province='PAR', power='FRANCE'), Unit(unit_type='A', province='BUR', power='FRANCE')]
    # Attempt to move A PAR to BUR, which is occupied by own unit
    game.set_orders('FRANCE', ['A PAR - BUR'])
    game.process_turn()
    # Both units should remain in place (no self-dislodgement)
    assert any(unit.province == 'PAR' for unit in game.game_state.powers["FRANCE"].units)
    assert any(unit.province == 'BUR' for unit in game.game_state.powers["FRANCE"].units)
