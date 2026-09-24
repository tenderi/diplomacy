"""W9 in the bot: /dummy, and dummies kept out of the join menu and shown in /players.

Thin-client tests: every HTTP call is mocked (see test_deadline_command.py).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.games import _power_selection_prompt, dummy, players

pytestmark = pytest.mark.unit


def _update(args: list[str] | None = None):
    update, context, message = Mock(), Mock(), Mock()
    message.reply_text = AsyncMock()
    update.effective_user = Mock(id=12345)
    update.message = message
    context.args = args
    return update, context, message


class TestDummyCommand:
    @patch("server.telegram_bot.games.api_post")
    def test_marks_a_seat_as_dummy(self, mock_post):
        mock_post.return_value = {"status": "ok", "dummy_powers": ["ITALY"]}
        update, context, message = _update(["7", "italy"])
        asyncio.run(dummy(update, context))
        mock_post.assert_called_once_with("/games/7/dummies", {"power": "ITALY", "dummy": True, "telegram_id": "12345"})
        assert "ITALY is now played by civil disorder" in message.reply_text.call_args[0][0]

    @patch("server.telegram_bot.games.api_post")
    def test_off_reopens_it(self, mock_post):
        mock_post.return_value = {"status": "ok", "dummy_powers": []}
        update, context, message = _update(["7", "ITALY", "off"])
        asyncio.run(dummy(update, context))
        assert mock_post.call_args[0][1]["dummy"] is False
        assert "open for a player again" in message.reply_text.call_args[0][0]

    @patch("server.telegram_bot.games.api_post")
    @pytest.mark.parametrize("args", [[], ["7"], ["7", "ITALY", "maybe"], ["7", "ATLANTIS"]])
    def test_bad_arguments_never_reach_the_api(self, mock_post, args):
        update, context, message = _update(args)
        asyncio.run(dummy(update, context))
        mock_post.assert_not_called()
        message.reply_text.assert_called_once()


@patch("server.telegram_bot.games.api_get")
def test_join_menu_leaves_out_dummies(mock_get):
    mock_get.side_effect = lambda path: (
        {"dummy_powers": ["TURKEY"]} if path.endswith("/state")
        else [{"power": "FRANCE", "user_id": 3}]
    )
    _text, keyboard = _power_selection_prompt("7")
    offered = {row[0].callback_data for row in keyboard.inline_keyboard}
    assert "join_game_7_TURKEY" not in offered and "join_game_7_FRANCE" not in offered
    assert "join_game_7_ENGLAND" in offered


@patch("server.telegram_bot.games.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_players_lists_dummies_as_civil_disorder(mock_ctx_get, mock_get):
    mock_ctx_get.return_value = {"games": [{"game_id": "7", "power": "FRANCE"}]}
    mock_get.side_effect = lambda path: (
        {"dummy_powers": ["TURKEY"]} if path.endswith("/state")
        else [{"power": "FRANCE", "full_name": "Ann", "is_active": True}]
    )
    update, context, message = _update([])
    asyncio.run(players(update, context))
    text = message.reply_text.call_args[0][0]
    assert "TURKEY" in text and "civil disorder" in text
