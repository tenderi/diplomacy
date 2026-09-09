"""Bot handlers when the home server is unreachable (Track J).

The player must get a "queued" reply -- never a stack trace and never silence
-- and the write must be in the durable outbox. ``requests`` is mocked at the
transport layer so the real ``api_post_reliable`` and outbox run.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import requests

from server.telegram_bot import api_client, app as bot_app, game_context
from server.telegram_bot.messages import broadcast, message
from server.telegram_bot.notifications import queue_status
from server.telegram_bot.orders import clearorders, order, submit_interactive_order
from server.telegram_bot.outbox import PENDING, reset_outbox_for_tests

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def fresh_outbox(tmp_path):
    return reset_outbox_for_tests(tmp_path / "outbox.sqlite3")


def _update(args, user_id=555):
    message_ = Mock()
    message_.reply_text = AsyncMock()
    update = Mock()
    update.message = message_
    update.effective_user = Mock(id=user_id, full_name="Tester")
    context = Mock()
    context.args = args
    return update, context, message_


def _down():
    return patch.object(api_client.requests, "post", side_effect=requests.ConnectionError("no route"))


def test_message_is_queued_with_a_clear_reply(fresh_outbox):
    update, context, msg = _update(["12", "france", "shall", "we", "ally?"])
    with _down():
        asyncio.run(message(update, context))
    text = msg.reply_text.call_args[0][0]
    assert "queued" in text and "/queue" in text and "Sent at" in text
    [entry] = fresh_outbox.pending(chat_id=555)
    assert entry.endpoint == "/games/12/message"
    assert entry.payload == {"telegram_id": "555", "recipient_power": "FRANCE", "text": "shall we ally?"}
    assert entry.state == PENDING and entry.attempts == 1
    assert 'message to FRANCE in game 12: "shall we ally?"' == entry.description


def test_broadcast_is_queued(fresh_outbox):
    update, context, msg = _update(["12", "hello", "all"])
    with _down():
        asyncio.run(broadcast(update, context))
    assert "queued" in msg.reply_text.call_args[0][0]
    [entry] = fresh_outbox.pending(chat_id=555)
    assert entry.endpoint == "/games/12/broadcast" and entry.payload["text"] == "hello all"


def test_order_resolves_power_from_cache_and_queues(fresh_outbox):
    # First, while online, the bot learns which power the user holds.
    with patch.object(game_context, "api_get", return_value={"games": [{"game_id": "3", "power": "GERMANY"}]}):
        game_context.fetch_user_games("555")
    update, context, msg = _update(["A", "BER", "-", "SIL;", "A", "MUN", "H"])
    with _down(), patch.object(game_context, "api_get", side_effect=api_client.ApiUnreachableError(OSError())):
        asyncio.run(order(update, context))
    assert "queued" in msg.reply_text.call_args[0][0]
    [entry] = fresh_outbox.pending(chat_id=555)
    assert entry.endpoint == "/games/set_orders"
    assert entry.payload == {"game_id": "3", "power": "GERMANY", "orders": ["A BER - SIL", "A MUN H"], "telegram_id": "555"}
    assert entry.description == "orders for game 3 (GERMANY): A BER - SIL; A MUN H"


def test_order_with_no_cache_and_no_server_says_unreachable(fresh_outbox):
    update, context, msg = _update(["A", "PAR", "H"], user_id=777)
    with _down(), patch.object(game_context, "api_get", side_effect=api_client.ApiUnreachableError(OSError())):
        asyncio.run(order(update, context))
    text = msg.reply_text.call_args[0][0]
    assert "unreachable" in text
    assert fresh_outbox.pending() == []


def test_clearorders_is_queued(fresh_outbox):
    with patch.object(game_context, "api_get", return_value={"games": [{"game_id": "3", "power": "GERMANY"}]}):
        game_context.fetch_user_games("555")
    update, context, msg = _update(["3"])
    with _down(), patch.object(game_context, "api_get", side_effect=api_client.ApiUnreachableError(OSError())):
        asyncio.run(clearorders(update, context))
    assert "queued" in msg.reply_text.call_args[0][0]
    [entry] = fresh_outbox.pending(chat_id=555)
    assert entry.endpoint == "/games/3/orders/GERMANY/clear"


def test_interactive_order_is_queued(fresh_outbox):
    query = Mock()
    query.from_user = Mock(id=555)
    query.edit_message_text = AsyncMock()
    with patch.object(game_context, "api_get", return_value={"games": [{"game_id": "3", "power": "GERMANY"}]}), _down():
        asyncio.run(submit_interactive_order(query, "3", "A BER - SIL"))
    assert "queued" in query.edit_message_text.call_args[0][0]
    assert fresh_outbox.pending(chat_id=555)[0].payload["orders"] == ["A BER - SIL"]


def test_clear_orders_button_is_queued(fresh_outbox):
    query = Mock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "clear_orders_3_GERMANY"
    query.from_user = Mock(id=555)
    update = Mock()
    update.callback_query = query
    with _down():
        asyncio.run(bot_app.button_callback(update, Mock()))
    assert "queued" in query.edit_message_text.call_args[0][0]
    assert fresh_outbox.pending(chat_id=555)[0].payload["orders"] == []


def test_queue_command_lists_pending_and_recent(fresh_outbox):
    update, context, msg = _update(["12", "GERMANY", "hi"])
    with _down():
        asyncio.run(message(update, context))
    update2, context2, msg2 = _update([])
    asyncio.run(queue_status(update2, context2))
    text = msg2.reply_text.call_args[0][0]
    assert "Queued (1)" in text and "message to GERMANY in game 12" in text
    assert "Game server:" in text


def test_when_server_answers_the_reply_is_the_normal_one(fresh_outbox):
    resp = Mock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = {"status": "ok", "message_id": 1}
    resp.raise_for_status.return_value = None
    update, context, msg = _update(["12", "france", "hi"])
    with patch.object(api_client.requests, "post", return_value=resp):
        asyncio.run(message(update, context))
    assert msg.reply_text.call_args[0][0] == "Message sent to FRANCE in game 12."
    assert fresh_outbox.pending() == []
