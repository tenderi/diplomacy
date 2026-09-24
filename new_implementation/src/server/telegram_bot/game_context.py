"""Game/power resolution shared by Telegram bot command handlers.

Almost every interactive command needs to answer "which game, and which
power in it, is this Telegram user acting for?" before it can call into the
HTTP API. That lookup used to be reimplemented inline at ~19 call sites
across ``orders.py``, ``games.py``, ``ui.py``, ``messages.py``, and
``channel_commands.py`` -- copy-pasted, and in three spots (``orders.py``
``/myorders``, ``/clearorders``, ``/orderhistory``) pointed at the wrong,
dead endpoint (``GET /users/{id}``, an in-memory session store the bot never
populated -- so it always 404'd; removed in Track T). This module is the
single place that logic lives now.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from .api_client import ApiUnreachableError, api_get
from .outbox import get_outbox

logger = logging.getLogger("diplomacy.telegram_bot.game_context")

__all__ = [
    "GameContextError", "current_game", "fetch_user_games", "resolve_game_and_power", "set_current_game",
]


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

    **Offline fallback.** Every successful answer is cached in the bot's
    local SQLite store. If the server is unreachable and a cached answer
    exists, the cache is returned instead of raising -- this is what lets
    ``/order A PAR - BUR`` resolve *which power you hold* and reach the
    durable queue while the API is down, rather than failing on the
    lookup before the order is ever queued. Only the ``(game_id, power)``
    pairs are load-bearing for that, and they change rarely. With no cache
    (a player the bot has never resolved before) the unreachable error is
    raised as usual.
    """
    try:
        response = api_get(f"/users/{user_id}/games")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return []
        raise
    except ApiUnreachableError:
        cached = get_outbox().cached_user_games(user_id)
        if cached is None:
            raise
        games, fetched_at = cached
        logger.info(
            "API unreachable; using cached games for user %s from %s", user_id, fetched_at.isoformat()
        )
        return games
    games = response.get("games", []) if response else []
    try:
        get_outbox().cache_user_games(user_id, games)
    except Exception as e:  # a cache write must never break a command
        logger.warning("Could not cache games for user %s: %s", user_id, e)
    return games


def set_current_game(user_id: str, game_id: str) -> None:
    """Remember ``game_id`` as the game ``user_id``'s bare commands act on.

    Stored in the bot's SQLite file, so it survives a restart. Best effort: a
    failed write only means the player names the game next time.
    """
    try:
        get_outbox().set_current_game(user_id, str(game_id))
    except Exception as e:  # a cache write must never break a command
        logger.warning("Could not remember current game for user %s: %s", user_id, e)


def current_game(user_id: str) -> Optional[str]:
    """The game ``user_id`` last opened, named, or was notified about, if any."""
    try:
        return get_outbox().current_game(user_id)
    except Exception as e:  # reading a convenience must never break a command
        logger.warning("Could not read current game for user %s: %s", user_id, e)
        return None


def resolve_game_and_power(user_id: str, game_id: Optional[str] = None) -> tuple[str, str]:
    """Resolve the ``(game_id, power)`` a Telegram user is acting for.

    - ``game_id`` given: looks that specific game up among the user's games
      and makes it the user's **current game**; raises ``GameContextError``
      if the user is not a player in it.
    - ``game_id`` omitted and the user is in exactly **one** game: that game.
    - ``game_id`` omitted and the user is in **more than one** game: the
      current game -- the one they last opened in the game menu, named in a
      command, or tapped a notification button for. Only with no current game
      (or one they have since left) does it raise, listing the games.
    - ``game_id`` omitted and the user is in **zero** games: raises
      ``GameContextError`` telling them to join a game first.

    Every failure path raises rather than returning ``None``/``(None,
    None)``, so a call site can't forget to check a falsy result -- it
    either gets a valid pair back or a ``GameContextError`` whose
    ``.message`` is already suitable to display.
    """
    games = fetch_user_games(user_id)

    if game_id is not None:
        for g in games:
            if str(g["game_id"]) == str(game_id):
                set_current_game(user_id, str(g["game_id"]))
                return str(g["game_id"]), g["power"]
        raise GameContextError(f"You are not in game {game_id}.")

    if not games:
        raise GameContextError(
            "❌ You're not in any games!\n\n"
            "\U0001f4a1 Find one with /findgame, or try a demo from /start."
        )

    if len(games) == 1:
        return str(games[0]["game_id"]), games[0]["power"]

    remembered = current_game(user_id)
    for g in games:
        if remembered is not None and str(g["game_id"]) == remembered:
            return str(g["game_id"]), g["power"]

    listing = "\n".join(f"• Game {g['game_id']} as {g['power']}" for g in games)
    raise GameContextError(
        f"❌ You're in {len(games)} games. Pick one with /game <id> (it stays picked), "
        f"or add the game id to this command.\n\nYour games:\n{listing}"
    )
