"""W10 in the bot: /autoprocess, /notready, /ready, and /status showing both.

Thin-client tests: every HTTP call is mocked (see test_deadline_command.py).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.games import autoprocess, notready, ready, status

pytestmark = pytest.mark.unit

_ONE_GAME = {"games": [{"game_id": "7", "power": "FRANCE"}]}


def _update(args: list[str] | None = None):
    update, context, message = Mock(), Mock(), Mock()
    message.reply_text = AsyncMock()
    update.effective_user = Mock(id=12345)
    update.message = message
    context.args = args
    return update, context, message


@patch("server.telegram_bot.games.api_post")
@patch("server.telegram_bot.game_context.api_get")
def test_notready_raises_this_powers_flag(mock_ctx_get, mock_post):
    mock_ctx_get.return_value = _ONE_GAME
    mock_post.return_value = {"status": "ok", "waiting": ["FRANCE"], "auto_processed": 0}
    update, context, message = _update([])
    asyncio.run(notready(update, context))
    mock_post.assert_called_once_with("/games/7/wait", {"power": "FRANCE", "waiting": True, "telegram_id": "12345"})
    assert "/ready" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_post")
@patch("server.telegram_bot.game_context.api_get")
def test_ready_that_unblocks_the_turn_says_so(mock_ctx_get, mock_post):
    mock_ctx_get.return_value = _ONE_GAME
    mock_post.return_value = {"status": "ok", "waiting": [], "auto_processed": 1}
    update, context, message = _update(["7"])
    asyncio.run(ready(update, context))
    assert mock_post.call_args[0][1]["waiting"] is False
    assert "has been processed" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_post")
def test_autoprocess_on(mock_post):
    mock_post.return_value = {"status": "ok", "auto_process": True, "auto_processed": 0}
    update, context, message = _update(["7", "ON"])
    asyncio.run(autoprocess(update, context))
    mock_post.assert_called_once_with("/games/7/auto_process", {"enabled": True, "telegram_id": "12345"})
    assert "as soon as all orders are in" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_post")
@pytest.mark.parametrize("args", [[], ["7"], ["7", "maybe"]])
def test_autoprocess_usage(mock_post, args):
    update, context, message = _update(args)
    asyncio.run(autoprocess(update, context))
    mock_post.assert_not_called()
    assert "Usage" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.games.api_get")
@patch("server.telegram_bot.game_context.api_get")
def test_status_shows_auto_processing_and_who_waits(mock_ctx_get, mock_get):
    mock_ctx_get.return_value = _ONE_GAME

    def fake_get(path, **_kw):
        if path.endswith("/orders_status"):
            return {"submitted": ["FRANCE"], "missing": [], "waiting": ["ENGLAND"], "auto_process": True}
        if path.endswith("/state"):
            return {"phase": "S1901M", "status": "ACTIVE", "players": {}, "units_by_power": {}}
        return {}

    mock_get.side_effect = fake_get
    update, context, message = _update(["7"])
    asyncio.run(status(update, context))
    text = message.reply_text.call_args[0][0]
    assert "automatically" in text and "ENGLAND" in text
