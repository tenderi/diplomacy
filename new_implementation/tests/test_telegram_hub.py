"""The game menu (hub.py), the current game, and notification buttons.

Driven through the real callback router (``app.button_callback``) and command
handlers; every HTTP call is mocked.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot import app as bot_app
from server.telegram_bot import hub
from server.telegram_bot.game_context import GameContextError, resolve_game_and_power, set_current_game
from server.telegram_bot.games import AWAITING, start
from server.telegram_bot.notifications import _send_outbox_item

pytestmark = pytest.mark.unit

TWO_GAMES = {"games": [
    {"game_id": "3", "power": "GERMANY", "is_creator": False},
    {"game_id": "5", "power": "FRANCE", "is_creator": True},
]}
STATE = {"phase": "S1901M", "phase_type": "MOVEMENT", "year": 1901, "season": "Spring", "status": "ACTIVE"}


def _press(data: str, context: Mock | None = None, message_text: str = "menu") -> tuple[Mock, Mock]:
    query = Mock()
    query.data = data
    query.answer = AsyncMock()
    query.from_user = Mock(id=555)
    query.edit_message_text = AsyncMock()
    query.message = Mock(text=message_text)
    query.message.reply_text = AsyncMock()
    query.message.reply_photo = AsyncMock()
    update = Mock()
    update.callback_query = query
    context = context or Mock(user_data={})
    asyncio.run(bot_app.button_callback(update, context))
    return query, context


def _hub_api_get(path: str, **_kw):
    if path.endswith("/state"):
        return STATE
    if path.endswith("/orders_status"):
        return {"submitted": [], "missing": ["FRANCE"], "auto_process": True, "waiting": []}
    if path.endswith("/deadline"):
        return {"deadline": None}
    if path.endswith("/draw_vote_status"):
        return {"votes": [], "required": []}
    raise AssertionError(path)


@pytest.fixture
def two_games():
    with patch("server.telegram_bot.game_context.api_get", return_value=TWO_GAMES):
        yield


def _buttons(markup) -> list[tuple[str, str]]:
    return [(b.text, b.callback_data) for row in markup.inline_keyboard for b in row]


class TestCurrentGame:
    def test_two_games_and_no_current_game_asks_which(self, two_games) -> None:
        with pytest.raises(GameContextError) as e:
            resolve_game_and_power("555")
        assert "/game <id>" in e.value.message

    def test_naming_a_game_makes_it_current(self, two_games) -> None:
        assert resolve_game_and_power("555", "5") == ("5", "FRANCE")
        assert resolve_game_and_power("555") == ("5", "FRANCE")

    def test_a_current_game_you_left_is_ignored(self, two_games) -> None:
        set_current_game("555", "99")
        with pytest.raises(GameContextError):
            resolve_game_and_power("555")


class TestGameMenu:
    def test_opening_it_shows_status_and_every_action(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", side_effect=_hub_api_get), \
             patch("server.telegram_bot.games.api_get", side_effect=_hub_api_get):
            query, _ = _press("g|3|hub")
        text, kwargs = query.edit_message_text.call_args[0][0], query.edit_message_text.call_args[1]
        assert "Game 3 · GERMANY" in text and "Waiting on" in text
        datas = [d for _t, d in _buttons(kwargs["reply_markup"])]
        for action in ("all", "one", "view", "map", "msgs", "dl", "nr"):
            assert f"g|3|{action}" in datas
        assert "g|3|pt" not in datas  # only the game's creator may process early
        assert resolve_game_and_power("555") == ("3", "GERMANY")  # and it is now current

    def test_the_creator_gets_process_turn_now(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", side_effect=_hub_api_get), \
             patch("server.telegram_bot.games.api_get", side_effect=_hub_api_get):
            query, _ = _press("g|5|hub")
        assert "g|5|pt" in [d for _t, d in _buttons(query.edit_message_text.call_args[1]["reply_markup"])]

    def test_a_notification_button_answers_in_a_new_message(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", side_effect=_hub_api_get), \
             patch("server.telegram_bot.games.api_get", side_effect=_hub_api_get):
            query, _ = _press("g|3|hub|n")
        query.edit_message_text.assert_not_called()  # the notification stays as it was
        assert "Game 3 · GERMANY" in query.message.reply_text.call_args[0][0]

    def test_enter_orders_starts_the_walk_for_that_game(self, two_games) -> None:
        legal = {
            "phase": "S1901M", "phase_type": "MOVEMENT",
            "units": [{"kind": "A", "location": "BER"}],
            "orders_by_unit": {"A BER": ["A BER H", "A BER - KIE"]},
        }
        with patch("server.telegram_bot.orders.api_get", return_value=legal):
            query, context = _press("g|3|all")
        assert "Unit 1/1" in query.edit_message_text.call_args[0][0]
        assert context.user_data["order_walk"]["3"]["power"] == "GERMANY"

    def test_an_old_orders_menu_button_opens_the_game_menu(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", side_effect=_hub_api_get), \
             patch("server.telegram_bot.games.api_get", side_effect=_hub_api_get):
            query, _ = _press("orders_menu_3_GERMANY")
        assert "Game 3 · GERMANY" in query.edit_message_text.call_args[0][0]


class TestWritingAMessage:
    def test_tap_a_power_then_just_type(self, two_games) -> None:
        _query, context = _press("g|3|msg|FRANCE")
        assert context.user_data[AWAITING] == {"kind": "compose", "game_id": "3", "recipient": "FRANCE"}

        update = Mock()
        update.effective_user = Mock(id=555)
        update.message = Mock(text="Lepanto?")
        update.message.reply_text = AsyncMock()
        delivered = SimpleNamespace(status="delivered", response={}, error=None)
        with patch("server.telegram_bot.messages.api_post_reliable", return_value=delivered) as post:
            assert asyncio.run(hub.handle_awaited_text(update, context)) is True
        endpoint, body = post.call_args[0][:2]
        assert endpoint == "/games/3/message" and body["recipient_power"] == "FRANCE" and body["text"] == "Lepanto?"
        assert "Message sent to FRANCE" in update.message.reply_text.call_args[0][0]
        assert AWAITING not in context.user_data

    def test_everyone_is_a_broadcast(self, two_games) -> None:
        _query, context = _press("g|3|msg|ALL")
        update = Mock()
        update.effective_user = Mock(id=555)
        update.message = Mock(text="hello all")
        update.message.reply_text = AsyncMock()
        delivered = SimpleNamespace(status="delivered", response={}, error=None)
        with patch("server.telegram_bot.messages.api_post_reliable", return_value=delivered) as post:
            asyncio.run(hub.handle_awaited_text(update, context))
        assert post.call_args[0][0] == "/games/3/broadcast"


class TestDeadlineButtons:
    def test_no_proposal_offers_lengths_to_vote_on(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", return_value={"deadline": None}):
            query, _ = _press("g|3|dl")
        datas = [d for _t, d in _buttons(query.edit_message_text.call_args[1]["reply_markup"])]
        assert {"g|3|dlp|12", "g|3|dlp|24", "g|3|dlp|48"} <= set(datas)

    def test_proposing_posts_the_hours(self, two_games) -> None:
        pending = {"proposed_by": "GERMANY", "value_hours": 24.0, "yes_votes": ["GERMANY"],
                   "no_votes": [], "needed_for_majority": 2}
        with patch("server.telegram_bot.games.api_post", return_value=pending) as post:
            _press("g|3|dlp|24")
        endpoint, body = post.call_args[0]
        assert endpoint == "/games/3/deadline/propose" and body["hours"] == 24.0 and body["power"] == "GERMANY"

    def test_a_pending_proposal_offers_a_vote(self, two_games) -> None:
        proposal = {"proposed_by": "FRANCE", "value_hours": 12.0, "yes_votes": ["FRANCE"],
                    "no_votes": [], "needed_for_majority": 2}
        with patch("server.telegram_bot.hub.api_get", return_value={"deadline": None, "pending_proposal": proposal}):
            query, _ = _press("g|3|dl")
        datas = [d for _t, d in _buttons(query.edit_message_text.call_args[1]["reply_markup"])]
        assert "g|3|dlv|yes" in datas and "g|3|dlw" not in datas


class TestFindAGame:
    def test_lists_only_games_you_could_join(self) -> None:
        listing = {"games": [
            {"id": 1, "status": "active", "player_count": 2, "max_players": 7},
            {"id": 3, "status": "active", "player_count": 2, "max_players": 7},  # already mine
            {"id": 4, "status": "active", "player_count": 7, "max_players": 7},  # full
            {"id": 6, "status": "active", "player_count": 1, "max_players": 1, "map_name": "demo"},
            {"id": 8, "status": "completed", "player_count": 2, "max_players": 7},
            {"id": 9, "status": "active", "player_count": 1, "max_players": 7, "private": True},
        ]}
        with patch("server.telegram_bot.hub.api_get", return_value=listing), \
             patch("server.telegram_bot.game_context.api_get", return_value=TWO_GAMES):
            query, _ = _press("find_game")
        buttons = _buttons(query.edit_message_text.call_args[1]["reply_markup"])
        games = [d for _t, d in buttons if d.startswith("select_game_")]
        assert games == ["select_game_1", "select_game_9"]
        assert any(t.startswith("🔒") for t, d in buttons if d == "select_game_9")
        assert ("⏳ Queue for the next new game", "join_waiting_list") in buttons


def test_start_registers_the_player_and_shows_three_keys() -> None:
    update = Mock()
    update.effective_user = Mock(id=555, first_name="Pat", last_name=None, username="pat")
    update.message.reply_text = AsyncMock()
    with patch("server.telegram_bot.games.api_post", return_value={"status": "ok"}) as post:
        asyncio.run(start(update, Mock()))
    assert post.call_args[0][0] == "/users/persistent_register"
    keyboard = update.message.reply_text.call_args[1]["reply_markup"].keyboard
    assert [b.text for row in keyboard for b in row] == ["🎮 My games", "🎲 Find a game", "ℹ️ Help"]


def test_a_dm_with_buttons_is_sent_with_them() -> None:
    bot = Mock()
    bot.send_message = AsyncMock()
    item = {"id": 1, "kind": "dm", "message": "The turn has been processed for game 3.",
            "created_at": None,
            "payload": {"buttons": [[{"text": "📝 Enter orders", "callback_data": "g|3|all|n"}]]}}
    asyncio.run(_send_outbox_item(bot, 555, item))
    markup = bot.send_message.call_args[1]["reply_markup"]
    assert _buttons(markup) == [("📝 Enter orders", "g|3|all|n")]
