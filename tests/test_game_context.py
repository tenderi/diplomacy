"""Tests for ``server.telegram_bot.game_context``.

Covers ``resolve_game_and_power``'s zero/one/many-game resolution rules and
the ``GET /users/{id}/games`` response shape it depends on (a dict with a
``"games"`` list, not a bare list -- see
``src/server/api/routes/users.py::get_user_games``).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import requests

from server.telegram_bot.game_context import (
    GameContextError,
    fetch_user_games,
    resolve_game_and_power,
)

pytestmark = pytest.mark.unit


@patch("server.telegram_bot.game_context.api_get")
def test_fetch_user_games_returns_list_from_games_key(mock_get):
    mock_get.return_value = {"games": [{"game_id": 1, "power": "FRANCE"}]}
    games = fetch_user_games("42")
    assert games == [{"game_id": 1, "power": "FRANCE"}]
    mock_get.assert_called_once_with("/users/42/games")


@patch("server.telegram_bot.game_context.api_get")
def test_fetch_user_games_404_is_zero_games(mock_get):
    resp = requests.Response()
    resp.status_code = 404
    mock_get.side_effect = requests.exceptions.HTTPError(response=resp)
    assert fetch_user_games("42") == []


@patch("server.telegram_bot.game_context.api_get")
def test_fetch_user_games_non_404_http_error_propagates(mock_get):
    resp = requests.Response()
    resp.status_code = 500
    mock_get.side_effect = requests.exceptions.HTTPError(response=resp)
    with pytest.raises(requests.exceptions.HTTPError):
        fetch_user_games("42")


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_zero_games_raises(mock_get):
    mock_get.return_value = {"games": []}
    with pytest.raises(GameContextError) as exc_info:
        resolve_game_and_power("42")
    assert "not in any games" in exc_info.value.message


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_exactly_one_game_returns_it(mock_get):
    mock_get.return_value = {"games": [{"game_id": 7, "power": "ITALY"}]}
    game_id, power = resolve_game_and_power("42")
    assert game_id == "7"
    assert power == "ITALY"


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_multiple_games_without_game_id_raises(mock_get):
    mock_get.return_value = {
        "games": [
            {"game_id": 1, "power": "FRANCE"},
            {"game_id": 2, "power": "GERMANY"},
        ]
    }
    with pytest.raises(GameContextError) as exc_info:
        resolve_game_and_power("42")
    assert "2 games" in exc_info.value.message
    assert "Game 1" in exc_info.value.message
    assert "Game 2" in exc_info.value.message


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_multiple_games_with_explicit_game_id(mock_get):
    """A game_id disambiguates even with several games in flight."""
    mock_get.return_value = {
        "games": [
            {"game_id": 1, "power": "FRANCE"},
            {"game_id": 2, "power": "GERMANY"},
        ]
    }
    game_id, power = resolve_game_and_power("42", "2")
    assert game_id == "2"
    assert power == "GERMANY"


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_explicit_game_id_not_a_player_raises(mock_get):
    mock_get.return_value = {"games": [{"game_id": 1, "power": "FRANCE"}]}
    with pytest.raises(GameContextError) as exc_info:
        resolve_game_and_power("42", "99")
    assert "not in game 99" in exc_info.value.message


@patch("server.telegram_bot.game_context.api_get")
def test_resolve_game_id_matches_regardless_of_type(mock_get):
    """game_id comparison is string-based -- an int arg matches a str stored id and vice versa."""
    mock_get.return_value = {"games": [{"game_id": 7, "power": "ITALY"}]}
    game_id, power = resolve_game_and_power("42", 7)  # type: ignore[arg-type]
    assert game_id == "7"
    assert power == "ITALY"
