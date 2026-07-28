"""Game/power resolution shared by Telegram bot command handlers.

Almost every interactive command needs to answer "which game, and which
power in it, is this Telegram user acting for?" before it can call into the
HTTP API. That lookup used to be reimplemented inline at ~19 call sites
across ``orders.py``, ``games.py``, ``ui.py``, ``messages.py``, and
``channel_commands.py`` -- copy-pasted, and in three spots (``orders.py``
``/myorders``, ``/clearorders``, ``/orderhistory``) pointed at the wrong,
dead endpoint (``GET /users/{id}``, which reads the in-memory
``user_sessions`` dict that is only ever populated by ``POST
/users/register``, a route the bot never calls -- so it always 404s). This
module is the single place that logic lives now.
"""
from __future__ import annotations

from typing import Any, Optional

import requests

from .api_client import api_get

__all__ = ["GameContextError", "fetch_user_games", "resolve_game_and_power"]


class GameContextError(Exception):
    """A game/power could not be resolved for a user.

    ``message`` is a ready-to-send, user-facing string (already formatted
    consistently with the rest of the bot's copy) -- callers can send it
    straight to ``reply_text``/``edit_message_text`` without further
    formatting.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def fetch_user_games(user_id: str) -> list[dict[str, Any]]:
    """The list of games ``user_id`` is an active player in.

    Wraps ``GET /users/{user_id}/games``, which returns a **dict** shaped
    ``{"games": [{"game_id", "map_name", "power", "current_turn", "status"},
    ...]}`` -- not a bare list (see
    ``src/server/api/routes/users.py::get_user_games`` /
    ``_user_games_response``). A 404 (no ``users`` row for this
    ``telegram_id`` yet) is treated as "zero games" rather than propagated,
    matching how several call sites already handled it ad hoc before this
    module existed.
    """
    try:
        response = api_get(f"/users/{user_id}/games")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return []
        raise
    return response.get("games", []) if response else []


def resolve_game_and_power(user_id: str, game_id: Optional[str] = None) -> tuple[str, str]:
    """Resolve the ``(game_id, power)`` a Telegram user is acting for.

    - ``game_id`` given: looks that specific game up among the user's games;
      raises ``GameContextError`` if the user is not a player in it.
    - ``game_id`` omitted and the user is in exactly **one** game: returns
      that game -- the common case for commands like ``/myorders`` and
      ``/selectunit`` that take no game id argument.
    - ``game_id`` omitted and the user is in **zero** games: raises
      ``GameContextError`` telling them to join a game first.
    - ``game_id`` omitted and the user is in **more than one** game: raises
      ``GameContextError`` listing the games and asking the caller to
      disambiguate by passing a game id explicitly (the same rule every
      converted call site already used).

    Every failure path raises rather than returning ``None``/``(None,
    None)``, so a call site can't forget to check a falsy result -- it
    either gets a valid pair back or a ``GameContextError`` whose
    ``.message`` is already suitable to display.
    """
    games = fetch_user_games(user_id)

    if game_id is not None:
        for g in games:
            if str(g["game_id"]) == str(game_id):
                return str(g["game_id"]), g["power"]
        raise GameContextError(f"You are not in game {game_id}.")

    if not games:
        raise GameContextError(
            "❌ You're not in any games!\n\n"
            "\U0001f4a1 Join a game first, then try this command again."
        )

    if len(games) > 1:
        listing = "\n".join(f"• Game {g['game_id']} as {g['power']}" for g in games)
        raise GameContextError(
            f"❌ You're in {len(games)} games. Please specify which game "
            f"by passing its id to this command.\n\nYour games:\n{listing}"
        )

    game = games[0]
    return str(game["game_id"]), game["power"]
