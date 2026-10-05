"""``fill_with_dummies``: make a test game's table full (BA6).

A turn is processed only when every power is seated or a dummy. Tests about
something else -- maps, history, notifications -- that seat one or two players
and then process call this first, so the game is the one a real creator would
have: the unseated powers left to civil disorder.
"""
from __future__ import annotations

from server.api.shared import db_service, game_service
from server.response_cache import invalidate_cache


def fill_with_dummies(game_id: str | int) -> list[str]:
    """Mark every power without a seat row a dummy; returns the dummy set.

    Goes through ``GameService.set_dummy``, which keeps one power for people.
    A game nobody has joined gets an empty seat row for its first free power -- the
    state of a game whose only player quit, which still counts as seated.
    """
    gid = str(game_id)
    row = db_service.get_game_by_game_id(gid)
    assert row is not None, f"game {gid} not found"
    seated = {str(p.power_name).upper() for p in db_service.get_players_by_game_id(int(row.id))}
    dummies = sorted(game_service.dummy_powers(gid))
    if not seated:
        first = min(set(game_service.map.home_centers) - set(dummies))
        db_service.create_player(int(row.id), first)
        seated = {first}
    for power in sorted(set(game_service.map.home_centers) - seated - set(dummies)):
        dummies = game_service.set_dummy(gid, power, True)
    invalidate_cache(f"games/{gid}")
    return dummies
