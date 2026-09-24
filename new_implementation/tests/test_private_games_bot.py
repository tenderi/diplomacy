"""W8 in the bot: /join with a password, the private-game join menu, the lock icon.

Thin-client tests: every HTTP call is mocked (see test_deadline_command.py).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.error import BadRequest

from server.telegram_bot.games import _power_selection_prompt, join

pytestmark = pytest.mark.unit


def _update(args: list[str]):
    update, context, message = Mock(), Mock(), Mock()
    message.reply_text = AsyncMock()
    message.delete = AsyncMock()
    update.effective_user = Mock(id=12345)
    update.message = message
    context.args = args
    return update, context, message


@patch("server.telegram_bot.games.api_post")
def test_join_sends_the_password_and_deletes_the_message(mock_post):
    mock_post.return_value = {"status": "ok"}
    update, context, message = _update(["7", "france", "open", "sesame"])
    asyncio.run(join(update, context))
    body = mock_post.call_args[0][1]
    assert body["power"] == "FRANCE" and body["join_password"] == "open sesame"
    message.delete.assert_awaited_once()


@patch("server.telegram_bot.games.api_post")
def test_a_message_that_cannot_be_deleted_still_joins(mock_post):
    mock_post.return_value = {"status": "ok"}
    update, context, message = _update(["7", "FRANCE", "pw12"])
    message.delete.side_effect = BadRequest("Message can't be deleted")
    asyncio.run(join(update, context))
    assert "Successfully joined" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_post")
def test_no_password_sends_none_and_deletes_nothing(mock_post):
    mock_post.return_value = {"status": "ok"}
    update, context, message = _update(["7", "FRANCE"])
    asyncio.run(join(update, context))
    assert "join_password" not in mock_post.call_args[0][1]
    message.delete.assert_not_awaited()


@patch("server.telegram_bot.games.api_get")
def test_private_menu_explains_instead_of_offering_buttons(mock_get):
    mock_get.side_effect = lambda path: (
        {"private": True, "dummy_powers": ["TURKEY"]} if path.endswith("/state")
        else [{"power": "FRANCE", "user_id": 3}]
    )
    text, keyboard = _power_selection_prompt("7")
    assert keyboard is None
    assert "private" in text and "/join 7 <POWER> <password>" in text
    assert "TURKEY" not in text and "FRANCE" not in text.split("Open seats:")[1].split(".")[0]
