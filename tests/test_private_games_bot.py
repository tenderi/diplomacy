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


@pytest.fixture(autouse=True)
def _no_group(monkeypatch):
    """These games belong to no Telegram group (group rules: test_telegram_groups.py)."""
    async def open_to_all(*_a, **_kw):
        return True

    monkeypatch.setattr("server.telegram_bot.games.may_join", open_to_all)


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
    assert "You joined game 7 as FRANCE" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_post")
def test_no_password_sends_none_and_deletes_nothing(mock_post):
    mock_post.return_value = {"status": "ok"}
    update, context, message = _update(["7", "FRANCE"])
    asyncio.run(join(update, context))
    assert "join_password" not in mock_post.call_args[0][1]
    message.delete.assert_not_awaited()


@patch("server.telegram_bot.games.api_get")
def test_private_menu_offers_the_open_seats_and_asks_for_the_password_after(mock_get):
    mock_get.side_effect = lambda path: (
        {"private": True, "dummy_powers": ["TURKEY"]} if path.endswith("/state")
        else [{"power": "FRANCE", "user_id": 3}]
    )
    text, keyboard = _power_selection_prompt("7")
    assert "private" in text and "password" in text
    offered = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "join_game_7_ENGLAND" in offered
    assert "join_game_7_TURKEY" not in offered and "join_game_7_FRANCE" not in offered


def test_a_private_game_button_asks_for_the_password_then_joins_with_it():
    """Pressing "Join as ENGLAND" in a private game: the bot asks, the next
    message is the password -- deleted from the chat, sent with the join."""
    from server.telegram_bot import hub
    from server.telegram_bot.games import AWAITING, join_from_button

    context = Mock()
    context.user_data = {}
    query = Mock()
    query.from_user = Mock(id=12345, first_name="Pat", last_name=None, username="")
    query.edit_message_text = AsyncMock()
    with patch("server.telegram_bot.games.api_get", return_value={"private": True}):
        asyncio.run(join_from_button(query, context, "7", "ENGLAND"))
    assert "Send the password" in query.edit_message_text.call_args[0][0]
    assert context.user_data[AWAITING]["kind"] == "join_password"

    update, _ctx, message = _update([])
    update.effective_user = query.from_user
    message.text = "open sesame"
    update.effective_chat.send_message = AsyncMock()
    with patch("server.telegram_bot.games.api_post", return_value={"status": "ok"}) as post:
        assert asyncio.run(hub.handle_awaited_text(update, context)) is True
    assert post.call_args[0][1]["join_password"] == "open sesame"
    message.delete.assert_awaited_once()
    assert "You joined game 7 as ENGLAND" in update.effective_chat.send_message.call_args[0][0]
    assert AWAITING not in context.user_data
