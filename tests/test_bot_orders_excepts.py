"""BF4: the order commands catch only what can really happen (a transport or HTTP
failure, a Telegram failure), and still answer the player in words."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from telegram.error import TelegramError

from server.telegram_bot import orders as bot_orders
from server.telegram_bot.api_client import ApiUnreachableError
from tests.test_bot_commands import ME, MY_GAMES, _command, _run

pytestmark = pytest.mark.unit

DOWN = ApiUnreachableError("connection refused")


def test_myorders_resolve_outage_reply() -> None:
    with patch("server.telegram_bot.game_context.api_get", side_effect=DOWN):
        reply = _run(bot_orders.myorders, *_command())
    assert reply == f"Error retrieving orders: {DOWN}"


def test_myorders_programming_bug_is_not_swallowed() -> None:
    with patch("server.telegram_bot.orders.resolve_game_and_power", side_effect=KeyError("power")):
        with pytest.raises(KeyError):
            _run(bot_orders.myorders, *_command())


def test_processturn_orders_status_outage_falls_back_to_processing() -> None:
    with patch("server.telegram_bot.game_context.api_get", return_value=MY_GAMES), \
         patch("server.telegram_bot.orders.api_get", side_effect=DOWN), \
         patch("server.telegram_bot.orders.api_post", side_effect=DOWN):
        reply = _run(bot_orders.processturn, *_command(args=["7"]))
    assert reply == f"❌ Process turn error: {DOWN}"


def test_run_process_turn_state_outage_still_confirms() -> None:
    sent: list[str] = []

    async def send(text: str, **_: object) -> None:
        sent.append(text)

    with patch("server.telegram_bot.orders.api_post", return_value={"status": "ok"}), \
         patch("server.telegram_bot.orders.api_get", side_effect=DOWN):
        asyncio.run(bot_orders.run_process_turn(send, "7", str(ME)))
    assert sent == ["✅ Turn processed successfully!"]


def test_viewmap_telegram_failure_replies() -> None:
    update, context = _command(args=["7"])
    with patch("server.telegram_bot.game_context.api_get", return_value=MY_GAMES), \
         patch("server.telegram_bot.maps.send_game_map", AsyncMock(side_effect=TelegramError("boom"))):
        reply = _run(bot_orders.viewmap, update, context)
    assert reply == "View map error: boom"


def test_viewmap_programming_bug_is_not_swallowed() -> None:
    update, context = _command(args=["7"])
    with patch("server.telegram_bot.game_context.api_get", return_value=MY_GAMES), \
         patch("server.telegram_bot.maps.send_game_map", AsyncMock(side_effect=KeyError("x"))):
        with pytest.raises(KeyError):
            _run(bot_orders.viewmap, update, context)
