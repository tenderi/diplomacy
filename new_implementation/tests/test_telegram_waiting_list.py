"""The bot's `/wait` and `/unwait` are thin clients over `/waiting_list/*` (G5).

This file used to test `telegram_bot.games.process_waiting_list`, a bot-side
function that held the queue in a module global, decided when it was full, created
the game, assigned powers, and "notified" players through a callback whose entire
body was a log line. All of that moved server-side, where the queue survives a
restart and filling it is atomic — see `tests/test_waiting_list.py`, which covers
what those tests were reaching for plus the mid-fill failure case they never had.

Worth noting about the tests that were here: they passed a *fake* notify callback
and asserted `len(notified) == 7`, so they looked like proof that seven players
were notified. In production the real callback only wrote a log line, and the
tests could not tell the difference — the injected fake was the only thing that
ever behaved correctly. That is why the new tests assert against the actual HTTP
payloads instead.

What is left to test here is what the bot still owns: calling the endpoint and
rendering the reply. The reply text matters because the six players who were
*already* queued are now DM'd by the server, so this reply is only for the one who
tipped the queue over.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from server.telegram_bot.games import WAITING_LIST_SIZE, leave_waiting_list, wait

pytestmark = pytest.mark.unit


def _update(user_id: int = 4242, first: str = "Ada", last: str | None = "Lovelace"):
    update = Mock()
    user = Mock()
    user.id = user_id
    user.first_name = first
    user.last_name = last
    update.effective_user = user
    update.message = Mock()
    update.message.reply_text = AsyncMock()
    return update


def _reply(update) -> str:
    return update.message.reply_text.call_args.args[0]


def test_wait_posts_to_the_waiting_list_endpoint() -> None:
    """The bot must not keep any queue state of its own — just call the API."""
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {
            "status": "queued", "size": 3, "required": 7, "game_created": False,
        }
        asyncio.run(wait(update, Mock()))

    endpoint, payload = mock_post.call_args.args
    assert endpoint == "/waiting_list/join"
    assert payload == {"telegram_id": "4242", "full_name": "Ada Lovelace"}
    assert "3/7" in _reply(update)


def test_wait_reports_the_server_reported_size_not_a_local_count() -> None:
    """A local counter would drift from the durable queue; there isn't one any more."""
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {
            "status": "queued", "size": 6, "required": 7, "game_created": False,
        }
        asyncio.run(wait(update, Mock()))
    assert "6/7" in _reply(update)


def test_wait_when_already_queued_says_so() -> None:
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {
            "status": "already_queued", "size": 2, "required": 7, "game_created": False,
        }
        asyncio.run(wait(update, Mock()))
    reply = _reply(update)
    assert "already" in reply.lower()
    assert "2/7" in reply


def test_wait_that_fills_the_queue_reports_the_players_own_power() -> None:
    """The tipping player should learn their power, and that everyone was told."""
    update = _update(user_id=4242)
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {
            "status": "queued",
            "size": 0,
            "required": 7,
            "game_created": True,
            "game_id": "77",
            "assignments": {
                "ENGLAND": "1", "FRANCE": "4242", "GERMANY": "3", "ITALY": "4",
                "AUSTRIA": "5", "RUSSIA": "6", "TURKEY": "7",
            },
        }
        asyncio.run(wait(update, Mock()))

    reply = _reply(update)
    assert "77" in reply
    assert "FRANCE" in reply, reply
    assert "ENGLAND" not in reply, "showed another player's power"
    assert str(WAITING_LIST_SIZE) in reply


def test_wait_survives_a_game_created_response_without_assignments() -> None:
    """Don't crash if the server omits assignments; just skip the power line."""
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {
            "status": "queued", "size": 0, "required": 7,
            "game_created": True, "game_id": "88", "assignments": None,
        }
        asyncio.run(wait(update, Mock()))
    assert "88" in _reply(update)


def test_wait_reports_an_api_failure_without_raising() -> None:
    """A bot command must never surface a traceback to the player."""
    update = _update()
    with patch("server.telegram_bot.games.api_post", side_effect=RuntimeError("boom")):
        asyncio.run(wait(update, Mock()))
    reply = _reply(update)
    assert "❌" in reply
    assert "Register" in reply, "an unregistered user gets no hint about what to do"


def test_wait_with_no_user_context_is_a_no_op() -> None:
    update = _update()
    update.effective_user = None
    with patch("server.telegram_bot.games.api_post") as mock_post:
        asyncio.run(wait(update, Mock()))
    assert not mock_post.called


def test_unwait_leaves_the_queue() -> None:
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {"status": "removed", "size": 2, "required": 7}
        asyncio.run(leave_waiting_list(update, Mock()))

    endpoint, payload = mock_post.call_args.args
    assert endpoint == "/waiting_list/leave"
    assert payload == {"telegram_id": "4242"}
    assert "Removed" in _reply(update)


def test_unwait_when_not_queued_says_so() -> None:
    update = _update()
    with patch("server.telegram_bot.games.api_post") as mock_post:
        mock_post.return_value = {"status": "not_queued", "size": 0, "required": 7}
        asyncio.run(leave_waiting_list(update, Mock()))
    assert "weren't" in _reply(update)


def test_unwait_reports_an_api_failure_without_raising() -> None:
    update = _update()
    with patch("server.telegram_bot.games.api_post", side_effect=RuntimeError("boom")):
        asyncio.run(leave_waiting_list(update, Mock()))
    assert "❌" in _reply(update)


def test_bot_holds_no_queue_state() -> None:
    """Regression guard for the whole G5 finding.

    The queue must not come back as a module global. It was one for the project's
    entire history, and every deploy silently dropped it along with everyone in it.
    """
    from server.telegram_bot import games

    assert not hasattr(games, "WAITING_LIST"), (
        "the in-memory waiting list is back; it cannot survive a bot restart"
    )
    assert not hasattr(games, "process_waiting_list"), (
        "queue-filling logic is back in the bot; it belongs to the server, where "
        "entries can be claimed atomically"
    )
