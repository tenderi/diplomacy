from src.engine.game import Game
from src.engine.data_models import Unit

def test_game_instantiation():
    game = Game()
    assert game is not None

def test_victory_condition_standard_map():
    from src.engine.game import Game
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
    state = game.get_game_state()
    assert state['done']
    assert 'FRANCE' in state['winner']
