"""BF5: the bot's commands catch only what can really happen (a transport or HTTP
failure, a Telegram failure, a SQLite failure) and answer the player in words; a
programming bug propagates to ``_on_handler_error``; the background loops stay
boundaries and a bad outbox row cannot wedge them."""
from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import Mock, patch

import pytest
import requests

from server.telegram_bot import api_client, channel_commands, channels, game_context
from server.telegram_bot import games as bot_games
from server.telegram_bot import maps as bot_maps
from server.telegram_bot import notifications
from server.telegram_bot.api_client import ApiUnreachableError
from server.telegram_bot.link_account import link_account
from tests.test_bot_commands import _command, _run

pytestmark = pytest.mark.unit

DOWN = ApiUnreachableError("connection refused")


def test_players_outage_reply_is_exact() -> None:
    with patch("server.telegram_bot.games.resolve_game_and_power", return_value=("7", "FRANCE")), \
         patch("server.telegram_bot.games.api_get", side_effect=DOWN):
        reply = _run(bot_games.players, *_command())
    assert reply == f"Could not retrieve players for game 7: {DOWN}"


def test_players_programming_bug_is_not_swallowed() -> None:
    with patch("server.telegram_bot.games.resolve_game_and_power", return_value=("7", "FRANCE")), \
         patch("server.telegram_bot.games.api_get", side_effect=KeyError("players")):
        with pytest.raises(KeyError):
            _run(bot_games.players, *_command())


def test_quit_with_a_non_numeric_game_id_still_answers() -> None:
    reply = _run(bot_games.quit, *_command(args=["abc"]))
    assert reply == "Quit error: invalid literal for int() with base 10: 'abc'"


def test_map_outage_reply_is_exact() -> None:
    update, context = _command()
    update.callback_query = None
    with patch("server.telegram_bot.maps.api_get_bytes", side_effect=DOWN):
        asyncio.run(bot_maps.send_default_map(update, context))
    assert update.message.reply_text.call_args[0][0] == f"❌ Error fetching standard map: {DOWN}"


def test_map_programming_bug_is_not_swallowed() -> None:
    update, context = _command()
    update.callback_query = None
    with patch("server.telegram_bot.maps.api_get_bytes", side_effect=KeyError("x")):
        with pytest.raises(KeyError):
            asyncio.run(bot_maps.send_default_map(update, context))


def test_link_with_a_non_json_error_body_shows_the_text() -> None:
    response = requests.Response()
    response.status_code = 400
    response._content = b"<html>Bad Gateway</html>"
    err = requests.HTTPError("400", response=response)
    with patch("server.telegram_bot.link_account.api_post", side_effect=err):
        reply = _run(link_account, *_command(text="/link 123456"))
    assert reply.endswith("Details: <html>Bad Gateway</html>")


def test_link_outage_reply_is_exact() -> None:
    with patch("server.telegram_bot.link_account.api_post", side_effect=DOWN):
        reply = _run(link_account, *_command(text="/link 123456"))
    assert reply == "❌ Something went wrong. Please try again or get a new code from the web app."


def test_link_programming_bug_is_not_swallowed() -> None:
    with patch("server.telegram_bot.link_account.api_post", side_effect=KeyError("x")):
        with pytest.raises(KeyError):
            _run(link_account, *_command(text="/link 123456"))


def test_channel_info_outage_reply_is_exact() -> None:
    with patch("server.telegram_bot.channel_commands.api_get", side_effect=DOWN):
        reply = _run(channel_commands.channel_info, *_command(args=["7"]))
    assert reply == f"Channel info error: {DOWN}"


def test_channel_info_programming_bug_is_not_swallowed() -> None:
    with patch("server.telegram_bot.channel_commands.api_get", side_effect=KeyError("x")):
        with pytest.raises(KeyError):
            _run(channel_commands.channel_info, *_command(args=["7"]))


def test_a_formatter_bug_propagates_instead_of_posting_an_error() -> None:
    with pytest.raises(AttributeError):
        channels.format_player_dashboard(["not", "a", "dict"])  # type: ignore[arg-type]


def test_game_context_cache_failure_is_swallowed_but_a_bug_is_not() -> None:
    boom = Mock()
    boom.current_game.side_effect = sqlite3.OperationalError("disk I/O error")
    with patch.object(game_context, "get_outbox", return_value=boom):
        assert game_context.current_game("555") is None
    boom.current_game.side_effect = KeyError("x")
    with patch.object(game_context, "get_outbox", return_value=boom):
        with pytest.raises(KeyError):
            game_context.current_game("555")


def test_validate_api_url_messages() -> None:
    with pytest.raises(ValueError, match=r"^Invalid DIPLOMACY_API_URL: 'nonsense'$"):
        api_client._validate_api_url("nonsense")
    api_client._validate_api_url("http://api:8000")


def test_a_bad_outbox_row_is_reported_failed_and_does_not_wedge_the_batch(caplog: pytest.LogCaptureFixture) -> None:
    items = [
        {"id": 1, "telegram_id": "10", "message": "ok"},
        {"id": 2, "telegram_id": "11", "message": "bug"},
        {"id": 3, "telegram_id": "12", "message": "ok"},
    ]

    async def send(_bot: object, chat_id: int, item: dict) -> None:
        if item["id"] == 2:
            raise KeyError("payload")

    with patch.object(notifications, "api_get", return_value={"items": items}), \
         patch.object(notifications, "api_post") as ack, \
         patch.object(notifications, "_send_outbox_item", new=send):
        counts = asyncio.run(notifications.deliver_pending_notifications(Mock()))
    assert counts == (2, 1)
    body = ack.call_args[0][1]
    assert body["delivered"] == [1, 3]
    assert list(body["failed"]) == [2] and "KeyError" in body["failed"][2]
    assert any(r.exc_info for r in caplog.records if "#2" in r.getMessage())
