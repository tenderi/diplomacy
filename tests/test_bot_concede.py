"""``/concede`` and the game menu's Concede button: a confirm step, then
``POST /games/{id}/concede``; the API's refusal is shown as worded."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from server.telegram_bot import hub
from server.telegram_bot.api_client import ApiError, ApiUnreachableError

pytestmark = pytest.mark.unit

ME = 4242
ONE_GAME = {"games": [{"game_id": "7", "power": "FRANCE"}]}


def _command(args: list[str] | None = None) -> tuple[Mock, Mock]:
    update, context = Mock(), Mock()
    update.effective_user = Mock(id=ME)
    update.message.reply_text = AsyncMock()
    context.args = args
    return update, context


def _conflict(detail: str) -> ApiError:
    response = requests.Response()
    response.status_code = 409
    response._content = f'{{"detail": "{detail}"}}'.encode()
    return ApiError(detail, response=response)


def test_concede_command_asks_first_and_posts_nothing() -> None:
    update, context = _command([])
    with patch("server.telegram_bot.game_context.api_get", return_value=ONE_GAME), \
            patch.object(hub, "api_post") as post:
        asyncio.run(hub.concede(update, context))
    post.assert_not_called()
    args, kwargs = update.message.reply_text.call_args
    assert args[0] == (
        "Concede game 7 as FRANCE? Your units are removed from the board and you "
        "FRANCE is out of the game; the others play on. This cannot be undone."
    )
    buttons = [(b.text, b.callback_data) for row in kwargs["reply_markup"].inline_keyboard for b in row]
    assert buttons == [("🏳️ Yes, concede", "g|7|cdok"), ("No, keep playing", "g|7|hub")]


def test_concede_without_a_game_says_so() -> None:
    update, context = _command([])
    with patch("server.telegram_bot.game_context.api_get", return_value={"games": []}):
        asyncio.run(hub.concede(update, context))
    assert update.message.reply_text.call_args[0][0] == "❌ You're not in any games!\n\n💡 Find one with /findgame, or try a demo from /start."


def test_confirmed_concede_posts_and_reports() -> None:
    with patch.object(hub, "api_post", return_value={"status": "ok"}) as post:
        text = hub.concede_game("7", "FRANCE", str(ME))
    post.assert_called_once_with("/games/7/concede", {"power": "FRANCE", "telegram_id": str(ME)})
    assert text == "🏳️ You have conceded game 7. FRANCE's units are removed; the others play on."


def test_concede_that_processes_the_turn_says_so() -> None:
    with patch.object(hub, "api_post", return_value={"status": "ok", "auto_processed": True}):
        text = hub.concede_game("7", "FRANCE", str(ME))
    assert text.endswith(" Your seat was the last hold-up, so the turn has been processed.")


def test_a_409_shows_the_apis_detail() -> None:
    with patch.object(hub, "api_post", side_effect=_conflict("FRANCE has already conceded")):
        assert hub.concede_game("7", "FRANCE", str(ME)) == "Could not concede game 7: FRANCE has already conceded"


def test_unreachable_api_is_reported_not_queued() -> None:
    with patch.object(hub, "api_post", side_effect=ApiUnreachableError(requests.ConnectionError("x"))):
        assert hub.concede_game("7", "FRANCE", str(ME)).startswith("Could not concede game 7: ")


def test_hub_keyboard_has_a_concede_button() -> None:
    markup: Any = hub._hub_keyboard("7", "FRANCE", {"status": "ACTIVE"}, None, False)
    data = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "g|7|cd" in data
