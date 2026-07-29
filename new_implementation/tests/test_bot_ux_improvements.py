"""Tests for Track E / E3 Telegram bot UX fixes.

Thin-client tests -- the bot never touches the engine or DB directly, so
every HTTP call is mocked. As with ``test_draw_vote_bot.py`` and
``test_interactive_orders.py``, ``server.telegram_bot.game_context.api_get``
(used by ``resolve_game_and_power``) and a given module's own
``api_get``/``api_post`` references are separate patch targets and both must
be patched independently where a code path uses both.

Covers:
- E3a: ``api_client`` surfaces the server's JSON ``detail`` instead of a bare
  HTTP status line, and the two "unregistered user tries to join" call sites
  add a /register hint on 401.
- E3b: user-controlled text (Telegram display names, broadcast/proposal
  text, channel names) is Markdown-escaped before being sent with
  ``parse_mode='Markdown'``.
- E3c: ``/messages`` shows the sender's power, not just the recipient.
- E3d: ``/processturn`` reports a dislodged/standoff summary afterwards.
- E3e: ``/processturn`` asks for confirmation before processing when some
  active power hasn't submitted orders yet.
- E3f: the bot registers a curated command list with Telegram.
- E3g: ``/order`` accepts an optional leading numeric game id and
  semicolon-separated orders (matching docs/TELEGRAM_BOT_COMMANDS.md), and
  ``/join <game_id>`` (no power) shows the power-selection menu.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from server.telegram_bot import app as bot_app
from server.telegram_bot.api_client import ApiError, api_get, api_post
from server.telegram_bot.games import join, players, register
from server.telegram_bot.messages import messages
from server.telegram_bot.orders import order, processturn, run_process_turn

pytestmark = pytest.mark.unit


def _make_update_and_context(user_id: int = 12345, args=None, first_name="Test", last_name=None):
    update = Mock()
    context = Mock()
    context.args = args
    context.user_data = {}

    message = Mock()
    message.reply_text = AsyncMock()
    user = Mock()
    user.id = user_id
    user.first_name = first_name
    user.last_name = last_name
    user.username = "testuser"

    update.effective_user = user
    update.message = message
    return update, context, message


def _mock_response(status_code: int, json_body=None, text_body: str = "") -> Mock:
    resp = Mock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.request = Mock()
    resp.text = text_body
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("no JSON body")

    def _raise() -> None:
        if status_code >= 400:
            raise requests.HTTPError(f"{status_code} Client Error: X for url: http://test", response=resp)

    resp.raise_for_status.side_effect = _raise
    return resp


# ---------------------------------------------------------------------------
# E3a -- api_client.py surfaces the server's `detail`
# ---------------------------------------------------------------------------


class TestApiClientErrorDetail:
    def test_api_post_error_message_is_server_detail_not_status_line(self):
        resp = _mock_response(401, json_body={"detail": "Not authenticated"})
        with patch("requests.post", return_value=resp):
            with pytest.raises(ApiError) as exc_info:
                api_post("/games/1/join", {"telegram_id": "5"})
        assert str(exc_info.value) == "Not authenticated"
        # Still a requests.HTTPError -- existing `except requests.HTTPError`
        # call sites (link_account.py) must keep working unchanged.
        assert isinstance(exc_info.value, requests.HTTPError)
        assert exc_info.value.response.status_code == 401

    def test_api_get_error_message_is_server_detail(self):
        resp = _mock_response(403, json_body={"detail": "Sender not in game"})
        with patch("requests.get", return_value=resp):
            with pytest.raises(ApiError) as exc_info:
                api_get("/games/1/messages")
        assert str(exc_info.value) == "Sender not in game"

    def test_falls_back_to_generic_message_when_body_is_not_json(self):
        resp = _mock_response(500, json_body=None)
        with patch("requests.post", return_value=resp):
            with pytest.raises(ApiError) as exc_info:
                api_post("/games/1/process_turn", {})
        # No `detail` available -- falls back to the plain HTTPError text,
        # not a crash inside the error-handling path itself.
        assert "500" in str(exc_info.value)

    def test_falls_back_when_json_body_has_no_detail_key(self):
        resp = _mock_response(400, json_body={"unrelated": "field"})
        with patch("requests.post", return_value=resp):
            with pytest.raises(ApiError) as exc_info:
                api_post("/games/1/join", {"telegram_id": "5"})
        assert "400" in str(exc_info.value)

    @patch("server.telegram_bot.games.api_post")
    def test_join_unregistered_user_gets_detail_and_register_hint(self, mock_post):
        mock_post.side_effect = ApiError("Not authenticated", response=Mock(status_code=401))
        update, context, message = _make_update_and_context(args=["1", "FRANCE"])

        asyncio.run(join(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Not authenticated" in text
        assert "/register" in text

    def test_app_join_callback_gets_detail_and_register_hint(self):
        """The exact call site the driver's example referred to: the inline
        'Browse Games' -> select power -> join_game_ callback in app.py,
        which has its own independent api_post call (not games.join())."""
        query = Mock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "join_game_1_FRANCE"
        query.from_user = Mock(id=12345)

        update = Mock()
        update.callback_query = query
        context = Mock()

        with patch("server.telegram_bot.app.api_post") as mock_post:
            mock_post.side_effect = ApiError("Not authenticated", response=Mock(status_code=401))
            asyncio.run(bot_app.button_callback(update, context))

        text = query.edit_message_text.call_args[0][0]
        assert "Not authenticated" in text
        assert "/register" in text


# ---------------------------------------------------------------------------
# E3b -- Markdown escaping of user-controlled text
# ---------------------------------------------------------------------------


class TestMarkdownEscaping:
    @patch("server.telegram_bot.games.api_post")
    def test_register_escapes_display_name_with_markdown_chars(self, mock_post):
        mock_post.return_value = {"status": "ok"}
        update, context, message = _make_update_and_context(first_name="John_Snow*Bot")

        asyncio.run(register(update, context))

        text = message.reply_text.call_args[0][0]
        assert "John\\_Snow\\*Bot" in text
        # And the raw, unescaped name must not appear unescaped inside the
        # Markdown message (that's exactly what made Telegram reject it).
        assert "John_Snow*Bot" not in text

    @patch("server.telegram_bot.games.api_post")
    def test_register_reply_failure_does_not_relabel_success_as_error(self, mock_post):
        """Even if the confirmation reply itself fails, registration already
        succeeded server-side -- the player must not be told 'Registration
        error'."""
        mock_post.return_value = {"status": "ok"}
        update, context, message = _make_update_and_context(first_name="X")
        message.reply_text.side_effect = Exception("Telegram API hiccup")

        asyncio.run(register(update, context))

        for call in message.reply_text.call_args_list:
            assert "Registration error" not in call[0][0]

    @patch("server.telegram_bot.games.api_get")
    @patch("server.telegram_bot.game_context.api_get")
    def test_players_escapes_full_name_with_markdown_chars(self, mock_ctx_get, mock_games_get):
        mock_ctx_get.return_value = {"games": [{"game_id": "1", "power": "FRANCE"}]}
        mock_games_get.return_value = [
            {"power": "FRANCE", "full_name": "Al_ice*", "is_active": True},
        ]
        update, context, message = _make_update_and_context()

        asyncio.run(players(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Al\\_ice\\*" in text

    @patch("server.telegram_bot.games.api_get")
    @patch("server.telegram_bot.game_context.api_get")
    def test_players_survives_reply_failure_instead_of_going_silent(self, mock_ctx_get, mock_games_get):
        """Before this fix, /players had no try/except around its final
        reply_text call at all -- a Markdown-breaking name made it do
        nothing, with no error shown either."""
        mock_ctx_get.return_value = {"games": [{"game_id": "1", "power": "FRANCE"}]}
        mock_games_get.return_value = [
            {"power": "FRANCE", "full_name": "Whatever", "is_active": True},
        ]
        update, context, message = _make_update_and_context()
        message.reply_text.side_effect = [Exception("boom"), None]

        asyncio.run(players(update, context))

        # Two attempts: the (failing) formatted listing, then a fallback
        # message -- /players no longer just does nothing.
        assert message.reply_text.call_count == 2

    def test_post_broadcast_to_channel_escapes_message_text(self):
        from server.telegram_bot.channels import post_broadcast_to_channel, set_telegram_bot

        mock_bot = Mock()
        mock_bot.send_message = Mock(return_value=Mock(message_id=1))
        set_telegram_bot(mock_bot)

        post_broadcast_to_channel(
            channel_id="-100123",
            game_id="1",
            message="Attack now! [link](evil) _urgent_",
            power="FRANCE",
        )

        sent_text = mock_bot.send_message.call_args.kwargs["text"]
        assert "\\[link\\]\\(evil\\)" in sent_text
        assert "\\_urgent\\_" in sent_text

    @patch("server.telegram_bot.channel_commands.api_get")
    def test_channel_info_escapes_channel_name(self, mock_get):
        from server.telegram_bot.channel_commands import channel_info

        mock_get.return_value = {
            "linked": True,
            "channel_id": "-100123",
            "channel_name": "War_Room*Alpha",
            "settings": {},
        }
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(channel_info(update, context))

        text = message.reply_text.call_args[0][0]
        assert "War\\_Room\\*Alpha" in text


# ---------------------------------------------------------------------------
# E3c -- /messages sender attribution
# ---------------------------------------------------------------------------


class TestMessagesSenderAttribution:
    @patch("server.telegram_bot.messages.api_get")
    def test_messages_shows_sender_power(self, mock_get):
        def side_effect(endpoint, *args, **kwargs):
            if "/messages" in endpoint:
                return {
                    "messages": [
                        {
                            "id": 1,
                            "sender_user_id": 42,
                            "recipient_power": "FRANCE",
                            "text": "Let's ally",
                            "timestamp": "2024-01-01T00:00:00",
                        }
                    ]
                }
            if endpoint.endswith("/players"):
                return [
                    {"user_id": 42, "power": "GERMANY"},
                    {"user_id": 43, "power": "FRANCE"},
                ]
            raise AssertionError(f"unexpected endpoint {endpoint}")

        mock_get.side_effect = side_effect
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(messages(update, context))

        text = message.reply_text.call_args[0][0]
        assert "GERMANY" in text
        assert "FRANCE" in text
        assert "Let's ally" in text

    @patch("server.telegram_bot.messages.api_get")
    def test_messages_degrades_to_unknown_when_players_lookup_fails(self, mock_get):
        def side_effect(endpoint, *args, **kwargs):
            if "/messages" in endpoint:
                return {
                    "messages": [
                        {
                            "id": 1,
                            "sender_user_id": 42,
                            "recipient_power": None,
                            "text": "hello all",
                            "timestamp": "2024-01-01T00:00:00",
                        }
                    ]
                }
            if endpoint.endswith("/players"):
                raise Exception("network blip")
            raise AssertionError(f"unexpected endpoint {endpoint}")

        mock_get.side_effect = side_effect
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(messages(update, context))

        text = message.reply_text.call_args[0][0]
        assert "Unknown" in text
        assert "hello all" in text


# ---------------------------------------------------------------------------
# E3d -- /processturn outcome summary
# ---------------------------------------------------------------------------


class TestProcessTurnSummary:
    def test_run_process_turn_reports_dislodged_and_standoffs(self):
        send = AsyncMock()

        def api_get_side(endpoint, *a, **kw):
            assert endpoint == "/games/1/state"
            return {
                "phase": "F1901M",
                "status": "IN_PROGRESS",
                "dislodged": [
                    {
                        "unit": {"kind": "A", "power": "GERMANY", "location": "MUN"},
                        "attacker_origin": "TYR",
                        "retreats": ["BOH", "SIL"],
                    }
                ],
                "contested": ["BUR"],
            }

        with patch("server.telegram_bot.orders.api_post", return_value={"status": "ok"}), \
             patch("server.telegram_bot.orders.api_get", side_effect=api_get_side):
            asyncio.run(run_process_turn(send, "1"))

        text = send.call_args[0][0]
        assert "GERMANY" in text and "MUN" in text
        assert "BUR" in text
        assert "F1901M" in text

    def test_run_process_turn_reports_game_complete_with_winners(self):
        send = AsyncMock()

        def api_get_side(endpoint, *a, **kw):
            return {
                "phase": "F1910M",
                "status": "COMPLETED",
                "winners": ["FRANCE", "ENGLAND"],
                "dislodged": [],
                "contested": [],
            }

        with patch("server.telegram_bot.orders.api_post", return_value={"status": "ok"}), \
             patch("server.telegram_bot.orders.api_get", side_effect=api_get_side):
            asyncio.run(run_process_turn(send, "1"))

        text = send.call_args[0][0]
        assert "Game Complete" in text
        assert "FRANCE" in text and "ENGLAND" in text


# ---------------------------------------------------------------------------
# E3e -- /processturn confirmation gate
# ---------------------------------------------------------------------------


class TestProcessTurnConfirmation:
    @patch("server.telegram_bot.orders.api_get")
    @patch("server.telegram_bot.game_context.api_get")
    def test_processturn_asks_confirmation_when_orders_missing(self, mock_ctx_get, mock_orders_get):
        mock_ctx_get.return_value = {"games": [{"game_id": "1", "power": "FRANCE"}]}
        mock_orders_get.return_value = {"submitted": ["FRANCE"], "missing": ["GERMANY", "ITALY"]}
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(processturn(update, context))

        message.reply_text.assert_called_once()
        _, kwargs = message.reply_text.call_args
        text = message.reply_text.call_args[0][0]
        assert "GERMANY" in text and "ITALY" in text
        assert kwargs.get("reply_markup") is not None

    @patch("server.telegram_bot.orders.api_post")
    @patch("server.telegram_bot.orders.api_get")
    @patch("server.telegram_bot.game_context.api_get")
    def test_processturn_proceeds_directly_when_nothing_missing(
        self, mock_ctx_get, mock_orders_get, mock_post
    ):
        mock_ctx_get.return_value = {"games": [{"game_id": "1", "power": "FRANCE"}]}

        def orders_get_side(endpoint, *a, **kw):
            if endpoint.endswith("/orders_status"):
                return {"submitted": ["FRANCE", "GERMANY"], "missing": []}
            if endpoint.endswith("/state"):
                return {"phase": "F1901M", "status": "IN_PROGRESS", "dislodged": [], "contested": []}
            raise AssertionError(endpoint)

        mock_orders_get.side_effect = orders_get_side
        mock_post.return_value = {"status": "ok"}
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(processturn(update, context))

        mock_post.assert_called_once_with("/games/1/process_turn", {})
        text = message.reply_text.call_args[0][0]
        assert "Turn Processed" in text

    def test_button_callback_ptforce_runs_process_turn(self):
        query = Mock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "ptforce|1"
        query.from_user = Mock(id=12345)
        update = Mock()
        update.callback_query = query
        context = Mock()

        def api_get_side(endpoint, *a, **kw):
            return {"phase": "F1901M", "status": "IN_PROGRESS", "dislodged": [], "contested": []}

        with patch("server.telegram_bot.orders.api_post", return_value={"status": "ok"}), \
             patch("server.telegram_bot.orders.api_get", side_effect=api_get_side):
            asyncio.run(bot_app.button_callback(update, context))

        text = query.edit_message_text.call_args[0][0]
        assert "Turn Processed" in text

    def test_button_callback_ptcancel_does_not_process(self):
        query = Mock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "ptcancel|1"
        query.from_user = Mock(id=12345)
        update = Mock()
        update.callback_query = query
        context = Mock()

        with patch("server.telegram_bot.orders.api_post") as mock_post:
            asyncio.run(bot_app.button_callback(update, context))
            mock_post.assert_not_called()

        text = query.edit_message_text.call_args[0][0]
        assert "cancelled" in text.lower()


# ---------------------------------------------------------------------------
# E3f -- registered command list
# ---------------------------------------------------------------------------


class TestBotCommandRegistration:
    def test_bot_commands_includes_draw_and_nodraw(self):
        names = {c.command for c in bot_app.BOT_COMMANDS}
        assert "draw" in names
        assert "nodraw" in names

    def test_bot_commands_is_curated_not_a_dump_of_everything(self):
        # 27 handlers are registered in main(); the "/" menu should be a
        # curated subset, not all of them (e.g. aliases/admin/debug skipped).
        assert 0 < len(bot_app.BOT_COMMANDS) < 27
        names = {c.command for c in bot_app.BOT_COMMANDS}
        assert "debug" not in names

    def test_post_init_registers_commands_with_telegram(self):
        mock_app = Mock()
        mock_app.bot.set_my_commands = AsyncMock()

        asyncio.run(bot_app._post_init(mock_app))

        mock_app.bot.set_my_commands.assert_called_once_with(bot_app.BOT_COMMANDS)


# ---------------------------------------------------------------------------
# E3g -- /order matches docs; /join <game_id> shows a power menu
# ---------------------------------------------------------------------------


class TestOrderMatchesDocs:
    @patch("server.telegram_bot.orders.api_post")
    @patch("server.telegram_bot.game_context.api_get")
    def test_order_accepts_leading_game_id_and_semicolons(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = {
            "games": [
                {"game_id": "1", "power": "FRANCE"},
                {"game_id": "2", "power": "GERMANY"},
            ]
        }
        mock_post.return_value = {
            "results": [
                {"success": True, "order": "A BER - SIL"},
                {"success": True, "order": "A MUN S A BER - SIL"},
            ]
        }
        update, context, message = _make_update_and_context(
            args=["2", "A", "BER", "-", "SIL;", "A", "MUN", "S", "A", "BER", "-", "SIL"]
        )

        asyncio.run(order(update, context))

        mock_post.assert_called_once()
        payload = mock_post.call_args[0][1]
        assert payload["game_id"] == "2"
        assert payload["power"] == "GERMANY"
        assert payload["orders"] == ["A BER - SIL", "A MUN S A BER - SIL"]

    @patch("server.telegram_bot.orders.api_post")
    @patch("server.telegram_bot.game_context.api_get")
    def test_order_without_game_id_still_autodetects(self, mock_ctx_get, mock_post):
        mock_ctx_get.return_value = {"games": [{"game_id": "1", "power": "FRANCE"}]}
        mock_post.return_value = {"results": [{"success": True, "order": "A PAR H"}]}
        update, context, message = _make_update_and_context(args=["A", "PAR", "H"])

        asyncio.run(order(update, context))

        payload = mock_post.call_args[0][1]
        assert payload["game_id"] == "1"
        assert payload["orders"] == ["A PAR H"]

    @patch("server.telegram_bot.games.api_get")
    def test_join_single_arg_shows_power_selection_menu(self, mock_get):
        def side_effect(endpoint, *a, **kw):
            if endpoint.endswith("/state"):
                return {"phase": "S1901M"}
            if endpoint.endswith("/players"):
                return [{"power": "FRANCE"}]
            raise AssertionError(endpoint)

        mock_get.side_effect = side_effect
        update, context, message = _make_update_and_context(args=["1"])

        asyncio.run(join(update, context))

        _, kwargs = message.reply_text.call_args
        text = message.reply_text.call_args[0][0]
        assert "Select Power" in text
        assert kwargs.get("reply_markup") is not None

    @patch("server.telegram_bot.games.api_post")
    def test_join_two_args_still_joins_directly(self, mock_post):
        mock_post.return_value = {"status": "ok"}
        update, context, message = _make_update_and_context(args=["1", "FRANCE"])

        asyncio.run(join(update, context))

        mock_post.assert_called_once()
        text = message.reply_text.call_args[0][0]
        assert "Successfully joined" in text
