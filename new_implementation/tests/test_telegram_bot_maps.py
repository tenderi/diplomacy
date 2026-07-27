"""Tests for the rewritten ``telegram_bot/maps.py``.

The bot must never import or call ``rendering.map.Map`` -- every map image it
shows is fetched as PNG bytes from the API (``api_client.api_get_bytes``),
which does the SVG->PNG rendering server-side. See the "PR 4" section of
``docs/specs/fix_plan.md``: the pre-rewrite bot called ``Map.render_board_png``
directly in five places, including one (``/replay``) that crashed outright
because the renderer's expected ``{power: [...]}`` unit shape no longer
matched the new engine's view.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.maps import map_command, replay, send_game_map
from rendering.map import Map

pytestmark = pytest.mark.unit


def _make_message_update(args: list[str]):
    update = Mock()
    context = Mock()
    context.args = args

    message = Mock()
    message.reply_text = AsyncMock()
    message.reply_photo = AsyncMock()
    user = Mock()
    user.id = 12345

    update.effective_user = user
    update.message = message
    update.callback_query = None
    return update, context, message


@patch("server.telegram_bot.maps.api_get_bytes")
def test_send_game_map_fetches_bytes_from_api(mock_get_bytes):
    """``send_game_map`` fetches ``GET /games/{id}/map`` bytes and posts them --
    it never touches the renderer."""
    mock_get_bytes.return_value = b"fake-png-bytes"
    update, context, message = _make_message_update([])

    asyncio.run(send_game_map(update, context, "42"))

    mock_get_bytes.assert_called_once_with("/games/42/map")
    message.reply_photo.assert_called_once()
    kwargs = message.reply_photo.call_args.kwargs
    assert kwargs["photo"].read() == b"fake-png-bytes"


@patch("server.telegram_bot.maps.api_get_bytes")
def test_map_command_delegates_to_send_game_map(mock_get_bytes):
    mock_get_bytes.return_value = b"fake-png-bytes"
    update, context, message = _make_message_update(["42"])

    asyncio.run(map_command(update, context))

    mock_get_bytes.assert_called_once_with("/games/42/map")
    message.reply_photo.assert_called_once()


@patch("server.telegram_bot.maps.api_get_bytes")
def test_map_command_requires_game_id_arg(mock_get_bytes):
    update, context, message = _make_message_update([])

    asyncio.run(map_command(update, context))

    mock_get_bytes.assert_not_called()
    message.reply_text.assert_called_once()
    assert "Usage" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.maps.api_get_bytes")
def test_replay_fetches_history_endpoint(mock_get_bytes):
    """``/replay`` used to crash with ``'list' object has no attribute 'items'``
    because the renderer wanted ``{power: [...]}`` and the new view's ``units``
    is a list of dicts. Fetching bytes removes that conversion from the bot
    entirely -- the server does it in ``rendering.view_adapter``."""
    mock_get_bytes.return_value = b"fake-png-bytes"
    update, context, message = _make_message_update(["42", "3"])

    asyncio.run(replay(update, context))

    mock_get_bytes.assert_called_once_with("/games/42/map/history/3")
    message.reply_photo.assert_called_once()


@patch("server.telegram_bot.maps.api_get_bytes")
def test_replay_requires_two_args(mock_get_bytes):
    update, context, message = _make_message_update(["42"])

    asyncio.run(replay(update, context))

    mock_get_bytes.assert_not_called()
    message.reply_text.assert_called_once()
    assert "Usage" in message.reply_text.call_args[0][0]


@patch("server.telegram_bot.maps.api_get_bytes")
def test_render_board_png_never_called_from_bot_for_a_game_map(mock_get_bytes):
    """The bot is a thin client over the HTTP API: rendering a game map must
    never invoke ``rendering.map.Map.render_board_png`` from bot code -- all
    three PNG-producing commands (``/map``, ``/viewmap`` -> ``send_game_map``,
    ``/replay``) go through ``api_get_bytes`` instead."""
    mock_get_bytes.return_value = b"fake-png-bytes"

    with patch.object(Map, "render_board_png") as mock_render:
        asyncio.run(send_game_map(*_make_message_update([])[:2], "42"))
        update, context, _ = _make_message_update(["42"])
        asyncio.run(map_command(update, context))
        update, context, _ = _make_message_update(["42", "3"])
        asyncio.run(replay(update, context))

        mock_render.assert_not_called()
