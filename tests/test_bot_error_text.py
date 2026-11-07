"""CT1: an API error shown in chat goes out where Markdown can't reject it.

Under legacy ``parse_mode='Markdown'`` an unpaired ``_``, ``*`` or ``[`` in the
error text makes Telegram refuse the whole message, so the player got nothing.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import requests

from server.telegram_bot import hub
from server.telegram_bot.api_client import ApiError

pytestmark = pytest.mark.unit


def _error(detail: str) -> ApiError:
    response = requests.Response()
    response.status_code = 400
    return ApiError(detail, response=response)


def test_a_game_menu_that_fails_to_load_is_sent_as_plain_text() -> None:
    send = AsyncMock()
    with patch.object(hub, "resolve_game_and_power", side_effect=_error("no such game_id: 7_b")):
        asyncio.run(hub.show_hub(send, "4242", "7"))
    send.assert_awaited_once_with("Could not load game 7: no such game_id: 7_b", parse_mode=None)
