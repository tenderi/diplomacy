"""The bot's player commands as a thin client: each one calls the right endpoint as
the right player, and turns the server's answer -- or its refusal, or its absence --
into a reply rather than an exception. Every HTTP call is mocked.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from server.telegram_bot import games as bot_games
from server.telegram_bot import messages as bot_messages
from server.telegram_bot import orders as bot_orders
from server.telegram_bot.api_client import ApiUnreachableError
from server.telegram_bot.link_account import link_account
from tests.reliability_helpers import delivered, queued, rejected

pytestmark = pytest.mark.unit

ME = 555
MY_GAMES = {"games": [{"game_id": "7", "power": "FRANCE"}]}


def _command(args: list[str] | None = None, text: str = "") -> tuple[Mock, Mock]:
    update, context = Mock(), Mock()
    update.effective_user = Mock(id=ME, full_name="Pat", first_name="Pat", last_name=None, username="pat")
    update.message.reply_text = AsyncMock()
    update.message.delete = AsyncMock()
    update.message.text = text
    update.effective_message = update.message
    update.effective_chat = Mock(type="private")
    context.args = args
    context.user_data = {}
    context.bot = Mock()
    return update, context


def _run(handler: Any, update: Mock, context: Mock) -> str:
    asyncio.run(handler(update, context))
    return update.message.reply_text.call_args[0][0]


def _http_error(status: int, detail: str) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    response._content = f'{{"detail": "{detail}"}}'.encode()
    return requests.HTTPError(detail, response=response)


class TestLink:
    def test_without_a_code_explains_where_to_get_one(self) -> None:
        with patch("server.telegram_bot.link_account.api_post") as post:
            reply = _run(link_account, *_command(text="/link"))
        post.assert_not_called()
        assert reply.startswith("Usage: /link <code>")

    def test_links_this_telegram_account_with_the_code(self) -> None:
        with patch("server.telegram_bot.link_account.api_post", return_value={"message": "Linked to pat@example.com."}) as post:
            reply = _run(link_account, *_command(text="/link 123456"))
        post.assert_called_once_with("/auth/telegram/link", {"telegram_id": str(ME), "code": "123456"})
        assert reply == "✅ Linked to pat@example.com."

    @pytest.mark.parametrize(("status", "expected"), [
        (409, "❌ This Telegram is already linked to another account."),
        (400, "❌ Invalid or expired code. Get a new code from the web app (Link Telegram).\nDetails: Invalid or expired code"),
    ])
    def test_a_refusal_says_why(self, status: int, expected: str) -> None:
        error = _http_error(status, "Invalid or expired code")
        with patch("server.telegram_bot.link_account.api_post", side_effect=error):
            assert _run(link_account, *_command(text="/link 999999")) == expected


class TestMessages:
    @pytest.fixture(autouse=True)
    def _my_games(self) -> Any:
        with patch("server.telegram_bot.game_context.api_get", return_value=MY_GAMES):
            yield

    def test_a_leading_game_id_of_mine_picks_that_game(self) -> None:
        with patch.object(bot_messages, "api_post_reliable", return_value=delivered()) as post:
            reply = _run(bot_messages.message, *_command(["7", "germany", "Belgium", "is", "yours"]))
        endpoint, body = post.call_args[0]
        assert (endpoint, body) == ("/games/7/message", {"telegram_id": str(ME), "recipient_power": "GERMANY", "text": "Belgium is yours"})
        assert post.call_args[1]["chat_id"] == ME
        assert reply == "Message sent to GERMANY in game 7."

    def test_without_a_game_id_it_goes_to_the_current_game(self) -> None:
        with patch.object(bot_messages, "api_post_reliable", return_value=delivered()) as post:
            _run(bot_messages.broadcast, *_command(["Peace", "in", "our", "time"]))
        assert post.call_args[0] == ("/games/7/broadcast", {"telegram_id": str(ME), "text": "Peace in our time"})

    @pytest.mark.parametrize(("handler", "args", "usage"), [
        (bot_messages.message, ["GERMANY"], "Usage: /message [game_id] <power> <text>"),
        (bot_messages.broadcast, ["7"], "Usage: /broadcast [game_id] <text>"),
    ])
    def test_too_few_words_is_usage_not_a_send(self, handler: Any, args: list[str], usage: str) -> None:
        with patch.object(bot_messages, "api_post_reliable") as post:
            assert _run(handler, *_command(args)).startswith(usage)
        post.assert_not_called()

    def test_a_refused_message_shows_the_servers_reason(self) -> None:
        with patch.object(bot_messages, "api_post_reliable", return_value=rejected("Recipient seat is vacant")):
            assert _run(bot_messages.message, *_command(["ITALY", "hi"])) == "Message error: Recipient seat is vacant"

    def test_offline_with_no_cache_a_numeric_game_id_is_trusted_and_queued(self) -> None:
        with patch("server.telegram_bot.messages.fetch_user_games", side_effect=ApiUnreachableError("down")), \
             patch.object(bot_messages, "api_post_reliable", return_value=queued()) as post:
            reply = _run(bot_messages.message, *_command(["12", "ITALY", "hello"]))
        assert post.call_args[0][0] == "/games/12/message"
        assert "queued" in reply.lower()

    def test_offline_with_no_cache_and_no_game_id_says_so(self) -> None:
        with patch("server.telegram_bot.messages.fetch_user_games", side_effect=ApiUnreachableError("down")), \
             patch.object(bot_messages, "api_post_reliable") as post:
            assert _run(bot_messages.message, *_command(["ITALY", "hello"])).startswith("⚠️ The game server is unreachable")
        post.assert_not_called()

    def test_messages_names_each_sender(self) -> None:
        def fake_get(path: str, **_kw: Any) -> Any:
            if path.startswith("/games/7/messages"):
                assert path == f"/games/7/messages?telegram_id={ME}"
                return {"messages": [
                    {"timestamp": "t1", "sender_user_id": 1, "recipient_power": "FRANCE", "text": "Hi"},
                    {"timestamp": "t2", "sender_user_id": 2, "recipient_power": None, "text": "All: peace"},
                    {"timestamp": "t3", "sender_user_id": 99, "recipient_power": "GERMANY", "text": "?"},
                ]}
            return [{"user_id": 1, "power": "GERMANY"}, {"user_id": 2, "power": "FRANCE"}]
        with patch.object(bot_messages, "api_get", side_effect=fake_get):
            reply = _run(bot_messages.messages, *_command([]))
        assert reply.splitlines() == [
            "Messages for game 7:",
            "[t1] GERMANY -> FRANCE: Hi",
            "[t2] FRANCE -> ALL: All: peace",
            "[t3] Unknown -> GERMANY: ?",
        ]

    def test_no_messages_yet(self) -> None:
        with patch.object(bot_messages, "api_get", return_value={"messages": []}):
            assert _run(bot_messages.messages, *_command([])) == "No messages in game 7 yet."


class TestSeats:
    def test_quit_leaves_the_named_game(self) -> None:
        with patch.object(bot_games, "api_post", return_value={"status": "ok"}) as post:
            assert _run(bot_games.quit, *_command(["7"])) == "You have left Game 7."
        post.assert_called_once_with("/games/7/quit", {"telegram_id": str(ME), "game_id": 7})

    def test_quit_shows_the_servers_refusal(self) -> None:
        with patch.object(bot_games, "api_post", side_effect=_http_error(404, "Player not found in game")):
            assert _run(bot_games.quit, *_command(["7"])) == "Quit error: Player not found in game"

    @pytest.mark.parametrize(("handler", "args", "usage"), [
        (bot_games.quit, [], "Usage: /quit <game_id>"),
        (bot_games.replace, ["7"], "Usage: /replace <game_id> <power> [password]"),
        (bot_games.join, [], "Usage: /join <game_id> [power] [password]"),
    ])
    def test_missing_arguments_is_usage(self, handler: Any, args: list[str], usage: str) -> None:
        with patch.object(bot_games, "api_post") as post:
            assert _run(handler, *_command(args)).startswith(usage)
        post.assert_not_called()

    def test_replace_with_a_password_sends_it_and_deletes_the_message(self) -> None:
        update, context = _command(["7", "italy", "open", "sesame"])
        with patch.object(bot_games, "api_post", return_value={"status": "ok"}) as post:
            reply = _run(bot_games.replace, update, context)
        post.assert_called_once_with("/games/7/replace", {"telegram_id": str(ME), "power": "ITALY", "join_password": "open sesame"})
        update.message.delete.assert_awaited_once()
        assert reply == "✅ Successfully replaced player for ITALY in Game 7!"

    def test_join_with_a_power_joins_and_remembers_the_game(self) -> None:
        with patch.object(bot_games, "api_get", return_value={"linked": False}), \
             patch.object(bot_games, "ensure_registered"), \
             patch.object(bot_games, "api_post", return_value={"status": "ok"}) as post, \
             patch.object(bot_games, "set_current_game") as remember:
            reply = _run(bot_games.join, *_command(["7", "austria"]))
        post.assert_called_once_with("/games/7/join", {"telegram_id": str(ME), "game_id": 7, "power": "AUSTRIA"})
        remember.assert_called_once_with(str(ME), "7")
        assert reply == "🎉 You joined game 7 as AUSTRIA! Open it any time with /game 7."

    def test_join_refuses_a_game_from_a_group_you_are_not_in(self) -> None:
        update, context = _command(["7", "AUSTRIA"])
        context.bot.get_chat_member = AsyncMock(return_value=Mock(status="left"))
        with patch.object(bot_games, "api_get", return_value={"linked": True, "channel_id": "-100"}), \
             patch.object(bot_games, "api_post") as post:
            assert _run(bot_games.join, update, context) == bot_games.NOT_IN_GROUP
        post.assert_not_called()
        context.bot.get_chat_member.assert_awaited_once_with("-100", ME)


class TestOrderReadouts:
    @pytest.fixture(autouse=True)
    def _my_games(self) -> Any:
        with patch("server.telegram_bot.game_context.api_get", return_value=MY_GAMES):
            yield

    def test_myorders_lists_this_phases_orders(self) -> None:
        with patch.object(bot_orders, "api_get", return_value={"orders": ["A PAR - BUR", "F BRE H"]}) as get:
            reply = _run(bot_orders.myorders, *_command([]))
        get.assert_called_once_with("/games/7/orders/FRANCE", telegram_id=str(ME))
        assert reply == "Your orders in game 7 (FRANCE):\nA PAR - BUR\nF BRE H"

    def test_myorders_with_none_yet(self) -> None:
        with patch.object(bot_orders, "api_get", return_value={"orders": []}):
            assert _run(bot_orders.myorders, *_command([])) == "You have not submitted any orders in game 7 this turn."

    def test_orderhistory_is_in_turn_order_not_string_order(self) -> None:
        history = {str(t): {"FRANCE": [f"order {t}"]} for t in (10, 2, 1)}
        with patch.object(bot_orders, "api_get", return_value={"order_history": history}):
            reply = _run(bot_orders.orderhistory, *_command([]))
        assert [line for line in reply.splitlines() if line.startswith("Turn")] == ["Turn 1:", "Turn 2:", "Turn 10:"]

    def test_a_long_history_keeps_the_latest_turns(self) -> None:
        history = {str(t): {"FRANCE": [f"A PAR H  # turn {t:03d} " + "x" * 80]} for t in range(80)}
        with patch.object(bot_orders, "api_get", return_value={"order_history": history}):
            reply = _run(bot_orders.orderhistory, *_command([]))
        assert len(reply) <= 4000 and reply.startswith("…")
        assert "turn 079" in reply and "turn 000" not in reply

    @pytest.mark.parametrize(("outcome", "expected"), [
        (delivered(), "Your orders for this turn have been cleared."),
        (rejected("Not your power"), "Error clearing orders: Not your power"),
    ])
    def test_clearorders(self, outcome: Any, expected: str) -> None:
        with patch.object(bot_orders, "api_post_reliable", return_value=outcome) as post:
            assert _run(bot_orders.clearorders, *_command([])) == expected
        assert post.call_args[0] == ("/games/7/orders/FRANCE/clear", {"telegram_id": str(ME)})

    def test_viewmap_sends_the_resolved_games_map(self) -> None:
        update, context = _command([])
        with patch("server.telegram_bot.maps.send_game_map", new=AsyncMock()) as send:
            asyncio.run(bot_orders.viewmap(update, context))
        send.assert_awaited_once_with(update, context, "7")


class TestDemoAndDebug:
    def test_a_demo_is_germany_against_six_computer_seats(self) -> None:
        from server.telegram_bot import admin as bot_admin
        update, context = _command()
        update.callback_query = None
        with patch.object(bot_admin, "ensure_registered"), \
             patch.object(bot_admin, "api_post", side_effect=[{"game_id": 31}, {"status": "ok"}]) as post, \
             patch.object(bot_admin, "set_current_game") as remember:
            asyncio.run(bot_admin.start_demo_game(update, context))
        create, join = post.call_args_list
        assert create.args == ("/games/create", {"map_name": "demo", "telegram_id": str(ME),
                                                 "dummy_powers": ["AUSTRIA", "ENGLAND", "FRANCE", "ITALY", "RUSSIA", "TURKEY"],
                                                 "auto_process": True})
        assert join.args == ("/games/31/join", {"telegram_id": str(ME), "game_id": 31, "power": "GERMANY"})
        remember.assert_called_once_with(str(ME), "31")
        markup = update.message.reply_text.call_args[1]["reply_markup"]
        assert [b.callback_data for row in markup.inline_keyboard for b in row] == ["g|31|all|n", "g|31|map", "g|31|hub|n", "demo_help_31"]

    def test_a_demo_that_cannot_start_says_so(self) -> None:
        from server.telegram_bot import admin as bot_admin
        update, context = _command()
        update.callback_query = None
        with patch.object(bot_admin, "ensure_registered"), \
             patch.object(bot_admin, "api_post", side_effect=requests.ConnectionError("down")):
            asyncio.run(bot_admin.start_demo_game(update, context))
        assert update.message.reply_text.call_args[0][0] == "❌ Could not start a demo game: down"

    def test_debug_shows_your_telegram_id_as_plain_text(self) -> None:
        from server.telegram_bot import admin as bot_admin
        update, context = _command()
        update.effective_user.full_name = "Pat *the* _Great_"
        reply = _run(bot_admin.debug_command, update, context)
        assert f"User ID: {ME}" in reply and "Pat *the* _Great_" in reply
        assert "parse_mode" not in update.message.reply_text.call_args[1]
