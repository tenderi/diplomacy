"""Playing in a Telegram group (bot side): /newgame, group-only visibility,
private commands refused in groups, and deep links into a private chat.

Every HTTP call is mocked; group membership comes from a fake
``bot.get_chat_member``.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.error import BadRequest
from telegram.ext import ApplicationHandlerStop

from server.telegram_bot import app as bot_app
from server.telegram_bot import games as bot_games
from server.telegram_bot import channel_commands
from server.telegram_bot.channel_commands import newgame
from server.telegram_bot.notifications import _send_outbox_item

pytestmark = pytest.mark.unit

GROUP_CHAT = -1001234


def _bot(member_of: set[int] = frozenset(), username: str = "DiplomacyTestBot") -> Mock:
    bot = Mock()
    bot.username = username

    async def get_chat_member(chat_id, user_id):
        if chat_id == "gone":
            raise BadRequest("Chat not found")
        return SimpleNamespace(status="member" if int(chat_id) in member_of else "left")

    bot.get_chat_member = get_chat_member
    return bot


def _message_update(text: str, chat_type: str = "group", user_id: int = 555) -> tuple[Mock, Mock]:
    update = Mock()
    update.effective_user = Mock(id=user_id, first_name="Pat", last_name=None, username="pat")
    update.effective_chat = Mock(id=GROUP_CHAT, type=chat_type, title="Friday Diplomacy")
    update.effective_message = update.message = Mock(text=text)
    update.message.reply_text = AsyncMock()
    context = Mock()
    context.bot = _bot()
    context.args = text.split()[1:]
    context.user_data = {}
    return update, context


class TestGroupGuard:
    def test_a_private_command_in_a_group_is_refused_with_a_link_to_a_private_chat(self) -> None:
        update, context = _message_update("/orderall")
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))
        text = update.message.reply_text.call_args[0][0]
        markup = update.message.reply_text.call_args[1]["reply_markup"]
        assert "private" in text
        assert markup.inline_keyboard[0][0].url == "https://t.me/DiplomacyTestBot?start=group"

    @pytest.mark.parametrize("command", ["/newgame", "/linkgroup 3", "/viewmap@DiplomacyTestBot", "/status"])
    def test_group_commands_pass(self, command: str) -> None:
        update, context = _message_update(command)
        asyncio.run(bot_app.group_command_guard(update, context))  # no ApplicationHandlerStop
        update.message.reply_text.assert_not_called()

    def test_private_chats_are_not_touched(self) -> None:
        update, context = _message_update("/orderall", chat_type="private")
        asyncio.run(bot_app.group_command_guard(update, context))
        update.message.reply_text.assert_not_called()

    def test_a_button_pressed_in_a_group_does_nothing_but_explain(self) -> None:
        query = Mock(data="g|3|all")
        query.message = Mock()
        query.message.chat = Mock(type="supergroup")
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = Mock(callback_query=query)
        asyncio.run(bot_app.button_callback(update, Mock(user_data={})))
        assert query.answer.call_args[1]["show_alert"] is True
        query.edit_message_text.assert_not_called()


class TestNewGame:
    def test_creates_a_group_game_and_posts_a_private_join_link(self) -> None:
        update, context = _message_update("/newgame")
        with patch("server.telegram_bot.channel_commands.api_post") as post, \
             patch("server.telegram_bot.channel_commands.ensure_registered"):
            post.side_effect = lambda path, body: {"game_id": 42} if path == "/games/create" else {"status": "ok"}
            asyncio.run(newgame(update, context))
        (create_path, create_body), (link_path, link_body) = [c[0] for c in post.call_args_list]
        assert create_path == "/games/create"
        assert create_body["telegram_id"] == "555" and create_body["auto_process"] is True
        assert link_path == "/games/42/channel/link" and link_body["channel_id"] == str(GROUP_CHAT)
        button = update.message.reply_text.call_args[1]["reply_markup"].inline_keyboard[0][0]
        assert button.url == "https://t.me/DiplomacyTestBot?start=join_42"
        assert button.callback_data is None  # a link, never a callback button in a group

    def test_in_a_private_chat_it_says_where_it_belongs(self) -> None:
        update, context = _message_update("/newgame", chat_type="private")
        with patch("server.telegram_bot.channel_commands.api_post") as post:
            asyncio.run(newgame(update, context))
        post.assert_not_called()
        assert "inside a Telegram group" in update.message.reply_text.call_args[0][0]


class TestOnlyYourGroupsGames:
    LISTING = {"games": [
        {"id": 1, "status": "active", "player_count": 1, "max_players": 7},
        {"id": 2, "status": "active", "player_count": 1, "max_players": 7, "channel_id": str(GROUP_CHAT)},
        {"id": 3, "status": "active", "player_count": 1, "max_players": 7, "channel_id": "-100999"},
    ]}

    def _find(self, member_of: set[int]) -> list[str]:
        query = Mock(data="find_game")
        query.message = Mock()
        query.message.chat = Mock(type="private")
        query.from_user = Mock(id=555)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = Mock(callback_query=query, effective_user=query.from_user)
        context = Mock(user_data={})
        context.bot = _bot(member_of)
        with patch("server.telegram_bot.hub.api_get", return_value=self.LISTING), \
             patch("server.telegram_bot.game_context.api_get", return_value={"games": []}):
            asyncio.run(bot_app.button_callback(update, context))
        markup = query.edit_message_text.call_args[1]["reply_markup"]
        return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data.startswith("select_game_")]

    def test_a_stranger_sees_only_games_without_a_group(self) -> None:
        assert self._find(set()) == ["select_game_1"]

    def test_a_member_also_sees_their_groups_game(self) -> None:
        assert self._find({GROUP_CHAT}) == ["select_game_1", "select_game_2"]

    def test_joining_another_groups_game_is_refused(self) -> None:
        query = Mock(from_user=Mock(id=555))
        query.edit_message_text = AsyncMock()
        context = Mock(user_data={}, bot=_bot(set()))
        with patch("server.telegram_bot.games.api_get", return_value={"linked": True, "channel_id": str(GROUP_CHAT)}), \
             patch("server.telegram_bot.games.api_post") as post:
            asyncio.run(bot_games.join_from_button(query, context, "2", "FRANCE"))
        post.assert_not_called()
        assert "group you're not in" in query.edit_message_text.call_args[0][0]

    def test_a_group_the_bot_was_removed_from_counts_as_not_a_member(self) -> None:
        assert asyncio.run(bot_games.is_group_member(_bot({1}), "gone", 555)) is False


class TestDeepLinks:
    def test_the_join_button_opens_the_seat_menu_in_private(self) -> None:
        update, context = _message_update("/start join_2", chat_type="private")
        context.bot = _bot({GROUP_CHAT})
        with patch("server.telegram_bot.games.api_post"), \
             patch("server.telegram_bot.games.api_get") as get:
            get.side_effect = lambda path, **_kw: (
                {"linked": True, "channel_id": str(GROUP_CHAT)} if path.endswith("/channel")
                else {"dummy_powers": []} if path.endswith("/state") else []
            )
            asyncio.run(bot_games.start(update, context))
        seats = update.message.reply_text.call_args[1]["reply_markup"]
        assert any(b.callback_data == "join_game_2_FRANCE" for row in seats.inline_keyboard for b in row)

    def test_start_in_a_group_explains_the_group_commands(self) -> None:
        update, context = _message_update("/start")
        with patch("server.telegram_bot.games.api_post") as post:
            asyncio.run(bot_games.start(update, context))
        post.assert_not_called()  # nobody is registered by a group /start
        assert "/newgame" in update.message.reply_text.call_args[0][0]


def test_a_group_post_gets_a_link_to_a_private_chat_not_a_callback() -> None:
    bot = Mock(username="DiplomacyTestBot")
    bot.send_message = AsyncMock()
    item = {"id": 1, "kind": "channel_text", "message": "🔔 Turn Processed - Game 2",
            "payload": {"dm_start": "orders_2"}}
    asyncio.run(_send_outbox_item(bot, GROUP_CHAT, item))
    button = bot.send_message.call_args[1]["reply_markup"].inline_keyboard[0][0]
    assert button.url == "https://t.me/DiplomacyTestBot?start=orders_2"
    assert "private" in button.text


class TestLinkingAnExistingGame:
    MINE = {"games": [{"game_id": "7", "power": "FRANCE"}]}

    def test_linkgroup_attaches_your_current_game_to_this_group(self) -> None:
        update, context = _message_update("/linkgroup")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_post", return_value={"status": "ok"}) as post:
            asyncio.run(channel_commands.linkgroup(update, context))
        post.assert_called_once_with("/games/7/channel/link", {"channel_id": str(GROUP_CHAT), "channel_name": "Friday Diplomacy"})
        assert update.message.reply_text.call_args[0][0].startswith("✅ Game 7 now belongs to this group")

    def test_linkgroup_of_a_game_you_are_not_in_links_nothing(self) -> None:
        update, context = _message_update("/linkgroup 42")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_post") as post:
            asyncio.run(channel_commands.linkgroup(update, context))
        post.assert_not_called()

    @pytest.mark.parametrize("command", ["linkgroup", "unlinkgroup", "newgame"])
    def test_group_commands_in_a_private_chat_explain_where_they_belong(self, command: str) -> None:
        update, context = _message_update(f"/{command}", chat_type="private")
        with patch.object(channel_commands, "api_post") as post:
            asyncio.run(getattr(channel_commands, command)(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == f"/{command} works inside a Telegram group: add me to your group and send it there."

    def test_unlinkgroup_only_from_the_group_the_game_belongs_to(self) -> None:
        update, context = _message_update("/unlinkgroup 7")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_get", return_value={"linked": True, "channel_id": "-100999"}), \
             patch.object(channel_commands, "api_delete") as delete:
            asyncio.run(channel_commands.unlinkgroup(update, context))
        delete.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == "Game 7 isn't linked to this group."

    def test_unlinkgroup_from_its_own_group(self) -> None:
        update, context = _message_update("/unlinkgroup 7")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_get", return_value={"linked": True, "channel_id": GROUP_CHAT}), \
             patch.object(channel_commands, "api_delete", return_value={"status": "ok"}) as delete:
            asyncio.run(channel_commands.unlinkgroup(update, context))
        delete.assert_called_once_with("/games/7/channel/unlink")


class TestOlderChannelCommands:
    """/link_channel and friends, from before /linkgroup; still registered."""

    def test_only_a_player_in_the_game_may_link_or_unlink(self) -> None:
        for command, text in ((channel_commands.link_channel, "/link_channel 42 -1001"),
                              (channel_commands.unlink_channel, "/unlink_channel 42")):
            update, context = _message_update(text, chat_type="private", user_id=8019538)
            with patch.object(channel_commands, "fetch_user_games", return_value=[]), \
                 patch.object(channel_commands, "api_post") as post, \
                 patch.object(channel_commands, "api_delete") as delete:
                asyncio.run(command(update, context))
            post.assert_not_called()
            delete.assert_not_called()
            assert "You must be a player in game 42" in update.message.reply_text.call_args[0][0]

    @pytest.mark.parametrize(("args", "sent"), [
        ("auto_post_maps off", {"auto_post_maps": False}),
        ("auto_post_broadcasts yes", {"auto_post_broadcasts": True}),
        ("notification_level Important", {"notification_level": "important"}),
    ])
    def test_channel_settings_sends_a_typed_value(self, args: str, sent: dict) -> None:
        update, context = _message_update(f"/channel_settings 7 {args}", chat_type="private")
        with patch.object(channel_commands, "api_post", return_value={"status": "ok"}) as post:
            asyncio.run(channel_commands.channel_settings(update, context))
        post.assert_called_once_with("/games/7/channel/settings", sent)

    @pytest.mark.parametrize(("args", "reply"), [
        ("auto_post_maps", "Please provide a value for the setting."),
        ("notification_level loud", "Notification level must be: all, important, or none"),
        ("colour blue", "Unknown setting: colour"),
    ])
    def test_channel_settings_refuses_bad_input_locally(self, args: str, reply: str) -> None:
        update, context = _message_update(f"/channel_settings 7 {args}", chat_type="private")
        with patch.object(channel_commands, "api_post") as post:
            asyncio.run(channel_commands.channel_settings(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == reply
