"""The game menu (hub.py), the current game, and notification buttons.

Driven through the real callback router (``app.button_callback``) and command
handlers; every HTTP call is mocked.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

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


def test_start_still_shows_the_menu_when_the_server_is_down() -> None:
    update = Mock()
    update.effective_user = Mock(id=555, first_name="Pat", last_name=None, username="pat")
    update.message.reply_text = AsyncMock()
    with patch("server.telegram_bot.games.api_post", side_effect=requests.ConnectionError("down")):
        asyncio.run(start(update, Mock(args=[])))
    text = update.message.reply_text.call_args[0][0]
    assert "isn't answering" in text
    assert update.message.reply_text.call_args[1]["reply_markup"] is not None


def test_a_dm_with_buttons_is_sent_with_them() -> None:
    bot = Mock()
    bot.send_message = AsyncMock()
    item = {"id": 1, "kind": "dm", "message": "The turn has been processed for game 3.",
            "created_at": None,
            "payload": {"buttons": [[{"text": "📝 Enter orders", "callback_data": "g|3|all|n"}]]}}
    asyncio.run(_send_outbox_item(bot, 555, item))
    markup = bot.send_message.call_args[1]["reply_markup"]
    assert _buttons(markup) == [("📝 Enter orders", "g|3|all|n")]


class TestGamesList:
    def _games(self, listed: list[dict]) -> Mock:
        update = Mock()
        update.effective_user = Mock(id=555)
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        with patch("server.telegram_bot.game_context.api_get", return_value={"games": listed}), \
             patch("server.telegram_bot.hub.api_get", side_effect=_hub_api_get), \
             patch("server.telegram_bot.games.api_get", side_effect=_hub_api_get):
            asyncio.run(hub.games(update, Mock(args=[])))
        return update.message.reply_text

    def test_no_games_points_to_finding_one(self) -> None:
        reply = self._games([])
        assert reply.call_args[0][0].startswith("🎮 *You're not in any games yet.*")
        assert _buttons(reply.call_args[1]["reply_markup"]) == [("🎲 Find a game", "find_game")]

    def test_a_single_game_opens_straight_into_its_menu(self) -> None:
        reply = self._games([{"game_id": "3", "power": "GERMANY"}])
        assert "Game 3 · GERMANY" in reply.call_args[0][0]

    def test_several_games_are_listed_with_the_current_one_starred(self) -> None:
        set_current_game("555", "5")
        reply = self._games(TWO_GAMES["games"])
        assert _buttons(reply.call_args[1]["reply_markup"]) == [
            ("Game 3 · GERMANY", "g|3|hub"), ("⭐ Game 5 · FRANCE", "g|5|hub"), ("🎲 Find another game", "find_game"),
        ]


class TestMenuActions:
    def test_a_finished_game_offers_only_what_still_makes_sense(self, two_games) -> None:
        def ended(path: str, **kw):
            return {**STATE, "status": "COMPLETED"} if path.endswith("/state") else _hub_api_get(path, **kw)
        with patch("server.telegram_bot.hub.api_get", side_effect=ended), \
             patch("server.telegram_bot.games.api_get", side_effect=ended):
            query, _ = _press("g|3|hub")
        assert [d for _t, d in _buttons(query.edit_message_text.call_args[1]["reply_markup"])] == [
            "g|3|map", "g|3|hist", "g|3|msgs", "my_games",
        ]

    def test_a_player_who_asked_to_wait_gets_the_ready_key(self, two_games) -> None:
        def waiting(path: str, **kw):
            if path.endswith("/orders_status"):
                return {"submitted": [], "missing": [], "auto_process": True, "waiting": ["GERMANY"]}
            return _hub_api_get(path, **kw)
        with patch("server.telegram_bot.hub.api_get", side_effect=waiting), \
             patch("server.telegram_bot.games.api_get", side_effect=waiting):
            query, _ = _press("g|3|hub")
        datas = [d for _t, d in _buttons(query.edit_message_text.call_args[1]["reply_markup"])]
        assert "g|3|rd" in datas and "g|3|nr" not in datas

    def test_clearing_asks_first_then_clears_this_power(self, two_games) -> None:
        query, _ = _press("g|3|clr")
        assert ("🗑 Yes, clear them", "g|3|clrok") in _buttons(query.edit_message_text.call_args[1]["reply_markup"])
        done = SimpleNamespace(status="delivered", response={}, error=None)
        with patch("server.telegram_bot.hub.api_post_reliable", return_value=done) as post:
            query, _ = _press("g|3|clrok")
        assert post.call_args[0] == ("/games/3/orders/GERMANY/clear", {"telegram_id": "555"})
        assert query.edit_message_text.call_args[0][0] == "🗑 Your orders in game 3 for this turn have been cleared."

    def test_the_map_arrives_as_a_photo_with_next_steps(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get_bytes", return_value=b"\x89PNG") as get:
            query, _ = _press("g|3|map")
        get.assert_called_once_with("/games/3/map")
        kwargs = query.message.reply_photo.call_args[1]
        assert kwargs["photo"].read() == b"\x89PNG" and kwargs["caption"] == "🗺 Game 3"
        assert _buttons(kwargs["reply_markup"]) == [("📝 Enter orders", "g|3|all"), ("🎮 Game menu", "g|3|hub")]

    def test_a_map_that_cannot_be_drawn_says_so(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get_bytes", side_effect=requests.ConnectionError("down")):
            query, _ = _press("g|3|map")
        query.message.reply_photo.assert_not_called()
        assert query.message.reply_text.call_args[0][0].startswith("❌ Could not draw the map for game 3")

    def test_messages_offer_a_key_per_other_seated_player(self, two_games) -> None:
        players = [{"power": "GERMANY", "user_id": 1}, {"power": "FRANCE", "user_id": 2},
                   {"power": "ITALY", "user_id": None}, {"power": "AUSTRIA", "user_id": 3}]
        with patch("server.telegram_bot.hub.api_get", return_value=players), \
             patch("server.telegram_bot.hub.recent_messages_text", return_value="No messages in game 3 yet."):
            query, _ = _press("g|3|msgs")
        assert _buttons(query.edit_message_text.call_args[1]["reply_markup"]) == [
            ("✉️ Austria", "g|3|msg|AUSTRIA"), ("✉️ France", "g|3|msg|FRANCE"),
            ("📣 Everyone", "g|3|msg|ALL"), ("⬅️ Game menu", "g|3|hub"),
        ]  # not yourself (GERMANY), not an empty seat (ITALY)

    def test_process_now_with_orders_missing_asks_for_confirmation(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", return_value={"missing": ["ITALY", "TURKEY"]}), \
             patch("server.telegram_bot.hub.run_process_turn", new=AsyncMock()) as run:
            query, _ = _press("g|5|pt")
        run.assert_not_awaited()
        assert query.edit_message_text.call_args[0][0] == "⚠️ Still waiting on: ITALY, TURKEY. Their units will hold if you process now."
        assert ("✅ Process anyway", "ptforce|5") in _buttons(query.edit_message_text.call_args[1]["reply_markup"])

    def test_process_now_with_everything_in_runs_it(self, two_games) -> None:
        with patch("server.telegram_bot.hub.api_get", return_value={"missing": []}), \
             patch("server.telegram_bot.hub.run_process_turn", new=AsyncMock()) as run:
            _press("g|5|pt")
        assert run.call_args[0][1:] == ("5", "555")

    def test_a_game_you_are_not_in_is_refused_before_any_action(self, two_games) -> None:
        with patch("server.telegram_bot.hub.run_process_turn", new=AsyncMock()) as run:
            query, _ = _press("g|42|pt")
        run.assert_not_awaited()
        assert "42" in query.edit_message_text.call_args[0][0]
