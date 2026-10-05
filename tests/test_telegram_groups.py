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
from telegram.ext import Application, ApplicationBuilder, ApplicationHandlerStop

from server.telegram_bot import app as bot_app
from server.telegram_bot import games as bot_games
from server.telegram_bot import channel_commands
from server.telegram_bot.api_client import ApiError
from server.telegram_bot.channel_commands import newgame
from server.telegram_bot.notifications import _send_outbox_item

pytestmark = pytest.mark.unit

GROUP_CHAT = -1001234


def _bot_application() -> Application:
    """An Application wired exactly like production (``main()``), never started."""
    application = ApplicationBuilder().token("123456:TEST").build()
    bot_app.register_handlers(application)
    return application


BOT_APPLICATION = _bot_application()


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
    # The bot has no admin rights by default: deleting the command is refused.
    update.message.delete = AsyncMock(side_effect=BadRequest("Message can't be deleted"))
    update.effective_chat.send_message = AsyncMock()
    update.message.is_topic_message = False
    context = Mock()
    context.bot = _bot()
    context.application = BOT_APPLICATION
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

    def test_a_private_command_is_deleted_when_the_bot_may_delete_it(self) -> None:
        update, context = _message_update("/rumour Italy will stab")
        update.message.delete = AsyncMock()
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))
        update.message.delete.assert_awaited_once()
        update.message.reply_text.assert_not_called()
        assert update.effective_chat.send_message.call_args[0][0] == (
            "🤫 I deleted that so the group can't read it. That command works in a private chat with me."
        )

    def test_a_private_command_is_stopped_even_when_the_pointer_cannot_be_sent(self) -> None:
        update, context = _message_update("/rumour Italy will stab")
        update.message.delete = AsyncMock()
        update.effective_chat.send_message = AsyncMock(side_effect=BadRequest("Topic_closed"))
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))

    def test_the_pointer_stays_in_the_commands_forum_topic(self) -> None:
        update, context = _message_update("/rumour Italy will stab")
        update.message.delete = AsyncMock()
        update.message.is_topic_message = True
        update.message.message_thread_id = 77
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))
        assert update.effective_chat.send_message.call_args[1]["message_thread_id"] == 77

    def test_a_private_command_the_bot_may_not_delete_gets_a_reply(self) -> None:
        update, context = _message_update("/rumour Italy will stab")
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))
        update.effective_chat.send_message.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == (
            "🤫 That command works in a private chat with me -- in a group, everyone would see it."
        )

    @pytest.mark.parametrize("command", ["/newgame", "/linkgroup 3", "/viewmap@DiplomacyTestBot", "/status"])
    def test_group_commands_pass(self, command: str) -> None:
        update, context = _message_update(command)
        asyncio.run(bot_app.group_command_guard(update, context))  # no ApplicationHandlerStop
        update.message.reply_text.assert_not_called()

    @pytest.mark.parametrize(
        "command",
        [
            "/rumour@OtherBot Italy will stab",  # one of ours by name, but addressed to another bot
            "/weather@OtherBot",
            "/weather",  # a command this bot doesn't have: not ours to take down
            "/weather@DiplomacyTestBot",  # addressed to us, but we don't have it
        ],
    )
    def test_other_bots_and_unknown_commands_are_left_alone(self, command: str) -> None:
        update, context = _message_update(command)
        update.message.delete = AsyncMock()
        asyncio.run(bot_app.group_command_guard(update, context))  # no ApplicationHandlerStop
        update.message.delete.assert_not_called()
        update.message.reply_text.assert_not_called()
        update.effective_chat.send_message.assert_not_called()

    @pytest.mark.parametrize(
        "command",
        [
            "/rumour Italy will stab",
            "/rumor x",
            "/RUMOUR x",
            "/rumour@DiplomacyTestBot x",
            "/Rumour@diplomacytestbot x",
            # Telegram's command entity ends at the first non-word character, and
            # python-telegram-bot dispatches on it: these run /rumour and /myorders.
            "/rumour,Italy will stab",
            "/myorders, please",
            "/rumour@DiplomacyTestBot,x",
        ],
    )
    def test_our_private_commands_are_taken_down_however_addressed(self, command: str) -> None:
        update, context = _message_update(command)
        update.message.delete = AsyncMock()
        with pytest.raises(ApplicationHandlerStop):
            asyncio.run(bot_app.group_command_guard(update, context))
        update.message.delete.assert_awaited_once()
        notice = update.effective_chat.send_message.call_args[0][0]
        assert "rumo" not in notice.lower()  # the group must not learn what was attempted

    def test_every_registered_command_is_recognised(self) -> None:
        commands = bot_app._registered_commands(BOT_APPLICATION)
        assert {"rumour", "rumor", "orderall", "message", "help", "newgame"} <= commands
        assert bot_app.GROUP_COMMANDS <= commands

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
    @pytest.fixture(autouse=True)
    def _group_has_no_game(self):  # type: ignore[no-untyped-def]
        with patch.object(channel_commands, "group_game", return_value=None):
            yield

    def test_a_group_with_another_players_game_gets_no_new_game(self) -> None:
        update, context = _message_update("/newgame public")
        with patch.object(channel_commands, "group_game", return_value="3"), \
             patch.object(channel_commands, "fetch_user_games", return_value=[{"game_id": "7", "power": "FRANCE"}]), \
             patch.object(channel_commands, "api_post") as post:
            asyncio.run(newgame(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == (
            "This group already plays Game 3, and a group has one game. Only a player of Game 3 can replace it."
        )

    def test_a_player_of_the_groups_game_may_replace_it(self) -> None:
        update, context = _message_update("/newgame public")
        with patch.object(channel_commands, "group_game", return_value="3"), \
             patch.object(channel_commands, "fetch_user_games", return_value=[{"game_id": "3", "power": "FRANCE"}]), \
             patch.object(channel_commands, "ensure_registered"), \
             patch.object(channel_commands, "api_post") as post:
            post.return_value = {"game_id": 42, "replaced_game_id": "3"}
            asyncio.run(newgame(update, context))
        post.assert_called_once_with("/games/create", {
            "map_name": "standard", "telegram_id": "555", "auto_process": True, "anonymous": False,
            "random_powers": False, "channel_id": str(GROUP_CHAT), "channel_name": "Friday Diplomacy",
        })
        assert update.message.reply_text.call_args[0][0].endswith("It replaces Game 3, which no longer belongs to this group.")

    def test_creates_a_group_game_and_posts_a_private_join_link(self) -> None:
        update, context = _message_update("/newgame public")
        with patch("server.telegram_bot.channel_commands.api_post") as post, \
             patch("server.telegram_bot.channel_commands.ensure_registered"):
            post.side_effect = lambda path, body: {"game_id": 42} if path == "/games/create" else {"status": "ok"}
            asyncio.run(newgame(update, context))
        # One call: the game is created linked to this group, or not at all (BB9).
        ((create_path, create_body),) = [c[0] for c in post.call_args_list]
        assert create_path == "/games/create"
        assert create_body["telegram_id"] == "555" and create_body["auto_process"] is True
        assert create_body["anonymous"] is False
        assert create_body["channel_id"] == str(GROUP_CHAT)
        button = update.message.reply_text.call_args[1]["reply_markup"].inline_keyboard[0][0]
        assert button.url == "https://t.me/DiplomacyTestBot?start=join_42"
        assert button.callback_data is None  # a link, never a callback button in a group

    @pytest.mark.parametrize("word, anonymous, says", [
        ("anonymous", True, "known only by their power"),
        ("Public", False, "nickname is shown next to their power"),
    ])
    def test_the_naming_choice_is_sent_and_announced(self, word: str, anonymous: bool, says: str) -> None:
        update, context = _message_update(f"/newgame {word}")
        with patch("server.telegram_bot.channel_commands.api_post") as post, \
             patch("server.telegram_bot.channel_commands.ensure_registered"):
            post.side_effect = lambda path, body: {"game_id": 42} if path == "/games/create" else {"status": "ok"}
            asyncio.run(newgame(update, context))
        assert post.call_args_list[0][0][1]["anonymous"] is anonymous
        assert says in update.message.reply_text.call_args[0][0]

    @pytest.mark.parametrize("text, random_powers", [
        ("/newgame public", False),
        ("/newgame anonymous random", True),
        ("/newgame random public", True),
    ])
    def test_random_deals_the_powers(self, text: str, random_powers: bool) -> None:
        update, context = _message_update(text)
        with patch("server.telegram_bot.channel_commands.api_post") as post, \
             patch("server.telegram_bot.channel_commands.ensure_registered"):
            post.side_effect = lambda path, body: {"game_id": 42} if path == "/games/create" else {"status": "ok"}
            asyncio.run(newgame(update, context))
        assert post.call_args_list[0][0][1]["random_powers"] is random_powers
        assert ("deal you a power at random" in update.message.reply_text.call_args[0][0]) is random_powers

    @pytest.mark.parametrize("text", [
        "/newgame", "/newgame secret", "/newgame anonymous public", "/newgame random", "/newgame public random random",
    ])
    def test_without_a_naming_choice_it_explains_both_and_creates_nothing(self, text: str) -> None:
        update, context = _message_update(text)
        with patch("server.telegram_bot.channel_commands.api_post") as post:
            asyncio.run(newgame(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == channel_commands.NEWGAME_CHOICE
        assert "/newgame anonymous" in channel_commands.NEWGAME_CHOICE
        assert "/newgame public" in channel_commands.NEWGAME_CHOICE

    def test_a_refused_link_reports_the_reason_and_announces_no_game(self) -> None:
        update, context = _message_update("/newgame public")
        refused = ApiError(
            "That Telegram group already belongs to game 3. Only a player of game 3 can move the group to another game.",
            response=Mock(status_code=409),
        )
        with patch.object(channel_commands, "api_post", side_effect=refused), \
             patch.object(channel_commands, "ensure_registered"), \
             patch.object(channel_commands, "set_current_game") as remember:
            asyncio.run(newgame(update, context))
        remember.assert_not_called()
        update.message.reply_text.assert_called_once_with(
            "❌ Could not create a game: That Telegram group already belongs to game 3. "
            "Only a player of game 3 can move the group to another game."
        )

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

    MINE = {"games": [{"game_id": "7", "power": "FRANCE"}]}

    def test_start_link_in_a_group_links_the_game_for_a_player(self) -> None:
        """BB2a: what Telegram sends to the group after t.me/<bot>?startgroup=link_7."""
        update, context = _message_update("/start link_7", chat_type="supergroup")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_post", return_value={"status": "ok", "replaced_game_id": "3"}) as post:
            asyncio.run(bot_games.start(update, context))
        post.assert_called_once_with("/games/7/channel/link", {
            "channel_id": str(GROUP_CHAT), "channel_name": "Friday Diplomacy", "telegram_id": "555",
        })
        text = update.message.reply_text.call_args[0][0]
        assert text.startswith("✅ Game 7 now belongs to this group")
        assert text.endswith("\n\nIt replaces Game 3, which no longer belongs to this group.")

    def test_start_link_in_a_group_links_nothing_for_a_non_player(self) -> None:
        update, context = _message_update("/start link_42")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_post") as post:
            asyncio.run(bot_games.start(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == "You are not in game 42."

    def test_start_link_in_a_private_chat_links_nothing(self) -> None:
        update, context = _message_update("/start link_7", chat_type="private")
        with patch.object(bot_games, "api_post") as register, \
             patch.object(channel_commands, "api_post") as link:
            asyncio.run(bot_games.start(update, context))
        link.assert_not_called()
        register.assert_called_once_with("/users/persistent_register", {"telegram_id": "555"})
        assert update.message.reply_text.call_args[0][0] == (
            "To link Game 7 to a Telegram group, add me to the group and send /linkgroup 7 there, "
            "or use \"Link a Telegram group\" on the game's web page and pick the group."
        )

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
        # The caller rides along: the API lets only a player of the group's
        # current game move the group to another.
        post.assert_called_once_with("/games/7/channel/link", {
            "channel_id": str(GROUP_CHAT), "channel_name": "Friday Diplomacy", "telegram_id": "555",
        })
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

    def test_linkgroup_names_the_game_it_replaced(self) -> None:
        update, context = _message_update("/linkgroup 7")
        with patch("server.telegram_bot.game_context.api_get", return_value=self.MINE), \
             patch.object(channel_commands, "api_post", return_value={"status": "ok", "replaced_game_id": "1"}):
            asyncio.run(channel_commands.linkgroup(update, context))
        assert update.message.reply_text.call_args[0][0].endswith(
            "\n\nIt replaces Game 1, which no longer belongs to this group."
        )

    def test_bare_unlinkgroup_detaches_the_groups_own_game(self) -> None:
        update, context = _message_update("/unlinkgroup")

        def lookup(endpoint: str, telegram_id: str | None = None) -> dict:
            return {"linked": True, "game_id": "7"} if endpoint == f"/channels/{GROUP_CHAT}/game" else self.MINE

        with patch("server.telegram_bot.game_context.api_get", side_effect=lookup), \
             patch("server.telegram_bot.game_context.current_game", return_value="3"), \
             patch.object(channel_commands, "api_get", return_value={"linked": True, "channel_id": GROUP_CHAT}), \
             patch.object(channel_commands, "api_delete", return_value={"status": "ok"}) as delete:
            asyncio.run(channel_commands.unlinkgroup(update, context))
        delete.assert_called_once_with("/games/7/channel/unlink")


class TestStatusInAGroup:
    """#158: /status typed in a group is about the group's game, not the
    caller's current game, and never says which power the caller plays."""

    STATE = {"year": 1901, "season": "Spring", "phase_type": "Movement", "phase": "S1901M"}

    def _run(self, chat_type: str, linked: dict, current: str = "1") -> tuple[Mock, list[str]]:
        update, context = _message_update("/status", chat_type=chat_type)
        mine = {"games": [{"game_id": "1", "power": "GERMANY"}, {"game_id": "2", "power": "FRANCE"}]}
        asked: list[str] = []

        def context_get(endpoint: str, telegram_id: str | None = None) -> dict:
            return linked if endpoint == f"/channels/{GROUP_CHAT}/game" else mine

        def games_get(endpoint: str, telegram_id: str | None = None) -> dict | None:
            asked.append(endpoint)
            return self.STATE if endpoint.endswith("/state") else None

        with patch("server.telegram_bot.game_context.api_get", side_effect=context_get), \
             patch("server.telegram_bot.game_context.current_game", return_value=current), \
             patch.object(bot_games, "api_get", side_effect=games_get):
            asyncio.run(bot_games.status(update, context))
        return update, asked

    def test_the_groups_game_not_the_callers_current_game(self) -> None:
        update, asked = self._run("supergroup", {"linked": True, "game_id": "2"}, current="1")
        text = update.message.reply_text.call_args[0][0]
        assert text.startswith("📊 *Game 2 Status*")
        assert asked[0] == "/games/2/state"
        assert "You are" not in text and "FRANCE" not in text

    def test_a_group_without_a_game_is_told_how_to_link_one(self) -> None:
        update, asked = self._run("group", {"linked": False})
        assert update.message.reply_text.call_args[0][0] == (
            "No game belongs to this group yet. A player can link one of their games with "
            "/linkgroup <game id>, or start a new one with /newgame."
        )
        assert asked == []

    def test_a_private_chat_still_uses_the_current_game_and_names_the_power(self) -> None:
        update, asked = self._run("private", {"linked": True, "game_id": "2"}, current="1")
        text = update.message.reply_text.call_args[0][0]
        assert asked[0] == "/games/1/state"
        assert "🎯 *You are:* GERMANY\n" in text

    def test_an_id_for_another_game_is_refused_in_the_group(self) -> None:
        update, context = _message_update("/status 1", chat_type="group")
        mine = {"games": [{"game_id": "1", "power": "GERMANY"}]}
        with patch("server.telegram_bot.game_context.api_get",
                   side_effect=lambda endpoint, telegram_id=None: (
                       {"linked": True, "game_id": "2"} if endpoint == f"/channels/{GROUP_CHAT}/game" else mine)), \
             patch.object(bot_games, "api_get") as games_get:
            asyncio.run(bot_games.status(update, context))
        games_get.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == (
            "This group's game is Game 2, and in the group I only show that one. "
            "Ask me about Game 1 in a private chat."
        )


class TestReadCommandsInAGroup:
    """BB7: /viewmap, /map and /players typed in a group are about the group's
    game, not the caller's current game; a private chat is unchanged."""

    MINE = {"games": [{"game_id": "1", "power": "GERMANY"}, {"game_id": "2", "power": "FRANCE"}]}

    def _run(self, text: str, chat_type: str, linked: dict) -> tuple[Mock, list[str]]:
        from server.telegram_bot import maps as bot_maps
        from server.telegram_bot import orders as bot_orders

        command = text.split()[0]
        handler = {"/viewmap": bot_orders.viewmap, "/map": bot_maps.map_command, "/players": bot_games.players}[command]
        update, context = _message_update(text, chat_type=chat_type)
        update.message.reply_photo = AsyncMock()
        update.callback_query = None
        asked: list[str] = []

        def context_get(endpoint: str, telegram_id: str | None = None) -> dict:
            return linked if endpoint == f"/channels/{GROUP_CHAT}/game" else self.MINE

        def games_get(endpoint: str, telegram_id: str | None = None) -> object:
            asked.append(endpoint)
            return [{"power": "FRANCE", "seated": True}] if endpoint.endswith("/players") else {}

        def map_bytes(endpoint: str) -> bytes:
            asked.append(endpoint)
            return b"\x89PNG"

        with patch("server.telegram_bot.game_context.api_get", side_effect=context_get), \
             patch("server.telegram_bot.game_context.current_game", return_value="1"), \
             patch.object(bot_games, "api_get", side_effect=games_get), \
             patch.object(bot_maps, "api_get_bytes", side_effect=map_bytes):
            asyncio.run(handler(update, context))
        return update, asked

    @pytest.mark.parametrize(("text", "first_call"), [
        ("/viewmap", "/games/2/map"), ("/map", "/games/2/map"), ("/players", "/games/2/players"),
        ("/viewmap 2", "/games/2/map"), ("/map 2", "/games/2/map"), ("/players 2", "/games/2/players"),
    ])
    def test_the_groups_game_not_the_callers_current_game(self, text: str, first_call: str) -> None:
        update, asked = self._run(text, "supergroup", {"linked": True, "game_id": "2"})
        assert asked[0] == first_call
        if text.startswith("/players"):
            assert update.message.reply_text.call_args[0][0] == "👥 *Players in Game 2*\n\n✅ *FRANCE*"
        else:
            assert update.message.reply_photo.call_args[1]["caption"] == "🗺️ *Game 2 Map*"

    @pytest.mark.parametrize("text", ["/viewmap", "/map", "/players"])
    def test_a_group_without_a_game_is_told_how_to_link_one(self, text: str) -> None:
        update, asked = self._run(text, "group", {"linked": False})
        assert asked == []
        assert update.message.reply_text.call_args[0][0] == (
            "No game belongs to this group yet. A player can link one of their games with "
            "/linkgroup <game id>, or start a new one with /newgame."
        )

    @pytest.mark.parametrize("text", ["/viewmap 1", "/map 1", "/players 1"])
    def test_an_id_for_another_game_is_refused(self, text: str) -> None:
        update, asked = self._run(text, "group", {"linked": True, "game_id": "2"})
        assert asked == []
        assert update.message.reply_text.call_args[0][0] == (
            "This group's game is Game 2, and in the group I only show that one. "
            "Ask me about Game 1 in a private chat."
        )

    @pytest.mark.parametrize(("text", "first_call"), [
        ("/viewmap", "/games/1/map"), ("/players", "/games/1/players"),
        ("/viewmap 2", "/games/2/map"), ("/map 2", "/games/2/map"), ("/players 2", "/games/2/players"),
    ])
    def test_a_private_chat_is_unchanged(self, text: str, first_call: str) -> None:
        update, asked = self._run(text, "private", {"linked": True, "game_id": "2"})
        assert asked[0] == first_call

    def test_a_bare_map_in_a_private_chat_still_asks_for_the_id(self) -> None:
        update, asked = self._run("/map", "private", {"linked": True, "game_id": "2"})
        assert asked == []
        assert update.message.reply_text.call_args[0][0] == "Usage: /map <game_id>"


class TestOlderChannelCommands:
    """/link_channel and friends, from before /linkgroup; still registered
    (/link_channel is now /linkgroup under its old name)."""

    def test_only_a_player_in_the_game_may_unlink(self) -> None:
        update, context = _message_update("/unlink_channel 42", chat_type="private", user_id=8019538)
        with patch.object(channel_commands, "fetch_user_games", return_value=[]), \
             patch.object(channel_commands, "api_delete") as delete:
            asyncio.run(channel_commands.unlink_channel(update, context))
        delete.assert_not_called()
        assert "You must be a player in game 42" in update.message.reply_text.call_args[0][0]

    @pytest.mark.parametrize("text", ["/link_channel 42 -1001", "/link_channel 42", "/link_channel"])
    def test_link_channel_in_a_private_chat_links_nothing(self, text: str) -> None:
        """BB9: it took any chat id, so a player could link their game to a
        group they aren't in and lock its members out of it."""
        update, context = _message_update(text, chat_type="private")
        with patch.object(channel_commands, "fetch_user_games", return_value=[{"game_id": "42", "power": "FRANCE"}]), \
             patch("server.telegram_bot.game_context.api_get", return_value={"games": [{"game_id": "42", "power": "FRANCE"}]}), \
             patch.object(channel_commands, "api_post") as post:
            asyncio.run(channel_commands.link_channel(update, context))
        post.assert_not_called()
        assert update.message.reply_text.call_args[0][0] == channel_commands.LINK_FROM_THE_GROUP

    def test_link_channel_in_a_group_links_that_group_whatever_id_is_typed(self) -> None:
        update, context = _message_update("/link_channel 42 -1001")
        with patch("server.telegram_bot.game_context.api_get", return_value={"games": [{"game_id": "42", "power": "FRANCE"}]}), \
             patch.object(channel_commands, "api_post", return_value={"status": "ok"}) as post:
            asyncio.run(channel_commands.link_channel(update, context))
        post.assert_called_once_with("/games/42/channel/link", {
            "channel_id": str(GROUP_CHAT), "channel_name": "Friday Diplomacy", "telegram_id": "555",
        })

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
