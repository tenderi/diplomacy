from .game import Game

def test_game_instantiation():
    game = Game()
    assert game is not None

def test_victory_condition_standard_map():
    from .game import Game
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
    game.powers['FRANCE'].units = {f'A {prov}' for prov in france_centers}
    game.powers['GERMANY'].units = {f'A {prov}' for prov in germany_centers}
    # Simulate adjustment phase (should trigger victory)
    game._process_adjustment_phase()
    state = game.get_state()
    assert state['done']
    assert 'FRANCE' in state['winner']
