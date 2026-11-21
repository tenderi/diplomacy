"""DU4: bot wording nits from the 2026-11-21 play-through."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot import help_text, maps as bot_maps, orders as bot_orders

pytestmark = pytest.mark.unit


def _command(args: list[str]) -> tuple[Mock, Mock]:
    update, context = Mock(), Mock()
    update.effective_user = Mock(id=5)
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    update.callback_query = None
    update.effective_chat = Mock(type="private")
    context.args = args
    return update, context


def test_a_bare_map_uses_the_current_game() -> None:
    update, context = _command([])
    with patch("server.telegram_bot.game_context.api_get", return_value={"games": [{"game_id": "7", "power": "FRANCE"}]}), \
         patch.object(bot_maps, "api_get_bytes", return_value=b"png") as get:
        asyncio.run(bot_maps.map_command(update, context))
    get.assert_called_once_with("/games/7/map")
    assert update.message.reply_photo.call_args.kwargs["caption"] == "🗺️ *Game 7 Map*"


def test_a_bare_orders_points_to_myorders() -> None:
    update, context = _command([])
    asyncio.run(bot_orders.orders(update, context))
    assert "To list the orders you have given so far, use /myorders." in update.message.reply_text.call_args[0][0]


def test_via_shows_as_via_convoy_in_the_echo_and_myorders() -> None:
    results = [{"success": True, "order": "A SMY - ARM VIA", "stored": "A SMY - ARM VIA"}]
    assert bot_orders.format_order_results(results) == "✅ A SMY - ARM VIA CONVOY"
    done = [{"success": True, "order": "A SMY - ARM VIA CONVOY", "stored": "A SMY - ARM VIA CONVOY"}]
    assert bot_orders.format_order_results(done) == "✅ A SMY - ARM VIA CONVOY"
    with patch.object(bot_orders, "api_get", return_value={"orders": ["A SMY - ARM VIA"]}):
        assert bot_orders.my_orders_text("7", "TURKEY", "5") == "Your orders in game 7 (TURKEY):\nA SMY - ARM VIA CONVOY"


def test_parse_errors_read_as_a_sentence() -> None:
    results: list[dict[str, Any]] = [
        {"success": False, "order": "GIBBERISH", "error": "parse error: expected unit kind 'A' or 'F', got 'GIBBERISH'"}
    ]
    assert bot_orders.format_order_results(results) == (
        "❌ GIBBERISH\n   Error: Couldn't read that order: expected unit kind 'A' or 'F', got 'GIBBERISH'. "
        "Example: A PAR - BUR"
    )


def test_replay_caption_names_the_phase() -> None:
    update, context = _command(["1", "1"])

    def fake(endpoint: str, headers_out: dict[str, str] | None = None) -> bytes:
        assert headers_out is not None
        headers_out["X-Phase-Code"] = "F1901M"
        return b"png"

    with patch.object(bot_maps, "api_get_bytes", side_effect=fake):
        asyncio.run(bot_maps.replay(update, context))
    assert update.message.reply_photo.call_args.kwargs["caption"] == "Board for game 1, turn 1 (F1901M)"


def test_help_lists_replay() -> None:
    assert "`/replay <game_id> <turn>`" in help_text.HELP_TEXT
