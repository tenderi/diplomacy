"""How updates reach handlers: the commands ``main()`` registers, the inline-button
router (``app.button_callback``) and the reply-keyboard router (``ui.handle_menu_buttons``).

Buttons outlive the code that drew them -- they sit under old messages in players'
chats -- so the legacy callback prefixes are routed to their modern screens and
pinned here.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telegram.ext import Application, CommandHandler

from server.telegram_bot import app as bot_app
from server.telegram_bot import games as bot_games
from server.telegram_bot import help_text
from server.telegram_bot import ui

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def registered_commands() -> set[str]:
    """Run ``main()`` up to polling and collect every CommandHandler's commands."""
    built: list[Application] = []
    with patch.object(bot_app, "TELEGRAM_TOKEN", "123456:TEST-TOKEN"), \
         patch.object(bot_app, "API_URL", "http://api:8000"), \
         patch.object(bot_app, "wait_for_api_health"), \
         patch.object(Application, "run_polling", autospec=True, side_effect=lambda self, **_kw: built.append(self)):
        bot_app.main()
    assert len(built) == 1
    return {cmd for group in built[0].handlers.values() for h in group if isinstance(h, CommandHandler) for cmd in h.commands}


def _slash_commands(*texts: str) -> set[str]:
    return {m.lower() for text in texts for m in re.findall(r"(?<![\w/])/([a-z_]+)", text)}


class TestRegistration:
    def test_every_command_offered_in_telegrams_menus_is_handled(self, registered_commands: set[str]) -> None:
        offered = {c.command for c in bot_app.BOT_COMMANDS + bot_app.GROUP_BOT_COMMANDS}
        assert offered - registered_commands == set()

    def test_every_command_the_bot_teaches_is_handled(self, registered_commands: set[str]) -> None:
        taught = _slash_commands(help_text.HELP_TEXT, help_text.RULES_TEXT, help_text.EXAMPLES_TEXT,
                                 bot_games.WELCOME_TEXT, bot_games.GROUP_WELCOME)
        assert taught, "the extractor found nothing -- the texts changed shape"
        assert taught - registered_commands == set()

    def test_commands_allowed_in_a_group_exist(self, registered_commands: set[str]) -> None:
        assert bot_app.GROUP_COMMANDS - registered_commands == set()


def _press(data: str) -> tuple[Mock, Mock, Mock]:
    query = Mock(data=data, from_user=Mock(id=555))
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.chat.type = "private"
    update = Mock(callback_query=query)
    context = Mock(user_data={"pending_orders": {"7": {"x": 1}}, "order_walk": {"7": {"y": 2}}})
    return update, query, context


# (callback data, handler patched on the app module, expected call args; U/Q/C stand
# for the update, the query and the context).
U, Q, C = object(), object(), object()
ROUTES = [
    ("g|7|hub", "handle_game_callback", (Q, C, "g|7|hub")),
    ("select_game_7", "show_power_selection", (U, "7")),
    ("join_game_7_FRANCE", "join_from_button", (Q, C, "7", "FRANCE")),
    ("find_game", "find_game", (U, C)),
    ("back_to_games", "find_game", (U, C)),
    ("my_games", "games_list_callback", (Q,)),
    ("show_map_menu", "games_list_callback", (Q,)),  # a pre-game-menu screen
    ("orders_menu_7_FRANCE", "handle_game_callback", (Q, C, "g|7|hub")),
    ("view_orders_7_FRANCE", "handle_game_callback", (Q, C, "g|7|view")),
    ("clear_orders_7_FRANCE", "handle_game_callback", (Q, C, "g|7|clr")),
    ("order_history_7", "handle_game_callback", (Q, C, "g|7|hist")),
    ("demo_orders_7", "handle_game_callback", (Q, C, "g|7|all")),
    ("view_map_7", "send_game_map", (U, C, "7")),
    ("view_default_map", "send_default_map", (U, C)),
    ("start_demo_game", "start_demo_game", (U, C)),
    ("back_to_main_menu", "show_main_menu", (U, C)),
    ("join_waiting_list", "wait", (U, C)),
    ("selunit|7|F STP/SC", "show_possible_moves", (Q, C, "7", "F STP/SC")),
    ("supopt|7|A PAR", "show_support_options", (Q, C, "7", "A PAR")),
    ("suporig|7|A PAR|BUR", "show_support_choices", (Q, C, "7", "A PAR", "BUR")),
    ("cvopt|7|F NTH", "show_convoy_options", (Q, C, "7", "F NTH")),
    ("cvorig|7|F NTH|LON", "show_convoy_destinations", (Q, C, "7", "F NTH", "LON")),
    ("wlk|7|skip", "handle_walk_action", (Q, C, "7", "skip")),
]


@pytest.mark.parametrize(("data", "target", "expected"), ROUTES, ids=[r[0] for r in ROUTES])
def test_each_button_reaches_its_screen(data: str, target: str, expected: tuple) -> None:
    update, query, context = _press(data)
    with patch.object(bot_app, target, new=AsyncMock()) as handler:
        asyncio.run(bot_app.button_callback(update, context))
    query.answer.assert_awaited_once_with()
    stand_in = {id(U): update, id(Q): query, id(C): context}
    handler.assert_awaited_once_with(*(stand_in.get(id(a), a) for a in expected))


def test_cancel_forgets_that_games_pending_choices_only() -> None:
    update, query, context = _press("cancelunit|7")
    context.user_data["pending_orders"]["9"] = {"keep": 1}
    asyncio.run(bot_app.button_callback(update, context))
    assert context.user_data == {"pending_orders": {"9": {"keep": 1}}, "order_walk": {}}
    query.edit_message_text.assert_awaited_once_with("❌ Selection cancelled for game 7.")


def test_an_expired_order_button_says_so_instead_of_submitting() -> None:
    update, query, context = _press("ord|7|3")
    with patch.object(bot_app, "submit_interactive_order", new=AsyncMock()) as submit:
        asyncio.run(bot_app.button_callback(update, context))
    submit.assert_not_awaited()
    assert "expired" in query.edit_message_text.call_args[0][0]


def test_process_turn_confirmation_runs_it_as_the_presser() -> None:
    update, _query, context = _press("ptforce|7")
    with patch.object(bot_app, "run_process_turn", new=AsyncMock()) as run:
        asyncio.run(bot_app.button_callback(update, context))
    assert run.call_args[0][1:] == ("7", "555")


def test_a_button_forwarded_into_a_group_does_nothing() -> None:
    update, query, context = _press("g|7|hub")
    query.message.chat.type = "supergroup"
    with patch.object(bot_app, "handle_game_callback", new=AsyncMock()) as handler:
        asyncio.run(bot_app.button_callback(update, context))
    handler.assert_not_awaited()
    assert query.answer.call_args[1] == {"show_alert": True}


def _typed(text: str) -> tuple[Mock, Mock]:
    update, context = Mock(), Mock(user_data={})
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update, context


@pytest.mark.parametrize(("text", "target"), [
    (bot_games.MENU_MY_GAMES, "games"),
    ("📋 My Orders", "games"),  # the old eight-key keyboard, still on some phones
    (bot_games.MENU_FIND_GAME, "find_game"),
    ("⏳ Join Waiting List", "find_game"),
    (bot_games.MENU_HELP, "show_help"),
])
def test_each_keyboard_key_opens_its_screen(text: str, target: str) -> None:
    update, context = _typed(text)
    with patch.object(ui, "handle_awaited_text", new=AsyncMock(return_value=False)), \
         patch.object(ui, target, new=AsyncMock()) as handler:
        asyncio.run(ui.handle_menu_buttons(update, context))
    handler.assert_awaited_once_with(update, context)


def test_an_awaited_answer_is_consumed_before_any_key_matches() -> None:
    update, context = _typed(bot_games.MENU_MY_GAMES)
    with patch.object(ui, "handle_awaited_text", new=AsyncMock(return_value=True)), \
         patch.object(ui, "games", new=AsyncMock()) as games:
        asyncio.run(ui.handle_menu_buttons(update, context))
    games.assert_not_awaited()


def test_other_text_gets_a_pointer_not_silence() -> None:
    update, context = _typed("hello?")
    with patch.object(ui, "handle_awaited_text", new=AsyncMock(return_value=False)):
        asyncio.run(ui.handle_menu_buttons(update, context))
    assert "/help" in update.message.reply_text.call_args[0][0]
