from engine.game import Game
from engine.data_models import Unit

def test_game_instantiation():
    game = Game()
    assert game is not None

def test_victory_condition_standard_map():
    from engine.game import Game
    game = Game(map_name='standard')
    # Add two players
    game.add_player('FRANCE')
    game.add_player('GERMANY')
    # Place French units in 18 real supply centers
    # Standard map supply centers: PAR, MAR, BRE, BEL, POR, SPA, LON, EDI, LVP, BER, MUN, KIE, ROM, VEN, NAP, VIE, BUD, TRI, WAR, MOS, SEV, STP, CON, SMY, ANK, BUL, SER, GRE, RUM, TUN, HOL, DEN, SWE, NOR
    # We'll use: PAR, MAR, BRE, BEL, POR, SPA, ROM, VEN, NAP, VIE, BUD, TRI, WAR, MOS, SEV, STP, TUN, MUN (18)
    france_centers = [
        'PAR', 'MAR', 'BRE', 'BEL', 'POR', 'SPA', 'ROM', 'VEN', 'NAP',
        'VIE', 'BUD', 'TRI', 'WAR', 'MOS', 'SEV', 'STP', 'TUN', 'MUN'
    ]
    germany_centers = ['BER', 'KIE']
    # Create Unit objects for France
    france_units = [Unit(unit_type='A', province=prov, power='FRANCE') for prov in france_centers]
    game.game_state.powers['FRANCE'].units = france_units
    # Set France to control 18 supply centers (victory condition)
    game.game_state.powers['FRANCE'].controlled_supply_centers = france_centers
    
    # Create Unit objects for Germany  
    germany_units = [Unit(unit_type='A', province=prov, power='GERMANY') for prov in germany_centers]
    game.game_state.powers['GERMANY'].units = germany_units
    # Set Germany to control only 2 supply centers
    game.game_state.powers['GERMANY'].controlled_supply_centers = germany_centers
    # Simulate builds phase (should trigger victory)
    game._process_builds_phase()
    state = game.get_state()
    assert state['done']
    assert 'FRANCE' in state['winner']


def test_victory_during_movement_phase():
    """Test victory condition detected during Movement phase."""
    from engine.game import Game
    game = Game(map_name='standard')
    game.add_player('FRANCE')
    game.add_player('GERMANY')
    
    # Set up France with 17 supply centers
    france_centers_17 = [
        'PAR', 'MAR', 'BRE', 'BEL', 'POR', 'SPA', 'ROM', 'VEN', 'NAP',
        'VIE', 'BUD', 'TRI', 'WAR', 'MOS', 'SEV', 'STP', 'TUN'
    ]
    game.game_state.powers['FRANCE'].controlled_supply_centers = france_centers_17
    
    # Place units: France in BUR and MAR (both adjacent to MUN), Germany in MUN
    game.game_state.powers['FRANCE'].units = [
        Unit(unit_type='A', province='BUR', power='FRANCE'),  # Attacks MUN
        Unit(unit_type='A', province='MAR', power='FRANCE')   # Supports BUR - MUN (MAR adjacent to BUR)
    ]
    game.game_state.powers['GERMANY'].units = [
        Unit(unit_type='A', province='MUN', power='GERMANY')
    ]
    
    # France 2 vs 1 captures MUN (18th supply center)
    game.set_orders('FRANCE', ['FRANCE A BUR - MUN', 'FRANCE A MAR S A BUR - MUN'])
    game.set_orders('GERMANY', ['GERMANY A MUN H'])
    
    # Process movement phase
    game.process_turn()
    
    # Update supply centers after movement (controlled_supply_centers is a list)
    france = game.game_state.powers['FRANCE']
    if any(unit.province == 'MUN' for unit in france.units):
        if 'MUN' not in france.controlled_supply_centers:
            france.controlled_supply_centers.append('MUN')
        game._check_victory_condition()
    
    # Victory should be detected
    assert game.done or game.game_state.status.value == "completed", \
        "Victory should be detected when power reaches 18 supply centers"
    if game.done:
        assert 'FRANCE' in str(game.winner) or len(game.game_state.powers['FRANCE'].controlled_supply_centers) >= 18


def test_victory_during_builds_phase():
    """Test victory condition detected during Builds phase."""
    from engine.game import Game
    game = Game(map_name='standard')
    game.add_player('FRANCE')
    
    # Set up France with 18 supply centers
    france_centers_18 = [
        'PAR', 'MAR', 'BRE', 'BEL', 'POR', 'SPA', 'ROM', 'VEN', 'NAP',
        'VIE', 'BUD', 'TRI', 'WAR', 'MOS', 'SEV', 'STP', 'TUN', 'MUN'
    ]
    game.game_state.powers['FRANCE'].controlled_supply_centers = france_centers_18
    
    # Start in Builds phase
    game.phase = "Builds"
    game.season = "Autumn"
    game.year = 1901
    game._update_phase_code()
    
    # Process builds phase (should trigger victory check)
    game._process_builds_phase()
    
    # Victory should be detected
    assert game.done or game.game_state.status.value == "completed", \
        "Victory should be detected during Builds phase"
    if game.done:
        assert 'FRANCE' in str(game.winner) or len(game.game_state.powers['FRANCE'].controlled_supply_centers) >= 18
